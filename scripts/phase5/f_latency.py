"""Phase 5-F: risk-call short-circuit before/after on DEV messages (never golden), full agent, live LLM.
Measures LLM calls, live calls, tokens, estimated cost, latency, and checks that the final action and reason code are
IDENTICAL with and without the short-circuit (the skip is only taken when the rules-only policy already guarantees a
non-clarifiable handoff, and the LLM can only add flags).
  python scripts/phase5/f_latency.py [n]
Writes artifacts/resolution/short_circuit.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import resolveai  # noqa: F401
from resolveai import config
from resolveai.agent import AgentConfig, ResolveAI
from resolveai.evaluation import load_golden
from resolveai.intelligence.context import parse_context
from resolveai.observability import TraceStore

OUT = Path("artifacts/resolution")
OUT.mkdir(parents=True, exist_ok=True)


def dev_messages(n: int) -> pd.DataFrame:
    sub = pd.read_csv(config.PROCESSED_DIR / "apple_pairs.csv", keep_default_na=False)
    gold_ids = set(load_golden().customer_tweet_id.astype(int))
    pool = sub[(sub.split == "holdout") & ~sub.customer_tweet_id.isin(gold_ids)]
    return pool.sample(n=n, random_state=config.SEED + 9).reset_index(drop=True)


def run(rows: pd.DataFrame, short_circuit: bool, store: TraceStore) -> list[dict]:
    agent = ResolveAI(cfg=AgentConfig(risk_short_circuit=short_circuit), trace_store=store)
    out = []
    for r in rows.itertuples():
        res = agent.resolve(r.customer_message, parse_context(r.context), customer_author=(r.customer_author or None), created_at=r.created_at, message_id=f"sc{int(short_circuit)}_{r.customer_tweet_id}")
        t = store.read(res.trace_id)
        risk_ev = next((e for e in t.events if e.name.value == "risk_flags_extracted"), None) if t else None
        out.append({"id": int(r.customer_tweet_id), "action": res.action, "reason": res.decision.escalation.reason_code, "rule": res.decision.escalation.rule, "risk_status": (risk_ev.status if risk_ev else None),
                    "risk_source": res.risk.source, "llm_calls": res.usage.llm_calls, "live_calls": res.usage.live_calls, "tokens_in": res.usage.tokens_in, "tokens_out": res.usage.tokens_out,
                    "cost": res.usage.estimated_cost_usd, "total_ms": res.latency["total"], "risk_ms": res.latency.get("risk", 0)})
    return out


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    rows = dev_messages(n)
    store = TraceStore(OUT / "traces_dev")
    off = run(rows, False, store)   # first: every risk call live (uncached), so the 'after' run's savings are not cache artefacts
    on = run(rows, True, store)
    def agg(xs):
        return {"llm_calls_per_msg": round(float(np.mean([x["llm_calls"] for x in xs])), 3), "live_calls_per_msg": round(float(np.mean([x["live_calls"] for x in xs])), 3),
                "tokens_in_per_msg": round(float(np.mean([x["tokens_in"] for x in xs])), 1), "tokens_out_per_msg": round(float(np.mean([x["tokens_out"] for x in xs])), 1),
                "cost_usd_per_msg": round(float(np.mean([x["cost"] for x in xs])), 6), "total_ms_p50": round(float(np.percentile([x["total_ms"] for x in xs], 50))), "total_ms_p95": round(float(np.percentile([x["total_ms"] for x in xs], 95))),
                "risk_ms_p50": round(float(np.percentile([x["risk_ms"] for x in xs], 50))), "risk_status": dict(pd.Series([x["risk_status"] for x in xs]).value_counts()), "actions": dict(pd.Series([x["action"] for x in xs]).value_counts())}
    same_action = sum(1 for a, b in zip(off, on, strict=False) if a["action"] == b["action"])
    same_reason = sum(1 for a, b in zip(off, on, strict=False) if a["reason"] == b["reason"])
    skipped = [b for b in on if b["risk_status"] == "policy_hard_handoff"]
    res = {"n": n, "dev_seed": config.SEED + 9, "before_short_circuit": agg(off), "after_short_circuit": agg(on), "risk_calls_skipped": len(skipped), "skipped_share": round(len(skipped) / n, 3),
           "behaviour": {"same_action": same_action, "same_reason_code": same_reason, "differences": [{"id": a["id"], "before": (a["action"], a["reason"]), "after": (b["action"], b["reason"])} for a, b in zip(off, on, strict=False) if (a["action"], a["reason"]) != (b["action"], b["reason"])]},
           "note": "The 'after' run re-uses cached second-opinion/draft calls where prompts are identical; risk calls that still happen are cache hits of the 'before' run, so latency savings are conservative: compare llm_calls and risk_status, and the 'before' live latency."}
    (OUT / "short_circuit.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    print(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main()
