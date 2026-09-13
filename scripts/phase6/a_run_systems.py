"""Phase 6-A: run every evaluated system on the frozen golden set and write one records file per system.
  python scripts/phase6/a_run_systems.py [system ...]      # default: baselines + resolveai_full; ablations by name
Systems: B0_trivial B0_trivial_always_handoff B1_simple_ml B2_direct_llm resolveai_full minus_second_opinion
         minus_resolution_rerank minus_risk_llm minus_retrieval
Golden hash is asserted on load (load_golden). LLM calls go through the SHA-256 disk cache; nothing is tuned here.
Writes artifacts/evaluation/runs/<system>.jsonl and artifacts/evaluation/runs/<system>.meta.json
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pandas as pd

import resolveai  # noqa: F401
from resolveai.evaluation import load_golden
from resolveai.evaluation.baselines import DirectLLMBaseline, SimpleMLBaseline, TrivialBaseline, describe, load_silver
from resolveai.evaluation.records import write_records
from resolveai.evaluation.systems import ABLATIONS, build_agent, run_agent
from resolveai.llm import DiskCache, LLMClient, OpenAICompatibleProvider
from resolveai.retrieval import KnowledgeBase, RetrieverConfig
from resolveai.retrieval.dense import SUPPORTED

OUT = Path("artifacts/evaluation/runs")
OUT.mkdir(parents=True, exist_ok=True)
DEFAULT = ["B0_trivial", "B0_trivial_always_handoff", "B1_simple_ml", "B2_direct_llm", "resolveai_full"]


def main() -> None:
    names = sys.argv[1:] or DEFAULT
    gold = load_golden()
    authors = pd.read_csv("data/golden/golden_customer_authors.csv", dtype=str).set_index("gid").customer_author.to_dict()
    kb = None
    llm = None
    for name in names:
        t0 = time.perf_counter()
        meta = {"system": name, "description": describe().get(name, ABLATIONS[name].description if name in ABLATIONS else "")}
        if name.startswith("B0_trivial"):
            train, _ = load_silver()
            b = TrivialBaseline.fit(train[train.silver_band.isin(["HIGH", "MEDIUM"])].silver_intent.tolist(), "always_handoff" if name.endswith("handoff") else "never_escalate")
            recs = b.run(gold)
            meta["majority_intent"] = b.majority_intent
        elif name == "B1_simple_ml":
            kb = kb or KnowledgeBase.build(dense_models=[SUPPORTED["bge-small"]], with_bm25=False)
            train, dev = load_silver()
            b = SimpleMLBaseline(kb).fit(train, dev)
            recs = b.run(gold, authors)
            meta["classifier"] = b.meta
        elif name == "B2_direct_llm":
            llm = llm or LLMClient(provider=OpenAICompatibleProvider(), cache=DiskCache())
            recs = DirectLLMBaseline(llm).run(gold)
            meta["model"] = llm.model
        elif name in ABLATIONS:
            kb = kb or KnowledgeBase.build(dense_models=[RetrieverConfig().model], with_bm25=False)
            llm = llm or LLMClient(provider=OpenAICompatibleProvider(), cache=DiskCache())
            agent = build_agent(ABLATIONS[name], kb, llm=llm)
            recs = run_agent(agent, gold, authors, name, progress=lambda k, _n=name: print(f"  {_n}: {k}/{len(gold)}", flush=True))
            meta["config"] = ABLATIONS[name].cfg.__dict__ | {"retriever": agent.retriever.cfg.name if hasattr(agent.retriever, "cfg") else "none", "second_opinion_policy": agent.policy}
        else:
            raise SystemExit(f"unknown system {name}")
        write_records(OUT / f"{name}.jsonl", recs)
        meta |= {"n": len(recs), "failed": sum(1 for r in recs if r.failed), "wall_seconds": round(time.perf_counter() - t0, 1), "golden_sha256": json.loads(Path("data/golden/golden_freeze_manifest.json").read_text())["sha256"]}
        (OUT / f"{name}.meta.json").write_text(json.dumps(meta, indent=1, default=str), encoding="utf-8")
        print(f"{name}: n={len(recs)} failed={meta['failed']} wall={meta['wall_seconds']}s", flush=True)


if __name__ == "__main__":
    main()
