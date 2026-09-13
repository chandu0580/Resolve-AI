"""Frozen golden-set access. The ONLY sanctioned way for code to read the gold labels.

- Verifies the file hash against golden_freeze_manifest.json on every load, so a silent edit fails loudly.
- Never writes. Model development must not modify the golden set (locked invariant).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from resolveai import config

GOLDEN_CSV = config.GOLDEN_DIR / "golden_final.csv"
MANIFEST = config.GOLDEN_DIR / "golden_freeze_manifest.json"
REQUIRED = ["gid", "customer_tweet_id", "brand_tweet_id", "created_at", "context", "customer_message", "intent", "should_escalate", "escalation_reason"]
FLAGS = ["taxonomy_gap", "insufficient_context", "multi_intent", "evidence_unavailable"]


class GoldenIntegrityError(RuntimeError):
    pass


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_golden(verify: bool = True) -> pd.DataFrame:
    if not GOLDEN_CSV.exists():
        raise GoldenIntegrityError("golden_final.csv not found; the golden set has not been frozen")
    if verify:
        man = json.loads(MANIFEST.read_text(encoding="utf-8"))
        actual = sha256_file(GOLDEN_CSV)
        if actual != man["sha256"]:
            raise GoldenIntegrityError(f"golden_final.csv hash {actual[:12]} != manifest {man['sha256'][:12]}: the frozen set was modified")
    df = pd.read_csv(GOLDEN_CSV, dtype=str, keep_default_na=False)
    df["should_escalate"] = df.should_escalate.str.lower().eq("true")
    for f in FLAGS:
        df[f] = df[f].str.lower().eq("true")
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise GoldenIntegrityError(f"golden_final.csv missing columns {missing}")
    return df
