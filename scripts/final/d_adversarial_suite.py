"""Phase 10-D: run the final adversarial suite and write the PASS/FAIL table.

  python scripts/final/d_adversarial_suite.py

The cases live in tests/test_final_adversarial_suite.py and pytest runs the same code; this script only records expected vs actual.
Writes artifacts/final/adversarial_suite.json and artifacts/final/adversarial_suite.md. Exit code 1 if any case fails.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
OUT = ROOT / "artifacts" / "final"


def main() -> int:
    spec = importlib.util.spec_from_file_location("final_adversarial_suite", ROOT / "tests" / "test_final_adversarial_suite.py")
    suite = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = suite   # dataclasses resolve the defining module through sys.modules
    spec.loader.exec_module(suite)
    t0 = time.perf_counter()
    parts = suite.build_parts()
    results = []
    for case in suite.CASES:
        tmp = Path(tempfile.mkdtemp(prefix="resolveai_adv_"))
        try:
            results.append(suite.run_case(case, parts, tmp))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        r = results[-1]
        print(f"{r['id']} {'PASS' if r['passed'] else 'FAIL'} {r['name']}: {r['actual_action']} {r['reason_code']} {r['failed_checks'] or ''}", flush=True)
    passed = sum(r["passed"] for r in results)
    report = {"n_cases": len(results), "passed": passed, "failed": len(results) - passed, "wall_seconds": round(time.perf_counter() - t0, 1),
              "model": "scripted double (tests/test_phase9_adversarial.py::Model); knowledge base, classifier, policy, gates, API and trace store are real",
              "cases": results}
    (OUT / "adversarial_suite.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    L = ["# Final adversarial suite", "",
         f"{passed} of {len(results)} cases pass. Source: `tests/test_final_adversarial_suite.py` (pytest runs the same cases). The knowledge base, classifier, "
         "policy, gates, API and trace store are real; the model is a scripted double whose answers, failures and latency are set per case.", "",
         "| # | Scenario | Expected | Actual | Result | Checks |", "|---|---|---|---|---|---|"]
    for r in results:
        checks = ", ".join(f"{k}{'' if ok else ' ✗'}" for k, ok in r["checks"].items())
        actual = f"{r['actual_action']}" + (f" / {r['reason_code']}" if r["reason_code"] else "")
        L.append(f"| {r['id']} | {r['name']} | {r['expected']} | {actual} | {'PASS' if r['passed'] else '**FAIL**'} | {checks} |")
    (OUT / "adversarial_suite.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"{passed}/{len(results)} passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
