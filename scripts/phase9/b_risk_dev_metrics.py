"""Phase 9-B: score the risk variants on the labelled DEV disagreement set and apply the PRE-REGISTERED acceptance rule.

  python scripts/phase9/b_risk_dev_metrics.py

Inputs:  artifacts/phase9/risk/dev_runs.jsonl (a_risk_dev_experiment.py)
         data/dev/phase9_risk_labels.json     (should_escalate per disagreement row; AI annotator under ANNOTATION_GUIDE v1.1, NOT human)
Outputs: artifacts/phase9/risk/risk_dev_report.json, artifacts/phase9/risk/risk_dev_report.md

Why only the disagreement set: rows where every variant makes the same handoff decision contribute identically to every
variant, so all DIFFERENCES in true/false escalations between variants come from the rows where they disagree. Absolute
precision and recall on dev are therefore not claimed; the deltas are exact for the labelled rows.

escalate_pred = HANDOFF (a clarification is not an escalation), exactly as in the golden evaluation.

Acceptance rule, fixed in this file before any experiment result existed. A candidate (V2, V3, V4) is ACCEPTED only if ALL hold:
  1. no new missed escalation whose gold reason is safety, legal_media or private_info       (safety first)
  2. at most one new missed escalation in total                                              (recall floor)
  3. at least 3 fewer unnecessary handoffs than V0 (production)                              (a real improvement, not noise)
  4. its model fallback rate is no more than 5 percentage points above the production prompt's
Among accepted candidates the one with the largest reduction in unnecessary handoffs wins; ties go to the smaller change
(V2: no prompt change < V3: prompt change < V4: both). If none is accepted, production behaviour is kept.
"""
from __future__ import annotations

import json
import math
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "artifacts" / "phase9" / "risk" / "dev_runs.jsonl"
LABELS = ROOT / "data" / "dev" / "phase9_risk_labels.json"
OUT = ROOT / "artifacts" / "phase9" / "risk"
VARIANTS = ("V0", "V1", "V2", "V3", "V4")
CANDIDATES = ("V2", "V3", "V4")
PROTECTED_REASONS = {"safety", "legal_media", "private_info"}
SIZE_ORDER = {"V2": 0, "V3": 1, "V4": 2}


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float] | None:
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return round(c - h, 3), round(c + h, 3)


def main() -> int:
    runs = [json.loads(line) for line in RUNS.read_text(encoding="utf-8").splitlines() if line.strip()]
    labels = json.loads(LABELS.read_text(encoding="utf-8"))
    gold = labels["labels"]
    disagree = [r for r in runs if len({r["decisions"][v]["outcome"] == "HANDOFF" for v in VARIANTS}) > 1]
    missing = [r["customer_tweet_id"] for r in disagree if r["customer_tweet_id"] not in gold]
    if missing:
        raise SystemExit(f"{len(missing)} disagreement rows are unlabelled: {missing[:5]}")
    scored = {}
    for v in VARIANTS:
        tp = fp = fn = tn = 0
        fn_reasons: Counter = Counter()
        for r in disagree:
            g = gold[r["customer_tweet_id"]]
            pred = r["decisions"][v]["outcome"] == "HANDOFF"
            if pred and g["should_escalate"]:
                tp += 1
            elif pred:
                fp += 1
            elif g["should_escalate"]:
                fn += 1
                fn_reasons[g["reason"]] += 1
            else:
                tn += 1
        scored[v] = {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "fn_reasons": dict(fn_reasons),
                     "outcomes": dict(Counter(r["decisions"][v]["outcome"] for r in runs))}
    base = scored["V0"]
    summary = json.loads((OUT / "dev_run_summary.json").read_text(encoding="utf-8"))
    fallback = {"V0": summary["model_v2"]["fallback_rate"], "V1": 0.0, "V2": summary["model_v2"]["fallback_rate"],
                "V3": summary["model_v3"]["fallback_rate"], "V4": summary["model_v3"]["fallback_rate"]}
    decisions = {}
    for c in CANDIDATES:
        s = scored[c]
        new_fn = [r for r in disagree if gold[r["customer_tweet_id"]]["should_escalate"] and r["decisions"]["V0"]["outcome"] == "HANDOFF" and r["decisions"][c]["outcome"] != "HANDOFF"]
        new_fn_protected = [r["customer_tweet_id"] for r in new_fn if gold[r["customer_tweet_id"]]["reason"] in PROTECTED_REASONS]
        removed = [r for r in disagree if r["decisions"]["V0"]["outcome"] == "HANDOFF" and r["decisions"][c]["outcome"] != "HANDOFF"]
        removed_correctly = sum(1 for r in removed if not gold[r["customer_tweet_id"]]["should_escalate"])
        checks = {"no_new_protected_misses": not new_fn_protected, "at_most_one_new_miss": len(new_fn) <= 1,
                  "at_least_3_fewer_unnecessary_handoffs": base["fp"] - s["fp"] >= 3, "fallback_within_5pp": fallback[c] <= fallback["V0"] + 0.05}
        decisions[c] = {"delta_fp": s["fp"] - base["fp"], "delta_fn": s["fn"] - base["fn"], "new_misses": [r["customer_tweet_id"] for r in new_fn],
                        "new_protected_misses": new_fn_protected, "handoffs_removed": len(removed), "removed_correctly": removed_correctly,
                        "removed_correctly_wilson95": wilson(removed_correctly, len(removed)), "fallback_rate": fallback[c], "checks": checks, "accepted": all(checks.values())}
    accepted = sorted((c for c in CANDIDATES if decisions[c]["accepted"]), key=lambda c: (decisions[c]["delta_fp"], SIZE_ORDER[c]))
    winner = accepted[0] if accepted else None
    # which model-only flags produced V0's unnecessary handoffs (the false-positive pattern)
    patterns: Counter = Counter()
    for r in disagree:
        g = gold[r["customer_tweet_id"]]
        if r["decisions"]["V0"]["outcome"] == "HANDOFF" and not g["should_escalate"]:
            model_only = sorted(set(r["decisions"]["V0"]["flags"]) - set(r["rules_flags"]))
            patterns[f"{r['decisions']['V0']['reason_code']} <- model-only flags {model_only}"] += 1
    report = {"n_dev_rows": len(runs), "n_disagreement_rows": len(disagree), "labels_provenance": labels.get("provenance"), "scored_on_disagreement_rows": scored,
              "candidates": decisions, "accepted": accepted, "selected": winner, "false_positive_patterns_v0": dict(patterns.most_common()),
              "acceptance_rule": __doc__.split("Acceptance rule")[1].strip()}
    (OUT / "risk_dev_report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    L = ["# Phase 9 risk over-escalation: DEV results", "", f"Dev rows: {len(runs)} (holdout, golden excluded). Rows where the variants disagree on handoff: {len(disagree)}, "
         f"all labelled for `should_escalate` by an AI annotator under the annotation guide v1.1 (**not human labels**).", "",
         "| variant | handoffs (all rows) | TP | FP (unnecessary) | FN (missed) | missed by reason |", "|---|---|---|---|---|---|"]
    for v in VARIANTS:
        s = scored[v]
        L.append(f"| {v} | {s['outcomes'].get('HANDOFF', 0)} | {s['tp']} | {s['fp']} | {s['fn']} | {s['fn_reasons'] or '-'} |")
    L += ["", "| candidate | Δ unnecessary handoffs | Δ missed | removed handoffs (correctly removed, 95% Wilson) | fallback rate | accepted |", "|---|---|---|---|---|---|"]
    for c in CANDIDATES:
        d = decisions[c]
        L.append(f"| {c} | {d['delta_fp']} | {d['delta_fn']} | {d['handoffs_removed']} ({d['removed_correctly']}, {d['removed_correctly_wilson95']}) | {d['fallback_rate']} | "
                 f"{'yes' if d['accepted'] else 'no: ' + ', '.join(k for k, ok in d['checks'].items() if not ok)} |")
    L += ["", f"**Selected: {winner or 'none (production behaviour kept)'}**", "", "False-positive patterns of production (V0) on the labelled rows:", ""]
    L += [f"- {k}: {n}" for k, n in patterns.most_common()] or ["- none"]
    (OUT / "risk_dev_report.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())
