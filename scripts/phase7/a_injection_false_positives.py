"""Phase 7-A: false-positive rate of the deterministic prompt-injection detector on real historical customer messages
(knowledge-base split + non-golden holdout; the golden set is not used). Writes artifacts/phase7/injection_false_positives.json.
  python scripts/phase7/a_injection_false_positives.py
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pandas as pd

import resolveai  # noqa: F401
from resolveai import config
from resolveai.evaluation import load_golden
from resolveai.trust.injection import detect_injection

OUT = Path("artifacts/phase7")
OUT.mkdir(parents=True, exist_ok=True)


def main() -> None:
    df = pd.read_csv(config.PROCESSED_DIR / "apple_pairs.csv", keep_default_na=False)
    gold = set(load_golden().customer_tweet_id.astype(int))
    df = df[~df.customer_tweet_id.isin(gold)]
    hits = []
    for r in df.itertuples():
        c = detect_injection(r.customer_message + " " + (r.context or ""))
        if c.detected:
            hits.append({"customer_tweet_id": int(r.customer_tweet_id), "patterns": c.patterns, "message": r.customer_message[:200]})
    res = {"n_messages": int(len(df)), "n_flagged": len(hits), "flag_rate": round(len(hits) / len(df), 5), "by_pattern": dict(Counter(p for h in hits for p in h["patterns"])),
           "flagged_examples": hits[:25], "note": "every flag on this historical traffic is a false positive by construction (2017 Twitter support, no AI assistant to attack); golden rows excluded"}
    (OUT / "injection_false_positives.json").write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k != "flagged_examples"}))
    for h in hits[:25]:
        print(" ", h["patterns"], "|", h["message"][:140].replace("\n", " "))


if __name__ == "__main__":
    main()
