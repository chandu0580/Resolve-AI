"""Phase 10-C: final performance and cost profile on DEV messages (never golden).

  python -u scripts/final/c_perf_final.py [--n 100] [--n-live 40] [--n-draft 20]

The same orchestrator the API uses (traces off, so disk writes are not timed). Modes:
  no_model      AgentConfig(use_llm=False): redaction, context, classifier, retrieval, gate, rules, policy, clarify/handoff
  cached_model  the configured model behind the SHA-256 response cache; an unmeasured warm pass fills the cache, the measured pass replays it
  live_random   NO cache, the production request budget (45 s), n_live random fresh DEV messages: the representative traffic mix
  live_draft    NO cache, 45 s budget, DEV messages selected because the no-model pass found SUFFICIENT or STRONG evidence, the only
                messages that can reach drafting. Conditional on the evidence gate and dominated by one issue, so NOT representative; it
                exists to measure draft and verification latency. If no request drafts, the report says so instead of estimating.
Before every measured pass the embedding memo and the query-vector cache are cleared (the Phase 9 profiler artifact).
Per mode: total and per-stage p50 / p95, p99 only when n >= 100 (otherwise the maximum is shown), model calls, live calls, cache hits,
input and output tokens, estimated cost at the list price the orchestrator uses, and how many requests drafted and verified with the model
(a canned template marks verification "ok" with 0 ms, so a model-verified request is one whose verification stage took time).
Writes artifacts/final/performance/perf_final.json and perf_final.md.
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
from resolveai.agent.orchestrator import PRICE_PER_M  # noqa: E402
from resolveai.evaluation import load_golden  # noqa: E402
from resolveai.intelligence.classifier import IntentService  # noqa: E402
from resolveai.intelligence.context import parse_context  # noqa: E402
from resolveai.llm import DiskCache, LLMClient, OpenAICompatibleProvider  # noqa: E402
from resolveai.retrieval import KnowledgeBase, Retriever, RetrieverConfig  # noqa: E402
from resolveai.retrieval.dense import Embedder  # noqa: E402

OUT = ROOT / "artifacts" / "final" / "performance"
STAGES = ("pii_redaction", "context", "intent", "second_opinion", "retrieval", "evidence_gate", "risk", "policy", "draft", "verification", "output_gate", "handoff", "total")
BUDGET_S = 45.0


def dev_pool() -> pd.DataFrame:
    sub = pd.read_csv(config.PROCESSED_DIR / "apple_pairs.csv", keep_default_na=False)
    gold_ids = set(load_golden().customer_tweet_id.astype(str))
    pool = sub[(sub.split == "holdout") & ~sub.customer_tweet_id.astype(str).isin(gold_ids)].reset_index(drop=True)
    assert not set(pool.customer_tweet_id.astype(str)) & gold_ids
    return pool


def pct(values: list[float]) -> dict:
    if not values:
        return {"n": 0}
    a = np.array(values, dtype=float)
    return {"n": len(values), "p50": round(float(np.percentile(a, 50)), 1), "p95": round(float(np.percentile(a, 95)), 1),
            "p99": round(float(np.percentile(a, 99)), 1) if len(values) >= 100 else None, "max": round(float(a.max()), 1), "mean": round(float(a.mean()), 1)}


def run(agent: ResolveAI, rows: pd.DataFrame, budget_s: float | None) -> list[dict]:
    Embedder._memo.clear()
    agent.retriever._qcache.clear()
    out = []
    for r in rows.itertuples():
        t = time.perf_counter()
        res = agent.resolve(r.customer_message, parse_context(r.context), customer_author=r.customer_author, created_at=r.created_at, budget_s=budget_s)
        wall = (time.perf_counter() - t) * 1000
        lat = dict(res.latency)
        out.append({"id": str(r.customer_tweet_id), "action": res.action, "reason": res.decision.escalation.reason_code, "evidence_level": res.evidence.sufficiency_level,
                    "latency": lat, "wall_ms": wall, "llm_calls": res.usage.llm_calls, "live_calls": res.usage.live_calls, "cache_hits": res.usage.cache_hits,
                    "tokens_in": res.usage.tokens_in, "tokens_out": res.usage.tokens_out, "cost_usd": res.usage.estimated_cost_usd, "timeouts": res.usage.timeouts,
                    "retries": res.usage.retries, "budget_exhausted": res.usage.budget_exhausted, "draft_status": res.stage_status.get("draft"),
                    "verification_status": res.stage_status.get("verification"),
                    "model_verified": res.stage_status.get("verification") == "ok" and lat.get("verification", 0) > 0})
    return out


def summarise(recs: list[dict]) -> dict:
    drafted = [r for r in recs if r["draft_status"] == "ok" and r["model_verified"]]
    calls = sum(r["llm_calls"] for r in recs)
    return {"n": len(recs), "total_ms": pct([r["latency"]["total"] for r in recs]),
            "stages_ms": {s: pct([r["latency"][s] for r in recs if s in r["latency"]]) for s in STAGES},
            "llm_calls_per_request": pct([r["llm_calls"] for r in recs]), "mean_llm_calls": round(calls / max(1, len(recs)), 3),
            "live_calls_total": sum(r["live_calls"] for r in recs), "cache_hits_total": sum(r["cache_hits"] for r in recs),
            "cache_hit_rate": round(sum(r["cache_hits"] for r in recs) / calls, 3) if calls else None,
            "tokens_in_per_request": pct([r["tokens_in"] for r in recs]), "tokens_out_per_request": pct([r["tokens_out"] for r in recs]),
            "cost_usd_per_request": {"mean": round(float(np.mean([r["cost_usd"] for r in recs])), 6), "p50": round(float(np.percentile([r["cost_usd"] for r in recs], 50)), 6),
                                     "p95": round(float(np.percentile([r["cost_usd"] for r in recs], 95)), 6)},
            "timeouts": sum(r["timeouts"] for r in recs), "retries": sum(r["retries"] for r in recs), "budget_exhausted": sum(r["budget_exhausted"] for r in recs),
            "actions": dict(Counter(r["action"] for r in recs)), "reasons": dict(Counter(r["reason"] for r in recs)), "evidence_levels": dict(Counter(r["evidence_level"] for r in recs)),
            "model_drafted_and_verified": len(drafted),
            "draft_stage_ms": pct([r["latency"]["draft"] for r in drafted]), "verification_stage_ms": pct([r["latency"]["verification"] for r in drafted]),
            "total_ms_when_drafted": pct([r["latency"]["total"] for r in drafted])}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--n-live", type=int, default=40)
    ap.add_argument("--n-draft", type=int, default=20)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    pool = dev_pool()
    kb = KnowledgeBase.build(dense_models=[RetrieverConfig().model], with_bm25=False)
    retriever, intents = Retriever(kb, RetrieverConfig()), IntentService()
    shuffled = pool.sample(frac=1.0, random_state=config.SEED + 13).reset_index(drop=True)
    rows = shuffled.iloc[: a.n].reset_index(drop=True)
    live_rows = shuffled.iloc[a.n: a.n + a.n_live].reset_index(drop=True)
    candidates = shuffled.iloc[a.n + a.n_live:].reset_index(drop=True)
    report = {"protocol": __doc__.split("Modes:")[1].split("Writes")[0].strip(), "machine_note": "single local CPU process; the model runs behind a remote OpenAI-compatible proxy",
              "price_per_million_tokens_usd": {"input": PRICE_PER_M[0], "output": PRICE_PER_M[1], "note": "GLM-5.2 list price; the proxy's real billing is unknown"},
              "dev_pool_rows": len(pool), "seed": config.SEED + 13}

    nomodel = ResolveAI(kb=kb, retriever=retriever, intents=intents, cfg=AgentConfig(use_llm=False, write_traces=False))
    nomodel.resolve("warm up the embedding model and classifier")
    report["no_model"] = summarise(run(nomodel, rows, None))
    print("no_model", json.dumps(report["no_model"]["total_ms"]), flush=True)

    cached = ResolveAI(kb=kb, retriever=retriever, intents=intents, llm=LLMClient(provider=OpenAICompatibleProvider(), cache=DiskCache()), cfg=AgentConfig(write_traces=False))
    run(cached, rows, None)
    report["cached_model"] = summarise(run(cached, rows, None))
    print("cached_model", json.dumps(report["cached_model"]["total_ms"]), flush=True)

    # draft-path selection: scan the remaining pool with the no-model agent for SUFFICIENT/STRONG evidence
    picked, scanned = [], 0
    for r in candidates.itertuples():
        scanned += 1
        res = nomodel.resolve(r.customer_message, parse_context(r.context), customer_author=r.customer_author, created_at=r.created_at)
        if res.evidence.sufficiency_level in ("SUFFICIENT", "STRONG"):
            picked.append(r.Index)
            if len(picked) >= a.n_draft:
                break
    draft_rows = candidates.loc[picked].reset_index(drop=True)
    report["live_draft_selection"] = {"scanned": scanned, "selected": len(draft_rows), "rule": "no-model evidence level SUFFICIENT or STRONG"}
    print("draft-path rows", report["live_draft_selection"], flush=True)

    live = ResolveAI(kb=kb, retriever=retriever, intents=intents, llm=LLMClient(provider=OpenAICompatibleProvider(), cache=None), cfg=AgentConfig(write_traces=False))
    report["live_random"] = summarise(run(live, live_rows, BUDGET_S))
    print("live_random", json.dumps(report["live_random"]["total_ms"]), flush=True)
    report["live_draft"] = summarise(run(live, draft_rows, BUDGET_S))
    print("live_draft", json.dumps(report["live_draft"]["total_ms"]), "drafted", report["live_draft"]["model_drafted_and_verified"], flush=True)
    report["wall_seconds"] = round(time.perf_counter() - t0, 1)
    (OUT / "perf_final.json").write_text(json.dumps(report, indent=1), encoding="utf-8")

    def cell(d, key="p50"):
        return "—" if not d or not d.get("n") else f"{d[key]}"

    def p99(d):
        return "—" if not d or not d.get("n") else (f"{d['p99']}" if d.get("p99") is not None else f"max {d['max']}")

    L = ["# Final performance and cost profile (DEV messages)", "", report["protocol"], "",
         "| mode | n | total p50 ms | p95 ms | p99 ms (n ≥ 100) | model calls / request (mean) | live calls | cache hit rate | tokens in / out per request (mean) | est. cost / request (mean USD) | drafted + model-verified |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    for mode in ("no_model", "cached_model", "live_random", "live_draft"):
        s = report[mode]
        L.append(f"| {mode} | {s['n']} | {cell(s['total_ms'])} | {cell(s['total_ms'], 'p95')} | {p99(s['total_ms'])} | {s['mean_llm_calls']} | {s['live_calls_total']} | "
                 f"{s['cache_hit_rate']} | {s['tokens_in_per_request'].get('mean')} / {s['tokens_out_per_request'].get('mean')} | {s['cost_usd_per_request']['mean']} | {s['model_drafted_and_verified']} |")
    L += ["", "## Stage latency p50 / p95 ms", "", "| stage | " + " | ".join(("no_model", "cached_model", "live_random", "live_draft")) + " |", "|---|---|---|---|---|"]
    for st in STAGES:
        L.append(f"| {st} | " + " | ".join(f"{cell(report[m]['stages_ms'][st])} / {cell(report[m]['stages_ms'][st], 'p95')}" for m in ("no_model", "cached_model", "live_random", "live_draft")) + " |")
    ld = report["live_draft"]
    L += ["", "## Live drafting and verification", ""]
    if ld["model_drafted_and_verified"]:
        L += [f"Requests that drafted and were verified with the live model: {ld['model_drafted_and_verified']} of {ld['n']} (selection: {report['live_draft_selection']}).",
              f"- draft stage p50 / p95: {ld['draft_stage_ms'].get('p50')} / {ld['draft_stage_ms'].get('p95')} ms",
              f"- verification stage p50 / p95: {ld['verification_stage_ms'].get('p50')} / {ld['verification_stage_ms'].get('p95')} ms",
              f"- total for those requests p50 / p95: {ld['total_ms_when_drafted'].get('p50')} / {ld['total_ms_when_drafted'].get('p95')} ms",
              f"- small sample (n = {ld['model_drafted_and_verified']}): an engineering estimate, not a service level"]
    else:
        L.append("**Live draft/verification latency not measured**: no request in the live samples reached drafting.")
    L += ["", "Outcomes: " + "; ".join(f"{m} {report[m]['actions']}" for m in ("no_model", "cached_model", "live_random", "live_draft")),
          "Timeouts / retries / budget refusals: " + "; ".join(f"{m} {report[m]['timeouts']}/{report[m]['retries']}/{report[m]['budget_exhausted']}" for m in ("no_model", "cached_model", "live_random", "live_draft"))]
    (OUT / "perf_final.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
