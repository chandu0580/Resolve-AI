"""Observability contract: one AgentTrace per agent execution, made of ordered TraceEvents.

Stores timestamps, latency, component, status, ids, scores, evidence references, gate verdicts, policy decision,
error/fallback info and model usage. It never stores raw (unredacted) customer text or hidden chain-of-thought.
"""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class TraceEventName(str, Enum):
    request_received = "request_received"
    pii_redacted = "pii_redacted"
    injection_checked = "injection_checked"
    clarification_created = "clarification_created"
    context_built = "context_built"
    intent_classified = "intent_classified"
    intent_predicted = "intent_predicted"
    second_opinion_used = "second_opinion_used"
    risk_extracted = "risk_extracted"
    risk_flags_extracted = "risk_flags_extracted"
    retrieval_started = "retrieval_started"
    retrieval_completed = "retrieval_completed"
    retrieval_skipped = "retrieval_skipped"           # final product pass: nothing to retrieve for (a bare greeting)
    evidence_gate = "evidence_gate"
    evidence_evaluated = "evidence_evaluated"
    evidence_quarantined = "evidence_quarantined"     # Phase 9: retrieved items carrying instruction-like text were excluded
    escalation_decided = "escalation_decided"
    draft_generated = "draft_generated"
    grounding_checked = "grounding_checked"
    response_verified = "response_verified"
    policy_checked = "policy_checked"
    decision_made = "decision_made"
    output_allowed = "output_allowed"
    handoff = "handoff"
    handoff_created = "handoff_created"
    response_returned = "response_returned"
    model_call_failed = "model_call_failed"           # Phase 9: a model call failed (kind: timeout | transport | invalid_output | budget_exhausted ...)
    dependency_failed = "dependency_failed"           # Phase 9: a non-model stage raised (retrieval, embedding, classifier, verifier, ...)
    execution_failed = "execution_failed"
    error = "error"
    fallback = "fallback"


_FORBIDDEN_KEYS = {"raw_text", "reasoning", "chain_of_thought", "thoughts", "scratchpad", "api_key", "authorization", "token", "password"}


class TraceEvent(BaseModel):
    name: TraceEventName
    ts: str = Field(description="ISO-8601 UTC timestamp")
    component: str
    status: str = Field(default="ok", description="ok | skipped | failed | fallback")
    latency_ms: float = 0
    data: dict[str, Any] = Field(default_factory=dict, description="ids, scores, evidence refs, gate verdicts, decisions, token usage")

    @field_validator("data")
    @classmethod
    def _no_hidden_or_raw_fields(cls, v: dict[str, Any]) -> dict[str, Any]:
        bad = _FORBIDDEN_KEYS & set(v)
        if bad:
            raise ValueError(f"trace event data may not contain {sorted(bad)}")
        return v


class ModelUsage(BaseModel):
    model: str
    calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    cache_hits: int = 0
    estimated_cost_usd: float | None = None
    retries: int = 0
    timeouts: int = 0
    errors: int = 0
    fallbacks: int = 0
    budget_exhausted: int = 0


class AgentTrace(BaseModel):
    trace_id: str
    started_at: str
    finished_at: str | None = None
    message_id: str
    request_id: str = Field(default="", description="correlation id propagated from the API (X-Request-ID)")
    pipeline_version: str = ""
    versions: dict[str, str] = Field(default_factory=dict, description="policy, gate, retrieval, rerank, classifier, model versions")
    request_meta: dict[str, str] = Field(default_factory=dict, description="non-identifying request metadata (channel, locale)")
    config_hash: str = Field(default="", description="hash of the effective configuration for reproducibility")
    prompt_versions: dict[str, str] = Field(default_factory=dict)
    events: list[TraceEvent] = Field(default_factory=list)
    usage: list[ModelUsage] = Field(default_factory=list)
    final_decision: str | None = None
    stage_status: dict[str, str] = Field(default_factory=dict)
    latency_ms: dict[str, float] = Field(default_factory=dict, description="per-stage latency, including total")
    budget_s: float | None = Field(default=None, description="wall-clock budget the request ran under (Phase 9)")
    failures: list[dict[str, str]] = Field(default_factory=list, description="classified failures: {category, stage, kind}; codes only, never free text (Phase 9)")
    error: str | None = None

    @property
    def total_latency_ms(self) -> float:
        return sum(e.latency_ms for e in self.events)
