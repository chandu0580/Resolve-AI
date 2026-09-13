"""Trace recording. One JSON line per agent execution under traces/YYYY-MM-DD.jsonl (gitignored).

Guarantees: every free-text value written passes the PII guard; forbidden keys (raw text, reasoning) are rejected
by the TraceEvent schema; secrets are never part of any event.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from resolveai import config
from resolveai.schemas.trace import AgentTrace, ModelUsage, TraceEvent, TraceEventName
from resolveai.trust.pii import contains_unredacted_pii


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def config_hash() -> str:
    return hashlib.sha256(json.dumps(config.masked_summary(), sort_keys=True).encode()).hexdigest()[:12]


class TraceRecorder:
    def __init__(self, message_id: str, trace_id: str | None = None, prompt_versions: dict[str, str] | None = None):
        self.trace = AgentTrace(trace_id=trace_id or uuid.uuid4().hex, started_at=_now(), message_id=message_id,
                                config_hash=config_hash(), prompt_versions=prompt_versions or {})
        self._t0 = time.perf_counter()

    def event(self, name: TraceEventName | str, component: str, status: str = "ok", latency_ms: float = 0, **data: Any) -> TraceEvent:
        for k, v in data.items():
            if isinstance(v, str) and contains_unredacted_pii(v):
                raise ValueError(f"trace field '{k}' contains unredacted PII")
        ev = TraceEvent(name=TraceEventName(name), ts=_now(), component=component, status=status, latency_ms=latency_ms, data=data)
        self.trace.events.append(ev)
        return ev

    def usage(self, model: str, **fields: Any) -> None:
        self.trace.usage.append(ModelUsage(model=model, **fields))

    def finish(self, final_decision: str | None = None, error: str | None = None) -> AgentTrace:
        self.trace.finished_at = _now()
        self.trace.final_decision = final_decision
        self.trace.error = error
        return self.trace


class TraceStore:
    def __init__(self, root: Path | None = None):
        self.root = root or config.TRACE_DIR
        self.root.mkdir(parents=True, exist_ok=True)

    def write(self, trace: AgentTrace) -> Path:
        p = self.root / f"{trace.started_at[:10]}.jsonl"
        with p.open("a", encoding="utf-8") as f:
            f.write(trace.model_dump_json() + "\n")
        return p

    def read(self, trace_id: str) -> AgentTrace | None:
        for p in sorted(self.root.glob("*.jsonl")):
            for line in p.read_text(encoding="utf-8").splitlines():
                if f'"trace_id":"{trace_id}"' in line:
                    try:
                        return AgentTrace.model_validate_json(line)
                    except ValueError:   # a corrupted record is never served; a later intact copy may still exist
                        continue
        return None
