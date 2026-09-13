"""Phase 10-K: extract the real examples and counts behind the final failure analysis from the release golden run (read-only).

  python scripts/final/k_failure_modes.py

Inputs: artifacts/final/evaluation/runs/final_release.jsonl (+ judge), data/golden (hash-verified), artifacts/final/risk_experiment/report.json.
Writes artifacts/final/failure_modes.json: unnecessary handoffs by reason code and flag source, the missed escalations, the evidence-level
distribution and what STRONG rows are about, the most frequent intent confusions, and judge-flagged response templates. Messages are
the already-redacted golden texts, truncated.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from resolveai.evaluation import load_golden  # noqa: E402
from resolveai.evaluation.records import read_records  # noqa: E402
from resolveai.evaluation.reporting import gold_map  # noqa: E402

REL = ROOT / "artifacts" / "final" / "evaluation"
OUT = ROOT / "artifacts" / "final" / "failure_modes.json"


def main() -> int:
    gm = gold_map(load_golden())
    recs = sorted(read_records(REL / "runs" / "final_release.jsonl"), key=lambda r: r.gid)
    judge = {j["gid"]: j for j in (json.loads(x) for x in (REL / "judge_final_release.jsonl").read_text(encoding="utf-8").splitlines() if x.strip())}
    unnecessary = [r for r in recs if r.escalate_pred and not gm[r.gid]["should_escalate"]]
    by_reason = Counter(r.reason_code for r in unnecessary)
    examples = {}
    for reason, _ in by_reason.most_common():
        examples[reason] = [{"gid": r.gid, "intent_gold": gm[r.gid]["intent"], "risk_flags": r.risk_flags, "evidence_level": r.evidence_level, "message": r.message[:140]}
                            for r in unnecessary if r.reason_code == reason][:4]
    missed = [{"gid": r.gid, "gold_reason": gm[r.gid]["escalation_reason"], "action": r.action, "reason_code": r.reason_code, "risk_flags": r.risk_flags, "message": r.message[:160]}
              for r in recs if gm[r.gid]["should_escalate"] and not r.escalate_pred]
    strong = [r for r in recs if r.evidence_level == "STRONG"]
    confusions = Counter((gm[r.gid]["intent"], r.intent_pred) for r in recs if r.intent_pred != gm[r.gid]["intent"])
    flagged_templates = Counter(r.response for r in recs if r.gid in judge and not judge[r.gid].get("failed") and judge[r.gid]["hallucination"] and r.response_kind in ("handoff", "clarify"))
    non_english_handoffs = [{"gid": r.gid, "reason_code": r.reason_code, "message": r.message[:100]} for r in recs if gm[r.gid]["intent"] == "non_english" and r.action == "HUMAN_HANDOFF"]
    report = {
        "n": len(recs),
        "unnecessary_handoffs": {"total": len(unnecessary), "by_reason_code": dict(by_reason.most_common()), "examples": examples},
        "missed_escalations": missed,
        "evidence_levels": dict(Counter(r.evidence_level for r in recs)),
        "strong_evidence_rows": [{"gid": r.gid, "intent_gold": gm[r.gid]["intent"], "action": r.action, "reason_code": r.reason_code, "message": r.message[:120]} for r in strong],
        "autonomous_replies": [{"gid": r.gid, "kind": r.response_kind, "intent_gold": gm[r.gid]["intent"]} for r in recs if r.action == "AUTO_HANDLE"],
        "intent_errors": sum(1 for r in recs if r.intent_pred != gm[r.gid]["intent"]),
        "top_intent_confusions": [{"gold": g, "predicted": p, "count": n} for (g, p), n in confusions.most_common(6)],
        "judge_flagged_templates": [{"text": t[:160], "hallucination_flags": n} for t, n in flagged_templates.most_common(6)],
        "non_english_rows_handed_off": non_english_handoffs,
    }
    OUT.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("unnecessary_handoffs", "missed_escalations", "evidence_levels", "intent_errors", "top_intent_confusions", "judge_flagged_templates")}, indent=1, ensure_ascii=False)[:6000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
