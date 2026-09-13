"""Phase 10-B: the final metrics table, ResolveAI 1.0.0 vs the baselines and vs Phase 9, from EXISTING run records (nothing is re-run).

  python scripts/final/b_final_metrics.py

Inputs (read only):
  artifacts/final/evaluation/runs/final_release.jsonl        ResolveAI 1.0.0: the single golden run of the release configuration
  artifacts/final/evaluation/judge_final_release.jsonl       frozen rubric-v1 GLM-5.2 judge on that run
  artifacts/phase9/evaluation/runs/phase9_final.jsonl        the single Phase 9 final run (same pipeline, no needs_private_info corroboration)
  artifacts/phase9/evaluation/judge_phase9_final.jsonl
  artifacts/evaluation/runs/B2_direct_llm.jsonl, B1_simple_ml.jsonl   frozen Phase 6 baselines; artifacts/evaluation/judge_results.jsonl
  artifacts/evaluation/retrieval_report.json                 frozen retrieval measurements (Phases 2 and 5)
  data/human_eval/human_scoring_packet.csv                   human ratings (judge-human agreement only if rated)
The golden hash is verified by load_golden(). Differences are ResolveAI minus the comparison system with a 95% PAIRED bootstrap over the
same golden rows (1,000 resamples, seed 42); judge differences pair the rows both judge calls parsed. Every row names its evaluation source
(golden labels, LLM judge, run records) so evidence kinds are never mixed; AI-labelled dev results live in artifacts/final/risk_experiment/.
Writes artifacts/final/final_metrics.json and artifacts/final/final_metrics.md.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from resolveai.evaluation import load_golden  # noqa: E402
from resolveai.evaluation.bootstrap import bootstrap_ci, paired_bootstrap  # noqa: E402
from resolveai.evaluation.metrics import escalation_metrics, intent_metrics, is_safe_autonomous  # noqa: E402
from resolveai.evaluation.records import read_records  # noqa: E402
from resolveai.evaluation.reporting import gold_map  # noqa: E402

OUT = ROOT / "artifacts" / "final"
REL = OUT / "evaluation"
P9 = ROOT / "artifacts" / "phase9" / "evaluation"
P6 = ROOT / "artifacts" / "evaluation"
SEED, N_BOOT = 42, 1000
JUDGE_MODEL = "glm-5.2"
COMPARISONS = (("B2_direct_llm", "Direct-LLM baseline (B2: one GLM-5.2 prompt with the taxonomy, escalation criteria and the full thread)"),
               ("B1_simple_ml", "Simple-ML baseline (B1: TF-IDF+LR, nearest-neighbour historical reply, the same deterministic risk rules)"),
               ("phase9_final", "Phase 9 final run (same pipeline without the needs_private_info corroboration)"))


def _acc(rows):
    return float(np.mean([g == p for g, p in rows])) if rows else 0.0


def _macro_f1(rows):
    return intent_metrics([g for g, _ in rows], [p for _, p in rows])["macro_f1"]


def _esc(key):
    def stat(rows):
        return escalation_metrics([g for g, _ in rows], [p for _, p in rows])[key]
    return stat


def _mean(rows):
    return float(np.mean(rows)) if rows else 0.0


def _load_judge(path: Path, system: str | None = None) -> dict:
    out = {}
    for j in (json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()):
        if j.get("judge_model", JUDGE_MODEL) == JUDGE_MODEL and (system is None or j["system"] == system):
            out[j["gid"]] = j
    return out


def main() -> int:
    gold = load_golden()
    gm = gold_map(gold)
    systems = {"resolveai": read_records(REL / "runs" / "final_release.jsonl"), "phase9_final": read_records(P9 / "runs" / "phase9_final.jsonl"),
               "B2_direct_llm": read_records(P6 / "runs" / "B2_direct_llm.jsonl"), "B1_simple_ml": read_records(P6 / "runs" / "B1_simple_ml.jsonl")}
    by = {s: {r.gid: r for r in recs} for s, recs in systems.items()}
    gids = sorted(set.intersection(*(set(m) for m in by.values())))
    assert len(gids) == len(gold) == 197, "every system must cover the full golden set"
    judge = {"resolveai": _load_judge(REL / "judge_final_release.jsonl"), "phase9_final": _load_judge(P9 / "judge_phase9_final.jsonl"),
             "B2_direct_llm": _load_judge(P6 / "judge_results.jsonl", "B2_direct_llm"), "B1_simple_ml": _load_judge(P6 / "judge_results.jsonl", "B1_simple_ml")}

    def row_values(system: str, metric: str) -> list:
        m = by[system]
        if metric in ("intent_accuracy", "intent_macro_f1"):
            return [(gm[g]["intent"], m[g].intent_pred) for g in gids]
        if metric.startswith("escalation_"):
            return [(gm[g]["should_escalate"], m[g].escalate_pred) for g in gids]
        if metric == "autonomous_rate":
            return [m[g].action == "AUTO_HANDLE" for g in gids]
        if metric == "safe_autonomous_rate":
            return [is_safe_autonomous(m[g], gm[g]["should_escalate"], gm[g]["intent"])[0] for g in gids]
        if metric == "unsafe_autonomous_count":
            return [m[g].action == "AUTO_HANDLE" and gm[g]["should_escalate"] for g in gids]
        if metric == "unnecessary_handoffs":
            return [m[g].escalate_pred and not gm[g]["should_escalate"] for g in gids]
        if metric == "llm_calls_per_message":
            return [m[g].llm_calls for g in gids]
        if metric == "cost_usd_per_message":
            return [m[g].cost_usd for g in gids]
        raise KeyError(metric)

    stats = {"intent_accuracy": _acc, "intent_macro_f1": _macro_f1, "escalation_precision": _esc("precision"), "escalation_recall": _esc("recall"),
             "escalation_f1": _esc("f1"), "autonomous_rate": _mean, "safe_autonomous_rate": _mean, "unsafe_autonomous_count": lambda rows: float(sum(rows)),
             "unnecessary_handoffs": lambda rows: float(sum(rows)), "llm_calls_per_message": _mean, "cost_usd_per_message": _mean}
    table = {}
    for base, _ in COMPARISONS:
        rows = {}
        for metric, stat in stats.items():
            ra, rb = row_values("resolveai", metric), row_values(base, metric)
            rows[metric] = {"resolveai": round(float(stat(ra)), 4), "baseline": round(float(stat(rb)), 4),
                            "resolveai_ci": bootstrap_ci(ra, stat, n_boot=N_BOOT, seed=SEED), "difference": paired_bootstrap(rb, ra, stat, n_boot=N_BOOT, seed=SEED)}
        ja, jb = judge["resolveai"], judge[base]
        for dim in ("groundedness", "hallucination", "policy_violation"):
            parsed_a = [g for g in gids if g in ja and not ja[g].get("failed")]
            parsed_b = [g for g in gids if g in jb and not jb[g].get("failed")]
            both = [g for g in parsed_a if g in set(parsed_b)]
            va = [float(ja[g][dim]) for g in parsed_a]
            rows[f"judge_{dim}"] = {"resolveai": round(_mean(va), 4), "baseline": round(_mean([float(jb[g][dim]) for g in parsed_b]), 4), "n_resolveai": len(parsed_a),
                                    "n_baseline": len(parsed_b), "n_paired": len(both), "resolveai_ci": bootstrap_ci(va, _mean, n_boot=N_BOOT, seed=SEED),
                                    "difference": paired_bootstrap([float(jb[g][dim]) for g in both], [float(ja[g][dim]) for g in both], _mean, n_boot=N_BOOT, seed=SEED)}
        rows["latency_p50_ms_as_run"] = {"resolveai": round(float(np.percentile([by["resolveai"][g].latency_ms for g in gids], 50)), 1),
                                         "baseline": round(float(np.percentile([by[base][g].latency_ms for g in gids], 50)), 1), "difference": None}
        table[base] = rows
    changed = []
    for g in gids:
        a, b = by["phase9_final"][g], by["resolveai"][g]
        if (a.action, a.reason_code) != (b.action, b.reason_code):
            changed.append({"gid": g, "phase9_final": f"{a.action}/{a.reason_code}", "release": f"{b.action}/{b.reason_code}", "gold_should_escalate": gm[g]["should_escalate"],
                            "gold_reason": gm[g]["escalation_reason"], "gold_intent": gm[g]["intent"], "safe_autonomous_now": is_safe_autonomous(b, gm[g]["should_escalate"], gm[g]["intent"])[0],
                            "message": b.message[:120]})
    fn = [{"gid": g, "gold_reason": gm[g]["escalation_reason"], "action": by["resolveai"][g].action, "reason_code": by["resolveai"][g].reason_code, "message": by["resolveai"][g].message[:140]}
          for g in gids if gm[g]["should_escalate"] and not by["resolveai"][g].escalate_pred]
    auto = [{"gid": g, "kind": by["resolveai"][g].response_kind, "safe": is_safe_autonomous(by["resolveai"][g], gm[g]["should_escalate"], gm[g]["intent"])[1]}
            for g in gids if by["resolveai"][g].action == "AUTO_HANDLE"]
    retrieval = json.loads((P6 / "retrieval_report.json").read_text(encoding="utf-8"))["same_resolution_recall"]
    packet = pd.read_csv(ROOT / "data" / "human_eval" / "human_scoring_packet.csv", keep_default_na=False)
    human_cols = [c for c in packet.columns if c.startswith("human_") and c != "human_notes"]
    rated = int((packet[human_cols].astype(str).apply(lambda s: s.str.strip() != "")).all(axis=1).sum())
    meta = json.loads((REL / "runs" / "final_release.meta.json").read_text(encoding="utf-8"))
    judge_failures = sum(1 for j in judge["resolveai"].values() if j.get("failed"))
    out = {"golden_sha256": json.loads((ROOT / "data/golden/golden_freeze_manifest.json").read_text())["sha256"], "n_golden": len(gids), "n_boot": N_BOOT, "seed": SEED,
           "resolveai_run": {"file": "artifacts/final/evaluation/runs/final_release.jsonl", "pipeline_version": meta["pipeline_version"], "config_hash": meta["config_hash"],
                             "live_calls": meta["live_calls"], "failed": meta["failed"], "judge_failures": judge_failures},
           "table": table, "decision_changes_vs_phase9_final": changed, "missed_escalations": fn, "autonomous_replies": auto,
           "evidence_levels": {k: int(v) for k, v in pd.Series([r.evidence_level for r in systems["resolveai"]]).value_counts().items()},
           "retrieval_same_resolution_recall_at_5": {"resolveai_phase5_pair_rerank_gate_v3": retrieval["phase5_pair_rerank_gate_v3"]["recall@5"],
                                                     "phase2_customer_index": retrieval["phase2_customer_index_gate_v2"]["recall@5"], "n_ref": retrieval["phase5_pair_rerank_gate_v3"]["n_ref"]},
           "human_evaluation": {"packet_rows": int(len(packet)), "fully_rated_rows": rated, "status": "NOT COMPLETED" if rated == 0 else "PARTIAL" if rated < len(packet) else "COMPLETE"}}
    (OUT / "final_metrics.json").write_text(json.dumps(out, indent=1), encoding="utf-8")

    def ci(d, digits=3):
        return f"[{d['ci_low']:.{digits}f}, {d['ci_high']:.{digits}f}]"

    def diff(d, digits=3):
        return f"{d['difference']:+.{digits}f} [{d['ci_low']:+.{digits}f}, {d['ci_high']:+.{digits}f}]" + (" *" if d["interval_excludes_zero"] else "")

    labels = {"intent_accuracy": ("Intent accuracy", "golden labels", "adjudicated from two passes, annotator B was an AI; smallest class 7 rows"),
              "intent_macro_f1": ("Intent macro-F1", "golden labels", "equal weight to 7-row and 38-row classes"),
              "escalation_precision": ("Escalation precision", "golden labels", "HUMAN_HANDOFF vs should_escalate; a clarification counts as not escalated"),
              "escalation_recall": ("Escalation recall", "golden labels", "37 positives: one row moves it 2.7 points"),
              "escalation_f1": ("Escalation F1", "golden labels", "37 positives"),
              "unnecessary_handoffs": ("Unnecessary handoffs (count)", "golden labels", "handoff on a row the annotators did not mark for escalation"),
              "autonomous_rate": ("Autonomous rate (AUTO_HANDLE)", "golden run", "answering more is not answering safely"),
              "safe_autonomous_rate": ("Safe autonomous rate", "golden labels + project definition", "strict definition written by the project; a handful of events"),
              "unsafe_autonomous_count": ("Unsafe autonomous replies (count)", "golden labels", "AUTO_HANDLE on a should-escalate row"),
              "judge_groundedness": ("Groundedness (1-5)", "LLM judge, GLM-5.2 rubric-v1", "NOT human-validated; same model family as the drafter and B2"),
              "judge_hallucination": ("Hallucination rate", "LLM judge, GLM-5.2 rubric-v1", "NOT human-validated; most ResolveAI flags fall on clarification wording"),
              "judge_policy_violation": ("Policy-violation rate", "LLM judge, GLM-5.2 rubric-v1", "NOT human-validated"),
              "llm_calls_per_message": ("LLM calls per message", "golden run records", "ResolveAI's run was cache-served; calls counted as made"),
              "cost_usd_per_message": ("Est. cost per message (USD)", "golden run records, list price", "tokens the calls used when live; real billing unknown")}
    L = ["# Final metrics (golden set, n = 197)", "",
         f"Golden sha256 `{out['golden_sha256'][:16]}…`. **ResolveAI = release 1.0.0** (`final_release`, {meta['pipeline_version']}, config `{meta['config_hash']}`), "
         f"run once on the golden set after the DEV decision was frozen; cache-served ({meta['live_calls']} live calls); judge failures {judge_failures}. "
         "Difference = ResolveAI minus the comparison system, 95% paired bootstrap (1,000 resamples, seed 42); `*` = the interval excludes zero. Nothing here was re-run.", ""]
    for base, title in COMPARISONS:
        rows = table[base]
        L += [f"## vs {title}", "", "| Metric | ResolveAI [95% CI] | Comparison | Difference [95% CI] | Evaluation source | Limitations |", "|---|---|---|---|---|---|"]
        for key, (name, source, limit) in labels.items():
            r = rows[key]
            digits = 4 if key == "cost_usd_per_message" else 3
            counts = key in ("unsafe_autonomous_count", "unnecessary_handoffs")
            ra = f"{int(r['resolveai'])}" if counts else f"{r['resolveai']:.{digits}f} {ci(r['resolveai_ci'], digits)}"
            rb = f"{int(r['baseline'])}" if counts else f"{r['baseline']:.{digits}f}"
            dd = f"{r['difference']['difference']:+.0f} [{r['difference']['ci_low']:+.0f}, {r['difference']['ci_high']:+.0f}]" + (" *" if r["difference"]["interval_excludes_zero"] else "") if counts else diff(r["difference"], digits)
            extra = f" (n={r['n_resolveai']} / {r['n_baseline']}; paired {r['n_paired']})" if key.startswith("judge_") else ""
            L.append(f"| {name} | {ra}{extra} | {rb} | {dd} | {source} | {limit} |")
        lat = rows["latency_p50_ms_as_run"]
        L += [f"| p50 latency as run (ms) | {lat['resolveai']} | {lat['baseline']} | n/a | golden run records | not comparable across cache-served and live runs; live latency is in `performance/perf_final.md` |", ""]
    rr = out["retrieval_same_resolution_recall_at_5"]
    L += ["## Other rows", "", "| Metric | ResolveAI | Comparison | Difference | Evaluation source | Limitations |", "|---|---|---|---|---|---|",
          f"| Retrieval same-resolution recall@5 | {rr['resolveai_phase5_pair_rerank_gate_v3']:.3f} (pair index + resolution rerank) | {rr['phase2_customer_index']:.3f} (Phase 2 customer index) | "
          f"{rr['resolveai_phase5_pair_rerank_gate_v3'] - rr['phase2_customer_index']:+.3f} (no interval: per-row results not stored) | golden, label-free TF-IDF protocol, n = {rr['n_ref']} scorable rows | "
          "the reranker trades this for resolution-bearing@1 0.18 → 0.76; unchanged since Phase 5 |",
          f"| Evidence levels (INSUFFICIENT / WEAK / STRONG) | {out['evidence_levels'].get('INSUFFICIENT', 0)} / {out['evidence_levels'].get('WEAK', 0)} / {out['evidence_levels'].get('STRONG', 0)} | — | — | golden run | retrieval ceiling: almost nothing reaches STRONG |",
          f"| Judge-human agreement | {'not available: no human ratings' if rated == 0 else 'see artifacts/evaluation/judge_agreement.md'} | — | — | human packet ({rated} of {len(packet)} rows rated) | HUMAN EVALUATION = {out['human_evaluation']['status']} |",
          "", f"## Decisions that changed from Phase 9 final to the release ({len(changed)} of 197)", "",
          "| gid | Phase 9 final | Release 1.0.0 | gold should_escalate | gold reason | safe autonomous now | message (redacted) |", "|---|---|---|---|---|---|---|"]
    L += [f"| {c['gid']} | {c['phase9_final']} | {c['release']} | {c['gold_should_escalate']} | {c['gold_reason']} | {c['safe_autonomous_now']} | {c['message'].replace('|', '/')} |" for c in changed]
    L += ["", f"Missed escalations in the release run: {len(fn)} " + "; ".join(f"{f['gid']} ({f['gold_reason']} → {f['action']}/{f['reason_code']})" for f in fn),
          f"Autonomous replies in the release run: {len(auto)} (" + ", ".join(f"{x['gid']} {x['kind']} {x['safe']}" for x in auto) + ")", "",
          "Live latency and cost per request: `artifacts/final/performance/perf_final.md`. AI-labelled dev results: `artifacts/final/risk_experiment/report.md`."]
    (OUT / "final_metrics.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())
