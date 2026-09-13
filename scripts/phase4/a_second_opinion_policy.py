"""Phase 4-A: choose the second-opinion ADOPTION policy on development data, then freeze it.
Dev = 30 hand-labelled smoke rows (human-quality labels, primary) + 120 silver-v2 HIGH-band dev rows where the classifier is
LOW/MEDIUM (noisy, tie-breaker). Selection rule fixed before running: highest accuracy on the 30 smoke rows, tie broken by
the silver rows. Golden is not used.  python scripts/phase4/a_second_opinion_policy.py
Writes resolveai/agent/second_opinion_policy.json and artifacts/agent/second_opinion_policy.json.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

import resolveai  # noqa: F401
from resolveai import config
from resolveai.agent import second_opinion as so
from resolveai.intelligence.classifier import IntentService
from resolveai.intelligence.context import build_context, parse_context
from resolveai.llm import LLMClient, OpenAICompatibleProvider

OUT = Path("artifacts/agent")
OUT.mkdir(parents=True, exist_ok=True)


def rows_smoke():
    return [dict(id=r["id"], message=r["customer_message"], context=r.get("context", ""), label=r["intent"]) for r in map(json.loads, Path("data/dev/smoke_dev.jsonl").read_text(encoding="utf-8").splitlines())]


def rows_silver(svc: IntentService, n: int = 120):
    d = pd.read_csv(config.PROCESSED_DIR / "silver_dev.csv", keep_default_na=False)
    d = d[d.silver_band == "HIGH"].sample(frac=1, random_state=config.SEED)
    out = []
    for r in d.itertuples():
        b = build_context(r.customer_message, parse_context(r.context))
        if svc.classify(b).confidence_band in ("LOW", "MEDIUM"):
            out.append(dict(id=f"dev{r.customer_tweet_id}", message=r.customer_message, context=r.context, label=r.silver_intent))
        if len(out) >= n:
            break
    return out


def main() -> None:
    svc, client = IntentService(), LLMClient(provider=OpenAICompatibleProvider())
    sets = {"smoke_human_30": rows_smoke(), "silver_high_dev": rows_silver(svc)}
    results = {p: {} for p in so.POLICIES}
    for name, rows in sets.items():
        recs = []
        for r in rows:
            b = build_context(r["message"], parse_context(r["context"]))
            base = svc.classify(b)
            op = so.consult(client, b) if base.confidence_band != "HIGH" else None
            recs.append((base, op, r["label"]))
        for p in so.POLICIES:
            fin = [so.adopt(p, base, op)[0] for base, op, _ in recs]
            results[p][name] = {"n": len(recs), "accuracy": round(sum(f == lab for f, (_, _, lab) in zip(fin, recs, strict=False)) / len(recs), 4),
                                "classifier_only": round(sum(base.intent == lab for base, _, lab in recs) / len(recs), 4)}
    best = max(so.POLICIES, key=lambda p: (results[p]["smoke_human_30"]["accuracy"], results[p]["silver_high_dev"]["accuracy"]))
    frozen = {"policy": best, "selected_on": "smoke_human_30 accuracy, tie-break silver_high_dev", "results": results, "consult_when": "confidence_band in (LOW, MEDIUM)"}
    Path("resolveai/agent/second_opinion_policy.json").write_text(json.dumps({"policy": best, "version": "so-policy-v1"}, indent=2), encoding="utf-8")
    (OUT / "second_opinion_policy.json").write_text(json.dumps(frozen, indent=2), encoding="utf-8")
    print(json.dumps(frozen, indent=1))
    print("usage:", client.usage.as_dict())


if __name__ == "__main__":
    main()
