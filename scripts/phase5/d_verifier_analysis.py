"""Phase 5-D: verifier block analysis on the DEV drafts from c_draft_experiment.py.
Step 1 (`--review`): writes verifier_review.md listing every BLOCKED draft (both arms) with the cited evidence and the
verifier's issues, plus a sample of PASSED drafts, for hand labelling.
Step 2 (default): reads artifacts/resolution/verifier_labels.json  {"<case_id>:<arm>": "TRUE_BLOCK|FALSE_BLOCK|UNCERTAIN|TRUE_PASS|FALSE_PASS"}
and writes verifier_analysis.json/.md. Labels are by an AI annotator (stated in the report), not a human study.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

OUT = Path("artifacts/resolution")


def load():
    return [json.loads(x) for x in (OUT / "draft_experiment.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]


def review() -> None:
    recs = load()
    L = ["# Verifier review sheet (DEV drafts)", ""]
    passed = 0
    for r in recs:
        for arm in ("A_v1", "B_v2"):
            d = r[arm]
            blocked = not d["verified"]
            if not blocked and passed >= 12:
                continue
            if not blocked:
                passed += 1
            L += [f"## {r['id']}:{arm}  [{'BLOCKED' if blocked else 'passed'}]  intent={r['intent']} level={r['level']}", f"- customer: {r['message']}", f"- draft: {d.get('text')}", f"- refs: {d.get('refs')}  issues: {d.get('issues')}"]
            by = {e["id"]: e for e in r["evidence"]}
            for ref in d.get("refs") or []:
                if ref in by:
                    L.append(f"  - cited [{by[ref]['action']}] {by[ref]['reply']}")
            L.append("")
    (OUT / "verifier_review.md").write_text("\n".join(L), encoding="utf-8")
    print(f"wrote {OUT / 'verifier_review.md'}: {sum(1 for r in recs for a in ('A_v1', 'B_v2') if not r[a]['verified'])} blocked drafts")


def summarize() -> None:
    recs = load()
    labels = json.loads((OUT / "verifier_labels.json").read_text(encoding="utf-8")).get("labels", {})
    rows = []
    for r in recs:
        for arm in ("A_v1", "B_v2"):
            d = r[arm]
            key = f"{r['id']}:{arm}"
            rows.append({"key": key, "arm": arm, "verified": d["verified"], "blocking": d.get("blocking", []), "label": labels.get(key)})
    blocked = [x for x in rows if not x["verified"]]
    labelled = [x for x in blocked if x["label"]]
    c = Counter(x["label"] for x in labelled)
    by_check = {}
    for x in labelled:
        for b in x["blocking"]:
            by_check.setdefault(b, Counter())[x["label"]] += 1
    passed_l = [x for x in rows if x["verified"] and x["label"]]
    out = {"n_drafts": len(rows), "n_blocked": len(blocked), "n_blocked_labelled": len(labelled), "labels": dict(c),
           "true_block_rate": round(c["TRUE_BLOCK"] / len(labelled), 3) if labelled else None, "false_block_rate": round(c["FALSE_BLOCK"] / len(labelled), 3) if labelled else None,
           "uncertain_rate": round(c["UNCERTAIN"] / len(labelled), 3) if labelled else None, "by_blocking_check": {k: dict(v) for k, v in by_check.items()},
           "by_arm": {a: dict(Counter(x["label"] for x in labelled if x["arm"] == a)) for a in ("A_v1", "B_v2")},
           "passed_sample": {"n": len(passed_l), "labels": dict(Counter(x["label"] for x in passed_l))},
           "annotator": "AI annotator (Claude) reading draft + cited evidence; not a human study"}
    (OUT / "verifier_analysis.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    L = ["# Verifier block analysis (Phase 5-D, DEV drafts)", "", f"{out['n_blocked']} of {out['n_drafts']} drafts were blocked; {out['n_blocked_labelled']} labelled by an AI annotator.", "",
         "| label | n |", "|---|---|"] + [f"| {k} | {v} |" for k, v in out["labels"].items()]
    L += ["", f"TRUE_BLOCK rate {out['true_block_rate']}, FALSE_BLOCK rate {out['false_block_rate']}, UNCERTAIN {out['uncertain_rate']}.", "", "By blocking check: `" + json.dumps(out["by_blocking_check"]) + "`",
          "By arm: `" + json.dumps(out["by_arm"]) + "`", f"Passed-draft sample: `{json.dumps(out['passed_sample'])}`"]
    (OUT / "verifier_analysis.md").write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    review() if "--review" in sys.argv else summarize()
