"""Phase 5 integration tests on the real frozen KB (skipped if artifacts are missing): reply-side and dual retrieval with
provenance, temporal isolation on every index, resolution ranking, gate-v3 inside the engine, the risk short-circuit
inside the agent, and the autonomy invariant on WEAK / mixed evidence. LLM = FakeProvider."""
import json

import pytest

from resolveai import config
from resolveai.agent import AgentConfig, ResolveAI
from resolveai.intelligence.classifier import ARTIFACT
from resolveai.llm import DiskCache, FakeProvider, LLMClient
from resolveai.observability import TraceStore
from resolveai.retrieval import KnowledgeBase, Retriever, RetrieverConfig
from resolveai.retrieval.dense import SUPPORTED
from resolveai.retrieval.resolution import RESOLUTION_ACTIONS, GateV3Config

pytestmark = pytest.mark.skipif(not ARTIFACT.exists() or not (config.PROCESSED_DIR / "apple_pairs.csv").exists(), reason="artifact or subsample missing")
BGE = SUPPORTED["bge-small"]
KEYBOARD = "every time I type the letter i it turns into an A with a question mark box, fix this"


@pytest.fixture(scope="module")
def kb():
    k = KnowledgeBase.build(dense_models=[BGE], with_bm25=False)
    for p in ("reply", "pair"):
        k.add_dense(BGE, p)
    return k


def test_reply_side_and_pair_indexes_cover_the_same_rows(kb):
    n = len(kb.rows)
    assert kb.dense_index(BGE, "customer").X.shape[0] == n == kb.dense_index(BGE, "reply").X.shape[0] == kb.dense_index(BGE, "pair").X.shape[0]
    with pytest.raises(ValueError):
        kb.add_dense(BGE, "bogus")


def test_reply_side_retrieval_surfaces_resolution_replies(kb):
    r = Retriever(kb, RetrieverConfig(paths=("reply",), rerank="none", gate="v2"))
    ev = r.retrieve(KEYBOARD, query_intent="keyboard_text_bug")
    assert ev.items and all(i.retrieval_source == "reply" for i in ev.items) and all("cos_reply" in i.scores for i in ev.items)
    assert any(i.quality.action_class in RESOLUTION_ACTIONS for i in ev.items)


def test_dual_retrieval_marks_provenance_and_scores_every_path(kb):
    r = Retriever(kb, RetrieverConfig(paths=("customer", "pair")))
    ev = r.retrieve(KEYBOARD, query_intent="keyboard_text_bug")
    assert ev.items and {i.retrieval_source for i in ev.items} <= {"customer", "pair", "dual"}
    for i in ev.items:
        assert set(i.scores) >= {"dense", "cos_pair", "rrf", "rerank", "final"} and -1 <= i.scores["cos_pair"] <= 1.0001 and i.retrieval_method.endswith("+rr+gatev3")
    assert ev.gate_version == "gate-v3" and ev.sufficiency_level in ("INSUFFICIENT", "WEAK", "SUFFICIENT", "STRONG")
    assert (ev.sufficient) == (ev.sufficiency_level in ("SUFFICIENT", "STRONG"))


def test_temporal_isolation_holds_on_every_path(kb):
    early = "2017-10-20T00:00:00Z"
    for paths in (("customer",), ("reply",), ("pair",), ("customer", "pair")):
        ev = Retriever(kb, RetrieverConfig(paths=paths)).retrieve(KEYBOARD, query_intent="keyboard_text_bug", query_created_at=early)
        assert all(i.created_at < early for i in ev.items), paths


def test_resolution_rerank_prefers_resolution_bearing_replies(kb):
    plain = Retriever(kb, RetrieverConfig(paths=("customer",), rerank="none", gate="v2", substantive_first=False))
    rr = Retriever(kb, RetrieverConfig(paths=("customer", "pair"), rerank="resolution", gate="v3"))
    q = "my iphone battery drains really fast since ios 11 update"
    a, b = plain.retrieve(q, query_intent="battery_power"), rr.retrieve(q, query_intent="battery_power")
    res = lambda ev: sum(1 for i in ev.items if i.substantive and i.quality.action_class in RESOLUTION_ACTIONS)  # noqa: E731
    assert res(b) >= res(a) and all(not i.dm_handoff for i in b.items[:2])
    assert b.items == sorted(b.items, key=lambda i: -i.scores["rerank"])


def test_same_customer_history_is_never_support(kb):
    r = Retriever(kb, RetrieverConfig())
    row = kb.rows[kb.rows.substantive].iloc[0]
    ev = r.retrieve(row.customer_message, query_intent=None, customer_author=str(row.customer_author))
    assert all(not (i.quality.same_customer and i.evidence_id in {e for c in ev.resolution_candidates for e in c.evidence_ids}) for i in ev.items)


def test_frozen_gate_v3_config_is_at_least_as_strict_as_defaults():
    g = GateV3Config.load()
    assert g.support_similarity >= 0.85 and g.min_support >= 2 and g.min_top_share >= 0.5 and g.require_symptom_term and g.version == "gate-v3"


# ------------------------------------------------------------------ agent-level ---------------------------------------
def make_agent(tmp_path, responses=None, default="{}", **cfg):
    prov = FakeProvider(responses=responses or {}, default=default)
    llm = LLMClient(provider=prov, model="fake", cache=DiskCache(tmp_path / "llm"))
    return ResolveAI(llm=llm, cfg=AgentConfig(use_second_opinion=False, write_traces=True, **cfg), trace_store=TraceStore(tmp_path / "traces")), prov


def test_risk_short_circuit_skips_llm_only_when_handoff_is_guaranteed(tmp_path):
    agent, prov = make_agent(tmp_path)
    r = agent.resolve("my order 123 was charged twice and I want a refund for the phone")   # payment/billing -> non-clarifiable handoff from rules alone
    t = agent.traces.read(r.trace_id)
    risk_ev = next(e for e in t.events if e.name.value == "risk_flags_extracted")
    assert r.action == "HUMAN_HANDOFF" and risk_ev.status in ("rules_hard_block", "policy_hard_handoff") and r.usage.llm_calls == 0 and r.risk.source == "rules"
    agent2, prov2 = make_agent(tmp_path, risk_short_circuit=False)
    r2 = agent2.resolve("my order 123 was charged twice and I want a refund for the phone")
    assert r2.action == r.action and r2.decision.escalation.reason_code == r.decision.escalation.reason_code   # identical behaviour, one more call at most
    agent3, prov3 = make_agent(tmp_path)
    r3 = agent3.resolve(KEYBOARD)
    if r3.action != "HUMAN_HANDOFF" or r3.decision.escalation.clarification_allowed:
        assert prov3.calls >= 1   # the LLM still runs whenever the outcome could change


def test_weak_or_mixed_evidence_never_auto_handles(tmp_path):
    agent, prov = make_agent(tmp_path, responses={"write ONLY": json.dumps({"reply": "Update to iOS 11.1.1 via Settings > General > Software Update.", "evidence_refs": ["E1"], "needs_more_info": False}),
                                                  "Is every concrete": json.dumps({"supported": True, "unsupported_claims": [], "invented_steps": False, "off_topic": False})})
    # scan a few realistic messages; every non-sufficient evidence set must end in clarification or handoff, never a factual auto reply
    for msg in ("my phone is doing something odd with the photos app since yesterday", "wifi drops every few minutes on my ipad", "the screen flickers when I open safari", "battery dies in two hours after the update"):
        r = agent.resolve(msg)
        if r.evidence.sufficiency_level in ("WEAK", "INSUFFICIENT"):
            assert r.action != "AUTO_HANDLE" and r.stage_status["draft"] == "skipped" and r.draft is None
            if r.evidence.sufficiency_reason in ("weak_resolution_evidence", "mixed_resolution") and not r.risk.any_hard_block():
                assert r.decision.escalation.clarification_allowed
        else:
            assert r.action == "AUTO_HANDLE" or r.decision.blocking


def test_handoff_packet_carries_resolution_clusters(tmp_path):
    agent, _ = make_agent(tmp_path)
    r = agent.resolve("I already reset network settings twice and wifi still drops, third time contacting you")
    assert r.action == "HUMAN_HANDOFF" and r.handoff is not None
    assert r.handoff.evidence_level == r.evidence.sufficiency_level and r.handoff.resolution_confidence == r.evidence.resolution_confidence
    assert all(c.evidence_ids for c in r.handoff.resolution_candidates)


def test_compact_risk_schema_is_used_by_default(tmp_path):
    agent, prov = make_agent(tmp_path, default=json.dumps({"flags": ["high_impact"], "actionable": True, "summary": "urgent battery issue"}))
    r = agent.resolve("battery drains from 100 to 20 in an hour since the ios 11 update and I need the phone for work tomorrow")
    assert r.risk.high_impact and r.risk.source in ("llm+rules", "rules") and agent.cfg.risk_schema == "compact"
    t = agent.traces.read(r.trace_id)
    assert t.prompt_versions["risk"] == "risk-flags-v2" and t.prompt_versions["draft"] == "draft-v2"
