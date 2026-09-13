"""Phase 9-F: prove Phase 9 left the frozen data and every earlier artifact untouched, and re-run the security scan.

  python scripts/phase9/f_verify_integrity.py

1. scripts/phase7/c_integrity.py: golden set, evaluation artifacts and earlier-phase artifacts vs the pre-Phase-7 hash snapshot.
2. scripts/security_scan.py: secrets, endpoint address, PII in traces, file sizes, over every committable file (frontend included).
3. Every file in the frozen locations modified after Phase 9 started (the creation time of scripts/phase9/a_risk_dev_experiment.py).
   The frozen retrieval and classifier configuration files are checked individually: Phase 9 changed retrieval CODE (quarantine,
   evidence re-redaction), never the frozen gate, rerank or classifier configuration.
Both Phase 7 scripts are executed unchanged except for their report path (artifacts/phase9/), so no earlier report is overwritten.
Writes artifacts/phase9/integrity.json and artifacts/phase9/security_scan.json.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "phase9"
FROZEN_DIRS = ["data/golden", "data/human_eval", "data/processed", "artifacts/evaluation", "artifacts/phase7", "artifacts/phase8", "artifacts/resolution",
               "artifacts/agent", "artifacts/intelligence", "artifacts/retrieval", "resolveai/models"]
FROZEN_FILES = ["resolveai/retrieval/gate_config.json", "resolveai/retrieval/gate_v3_config.json", "resolveai/retrieval/rerank_weights.json",
                "resolveai/agent/second_opinion_policy.json", "data/demo/scenarios.json"]


def run_redirected(script: Path, old: str, new: str) -> int:
    source = script.read_text(encoding="utf-8")
    if old not in source:
        raise SystemExit(f"{script}: expected report path {old!r} not found; refusing to guess")
    ns = {"__name__": "phase9_redirected", "__file__": str(script)}
    exec(compile(source.replace(old, new), str(script), "exec"), ns)  # noqa: S102 - the repository's own script, output path changed only
    return ns["main"]()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(ROOT))
    integrity_rc = run_redirected(ROOT / "scripts/phase7/c_integrity.py", '"artifacts/phase7/integrity.json"', '"artifacts/phase9/_phase7_snapshot_check.json"')
    scan_rc = run_redirected(ROOT / "scripts/security_scan.py", '"phase7" / "security_scan.json"', '"phase9" / "security_scan.json"')
    start = (ROOT / "scripts" / "phase9" / "a_risk_dev_experiment.py").stat().st_ctime
    touched = []
    for rel in FROZEN_DIRS:
        base = ROOT / rel
        if base.exists():
            touched += [str(p.relative_to(ROOT)).replace("\\", "/") for p in base.rglob("*") if p.is_file() and "__pycache__" not in p.parts and os.stat(p).st_mtime > start]
    touched += [f for f in FROZEN_FILES if (ROOT / f).exists() and os.stat(ROOT / f).st_mtime > start]
    snap = json.loads((OUT / "_phase7_snapshot_check.json").read_text(encoding="utf-8"))
    (OUT / "_phase7_snapshot_check.json").unlink()
    scan = json.loads((OUT / "security_scan.json").read_text(encoding="utf-8"))
    report = {"phase7_hash_snapshot": {"files_checked": snap["files_checked"], "changed": snap["changed"], "missing": snap["missing"], "golden_sha256": snap["golden_sha256"],
                                       "golden_matches_freeze_manifest": snap["golden_matches_freeze_manifest"], "passed": snap["passed"]},
              "frozen_locations": FROZEN_DIRS + FROZEN_FILES, "modified_after_phase9_start": touched,
              "security_scan": {"passed": scan["passed"], "committable_files": scan["committable_files"], "trace_records_scanned": scan["trace_records_scanned"],
                                "trace_records_with_pii": scan["trace_records_with_pii"], "env_committable": scan[".env_committable"], "findings": scan["findings"]},
              "passed": integrity_rc == 0 and scan_rc == 0 and not touched}
    (OUT / "integrity.json").write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=1))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
