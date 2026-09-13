"""Phase 5-B: risk-extraction structured-output hardening, measured before/after on DEV messages (never golden).
  v1  full 14-boolean schema, max_tokens 900   (Phase 4 production)
  v2  compact {flags: [...], actionable, summary}, max_tokens 900
  v2s compact, max_tokens 600  (does the smaller JSON let a smaller cap work?)
Metrics: fallback rate (invalid JSON after the bounded retry), live latency p50/p95, output tokens, flag agreement
between v1 and v2 (Jaccard over raised flags), unknown flag names dropped. The proxy ignores reasoning-off parameters
(tested: `thinking: disabled` and `reasoning_effort` still spend ~500 hidden tokens), so the lever is the output size.
  python scripts/phase5/b_risk_hardening.py [n]
Writes artifacts/resolution/risk_hardening.json
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

import resolveai  # noqa: F401
from resolveai import config
from resolveai.agent import risk
from resolveai.evaluation import load_golden
from resolveai.intelligence.context import build_context, parse_context
from resolveai.llm import DiskCache, LLMClient, OpenAICompatibleProvider

OUT = Path("artifacts/resolution")
OUT.mkdir(parents=True, exist_ok=True)


def dev_messages(n: int) -> pd.DataFrame:
    sub = pd.read_csv(config.PROCESSED_DIR / "apple_pairs.csv", keep_default_na=False)
    gold_ids = set(load_golden().customer_tweet_id.astype(int))
    pool = sub[(sub.split == "holdout") & ~sub.customer_tweet_id.isin(gold_ids)]
    return pool.sample(n=n, random_state=config.SEED + 5).reset_index(drop=True)   # a different seed from the retrieval dev set: fresh, uncached prompts


def run(client: LLMClient, rows: pd.DataFrame, schema: str, max_tokens: int) -> dict:
    recs = []
    for r in rows.itertuples():
        b = build_context(r.customer_message, parse_context(r.context))
        u0 = client.usage.as_dict()
        t = time.perf_counter()
        flags, status = risk.extract(client, b, None, schema=schema, max_tokens=max_tokens)
        ms = (time.perf_counter() - t) * 1000
        u1 = client.usage.as_dict()
        recs.append({"status": status, "ms": ms, "tokens_out": u1["tokens_out"] - u0["tokens_out"], "tokens_in": u1["tokens_in"] - u0["tokens_in"], "calls": u1["calls"] - u0["calls"],
                     "cached": (u1["cache_hits"] - u0["cache_hits"]) > 0, "flags": sorted(k for k, v in flags.model_dump().items() if v is True and k != "is_actionable"), "source": flags.source})
    live = [x for x in recs if not x["cached"]]
    return {"schema": schema, "max_tokens": max_tokens, "n": len(recs), "n_live": len(live), "fallback_rate": round(sum(x["status"] == "fallback" for x in recs) / len(recs), 4),
            "unknown_flags_dropped": sum(x["status"] == "ok_unknown_flags_dropped" for x in recs), "retry_rate": round(sum(x["calls"] > 1 for x in recs) / len(recs), 4),
            "latency_ms": {"p50": round(float(np.percentile([x["ms"] for x in live], 50)), 0) if live else None, "p95": round(float(np.percentile([x["ms"] for x in live], 95)), 0) if live else None},
            "tokens_out_mean": round(float(np.mean([x["tokens_out"] for x in live])), 1) if live else None, "tokens_in_mean": round(float(np.mean([x["tokens_in"] for x in live])), 1) if live else None,
            "flags_raised_mean": round(float(np.mean([len(x["flags"]) for x in recs])), 2), "_recs": recs}


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    rows = dev_messages(n)
    client = LLMClient(provider=OpenAICompatibleProvider(), cache=DiskCache())
    res = {"v1_full_900": run(client, rows, "full", 900), "v2_compact_900": run(client, rows, "compact", 900), "v2_compact_600": run(client, rows, "compact", 600)}
    a, b = res["v1_full_900"]["_recs"], res["v2_compact_900"]["_recs"]
    jac = []
    for x, y in zip(a, b, strict=False):
        if x["status"] == "fallback" or y["status"] == "fallback":
            continue
        sx, sy = set(x["flags"]), set(y["flags"])
        jac.append(1.0 if not (sx | sy) else len(sx & sy) / len(sx | sy))
    agreement = {"n_compared": len(jac), "mean_jaccard_v1_v2": round(float(np.mean(jac)), 3) if jac else None, "exact_match_rate": round(float(np.mean([j == 1.0 for j in jac])), 3) if jac else None,
                 "v1_only_flag_rows": sum(1 for x, y in zip(a, b, strict=False) if set(x["flags"]) - set(y["flags"])), "v2_only_flag_rows": sum(1 for x, y in zip(a, b, strict=False) if set(y["flags"]) - set(x["flags"]))}
    for k in res:
        res[k]["examples"] = [{"status": r["status"], "flags": r["flags"], "tokens_out": r["tokens_out"]} for r in res[k].pop("_recs")[:8]]
    out = {"n": n, "dev_seed": config.SEED + 5, "model": client.model, "results": res, "v1_vs_v2_agreement": agreement,
           "note": "DEV messages disjoint from golden; the golden set is never used for tuning. Rules-only flags are OR-merged in every variant, so the LLM only adds flags."}
    (OUT / "risk_hardening.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "examples"} for k, v in res.items()}, indent=1))
    print("agreement:", agreement)


if __name__ == "__main__":
    main()
