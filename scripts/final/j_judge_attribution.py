"""Phase 10-J: attribute the judge-score difference between the Phase 9 final run and the release run (read-only analysis).

  python scripts/final/j_judge_attribution.py

Question: the release configuration changed 27 of 197 decisions and the (unvalidated) GLM-5.2 judge's groundedness fell and hallucination
rate rose. Is that change on the rows whose response text changed, and on which response kinds? Identical responses replay from the judge
cache, so a difference there would indicate a scoring change rather than a response change.
Inputs: artifacts/phase9/evaluation/runs/phase9_final.jsonl + judge_phase9_final.jsonl; artifacts/final/evaluation/runs/final_release.jsonl +
judge_final_release.jsonl. Writes artifacts/final/evaluation/judge_attribution.json and .md. No model call, no golden label is changed.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from resolveai.evaluation import load_golden  # noqa: E402
from resolveai.evaluation.records import read_records  # noqa: E402
from resolveai.evaluation.reporting import gold_map  # noqa: E402

OUT = ROOT / "artifacts" / "final" / "evaluation"


def judge(path: Path) -> dict:
    return {j["gid"]: j for j in (json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip())}


def summary(rows: list[tuple[dict, dict]]) -> dict:
    ok = [(a, b) for a, b in rows if not a.get("failed") and not b.get("failed")]
    return {"n": len(rows), "n_both_parsed": len(ok), "hallucination_flags_phase9": sum(bool(a["hallucination"]) for a, _ in ok),
            "hallucination_flags_release": sum(bool(b["hallucination"]) for _, b in ok),
            "groundedness_mean_phase9": round(float(np.mean([a["groundedness"] for a, _ in ok])), 2) if ok else None,
            "groundedness_mean_release": round(float(np.mean([b["groundedness"] for _, b in ok])), 2) if ok else None,
            "judge_failures_phase9": sum(bool(a.get("failed")) for a, _ in rows), "judge_failures_release": sum(bool(b.get("failed")) for _, b in rows)}


def main() -> int:
    gm = gold_map(load_golden())
    p9 = {r.gid: r for r in read_records(ROOT / "artifacts/phase9/evaluation/runs/phase9_final.jsonl")}
    rel = {r.gid: r for r in read_records(OUT / "runs" / "final_release.jsonl")}
    j9, jr = judge(ROOT / "artifacts/phase9/evaluation/judge_phase9_final.jsonl"), judge(OUT / "judge_final_release.jsonl")
    gids = sorted(set(p9) & set(rel) & set(j9) & set(jr))
    same = [g for g in gids if p9[g].response == rel[g].response]
    changed = [g for g in gids if p9[g].response != rel[g].response]
    by_transition = defaultdict(list)
    for g in changed:
        by_transition[f"{p9[g].response_kind} -> {rel[g].response_kind}"].append(g)
    flips_on_identical = [g for g in same if not j9[g].get("failed") and not jr[g].get("failed") and bool(j9[g]["hallucination"]) != bool(jr[g]["hallucination"])]
    release_flags_by_kind = Counter(rel[g].response_kind for g in gids if not jr[g].get("failed") and jr[g]["hallucination"])
    release_parsed_by_kind = Counter(rel[g].response_kind for g in gids if not jr[g].get("failed"))
    rows = []
    for g in changed:
        a, b = j9[g], jr[g]
        rows.append({"gid": g, "phase9": f"{p9[g].action}/{p9[g].reason_code}/{p9[g].response_kind}", "release": f"{rel[g].action}/{rel[g].reason_code}/{rel[g].response_kind}",
                     "gold_should_escalate": gm[g]["should_escalate"], "halluc_phase9": None if a.get("failed") else bool(a["hallucination"]),
                     "halluc_release": None if b.get("failed") else bool(b["hallucination"]), "grounded_phase9": None if a.get("failed") else a["groundedness"],
                     "grounded_release": None if b.get("failed") else b["groundedness"], "release_response": rel[g].response[:160],
                     "judge_note_release": str(b.get("rationale") or b.get("reason") or b.get("notes") or "")[:200]})
    report = {"n": len(gids), "identical_responses": summary([(j9[g], jr[g]) for g in same]), "changed_responses": summary([(j9[g], jr[g]) for g in changed]),
              "hallucination_flips_on_identical_responses": flips_on_identical,
              "changed_by_kind_transition": {k: summary([(j9[g], jr[g]) for g in v]) | {"gids": v} for k, v in sorted(by_transition.items())},
              "release_hallucination_flags_by_response_kind": {k: {"flags": release_flags_by_kind.get(k, 0), "parsed": n} for k, n in release_parsed_by_kind.items()},
              "changed_rows": rows}
    (OUT / "judge_attribution.json").write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    s, c = report["identical_responses"], report["changed_responses"]
    L = ["# Judge attribution: Phase 9 final vs release 1.0.0 (golden, GLM-5.2 judge, NOT human-validated)", "",
         f"- Identical responses: {s['n']} rows (both parsed {s['n_both_parsed']}): hallucination flags {s['hallucination_flags_phase9']} → {s['hallucination_flags_release']}, "
         f"groundedness {s['groundedness_mean_phase9']} → {s['groundedness_mean_release']}; flips on identical text: {len(flips_on_identical)}.",
         f"- Changed responses: {c['n']} rows (both parsed {c['n_both_parsed']}): hallucination flags {c['hallucination_flags_phase9']} → {c['hallucination_flags_release']}, "
         f"groundedness {c['groundedness_mean_phase9']} → {c['groundedness_mean_release']}; judge failures {c['judge_failures_phase9']} → {c['judge_failures_release']}.", "",
         "| transition (response kind) | rows | both parsed | hallucination flags Phase 9 → release | groundedness Phase 9 → release |", "|---|---|---|---|---|"]
    for k, v in report["changed_by_kind_transition"].items():
        L.append(f"| {k} | {v['n']} | {v['n_both_parsed']} | {v['hallucination_flags_phase9']} → {v['hallucination_flags_release']} | {v['groundedness_mean_phase9']} → {v['groundedness_mean_release']} |")
    L += ["", "Release hallucination flags by response kind: " + "; ".join(f"{k} {v['flags']}/{v['parsed']}" for k, v in report["release_hallucination_flags_by_response_kind"].items()), "",
          "| gid | Phase 9 | release | gold escalate | halluc P9 → rel | grounded P9 → rel | release response | judge note (release) |", "|---|---|---|---|---|---|---|---|"]
    L += [f"| {r['gid']} | {r['phase9']} | {r['release']} | {r['gold_should_escalate']} | {r['halluc_phase9']} → {r['halluc_release']} | {r['grounded_phase9']} → {r['grounded_release']} | "
          f"{r['release_response'].replace('|', '/')} | {r['judge_note_release'].replace('|', '/')} |" for r in rows]
    (OUT / "judge_attribution.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L[:12 + len(report["changed_by_kind_transition"])]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
