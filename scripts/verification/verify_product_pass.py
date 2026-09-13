"""Product-1: integrity, reproducibility and security verification after the product completion work. Non-destructive.

  python scripts/verification/verify_product_pass.py [--skip-cached-eval] [--skip-scan]

Runs scripts/final/f_final_verification.py unchanged except for WHERE it compares and writes:
- the baseline is artifacts/product/product_start_snapshot.json (413 files hashed before any product change), so every frozen
  location, now INCLUDING artifacts/final/ (the release artifacts of record), must be byte-identical and must have no new files;
- the reports (verification.json, cached_eval_check.json, security_scan.json) go to artifacts/product/.
Golden hash, the Phase 7 hash snapshot, the cached evaluation (11 Phase 6 result files) and the security scan run exactly as in the
release verification. Exit code 1 on any failure.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FINAL = ROOT / "scripts" / "final" / "f_final_verification.py"

REPLACEMENTS = [
    ('OUT = ROOT / "artifacts" / "final"', 'OUT = ROOT / "artifacts" / "product"'),
    ('SNAPSHOT = OUT / "phase10_start_snapshot.json"', 'SNAPSHOT = OUT / "product_start_snapshot.json"'),
    ('OUTPUT_FOLDERS = ("artifacts/final/", "artifacts/product/")', 'OUTPUT_FOLDERS = ("artifacts/product/",)'),
    ('"artifacts/final/_phase7_snapshot_check.json"', '"artifacts/product/_phase7_snapshot_check.json"'),
    ("'\"artifacts\" / \"final\" / \"_cached_check_scratch\"'", "'\"artifacts\" / \"product\" / \"_cached_check_scratch\"'"),
    ("'ROOT / \"artifacts\" / \"final\" / \"cached_eval_check.json\"'", "'ROOT / \"artifacts\" / \"product\" / \"cached_eval_check.json\"'"),
    ("'\"final\" / \"security_scan.json\"'", "'\"product\" / \"security_scan.json\"'"),
    ('"mutable_changes_since_phase10_start"', '"mutable_changes_since_product_start"'),
]


def main() -> int:
    source = FINAL.read_text(encoding="utf-8")
    for old, new in REPLACEMENTS:
        if old not in source:
            raise SystemExit(f"{FINAL}: expected text {old!r} not found; refusing to guess where it writes")
        source = source.replace(old, new)
    ns = {"__name__": "product_verification", "__file__": str(FINAL)}
    exec(compile(source, str(FINAL), "exec"), ns)  # noqa: S102 - the repository's own script, baseline and output location changed only
    return ns["main"]()


if __name__ == "__main__":
    sys.exit(main())
