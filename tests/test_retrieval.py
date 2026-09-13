"""Retrieval engine tests. Deterministic; the heavy parts (real embeddings) run on a tiny synthetic KB with a fake embedder."""
import numpy as np
import pandas as pd
import pytest

from resolveai import config
from resolveai.retrieval.bm25 import BM25Index, tokenize
from resolveai.retrieval.dense import DenseIndex, texts_hash
from resolveai.retrieval.fusion import rrf
from resolveai.retrieval.gate import GateConfig, decide
from resolveai.retrieval.kb import KnowledgeBase, load_kb_rows
from resolveai.retrieval.rerank import OutcomeBonus, apply_bonus
from resolveai.schemas.evidence import EvidenceItem, EvidenceQuality, EvidenceSet


# ------------------------------------------------------------------ helpers -----------------------------------------
def item(rank, cos, *, substantive=True, outcome="none", intent="battery_power", action="restart", same_customer=False, dm=False, reply="Try a restart."):
    return EvidenceItem(evidence_id=str(100 + rank), thread_id=str(rank), source_row_id=str(rank), customer_message="m", brand_reply=reply,
                        created_at="2017-11-01", outcome=outcome, dm_handoff=dm, substantive=substantive, retrieval_method="t", rank=rank,
                        quality=EvidenceQuality(semantic_relevance=cos, lexical_relevance=1.0, candidate_intent=intent, action_class=action,
                                                same_customer=same_customer, resolution_relevance=substantive, quality="strong" if cos >= 0.7 else "usable" if cos >= 0.55 else "weak"))


G = GateConfig(relevance_floor=0.45, support_similarity=0.6, min_support=2, min_intent_agreement=0.5)


# ------------------------------------------------------------------ BM25 --------------------------------------------
def test_tokenizer_keeps_versions_tokens_and_negation():
    assert tokenize("My iPhone is NOT charging on iOS 11.1.1, call <PHONE> <url>") == ["iphone", "not", "charging", "ios", "11.1.1", "call", "<phone>", "<url>"]


def test_bm25_ranks_lexical_overlap_and_reports_no_result():
    idx = BM25Index(["battery drains fast after update", "wifi keeps disconnecting", "screen cracked"])
    hits = idx.search("battery drains", 3)
    assert hits[0][0] == 0 and all(s > 0 for _, s in hits)
    assert idx.search("zzz qqq", 3) == []


# ------------------------------------------------------------------ dense -------------------------------------------
def test_dense_index_returns_nearest_and_cosines():
    X = np.array([[1, 0], [0, 1], [0.7, 0.7]], dtype="float32")
    X /= np.linalg.norm(X, axis=1, keepdims=True)
    d = DenseIndex(X)
    hits = d.search(np.array([1, 0], dtype="float32"), 2)
    assert hits[0][0] == 0 and hits[1][0] == 2
    assert np.allclose(d.cosine(np.array([1, 0], dtype="float32"), [0, 1]), [1.0, 0.0])


def test_embedding_cache_key_is_deterministic_and_content_sensitive():
    a = texts_hash(["x", "y"])
    assert a == texts_hash(["x", "y"]) and a != texts_hash(["y", "x"]) and a != texts_hash(["x", "y "])


# ------------------------------------------------------------------ RRF ---------------------------------------------
def test_rrf_combines_rank_lists_without_scores():
    fused = rrf({"bm25": [1, 2, 3], "dense": [3, 1, 4]}, k=60)
    ids = [d for d, _, _ in fused]
    assert ids[:2] == [1, 3] and fused[0][2] == {"bm25": 1, "dense": 2}
    assert abs(fused[0][1] - (1 / 61 + 1 / 62)) < 1e-9
    assert rrf({"a": [7]}, k=60) == [(7, 1 / 61, {"a": 1})]
    assert rrf({"a": [], "b": []}) == []


def test_rrf_ties_are_deterministic():
    fused = rrf({"a": [5, 9], "b": [9, 5]})
    assert [d for d, _, _ in fused] == [5, 9]


# ------------------------------------------------------------------ outcome bonus ------------------------------------
def test_outcome_bonus_is_small_and_cannot_overturn_strong_evidence():
    b = OutcomeBonus()
    c = [dict(doc=1, rrf=1 / 61, outcome="none", substantive=False, dm_handoff=True),
         dict(doc=2, rrf=1 / 62, outcome="positive", substantive=True, dm_handoff=False),
         dict(doc=3, rrf=1 / 80, outcome="positive", substantive=True, dm_handoff=False)]
    out = apply_bonus(c, b)
    assert [x["doc"] for x in out] == [2, 1, 3]                 # near-tie reordered, rank-3 laggard not promoted
    assert out[0]["outcome_bonus"] == b.positive + b.substantive and out[1]["outcome_bonus"] == b.dm_handoff
    assert max(abs(x["outcome_bonus"]) for x in out) < 1 / 60 - 1 / 63   # bounded by ~3 RRF ranks
    off = apply_bonus([dict(x) for x in c], OutcomeBonus(enabled=False))
    assert [x["doc"] for x in off] == [1, 2, 3] and all(x["outcome_bonus"] == 0 for x in off)


# ------------------------------------------------------------------ gate ---------------------------------------------
def test_gate_reason_priority_and_sufficiency():
    assert decide([], G)[1] == "no_relevant_evidence"
    assert decide([item(1, 0.40), item(2, 0.39)], G)[1] == "no_relevant_evidence"
    assert decide([item(1, 0.55), item(2, 0.5)], G)[1] == "weak_similarity"
    same = [item(1, 0.8, same_customer=True), item(2, 0.75, same_customer=True), item(3, 0.5)]
    assert decide(same, G)[1] == "customer_history_risk"
    ambiguous = [item(1, 0.8, intent="battery_power"), item(2, 0.78, intent="connectivity"), item(3, 0.7, intent="apps_services"), item(4, 0.65, intent="other")]
    assert decide(ambiguous, G)[1] == "ambiguous_intent"
    conflict = [item(1, 0.8, action="update"), item(2, 0.78, action="reset"), item(3, 0.7, action="restart")]
    assert decide(conflict, G)[1] == "conflicting_evidence"
    thin = [item(1, 0.8), item(2, 0.5, substantive=False)]
    assert decide(thin, G)[1] == "insufficient_resolution_evidence"
    clarify_only = [item(1, 0.9, action="ask_info"), item(2, 0.85, action="ask_info"), item(3, 0.8, action="other")]
    assert decide(clarify_only, G)[1] == "insufficient_resolution_evidence"     # questions are not resolutions
    assert decide([item(1, 0.99), item(2, 0.99)], G, query="<url>")[1] == "insufficient_query"
    assert decide([item(1, 0.99), item(2, 0.99)], G, query="fix this")[1] == "insufficient_query"
    assert decide([item(1, 0.8), item(2, 0.7)], G, query="battery drains fast after update")[0]
    ok, reason, sig = decide([item(1, 0.8, outcome="positive"), item(2, 0.7), item(3, 0.5, substantive=False, dm=True)], G)
    assert ok and reason == "strong_consistent_evidence" and sig.support_count == 2 and sig.resolution_bearing == 1


def test_gate_does_not_count_same_customer_as_independent_support():
    items = [item(1, 0.9, same_customer=True), item(2, 0.8), item(3, 0.7)]
    ok, reason, sig = decide(items, G)
    assert ok and sig.support_count == 2 and sig.same_customer_count == 1


def test_gate_config_round_trip(tmp_path):
    p = tmp_path / "g.json"
    G.save(p)
    import json

    assert json.loads(p.read_text())["support_similarity"] == 0.6


def test_evidence_set_distinguishes_retrieved_relevant_sufficient():
    es = EvidenceSet(items=[item(1, 0.8), item(2, 0.3)], n_retrieved=2, n_relevant=1, sufficient=False, sufficiency_reason="insufficient_resolution_evidence")
    assert len(es.items) == 2 and len(es.relevant) == 1 and not es.sufficient


# ------------------------------------------------------------------ KB invariants (real data) ------------------------
@pytest.mark.skipif(not (config.PROCESSED_DIR / "apple_pairs.csv").exists(), reason="subsample missing")
def test_kb_rows_are_kb_split_eligible_deterministic_and_pii_safe():
    from resolveai.evaluation import load_golden
    from resolveai.trust.pii import contains_unredacted_pii

    rows = load_kb_rows()
    assert (rows.split == "kb").all() and rows.customer_tweet_id.is_unique and list(rows.doc) == list(range(len(rows)))
    # Phase 9: the corrected phone pattern finds sentence-end numbers the pre-Phase-9 redactor missed in the frozen corpus. The processed data
    # is manifest-hashed and not rewritten; evidence is redacted again when retrieval builds items. Pin the measured gap so it cannot grow silently.
    from resolveai.trust.pii import redact_pii
    gap = rows.customer_message[rows.customer_message.map(contains_unredacted_pii)]
    assert len(gap) == 4, f"expected the 4 measured pre-Phase-9 misses, found {len(gap)}"
    assert all(set(redact_pii(t).counts) == {"PHONE"} and not contains_unredacted_pii(redact_pii(t).text) for t in gap)
    kb = KnowledgeBase(rows=rows, manifest={"kb_max_created_at": str(rows.created_at.max()), "holdout_min_created_at": "2017-11-28"})
    kb.assert_eligible()
    kb.assert_isolated_from(set(load_golden().customer_tweet_id.astype(int)))
    with pytest.raises(AssertionError):
        kb.assert_isolated_from({int(rows.customer_tweet_id.iloc[0])}, "fake")
    assert not kb.temporally_eligible(0, pd.Timestamp("2017-01-01", tz="UTC")) and kb.temporally_eligible(0, pd.Timestamp("2018-01-01", tz="UTC"))


def test_malformed_kb_row_is_rejected():
    with pytest.raises(AssertionError):
        rows = pd.DataFrame({"split": ["kb", "holdout"], "customer_tweet_id": [1, 2], "brand_tweet_id": [3, 4], "created_at": pd.to_datetime(["2017-11-01", "2017-11-02"], utc=True)})
        KnowledgeBase(rows=rows, manifest={"kb_max_created_at": "2017-11-02", "holdout_min_created_at": "2017-11-28"}).assert_eligible()


def test_provenance_fields_present_on_items():
    it = item(1, 0.8)
    d = it.model_dump()
    for k in ("evidence_id", "thread_id", "source_row_id", "customer_message", "brand_reply", "created_at", "retrieval_method", "rank", "scores", "quality", "outcome", "source"):
        assert k in d
