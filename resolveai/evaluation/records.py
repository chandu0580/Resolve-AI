"""One record per (system, golden row). Every evaluated system - ResolveAI, its ablations and the three baselines - writes
this same shape so that every metric, slice, judge call and report reads one format. Failed calls are recorded, never
dropped: `failed=True` rows stay in every denominator.

Response kinds: troubleshoot (LLM draft from evidence), canned (template), clarify (deterministic question),
handoff (deterministic handoff line), copy (a historical reply copied verbatim), llm_direct (LLM reply with no evidence).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

Action = Literal["AUTO_HANDLE", "CLARIFICATION_REQUIRED", "HUMAN_HANDOFF", "CHANNEL_REDIRECT"]
ResponseKind = Literal["troubleshoot", "canned", "clarify", "handoff", "copy", "llm_direct", "none"]


class EvidenceSnippet(BaseModel):
    evidence_id: str
    customer_message: str = ""
    brand_reply: str
    cited: bool = False


class SystemRecord(BaseModel):
    gid: str
    system: str
    message: str
    context: str = ""
    intent_pred: str
    intent_confidence: float | None = None
    intent_band: str | None = None
    escalate_pred: bool = Field(description="True iff the system routes the message to a human (HUMAN_HANDOFF)")
    action: Action
    response: str = ""
    response_kind: ResponseKind = "none"
    evidence: list[EvidenceSnippet] = Field(default_factory=list, description="evidence the system had available (top-k), cited ones flagged")
    evidence_sufficient: bool = False
    evidence_level: str = ""
    resolution_confidence: float | None = None
    verified: bool | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    reason_code: str = ""
    latency_ms: float = 0.0
    llm_calls: int = 0
    live_calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    failed: bool = False
    error: str = ""
    extra: dict = Field(default_factory=dict)


def write_records(path: Path, recs: list[SystemRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(r.model_dump_json() for r in recs) + "\n", encoding="utf-8")


def read_records(path: Path) -> list[SystemRecord]:
    return [SystemRecord.model_validate(json.loads(x)) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
