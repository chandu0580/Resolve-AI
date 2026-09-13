"""AgentState: the explicit, typed working memory of one ResolveAI execution. Operational data only: no hidden
chain-of-thought, no secrets, no unredacted PII (the context builder and LLM client refuse it)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from resolveai.intelligence.context import ContextBundle
from resolveai.intelligence.query import QueryPlan
from resolveai.schemas.core import (
    AutomationDecision,
    ClarificationPacket,
    ConversationContext,
    CustomerMessage,
    DraftResponse,
    EscalationResult,
    EvidenceRef,
    EvidenceSet,
    HandoffPacket,
    IntentResult,
    RiskFlags,
    VerificationResult,
)
from resolveai.trust.injection import InjectionCheck

StageStatus = Literal["ok", "skipped", "failed", "fallback"]
STAGES = ("pii_redaction", "context", "intent", "second_opinion", "retrieval", "evidence_gate", "risk", "policy", "draft", "verification", "output_gate", "handoff")


@dataclass
class AgentState:
    trace_id: str
    message: CustomerMessage
    context: ConversationContext = field(default_factory=ConversationContext)
    customer_author: str | None = None
    created_at: str | None = None
    bundle: ContextBundle | None = None
    intent: IntentResult | None = None
    plan: QueryPlan | None = None
    evidence: EvidenceSet | None = None
    risk: RiskFlags | None = None
    escalation: EscalationResult | None = None
    strategy: str | None = None                     # troubleshoot | clarify | canned | handoff
    draft: DraftResponse | None = None
    verification: VerificationResult | None = None
    decision: AutomationDecision | None = None
    handoff: HandoffPacket | None = None
    response: str = ""
    evidence_refs: list[str] = field(default_factory=list)
    stage_status: dict[str, StageStatus] = field(default_factory=dict)
    latency_ms: dict[str, float] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)
    llm_available: bool = True
    request_id: str = ""
    injection: InjectionCheck | None = None
    clarification: ClarificationPacket | None = None
    citations: list[EvidenceRef] = field(default_factory=list)
    current_stage: str = ""                                   # Phase 9: the stage running when an exception is raised
    failures: list[dict[str, str]] = field(default_factory=list)   # Phase 9: {category, stage, kind}; codes only

    def mark(self, stage: str, status: StageStatus, ms: float | None = None, error: str | None = None) -> None:
        self.stage_status[stage] = status
        if ms is not None:
            self.latency_ms[stage] = round(ms, 2)
        if error:
            self.errors[stage] = error[:300]
