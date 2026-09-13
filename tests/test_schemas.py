import pytest
from pydantic import ValidationError

from resolveai.schemas import (
    AgentResult,
    AgentTrace,
    AutomationDecision,
    ConversationContext,
    ConversationTurn,
    CustomerMessage,
    DraftResponse,
    EscalationResult,
    EvidenceItem,
    EvidenceQuality,
    EvidenceSet,
    GroundingResult,
    IntentResult,
    ResponseStrategy,
    RiskFlags,
    TraceEvent,
    TraceEventName,
)


def _result() -> AgentResult:
    msg = CustomerMessage(message_id="m1", text="battery dies at 40%, call <PHONE>", pii_counts={"PHONE": 1})
    ctx = ConversationContext(turns=[ConversationTurn(role="customer", text="hi"), ConversationTurn(role="brand", text="which iPhone?")])
    intent = IntentResult(intent="battery_power", confidence=0.83, top3=[("battery_power", 0.83), ("performance_crash", 0.1), ("other", 0.02)])
    ev = EvidenceSet(items=[EvidenceItem(evidence_id="42", thread_id="41", source_row_id="41", customer_message="battery drains",
                                         brand_reply="Try a restart and update to iOS 11.2.", created_at="2017-11-01", outcome="positive",
                                         retrieval_method="hybrid:bge-small", rank=1, quality=EvidenceQuality(semantic_relevance=0.81, lexical_relevance=3.2, quality="strong"))],
                     query=msg.text, retriever="hybrid:bge-small", n_retrieved=1, n_relevant=1, sufficient=True, sufficiency_reason="strong_consistent_evidence")
    draft = DraftResponse(text="Sorry about the battery. Try a restart, then update to iOS 11.2 and let us know.", strategy=ResponseStrategy.troubleshoot, evidence_ids=["42"], model="glm-5.2", prompt_version="draft-v1")
    esc = EscalationResult(decision="auto_handle", reason_code="none", reason="clear issue", rule="default_auto")
    dec = AutomationDecision(decision="auto_handle", escalation=esc, gates={"evidence_gate": True, "grounding_gate": True, "policy_gate": True}, autonomous_response_allowed=True)
    return AgentResult(trace_id="t1", action="AUTO_HANDLE", response=draft.text, message=msg, context=ctx, intent=intent, risk=RiskFlags(), evidence=ev, draft=draft,
                       grounding=GroundingResult(grounded=True, checks={"no_url": True}), decision=dec, answer=draft.text, llm_calls=2, latency_ms=1234)


def test_agent_result_round_trip_exposes_required_fields():
    r = _result()
    d = r.model_dump()
    for k in ("action", "response", "answer", "intent", "evidence", "grounding", "decision", "trace_id"):
        assert k in d
    assert d["intent"]["confidence"] == 0.83 and d["decision"]["escalation"]["reason_code"] == "none"
    assert AgentResult.model_validate_json(r.model_dump_json()) == r


def test_context_counts_brand_turns():
    assert _result().context.brand_turns == 1


def test_draft_length_and_confidence_bounds():
    with pytest.raises(ValidationError):
        DraftResponse(text="x" * 281, strategy=ResponseStrategy.troubleshoot)
    with pytest.raises(ValidationError):
        IntentResult(intent="other", confidence=1.2)


def test_trace_event_rejects_hidden_reasoning_and_raw_text():
    ok = TraceEvent(name=TraceEventName.decision_made, ts="2026-09-10T00:00:00Z", component="policy", data={"rule": "safety", "score": 0.9})
    assert ok.name == "decision_made"
    for bad in ("reasoning", "chain_of_thought", "raw_text", "api_key"):
        with pytest.raises(ValidationError):
            TraceEvent(name="decision_made", ts="t", component="policy", data={bad: "x"})


def test_trace_event_names_cover_contract():
    expected = {"request_received", "pii_redacted", "intent_classified", "risk_extracted", "retrieval_started", "retrieval_completed", "evidence_gate",
                "draft_generated", "grounding_checked", "policy_checked", "decision_made", "handoff", "response_returned", "error", "fallback"}
    assert expected <= {e.value for e in TraceEventName}
    assert {"context_built", "second_opinion_used", "evidence_evaluated", "escalation_decided", "response_verified", "output_allowed", "handoff_created", "execution_failed"} <= {e.value for e in TraceEventName}


def test_agent_trace_latency_sums_events():
    t = AgentTrace(trace_id="t", started_at="s", message_id="m", events=[
        TraceEvent(name="request_received", ts="a", component="api", latency_ms=1.5),
        TraceEvent(name="response_returned", ts="b", component="api", latency_ms=2.5),
    ])
    assert t.total_latency_ms == 4.0
