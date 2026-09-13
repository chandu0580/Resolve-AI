"""Phase 3-A: build silver intent labels for TRAIN (kb split) and DEV (holdout, non-golden), and draw a hand-check sample.
  python scripts/phase3/a_silver_labels.py
Writes data/processed/silver_train.csv, silver_dev.csv, artifacts/intelligence/silver_stats.json, silver_noise_sample.csv
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

import resolveai  # noqa: F401
from resolveai import config
from resolveai.evaluation import load_golden
from resolveai.intelligence.silver import SILVER_VERSION, SilverLabeler

OUT = Path("artifacts/intelligence")
OUT.mkdir(parents=True, exist_ok=True)
DEV_N = 800


def main() -> None:
    sub = pd.read_csv(config.PROCESSED_DIR / "apple_pairs.csv", keep_default_na=False)
    gold_ids = set(load_golden().customer_tweet_id.astype(int))
    train = sub[sub.split == "kb"].copy()
    dev = sub[(sub.split == "holdout") & ~sub.customer_tweet_id.isin(gold_ids)].sample(n=DEV_N, random_state=config.SEED).copy()
    assert not set(dev.customer_tweet_id) & gold_ids and not set(train.customer_tweet_id) & gold_ids
    lab = SilverLabeler()
    for name, df, tag in (("train", train, "kb"), ("dev", dev, "silverdev")):
        labels = lab.label_many(df.customer_message.tolist(), tag=tag)
        df["silver_intent"] = [x.intent for x in labels]
        df["silver_confidence"] = [x.confidence for x in labels]
        df["silver_band"] = [x.band for x in labels]
        df["silver_source"] = [x.source for x in labels]
        cols = ["customer_tweet_id", "customer_author", "created_at", "customer_message", "context", "n_context_turns", "brand_reply", "split",
                "silver_intent", "silver_confidence", "silver_band", "silver_source"]
        df[cols].to_csv(config.PROCESSED_DIR / f"silver_{name}.csv", index=False)
    stats = {"version": SILVER_VERSION, "train_rows": len(train), "dev_rows": len(dev),
             "train_intent_distribution": train.silver_intent.value_counts().to_dict(), "dev_intent_distribution": dev.silver_intent.value_counts().to_dict(),
             "train_band": train.silver_band.value_counts().to_dict(), "train_source": train.silver_source.value_counts().to_dict(),
             "coverage_high_or_medium": round(float(train.silver_band.isin(["HIGH", "MEDIUM"]).mean()), 4),
             "confidence_quantiles": train.silver_confidence.quantile([0.1, 0.25, 0.5, 0.75, 0.9]).round(3).to_dict()}
    (OUT / "silver_stats.json").write_text(json.dumps(stats, indent=2, default=str), encoding="utf-8")
    print(json.dumps(stats, indent=2, default=str))
    # hand-check sample: 20 per band from TRAIN, fixed seed
    parts = [train[train.silver_band == b].sample(n=min(20, (train.silver_band == b).sum()), random_state=config.SEED) for b in ("HIGH", "MEDIUM", "LOW")]
    smp = pd.concat(parts)[["customer_tweet_id", "customer_message", "silver_intent", "silver_confidence", "silver_band", "silver_source"]]
    smp["human_intent"] = ""
    smp.to_csv(OUT / "silver_noise_sample.csv", index=False)
    for _, r in smp.iterrows():
        print(f"{r.customer_tweet_id} [{r.silver_band:6s} {r.silver_confidence:.2f} {r.silver_intent:20s}] {r.customer_message[:150]}")


if __name__ == "__main__":
    main()
