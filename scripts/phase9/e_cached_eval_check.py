"""Phase 9-E: re-run the cached Phase 6 evaluation WITHOUT touching the frozen artifacts, and prove it reproduces them.

  python scripts/phase9/e_cached_eval_check.py

`scripts/evaluate.py --cached` writes its tables into artifacts/evaluation/. Running it in place would overwrite the frozen
results (and its narrative step would rewrite the Phase 6 reports). This check instead:
  1. copies the evaluation INPUTS (runs, judge and pairwise results, offline ablations, judge config, previous manifest) to a scratch folder;
  2. executes scripts/evaluate.py unchanged except that its output folder points at the scratch folder and the narrative step is skipped;
  3. compares every regenerated JSON result with the frozen file (parsed JSON equality);
  4. deletes the scratch copies and writes artifacts/phase9/evaluation/cached_eval_check.json.
The golden hash is verified by evaluate.py itself (load_golden).
"""
from __future__ import annotations

import json
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FROZEN = ROOT / "artifacts" / "evaluation"
SCRATCH = ROOT / "artifacts" / "phase9" / "evaluation" / "_cached_check_scratch"
OUT = ROOT / "artifacts" / "phase9" / "evaluation" / "cached_eval_check.json"
INPUTS = ["judge_results.jsonl", "pairwise_results.jsonl", "offline_ablations.json", "judge_config.json", "reproduction_manifest.json"]
COMPARED = ["headline_metrics.json", "intent_report.json", "escalation_report.json", "autonomy_report.json", "reply_quality.json", "pairwise_results.json",
            "slice_analysis.json", "baseline_comparison.json", "judge_agreement.json", "retrieval_report.json", "judge_rubric.json"]


def diff_keys(a, b, path="") -> list[str]:
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                out.append(f"{path}/{k} (missing on one side)")
            else:
                out += diff_keys(a[k], b[k], f"{path}/{k}")
        return out
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return [f"{path} (length {len(a)} vs {len(b)})"]
        return [d for i, (x, y) in enumerate(zip(a, b, strict=True)) for d in diff_keys(x, y, f"{path}[{i}]")]
    return [] if a == b else [f"{path}: {str(a)[:60]} != {str(b)[:60]}"]


def main() -> int:
    if SCRATCH.exists():
        shutil.rmtree(SCRATCH)
    (SCRATCH / "runs").mkdir(parents=True)
    for p in (FROZEN / "runs").glob("*"):
        if p.suffix in (".jsonl", ".json"):
            shutil.copy2(p, SCRATCH / "runs" / p.name)
    for name in INPUTS:
        if (FROZEN / name).exists():
            shutil.copy2(FROZEN / name, SCRATCH / name)
    src = (ROOT / "scripts" / "evaluate.py").read_text(encoding="utf-8")
    old_ev = 'EV = ROOT / "artifacts" / "evaluation"'
    old_narr = 'narr = ROOT / "scripts/phase6/e_narrative.py"'
    if old_ev not in src or old_narr not in src:
        raise SystemExit("scripts/evaluate.py changed shape; refusing to guess where it writes")
    src = src.replace(old_ev, 'EV = ROOT / "artifacts" / "phase9" / "evaluation" / "_cached_check_scratch"').replace(old_narr, 'narr = ROOT / "__narrative_step_skipped__.py"')
    sys.argv = ["evaluate.py", "--cached"]
    sys.path.insert(0, str(ROOT))
    t0 = time.perf_counter()
    ns = {"__name__": "phase9_cached_check", "__file__": str(ROOT / "scripts" / "evaluate.py")}
    exec(compile(src, str(ROOT / "scripts" / "evaluate.py"), "exec"), ns)  # noqa: S102 - the repository's own script, output folder redirected
    rc = ns["main"]()
    results = {}
    for name in COMPARED:
        a, b = FROZEN / name, SCRATCH / name
        if not b.exists():
            results[name] = {"identical": False, "reason": "not regenerated"}
            continue
        d = diff_keys(json.loads(a.read_text(encoding="utf-8")), json.loads(b.read_text(encoding="utf-8")))
        results[name] = {"identical": not d, "differences": d[:20], "n_differences": len(d)}
    report = {"evaluate_exit_code": rc, "runtime_seconds": round(time.perf_counter() - t0, 1), "compared": results,
              "all_identical": all(r["identical"] for r in results.values()), "frozen_artifacts_touched": False,
              "note": "evaluate.py executed unchanged except for its output folder and the skipped narrative step; scratch copies deleted afterwards"}
    shutil.rmtree(SCRATCH)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "compared"} | {"files": {k: v["identical"] for k, v in results.items()}}, indent=1))
    return 0 if report["all_identical"] else 1


if __name__ == "__main__":
    sys.exit(main())
