"""Gate v2: re-tune thresholds on DEV only for the final retrieval configuration, freeze, evaluate GOLDEN once, and print
DEV 'sufficient' verdicts for a hand-check (so the check is done on development data, not on the golden set).
  python scripts/phase2/gate_v2.py
Writes artifacts/retrieval/gate_v2.json (tuning + golden summary + per-query) and resolveai/retrieval/gate_config.json.
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

import resolveai  # noqa: F401
from resolveai.retrieval import GateConfig, KnowledgeBase, OutcomeBonus, Retriever, RetrieverConfig
from resolveai.retrieval.dense import SUPPORTED

sys.path.insert(0, str(Path(__file__).parent))
from run_retrieval_benchmark import OUT, ReplyJudge, dev_queries, evaluate, golden_queries, tune_gate  # noqa: E402

FINAL = RetrieverConfig(method="dense", model=SUPPORTED["bge-small"], outcome_bonus=OutcomeBonus(enabled=False), substantive_first=True)


def main() -> None:
    kb = KnowledgeBase.build(dense_models=[SUPPORTED["bge-small"]], with_bm25=False)
    golden, dev = golden_queries(), dev_queries(500)
    kb.assert_isolated_from(set(golden.customer_tweet_id.astype(int)), "golden")
    judge = ReplyJudge(kb, golden.brand_reply.tolist() + dev.brand_reply.tolist())

    gate, tuning = tune_gate(Retriever(kb, FINAL, gate=GateConfig()), kb, dev, judge)
    gate.save()
    print("gate-v2 frozen:", asdict(gate), "| tuning:", tuning["chosen"], "| feasible:", tuning["feasible"])

    r = Retriever(kb, FINAL, gate=gate)
    dev_summary, dev_recs = evaluate(r, kb, dev, judge, with_intent=True, gate=gate)
    gold_summary, gold_recs = evaluate(r, kb, golden, judge, with_intent=True, gate=gate)
    print("DEV   sufficient_rate", dev_summary["sufficient_rate"], "reasons", dev_summary["gate_reasons"], "precision(auto judge)", dev_summary["gate_precision_hit@5_given_sufficient"])
    print("GOLD  sufficient_rate", gold_summary["sufficient_rate"], "reasons", gold_summary["gate_reasons"], "precision(auto judge)", gold_summary["gate_precision_hit@5_given_sufficient"])
    print("GOLD  R@1/3/5", gold_summary["recall@1"], gold_summary["recall@3"], gold_summary["recall@5"], "MRR", gold_summary["mrr"], "latency", gold_summary["latency_ms"])
    print("GOLD  slices sufficient:", {k: v["sufficient_rate"] for k, v in gold_summary["slices"].items()})
    (OUT / "gate_v2.json").write_text(json.dumps({"config": asdict(FINAL) | {"outcome_bonus": asdict(FINAL.outcome_bonus)}, "gate": asdict(gate), "tuning": tuning,
                                                  "dev": dev_summary, "golden": gold_summary, "golden_per_query": gold_recs}, indent=1, default=str), encoding="utf-8")
    # hand-check material: DEV sufficient verdicts (development data), with evidence
    kbrows = kb.rows.set_index("brand_tweet_id")
    devi = dev.set_index("qid")
    suff = [x for x in dev_recs if x["sufficient"]]
    print(f"\n=== DEV sufficient verdicts for hand-check: {len(suff)} (showing up to 25)")
    for x in suff[:25]:
        q = devi.loc[x["qid"]]
        print(f"\n### {x['qid']} weak_intent={q.intent} ctx_turns={q.n_context_turns}\n  Q: {q.customer_message[:160]}\n  own reply: {q.brand_reply[:110]}")
        for eid, cos, act in list(zip(x["top_ids"], x["top_cos"], x["top_actions"], strict=False))[:3]:
            print(f"    [{cos:.2f} {act:9s}] {kbrows.loc[int(eid)].brand_reply[:140]}")


if __name__ == "__main__":
    main()
