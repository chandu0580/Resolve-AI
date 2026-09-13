"""Phase 9-C: profile the real request path on DEV messages (never golden) and look for duplicate computation.

  python -u scripts/phase9/c_perf_profile.py [--n 60] [--n-live 20]

Modes (the same ResolveAI orchestrator the API uses; traces off so disk writes are not measured):
  no_model      AgentConfig(use_llm=False): redaction, context, classifier, retrieval, gate, rules, policy, clarify/handoff
  cached_model  the configured model behind the SHA-256 response cache; one unmeasured warm pass fills the cache, the
                measured pass is served from it (what a cache-served evaluation run measures)
  live_model    the configured model with NO cache and the API's request budget (45 s), n_live fresh messages
Per mode: p50 / p95 / p99 of every stage and of the total, model calls, embedding computations per request.
Writes artifacts/phase9/performance/perf_report.json and perf_report.md.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from resolveai import config  # noqa: E402
from resolveai.agent import AgentConfig, ResolveAI  # noqa: E402
from resolveai.evaluation import load_golden  # noqa: E402
from resolveai.intelligence.classifier import IntentService  # noqa: E402
from resolveai.intelligence.context import parse_context  # noqa: E402
from resolveai.llm import DiskCache, LLMClient, OpenAICompatibleProvider  # noqa: E402
from resolveai.retrieval import KnowledgeBase, Retriever, RetrieverConfig  # noqa: E402
from resolveai.retrieval.dense import Embedder  # noqa: E402

OUT = ROOT / "artifacts" / "phase9" / "performance"
STAGES = ("pii_redaction", "context", "intent", "second_opinion", "retrieval", "evidence_gate", "risk", "policy", "draft", "verification", "output_gate", "handoff", "total")


def dev_rows(n: int, seed: int) -> pd.DataFrame:
    sub = pd.read_csv(config.PROCESSED_DIR / "apple_pairs.csv", keep_default_na=False)
    gold_ids = set(load_golden().customer_tweet_id.astype(str))
    pool = sub[(sub.split == "holdout") & ~sub.customer_tweet_id.astype(str).isin(gold_ids)]
    return pool.sample(n=n, random_state=seed).reset_index(drop=True)


def pct(values: list[float]) -> dict:
    if not values:
        return {"n": 0}
    a = np.array(values, dtype=float)
    return {"n": len(values), "p50": round(float(np.percentile(a, 50)), 1), "p95": round(float(np.percentile(a, 95)), 1), "p99": round(float(np.percentile(a, 99)), 1),
            "mean": round(float(a.mean()), 1)}


def run(agent: ResolveAI, rows: pd.DataFrame, budget_s: float | None) -> list[dict]:
    # The embedder memoises vectors by text and the retriever caches query vectors: without clearing them, a pass over rows seen before
    # would skip embedding and look faster than it is (found in the first profile: cached mode measured below no-model mode).
    Embedder._memo.clear()
    agent.retriever._qcache.clear()
    out = []
    calls = {"encode_one": 0, "computed": 0}
    original = agent.embedder.encode_one

    def counting(text):
        calls["encode_one"] += 1
        before = len(Embedder._memo)
        v = original(text)
        calls["computed"] += len(Embedder._memo) - before
        return v

    agent.embedder.encode_one = counting
    agent.retriever.embedder.encode_one = counting
    try:
        for r in rows.itertuples():
            c0 = dict(calls)
            t = time.perf_counter()
            res = agent.resolve(r.customer_message, parse_context(r.context), customer_author=r.customer_author, created_at=r.created_at, budget_s=budget_s)
            wall = (time.perf_counter() - t) * 1000
            out.append({"action": res.action, "reason": res.decision.escalation.reason_code, "latency": dict(res.latency), "wall_ms": wall, "llm_calls": res.usage.llm_calls,
                        "live_calls": res.usage.live_calls, "cache_hits": res.usage.cache_hits, "timeouts": res.usage.timeouts, "retries": res.usage.retries,
                        "budget_exhausted": res.usage.budget_exhausted, "risk_status": res.stage_status.get("risk"), "strategy_draft": res.stage_status.get("draft"),
                        "embed_calls": calls["encode_one"] - c0["encode_one"], "embed_computed": calls["computed"] - c0["computed"]})
    finally:
        agent.embedder.encode_one = original
        agent.retriever.embedder.encode_one = original
    return out


def summarise(recs: list[dict]) -> dict:
    return {"n": len(recs), "stages_ms": {s: pct([r["latency"][s] for r in recs if s in r["latency"]]) for s in STAGES}, "wall_ms": pct([r["wall_ms"] for r in recs]),
            "llm_calls_per_request": pct([r["llm_calls"] for r in recs]), "live_calls_per_request": pct([r["live_calls"] for r in recs]),
            "embedding_computations_per_request": pct([r["embed_computed"] for r in recs]), "embedding_lookups_per_request": pct([r["embed_calls"] for r in recs]),
            "timeouts": sum(r["timeouts"] for r in recs), "retries": sum(r["retries"] for r in recs), "budget_exhausted": sum(r["budget_exhausted"] for r in recs),
            "actions": dict(Counter(r["action"] for r in recs)), "reasons": dict(Counter(r["reason"] for r in recs)), "risk_status": dict(Counter(r["risk_status"] for r in recs))}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=60)
    ap.add_argument("--n-live", type=int, default=20)
    ap.add_argument("--keep-live", action="store_true", help="re-measure no_model and cached_model only; keep the live_model section of the existing report "
                                                              "(valid when that run used fresh messages, whose embeddings were computed)")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    kb = KnowledgeBase.build(dense_models=[RetrieverConfig().model], with_bm25=False)
    retriever, intents = Retriever(kb, RetrieverConfig()), IntentService()
    rows = dev_rows(a.n, config.SEED + 9)           # the experiment's dev sample: model responses for these are already cached
    live_rows = dev_rows(a.n + a.n_live, config.SEED + 11).iloc[a.n:].reset_index(drop=True)   # a different sample: fresh prompts
    report = {"protocol": __doc__.split("Modes")[1].split("Writes")[0].strip(), "machine_note": "single local CPU process; the model runs behind a remote OpenAI-compatible proxy"}

    nomodel = ResolveAI(kb=kb, retriever=retriever, intents=intents, cfg=AgentConfig(use_llm=False, write_traces=False))
    nomodel.resolve("warm up the embedding model and classifier")
    report["no_model"] = summarise(run(nomodel, rows, None))
    print("no_model", json.dumps(report["no_model"]["stages_ms"]["total"]), flush=True)

    cached_llm = LLMClient(provider=OpenAICompatibleProvider(), cache=DiskCache())
    cached = ResolveAI(kb=kb, retriever=retriever, intents=intents, llm=cached_llm, cfg=AgentConfig(write_traces=False))
    run(cached, rows, None)   # warm pass: fills the cache for any prompt not seen before
    report["cached_model"] = summarise(run(cached, rows, None))
    print("cached_model", json.dumps(report["cached_model"]["stages_ms"]["total"]), flush=True)

    previous = OUT / "perf_report.json"
    if a.keep_live and previous.exists():
        report["live_model"] = json.loads(previous.read_text(encoding="utf-8"))["live_model"]
        report["live_model_note"] = ("kept from the previous run of this script: fresh messages whose embeddings were computed, 45 s budget; "
                                     "only no_model and cached_model were re-measured after the embedding-memo fix")
    else:
        live_llm = LLMClient(provider=OpenAICompatibleProvider(), cache=None)
        live = ResolveAI(kb=kb, retriever=retriever, intents=intents, llm=live_llm, cfg=AgentConfig(write_traces=False))
        report["live_model"] = summarise(run(live, live_rows, 45.0))
    print("live_model", json.dumps(report["live_model"]["stages_ms"]["total"]), flush=True)

    (OUT / "perf_report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    L = ["# Phase 9 performance profile (DEV messages)", "", report["protocol"], ""]
    for mode in ("no_model", "cached_model", "live_model"):
        s = report[mode]
        L += [f"## {mode} (n={s['n']})", "", "| stage | p50 ms | p95 ms | p99 ms |", "|---|---|---|---|"]
        for st, v in s["stages_ms"].items():
            if v.get("n"):
                L.append(f"| {st} | {v['p50']} | {v['p95']} | {v['p99']} |")
        L += ["", f"Model calls per request p50/p95: {s['llm_calls_per_request'].get('p50')}/{s['llm_calls_per_request'].get('p95')}; live calls p50/p95: "
              f"{s['live_calls_per_request'].get('p50')}/{s['live_calls_per_request'].get('p95')}; embedding computations per request p50/p95: "
              f"{s['embedding_computations_per_request'].get('p50')}/{s['embedding_computations_per_request'].get('p95')}; timeouts {s['timeouts']}, retries {s['retries']}, "
              f"budget refusals {s['budget_exhausted']}; risk stage {s['risk_status']}; actions {s['actions']}", ""]
    (OUT / "perf_report.md").write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
