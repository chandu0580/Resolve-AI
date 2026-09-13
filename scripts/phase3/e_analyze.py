"""Phase 3-E: classifier failure analysis on golden (per-query records from b_train_eval) + latency summary.
Writes artifacts/intelligence/failure_candidates.json and prints category counts and examples for the hand-written
failure_analysis.md.  python scripts/phase3/e_analyze.py
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from resolveai.evaluation import load_golden

OUT = Path("artifacts/intelligence")


def main() -> None:
    recs = [json.loads(line) for line in (OUT / "per_query_golden_intent.jsonl").read_text(encoding="utf-8").splitlines()]
    g = load_golden().set_index("gid")
    wrong = [r for r in recs if not r["correctA"]]
    conf = Counter((r["gold"], r["predA"]) for r in wrong)
    cats = {
        "short_message": [r for r in wrong if r["slices"]["short"]],
        "multi_turn_short_reply": [r for r in wrong if r["short_reply"] and r["slices"]["multi_turn"]],
        "gold_other_missed": [r for r in wrong if r["gold"] == "other"],
        "gold_general_complaint": [r for r in wrong if r["gold"] == "general_complaint"],
        "pred_general_complaint": [r for r in wrong if r["predA"] == "general_complaint"],
        "keyboard_overpredicted": [r for r in wrong if r["predA"] == "keyboard_text_bug"],
        "app_vs_device_scope": [r for r in wrong if {r["gold"], r["predA"]} == {"apps_services", "performance_crash"}],
        "data_loss_confusions": [r for r in wrong if "data_loss_sync" in (r["gold"], r["predA"])],
        "high_confidence_wrong": [r for r in wrong if r["confA"] >= 0.75],
        "low_confidence_wrong": [r for r in wrong if r["confA"] < 0.40],
        "multi_intent_gold": [r for r in wrong if r["slices"]["multi_intent"]],
        "insufficient_context_gold": [r for r in wrong if r["slices"]["insufficient_context"]],
        "taxonomy_gap_gold": [r for r in wrong if r["slices"]["taxonomy_gap"]],
    }
    print(f"golden errors (message-only): {len(wrong)}/{len(recs)}")
    print("top confusions:", conf.most_common(10))
    for k, v in cats.items():
        print(f"\n== {k}: {len(v)}")
        for r in v[:4]:
            q = g.loc[r["gid"]]
            print(f"  {r['gid']} gold={r['gold']} pred={r['predA']} conf={r['confA']:.2f} ctx_helped={r['correctB'] and not r['correctA']} | {q.customer_message[:150]}")
    (OUT / "failure_candidates.json").write_text(json.dumps({"n_wrong": len(wrong), "top_confusions": [[list(k), n] for k, n in conf.most_common(15)],
                                                            "categories": {k: [r["gid"] for r in v] for k, v in cats.items()}, "records": wrong}, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
