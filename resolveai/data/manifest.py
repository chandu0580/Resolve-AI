"""Dataset manifest: everything a reader needs to trust and reproduce the processed data.

Run after ingestion:  python -m resolveai.data.manifest
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from resolveai import config

MANIFEST = config.PROCESSED_DIR / "dataset_manifest.json"


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build(include_raw_hash: bool = True) -> dict:
    sub_path = config.PROCESSED_DIR / "apple_pairs.csv"
    sub = pd.read_csv(sub_path, parse_dates=["created_at"])
    full_path = config.PROCESSED_DIR / "full_apple_pairs.csv"
    full = pd.read_csv(full_path, usecols=["split", "pii_redacted", "outcome", "created_at"], parse_dates=["created_at"]) if full_path.exists() else None

    def pii_stats(df: pd.DataFrame) -> dict:
        counts: dict[str, int] = {}
        for s in df.pii_redacted.dropna():
            if s:
                for k, v in json.loads(s).items():
                    counts[k] = counts.get(k, 0) + int(v)
        return {"rows_with_pii": int((df.pii_redacted.fillna("") != "").sum()), "tokens_by_type": counts}

    kb, ho = sub[sub.split == "kb"], sub[sub.split == "holdout"]
    m = {
        "source": {"name": "Customer Support on Twitter", "provider": "Kaggle thoughtvector/customer-support-on-twitter", "version": "10", "file": "twcs.csv", "license": "CC BY-NC-SA 4.0 (per Kaggle listing)"},
        "raw_sha256": sha256_file(config.RAW_CSV) if include_raw_hash and config.RAW_CSV.exists() else None,
        "brand": config.BRAND,
        "preprocessing_version": config.PREPROCESSING_VERSION,
        "seed": config.SEED,
        "row_counts": {
            "full_pairs": int(len(full)) if full is not None else None,
            "full_split": full.split.value_counts().to_dict() if full is not None else None,
            "subsample": int(len(sub)),
            "subsample_split": sub.split.value_counts().to_dict(),
        },
        "split_boundaries": {
            "kb_max_created_at": str(kb.created_at.max()),
            "holdout_min_created_at": str(ho.created_at.min()),
            "holdout_max_created_at": str(ho.created_at.max()),
            "rule": "temporal: holdout = final 5 calendar days; kb strictly earlier",
        },
        "pii": {"subsample": pii_stats(sub), "full": pii_stats(full) if full is not None else None},
        "outcome_signal": {"subsample": sub.outcome.value_counts().to_dict(), "note": "weak signal; rerank bonus only (hand-check precision: positive 0.72, negative 1.00)"},
        "holdout_customer_seen_in_kb_share": round(float(ho.customer_seen_in_kb.mean()), 4),
        "artifacts": {
            "apple_pairs.csv": {"sha256": sha256_file(sub_path), "bytes": sub_path.stat().st_size, "committed": True},
            "full_apple_pairs.csv": {"sha256": sha256_file(full_path), "bytes": full_path.stat().st_size, "committed": False} if full_path.exists() else None,
        },
        "columns": list(sub.columns),
    }
    return m


def main() -> None:
    m = build()
    MANIFEST.write_text(json.dumps(m, indent=2, default=str), encoding="utf-8")
    print(json.dumps({k: m[k] for k in ("brand", "preprocessing_version", "row_counts", "split_boundaries", "holdout_customer_seen_in_kb_share")}, indent=2, default=str))
    print("wrote", MANIFEST)


if __name__ == "__main__":
    main()
