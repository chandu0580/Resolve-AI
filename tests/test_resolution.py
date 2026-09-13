"""Phase 5 unit tests: resolution reranker, clusters, consistency, resolution confidence, gate-v3, risk hardening,
policy short-circuit, resolution-aware drafting helpers. No KB, no network."""
import json

import pytest

from resolveai.agent import drafter, risk
from resolveai.agent.risk import RiskCompact, normalise_flags
from resolveai.intelligence.context import build_context
from resolveai.policy import escalation as policy
from resolveai.retrieval.resolution import (
    GateV3Config,
    RerankWeights,
    cluster_resolutions,
    consistency_of,
    decide_v3,
    rerank,
    resolution_confidence,
    symptom_tokens,
)
from resolveai.schemas.core import ConversationContext, IntentResult, RiskFlags
from resolveai.schemas.evidence import EvidenceItem, EvidenceQuality, EvidenceSet, ResolutionCandidate


def item(i, *, sim=0.9, action="update", substantive=True, same=False, reply=None, outcome="none", source="customer"):
    return EvidenceItem(evidence_id=f"e{i}", thread_id=f"t{i}", source_row_id=f"t{i}", customer_message=f"customer {i} says the letter i becomes a box",
                        brand_reply=reply or f"Update to iOS 11.1.1 to fix this, case {i}. Go to Settings > General > Software Update.", created_at=f"2017-11-0{i % 9 + 1}T00:00:00Z",
                        outcome=outcome, substantive=substantive, dm_handoff=not substantive, retrieval_method="test", retrieval_source=source, rank=i,
                        quality=EvidenceQuality(semantic_relevance=sim, lexical_relevance=0, candidate_intent="keyboard_text_bug", intent_match=True, resolution_relevance=substantive,
                                                action_class=action, same_customer=same, quality="strong" if sim >= 0.7 else "weak"))


QUERY = "every time I type the letter i it turns into a box with autocorrect"


# ------------------------------------------------------------------ reranker ------------------------------------------
def cand(doc, **kw):
    base = dict(doc=doc, cos_customer=0.8, cos_reply=0.5, cos_pair=0.5, weak_intent="keyboard_text_bug", action_class="update", substantive=True, dm_handoff=False,
                outcome="none", reply=f"Update to iOS 11.1.1, go to Settings > General {doc}", same_customer=False)
    base.update(kw)
    return base


def test_rerank_prefers_resolution_bearing_and_penalises_dm_and_same_customer():
    w = RerankWeights()
    cands = [cand(1, action_class="dm_handoff", substantive=False, dm_handoff=True, reply="Send us a DM", cos_customer=0.9),
             cand(2, cos_customer=0.85), cand(3, cos_customer=0.85, same_customer=True), cand(4, cos_customer=0.85, reply="Update to iOS 11.1.1, go to Settings > General 2")]
    out = rerank(cands, w, "keyboard_text_bug")
    order = [c["doc"] for c in out]
    assert order[0] == 2 and order.index(3) > order.index(2) and order.index(1) > order.index(2)
    dup = next(c for c in out if c["doc"] == 4)
    assert dup["duplicate"] and dup["rerank"] < next(c for c in out if c["doc"] == 2)["rerank"]


def test_outcome_bonus_cannot_overturn_semantics():
    w = RerankWeights()
    a = cand(1, cos_customer=0.80, outcome="positive")
    b = cand(2, cos_customer=0.86, outcome="negative")
    out = rerank([a, b], w, None)
    assert out[0]["doc"] == 2   # 0.06 cosine gap (0.021 score) > the bonus swing 1.5*w_outcome = 0.015


def test_reply_side_similarity_counts():
    w = RerankWeights()
    a = cand(1, cos_customer=0.80, cos_reply=0.3, cos_pair=0.3)
    b = cand(2, cos_customer=0.78, cos_reply=0.9, cos_pair=0.9)
    assert rerank([a, b], w, None)[0]["doc"] == 2


# ------------------------------------------------------------------ clusters / consistency -----------------------------
def test_clusters_group_by_action_class_and_keep_every_source_id():
    items = [item(1), item(2), item(3, action="article", reply="Check out this article on autocorrect: <url>"), item(4, substantive=False, action="dm_handoff"), item(5, same=True)]
    cands = cluster_resolutions(items, min_sim=0.85)
    assert [c.action_class for c in cands] == ["update", "article"]
    assert cands[0].support_count == 2 and set(cands[0].evidence_ids) == {"e1", "e2"} and cands[0].representative_id in {"e1", "e2"}
    assert cands[0].share == pytest.approx(2 / 3, abs=1e-3) and consistency_of(cands, 0.6) == "consistent"
    assert all("e5" not in c.evidence_ids and "e4" not in c.evidence_ids for c in cands)   # same-customer and DM items are never support


def test_mixed_resolution_is_detected():
    items = [item(1, action="update"), item(2, action="reset", reply="Reset all settings: Settings > General > Reset"), item(3, action="article", reply="See this article <url> for steps")]
    cands = cluster_resolutions(items, min_sim=0.85)
    assert consistency_of(cands, 0.6) == "mixed_resolution" and consistency_of([], 0.6) == "no_resolution"


# ------------------------------------------------------------------ confidence + gate v3 ------------------------------
def test_resolution_confidence_formula_is_bounded_and_monotone():
    hi = resolution_confidence(1.0, 3, 0.9, False, False, False)
    lo = resolution_confidence(0.5, 1, 0.6, True, False, False)
    assert 0 <= lo < hi <= 1 and resolution_confidence(1.0, 3, 0.9, False, False, True) == 0.0
    assert resolution_confidence(1.0, 3, 0.9, False, True, False) < hi


def test_gate_v3_levels_and_reasons():
    cfg = GateV3Config()
    strong = decide_v3([item(1), item(2), item(3)], cfg, "keyboard_text_bug", QUERY)
    assert strong["level"] == "STRONG" and strong["sufficient"] and strong["consistency"] == "consistent" and strong["candidates"][0].support_count == 3
    mixed = decide_v3([item(1, action="update"), item(2, action="reset", reply="Reset all settings: Settings > General > Reset")], cfg, "keyboard_text_bug", QUERY)
    assert mixed["level"] == "WEAK" and mixed["reason"] == "mixed_resolution" and not mixed["sufficient"]
    weak = decide_v3([item(1), item(2, sim=0.7)], cfg, "keyboard_text_bug", QUERY)
    assert weak["level"] == "WEAK" and weak["reason"] == "weak_resolution_evidence"
    none = decide_v3([item(1, sim=0.6), item(2, sim=0.6)], cfg, "keyboard_text_bug", QUERY)
    assert none["level"] == "INSUFFICIENT" and none["reason"] == "weak_similarity"
    empty = decide_v3([], cfg, None, QUERY)
    assert empty["level"] == "INSUFFICIENT" and empty["reason"] == "no_relevant_evidence"


def test_gate_v3_vague_query_is_insufficient_even_with_strong_evidence():
    cfg = GateV3Config()
    assert symptom_tokens("my phone keeps bugging out why u doing this") == 0 and symptom_tokens("the letter i turns into a box") >= 1 and symptom_tokens("please fix the I.T problem") == 1
    g = decide_v3([item(1), item(2), item(3)], cfg, "general_complaint", "my phone keeps bugging out why u doing this")
    assert g["level"] == "INSUFFICIENT" and g["reason"] == "insufficient_query" and g["confidence"] == 0.0
    short = decide_v3([item(1), item(2), item(3)], cfg, None, "fix this")
    assert short["reason"] == "insufficient_query"


def test_gate_v3_customer_history_is_not_evidence():
    g = decide_v3([item(1, same=True), item(2, same=True), item(3, sim=0.6)], GateV3Config(), "keyboard_text_bug", QUERY)
    assert g["level"] == "INSUFFICIENT" and g["reason"] == "customer_history_risk"


def test_gate_v3_thresholds_never_below_gate_v2_support():
    from resolveai.retrieval.gate import GateConfig

    v3, v2 = GateV3Config.load(), GateConfig.load()
    assert v3.support_similarity >= min(0.85, v2.support_similarity) and v3.min_support >= 2 and v3.t_sufficient >= 0.45


# ------------------------------------------------------------------ risk hardening -------------------------------------
def test_compact_risk_schema_parses_strictly_and_drops_unknown_flags():
    known, unknown = normalise_flags(["Safety Concern", "repeat-contact", "made_up_flag", "actionable", ""])
    assert known == {"safety_concern", "repeat_contact"} and unknown == ["made_up_flag"]
    out = RiskCompact.model_validate({"flags": ["high_impact"], "actionable": False, "summary": "x", "extra": 1})
    assert out.flags == ["high_impact"] and not out.actionable
    legacy = RiskCompact.model_validate(json.loads('{"safety_concern": true, "is_actionable": true}'))   # v1-shaped answer degrades to no flags, not a fallback
    assert legacy.flags == [] and legacy.actionable


def test_risk_extract_compact_merges_with_rules_and_falls_back(tmp_path):
    from resolveai.llm import DiskCache, FakeProvider, LLMClient

    b = build_context("my lawyer will call, the phone keeps freezing", ConversationContext())
    good = LLMClient(provider=FakeProvider(default=json.dumps({"flags": ["high_impact", "bogus"], "actionable": True, "summary": "freezing phone"})), model="fake", cache=DiskCache(tmp_path / "a"))
    flags, status = risk.extract(good, b, None, schema="compact")
    assert flags.legal_or_media_threat and flags.high_impact and status == "ok_unknown_flags_dropped" and flags.source == "llm+rules"
    bad = LLMClient(provider=FakeProvider(default="not json at all"), model="fake", cache=DiskCache(tmp_path / "b"))
    flags2, status2 = risk.extract(bad, b, None, schema="compact")
    assert status2 == "fallback" and flags2.legal_or_media_threat and flags2.source == "fallback"
    flags3, status3 = risk.extract(None, b, None)
    assert status3 == "rules_only" and flags3.legal_or_media_threat


# ------------------------------------------------------------------ policy short-circuit -------------------------------
def test_short_circuit_only_when_rules_alone_guarantee_a_handoff():
    intent = IntentResult(intent="battery_power", confidence=0.9, confidence_band="HIGH")
    ev_ok = EvidenceSet(sufficient=True, sufficiency_reason="strong_consistent_evidence", sufficiency_level="STRONG")
    assert policy.hard_handoff_guaranteed(intent, RiskFlags(legal_or_media_threat=True), None, ev_ok, "my lawyer will call") is True
    assert policy.hard_handoff_guaranteed(intent, RiskFlags(), None, ev_ok, "battery drains fast") is False           # auto path: LLM must still run
    weak = EvidenceSet(sufficient=False, sufficiency_reason="weak_resolution_evidence", sufficiency_level="WEAK")
    assert policy.hard_handoff_guaranteed(intent, RiskFlags(), None, weak, "battery drains fast") is False           # clarify path: LLM may still convert it to a handoff
    multi = IntentResult(intent="battery_power", confidence=0.9, confidence_band="HIGH", multi_intent=True)
    assert policy.hard_handoff_guaranteed(multi, RiskFlags(), None, weak, "battery drains fast") is True             # non-clarifiable handoff


def test_policy_v3_clarifies_on_weak_or_mixed_evidence_and_never_auto_handles_them():
    intent = IntentResult(intent="keyboard_text_bug", confidence=0.9, confidence_band="HIGH")
    for reason in ("weak_resolution_evidence", "mixed_resolution"):
        e = policy.decide(intent, RiskFlags(), evidence=EvidenceSet(sufficient=False, sufficiency_reason=reason, sufficiency_level="WEAK"))
        assert e.decision == "escalate" and e.clarification_allowed and e.reason_code == "insufficient_evidence"
    e2 = policy.decide(intent, RiskFlags(high_impact=True), evidence=EvidenceSet(sufficient=False, sufficiency_reason="mixed_resolution", sufficiency_level="WEAK"))
    assert e2.decision == "escalate" and not e2.clarification_allowed
    assert policy.POLICY_VERSION in ("policy-v3.3", "policy-v3.4")


# ------------------------------------------------------------------ resolution-aware drafting --------------------------
def test_resolution_block_leads_with_candidates_and_ask_only_detection():
    items = [item(1, reply="Let's look into this. Which iPhone and iOS version do you have?", action="ask_info"), item(2), item(3, action="article", reply="See this article <url>")]
    ev = EvidenceSet(items=items, sufficient=True, sufficiency_level="STRONG", resolution_candidates=[
        ResolutionCandidate(action_class="update", representative_reply=items[1].brand_reply, representative_id="e2", evidence_ids=["e2"], support_count=2, mean_similarity=0.9, share=0.67)])
    block, labels, has_res = drafter._resolution_block(ev)
    assert has_res and labels["E1"] == "e2" and block.startswith("[E1] RESOLUTION (update") and "E2" in labels and "E3" in labels
    assert drafter.is_ask_only("Which iPhone and iOS version are you on?") and not drafter.is_ask_only("Update to iOS 11.1.1 via Settings > General > Software Update. Which model do you have?")


def test_draft_v2_retries_once_when_reply_only_asks(tmp_path):
    from resolveai.llm import DiskCache, FakeProvider, LLMClient

    items = [item(2), item(3)]
    ev = EvidenceSet(items=items, sufficient=True, sufficiency_level="STRONG", resolution_candidates=[
        ResolutionCandidate(action_class="update", representative_reply=items[0].brand_reply, representative_id="e2", evidence_ids=["e2", "e3"], support_count=2, mean_similarity=0.9, share=1.0)])
    ask = json.dumps({"reply": "Which iPhone and iOS version are you on?", "evidence_refs": ["E1"], "needs_more_info": True})
    fix = json.dumps({"reply": "Update to iOS 11.1.1: Settings > General > Software Update. Let us know if it continues.", "evidence_refs": ["E1"], "needs_more_info": False})
    prov = FakeProvider(responses={"That reply only asks a question": fix, "write ONLY from the evidence": ask})
    client = LLMClient(provider=prov, model="fake", cache=DiskCache(tmp_path))
    b = build_context(QUERY, ConversationContext())
    d = drafter.draft_troubleshoot(client, b, IntentResult(intent="keyboard_text_bug", confidence=0.9, confidence_band="HIGH"), ev)
    assert d.text.startswith("Update to iOS 11.1.1") and d.evidence_ids == ["e2"] and d.attempts == 2 and prov.calls == 2


def test_policy_v3_general_complaint_is_clarified_never_auto_handled():
    intent = IntentResult(intent="general_complaint", confidence=0.9, confidence_band="HIGH")
    strong = EvidenceSet(sufficient=True, sufficiency_reason="strong_consistent_evidence", sufficiency_level="STRONG")
    e = policy.decide(intent, RiskFlags(), evidence=strong, message="please sort out your bug fixes")
    assert e.decision == "escalate" and e.clarification_allowed and e.rule == "general_complaint_clarify" and e.reason_code == "insufficient_context"
    hostile = policy.decide(intent, RiskFlags(high_frustration=True, is_actionable=False), evidence=strong, message="fix your shit")
    assert hostile.reason_code == "vague_hostile" and not hostile.clarification_allowed


def test_structured_retry_uses_example_shape_and_bumps_tokens_on_truncation(tmp_path):
    from resolveai.llm import DiskCache, FakeProvider, LLMClient
    from resolveai.llm.provider import example_shape

    shape = example_shape(RiskCompact)
    assert shape == {"flags": [], "actionable": False, "summary": "..."}

    class Recorder(FakeProvider):
        def __init__(self):
            super().__init__()
            self.seen = []

        def complete(self, model, messages, *, temperature, max_tokens, json_mode, timeout_s):
            self.seen.append((messages[-1]["content"], max_tokens))
            content = "thinking... no json here" if len(self.seen) == 1 else json.dumps({"flags": ["high_impact"], "actionable": True, "summary": "ok"})
            self.calls += 1
            from resolveai.llm.provider import Completion
            return Completion(content=content, tokens_in=10, tokens_out=10, latency_ms=1)

    prov = Recorder()
    client = LLMClient(provider=prov, model="fake", cache=DiskCache(tmp_path))
    out = client.structured([{"role": "user", "content": "extract flags"}], RiskCompact, prompt_version="t", max_tokens=600)
    assert out.flags == ["high_impact"] and len(prov.seen) == 2
    assert prov.seen[1][1] == 900 and "exact shape" in prov.seen[1][0] and '"type"' not in prov.seen[1][0]   # 600 * 1.5, example shape, never the JSON schema
