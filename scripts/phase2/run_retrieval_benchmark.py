"""Phase 2: reproducible retrieval benchmark.  python scripts/phase2/run_retrieval_benchmark.py [--dev-n 500] [--configs all]

Protocol
--------
Relevance ("resolution-match"): a retrieved KB case is relevant to a query iff (a) its brand reply is substantive (not a
DM handoff, >= 60 chars) and (b) the TF-IDF cosine between its brand reply and the query's OWN historical brand reply is
>= TAU. This asks "did the retriever find cases the brand resolved the same way", which is what grounding needs, without
any LLM or hand labels. Queries whose own reply is not substantive have no reference and are excluded from Recall/MRR
(their share is reported). The reply-side TF-IDF judge is independent of every retriever under test.

Two query sets: DEV = 500 holdout rows that are NOT golden (for tuning RRF k and the gate); GOLDEN = the frozen 197
(evaluated ONCE per configuration with frozen parameters; never used for tuning).

Outputs: artifacts/retrieval/{results.json, results.md, experiment_manifest.json, per_query_golden.jsonl,
gate_tuning.json, failure_candidates.json}; resolveai/retrieval/gate_config.json (frozen gate thresholds).
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
import platform
import sys
import time
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

import resolveai  # noqa: F401  (TF guard)
from resolveai import config
from resolveai.data.clean import is_dm_handoff
from resolveai.evaluation import load_golden
from resolveai.models.weak_labels import weak_intent
from resolveai.retrieval import GateConfig, KnowledgeBase, OutcomeBonus, Retriever, RetrieverConfig
from resolveai.retrieval.dense import SUPPORTED
from resolveai.retrieval.gate import decide

OUT = Path("artifacts/retrieval")
OUT.mkdir(parents=True, exist_ok=True)
TAU = 0.5
TAU_SENS = (0.4, 0.5, 0.6)
SEED = config.SEED
MINILM, BGE = SUPPORTED["minilm"], SUPPORTED["bge-small"]
NO_BONUS = OutcomeBonus(enabled=False)

MATRIX: dict[str, RetrieverConfig] = {
    "bm25": RetrieverConfig(method="bm25", model=MINILM, outcome_bonus=NO_BONUS),
    "dense:minilm": RetrieverConfig(method="dense", model=MINILM, outcome_bonus=NO_BONUS),
    "dense:bge-small": RetrieverConfig(method="dense", model=BGE, outcome_bonus=NO_BONUS),
    "hybrid:minilm": RetrieverConfig(method="hybrid", model=MINILM, outcome_bonus=NO_BONUS),
    "hybrid:bge-small": RetrieverConfig(method="hybrid", model=BGE, outcome_bonus=NO_BONUS),
    "hybrid:minilm+outcome": RetrieverConfig(method="hybrid", model=MINILM),
    "hybrid:bge-small+outcome": RetrieverConfig(method="hybrid", model=BGE),
    "hybrid:bge-small+subst": RetrieverConfig(method="hybrid", model=BGE, outcome_bonus=NO_BONUS, substantive_first=True),
    "hybrid:bge-small+outcome+subst": RetrieverConfig(method="hybrid", model=BGE, substantive_first=True),
    "hybrid:minilm+outcome+subst": RetrieverConfig(method="hybrid", model=MINILM, substantive_first=True),
}


# ---------------------------------------------------------------- query sets ----------------------------------------
def dev_queries(n: int) -> pd.DataFrame:
    sub = pd.read_csv(config.PROCESSED_DIR / "apple_pairs.csv", keep_default_na=False)
    gold_ids = set(load_golden().customer_tweet_id.astype(int))
    pool = sub[(sub.split == "holdout") & ~sub.customer_tweet_id.isin(gold_ids)]
    d = pool.sample(n=min(n, len(pool)), random_state=SEED).copy()
    d["qid"] = "dev" + d.customer_tweet_id.astype(str)
    d["intent"] = d.customer_message.map(weak_intent)  # weak: dev has no gold labels
    d["short"] = d.customer_message.str.len() < 40
    d["multi_turn"] = d.n_context_turns.astype(int) > 0
    for f in ("multi_intent", "taxonomy_gap", "insufficient_context"):
        d[f] = False
    return d


def golden_queries() -> pd.DataFrame:
    g = load_golden().copy()
    g["qid"] = g.gid
    authors_path = config.GOLDEN_DIR / "golden_customer_authors.csv"
    full = config.PROCESSED_DIR / "full_apple_pairs.csv"
    if not authors_path.exists() and full.exists():
        fa = pd.read_csv(full, usecols=["customer_tweet_id", "customer_author"])
        m = g[["gid", "customer_tweet_id"]].astype({"customer_tweet_id": int}).merge(fa, on="customer_tweet_id", how="left")
        m[["gid", "customer_author"]].to_csv(authors_path, index=False)
    if authors_path.exists():
        g = g.merge(pd.read_csv(authors_path, dtype=str), on="gid", how="left")
    else:
        g["customer_author"] = ""
    g["customer_seen_in_kb"] = g.customer_seen_in_kb.astype(str).str.lower().eq("true")
    g["short"] = g.customer_message.str.len() < 40
    g["multi_turn"] = g.n_context_turns.astype(int) > 0
    return g


# ---------------------------------------------------------------- relevance judge ------------------------------------
class ReplyJudge:
    """Reply-side TF-IDF similarity between a query's own reply and each substantive KB reply."""

    def __init__(self, kb: KnowledgeBase, refs: list[str]):
        self.sub_idx = np.where(kb.rows.substantive.values)[0]
        kb_replies = kb.rows.brand_reply.iloc[self.sub_idx].tolist()
        self.vec = TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True, stop_words="english").fit(kb_replies + refs)
        self.K = self.vec.transform(kb_replies)
        self.doc_pos = {int(d): j for j, d in enumerate(self.sub_idx)}

    def relevant_docs(self, ref_reply: str, tau: float) -> set[int]:
        if not ref_reply or is_dm_handoff(ref_reply) or len(ref_reply) < 60:
            return set()
        sims = cosine_similarity(self.vec.transform([ref_reply]), self.K)[0]
        return {int(self.sub_idx[j]) for j in np.where(sims >= tau)[0]}


# ---------------------------------------------------------------- metrics ---------------------------------------------
def evaluate(retriever: Retriever, kb: KnowledgeBase, queries: pd.DataFrame, judge: ReplyJudge, *, with_intent: bool, gate: GateConfig) -> tuple[dict, list[dict]]:
    rows = kb.rows
    doc_by_cust = dict(zip(rows.customer_tweet_id.astype(int), rows.doc, strict=False))
    recs, lat = [], []
    for _, q in queries.iterrows():
        ev = retriever.retrieve(q.customer_message, query_intent=(q.intent if with_intent else None),
                                customer_author=(q.customer_author or None), query_created_at=q.created_at)
        lat.append(ev.latency_ms)
        rel = judge.relevant_docs(q.brand_reply, TAU)
        rel_s = {t: judge.relevant_docs(q.brand_reply, t) for t in TAU_SENS}
        docs = [doc_by_cust[int(i.thread_id)] for i in ev.items]
        hit_rank = next((r for r, d in enumerate(docs, start=1) if d in rel), None)
        ok, reason, sig = decide(ev.items, gate, q.intent if with_intent else None, q.customer_message)
        norm = [i.brand_reply.lower().strip() for i in ev.items]
        recs.append(dict(
            qid=q.qid, has_ref=bool(rel), hit_rank=hit_rank, hits_sens={str(t): any(d in rel_s[t] for d in docs) for t in TAU_SENS},
            n_retrieved=ev.n_retrieved, top_ids=[i.evidence_id for i in ev.items], top_scores=[round(i.scores["final"], 5) for i in ev.items],
            top_cos=[round(i.scores["dense"], 3) for i in ev.items], top_actions=[i.quality.action_class for i in ev.items],
            intent_represented=(any(i.quality.intent_match for i in ev.items) if with_intent else None),
            resolution_bearing=any(i.substantive and i.outcome == "positive" for i in ev.items),
            any_substantive=any(i.substantive for i in ev.items),
            duplicate=len(norm) != len(set(norm)), sufficient=ok, reason=reason, top_similarity=sig.top_similarity,
            support_count=sig.support_count, conflicting=sig.conflicting, intent_agreement=sig.intent_agreement,
            slices=dict(customer_seen_in_kb=bool(q.get("customer_seen_in_kb", False)), short=bool(q.short), multi_turn=bool(q.multi_turn),
                        multi_intent=bool(q.get("multi_intent", False)), taxonomy_gap=bool(q.get("taxonomy_gap", False)),
                        insufficient_context=bool(q.get("insufficient_context", False)), first_turn=not bool(q.multi_turn)),
            intent=q.intent,
        ))
    return summarize(recs, lat), recs


def summarize(recs: list[dict], lat: list[float]) -> dict:
    ref = [r for r in recs if r["has_ref"]]

    def recall(rs, k):
        return round(sum(1 for r in rs if r["hit_rank"] and r["hit_rank"] <= k) / len(rs), 4) if rs else None

    def mrr(rs):
        return round(sum(1 / r["hit_rank"] for r in rs if r["hit_rank"]) / len(rs), 4) if rs else None

    m = {
        "n_queries": len(recs), "n_with_reference": len(ref), "no_reference_share": round(1 - len(ref) / len(recs), 4),
        "recall@1": recall(ref, 1), "recall@3": recall(ref, 3), "recall@5": recall(ref, 5), "mrr": mrr(ref),
        "recall@5_tau": {t: round(sum(1 for r in ref if r["hits_sens"][t]) / len(ref), 4) for t in ("0.4", "0.5", "0.6")} if ref else None,
        "same_intent_recall@5": round(sum(1 for r in recs if r["intent_represented"]) / len(recs), 4) if recs and recs[0]["intent_represented"] is not None else None,
        "resolution_bearing_recall@5": round(sum(1 for r in recs if r["resolution_bearing"]) / len(recs), 4),
        "any_substantive@5": round(sum(1 for r in recs if r["any_substantive"]) / len(recs), 4),
        "no_result_rate": round(sum(1 for r in recs if r["n_retrieved"] == 0) / len(recs), 4),
        "duplicate_result_rate": round(sum(1 for r in recs if r["duplicate"]) / len(recs), 4),
        "sufficient_rate": round(sum(1 for r in recs if r["sufficient"]) / len(recs), 4),
        "gate_precision_hit@5_given_sufficient": _cond(ref, lambda r: r["sufficient"], lambda r: bool(r["hit_rank"]) and r["hit_rank"] <= 5),
        "gate_recall_sufficient_given_hit@5": _cond(ref, lambda r: bool(r["hit_rank"]) and r["hit_rank"] <= 5, lambda r: r["sufficient"]),
        "gate_reasons": pd.Series([r["reason"] for r in recs]).value_counts().to_dict(),
        "latency_ms": {"p50": round(float(np.percentile(lat, 50)), 1), "p95": round(float(np.percentile(lat, 95)), 1), "p99": round(float(np.percentile(lat, 99)), 1)},
        "slices": {},
    }
    for s in ("customer_seen_in_kb", "short", "multi_turn", "first_turn", "multi_intent", "taxonomy_gap", "insufficient_context"):
        sl = [r for r in ref if r["slices"][s]]
        allsl = [r for r in recs if r["slices"][s]]
        if allsl:
            m["slices"][s] = {"n": len(allsl), "n_ref": len(sl), "recall@5": recall(sl, 5), "mrr": mrr(sl),
                              "sufficient_rate": round(sum(1 for r in allsl if r["sufficient"]) / len(allsl), 4),
                              "same_intent_recall@5": (round(sum(1 for r in allsl if r["intent_represented"]) / len(allsl), 4) if allsl[0]["intent_represented"] is not None else None)}
    return m


def _cond(rs, cond, target):
    c = [r for r in rs if cond(r)]
    return round(sum(1 for r in c if target(r)) / len(c), 4) if c else None


# ---------------------------------------------------------------- gate tuning (DEV only) ------------------------------
def tune_gate(retriever: Retriever, kb: KnowledgeBase, dev: pd.DataFrame, judge: ReplyJudge) -> tuple[GateConfig, dict]:
    """Grid search on DEV: maximise coverage (sufficient rate) subject to precision P(hit@5 | sufficient) >= 0.80."""
    base = GateConfig()
    doc_by_cust = dict(zip(kb.rows.customer_tweet_id.astype(int), kb.rows.doc, strict=False))
    cache = []
    for _, q in dev.iterrows():
        ev = retriever.retrieve(q.customer_message, query_intent=q.intent, customer_author=q.customer_author or None, query_created_at=q.created_at)
        rel = judge.relevant_docs(q.brand_reply, TAU)
        docs = [doc_by_cust[int(i.thread_id)] for i in ev.items]
        cache.append((ev.items, bool(rel), any(d in rel for d in docs), q.customer_message))
    grid = list(itertools.product([0.35, 0.45, 0.55], [0.55, 0.65, 0.75, 0.85], [1, 2, 3], [0.4, 0.6]))
    results = []
    for floor, supp, ms, agree in grid:
        cfg = replace(base, relevance_floor=floor, support_similarity=supp, min_support=ms, min_intent_agreement=agree)
        dec = [(decide(items, cfg, None, qtext)[0], has_ref, hit) for items, has_ref, hit, qtext in cache]
        withref = [(s, h) for s, r, h in dec if r]
        suff = [h for s, h in withref if s]
        prec = (sum(suff) / len(suff)) if suff else 0.0
        cov = sum(1 for s, _, _ in dec if s) / len(dec)
        results.append({"relevance_floor": floor, "support_similarity": supp, "min_support": ms, "min_intent_agreement": agree,
                        "precision": round(prec, 4), "coverage": round(cov, 4), "n_sufficient_with_ref": len(suff)})
    feasible = [r for r in results if r["precision"] >= 0.80 and r["n_sufficient_with_ref"] >= 20]
    best = max(feasible, key=lambda r: (r["coverage"], r["precision"])) if feasible else max(results, key=lambda r: (r["precision"], r["coverage"]))
    chosen = replace(base, **{k: best[k] for k in ("relevance_floor", "support_similarity", "min_support", "min_intent_agreement")})
    return chosen, {"objective": "max coverage s.t. precision(hit@5|sufficient) >= 0.80 on DEV, >= 20 sufficient refs", "grid_size": len(grid),
                    "chosen": best, "feasible": len(feasible), "top10": sorted(results, key=lambda r: (-r["coverage"], -r["precision"]))[:10] if feasible else results[:10]}


# ---------------------------------------------------------------- resumable cache --------------------------------------
_EVAL_CACHE = config.CACHE_DIR / "retrieval_bench"


def cached_evaluate(tag: str, retriever: Retriever, kb: KnowledgeBase, queries: pd.DataFrame, judge: ReplyJudge, *, with_intent: bool, gate: GateConfig) -> tuple[dict, list[dict]]:
    """Expensive evaluate() results keyed by (tag, config, gate, kb corpus hash, query ids). Delete .cache/retrieval_bench to recompute."""
    _EVAL_CACHE.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(json.dumps({"tag": tag, "cfg": asdict(retriever.cfg), "gate": asdict(gate), "kb": kb.manifest["corpus_hash"], "q": list(queries.qid), "tau": TAU}, sort_keys=True, default=str).encode()).hexdigest()[:20]
    p = _EVAL_CACHE / f"{key}.json"
    if p.exists():
        d = json.loads(p.read_text(encoding="utf-8"))
        return d["summary"], d["records"]
    summary, records = evaluate(retriever, kb, queries, judge, with_intent=with_intent, gate=gate)
    p.write_text(json.dumps({"summary": summary, "records": records}, default=str), encoding="utf-8")
    return summary, records


# ---------------------------------------------------------------- main ------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dev-n", type=int, default=500)
    ap.add_argument("--configs", default="all")
    a = ap.parse_args()
    t_all = time.perf_counter()

    kb = KnowledgeBase.build(dense_models=[MINILM, BGE])
    golden = golden_queries()
    kb.assert_isolated_from(set(golden.customer_tweet_id.astype(int)), "golden")
    dev = dev_queries(a.dev_n)
    kb.assert_isolated_from(set(dev.customer_tweet_id.astype(int)), "dev")
    judge = ReplyJudge(kb, golden.brand_reply.tolist() + dev.brand_reply.tolist())
    names = list(MATRIX) if a.configs == "all" else a.configs.split(",")

    # 1. DEV: full matrix with the default gate (gate not yet tuned) + RRF k sensitivity for the bge hybrid
    dev_results, dev_rrf = {}, {}
    default_gate = GateConfig()
    for n in names:
        r = Retriever(kb, MATRIX[n], gate=default_gate)
        dev_results[n], _ = cached_evaluate("dev", r, kb, dev, judge, with_intent=True, gate=default_gate)
        print(f"dev  {n:32s} R@1={dev_results[n]['recall@1']} R@5={dev_results[n]['recall@5']} MRR={dev_results[n]['mrr']} subst@5={dev_results[n]['any_substantive@5']}")
    for k in (20, 60, 100):
        r = Retriever(kb, replace(MATRIX["hybrid:bge-small"], rrf_k=k), gate=default_gate)
        dev_rrf[k], _ = cached_evaluate("dev-rrf", r, kb, dev, judge, with_intent=True, gate=default_gate)
        print(f"dev  rrf_k={k:3d} R@5={dev_rrf[k]['recall@5']} MRR={dev_rrf[k]['mrr']}")

    # 2. pick the best DEV config by (recall@5, mrr, any_substantive@5) among hybrids and tune the gate on DEV with it
    order = sorted(names, key=lambda n: (dev_results[n]["recall@5"] or 0, dev_results[n]["mrr"] or 0, dev_results[n]["any_substantive@5"]), reverse=True)
    best_name = order[0]
    best_k = max(dev_rrf, key=lambda k: (dev_rrf[k]["recall@5"] or 0, dev_rrf[k]["mrr"] or 0))
    best_cfg = replace(MATRIX[best_name], rrf_k=best_k) if MATRIX[best_name].method == "hybrid" else MATRIX[best_name]
    gate, tuning = tune_gate(Retriever(kb, best_cfg, gate=default_gate), kb, dev, judge)
    gate.save()
    (OUT / "gate_tuning.json").write_text(json.dumps(tuning, indent=2), encoding="utf-8")
    print("gate frozen:", asdict(gate))

    # 3. GOLDEN: evaluated once per config with the frozen gate
    golden_results, per_query = {}, {}
    for n in names:
        cfg = replace(MATRIX[n], rrf_k=best_k) if MATRIX[n].method == "hybrid" else MATRIX[n]
        r = Retriever(kb, cfg, gate=gate)
        golden_results[n], per_query[n] = cached_evaluate("golden", r, kb, golden, judge, with_intent=True, gate=gate)
        print(f"gold {n:32s} R@1={golden_results[n]['recall@1']} R@5={golden_results[n]['recall@5']} MRR={golden_results[n]['mrr']} suff={golden_results[n]['sufficient_rate']}")
    final_name = best_name
    with (OUT / "per_query_golden.jsonl").open("w", encoding="utf-8") as f:
        for rec in per_query[final_name]:
            f.write(json.dumps(rec) + "\n")
    misses = [r for r in per_query[final_name] if r["has_ref"] and not (r["hit_rank"] and r["hit_rank"] <= 5)]
    (OUT / "failure_candidates.json").write_text(json.dumps(misses, indent=1), encoding="utf-8")

    # 4. artifacts
    env = {"platform": platform.platform(), "python": sys.version.split()[0], "cpu_count": os.cpu_count(), "processor": platform.processor()}
    manifest = {
        "protocol": {"relevance": "resolution-match: substantive KB reply with reply-side TF-IDF cosine >= tau to the query's own historical reply", "tau": TAU, "tau_sensitivity": TAU_SENS,
                     "query": "customer_message only (context not used as query in this phase)", "dev": {"n": len(dev), "source": "holdout rows not in golden, seed 42"},
                     "golden": {"n": len(golden), "sha256": json.loads((config.GOLDEN_DIR / "golden_freeze_manifest.json").read_text())["sha256"], "evaluated_once_per_config": True}},
        "kb": kb.manifest, "timings_s": {k: round(v, 2) for k, v in kb.timings.items()},
        "configs": {n: {**asdict(MATRIX[n]), "outcome_bonus": asdict(MATRIX[n].outcome_bonus)} for n in names},
        "rrf_k_sensitivity_dev": {str(k): {"recall@5": v["recall@5"], "mrr": v["mrr"]} for k, v in dev_rrf.items()},
        "selected": {"config": final_name, "rrf_k": best_k, "selection_rule": "highest DEV recall@5, then MRR, then any_substantive@5; golden used once for reporting"},
        "gate": asdict(gate), "gate_tuning": tuning["chosen"], "bm25": {"k1": 1.5, "b": 0.75, "tokenizer": "see resolveai/retrieval/bm25.py"},
        "environment": env, "seed": SEED, "total_runtime_s": round(time.perf_counter() - t_all, 1),
        "code_hash": hashlib.sha256(b"".join(Path(p).read_bytes() for p in sorted(Path("resolveai/retrieval").glob("*.py")))).hexdigest()[:16],
    }
    (OUT / "experiment_manifest.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    (OUT / "results.json").write_text(json.dumps({"dev": dev_results, "golden": golden_results}, indent=2, default=str), encoding="utf-8")
    write_md(dev_results, golden_results, final_name, gate, tuning, manifest)
    print("done in", manifest["total_runtime_s"], "s")


def write_md(dev: dict, gold: dict, final: str, gate: GateConfig, tuning: dict, man: dict) -> None:
    cols = ["recall@1", "recall@3", "recall@5", "mrr", "same_intent_recall@5", "resolution_bearing_recall@5", "any_substantive@5", "no_result_rate", "duplicate_result_rate", "sufficient_rate", "gate_precision_hit@5_given_sufficient"]
    L = ["# Retrieval benchmark results", "", f"Protocol: {man['protocol']['relevance']} (tau={TAU}). DEV n={man['protocol']['dev']['n']} (tuning). GOLDEN n={man['protocol']['golden']['n']} (final, once).", ""]
    for title, res in (("DEV (default gate; used for selection and tuning)", dev), ("GOLDEN (frozen gate; final)", gold)):
        L += [f"## {title}", "", "| config | " + " | ".join(cols) + " |", "|---|" + "---|" * len(cols)]
        for n, m in res.items():
            L.append(f"| {n}{' **(selected)**' if n == final else ''} | " + " | ".join(str(m.get(c)) for c in cols) + " |")
        L.append("")
    g = gold[final]
    L += [f"## Difficult slices, GOLDEN, {final}", "", "| slice | n | n_ref | recall@5 | mrr | same_intent_recall@5 | sufficient_rate |", "|---|---|---|---|---|---|---|"]
    for s, v in g["slices"].items():
        L.append(f"| {s} | {v['n']} | {v['n_ref']} | {v['recall@5']} | {v['mrr']} | {v['same_intent_recall@5']} | {v['sufficient_rate']} |")
    L += ["", f"Gate reasons (GOLDEN): {g['gate_reasons']}", "", f"Latency ms (GOLDEN, {final}): {g['latency_ms']}", "",
          f"tau sensitivity recall@5 (GOLDEN, {final}): {g['recall@5_tau']}", "",
          "## Frozen gate (tuned on DEV only)", "", f"`{asdict(gate)}`  chosen from grid: {tuning['chosen']}", "",
          "## Timings", "", f"`{man['timings_s']}` on {man['environment']}", ""]
    (OUT / "results.md").write_text("\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    main()
