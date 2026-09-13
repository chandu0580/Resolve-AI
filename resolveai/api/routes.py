"""HTTP endpoints (/api/v1). One canonical agent endpoint, POST /resolve, runs the whole trusted pipeline and returns the
complete structured result. Separate analyze / draft / decision endpoints were not added: each would run the same pipeline
(a draft without the evidence gate, risk flags and policy would bypass the invariant), so they would be views of this one
response rather than different capabilities.

Authentication, scopes and rate limits are enforced before these handlers run (resolveai.api.access).
"""
from __future__ import annotations

import json
import logging
import re
import time

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import JSONResponse

from resolveai import config
from resolveai.api import API_VERSION, SERVICE_VERSION, product
from resolveai.api.errors import ApiError, ErrorBody, request_id_of
from resolveai.api.presenter import autonomy_violations, present
from resolveai.api.schemas import HealthResponse, ReadinessResponse, ResolveRequest, ResolveResponse, TraceListResponse
from resolveai.api.service import AgentService, safe_runtime_config
from resolveai.schemas.trace import AgentTrace

log = logging.getLogger("resolveai.api")
router = APIRouter(prefix=f"/api/{API_VERSION}")
TRACE_ID_RE = re.compile(r"^[a-f0-9]{32}$")
EVALUATION_DIR = config.ROOT / "artifacts" / "evaluation"
DEMO_FILE = config.DATA_DIR / "demo" / "scenarios.json"
ERRORS = {code: {"model": ErrorBody} for code in (400, 401, 403, 404, 411, 413, 422, 429, 500, 503)}


def _service(request: Request) -> AgentService:
    return request.app.state.service


def _check_limits(body: ResolveRequest, service: AgentService) -> None:
    s = service.settings
    turns = body.conversation
    if turns[-1].role != "customer":
        raise ApiError(400, "invalid_conversation", "The last turn must be the customer message to handle.")
    problems = []
    if len(turns) > s.max_turns:
        problems.append(f"conversation has {len(turns)} turns (max {s.max_turns})")
    if len(turns[-1].text) > s.max_message_chars:
        problems.append(f"customer message has {len(turns[-1].text)} characters (max {s.max_message_chars})")
    long_turns = [i for i, t in enumerate(turns[:-1]) if len(t.text) > s.max_turn_chars]
    if long_turns:
        problems.append(f"turns {long_turns[:5]} exceed {s.max_turn_chars} characters")
    total = sum(len(t.text) for t in turns)
    if total > s.max_total_chars:
        problems.append(f"conversation has {total} characters in total (max {s.max_total_chars})")
    if problems:
        raise ApiError(413, "input_too_large", "The conversation exceeds the configured input limits; nothing was processed.", details=problems)


@router.post("/resolve", response_model=ResolveResponse, tags=["agent"], responses=ERRORS, summary="Run one conversation through the ResolveAI agent",
             description="Runs the full pipeline (PII redaction, injection check, intent, retrieval, evidence gate, risk flags, deterministic policy, "
                         "draft / clarify / handoff, verification, output gate) and returns what happened, why, on which evidence, and what happens next. "
                         "Exactly one action is returned: AUTO_HANDLE, CLARIFICATION_REQUIRED or HUMAN_HANDOFF. A model outage, a model timeout or an "
                         "exhausted request time budget is not an HTTP error: the agent's deterministic fallback returns a safe clarification or handoff.")
def resolve(body: ResolveRequest, request: Request, response: Response) -> ResolveResponse:
    service = _service(request)
    _check_limits(body, service)
    result = service.resolve(body, request_id_of(request))
    violations = autonomy_violations(result)
    if violations:
        log.error("autonomy invariant violation request_id=%s trace_id=%s violations=%s", result.request_id, result.trace_id, violations)
        raise ApiError(500, "autonomy_invariant_violation", "The agent produced an automatic reply that failed the evidence invariant; the reply was withheld.",
                       trace_id=result.trace_id, details={"violations": violations})
    response.headers["X-Trace-ID"] = result.trace_id
    return present(result)


@router.get("/traces/{trace_id}", response_model=AgentTrace, tags=["audit"], responses=ERRORS, summary="Audit trace of one agent execution")
def get_trace(trace_id: str, request: Request) -> AgentTrace:
    trace_id = trace_id.strip().lower()   # canonical form is lowercase hex; an upper-case copy of the same id finds the same trace
    if not TRACE_ID_RE.fullmatch(trace_id):
        raise ApiError(400, "invalid_trace_id", "A trace id is 32 lowercase hexadecimal characters.")
    trace = _service(request).get_trace(trace_id)
    if trace is None:
        raise ApiError(404, "trace_not_found", "No trace with this id exists in the trace store.", trace_id=trace_id)
    return trace


@router.get("/traces", response_model=TraceListResponse, tags=["audit"], responses=ERRORS, summary="Most recent traces (newest first)")
def list_traces(request: Request, limit: int = Query(20, ge=1, le=200),
                action: str | None = Query(None, pattern="^(?i)(AUTO_HANDLE|CLARIFICATION_REQUIRED|HUMAN_HANDOFF)$", description="any capitalization")) -> TraceListResponse:
    return TraceListResponse(items=_service(request).recent_traces(limit, action.upper() if action else None), limit=limit)


@router.get("/health", response_model=HealthResponse, tags=["operations"], summary="Process liveness (no inference, no authentication)")
def health(request: Request) -> HealthResponse:
    s = _service(request)
    return HealthResponse(service="resolveai", version=SERVICE_VERSION, env=s.settings.env, uptime_s=round(time.monotonic() - s.started, 1))


def _component_ok(c: dict) -> bool:
    if "ok" in c:
        return bool(c["ok"])
    if "state" in c:
        return c["state"] == "loaded"
    return c.get("status") in ("configured", "disabled")


@router.get("/ready", response_model=ReadinessResponse, tags=["operations"], responses={503: {"model": ReadinessResponse}},
            summary="Readiness of runtime components (never calls the LLM; detail only for authenticated callers when auth is on)")
def ready(request: Request):
    body = _service(request).readiness()
    if request.app.state.settings.auth_required and request.scope.get("state", {}).get("principal") is None:
        body = {"ready": body["ready"], "components": {name: {"ok": _component_ok(c)} for name, c in body["components"].items()}}
    return JSONResponse(status_code=200 if body["ready"] else 503, content=ReadinessResponse(**body).model_dump())


@router.get("/config", tags=["operations"], responses=ERRORS, summary="Safe runtime configuration (no secrets)")
def runtime_config(request: Request) -> dict:
    return safe_runtime_config(_service(request))


@router.get("/evaluation/summary", tags=["evaluation"], responses=ERRORS, summary="Headline evaluation results from the frozen Phase 6 artifacts")
def evaluation_summary() -> dict:
    files = {"headline": "headline_metrics.json", "baselines": "baseline_comparison.json", "agreement": "judge_agreement.json"}
    if not all((EVALUATION_DIR / f).exists() for f in files.values()):
        raise ApiError(404, "evaluation_not_available", "Evaluation artifacts are missing; run python scripts/evaluate.py --cached.")
    data = {k: json.loads((EVALUATION_DIR / f).read_text(encoding="utf-8")) for k, f in files.items()}
    systems = {name: {k: v for k, v in s.items() if k in ("description", "intent", "escalation", "autonomy", "cost_latency", "judge")} for name, s in data["baselines"].get("systems", {}).items()}
    optional = {}
    for key, fname in (("retrieval", "retrieval_report.json"), ("reply_quality", "reply_quality.json")):
        if (EVALUATION_DIR / fname).exists():
            optional[key] = json.loads((EVALUATION_DIR / fname).read_text(encoding="utf-8"))
    texts = {key: (EVALUATION_DIR / fname).read_text(encoding="utf-8") for key, fname in (("misleading_headline_md", "misleading_headline.md"), ("statistical_uncertainty_md", "statistical_uncertainty.md"))
             if (EVALUATION_DIR / fname).exists()}
    return {"headline": data["headline"], "systems": systems, "pairwise_judge": data["baselines"].get("pairwise_judge", {}), "human_study": (data["agreement"].get("human") or {}).get("status"),
            "caveats": "See artifacts/evaluation/misleading_headline.md. The evaluated system is the Phase 5 configuration; Phase 7 changes are listed in artifacts/phase7/PHASE7_REPORT.md.",
            "agreement": data["agreement"], **optional, **texts,
            "provenance": {"golden_rows": data["headline"].get("n"), "golden_sha256": data["headline"].get("golden_sha256"), "source": "frozen Phase 6 artifacts (artifacts/evaluation); served as stored, nothing recomputed"}}


@router.get("/evaluation/release", tags=["evaluation"], responses=ERRORS, summary="Release 1.0.0 scorecard from the frozen release artifacts, by dataset")
def evaluation_release() -> dict:
    return product.release_view()


@router.get("/agent/profile", tags=["operations"], responses=ERRORS, summary="Active agent configuration next to the evaluated configuration (read-only, no secrets)")
def agent_profile(request: Request) -> dict:
    return product.agent_profile(_service(request))


@router.get("/knowledge/summary", tags=["operations"], responses=ERRORS, summary="Knowledge-base aggregates (counts and shares only, no message text)")
def knowledge_summary(request: Request) -> dict:
    return product.knowledge_summary(_service(request))


@router.get("/demo/scenarios", tags=["evaluation"], responses=ERRORS, summary="Synthetic demo scenarios and their expected outcomes")
def demo_scenarios() -> list[dict]:
    if not DEMO_FILE.exists():
        raise ApiError(404, "demo_not_available", "data/demo/scenarios.json is missing.")
    return json.loads(DEMO_FILE.read_text(encoding="utf-8"))
