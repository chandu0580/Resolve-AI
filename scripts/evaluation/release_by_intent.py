"""Product-1: evaluated-release outcomes by intent (frozen golden set), for the console's Knowledge Center. Read-only.

  python scripts/evaluation/release_by_intent.py

Inputs: artifacts/final/evaluation/runs/final_release.jsonl (the single release run) and data/golden (hash-verified on load).
For each GOLD intent it counts:
- rows;
- evidence levels;
- automatic replies, clarifications and handoffs;
- unnecessary handoffs (a handoff on a row not marked for escalation);
- missed escalations.
It keeps up to three example messages per intent, PII-redacted again here and truncated.

Knowledge-gap candidate rule, fixed here and shown in the console: rows >= 10 AND SUFFICIENT/STRONG share <= 0.10 AND
handoff share >= 0.5. It is a signal for curation, not a recommendation.
Writes artifacts/product/release_by_intent.json. Nothing frozen is written; no model is called.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from resolveai.evaluation import load_golden  # noqa: E402
from resolveai.evaluation.records import read_records  # noqa: E402
from resolveai.evaluation.reporting import gold_map  # noqa: E402
from resolveai.trust.pii import redact_pii  # noqa: E402

RUN = ROOT / "artifacts" / "final" / "evaluation" / "runs" / "final_release.jsonl"
OUT = ROOT / "artifacts" / "product" / "release_by_intent.json"
GAP_RULE = {"min_rows": 10, "max_sufficient_share": 0.10, "min_handoff_share": 0.5}


def main() -> int:
    gm = gold_map(load_golden())
    recs = read_records(RUN)
    groups: dict[str, list] = defaultdict(list)
    for r in recs:
        groups[gm[r.gid]["intent"]].append(r)
    rows = []
    for intent, rs in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        n = len(rs)
        levels = Counter(r.evidence_level or "INSUFFICIENT" for r in rs)
        actions = Counter(r.action for r in rs)
        sufficient = levels.get("SUFFICIENT", 0) + levels.get("STRONG", 0)
        handoffs = actions.get("HUMAN_HANDOFF", 0)
        unnecessary = sum(1 for r in rs if r.escalate_pred and not gm[r.gid]["should_escalate"])
        missed = sum(1 for r in rs if gm[r.gid]["should_escalate"] and not r.escalate_pred)
        gap = n >= GAP_RULE["min_rows"] and sufficient / n <= GAP_RULE["max_sufficient_share"] and handoffs / n >= GAP_RULE["min_handoff_share"]
        rows.append({"intent": intent, "rows": n, "evidence_levels": {k: levels.get(k, 0) for k in ("INSUFFICIENT", "WEAK", "SUFFICIENT", "STRONG")},
                     "sufficient_share": round(sufficient / n, 3), "auto_handled": actions.get("AUTO_HANDLE", 0), "clarifications": actions.get("CLARIFICATION_REQUIRED", 0),
                     "handoffs": handoffs, "handoff_share": round(handoffs / n, 3), "unnecessary_handoffs": unnecessary, "missed_escalations": missed,
                     "top_reasons": dict(Counter(r.reason_code or "none" for r in rs if r.action != "AUTO_HANDLE").most_common(3)),
                     "knowledge_gap_candidate": gap,
                     "examples": [{"gid": r.gid, "action": r.action, "reason_code": r.reason_code, "evidence_level": r.evidence_level, "message": redact_pii(r.message).text[:120]}
                                  for r in rs if r.action != "AUTO_HANDLE"][:3]})
    out = {"source": "artifacts/final/evaluation/runs/final_release.jsonl (release 1.0.0, single golden run) + data/golden labels (hash-verified)",
           "dataset": "FROZEN GOLDEN SET", "n": len(recs), "gap_rule": GAP_RULE, "by_intent": rows,
           "note": "Counts are from 197 annotated tweets of one 2017 AppleSupport burst; small per-intent counts. A gap candidate marks where the knowledge base rarely supports an answer and humans receive most cases."}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    for r in rows:
        print(f"{r['intent']:22s} n={r['rows']:3d} sufficient={r['sufficient_share']:.2f} handoff={r['handoff_share']:.2f} unnecessary={r['unnecessary_handoffs']:2d} gap={r['knowledge_gap_candidate']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
