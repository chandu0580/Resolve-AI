from resolveai.observability import TraceRecorder, TraceStore
from resolveai.policy import CONFIDENCE_FLOOR, decide
from resolveai.schemas import ConversationContext, ConversationTurn, EvidenceSet, GroundingResult, IntentResult, RiskFlags


def _intent(name="battery_power", conf=0.9):
    return IntentResult(intent=name, confidence=conf)


def test_safety_beats_everything():
    r = decide(_intent("other"), RiskFlags(safety_concern=True, needs_private_info=True))
    assert r.decision == "escalate" and r.reason_code == "safety" and r.rule == "safety"


def test_reason_priority_order():
    assert decide(_intent(), RiskFlags(legal_or_media_threat=True, physical_damage=True)).reason_code == "legal_media"
    assert decide(_intent(), RiskFlags(needs_private_info=True, physical_damage=True)).reason_code == "private_info"
    assert decide(_intent("hardware_damage"), RiskFlags()).reason_code == "hardware"
    assert decide(_intent(), RiskFlags(repeat_contact=True, high_frustration=True, is_actionable=False)).reason_code == "repeat_contact"


def test_deep_thread_without_progress_escalates():
    ctx = ConversationContext(turns=[ConversationTurn(role="brand", text="a"), ConversationTurn(role="customer", text="b"), ConversationTurn(role="brand", text="c")])
    assert decide(_intent(), RiskFlags(), ctx).rule == "repeat_contact"


def test_canned_intents_auto_handle_without_evidence():
    r = decide(_intent("non_english"), RiskFlags(), evidence=EvidenceSet(sufficient=False))
    assert r.decision == "auto_handle" and r.rule == "canned:non_english"


def test_low_confidence_escalates():
    assert decide(_intent(conf=CONFIDENCE_FLOOR - 0.01), RiskFlags()).reason_code == "low_confidence"


def test_no_evidence_means_no_autonomous_response():
    assert decide(_intent(), RiskFlags(), evidence=EvidenceSet(sufficient=False)).reason_code == "insufficient_evidence"
    assert decide(_intent(), RiskFlags(), evidence=EvidenceSet(sufficient=True), grounding=GroundingResult(grounded=False)).reason_code == "grounding_failed"
    assert decide(_intent(), RiskFlags(), evidence=EvidenceSet(sufficient=True), grounding=GroundingResult(grounded=True), llm_available=False).reason_code == "llm_unavailable"


def test_default_auto_only_when_all_gates_pass():
    r = decide(_intent(), RiskFlags(), evidence=EvidenceSet(sufficient=True), grounding=GroundingResult(grounded=True))
    assert r.decision == "auto_handle" and r.rule == "default_auto" and r.reason_code == "none"


def test_trace_store_round_trip(tmp_path):
    rec = TraceRecorder(message_id="m1", prompt_versions={"draft": "v1"})
    rec.event("request_received", "api", message_id="m1")
    rec.event("retrieval_completed", "retrieval", latency_ms=3.2, evidence_ids=["1", "2"], top_similarity=0.81)
    rec.event("decision_made", "policy", rule="default_auto", decision="auto_handle")
    rec.usage("glm-5.2", calls=2, tokens_in=400, tokens_out=600, cache_hits=1)
    t = rec.finish("auto_handle")
    store = TraceStore(tmp_path)
    p = store.write(t)
    assert p.exists() and store.read(t.trace_id) == t and t.config_hash and len(t.events) == 3
