"""Phase 10-A: the targeted `needs_private_info` risk candidate, measured on DEV only (the golden set is never read here).

  python -u scripts/final/a_private_info_experiment.py [--workers 4]

Pre-registered in artifacts/final/risk_experiment/PREREGISTRATION.md before this script produced any result; the file's SHA-256 is
recorded in the report, so a later edit is detectable.

Why this candidate: in Phase 9 the largest source of unnecessary handoffs on the AI-labelled dev rows was the model raising
`needs_private_info` with no deterministic private-info signal (17 of 41). Phase 9's V2 corroborated three flags at once and lost 22
true escalations, almost all through `repeat_contact`; this candidate corroborates ONLY `needs_private_info`.

Protocol:
  rows    the same 240 DEV rows as Phase 9 (holdout, golden excluded and asserted, seed 51), through the unchanged production
          understanding pipeline (scripts/phase9/a_risk_dev_experiment.py: understand, model_opinion) and the same response cache
  V0      production: deterministic rules OR risk-flags-v2 model flags
  P10     V0, except that a model-raised needs_private_info counts only when the deterministic private-info rule also fired
          (AgentConfig.risk_corroborate = ("needs_private_info",)); same prompt, same model call
  checks  V0 must reproduce the stored Phase 9 V0 outcome; every row where P10 and V0 differ on handoff must carry a Phase 9 label,
          otherwise the script stops without a decision (no label is created here)
Labels: data/dev/phase9_risk_labels.json (AI annotator under ANNOTATION_GUIDE v1.1, NOT human). No human-labelled dev set exists.
Acceptance rule: the Phase 9 rule, unchanged (PREREGISTRATION.md).
Writes artifacts/final/risk_experiment/runs.jsonl, report.json, report.md and decision.json.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import hashlib
import importlib.util
import json
import math
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from resolveai.agent import risk, second_opinion  # noqa: E402
from resolveai.intelligence.classifier import IntentService  # noqa: E402
from resolveai.llm import DiskCache, LLMClient, OpenAICompatibleProvider  # noqa: E402
from resolveai.policy import escalation as policy  # noqa: E402
from resolveai.retrieval import KnowledgeBase, Retriever, RetrieverConfig  # noqa: E402
from resolveai.retrieval.dense import Embedder  # noqa: E402

OUT = ROOT / "artifacts" / "final" / "risk_experiment"
PREREG = OUT / "PREREGISTRATION.md"
P9_RUNS = ROOT / "artifacts" / "phase9" / "risk" / "dev_runs.jsonl"
P9_REPORT = ROOT / "artifacts" / "phase9" / "risk" / "risk_dev_report.json"
LABELS = ROOT / "data" / "dev" / "phase9_risk_labels.json"
P9_VARIANTS = ("V0", "V1", "V2", "V3", "V4")
CANDIDATE = ("needs_private_info",)
PROTECTED_REASONS = {"safety", "legal_media", "private_info"}


def _phase9_module():
    spec = importlib.util.spec_from_file_location("phase9_risk_experiment", ROOT / "scripts" / "phase9" / "a_risk_dev_experiment.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


P9 = _phase9_module()


def flag_names(flags) -> list[str]:
    return sorted(k for k, val in flags.model_dump().items() if val is True and k != "is_actionable")


def run_row(row, parts: dict) -> dict:
    u = P9.understand(row, parts["intents"], parts["embedder"], parts["retriever"], parts["llm"], parts["so_policy"])
    b, ctx, intent, ev = u["bundle"], u["ctx"], u["intent"], u["evidence"]
    rules = risk.extract_rules(b)
    conflicting = ev.sufficiency_reason == "conflicting_evidence"
    guaranteed = rules.any_hard_block() or policy.hard_handoff_guaranteed(intent, rules, ctx, ev, b.current)
    op = None if guaranteed else P9.model_opinion(parts["llm"], b, "compact")
    rules_c = rules.model_copy(update={"conflicting_evidence": conflicting})
    decisions = {}
    for variant, corroborate in (("V0", frozenset()), ("P10", frozenset(CANDIDATE))):
        if op is None or op["status"] != "ok":
            flags = rules_c
        else:
            flags = risk.merge(rules, set(op["raised"]), op["actionable"], op["summary"], b, conflicting, corroborate=corroborate)
        e = policy.decide(intent, flags, ctx, ev, None, llm_available=True, message=b.current)
        decisions[variant] = {"outcome": P9.outcome(e), "reason_code": e.reason_code, "rule": e.rule, "flags": flag_names(flags)}
    return {"customer_tweet_id": str(row.customer_tweet_id), "intent": intent.intent, "evidence_level": ev.sufficiency_level, "rules_flags": flag_names(rules),
            "model_skipped_hard_handoff": guaranteed, "model_status": None if op is None else op["status"], "model_raised": [] if op is None else op["raised"],
            "decisions": decisions}


def wilson(k: int, n: int, z: float = 1.96) -> list[float] | None:
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(c - h, 3), round(c + h, 3)]


def score(decision_of, ids: list[str], gold: dict) -> dict:
    """Handoff vs should_escalate on the labelled rows (a clarification is not an escalation, as in the golden evaluation)."""
    tp = fp = fn = tn = 0
    fn_reasons: Counter = Counter()
    for i in ids:
        pred = decision_of(i)["outcome"] == "HANDOFF"
        g = gold[i]
        if pred and g["should_escalate"]:
            tp += 1
        elif pred:
            fp += 1
        elif g["should_escalate"]:
            fn += 1
            fn_reasons[g["reason"]] += 1
        else:
            tn += 1
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = 2 * precision * recall / (precision + recall) if precision and recall else 0.0
    auto_on_escalate = sum(1 for i in ids if decision_of(i)["outcome"] == "AUTO_CANDIDATE" and gold[i]["should_escalate"])
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": None if precision is None else round(precision, 3), "recall": None if recall is None else round(recall, 3),
            "f1": round(f1, 3), "fn_reasons": dict(fn_reasons), "auto_candidates_on_should_escalate_rows": auto_on_escalate}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    if not PREREG.exists():
        raise SystemExit(f"{PREREG} is missing: pre-register the candidate and the acceptance rule before running")
    prereg_sha = hashlib.sha256(PREREG.read_bytes()).hexdigest()
    stored = {r["customer_tweet_id"]: r for r in (json.loads(line) for line in P9_RUNS.read_text(encoding="utf-8").splitlines() if line.strip())}
    labels = json.loads(LABELS.read_text(encoding="utf-8"))
    gold = labels["labels"]
    t0 = time.perf_counter()
    rows = P9.dev_rows(240)
    if set(rows.customer_tweet_id.astype(str)) != set(stored):
        raise SystemExit("the DEV sample does not match the Phase 9 sample; refusing to compare")
    kb = KnowledgeBase.build(dense_models=[RetrieverConfig().model], with_bm25=False)
    llm = LLMClient(provider=OpenAICompatibleProvider(), cache=DiskCache())
    parts = {"retriever": Retriever(kb, RetrieverConfig()), "intents": IntentService(), "embedder": Embedder(RetrieverConfig().model), "llm": llm,
             "so_policy": second_opinion.load_policy()}
    print(f"loaded in {time.perf_counter() - t0:.0f}s; running {len(rows)} dev rows", flush=True)
    records = []
    with cf.ThreadPoolExecutor(max_workers=a.workers) as pool:
        futures = [pool.submit(run_row, r, parts) for r in rows.itertuples()]
        for k, fut in enumerate(cf.as_completed(futures), start=1):
            records.append(fut.result())
            if k % 40 == 0:
                print(f"  {k}/{len(rows)} ({time.perf_counter() - t0:.0f}s)", flush=True)
    records.sort(key=lambda r: r["customer_tweet_id"])
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "runs.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")
    by_id = {r["customer_tweet_id"]: r for r in records}

    def handoff(i, variant):
        return by_id[i]["decisions"][variant]["outcome"] == "HANDOFF"

    # validity check 1: the recomputed production decision reproduces Phase 9
    mismatch = [{"id": i, "phase9": f"{stored[i]['decisions']['V0']['outcome']}/{stored[i]['decisions']['V0']['reason_code']}",
                 "now": f"{r['decisions']['V0']['outcome']}/{r['decisions']['V0']['reason_code']}"}
                for i, r in by_id.items() if (r["decisions"]["V0"]["outcome"], r["decisions"]["V0"]["reason_code"]) != (stored[i]["decisions"]["V0"]["outcome"], stored[i]["decisions"]["V0"]["reason_code"])]
    # validity check 2: every changed handoff decision is labelled
    labelled = sorted(gold)
    changed = sorted(i for i in by_id if handoff(i, "V0") != handoff(i, "P10"))
    unlabelled = [i for i in changed if i not in gold]
    calls = [r for r in records if r["model_status"] is not None]
    fallback_rate = round(sum(r["model_status"] != "ok" for r in calls) / max(1, len(calls)), 4)
    raised_npi = [r for r in calls if "needs_private_info" in r["model_raised"]]
    report = {"preregistration_sha256": prereg_sha, "n_dev_rows": len(records), "n_labelled_rows": len(labelled), "labels_provenance": labels.get("provenance"),
              "live_model_calls": llm.usage.live_calls, "cache_hits": llm.usage.cache_hits, "wall_seconds": round(time.perf_counter() - t0, 1),
              "validity": {"v0_reproduces_phase9": not mismatch, "v0_mismatches": mismatch, "changed_handoff_rows": changed, "unlabelled_changed_rows": unlabelled},
              "model": {"calls": len(calls), "fallback_rate": fallback_rate, "rows_model_raised_needs_private_info": len(raised_npi),
                        "of_which_rule_corroborated": sum(1 for r in raised_npi if "needs_private_info" in r["rules_flags"])},
              "outcomes_240": {v: dict(Counter(r["decisions"][v]["outcome"] for r in records)) for v in ("V0", "P10")}}
    if unlabelled:
        report["status"] = "blocked: rows changed by the candidate have no label; no decision made and no label created"
        (OUT / "report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
        print(json.dumps(report, indent=1))
        return 2

    scores = {v: score(lambda i, v=v: by_id[i]["decisions"][v], labelled, gold) for v in ("V0", "P10")}
    # Phase 9's stored variants on the same labelled rows, for context (their own run, not recomputed)
    p9_scores = {v: score(lambda i, v=v: stored[i]["decisions"][v], labelled, gold) for v in P9_VARIANTS}
    new_fn = [i for i in changed if gold[i]["should_escalate"] and handoff(i, "V0") and not handoff(i, "P10")]
    new_fn_protected = [i for i in new_fn if gold[i]["reason"] in PROTECTED_REASONS]
    removed = [i for i in changed if handoff(i, "V0")]
    added = [i for i in changed if handoff(i, "P10")]
    removed_correctly = sum(1 for i in removed if not gold[i]["should_escalate"])
    checks = {"no_new_protected_misses": not new_fn_protected, "at_most_one_new_miss": len(new_fn) <= 1,
              "at_least_3_fewer_unnecessary_handoffs": scores["V0"]["fp"] - scores["P10"]["fp"] >= 3,
              "fallback_within_5pp": True}   # both variants read the same model call, so their fallback rates are identical
    accepted = all(checks.values())
    report.update({
        "status": "complete", "scores_on_labelled_rows": scores, "phase9_variants_on_labelled_rows": p9_scores,
        "candidate": {"definition": "V0 with AgentConfig.risk_corroborate = ('needs_private_info',)", "delta_fp": scores["P10"]["fp"] - scores["V0"]["fp"],
                      "delta_fn": scores["P10"]["fn"] - scores["V0"]["fn"], "new_misses": new_fn, "new_protected_misses": new_fn_protected,
                      "handoffs_removed": len(removed), "removed_correctly": removed_correctly, "removed_correctly_wilson95": wilson(removed_correctly, len(removed)),
                      "handoffs_added": len(added), "removed_handoffs_now": dict(Counter(by_id[i]["decisions"]["P10"]["outcome"] for i in removed)),
                      "checks": checks, "accepted": accepted},
        "changed_rows": [{"id": i, "v0": f"{by_id[i]['decisions']['V0']['outcome']}/{by_id[i]['decisions']['V0']['reason_code']}",
                          "p10": f"{by_id[i]['decisions']['P10']['outcome']}/{by_id[i]['decisions']['P10']['reason_code']}",
                          "gold_should_escalate": gold[i]["should_escalate"], "gold_reason": gold[i]["reason"], "label_note": gold[i].get("note", ""),
                          "model_flags": by_id[i]["model_raised"], "message": stored[i]["message"][:120]} for i in changed],
        "acceptance_rule": "Phase 9 rule, unchanged: no new protected (safety/legal_media/private_info) miss; at most one new miss; >= 3 fewer unnecessary handoffs; fallback within 5 pp",
    })
    decision = {"candidate": "P10: model-raised needs_private_info counts only with the deterministic private-info rule", "accepted": accepted,
                "risk_corroborate": list(CANDIDATE) if accepted else [], "risk_schema": "compact",
                "decision": "accept and enable in the release configuration" if accepted else "reject; production risk extraction (V0) is kept unchanged",
                "evidence": ["artifacts/final/risk_experiment/report.md", "artifacts/final/risk_experiment/report.json", "artifacts/final/risk_experiment/runs.jsonl",
                             "data/dev/phase9_risk_labels.json"],
                "labels": "AI annotator, not human", "preregistration_sha256": prereg_sha, "golden_touched": False}
    (OUT / "report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    (OUT / "decision.json").write_text(json.dumps(decision, indent=1), encoding="utf-8")

    def fmt(s):
        return f"| {s['tp']} | {s['fp']} | {s['fn']} | {s['precision']} | {s['recall']} | {s['f1']} | {s['fn_reasons'] or '-'} |"

    c = report["candidate"]
    L = ["# Phase 10 risk experiment: targeted `needs_private_info` corroboration (DEV only)", "",
         f"Pre-registration: `PREREGISTRATION.md` (sha256 `{prereg_sha[:16]}…`). 240 DEV rows (holdout, golden excluded); scores on the {len(labelled)} rows labelled "
         "by an **AI annotator, not a human**. Precision, recall and F1 are on that labelled subset only, not estimates for the dev population.", "",
         f"Validity: V0 reproduces Phase 9 on every row: **{'yes' if not mismatch else 'no (' + str(len(mismatch)) + ' rows)'}**; rows whose handoff decision changed: "
         f"{len(changed)}, all labelled: **{'yes' if not unlabelled else 'no'}**; live model calls: {llm.usage.live_calls} (cache hits {llm.usage.cache_hits}).", "",
         "| variant | TP | FP (unnecessary handoffs) | FN (missed) | precision | recall | F1 | missed by gold reason |", "|---|---|---|---|---|---|---|---|",
         "| V0 production (this run) " + fmt(scores["V0"]), "| **P10 candidate** " + fmt(scores["P10"])]
    L += [f"| Phase 9 {v} (stored run) " + fmt(p9_scores[v]) for v in P9_VARIANTS[1:]]
    L += ["", "Outcomes over all 240 rows: " + "; ".join(f"{v} {report['outcomes_240'][v]}" for v in ("V0", "P10")), "",
          f"Model-raised `needs_private_info`: {report['model']['rows_model_raised_needs_private_info']} of {len(calls)} model calls, "
          f"{report['model']['of_which_rule_corroborated']} corroborated by the deterministic rule. Model fallback rate {fallback_rate}.", "",
          "| check | result |", "|---|---|"] + [f"| {k} | {'pass' if ok else 'FAIL'} |" for k, ok in checks.items()]
    L += ["", f"Δ unnecessary handoffs {c['delta_fp']:+d}; Δ missed escalations {c['delta_fn']:+d}; handoffs removed {c['handoffs_removed']} "
          f"({c['removed_correctly']} correctly, Wilson 95% {c['removed_correctly_wilson95']}); removed handoffs now {c['removed_handoffs_now']}; new misses {c['new_misses'] or 'none'}.", "",
          f"**Decision: {decision['decision']}.**", "", "## Rows whose handoff decision changed", "",
          "| id | V0 | P10 | gold should_escalate | gold reason | model flags | message (redacted) |", "|---|---|---|---|---|---|---|"]
    L += [f"| {r['id']} | {r['v0']} | {r['p10']} | {r['gold_should_escalate']} | {r['gold_reason']} | {', '.join(r['model_flags'])} | {r['message'].replace('|', '/')} |" for r in report["changed_rows"]]
    (OUT / "report.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())
