"""API request and response models. The response embeds the agent's existing contracts (IntentResult, EvidenceSet,
RiskFlags, VerificationResult, ClarificationPacket, HandoffPacket, RuntimeVersions, ...) rather than redefining them; only
the request shape and the presentation wrappers (outcome, response) are API-specific.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from resolveai.schemas.core import (
    AgentAction,
    ClarificationPacket,
    ConversationContext,
    CustomerMessage,
    EvidenceRef,
    HandoffPacket,
    IntentResult,
    RiskFlags,
    RuntimeVersions,
    UsageSummary,
    VerificationResult,
)
from resolveai.schemas.evidence import EvidenceSet

ABS_MAX_TEXT = 20_000     # schema hard cap; the configured (lower) limits are enforced by the route with 413
ABS_MAX_TURNS = 200

EXAMPLE_REQUEST = {"conversation": [{"role": "customer", "text": "My iPhone keeps changing \"it\" to \"I.T\" whenever I type. How do I fix this autocorrect bug?"}],
                   "metadata": {"channel": "twitter", "locale": "en-US"}}


class TurnIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["customer", "brand"] = Field(description="who wrote the turn; the LAST turn must be the customer's")
    text: str = Field(min_length=1, max_length=ABS_MAX_TEXT, description="raw turn text; redacted by the agent before any storage or model call")


class RequestMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")
    channel: Literal["twitter", "email", "chat", "web", "api"] | None = None
    customer_id_hash: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$",
                                         description="SHA-256 hex of the caller's customer id. Validated and then discarded: never stored, traced or sent to a model. Raw ids or emails are rejected by the pattern.")
    timestamp: datetime | None = Field(default=None, description="when the customer message was sent; historical evidence must predate it")
    locale: str | None = Field(default=None, pattern=r"^[a-z]{2}(-[A-Z]{2})?$", description="e.g. en-US; recorded in the trace")


class ResolveRequest(BaseModel):
    """One customer conversation, oldest turn first, ending with the customer message to handle. Unknown fields (including any
    attempt to supply 'evidence', 'policy' or 'system' fields) are rejected: evidence only comes from the retrieval index."""
    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [EXAMPLE_REQUEST]})
    conversation: list[TurnIn] = Field(min_length=1, max_length=ABS_MAX_TURNS)
    metadata: RequestMetadata | None = None


class OutcomeView(BaseModel):
    """WHAT happened, WHY, on WHAT evidence, and WHAT happens next (from the agent's DecisionSummary plus gate details)."""
    action: AgentAction
    what_happened: str
    why: str
    evidence_basis: str
    next_step: str
    reason_code: str
    rule: str
    policy_version: str
    autonomous_response_allowed: bool
    output_gate: dict[str, bool] = Field(default_factory=dict, description="every output-gate check and whether it passed")
    blocking_checks: list[str] = Field(default_factory=list)


class ResponseView(BaseModel):
    kind: Literal["auto_reply", "template_reply", "clarifying_question", "handoff_notice"]
    text: str = Field(description="customer-facing text; for a handoff it is only a holding notice, never an answer")
    sent_automatically: bool = Field(description="true only for AUTO_HANDLE")
    evidence_refs: list[EvidenceRef] = Field(default_factory=list, description="citations for an auto_reply; empty for every other kind")
    draft_attempts: int = 0


class ConversationView(BaseModel):
    message: CustomerMessage = Field(description="the current customer message AFTER PII redaction")
    context: ConversationContext = Field(description="earlier turns AFTER PII redaction")


class ResolveResponse(BaseModel):
    request_id: str
    trace_id: str
    action: AgentAction
    outcome: OutcomeView
    response: ResponseView
    intent: IntentResult
    evidence: EvidenceSet
    risk: RiskFlags
    verification: VerificationResult | None = None
    clarification: ClarificationPacket | None = Field(default=None, description="present only for CLARIFICATION_REQUIRED")
    handoff: HandoffPacket | None = Field(default=None, description="present only for HUMAN_HANDOFF")
    conversation: ConversationView
    versions: RuntimeVersions
    stage_status: dict[str, str]
    latency_ms: dict[str, float]
    usage: UsageSummary


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: str
    version: str
    env: str
    uptime_s: float


class ReadinessResponse(BaseModel):
    ready: bool
    components: dict[str, Any]


class TraceSummary(BaseModel):
    trace_id: str
    request_id: str = ""
    started_at: str
    final_decision: str | None = None
    reason_code: str | None = None
    pipeline_version: str = ""
    latency_ms: float | None = None
    error: str | None = None
    intent: str | None = Field(default=None, description="final intent (after an applied second opinion)")
    intent_confidence: float | None = None
    confidence_band: str | None = None
    evidence_level: str | None = Field(default=None, description="INSUFFICIENT | WEAK | SUFFICIENT | STRONG")
    evidence_sufficient: bool | None = None
    risk_flags: list[str] = Field(default_factory=list)
    rule: str | None = Field(default=None, description="policy rule that fired at the policy stage")
    policy_version: str | None = None
    channel: str | None = None
    llm_calls: int | None = None
    estimated_cost_usd: float | None = Field(default=None, description="estimated model cost of the execution at list price (from the trace's usage records)")


class TraceListResponse(BaseModel):
    items: list[TraceSummary]
    limit: int
