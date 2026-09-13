"""Evaluate additional configurations with the FROZEN gate and the same protocol, without re-tuning anything.
Each new configuration is evaluated once on DEV and once on GOLDEN and appended to results.json.
  python scripts/phase2/extra_configs.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import resolveai  # noqa: F401
from resolveai.retrieval import GateConfig, KnowledgeBase, OutcomeBonus, Retriever, RetrieverConfig
from resolveai.retrieval.dense import SUPPORTED

sys.path.insert(0, str(Path(__file__).parent))
from run_retrieval_benchmark import OUT, ReplyJudge, cached_evaluate, dev_queries, golden_queries  # noqa: E402

MINILM, BGE = SUPPORTED["minilm"], SUPPORTED["bge-small"]
EXTRA = {
    "dense:bge-small+subst": RetrieverConfig(method="dense", model=BGE, outcome_bonus=OutcomeBonus(enabled=False), substantive_first=True),
    "dense:minilm+subst": RetrieverConfig(method="dense", model=MINILM, outcome_bonus=OutcomeBonus(enabled=False), substantive_first=True),
}


def main() -> None:
    kb = KnowledgeBase.build(dense_models=[MINILM, BGE])
    golden, dev = golden_queries(), dev_queries(500)
    kb.assert_isolated_from(set(golden.customer_tweet_id.astype(int)), "golden")
    judge = ReplyJudge(kb, golden.brand_reply.tolist() + dev.brand_reply.tolist())
    gate = GateConfig.load()
    res = json.loads((OUT / "results.json").read_text(encoding="utf-8"))
    man = json.loads((OUT / "experiment_manifest.json").read_text(encoding="utf-8"))
    for n, cfg in EXTRA.items():
        r = Retriever(kb, cfg, gate=GateConfig())
        res["dev"][n], _ = cached_evaluate("dev", r, kb, dev, judge, with_intent=True, gate=GateConfig())
        r = Retriever(kb, cfg, gate=gate)
        res["golden"][n], recs = cached_evaluate("golden", r, kb, golden, judge, with_intent=True, gate=gate)
        (OUT / f"per_query_golden__{n.replace(':', '_')}.jsonl").write_text("\n".join(json.dumps(x) for x in recs), encoding="utf-8")
        man["configs"][n] = {**{k: v for k, v in cfg.__dict__.items() if k != "outcome_bonus"}, "outcome_bonus": cfg.outcome_bonus.__dict__}
        print(f"dev  {n:28s} R@5={res['dev'][n]['recall@5']} MRR={res['dev'][n]['mrr']} | gold R@1={res['golden'][n]['recall@1']} R@5={res['golden'][n]['recall@5']} MRR={res['golden'][n]['mrr']} suff={res['golden'][n]['sufficient_rate']} lat={res['golden'][n]['latency_ms']}")
    (OUT / "results.json").write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")
    man.setdefault("extra_configs_evaluated_once", list(EXTRA))
    (OUT / "experiment_manifest.json").write_text(json.dumps(man, indent=2, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
