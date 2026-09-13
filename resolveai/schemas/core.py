"""Core agent contracts (pydantic v2).

Design rules:
- Customer text is stored ONLY in redacted form (`CustomerMessage.text` is post-redaction). The raw tweet never
  enters these objects, so nothing downstream (LLM calls, traces, API responses) can leak PII.
- Every decision object carries the rule or check that produced it, so decisions are auditable.
- No free-text "reasoning" fields that could hold chain-of-thought; `reason` fields are short, customer-safe summaries.
"""
from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from resolveai.schemas.evidence import EvidenceItem, EvidenceSet, ResolutionCandidate  # noqa: F401  (Phase-2/5 evidence contracts)

Decision = Literal["auto_handle", "escalate"]
EscalationReason = Literal["safety", "prompt_injection", "legal_media", "abusive_threatening", "private_info", "account_access", "payment_billing", "sensitive_action", "hardware",
                           "repeat_contact", "human_requested", "vague_hostile", "taxonomy_gap_risk", "conflicting_evidence", "low_confidence", "insufficient_context",
                           "insufficient_evidence", "grounding_failed", "verification_failed", "output_gate", "llm_unavailable",
                           "model_timeout", "dependency_failure", "audit_unavailable", "none"]   # Phase 9: classified failures
AgentAction = Literal["AUTO_HANDLE", "HUMAN_HANDOFF", "CLARIFICATION_REQUIRED", "CHANNEL_REDIRECT"]


class CustomerMessage(BaseModel):
    """One inbound customer message, already PII-redacted."""
    message_id: str
    text: str = Field(description="PII-redacted customer text (typed tokens such as <PHONE>)")
    pii_counts: dict[str, int] = Field(default_factory=dict, description="redaction counts by type; the raw values are never stored")
    language_hint: str | None = None
    received_at: str | None = None


class ConversationTurn(BaseModel):
    role: Literal["customer", "brand"]
    text: str  # redacted


class ConversationContext(BaseModel):
    turns: list[ConversationTurn] = Field(default_factory=list, description="prior turns, oldest first")
    truncated: bool = False

    @property
    def brand_turns(self) -> int:
        return sum(1 for t in self.turns if t.role == "brand")


class IntentResult(BaseModel):
    """Classifier output. `intent` is the primary (predicted) intent; probabilities are calibrated when `calibrated` is True."""
    intent: str
    confidence: float = Field(ge=0, le=1)
    top3: list[tuple[str, float]] = Field(default_factory=list, description="top alternatives with calibrated probabilities")
    method: Literal["majority", "keyword", "tfidf_lr", "embed_lr", "llm", "ensemble", "procedural"] = "embed_lr"
    confidence_band: Literal["HIGH", "MEDIUM", "LOW"] = "LOW"
    calibrated: bool = False
    calibration: dict[str, float | str] = Field(default_factory=dict, description="method, temperature, dev ECE")
    secondary_intents: list[str] = Field(default_factory=list)
    multi_intent: bool = False
    insufficient_context: bool = Field(default=False, description="short reply with no informative prior turn; intent is a guess")
    taxonomy_gap: bool = Field(default=False, description="prediction fell to the fallback class with a flat distribution")
    context_used: bool = False
    second_opinion: str | None = Field(default=None, description="LLM intent when consulted; never overrides silently")
    second_opinion_applied: bool = False
    procedural_id: str | None = Field(default=None, description="Canonical procedure ID if matched by trusted procedural knowledge")

    @model_validator(mode="after")
    def _derive_band(self):
        """A band not set explicitly is derived from the confidence with the default thresholds (0.75 / 0.45)."""
        if "confidence_band" not in self.model_fields_set:
            self.confidence_band = "HIGH" if self.confidence >= 0.75 else "MEDIUM" if self.confidence >= 0.45 else "LOW"
        return self


class RiskFlags(BaseModel):
    """Signals extracted for the deterministic policy. The LLM may fill these; it never decides from them.
    Every field is a FLAG; the escalation decision is made by resolveai.policy."""
    safety_concern: bool = False            # injury, smoke, burns, self-harm, medical emergency
    security_concern: bool = False          # hacked, unauthorised access, phishing, malware
    privacy_concern: bool = False           # customer shared or asks about personal data exposure
    account_access_risk: bool = False       # locked out, activation lock, 2FA loop, password recovery
    payment_billing_risk: bool = False      # charges, refunds, subscriptions, orders, delivery
    legal_or_media_threat: bool = False     # lawyer, lawsuit, press, regulator
    abusive_threatening: bool = False       # abuse directed at the agent, threats
    high_impact: bool = False               # customer is stranded, business-critical, deadline
    needs_private_info: bool = False        # resolution requires serial/IMEI/Apple ID/order/case ids
    physical_damage: bool = False           # explicit physical fault or damage
    repeat_contact: bool = False            # explicit prior attempts or repeated contact (guide R1)
    sensitive_action_required: bool = False # refund, replacement, account change, data deletion
    high_frustration: bool = False
    prompt_injection: bool = False          # customer text tries to instruct the assistant or supply evidence (trust/injection.py, deterministic)
    is_actionable: bool = True              # a concrete symptom or request is stated
    insufficient_context: bool = False      # copied from the context builder
    conflicting_evidence: bool = False      # copied from the evidence gate
    summary: str = Field(default="", max_length=200, description="one-line operational summary, customer-safe")
    source: Literal["llm", "rules", "llm+rules", "fallback"] = "rules"

    def any_hard_block(self) -> bool:
        return self.safety_concern or self.security_concern or self.legal_or_media_threat or self.abusive_threatening or self.prompt_injection


class ResponseStrategy(str, Enum):
    troubleshoot = "troubleshoot"
    clarify = "clarify"
    canned = "canned"
    handoff = "handoff"


class DraftResponse(BaseModel):
    text: str = Field(max_length=280)
    strategy: ResponseStrategy
    evidence_ids: list[str] = Field(default_factory=list, description="evidence the draft was generated from")
    model: str = ""
    prompt_version: str = ""
    attempts: int = 1


class GroundingResult(BaseModel):
    grounded: bool
    checks: dict[str, bool] = Field(default_factory=dict, description="named gate checks, e.g. length_ok, no_url, no_promise, steps_in_evidence")
    unsupported_claims: list[str] = Field(default_factory=list)
    method: Literal["lexical", "llm", "lexical+llm"] = "lexical"


class EscalationResult(BaseModel):
    decision: Decision
    reason_code: EscalationReason
    reason: str = Field(description="human-readable, customer-safe reason")
    rule: str = Field(description="name of the deterministic rule that fired")
    policy_version: str = "policy-v1"
    clarification_allowed: bool = Field(default=False, description="policy permits a clarifying question instead of a handoff")


class VerificationIssue(BaseModel):
    check: str
    severity: Literal["info", "warning", "blocking"]
    detail: str = Field(max_length=300)


class VerificationResult(BaseModel):
    """Grounded-response verification. `verified` is False if any blocking issue exists."""
    verified: bool
    issues: list[VerificationIssue] = Field(default_factory=list)
    severity: Literal["none", "info", "warning", "blocking"] = "none"
    evidence_refs: list[str] = Field(default_factory=list, description="evidence_ids the response is supported by")
    coverage: float = Field(default=0.0, ge=0, le=1, description="share of response content words found in cited evidence")
    method: Literal["lexical", "lexical+llm"] = "lexical"
    attempts: int = 1


class AutomationDecision(BaseModel):
    """Final automation verdict after ALL gates. This is what the API returns and what a human sees."""
    decision: Decision
    escalation: EscalationResult
    gates: dict[str, bool] = Field(default_factory=dict, description="evidence_gate, grounding_gate, policy_gate, format_gate")
    autonomous_response_allowed: bool
    action: AgentAction = "HUMAN_HANDOFF"
    gate_version: str = "output-gate-v1"
    blocking: list[str] = Field(default_factory=list, description="names of the gate checks that failed")


class HistoricalExample(BaseModel):
    evidence_id: str
    thread_id: str
    customer_message: str
    brand_reply: str
    outcome: str
    similarity: float
    action_class: str


class HandoffPacket(BaseModel):
    """What a human agent receives when the case is escalated. Self-contained: readable without re-running the agent."""
    summary: str = Field(description="conversation summary, customer-safe")
    customer_issue: str
    intent: str
    confidence: float
    confidence_band: str = "LOW"
    alternatives: list[str] = Field(default_factory=list)
    risk: RiskFlags
    reason: EscalationResult
    evidence_summary: str = ""
    historical_examples: list[HistoricalExample] = Field(default_factory=list)
    evidence_sufficient: bool = False
    evidence_reason: str = ""
    evidence_level: str = "INSUFFICIENT"
    resolution_confidence: float = 0.0
    resolution_candidates: list[ResolutionCandidate] = Field(default_factory=list, description="clustered historical resolutions with their source ids (Phase 5)")
    recommended_next_action: str = ""
    unresolved_questions: list[str] = Field(default_factory=list)
    suggested_opening: str = ""
    draft_if_any: str | None = Field(default=None, description="a generated draft that failed verification, for the human to reuse or discard")
    trace_id: str = ""
    policy_version: str = ""
    evidence: list[EvidenceItem] = Field(default_factory=list)


class EvidenceRef(BaseModel):
    """Citation for a customer-facing reply: one retrieved historical case the reply was drafted from (Phase 7 API contract)."""
    evidence_id: str = Field(description="brand_tweet_id of the historical reply")
    thread_id: str = Field(description="customer_tweet_id of the historical customer message")
    source_row_id: str
    created_at: str = Field(description="timestamp of the historical case (always before the knowledge-base cutoff)")
    rank: int
    similarity: float = Field(description="cosine similarity between the query and the historical customer message")
    retrieval_source: str
    action_class: str
    resolution_bearing: bool
    outcome: str = "none"


class ClarificationPacket(BaseModel):
    """What the agent needs from the customer before it can answer (CLARIFICATION_REQUIRED)."""
    reason_code: str
    why: str = Field(description="why the agent did not answer: evidence or understanding gap")
    evidence_level: str = "INSUFFICIENT"
    evidence_reason: str = ""
    missing_information: list[str] = Field(default_factory=list, description="details the question asks for")
    already_provided: list[str] = Field(default_factory=list, description="details found in the conversation, therefore not asked again")
    question: str = Field(description="the single customer-facing clarifying question")
    intent_hypothesis: str
    intent_confidence: float = 0.0
    confidence_band: str = "LOW"
    alternatives: list[str] = Field(default_factory=list)
    evidence_summary: str = ""
    trace_id: str = ""
    policy_version: str = ""


class DecisionSummary(BaseModel):
    """Operator-facing explanation assembled from recorded fields (resolveai/agent/explain.py); contains no model reasoning."""
    action: AgentAction
    what_happened: str
    why: str
    evidence_basis: str
    next_step: str
    reason_code: str
    rule: str
    policy_version: str = ""
    blocking_checks: list[str] = Field(default_factory=list)


class RuntimeVersions(BaseModel):
    """Everything needed to reproduce a decision: component versions, prompt versions, model and a hash of the effective config."""
    pipeline: str
    policy: str
    output_gate: str
    retrieval: str
    evidence_gate: str
    rerank: str
    classifier: str = Field(description="first 12 hex characters of the frozen classifier artifact's SHA-256")
    prompts: dict[str, str] = Field(default_factory=dict)
    model: str | None = None
    config_hash: str


class UsageSummary(BaseModel):
    llm_calls: int = 0
    live_calls: int = 0
    cache_hits: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    estimated_cost_usd: float = 0.0
    fallbacks: int = 0
    retries: int = 0            # Phase 9: provider attempts after the first
    timeouts: int = 0           # Phase 9: attempts that hit the wall-clock limit
    model_errors: int = 0       # Phase 9: failed provider attempts, any cause
    budget_exhausted: int = 0   # Phase 9: model calls refused because the request budget was spent


class AgentResult(BaseModel):
    """Stable product contract returned by ResolveAI.resolve(). Rendered by the CLI now and the UI later."""
    trace_id: str
    request_id: str = Field(default="", description="caller-supplied or generated correlation id (equals trace_id when none was given)")
    action: AgentAction
    response: str = Field(default="", description="customer-facing text: an auto reply, a clarifying question, or a handoff line")
    message: CustomerMessage
    context: ConversationContext = Field(default_factory=ConversationContext)
    intent: IntentResult
    risk: RiskFlags
    evidence: EvidenceSet
    evidence_refs: list[str] = Field(default_factory=list, description="evidence_ids supporting the response (audit trail)")
    draft: DraftResponse | None = None
    grounding: GroundingResult | None = None
    verification: VerificationResult | None = None
    decision: AutomationDecision
    handoff: HandoffPacket | None = None
    clarification: ClarificationPacket | None = None
    summary: DecisionSummary | None = None
    citations: list[EvidenceRef] = Field(default_factory=list, description="provenance of an autonomous troubleshooting reply; empty for every other action")
    answer: str = Field(default="", description="alias of response, kept for Phase-1 compatibility")
    policy_version: str = ""
    stage_status: dict[str, str] = Field(default_factory=dict, description="stage -> ok | skipped | failed | fallback")
    latency: dict[str, float] = Field(default_factory=dict, description="per-stage ms")
    usage: UsageSummary = Field(default_factory=UsageSummary)
    llm_calls: int = 0
    latency_ms: float = 0
    versions: RuntimeVersions | None = None
