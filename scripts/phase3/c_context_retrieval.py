"""Phase 3-C: does intelligence improve evidence retrieval? Same Phase-2 protocol (resolution-match judge, DEV 500 for
selection, GOLDEN 197 once), same retriever (dense BGE-small, substantive-first, gate-v2). Variants:
  A  raw customer message                                  (Phase 2 baseline)
  B  bounded context text (issue text + short reply)
  C  B + predicted-intent boost (widen-not-discard RRF fusion at HIGH/MEDIUM confidence)
  D  C + query construction (canonical intent phrase at HIGH confidence)
Also records per-stage latency. Writes artifacts/intelligence/retrieval_intelligence.{json,md}.
  python scripts/phase3/c_context_retrieval.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

import resolveai  # noqa: F401
from resolveai.intelligence.classifier import IntentService
from resolveai.intelligence.context import build_context, parse_context
from resolveai.intelligence.query import build_query
from resolveai.retrieval import GateConfig, KnowledgeBase, Retriever, RetrieverConfig
from resolveai.retrieval.dense import SUPPORTED
from resolveai.retrieval.gate import decide

sys.path.insert(0, str(Path(__file__).parent.parent / "phase2"))
from run_retrieval_benchmark import TAU, TAU_SENS, ReplyJudge, dev_queries, golden_queries, summarize  # noqa: E402

OUT = Path("artifacts/intelligence")
VARIANTS = ("A_raw", "B_context", "C_context_intent", "D_context_intent_query")


def run(variant: str, retriever: Retriever, kb: KnowledgeBase, queries: pd.DataFrame, judge: ReplyJudge, svc: IntentService, gate: GateConfig):
    doc_by_cust = dict(zip(kb.rows.customer_tweet_id.astype(int), kb.rows.doc, strict=False))
    recs, lat, stage = [], [], {"context": [], "classify": [], "query": [], "retrieve": []}
    for _, q in queries.iterrows():
        t0 = time.perf_counter()
        b = build_context(q.customer_message, parse_context(q.get("context", "")))
        stage["context"].append((time.perf_counter() - t0) * 1000)
        intent = None
        if variant != "A_raw":
            t0 = time.perf_counter()
            intent = svc.classify(b)
            stage["classify"].append((time.perf_counter() - t0) * 1000)
        t0 = time.perf_counter()
        if variant == "A_raw":
            text, allowed, boost = q.customer_message, (), "none"
        elif variant == "B_context":
            text, allowed, boost = b.text_for_retrieval, (), "none"
        elif variant == "C_context_intent":
            plan = build_query(b, intent)
            text, allowed, boost = b.text_for_retrieval, plan.allowed_intents, plan.boost
        else:
            plan = build_query(b, intent)
            text, allowed, boost = plan.text, plan.allowed_intents, plan.boost
        stage["query"].append((time.perf_counter() - t0) * 1000)
        qi = q.intent if "intent" in q else None
        t0 = time.perf_counter()
        ev = retriever.retrieve(text, query_intent=qi, customer_author=(q.customer_author or None), query_created_at=q.created_at, allowed_intents=allowed, boost=boost)
        stage["retrieve"].append((time.perf_counter() - t0) * 1000)
        lat.append(sum(s[-1] for s in stage.values() if s))
        rel = judge.relevant_docs(q.brand_reply, TAU)
        rel_s = {t: judge.relevant_docs(q.brand_reply, t) for t in TAU_SENS}
        docs = [doc_by_cust[int(i.thread_id)] for i in ev.items]
        hit = next((r for r, d in enumerate(docs, start=1) if d in rel), None)
        ok, reason, sig = decide(ev.items, gate, qi, text)
        norm = [i.brand_reply.lower().strip() for i in ev.items]
        recs.append(dict(qid=q.qid, has_ref=bool(rel), hit_rank=hit, hits_sens={str(t): any(d in rel_s[t] for d in docs) for t in TAU_SENS}, n_retrieved=ev.n_retrieved,
                         top_ids=[i.evidence_id for i in ev.items], top_scores=[round(i.scores["final"], 5) for i in ev.items], top_cos=[round(i.scores["dense"], 3) for i in ev.items],
                         top_actions=[i.quality.action_class for i in ev.items], intent_represented=any(i.quality.intent_match for i in ev.items) if qi else None,
                         resolution_bearing=any(i.substantive and i.outcome == "positive" for i in ev.items), any_substantive=any(i.substantive for i in ev.items),
                         duplicate=len(norm) != len(set(norm)), sufficient=ok, reason=reason, top_similarity=sig.top_similarity, support_count=sig.support_count,
                         conflicting=sig.conflicting, intent_agreement=sig.intent_agreement, intent=qi, pred_intent=(intent.intent if intent else None), band=(intent.confidence_band if intent else None),
                         slices=dict(customer_seen_in_kb=bool(q.get("customer_seen_in_kb", False)), short=bool(q.short), multi_turn=bool(q.multi_turn), first_turn=not bool(q.multi_turn),
                                     multi_intent=bool(q.get("multi_intent", False)), taxonomy_gap=bool(q.get("taxonomy_gap", False)), insufficient_context=bool(q.get("insufficient_context", False)))))
    summ = summarize(recs, lat)
    summ["stage_latency_ms_p50"] = {k: round(float(np.percentile(v, 50)), 2) for k, v in stage.items() if v}
    summ["stage_latency_ms_p95"] = {k: round(float(np.percentile(v, 95)), 2) for k, v in stage.items() if v}
    return summ, recs


def main() -> None:
    kb = KnowledgeBase.build(dense_models=[SUPPORTED["bge-small"]], with_bm25=False)
    golden, dev = golden_queries(), dev_queries(500)
    kb.assert_isolated_from(set(golden.customer_tweet_id.astype(int)), "golden")
    judge = ReplyJudge(kb, golden.brand_reply.tolist() + dev.brand_reply.tolist())
    gate = GateConfig.load()
    retriever = Retriever(kb, RetrieverConfig(), gate=gate)
    svc = IntentService()
    results = {"dev": {}, "golden": {}}
    per_query = {}
    for v in VARIANTS:
        results["dev"][v], _ = run(v, retriever, kb, dev, judge, svc, gate)
        results["golden"][v], per_query[v] = run(v, retriever, kb, golden, judge, svc, gate)
        d, g = results["dev"][v], results["golden"][v]
        print(f"{v:24s} DEV R@5={d['recall@5']} MRR={d['mrr']} | GOLD R@1={g['recall@1']} R@3={g['recall@3']} R@5={g['recall@5']} MRR={g['mrr']} sameint={g['same_intent_recall@5']} resbear={g['resolution_bearing_recall@5']} suff={g['sufficient_rate']} lat={g['latency_ms']}")
    for v in VARIANTS:
        (OUT / f"per_query_golden_retrieval__{v}.jsonl").write_text("\n".join(json.dumps(r) for r in per_query[v]), encoding="utf-8")
    (OUT / "retrieval_intelligence.json").write_text(json.dumps(results, indent=1, default=str), encoding="utf-8")
    cols = ["recall@1", "recall@3", "recall@5", "mrr", "same_intent_recall@5", "resolution_bearing_recall@5", "any_substantive@5", "sufficient_rate", "duplicate_result_rate"]
    L = ["# Intent-aware retrieval (Phase 3-C)", "", "Same protocol and retriever as Phase 2 (dense BGE-small, substantive-first, gate-v2). Variants: A raw message; B bounded context; C B + intent boost (RRF fusion, never discards); D C + canonical intent phrase at HIGH confidence.", ""]
    for name, res in (("DEV (67 refs)", results["dev"]), ("GOLDEN (46 refs; once)", results["golden"])):
        L += [f"## {name}", "", "| variant | " + " | ".join(cols) + " | latency p50/p95 ms |", "|---|" + "---|" * (len(cols) + 1)]
        for v, m in res.items():
            L.append(f"| {v} | " + " | ".join(str(m.get(c)) for c in cols) + f" | {m['latency_ms']['p50']}/{m['latency_ms']['p95']} |")
        L.append("")
    g = results["golden"]
    L += ["## Slices (GOLDEN recall@5 / sufficient rate)", "", "| slice | " + " | ".join(VARIANTS) + " |", "|---|" + "---|" * len(VARIANTS)]
    for s in g["A_raw"]["slices"]:
        L.append(f"| {s} | " + " | ".join(f"{g[v]['slices'][s]['recall@5']} / {g[v]['slices'][s]['sufficient_rate']}" for v in VARIANTS) + " |")
    L += ["", "## Stage latency (GOLDEN, variant D, ms)", "", f"p50: {g['D_context_intent_query']['stage_latency_ms_p50']}", f"p95: {g['D_context_intent_query']['stage_latency_ms_p95']}", ""]
    (OUT / "retrieval_intelligence.md").write_text("\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    main()
