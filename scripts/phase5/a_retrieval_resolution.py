"""Phase 5-A: reply-side / dual retrieval + resolution reranking benchmark, same protocol as Phase 2/3
(resolution-match judge, DEV 500 for tuning, GOLDEN once). Variants:
  A  customer index (Phase 2 default: dense BGE-small, substantive-first, gate-v2)
  B  reply index only            B2 pair index only
  C  dual customer+reply (RRF)   C2 dual customer+pair (RRF)
  D  best dual + resolution reranker (weights tuned on DEV) + gate-v3 (calibrated on hand-checked DEV verdicts)
Extra metrics: resolution-bearing Recall@1/3/5 (a reply whose non-question sentences state an instruction or released
fix, resolution.is_resolution_bearing) and same-resolution Recall@k (Phase-2 judge).
Two steps, so that nothing is tuned on golden and the gate is calibrated on hand-checked DEV verdicts (the automatic
same-resolution judge scored 0 precision for every gate, as in Phase 2):
  python scripts/phase5/a_retrieval_resolution.py --dev     # variants on DEV, tune weights, write gate_v3_handcheck_sheet.md
  (hand-label the sheet into gate_v3_handcheck.json)
  python scripts/phase5/a_retrieval_resolution.py --final   # choose + freeze gate_v3_config.json from the labels, GOLDEN once
Writes artifacts/resolution/retrieval_{results.json,results.md}, rerank_weights.json, gate_v3_config.json (frozen into the package).
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np
import pandas as pd

import resolveai  # noqa: F401
from resolveai.retrieval import GateConfig, KnowledgeBase, Retriever, RetrieverConfig
from resolveai.retrieval.dense import SUPPORTED
from resolveai.retrieval.resolution import GateV3Config, RerankWeights, decide_v3

sys.path.insert(0, str(Path(__file__).parent.parent / "phase2"))
from run_retrieval_benchmark import TAU, ReplyJudge, dev_queries, golden_queries  # noqa: E402

OUT = Path("artifacts/resolution")
OUT.mkdir(parents=True, exist_ok=True)
BGE = SUPPORTED["bge-small"]
V2 = dict(method="dense", model=BGE, rerank="none", gate="v2", substantive_first=True)
VARIANTS = {
    "A_customer_v2": RetrieverConfig(paths=("customer",), **V2),
    "B_reply_v2": RetrieverConfig(paths=("reply",), **V2),
    "B2_pair_v2": RetrieverConfig(paths=("pair",), **V2),
    "C_dual_customer_reply_v2": RetrieverConfig(paths=("customer", "reply"), **V2),
    "C2_dual_customer_pair_v2": RetrieverConfig(paths=("customer", "pair"), **V2),
}
CANDIDATE_GATES = {   # support similarity is never below the gate-v2 level (0.85); the knobs are consistency and support
    "share0.5_ms2": GateV3Config(min_top_share=0.5, min_support=2, t_sufficient=0.45),
    "share0.6_ms2": GateV3Config(min_top_share=0.6, min_support=2, t_sufficient=0.45),
    "share0.7_ms2": GateV3Config(min_top_share=0.7, min_support=2, t_sufficient=0.45),
    "share0.6_ms3": GateV3Config(min_top_share=0.6, min_support=3, t_sufficient=0.55),
    "share0.7_ms3": GateV3Config(min_top_share=0.7, min_support=3, t_sufficient=0.55),
}
SHEET = OUT / "gate_v3_handcheck_sheet.md"
LABELS = OUT / "gate_v3_handcheck.json"
STATE = OUT / "_dev_state.json"


def run(name: str, retriever: Retriever, kb: KnowledgeBase, queries: pd.DataFrame, judge: ReplyJudge) -> tuple[dict, list[dict]]:
    doc_by_cust = dict(zip(kb.rows.customer_tweet_id.astype(int), kb.rows.doc, strict=False))
    recs, lat = [], []
    for _, q in queries.iterrows():
        ev = retriever.retrieve(q.customer_message, query_intent=q.intent, customer_author=(q.customer_author or None), query_created_at=q.created_at)
        lat.append(ev.latency_ms)
        rel = judge.relevant_docs(q.brand_reply, TAU)
        docs = [doc_by_cust[int(i.thread_id)] for i in ev.items]
        hit = next((r for r, d in enumerate(docs, start=1) if d in rel), None)
        resb = next((r for r, i in enumerate(ev.items, start=1) if i.quality.resolution_relevance), None)
        recs.append(dict(qid=q.qid, has_ref=bool(rel), hit_rank=hit, res_rank=resb, sufficient=ev.sufficient, level=ev.sufficiency_level, reason=ev.sufficiency_reason,
                         rc=ev.resolution_confidence, consistency=ev.consistency, n_cands=len(ev.resolution_candidates), sources=[i.retrieval_source for i in ev.items],
                         intent_represented=any(i.quality.intent_match for i in ev.items), top_ids=[i.evidence_id for i in ev.items],
                         slices=dict(short=bool(q.short), multi_turn=bool(q.multi_turn), first_turn=not bool(q.multi_turn), customer_seen_in_kb=bool(q.get("customer_seen_in_kb", False)),
                                     multi_intent=bool(q.get("multi_intent", False)), insufficient_context=bool(q.get("insufficient_context", False)))))
    return summarize(recs, lat), recs


def _counts(xs) -> dict:
    return {k: int(v) for k, v in pd.Series([str(x) for x in xs]).value_counts().items()}


def summarize(recs, lat) -> dict:
    ref = [r for r in recs if r["has_ref"]]
    rk = lambda rs, key, k: round(sum(1 for r in rs if r[key] and r[key] <= k) / len(rs), 4) if rs else None  # noqa: E731
    mrr = lambda rs, key: round(sum(1 / r[key] for r in rs if r[key]) / len(rs), 4) if rs else None  # noqa: E731
    suff = [r for r in recs if r["sufficient"]]
    m = {"n": len(recs), "n_ref": len(ref), "recall@1": rk(ref, "hit_rank", 1), "recall@3": rk(ref, "hit_rank", 3), "recall@5": rk(ref, "hit_rank", 5), "mrr": mrr(ref, "hit_rank"),
         "resolution_bearing@1": rk(recs, "res_rank", 1), "resolution_bearing@3": rk(recs, "res_rank", 3), "resolution_bearing@5": rk(recs, "res_rank", 5), "resolution_mrr": mrr(recs, "res_rank"),
         "same_intent@5": round(sum(1 for r in recs if r["intent_represented"]) / len(recs), 4),
         "sufficient_rate": round(len(suff) / len(recs), 4), "levels": _counts(r["level"] for r in recs), "reasons": _counts(r["reason"] for r in recs), "consistency": _counts(r["consistency"] for r in recs),
         "gate_precision_same_resolution_hit@5": (round(sum(1 for r in suff if r["has_ref"] and r["hit_rank"] and r["hit_rank"] <= 5) / max(1, sum(1 for r in suff if r["has_ref"])), 4) if any(r["has_ref"] for r in suff) else None),
         "gate_precision_resolution_bearing@5": round(sum(1 for r in suff if r["res_rank"] and r["res_rank"] <= 5) / len(suff), 4) if suff else None,
         "dual_share_of_top5": round(float(np.mean([sum(1 for s in r["sources"] if s == "dual") / max(1, len(r["sources"])) for r in recs])), 3),
         "latency_ms": {"p50": round(float(np.percentile(lat, 50)), 1), "p95": round(float(np.percentile(lat, 95)), 1)}, "slices": {}}
    for s in ("short", "multi_turn", "first_turn", "customer_seen_in_kb", "multi_intent", "insufficient_context"):
        rs = [r for r in recs if r["slices"][s]]
        if rs:
            m["slices"][s] = {"n": len(rs), "recall@5": rk([r for r in rs if r["has_ref"]], "hit_rank", 5), "resolution_bearing@5": rk(rs, "res_rank", 5), "sufficient_rate": round(sum(r["sufficient"] for r in rs) / len(rs), 3)}
    return m


def tune_weights(kb, dev, judge, base_cfg) -> tuple[RerankWeights, list[dict]]:
    """Coordinate search on DEV maximising same-resolution recall@5 + resolution-bearing@3 (equal weight)."""
    grid = {"w_customer": [0.25, 0.35, 0.45], "w_reply": [0.15, 0.25, 0.35], "w_resolution": [0.1, 0.2, 0.3], "w_outcome": [0.0, 0.01, 0.02]}
    best, log = RerankWeights(), []

    def score(w):
        m, _ = run("tune", Retriever(kb, base_cfg, weights=w, gate_v3=GateV3Config()), kb, dev, judge)
        return (m["recall@5"] or 0) + (m["resolution_bearing@3"] or 0), m

    best_s, best_m = score(best)
    log.append({"weights": asdict(best), "objective": round(best_s, 4), "recall@5": best_m["recall@5"], "resolution_bearing@3": best_m["resolution_bearing@3"]})
    for _ in range(2):
        for k, vals in grid.items():
            for v in vals:
                cand = replace(best, **{k: v})
                if cand == best:
                    continue
                s, m = score(cand)
                log.append({"weights": asdict(cand), "objective": round(s, 4), "recall@5": m["recall@5"], "resolution_bearing@3": m["resolution_bearing@3"]})
                if s > best_s + 1e-9:
                    best, best_s = cand, s
    return best, log


def build_kb() -> KnowledgeBase:
    kb = KnowledgeBase.build(dense_models=[BGE], with_bm25=False)
    for p in ("reply", "pair"):
        kb.add_dense(BGE, p)
    return kb


def dev_step() -> None:
    kb = build_kb()
    dev, golden = dev_queries(500), golden_queries()
    judge = ReplyJudge(kb, golden.brand_reply.tolist() + dev.brand_reply.tolist())
    gate2 = GateConfig.load()
    results = {}
    for n, cfg in VARIANTS.items():
        results[n], _ = run(n, Retriever(kb, cfg, gate=gate2), kb, dev, judge)
        print(f"dev  {n:28s} R@5={results[n]['recall@5']} MRR={results[n]['mrr']} resb@1/3/5={results[n]['resolution_bearing@1']}/{results[n]['resolution_bearing@3']}/{results[n]['resolution_bearing@5']} suff={results[n]['sufficient_rate']}", flush=True)
    best_dual = max(("C_dual_customer_reply_v2", "C2_dual_customer_pair_v2", "B2_pair_v2"), key=lambda n: ((results[n]["recall@5"] or 0) + (results[n]["resolution_bearing@3"] or 0)))
    base = replace(VARIANTS[best_dual], rerank="resolution", gate="v3")
    weights, wlog = tune_weights(kb, dev, judge, base)
    weights = replace(weights, version="rerank-v1")
    weights.save()
    print("frozen weights:", asdict(weights), flush=True)
    dname = "D_" + best_dual.replace("_v2", "") + "_rr_v3"
    loose = CANDIDATE_GATES["share0.5_ms2"]
    results[dname + "__loosest_gate"], _ = run(dname, Retriever(kb, base, weights=weights, gate_v3=loose), kb, dev, judge)
    # hand-check sheet: every DEV case the loosest candidate gate calls sufficient, with each candidate's verdict
    r = Retriever(kb, base, weights=weights, gate_v3=loose)
    sheet, cases = [], []
    for _, q in dev.iterrows():
        ev = r.retrieve(q.customer_message, query_intent=q.intent, customer_author=(q.customer_author or None), query_created_at=q.created_at)
        if not ev.sufficient:
            continue
        verdicts = {k: decide_v3(ev.items, g, q.intent, q.customer_message)["level"] for k, g in CANDIDATE_GATES.items()}
        top = ev.resolution_candidates[0]
        cases.append({"qid": q.qid, "query": q.customer_message, "intent": q.intent, "verdicts": verdicts, "clusters": [(c.action_class, c.support_count, c.share) for c in ev.resolution_candidates], "top_reply": top.representative_reply})
        sheet += [f"### {q.qid}  verdicts={verdicts}  clusters={cases[-1]['clusters']}", f"- query: {q.customer_message}", f"- top resolution ({top.action_class}, support {top.support_count}): {top.representative_reply}",
                  f"- brand's actual reply: {q.brand_reply}", ""]
    header = ["# Gate-v3 hand-check sheet (DEV cases the loosest candidate gate calls sufficient)", "",
              "Label each qid in gate_v3_handcheck.json as RESOLVES (the top resolution plausibly fixes the stated symptom), PARTIAL (right area, incomplete or conditional), "
              "ASK (the 'resolution' only asks for information), WRONG (unrelated, or the message states no issue).", ""]
    SHEET.write_text("\n".join(header + sheet), encoding="utf-8")
    STATE.write_text(json.dumps({"dev": results, "weight_search": wlog, "selected_dual": best_dual, "final_variant": dname, "handcheck_cases": cases}, indent=1, default=str), encoding="utf-8")
    print(f"wrote {SHEET} with {len(cases)} cases; label them into {LABELS} then run --final", flush=True)


def choose_gate(cases: list[dict], labels: dict[str, str]) -> tuple[str, dict]:
    """Per candidate gate: coverage (#sufficient on DEV 500) and hand-checked precision. Choose the largest coverage whose
    hand-checked precision (RESOLVES+PARTIAL) >= 0.9 (safe resolution quality is the primary target, so a WRONG share
    above ~10% is not bought back with coverage); tie -> the stricter candidate. Falls back to the strictest."""
    table = {}
    for k in CANDIDATE_GATES:
        suff = [c for c in cases if c["verdicts"][k] in ("SUFFICIENT", "STRONG")]
        lab = [labels.get(c["qid"], "UNLABELLED") for c in suff]
        n = len(lab)
        table[k] = {"n_sufficient": n, "coverage": round(n / 500, 4), "labels": {x: lab.count(x) for x in ("RESOLVES", "PARTIAL", "ASK", "WRONG", "UNLABELLED")},
                    "precision_resolves": round(lab.count("RESOLVES") / n, 3) if n else None, "precision_resolves_or_partial": round((lab.count("RESOLVES") + lab.count("PARTIAL")) / n, 3) if n else None}
    ok = [k for k, v in table.items() if v["n_sufficient"] and (v["precision_resolves_or_partial"] or 0) >= 0.9]
    chosen = max(ok, key=lambda k: (table[k]["coverage"], list(CANDIDATE_GATES).index(k))) if ok else "share0.7_ms3"
    return chosen, table


def final_step() -> None:
    st = json.loads(STATE.read_text(encoding="utf-8"))
    labels = json.loads(LABELS.read_text(encoding="utf-8")).get("labels", {}) if LABELS.exists() else {}
    chosen, table = choose_gate(st["handcheck_cases"], labels)
    gate3 = CANDIDATE_GATES[chosen]
    gate3.save()
    weights = RerankWeights.load()
    print("chosen gate:", chosen, asdict(gate3), flush=True)
    kb = build_kb()
    golden, dev = golden_queries(), dev_queries(500)
    kb.assert_isolated_from(set(golden.customer_tweet_id.astype(int)), "golden")
    judge = ReplyJudge(kb, golden.brand_reply.tolist() + dev.brand_reply.tolist())
    gate2 = GateConfig.load()
    base = replace(VARIANTS[st["selected_dual"]], rerank="resolution", gate="v3")
    variants = dict(VARIANTS) | {st["final_variant"]: base}
    results = {"dev": st["dev"], "golden": {}}
    results["dev"][st["final_variant"]], _ = run("D", Retriever(kb, base, weights=weights, gate_v3=gate3), kb, dev, judge)
    per_query = {}
    for n, cfg in variants.items():
        results["golden"][n], per_query[n] = run(n, Retriever(kb, cfg, gate=gate2, weights=weights, gate_v3=gate3), kb, golden, judge)
        g = results["golden"][n]
        print(f"gold {n:28s} R@1/3/5={g['recall@1']}/{g['recall@3']}/{g['recall@5']} MRR={g['mrr']} resb@1/3/5={g['resolution_bearing@1']}/{g['resolution_bearing@3']}/{g['resolution_bearing@5']} suff={g['sufficient_rate']} levels={g['levels']} lat={g['latency_ms']}", flush=True)
    (OUT / "retrieval_results.json").write_text(json.dumps({
        "variants": {n: {**asdict(c), "outcome_bonus": asdict(c.outcome_bonus)} for n, c in variants.items()}, "dev": results["dev"], "golden": results["golden"],
        "weights": asdict(weights), "weight_search": st["weight_search"], "gate_v3": asdict(gate3), "gate_candidates": {k: asdict(v) for k, v in CANDIDATE_GATES.items()},
        "gate_handcheck": {"chosen": chosen, "table": table, "n_labelled": len(labels), "annotator": "AI annotator (Claude); not a human study"},
        "selected_dual": st["selected_dual"], "protocol": "Phase-2 resolution-match judge; DEV for weights and gate (hand-checked); GOLDEN once per variant"}, indent=1, default=str), encoding="utf-8")
    for n, recs in per_query.items():
        (OUT / f"per_query_golden__{n}.jsonl").write_text("\n".join(json.dumps(x) for x in recs), encoding="utf-8")
    write_md(results, weights, gate3, chosen, table, st)


def write_md(results, weights, gate3, chosen, table, st) -> None:
    cols = ["recall@1", "recall@3", "recall@5", "mrr", "resolution_bearing@1", "resolution_bearing@3", "resolution_bearing@5", "resolution_mrr", "same_intent@5", "sufficient_rate", "gate_precision_resolution_bearing@5", "gate_precision_same_resolution_hit@5"]
    last = st["final_variant"]
    L = ["# Reply-side, dual and resolution-reranked retrieval (Phase 5-A)", "",
         "Same protocol as Phase 2 (same-resolution TF-IDF judge, 46 golden references; DEV 500 for tuning; GOLDEN once per variant). resolution_bearing@k = a substantive reply whose "
         "non-question sentences state an instruction or released fix (resolution.is_resolution_bearing) in the top-k. gate_precision_same_resolution_hit@5 is the automatic judge's hit rate "
         "among SUFFICIENT cases with a reference; it was 0 for every variant including Phase 2's, as in Phase 2, so the gate is calibrated on hand-checked DEV verdicts (gate_v3_handcheck_sheet.md / gate_v3_handcheck.json).", ""]
    for title, res in (("DEV (tuning)", results["dev"]), ("GOLDEN (once)", results["golden"])):
        L += [f"## {title}", "", "| variant | " + " | ".join(cols) + " | p50 ms |", "|---|" + "---|" * (len(cols) + 1)]
        for n, m in res.items():
            L.append(f"| {n} | " + " | ".join(str(m.get(c)) for c in cols) + f" | {m['latency_ms']['p50']} |")
        L.append("")
    L += [f"Selected dual variant (dev objective R@5 + resolution_bearing@3): `{st['selected_dual']}`", f"Frozen reranker weights (coordinate search on DEV, {len(st['weight_search'])} evaluations): `{asdict(weights)}`",
          f"Frozen gate-v3: `{chosen}` = `{asdict(gate3)}`", "", "## Gate-v3 candidates on DEV (hand-checked by an AI annotator)", "",
          "| candidate | n sufficient | coverage | RESOLVES | PARTIAL | ASK | WRONG | precision (R+P) |", "|---|---|---|---|---|---|---|---|"]
    for k, v in table.items():
        L.append(f"| {k}{' (chosen)' if k == chosen else ''} | {v['n_sufficient']} | {v['coverage']} | {v['labels']['RESOLVES']} | {v['labels']['PARTIAL']} | {v['labels']['ASK']} | {v['labels']['WRONG']} | {v['precision_resolves_or_partial']} |")
    L += ["", "Golden gate levels (final): " + json.dumps(results["golden"][last]["levels"]), "Golden consistency (final): " + json.dumps(results["golden"][last]["consistency"]), "",
          "## Slices (golden, final variant)", "", "| slice | n | recall@5 | resolution_bearing@5 | sufficient |", "|---|---|---|---|---|"]
    for s_, v in results["golden"][last]["slices"].items():
        L.append(f"| {s_} | {v['n']} | {v['recall@5']} | {v['resolution_bearing@5']} | {v['sufficient_rate']} |")
    (OUT / "retrieval_results.md").write_text("\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    final_step() if "--final" in sys.argv else dev_step()
