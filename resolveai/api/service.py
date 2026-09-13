"""AgentService: owns the single ResolveAI instance the API uses (the same orchestrator as the CLI and the evaluation).

The agent loads in a background thread at startup so /health answers immediately and /ready reports progress; readiness
checks components without calling the LLM. Trace lookup reads the agent's own file-backed TraceStore.
"""
from __future__ import annotations

import json
import logging
import tempfile
import threading
import time
from collections.abc import Callable
from pathlib import Path

from resolveai import config
from resolveai.api.errors import ApiError
from resolveai.api.guards import AgentGate, RateLimiter
from resolveai.api.schemas import ResolveRequest, TraceSummary
from resolveai.api.settings import ApiSettings
from resolveai.observability import TraceStore
from resolveai.schemas.core import AgentResult, ConversationContext, ConversationTurn
from resolveai.schemas.trace import AgentTrace

log = logging.getLogger("resolveai.api")


class AgentService:
    def __init__(self, settings: ApiSettings, agent=None, agent_factory: Callable[[], object] | None = None):
        self.settings = settings
        self._agent = agent
        self._factory = agent_factory or self._default_factory
        self._state = "loaded" if agent is not None else "not_started"
        self._error: str | None = None
        self._lock = threading.Lock()
        self.gate = AgentGate(settings.max_queue, settings.queue_timeout_s)
        self.limiter = RateLimiter(settings.rate_limit_per_minute)             # POST /resolve
        self.read_limiter = RateLimiter(settings.read_rate_limit_per_minute)   # every other authenticated endpoint
        self.auth_failures = RateLimiter(settings.auth_failures_per_minute)    # failed authentication attempts per client address
        self.started = time.monotonic()
        self._fallback_store: TraceStore | None = None

    # ---------------------------------------------------------------- lifecycle
    def _default_factory(self):
        from resolveai.agent import AgentConfig, ResolveAI

        s = self.settings
        return ResolveAI(cfg=AgentConfig(use_llm=s.use_llm, write_traces=s.write_traces), trace_store=TraceStore(s.trace_dir) if s.write_traces else None)

    def load(self) -> None:
        with self._lock:
            if self._state in ("loaded", "loading"):
                return
            self._state = "loading"
        t0 = time.perf_counter()
        try:
            agent = self._factory()
        except Exception as e:  # noqa: BLE001 - surfaced through /ready, never as a traceback
            log.exception("agent load failed")
            self._error, self._state = type(e).__name__, "failed"
            return
        self._agent, self._state = agent, "loaded"
        log.info("agent loaded in %.1f s", time.perf_counter() - t0)

    def start_background_load(self) -> None:
        threading.Thread(target=self.load, name="resolveai-agent-load", daemon=True).start()

    @property
    def state(self) -> str:
        return self._state

    @property
    def agent(self):
        if self._state == "loaded":
            return self._agent
        if self._state == "failed":
            raise ApiError(503, "agent_unavailable", "The agent failed to load; see /api/v1/ready.")
        raise ApiError(503, "agent_not_ready", "The agent is still loading; see /api/v1/ready.", headers={"Retry-After": "10"})

    @property
    def trace_store(self) -> TraceStore:
        if self._state == "loaded" and getattr(self._agent, "traces", None) is not None:
            return self._agent.traces
        if self._fallback_store is None:
            self._fallback_store = TraceStore(self.settings.trace_dir)
        return self._fallback_store

    # ---------------------------------------------------------------- readiness (never calls the LLM)
    def readiness(self) -> dict:
        comps: dict = {"agent": {"state": self._state, **({"error": self._error} if self._error else {})}}
        ok = self._state == "loaded"
        if ok:
            a = self._agent
            rows = int(len(a.kb.rows)) if getattr(a, "kb", None) is not None else 0
            indexes = sorted(getattr(a.kb, "dense", {}).keys()) if rows else []
            comps["knowledge_base"] = {"ok": rows > 0 and bool(indexes), "rows": rows, "dense_indexes": len(indexes)}
            clf = getattr(getattr(a, "intents", None), "model", None)
            comps["intent_classifier"] = {"ok": clf is not None, "artifact": a.versions.classifier}
            comps["evidence_gate"] = {"ok": a.versions.evidence_gate != "none", "version": a.versions.evidence_gate, "policy": a.versions.policy}
            llm = getattr(a, "llm", None)
            comps["llm"] = {"status": "configured" if llm is not None else ("disabled" if not self.settings.use_llm else "not_configured"), "model": getattr(llm, "model", None),
                            "checked_live": False, "note": "readiness never calls the model; if it is down the agent falls back to handoff"}
            ok = ok and comps["knowledge_base"]["ok"] and comps["intent_classifier"]["ok"] and comps["evidence_gate"]["ok"]
        comps["trace_store"] = {"ok": self._trace_dir_writable()} if self.settings.write_traces else {"ok": True, "disabled": True}
        return {"ready": bool(ok and comps["trace_store"]["ok"]), "components": comps}

    def _trace_dir_writable(self) -> bool:
        try:
            d = Path(self.trace_store.root)
            d.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=d, prefix=".ready-", delete=True):
                pass
            return True
        except OSError:
            return False

    # ---------------------------------------------------------------- agent execution
    def resolve(self, req: ResolveRequest, request_id: str) -> AgentResult:
        agent = self.agent
        *earlier, current = req.conversation
        ctx = ConversationContext(turns=[ConversationTurn(role=t.role, text=t.text) for t in earlier])
        meta = req.metadata
        created_at = meta.timestamp.isoformat() if meta and meta.timestamp else None
        request_meta = {"channel": meta.channel, "locale": meta.locale} if meta else {}
        with self.gate.acquire():
            return agent.resolve(current.text, ctx, created_at=created_at, request_id=request_id, request_meta=request_meta, budget_s=self.settings.request_budget_s)

    # ---------------------------------------------------------------- traces
    def get_trace(self, trace_id: str) -> AgentTrace | None:
        return self.trace_store.read(trace_id)

    def recent_traces(self, limit: int, action: str | None = None) -> list[TraceSummary]:
        out: list[TraceSummary] = []
        skipped = 0
        root = Path(self.trace_store.root)
        for p in sorted(root.glob("*.jsonl"), reverse=True):
            for line in reverse_lines(p):
                if not line.strip():
                    continue
                try:
                    t = json.loads(line)
                    if action and t.get("final_decision") != action:
                        continue
                    row = summarize_trace(t)
                except (ValueError, KeyError, TypeError, AttributeError):
                    skipped += 1   # a corrupted or truncated line must not take the audit trail down; counted, never echoed
                    continue
                out.append(row)
                if len(out) >= limit:
                    break
            if len(out) >= limit:
                break
        if skipped:
            log.warning("skipped %d unreadable trace line(s) while listing traces", skipped)
        return out


def reverse_lines(path: Path, block: int = 1 << 16):
    """Lines of a file from last to first, read in blocks from the end, so listing the newest traces stops after `limit` rows instead
    of reading the whole day's file (measured: 20,000 traces, 108 MB, 629 ms p50 for 200 rows when the file was read whole).
    Splitting happens on raw newline bytes, so a multi-byte character across a block boundary is never cut."""
    with path.open("rb") as f:
        f.seek(0, 2)
        pos, tail = f.tell(), b""
        while pos > 0:
            step = min(block, pos)
            pos -= step
            f.seek(pos)
            parts = (f.read(step) + tail).split(b"\n")
            tail = parts[0]
            for raw in reversed(parts[1:]):
                yield raw.decode("utf-8", errors="replace")
        if tail:
            yield tail.decode("utf-8", errors="replace")


def summarize_trace(t: dict) -> TraceSummary:
    """One list row from a stored trace. Every field comes from events the trace already records; customer text is never stored."""
    ev = {e["name"]: e.get("data", {}) for e in t.get("events", [])}
    final = ev.get("handoff_created") or ev.get("clarification_created") or ev.get("escalation_decided") or {}
    predicted, second, gate_ev, policy_ev = ev.get("intent_predicted", {}), ev.get("second_opinion_used", {}), ev.get("evidence_evaluated", {}), ev.get("escalation_decided", {})
    usage = t.get("usage") or []
    return TraceSummary(trace_id=t["trace_id"], request_id=t.get("request_id", ""), started_at=t["started_at"], final_decision=t.get("final_decision"),
                        reason_code=final.get("reason_code"), pipeline_version=t.get("pipeline_version", ""), latency_ms=(t.get("latency_ms") or {}).get("total"), error=t.get("error"),
                        intent=(second.get("after") if second.get("applied") else None) or predicted.get("intent"), intent_confidence=predicted.get("confidence"),
                        confidence_band=predicted.get("band"), evidence_level=gate_ev.get("level"), evidence_sufficient=gate_ev.get("sufficient"),
                        risk_flags=list((ev.get("risk_flags_extracted") or {}).get("flags") or []), rule=policy_ev.get("rule"),
                        policy_version=(t.get("versions") or {}).get("policy") or policy_ev.get("policy_version"), channel=(t.get("request_meta") or {}).get("channel"),
                        llm_calls=sum(int(u.get("calls", 0)) for u in usage),
                        estimated_cost_usd=round(sum(float(u.get("estimated_cost_usd") or 0.0) for u in usage), 6) if usage else None)


def safe_runtime_config(service: AgentService) -> dict:
    """Configuration safe to expose: never keys, base URLs, absolute paths or environment dumps."""
    s = service.settings
    body = {"service": s.public_view(), "llm": {"configured": bool(config.LLM_API_KEY), "enabled": s.use_llm, "model": config.LLM_MODEL, "provider": "openai_compatible",
                                                "temperature": config.LLM_TEMPERATURE, "timeout_s": config.LLM_TIMEOUT_S, "max_retries": config.LLM_MAX_RETRIES},
            "embedding_model": config.EMBED_MODEL, "brand": config.BRAND, "agent_state": service.state}
    if service.state == "loaded":
        body["versions"] = service.agent.versions.model_dump()
    return body
