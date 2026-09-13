"""Phase 10-F: final integrity, reproducibility and security verification. Non-destructive: nothing frozen is written.

  python scripts/final/f_final_verification.py [--skip-cached-eval] [--skip-scan]

1. Golden set: load_golden() verifies data/golden/golden_final.csv against its freeze manifest.
2. Frozen and final artifacts: every file recorded in artifacts/final/phase10_start_snapshot.json under a FROZEN location (data/, artifacts/
   except the output folders artifacts/final/ and artifacts/product/, resolveai/models/, the frozen gate, rerank and second-opinion configuration files) must be byte-identical now.
   Snapshot files that are gitignored and absent (a fresh clone) are counted, not failed. Files that appeared since the snapshot under a
   frozen location are listed and fail the check. Code, tests, scripts and docs are MUTABLE: their changes since the snapshot are listed
   for transparency.
3. Phase 7 hash snapshot: scripts/phase7/c_integrity.py, unchanged except that its report goes to artifacts/final/. Snapshot files that are
   gitignored and absent (a fresh clone) are counted as local-only, not failed.
4. Cached evaluation: scripts/phase9/e_cached_eval_check.py, unchanged except that its scratch folder and report live under artifacts/final/.
   It runs scripts/evaluate.py --cached and compares the 11 regenerated Phase 6 result files with the frozen ones.
5. Security scan: scripts/security_scan.py, report redirected to artifacts/final/security_scan.json.
Writes artifacts/final/verification.json. Exit code 1 on any failure.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "final"
SNAPSHOT = OUT / "phase10_start_snapshot.json"
FROZEN_PREFIXES = ("data/", "artifacts/", "resolveai/models/", "resolveai/retrieval/gate_config.json", "resolveai/retrieval/gate_v3_config.json",
                   "resolveai/retrieval/rerank_weights.json", "resolveai/agent/second_opinion_policy.json")
FROZEN_WALK = ["data/golden", "data/human_eval", "data/processed", "data/dev", "data/demo", "artifacts", "resolveai/models"]
MUTABLE_WALK = ["resolveai", "scripts", "tests", "frontend/app", "frontend/components", "frontend/lib", "frontend/tests", "frontend/scripts", "docs"]
MUTABLE_FILES = ["README.md", ".gitignore", ".env.example", "requirements.txt", "pyproject.toml", "frontend/package.json"]


# Output folders written after the Phase 10 snapshot: artifacts/final/ (this release's results) and artifacts/product/ (the product and
# final hardening passes, verified against their own baselines by scripts/verification/final_verification.py). Without the second
# entry a clean copy of the final repository failed this check on 84 committable product files (final hardening clean-environment run).
OUTPUT_FOLDERS = ("artifacts/final/", "artifacts/product/")


def frozen(rel: str) -> bool:
    return rel.startswith(FROZEN_PREFIXES) and not rel.startswith(OUTPUT_FOLDERS)


def sha(p: Path) -> str:
    d = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            d.update(chunk)
    return d.hexdigest()


def skip(rel: str) -> bool:
    return "__pycache__" in rel or rel.endswith(".pyc") or "/traces/" in rel or "/traces_dev/" in rel


def walk(locations: list[str]) -> set[str]:
    out = set()
    for loc in locations:
        base = ROOT / loc
        if base.is_file():
            out.add(loc)
        elif base.exists():
            out |= {str(p.relative_to(ROOT)).replace("\\", "/") for p in base.rglob("*") if p.is_file()}
    return {r for r in out if not skip(r)}


def ignored(paths: list[str]) -> set[str]:
    if not paths:
        return set()
    try:
        # bytes, not text: on Windows text mode writes "\r\n", and git then matches none of the paths but the last
        res = subprocess.run(["git", "check-ignore", "--stdin"], cwd=ROOT, input=("\n".join(paths) + "\n").encode("utf-8"), capture_output=True)
        return {line.strip() for line in res.stdout.decode("utf-8").splitlines() if line.strip()}
    except OSError:
        return set()


def run_redirected(script: Path, replacements: list[tuple[str, str]], argv: list[str] | None = None) -> int:
    source = script.read_text(encoding="utf-8")
    for old, new in replacements:
        if old not in source:
            raise SystemExit(f"{script}: expected text {old!r} not found; refusing to guess where it writes")
        source = source.replace(old, new)
    if argv is not None:
        sys.argv = argv
    ns = {"__name__": "final_verification_redirected", "__file__": str(script)}
    exec(compile(source, str(script), "exec"), ns)  # noqa: S102 - the repository's own script, output location changed only
    return ns["main"]()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-cached-eval", action="store_true")
    ap.add_argument("--skip-scan", action="store_true")
    a = ap.parse_args()
    sys.path.insert(0, str(ROOT))
    t0 = time.perf_counter()
    report: dict = {"started": time.strftime("%Y-%m-%dT%H:%M:%S")}

    from resolveai.evaluation import load_golden
    manifest = json.loads((ROOT / "data" / "golden" / "golden_freeze_manifest.json").read_text(encoding="utf-8"))
    try:
        n = len(load_golden())
        report["golden"] = {"verified": True, "rows": n, "sha256": manifest["sha256"]}
    except Exception as e:  # noqa: BLE001 - report any refusal
        report["golden"] = {"verified": False, "error": type(e).__name__}

    snap = json.loads(SNAPSHOT.read_text(encoding="utf-8"))["files"]
    frozen_snap = {k: v for k, v in snap.items() if frozen(k)}
    changed, missing = [], []
    for rel, digest in frozen_snap.items():
        p = ROOT / rel
        if not p.exists():
            missing.append(rel)
        elif sha(p) != digest:
            changed.append(rel)
    ign = ignored(missing)
    new_frozen = sorted(r for r in walk(FROZEN_WALK) if frozen(r) and r not in frozen_snap)
    report["frozen_artifacts"] = {"checked": len(frozen_snap), "changed": changed, "missing_committable": sorted(set(missing) - ign), "missing_gitignored_local_only": len(ign & set(missing)),
                                  "new_files_in_frozen_locations": new_frozen, "passed": not changed and not (set(missing) - ign) and not new_frozen}
    mutable_snap = {k: v for k, v in snap.items() if not frozen(k)}
    now = walk(MUTABLE_WALK) | {f for f in MUTABLE_FILES if (ROOT / f).exists()}
    report["mutable_changes_since_phase10_start"] = {"changed": sorted(r for r in now & set(mutable_snap) if sha(ROOT / r) != mutable_snap[r]),
                                                      "added": sorted(now - set(mutable_snap)), "removed": sorted(set(mutable_snap) - now)}

    rc7 = run_redirected(ROOT / "scripts/phase7/c_integrity.py", [('"artifacts/phase7/integrity.json"', '"artifacts/final/_phase7_snapshot_check.json"')])
    p7 = json.loads((OUT / "_phase7_snapshot_check.json").read_text(encoding="utf-8"))
    (OUT / "_phase7_snapshot_check.json").unlink()
    p7_ignored = ignored(list(p7["missing"])) & set(p7["missing"])   # the Phase 7 snapshot also lists local-only (gitignored) files
    p7_missing = sorted(set(p7["missing"]) - p7_ignored)
    report["phase7_hash_snapshot"] = {"files_checked": p7["files_checked"], "changed": p7["changed"], "missing_committable": p7_missing,
                                      "missing_gitignored_local_only": len(p7_ignored), "golden_matches_freeze_manifest": p7["golden_matches_freeze_manifest"],
                                      "script_exit_code": rc7, "passed": not p7["changed"] and not p7_missing and bool(p7["golden_matches_freeze_manifest"])}

    if not a.skip_cached_eval:
        rc = run_redirected(ROOT / "scripts/phase9/e_cached_eval_check.py",
                            [('"artifacts" / "phase9" / "evaluation" / "_cached_check_scratch"', '"artifacts" / "final" / "_cached_check_scratch"'),
                             ('ROOT / "artifacts" / "phase9" / "evaluation" / "cached_eval_check.json"', 'ROOT / "artifacts" / "final" / "cached_eval_check.json"')])
        ce = json.loads((OUT / "cached_eval_check.json").read_text(encoding="utf-8"))
        report["cached_evaluation"] = {"all_identical": ce["all_identical"], "files": {k: v["identical"] for k, v in ce["compared"].items()},
                                       "runtime_seconds": ce["runtime_seconds"], "passed": rc == 0 and ce["all_identical"]}
    if not a.skip_scan:
        rc = run_redirected(ROOT / "scripts/security_scan.py", [('"phase7" / "security_scan.json"', '"final" / "security_scan.json"')])
        sc = json.loads((OUT / "security_scan.json").read_text(encoding="utf-8"))
        report["security_scan"] = {"passed": rc == 0 and sc["passed"], "committable_files": sc["committable_files"], "committable_mb": sc["committable_mb"],
                                   "trace_records_scanned": sc["trace_records_scanned"], "trace_records_with_pii": sc["trace_records_with_pii"],
                                   "env_committable": sc[".env_committable"], "findings": sc["findings"]}
    parts = [report["golden"]["verified"], report["frozen_artifacts"]["passed"], report["phase7_hash_snapshot"]["passed"]]
    parts += [report[k]["passed"] for k in ("cached_evaluation", "security_scan") if k in report]
    report["passed"] = all(parts)
    report["wall_seconds"] = round(time.perf_counter() - t0, 1)
    (OUT / "verification.json").write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "mutable_changes_since_phase10_start"}, indent=1))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
