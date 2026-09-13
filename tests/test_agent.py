"""Agent-core tests. The LLM is a FakeProvider (deterministic, no network); the KB and classifier are the real frozen
artifacts (skipped if missing). Every safety-critical invariant has a test here."""
import json

import pytest

from resolveai import config
from resolveai.agent import AgentConfig, ResolveAI
from resolveai.agent import gate as gate_mod
from resolveai.agent.state import AgentState
from resolveai.agent.verifier import lexical_checks, verify
from resolveai.intelligence.classifier import ARTIFACT
from resolveai.llm import DiskCache, FakeProvider, LLMClient
from resolveai.observability import TraceStore
from resolveai.policy import escalation as policy
from resolveai.schemas import (
    ConversationContext,
    ConversationTurn,
    CustomerMessage,
    DraftResponse,
    EscalationResult,
    EvidenceSet,
    IntentResult,
    ResponseStrategy,
    RiskFlags,
)

pytestmark = pytest.mark.skipif(not ARTIFACT.exists() or not (config.PROCESSED_DIR / "apple_pairs.csv").exists(), reason="artifact or subsample missing")

RISK_OK = json.dumps({k: False for k in ("safety_concern", "security_concern", "privacy_concern", "account_access_risk", "payment_billing_risk", "legal_or_media_threat", "abusive_threatening",
                                        "high_impact", "needs_private_info", "physical_damage", "repeat_contact", "sensitive_action_required", "high_frustration")} | {"is_actionable": True, "summary": "keyboard autocorrect issue"})
KEYBOARD = "every time I type the letter i it turns into an A with a question mark box, fix this"


def make_agent(tmp_path, responses=None, default="{}", fail_times=0, **cfg):
    prov = FakeProvider(responses=responses or {}, default=default, fail_times=fail_times)
    llm = LLMClient(provider=prov, model="fake", cache=DiskCache(tmp_path / "llm"))
    return ResolveAI(llm=llm, cfg=AgentConfig(use_second_opinion=False, write_traces=True, **cfg), trace_store=TraceStore(tmp_path / "traces")), prov


def grounded_reply(agent):
    """A reply built from the actual top evidence so the lexical coverage check passes."""
    ev = agent.retriever.retrieve(KEYBOARD, query_intent="keyboard_text_bug")
    top = next(i for i in ev.items if i.substantive)
    text = top.brand_reply.replace("<url>", "").strip()[:200]   # placeholders would (correctly) be blocked by the verifier
    return json.dumps({"reply": text, "evidence_refs": ["E1"], "needs_more_info": False}), ev


# ------------------------------------------------------------------ happy path ----------------------------------------
def test_happy_path_auto_handle_with_grounded_reply(tmp_path):
    a0, _ = make_agent(tmp_path)
    reply, ev = grounded_reply(a0)
    if not ev.sufficient:
        pytest.skip("keyboard evidence not sufficient under the frozen gate on this KB")
    agent, prov = make_agent(tmp_path, responses={"Set each flag": RISK_OK, "write ONLY from the evidence": reply, "Is every concrete instruction": json.dumps({"supported": True, "unsupported_claims": [], "invented_steps": False, "off_topic": False})})
    r = agent.resolve(KEYBOARD)
    assert r.action == "AUTO_HANDLE" and r.response and r.evidence_refs and r.verification.verified and r.decision.autonomous_response_allowed
    assert r.intent.intent == "keyboard_text_bug" and r.evidence.sufficient and set(r.evidence_refs) <= {i.evidence_id for i in r.evidence.items}
    assert r.usage.llm_calls == 3 and r.stage_status["draft"] == "ok" and r.stage_status["verification"] == "ok"
    t = agent.traces.read(r.trace_id)
    assert t is not None and t.final_decision == "AUTO_HANDLE" and {e.name.value for e in t.events} >= {"request_received", "pii_redacted", "context_built", "intent_predicted", "retrieval_completed", "evidence_evaluated", "risk_flags_extracted", "escalation_decided", "draft_generated", "response_verified", "output_allowed", "response_returned"}


# ------------------------------------------------------------------ evidence invariant --------------------------------
def test_insufficient_evidence_never_drafts(tmp_path):
    agent, prov = make_agent(tmp_path, responses={"Set each flag": RISK_OK})
    r = agent.resolve("my phone is doing something weird when I open the settings menu on tuesdays")
    assert r.action in ("HUMAN_HANDOFF", "CLARIFICATION_REQUIRED") and not r.evidence.sufficient
    assert r.stage_status["draft"] == "skipped" and r.draft is None and r.usage.llm_calls <= 1
    assert "evidence_sufficient" in r.decision.blocking or r.decision.escalation.decision == "escalate"


def test_policy_refuses_auto_without_sufficient_evidence():
    intent = IntentResult(intent="battery_power", confidence=0.9, confidence_band="HIGH")
    e = policy.decide(intent, RiskFlags(), evidence=EvidenceSet(sufficient=False, sufficiency_reason="weak_similarity"))
    assert e.decision == "escalate" and e.reason_code == "insufficient_evidence" and e.clarification_allowed
    e2 = policy.decide(intent, RiskFlags(), evidence=EvidenceSet(sufficient=False, sufficiency_reason="conflicting_evidence"))
    assert e2.reason_code == "conflicting_evidence" and not e2.clarification_allowed


def test_output_gate_blocks_unverified_or_unreferenced_drafts():
    st = AgentState(trace_id="t", message=CustomerMessage(message_id="m", text="x"))
    st.intent = IntentResult(intent="battery_power", confidence=0.9, confidence_band="HIGH")
    st.evidence = EvidenceSet(sufficient=True, sufficiency_reason="strong_consistent_evidence")
    st.risk = RiskFlags()
    st.escalation = EscalationResult(decision="auto_handle", reason_code="none", reason="ok", rule="default_auto")
    st.strategy = "troubleshoot"
    st.draft = DraftResponse(text="Try restarting your iPhone and updating to the latest iOS version.", strategy=ResponseStrategy.troubleshoot, evidence_ids=[])
    from resolveai.schemas import VerificationResult

    st.verification = VerificationResult(verified=False, severity="blocking")
    d = gate_mod.output_gate(st)
    assert d.action == "HUMAN_HANDOFF" and "response_verified" in d.blocking and "evidence_refs_exist" in d.blocking
    st.verification = VerificationResult(verified=True)
    st.draft = DraftResponse(text=st.draft.text, strategy=ResponseStrategy.troubleshoot, evidence_ids=["1"])
    assert gate_mod.output_gate(st).action == "AUTO_HANDLE"
    st.risk = RiskFlags(safety_concern=True)
    assert gate_mod.output_gate(st).action == "HUMAN_HANDOFF"


# ------------------------------------------------------------------ risk / policy ---------------------------------------
def test_high_risk_escalates_even_with_good_evidence(tmp_path):
    agent, _ = make_agent(tmp_path, responses={"Set each flag": RISK_OK})
    r = agent.resolve("my charging cable just started to smoke and burned my hand, the battery drains fast too")
    assert r.action == "HUMAN_HANDOFF" and r.decision.escalation.reason_code == "safety" and r.risk.safety_concern and r.handoff is not None
    assert r.handoff.recommended_next_action.startswith("Respond personally") and r.handoff.trace_id == r.trace_id


def test_low_confidence_becomes_conservative(tmp_path):
    agent, _ = make_agent(tmp_path, responses={"Set each flag": RISK_OK})
    r = agent.resolve("this thing is annoying")
    assert r.intent.confidence_band in ("LOW", "MEDIUM") and r.action != "AUTO_HANDLE" and r.stage_status["draft"] == "skipped"


def test_clarification_when_policy_permits(tmp_path):
    agent, _ = make_agent(tmp_path, responses={"Set each flag": RISK_OK})
    ctx = ConversationContext(turns=[ConversationTurn(role="brand", text="Which iPhone do you have?")])
    r = agent.resolve("still happening", ctx)
    assert r.intent.insufficient_context and r.action == "CLARIFICATION_REQUIRED" and r.response.startswith("We'd like to help") and r.evidence_refs == []


# ------------------------------------------------------------------ failure modes -----------------------------------------
def test_llm_unavailable_falls_back_deterministically(tmp_path):
    agent, prov = make_agent(tmp_path, fail_times=99)
    r = agent.resolve(KEYBOARD)
    assert r.action != "AUTO_HANDLE" and r.risk.source == "fallback" and r.stage_status["risk"] == "fallback"
    # FakeProvider fails with TimeoutError: since Phase 9 that is classified as model_timeout (a transport outage stays llm_unavailable)
    assert r.decision.escalation.reason_code in ("llm_unavailable", "model_timeout", "insufficient_evidence", "low_confidence", "insufficient_context") and r.handoff is not None


def test_no_llm_at_all_never_fabricates(tmp_path):
    agent = ResolveAI(cfg=AgentConfig(use_llm=False, write_traces=False))
    r = agent.resolve(KEYBOARD)
    assert r.action != "AUTO_HANDLE" and r.usage.llm_calls == 0 and r.draft is None and r.risk.source == "rules"


def test_malformed_draft_json_leads_to_handoff_not_reply(tmp_path):
    a0, _ = make_agent(tmp_path)
    _, ev = grounded_reply(a0)
    if not ev.sufficient:
        pytest.skip("keyboard evidence not sufficient under the frozen gate")
    agent, prov = make_agent(tmp_path, responses={"Set each flag": RISK_OK}, default="this is not json at all")
    r = agent.resolve(KEYBOARD)
    assert r.action == "HUMAN_HANDOFF" and r.decision.escalation.reason_code == "llm_unavailable" and r.stage_status["draft"] == "fallback"


def test_verifier_failure_redrafts_once_then_escalates(tmp_path):
    a0, _ = make_agent(tmp_path)
    _, ev = grounded_reply(a0)
    if not ev.sufficient:
        pytest.skip("keyboard evidence not sufficient under the frozen gate")
    bad = json.dumps({"reply": "We will refund you within 3 days and replace the device for free, guaranteed.", "evidence_refs": ["E1"], "needs_more_info": False})
    agent, prov = make_agent(tmp_path, responses={"Set each flag": RISK_OK, "write ONLY from the evidence": bad})
    r = agent.resolve(KEYBOARD)
    assert r.action == "HUMAN_HANDOFF" and r.decision.escalation.reason_code == "verification_failed" and r.draft.attempts == 2
    assert r.handoff.draft_if_any is not None and not r.verification.verified and any(i.check == "no_promise" for i in r.verification.issues)


def test_verifier_lexical_checks():
    ev = EvidenceSet(sufficient=True)
    intent = IntentResult(intent="battery_power", confidence=0.9)
    d = DraftResponse(text="Check our evidence retrieval score at http://x.y and call 415-555-0134 @me", strategy=ResponseStrategy.troubleshoot, evidence_ids=[])
    issues, cov, refs = lexical_checks(d, ev, intent)
    assert {i.check for i in issues} >= {"no_url", "no_handle", "no_internal_metadata", "no_pii", "evidence_refs"}
    v = verify(None, DraftResponse(text="You're welcome! If anything else comes up, we're here to help.", strategy=ResponseStrategy.canned), ev, intent, use_llm=False)
    assert v.verified and v.method == "lexical"


# ------------------------------------------------------------------ PII / traces / contract -------------------------------
def test_pii_redacted_before_llm_and_absent_from_traces(tmp_path):
    agent, prov = make_agent(tmp_path, responses={"Set each flag": RISK_OK})
    r = agent.resolve("my battery is dead, call me on 415-555-0134 or mail john@x.com")
    assert r.message.pii_counts.get("PHONE") == 1 and r.message.pii_counts.get("EMAIL") == 1 and "<PHONE>" in r.message.text
    dumped = agent.traces.read(r.trace_id).model_dump_json() + r.model_dump_json()
    assert "415-555" not in dumped and "john@x.com" not in dumped


def test_agent_result_contract_is_stable(tmp_path):
    agent, _ = make_agent(tmp_path, responses={"Set each flag": RISK_OK})
    r = agent.resolve("battery drains fast")
    d = r.model_dump()
    for k in ("action", "response", "intent", "evidence", "evidence_refs", "decision", "handoff", "verification", "trace_id", "usage", "latency", "stage_status", "policy_version"):
        assert k in d
    assert d["action"] in ("AUTO_HANDLE", "HUMAN_HANDOFF", "CLARIFICATION_REQUIRED") and d["policy_version"] == policy.POLICY_VERSION


def test_handoff_packet_is_self_contained(tmp_path):
    agent, _ = make_agent(tmp_path, responses={"Set each flag": RISK_OK})
    ctx = ConversationContext(turns=[ConversationTurn(role="customer", text="my order was charged twice"), ConversationTurn(role="brand", text="Which order?")])
    r = agent.resolve("the one from last week, I want a refund", ctx)
    h = r.handoff
    assert h is not None and h.customer_issue and h.summary and h.recommended_next_action and h.unresolved_questions and h.policy_version and h.trace_id == r.trace_id
    assert h.reason.reason_code in ("payment_billing", "private_info", "sensitive_action", "account_access") and h.evidence_summary


def test_shared_embedding_is_computed_once(tmp_path):
    agent, _ = make_agent(tmp_path, responses={"Set each flag": RISK_OK})
    from resolveai.retrieval.dense import Embedder

    Embedder._memo.clear()
    agent.resolve("my battery drains from full to forty percent within about an hour since installing the latest update")
    assert len(Embedder._memo) == 1  # long message: no canonical phrase appended, so classifier and retriever share one vector


def test_other_intent_canned_only_for_closures(tmp_path):
    agent, prov = make_agent(tmp_path, responses={"Set each flag": RISK_OK})
    r1 = agent.resolve("Thank you!!")
    r2 = agent.resolve("When will we get the TV app in the UK?")
    assert r1.action == "AUTO_HANDLE" and r1.response.startswith("You're welcome")
    assert r2.action == "HUMAN_HANDOFF" and r2.decision.escalation.reason_code == "insufficient_evidence"   # product question: never canned, never answered from thin evidence
    r3 = agent.resolve("Is the 9.7 iPad Pro no longer available?")
    assert r3.action == "HUMAN_HANDOFF" and not r3.response.startswith("You're welcome")


def test_rules_hard_block_skips_the_risk_llm(tmp_path):
    agent, prov = make_agent(tmp_path, responses={"Set each flag": RISK_OK})
    r = agent.resolve("I am going to sue you, my lawyer will be in touch about this phone")
    assert r.decision.escalation.reason_code == "legal_media" and r.usage.llm_calls == 0 and r.risk.source == "rules"
