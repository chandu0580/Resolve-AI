"""Phase 7-C: prove Phase 7 did not touch the frozen golden set, the evaluation artifacts, earlier phase artifacts, the human
packet or the frozen retrieval/classifier configuration. Compares against artifacts/phase7/_pre_phase7_hashes.json, taken
before any Phase 7 change. Writes artifacts/phase7/integrity.json; exit 1 on any difference.
  python scripts/phase7/c_integrity.py
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    snap = json.loads((ROOT / "artifacts/phase7/_pre_phase7_hashes.json").read_text(encoding="utf-8"))["files"]
    changed, missing = [], []
    for rel, h in snap.items():
        p = ROOT / rel
        if not p.exists():
            missing.append(rel)
        elif hashlib.sha256(p.read_bytes()).hexdigest() != h:
            changed.append(rel)
    golden = hashlib.sha256((ROOT / "data/golden/golden_final.csv").read_bytes()).hexdigest()
    manifest = json.loads((ROOT / "data/golden/golden_freeze_manifest.json").read_text(encoding="utf-8"))["sha256"]
    report = {"files_checked": len(snap), "changed": changed, "missing": missing, "golden_sha256": golden, "golden_matches_freeze_manifest": golden == manifest,
              "passed": not changed and not missing and golden == manifest}
    (ROOT / "artifacts/phase7/integrity.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(json.dumps(report, indent=1))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
