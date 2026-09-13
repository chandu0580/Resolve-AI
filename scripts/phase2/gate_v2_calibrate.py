"""Gate v2 calibration against HAND-CHECKED development verdicts.

Why: the automatic same-resolution judge cannot score most 'sufficient' verdicts (the query's own reply was a DM
handoff) and is too strict on the rest, so tuning against it drives precision to 0 for every grid point. Instead, the
25 first DEV 'sufficient' verdicts under the loosest v2 thresholds were hand-checked (annotator: Claude, an AI, not a
human; recorded in DEV_HAND_CHECK). Because stricter thresholds select a subset of the loose verdicts, the same labels
score every grid point. Rule: pick the LARGEST-coverage grid point whose hand-checked precision is >= 0.75 with at least
5 labelled verdicts; otherwise the strictest point. Golden is then evaluated once.
  python scripts/phase2/gate_v2_calibrate.py
"""
from __future__ import annotations

import itertools
import json
import sys
from dataclasses import asdict, replace
from pathlib import Path

import resolveai  # noqa: F401
from resolveai.retrieval import GateConfig, KnowledgeBase, OutcomeBonus, Retriever, RetrieverConfig
from resolveai.retrieval.dense import SUPPORTED
from resolveai.retrieval.gate import decide

sys.path.insert(0, str(Path(__file__).parent))
from run_retrieval_benchmark import OUT, ReplyJudge, dev_queries, evaluate, golden_queries  # noqa: E402

FINAL = RetrieverConfig(method="dense", model=SUPPORTED["bge-small"], outcome_bonus=OutcomeBonus(enabled=False), substantive_first=True)

# qid -> usable ("yes": evidence would ground a correct public reply; "weak": partially; "no": wrong/irrelevant/clarify-only)
DEV_HAND_CHECK = {
    "dev546657": "no", "dev489712": "weak", "dev2918861": "no", "dev493554": "no", "dev496796": "yes", "dev2894778": "no",
    "dev2911758": "weak", "dev2924678": "weak", "dev515893": "no", "dev564022": "no", "dev484484": "weak", "dev2889457": "no",
    "dev2958732": "no", "dev2888391": "no", "dev595817": "yes", "dev2965395": "no", "dev545250": "no", "dev559084": "weak",
    "dev491477": "yes", "dev2906753": "yes", "dev542376": "weak", "dev595768": "no", "dev483239": "no", "dev556128": "no", "dev583689": "yes",
}
USABLE = {"yes", "weak"}


def main() -> None:
    kb = KnowledgeBase.build(dense_models=[SUPPORTED["bge-small"]], with_bm25=False)
    golden, dev = golden_queries(), dev_queries(500)
    kb.assert_isolated_from(set(golden.customer_tweet_id.astype(int)), "golden")
    judge = ReplyJudge(kb, golden.brand_reply.tolist() + dev.brand_reply.tolist())
    r = Retriever(kb, FINAL, gate=GateConfig())
    items = {q.qid: (r.retrieve(q.customer_message, query_intent=q.intent, customer_author=q.customer_author or None, query_created_at=q.created_at).items, q.customer_message)
             for _, q in dev.iterrows()}
    grid = list(itertools.product([0.55, 0.65, 0.75, 0.85], [1, 2, 3], [0.4, 0.6]))
    rows = []
    for supp, ms, agree in grid:
        cfg = replace(GateConfig(), relevance_floor=0.35, support_similarity=supp, min_support=ms, min_intent_agreement=agree)
        suff = {qid for qid, (it, qt) in items.items() if decide(it, cfg, None, qt)[0]}
        labelled = [DEV_HAND_CHECK[q] for q in suff if q in DEV_HAND_CHECK]
        prec = sum(1 for v in labelled if v in USABLE) / len(labelled) if labelled else None
        strict = sum(1 for v in labelled if v == "yes") / len(labelled) if labelled else None
        rows.append(dict(support_similarity=supp, min_support=ms, min_intent_agreement=agree, coverage=round(len(suff) / len(items), 4),
                         n_labelled=len(labelled), hand_precision=None if prec is None else round(prec, 3), hand_precision_strict=None if strict is None else round(strict, 3)))
    feasible = [x for x in rows if x["hand_precision"] is not None and x["hand_precision"] >= 0.75 and x["n_labelled"] >= 5]
    best = max(feasible, key=lambda x: (x["coverage"], x["hand_precision"])) if feasible else max(rows, key=lambda x: (x["support_similarity"], x["min_support"]))
    gate = replace(GateConfig(), relevance_floor=0.35, support_similarity=best["support_similarity"], min_support=best["min_support"], min_intent_agreement=best["min_intent_agreement"])
    gate.save()
    print("feasible:", len(feasible), "| chosen:", best)
    for x in sorted(rows, key=lambda x: -x["coverage"])[:12]:
        print("  ", x)

    rf = Retriever(kb, FINAL, gate=gate)
    dev_summary, _ = evaluate(rf, kb, dev, judge, with_intent=True, gate=gate)
    gold_summary, gold_recs = evaluate(rf, kb, golden, judge, with_intent=True, gate=gate)
    print("\nFROZEN gate-v2:", asdict(gate))
    print("DEV   sufficient_rate", dev_summary["sufficient_rate"], dev_summary["gate_reasons"])
    print("GOLD  sufficient_rate", gold_summary["sufficient_rate"], gold_summary["gate_reasons"])
    print("GOLD  R@1/3/5", gold_summary["recall@1"], gold_summary["recall@3"], gold_summary["recall@5"], "MRR", gold_summary["mrr"], "lat", gold_summary["latency_ms"])
    print("GOLD  slices:", {k: (v["recall@5"], v["sufficient_rate"]) for k, v in gold_summary["slices"].items()})
    (OUT / "gate_v2.json").write_text(json.dumps({"config": asdict(FINAL) | {"outcome_bonus": asdict(FINAL.outcome_bonus)}, "gate": asdict(gate),
                                                  "calibration": {"method": "hand-checked DEV verdicts (AI annotator), largest coverage with precision>=0.75, n>=5", "grid": rows, "chosen": best,
                                                                  "hand_check": DEV_HAND_CHECK},
                                                  "dev": dev_summary, "golden": gold_summary, "golden_per_query": gold_recs}, indent=1, default=str), encoding="utf-8")
    (OUT / "per_query_golden__final.jsonl").write_text("\n".join(json.dumps(x) for x in gold_recs), encoding="utf-8")


if __name__ == "__main__":
    main()
