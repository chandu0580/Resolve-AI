"""Phase 8: prove the console phase left the frozen data and every earlier artifact untouched, and re-run the security scan.

  python scripts/phase8/verify_integrity.py

1. Runs scripts/phase7/c_integrity.py (golden set + evaluation + earlier artifacts vs the pre-Phase-7 hash snapshot).
2. Runs scripts/security_scan.py (secrets, endpoint address, PII in traces, file sizes) over every committable file,
   including frontend/.
3. Lists any file in the frozen locations modified after Phase 8 started (the creation time of frontend/package.json).
Both Phase 7 scripts are executed unchanged except that their report path points to artifacts/phase8/, so the Phase 7
reports are not overwritten. Writes artifacts/phase8/integrity.json and artifacts/phase8/security_scan.json.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "phase8"
FROZEN = ["data/golden", "data/human_eval", "data/processed", "artifacts/evaluation", "artifacts/phase7", "artifacts/resolution",
          "artifacts/agent", "artifacts/intelligence", "artifacts/retrieval", "resolveai/retrieval", "resolveai/models"]


def run_redirected(script: Path, old: str, new: str) -> int:
    source = script.read_text(encoding="utf-8")
    if old not in source:
        raise SystemExit(f"{script}: expected report path {old!r} not found; refusing to guess")
    code = compile(source.replace(old, new), str(script), "exec")
    namespace = {"__name__": "phase8_redirected", "__file__": str(script)}
    exec(code, namespace)  # noqa: S102 - the repository's own script, with only its output path changed
    return namespace["main"]()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(ROOT))
    integrity_rc = run_redirected(ROOT / "scripts/phase7/c_integrity.py", '"artifacts/phase7/integrity.json"', '"artifacts/phase8/_integrity_phase7_snapshot.json"')
    scan_rc = run_redirected(ROOT / "scripts/security_scan.py", '"phase7" / "security_scan.json"', '"phase8" / "security_scan.json"')

    phase8_start = (ROOT / "frontend" / "package.json").stat().st_ctime
    touched = []
    for rel in FROZEN:
        base = ROOT / rel
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if p.is_file() and "__pycache__" not in p.parts and os.stat(p).st_mtime > phase8_start:
                touched.append(str(p.relative_to(ROOT)).replace("\\", "/"))
    snapshot = json.loads((OUT / "_integrity_phase7_snapshot.json").read_text(encoding="utf-8"))
    (OUT / "_integrity_phase7_snapshot.json").unlink()
    report = {
        "phase7_hash_snapshot": snapshot,
        "frozen_locations": FROZEN,
        "modified_after_phase8_start": touched,
        "security_scan_passed": scan_rc == 0,
        "passed": integrity_rc == 0 and scan_rc == 0 and not touched,
    }
    (OUT / "integrity.json").write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "phase7_hash_snapshot"} | {"hash_snapshot_passed": snapshot["passed"], "files_checked": snapshot["files_checked"]}, indent=1))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
