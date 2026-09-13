"""ResolveAI evaluation harness entry point.

  python scripts/evaluate.py --cached     # DEFAULT. No API calls. Verifies the golden hash and every input artifact hash,
                                          # recomputes all headline metrics, bootstrap intervals, slices, ablations, judge
                                          # aggregates, agreement (or PENDING) and regenerates the result tables. Measured at 171.6 s
                                          # on an 8-core laptop (artifacts/product/hardening/cached_eval_check.json).
  python scripts/evaluate.py --live       # Re-runs every system, the judge, the offline ablations and the packet, then the
                                          # cached step. Needs LLM_API_KEY; ~3-4 hours of model time; never the default.
  python scripts/evaluate.py --cached --n-boot 200   # faster bootstrap for a smoke check (default 1000)

Inputs (all under artifacts/evaluation/): runs/<system>.jsonl, judge_results.jsonl, pairwise_results.jsonl, offline_ablations.json,
judge_config.json; data/human_eval/human_scoring_packet.csv (+ _packet_key.json). Outputs: the artifact list in docs/EVALUATION.md.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import resolveai  # noqa: E402,F401
from resolveai.evaluation import load_golden  # noqa: E402
from resolveai.evaluation.agreement import load_human_packet, per_dimension_agreement  # noqa: E402
from resolveai.evaluation.baselines import describe  # noqa: E402
from resolveai.evaluation.judge import BINARY, DIMENSIONS, JUDGE_PROMPT_VERSION, PAIR_PROMPT_VERSION, RUBRIC, RUBRIC_VERSION  # noqa: E402
from resolveai.evaluation.reporting import (  # noqa: E402
    PRIMARY_JUDGE,
    counts_by_intent,
    gold_map,
    judge_summary,
    load_judge,
    load_runs,
    paired_comparisons,
    pairwise_summary,
    sha256,
    slices_for,
    system_report,
)

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / "artifacts" / "evaluation"
RUNS = EV / "runs"
HUMAN = ROOT / "data" / "human_eval"
BASELINES = ["B0_trivial", "B0_trivial_always_handoff", "B1_simple_ml", "B2_direct_llm"]
ABLATIONS = ["minus_second_opinion", "minus_resolution_rerank", "minus_risk_llm", "minus_retrieval"]
REF = "resolveai_full"
LIVE_STEPS = [["python", "scripts/phase6/a_run_systems.py"], ["python", "scripts/phase6/a_run_systems.py", *ABLATIONS],
              ["python", "scripts/phase6/b_judge.py", "--absolute", REF, "B1_simple_ml", "B2_direct_llm", "B0_trivial"],
              ["python", "scripts/phase6/b_judge.py", "--pairwise", f"{REF}:B1_simple_ml", f"{REF}:B2_direct_llm"],
              ["python", "scripts/phase6/d_offline_ablations.py"], ["python", "scripts/phase6/c_human_packet.py"]]


def fmt(ci: dict | None) -> str:
    return "n/a" if not ci else f"{ci['point']:.3f} [{ci['ci_low']:.3f}, {ci['ci_high']:.3f}]"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cached", action="store_true")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--n-boot", type=int, default=1000)
    a = ap.parse_args()
    t_all = time.perf_counter()
    if a.live:
        for step in LIVE_STEPS:
            print("LIVE:", " ".join(step), flush=True)
            subprocess.run(step, check=True, cwd=ROOT)
    EV.mkdir(parents=True, exist_ok=True)

    # ---- 1. integrity -------------------------------------------------------------------------------------------
    gold = load_golden()   # raises if the frozen file hash changed
    gm = gold_map(gold)
    manifest = {"golden_sha256": json.loads((ROOT / "data/golden/golden_freeze_manifest.json").read_text())["sha256"], "golden_rows": int(len(gold)), "inputs": {}, "mode": "live" if a.live else "cached",
                "n_boot": a.n_boot, "seed": 42, "rubric_version": RUBRIC_VERSION, "judge_prompt_versions": [JUDGE_PROMPT_VERSION, PAIR_PROMPT_VERSION]}
    for p in sorted(list(RUNS.glob("*.jsonl")) + [EV / "judge_results.jsonl", EV / "pairwise_results.jsonl", EV / "offline_ablations.json", EV / "judge_config.json", HUMAN / "human_scoring_packet.csv",
                                                     ROOT / "resolveai/retrieval/gate_v3_config.json", ROOT / "resolveai/retrieval/rerank_weights.json", ROOT / "resolveai/models/artifacts/intent_bge_lr.json"]):
        if p.exists():
            manifest["inputs"][str(p.relative_to(ROOT)).replace("\\", "/")] = sha256(p)
    prev = EV / "reproduction_manifest.json"
    if prev.exists() and not a.live:
        old = json.loads(prev.read_text(encoding="utf-8")).get("inputs", {})
        changed = [k for k, v in manifest["inputs"].items() if k in old and old[k] != v]
        manifest["inputs_changed_since_last_run"] = changed
        if changed:
            print("WARNING: input artifacts changed since the last manifest:", changed)

    runs = load_runs(RUNS)
    systems = [s for s in [REF, *BASELINES, *ABLATIONS] if s in runs]
    reports = {s: system_report(runs[s], gold, gm, n_boot=a.n_boot) for s in systems}
    judge_rows = load_judge(EV / "judge_results.jsonl")
    pair_rows = load_judge(EV / "pairwise_results.jsonl")
    jq = judge_summary(judge_rows, systems + ["offline_weak_drafts"], gm, runs, n_boot=a.n_boot)
    jq_secondary = judge_summary(judge_rows, systems, gm, runs, judge_model="qwen/qwen3.8-27b", n_boot=a.n_boot)
    pw = pairwise_summary(pair_rows)
    comps = paired_comparisons(runs, gm, REF, BASELINES + ABLATIONS, n_boot=a.n_boot)
    sl = slices_for({s: runs[s] for s in systems if s in runs}, gold)
    offline = json.loads((EV / "offline_ablations.json").read_text(encoding="utf-8")) if (EV / "offline_ablations.json").exists() else {}

    # ---- 2. headline ---------------------------------------------------------------------------------------------
    R = reports[REF]
    headline = {"system": REF, "n": R["n"], "golden_sha256": manifest["golden_sha256"],
                "intent_accuracy": R["intent"]["bootstrap"]["accuracy"], "intent_macro_f1": R["intent"]["bootstrap"]["macro_f1"],
                "escalation_recall": R["escalation"]["bootstrap"]["recall"], "escalation_f1": R["escalation"]["bootstrap"]["f1"], "escalation_precision": R["escalation"]["precision"],
                "missed_escalations": R["escalation"]["fn"], "false_escalations": R["escalation"]["fp"],
                "auto_handle_rate": R["autonomy"]["auto_handle_rate"], "clarification_rate": R["autonomy"]["clarification_rate"], "handoff_rate": R["autonomy"]["handoff_rate"],
                "safe_auto_handle_rate": R["autonomy"]["bootstrap"]["safe_auto_handle_rate"], "safe_auto_handle_count": R["autonomy"]["safe_auto_handle_count"], "unsafe_auto_handle_count": R["autonomy"]["unsafe_auto_handle_count"],
                "grounded_auto_handle_count": R["autonomy"]["grounded_auto_handle_count"], "judge": (jq["systems"].get(REF) or {}).get("means"), "judge_hallucination_rate": (jq["systems"].get(REF) or {}).get("rates", {}).get("hallucination"),
                "cost_latency": R["cost_latency"], "caveat": "see misleading_headline.md; intervals are 95% bootstrap (seed 42)"}
    (EV / "headline_metrics.json").write_text(json.dumps(headline, indent=1), encoding="utf-8")
    (EV / "intent_report.json").write_text(json.dumps({s: reports[s]["intent"] | {"calibration": reports[s].get("calibration"), "accuracy_by_band": reports[s].get("accuracy_by_band"), "selective_prediction": reports[s].get("selective_prediction")} for s in systems}, indent=1), encoding="utf-8")
    (EV / "escalation_report.json").write_text(json.dumps({s: reports[s]["escalation"] for s in systems}, indent=1), encoding="utf-8")
    (EV / "autonomy_report.json").write_text(json.dumps({s: reports[s]["autonomy"] | {"by_gold_intent": counts_by_intent(runs[s], gm)} for s in systems}, indent=1), encoding="utf-8")
    (EV / "reply_quality.json").write_text(json.dumps({"primary": jq, "secondary_cross_family": jq_secondary, "rubric_version": RUBRIC_VERSION, "dimensions": list(DIMENSIONS), "binary": list(BINARY)}, indent=1), encoding="utf-8")
    (EV / "pairwise_results.json").write_text(json.dumps(pw, indent=1), encoding="utf-8")
    (EV / "slice_analysis.json").write_text(json.dumps(sl, indent=1), encoding="utf-8")
    (EV / "baseline_comparison.json").write_text(json.dumps({"systems": {s: {"description": describe().get(s, s), "intent": {k: reports[s]["intent"][k] for k in ("accuracy", "macro_f1")}, "escalation": {k: reports[s]["escalation"][k] for k in ("precision", "recall", "f1", "fp", "fn")},
                                                                                "autonomy": {k: reports[s]["autonomy"][k] for k in ("auto_handle_rate", "clarification_rate", "handoff_rate", "safe_auto_handle_count", "unsafe_auto_handle_count", "grounded_auto_handle_count", "correct_non_autonomous_count", "unnecessary_non_autonomous_count")},
                                                                                "cost_latency": reports[s]["cost_latency"], "judge": (jq["systems"].get(s) or {}).get("means"), "judge_rates": (jq["systems"].get(s) or {}).get("rates")} for s in systems},
                                                              "paired_differences_vs_resolveai": comps, "pairwise_judge": pw, "protocol": describe()["information_parity"]}, indent=1), encoding="utf-8")

    # ---- 3. markdown tables ---------------------------------------------------------------------------------------
    L = ["# Baseline comparison (golden, n=197, evaluated once per system)", "", describe()["information_parity"], "",
         "| system | intent acc | intent macro-F1 [95% CI] | esc precision | esc recall [95% CI] | esc F1 | auto | clarify | handoff | safe auto | unsafe auto | grounded auto | judge groundedness | judge hallucination | LLM calls | $/msg | p50 ms |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for s in systems:
        r, j = reports[s], jq["systems"].get(s) or {}
        L.append(f"| {s} | {r['intent']['accuracy']} | {fmt(r['intent']['bootstrap']['macro_f1'])} | {r['escalation']['precision']} | {fmt(r['escalation']['bootstrap']['recall'])} | {r['escalation']['f1']} | "
                 f"{r['autonomy']['auto_handle_rate']} | {r['autonomy']['clarification_rate']} | {r['autonomy']['handoff_rate']} | {r['autonomy']['safe_auto_handle_count']} | {r['autonomy']['unsafe_auto_handle_count']} | {r['autonomy']['grounded_auto_handle_count']} | "
                 f"{(j.get('means') or {}).get('groundedness', 'n/a')} | {(j.get('rates') or {}).get('hallucination', 'n/a')} | {r['cost_latency']['llm_calls_per_message']} | {r['cost_latency']['estimated_cost_usd_per_message']} | {r['cost_latency']['p50_latency_ms']} |")
    L += ["", "## Paired bootstrap differences (ResolveAI minus system; 95% CI; same resampled rows for both)", "", "| comparison | intent macro-F1 | escalation F1 | escalation recall | safe auto rate |", "|---|---|---|---|---|"]
    for k, v in comps.items():
        L.append(f"| {k} | {v['intent_macro_f1']['difference']} [{v['intent_macro_f1']['ci_low']}, {v['intent_macro_f1']['ci_high']}] | {v['escalation_f1']['difference']} [{v['escalation_f1']['ci_low']}, {v['escalation_f1']['ci_high']}] | "
                 f"{v['escalation_recall']['difference']} [{v['escalation_recall']['ci_low']}, {v['escalation_recall']['ci_high']}] | {v['safe_auto_rate']['difference']} [{v['safe_auto_rate']['ci_low']}, {v['safe_auto_rate']['ci_high']}] |")
    L += ["", "## Blinded pairwise judge (A/B position randomised, seed 42)", "", "| pair | n | win | tie | loss | win rate | x wins when in position A | x wins when in position B | judge failures |", "|---|---|---|---|---|---|---|---|---|"]
    for k, v in pw.items():
        L.append(f"| {k} | {v['n']} | {v['win']} | {v['tie']} | {v['loss']} | {v['win_rate']} | {v['position_check']['x_wins_when_A']} | {v['position_check']['x_wins_when_B']} | {v['judge_failures']} |")
    L += ["", "Judge: " + PRIMARY_JUDGE + " (same family as ResolveAI's drafter and the direct-LLM baseline; self-preference risk discussed in judge_agreement.md). B0's canned reply and B1's copied historical replies are not LLM-written."]
    (EV / "baseline_comparison.md").write_text("\n".join(L), encoding="utf-8")

    # slices
    L = ["# Slice analysis (per system; n = rows in slice)", "", "Slices come from the frozen golden flags (short, multi-turn, seen customer, multi-intent, taxonomy gap, insufficient context, rare intent) and from each system's own outputs (confidence band, evidence sufficiency).", ""]
    for s in [REF, "B1_simple_ml", "B2_direct_llm"]:
        if s not in sl:
            continue
        L += [f"## {s}", "", "| slice | n | intent acc | esc recall (n gold esc) | false esc rate | auto | clarify | handoff | unsafe auto | evidence sufficient |", "|---|---|---|---|---|---|---|---|---|---|"]
        for row in sl[s]:
            L.append(f"| {row['slice']} | {row['n']} | {row['intent_accuracy']} | {row['escalation_recall']} ({row['n_gold_escalate']}) | {row['false_escalation_rate']} | {row['auto_rate']} | {row['clarify_rate']} | {row['handoff_rate']} | {row['unsafe_auto']} | {row['evidence_sufficient_rate']} |")
        L.append("")
    if "calibration" in R:
        L += ["## ResolveAI intent calibration (confidence = calibrated top-class probability)", "", f"ECE {R['calibration']['ece']} over {R['calibration']['n']} rows", "", "| bin | n | mean confidence | accuracy |", "|---|---|---|---|"]
        L += [f"| {b['bin']} | {b['n']} | {b['mean_confidence']} | {b['accuracy']} |" for b in R["calibration"]["bins"]]
        L += ["", "| band | n | accuracy |", "|---|---|---|"] + [f"| {k} | {v['n']} | {v['accuracy']} |" for k, v in R["accuracy_by_band"].items()]
        L += ["", "Selective prediction (answer only when confidence >= t):", "", "| threshold | coverage | n | accuracy |", "|---|---|---|---|"] + [f"| {x['threshold']} | {x['coverage']} | {x['n']} | {x['accuracy']} |" for x in R["selective_prediction"]]
    (EV / "slice_analysis.md").write_text("\n".join(L), encoding="utf-8")

    # ablations
    L = ["# Ablations (golden; each ablation is one switch on the production agent, nothing re-tuned)", "", "| system | intent acc | intent macro-F1 | esc recall | esc precision | auto | clarify | handoff | safe auto | unsafe auto | evidence sufficient | LLM calls | $/msg |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for s in [REF, *ABLATIONS]:
        if s not in reports:
            continue
        r = reports[s]
        suff = sum(1 for x in runs[s] if x.evidence_sufficient) / len(runs[s])
        L.append(f"| {s} | {r['intent']['accuracy']} | {r['intent']['macro_f1']} | {r['escalation']['recall']} | {r['escalation']['precision']} | {r['autonomy']['auto_handle_rate']} | {r['autonomy']['clarification_rate']} | {r['autonomy']['handoff_rate']} | "
                 f"{r['autonomy']['safe_auto_handle_count']} | {r['autonomy']['unsafe_auto_handle_count']} | {suff:.3f} | {r['cost_latency']['llm_calls_per_message']} | {r['cost_latency']['estimated_cost_usd_per_message']} |")
    L += ["", "Paired differences (ResolveAI minus ablation) are in baseline_comparison.json under paired_differences_vs_resolveai.", ""]
    if offline:
        mv, mg = offline.get("minus_verifier", {}), offline.get("minus_gate_weak_rows", {})
        L += ["## Offline: minus verifier (never disabled on the production path)", "", f"`{json.dumps(mv)}`", "",
              "## Offline: minus gate on WEAK rows (abstention curve)", "", f"`{json.dumps(mg)}`", "",
              "Reading: production drafts only on SUFFICIENT/STRONG evidence. Drafting on WEAK evidence would add the rows above; their judge scores and hallucination rate show the quality the gate is protecting."]
    if "offline_weak_drafts" in jq["systems"]:
        w = jq["systems"]["offline_weak_drafts"]
        L += ["", f"Judge on WEAK-evidence drafts: n={w['n_parsed']}, means `{json.dumps(w['means'])}`, hallucination {w['rates'].get('hallucination')} vs STRONG-evidence production drafts `{json.dumps((jq['systems'].get(REF) or {}).get('by_response_kind', {}).get('troubleshoot'))}`."]
    (EV / "ablation_results.md").write_text("\n".join(L), encoding="utf-8")

    # statistical uncertainty
    L = ["# Statistical uncertainty", "", f"Bootstrap: resample the {R['n']} golden rows with replacement {a.n_boot} times (numpy default_rng seed 42), recompute the statistic, report the 2.5/97.5 percentiles. "
         "Paired comparisons resample the same row indices for both systems. Failed calls stay in every sample. Judge intervals resample the parsed judge rows (judge failures excluded from means but reported).", "",
         "| system | intent accuracy | intent macro-F1 | escalation recall | escalation F1 | safe auto rate | judge groundedness | judge hallucination |", "|---|---|---|---|---|---|---|---|"]
    for s in systems:
        r, j = reports[s], (jq["systems"].get(s) or {}).get("bootstrap", {})
        L.append(f"| {s} | {fmt(r['intent']['bootstrap']['accuracy'])} | {fmt(r['intent']['bootstrap']['macro_f1'])} | {fmt(r['escalation']['bootstrap']['recall'])} | {fmt(r['escalation']['bootstrap']['f1'])} | {fmt(r['autonomy']['bootstrap']['safe_auto_handle_rate'])} | {fmt(j.get('groundedness'))} | {fmt(j.get('hallucination'))} |")
    L += ["", "Escalation recall rests on 37 gold positives: one more missed escalation moves it by 2.7 points. Safe-auto rates rest on 9 autonomous rows. Intervals that overlap heavily are reported as not distinguishable in the reports."]
    (EV / "statistical_uncertainty.md").write_text("\n".join(L), encoding="utf-8")

    # ---- 4. judge agreement --------------------------------------------------------------------------------------
    agreement = {"status": "PENDING_HUMAN_RATINGS"}
    packet = HUMAN / "human_scoring_packet.csv"
    if packet.exists() and (HUMAN / "_packet_key.json").exists():
        pairs, status = load_human_packet(packet, HUMAN / "_packet_key.json", [j for j in judge_rows if j.get("judge_model") == PRIMARY_JUDGE])
        agreement = status
        if status.get("status") == "RATED" and len(pairs):
            agreement["per_dimension"] = per_dimension_agreement(pairs, n_boot=a.n_boot)
            pairs.to_csv(EV / "judge_human_pairs.csv", index=False)
    # cross-family check (secondary judge vs primary judge on the subset both scored)
    cross = {}
    prim = {(j["gid"], j["system"]): j for j in judge_rows if j.get("judge_model") == PRIMARY_JUDGE and not j.get("failed")}
    sec = {(j["gid"], j["system"]): j for j in judge_rows if j.get("judge_model") == "qwen/qwen3.8-27b" and not j.get("failed")}
    both = sorted(set(prim) & set(sec))
    if both:
        df = pd.DataFrame([{**{f"human_{d}": sec[k][d] for d in DIMENSIONS + BINARY}, **{f"judge_{d}": prim[k][d] for d in DIMENSIONS + BINARY}} for k in both])
        cross = {"n": len(both), "note": "'human_' columns here hold the SECOND-FAMILY judge (qwen3.8-27b), not a human; this is judge-vs-judge", "per_dimension": per_dimension_agreement(df, n_boot=a.n_boot),
                 "per_system_means_primary": {s: {d: round(float(sum(prim[k][d] for k in both if k[1] == s) / max(1, sum(1 for k in both if k[1] == s))), 2) for d in DIMENSIONS} for s in sorted({k[1] for k in both})},
                 "per_system_means_secondary": {s: {d: round(float(sum(sec[k][d] for k in both if k[1] == s) / max(1, sum(1 for k in both if k[1] == s))), 2) for d in DIMENSIONS} for s in sorted({k[1] for k in both})}}
    (EV / "judge_agreement.json").write_text(json.dumps({"human": agreement, "cross_family": cross}, indent=1), encoding="utf-8")
    L = ["# Judge <-> human agreement", ""]
    if agreement.get("status") != "RATED":
        L += ["**PENDING HUMAN RATINGS.** The blinded packet `data/human_eval/human_scoring_packet.csv` has " + str(agreement.get("n_examples", 0)) + " examples and " + str(agreement.get("n_fully_rated", 0)) + " fully rated rows. "
              "Fill columns human_groundedness .. human_policy_violation (see docs/HUMAN_JUDGE_GUIDE.md), save, and re-run `python scripts/evaluate.py --cached`.",
              "", "No human rating in this project exists yet; every earlier 'hand-check' (gate calibration, verifier audit, Annotator B) was an AI annotator and is labelled as such.", ""]
    else:
        pdm = agreement["per_dimension"]
        L += [f"{agreement['n_joined']} rated examples joined to primary-judge scores.", "", "| dimension | n | weighted kappa [95% CI] | Spearman rho | exact | within 1 | mean human | mean judge | judge bias |", "|---|---|---|---|---|---|---|---|---|"]
        for d, v in pdm["ordinal"].items():
            if "weighted_kappa" in v:
                L.append(f"| {d} | {v['n']} | {v['weighted_kappa']} {v['weighted_kappa_ci']} | {v['spearman_rho']} | {v['exact_agreement']} | {v['within_one']} | {v['mean_human']} | {v['mean_judge']} | {v['judge_leniency']} ({v['judge_minus_human']:+.2f}) |")
        L += ["", "| binary | n | Cohen kappa [95% CI] | raw agreement | human positive rate | judge positive rate |", "|---|---|---|---|---|---|"]
        for d, v in pdm["binary"].items():
            if "cohen_kappa" in v:
                L.append(f"| {d} | {v['n']} | {v['cohen_kappa']} {v['cohen_kappa_ci']} | {v['raw_agreement']} | {v['human_positive_rate']} | {v['judge_positive_rate']} |")
        L += ["", "### Where they disagree", ""]
        num = pairs.copy()
        for c in [f"{w}_{d}" for w in ("human", "judge") for d in DIMENSIONS + BINARY]:
            num[c] = pd.to_numeric(num[c], errors="coerce")
        # 1. which system the judge over- or under-rates relative to the human (the self-preference question)
        L += ["Judge minus human, by system (positive = the judge is more generous than the human):", "",
              "| system | n | " + " | ".join(DIMENSIONS) + " |", "|---|---|" + "---|" * len(DIMENSIONS)]
        for s, g in num.groupby("system"):
            L.append(f"| {s} | {len(g)} | " + " | ".join(f"{g[f'judge_{d}'].mean() - g[f'human_{d}'].mean():+.2f}" for d in DIMENSIONS) + " |")
        L += ["", "The judge shares a model family with ResolveAI's drafter and with B2. If its generosity is larger for those two "
              "systems than for B1's copied historical replies, that is a self-preference effect, not a quality difference.", ""]
        # 2. the individual rows that disagree most, so they can be read rather than summarised
        gaps = []
        for _, r in num.iterrows():
            worst = max(DIMENSIONS, key=lambda d: abs(r[f"judge_{d}"] - r[f"human_{d}"]))
            gaps.append((abs(r[f"judge_{worst}"] - r[f"human_{worst}"]), r["example_id"], r["system"], r["gid"], worst, r[f"human_{worst}"], r[f"judge_{worst}"]))
        gaps.sort(key=lambda g: -g[0])
        big = [g for g in gaps if g[0] >= 2][:12]
        L += [f"{sum(1 for g in gaps if g[0] >= 2)} of {len(gaps)} rows differ by 2 or more points on at least one dimension"
              + (f"; the largest {len(big)}:" if big else "."), ""]
        if big:
            L += ["| example | system | golden row | dimension | human | judge |", "|---|---|---|---|---|---|"]
            L += [f"| {e} | {s} | {g} | {d} | {h:.0f} | {j:.0f} |" for _, e, s, g, d, h, j in big]
            L += ["", "Read these rows in `artifacts/evaluation/judge_human_pairs.csv` before trusting any judge-scored headline.", ""]
        # 3. binary disagreements are the ones that change a safety claim
        for d in BINARY:
            missed = int(((num[f"human_{d}"] == 1) & (num[f"judge_{d}"] == 0)).sum())
            added = int(((num[f"human_{d}"] == 0) & (num[f"judge_{d}"] == 1)).sum())
            L.append(f"- **{d}**: the judge missed {missed} case(s) the human flagged and flagged {added} the human did not. "
                     f"A judge that misses {d} understates the risk of every system it scores.")
        L.append("")
    L += ["## Cross-family judge check (judge vs judge, NOT human)", ""]
    if cross:
        L += [f"{cross['n']} responses scored by both GLM-5.2 (primary) and qwen3.8-27b (Groq, second family).", "", "| dimension | weighted kappa | Spearman | exact | within 1 | mean primary | mean secondary |", "|---|---|---|---|---|---|---|"]
        for d, v in cross["per_dimension"]["ordinal"].items():
            if "weighted_kappa" in v:
                L.append(f"| {d} | {v['weighted_kappa']} | {v['spearman_rho']} | {v['exact_agreement']} | {v['within_one']} | {v['mean_judge']} | {v['mean_human']} |")
        for d, v in cross["per_dimension"]["binary"].items():
            if "cohen_kappa" in v:
                L.append(f"| {d} (binary) | kappa {v['cohen_kappa']} | raw {v['raw_agreement']} | | | primary rate {v['judge_positive_rate']} | secondary rate {v['human_positive_rate']} |")
        L += ["", "Per-system means (primary vs secondary): `" + json.dumps(cross["per_system_means_primary"]) + "` vs `" + json.dumps(cross["per_system_means_secondary"]) + "`",
              "If the primary judge rates GLM-written responses (ResolveAI drafts, B2) higher than the second family does while agreeing on the non-LLM responses (B1 copies, templates), that is the self-preference signature."]
    else:
        L.append("Not available (second-family judge not run).")
    L += ["", "## Limitations of this study", "",
          "These apply whether or not the packet has been rated, and no result above should be quoted without them.", "",
          "1. **One rater.** The packet is rated by the repository owner alone, so there is no inter-human reliability figure and "
          "no way to separate judge error from rater idiosyncrasy. A kappa here measures agreement with *one* person.",
          "2. **The rater is not independent.** The owner built the system under test. The packet is blinded (the system that "
          "produced each response is only in `_packet_key.json`), which limits but does not remove that bias.",
          "3. **50 stratified rows, not a random sample.** The packet oversamples handoffs, clarifications, difficult rows and "
          "judge-extreme rows (`packet_manifest.json`) so that disagreement is visible at small n. Rates read off it are "
          "therefore not estimates of the golden set's rates, and the CIs are wide at n = 50.",
          "4. **The judge shares a family with two systems under test.** GLM-5.2 judges GLM-5.2 drafts (ResolveAI) and the "
          "direct-LLM baseline. The cross-family check above is the control; human agreement measures a different thing again.",
          "5. **Agreement is not accuracy.** A judge and a human can agree and both be wrong, particularly on groundedness, "
          "where both are reading evidence they cannot verify against Apple's actual policy.",
          "6. **Every other 'hand-check' in this project is AI annotation.** Annotator B, the gate calibration checks and the "
          "verifier audit were done by an isolated AI agent and are labelled as such; only this packet's `human_*` columns "
          "are human ratings. AI annotation is never reported as human evaluation.", ""]
    (EV / "judge_agreement.md").write_text("\n".join(L), encoding="utf-8")

    # ---- 4b. retrieval report (Phase 2 / Phase 5 measurements, re-stated with their provenance) ------------------
    r2 = json.loads((ROOT / "artifacts/retrieval/results.json").read_text(encoding="utf-8")) if (ROOT / "artifacts/retrieval/results.json").exists() else {}
    r5 = json.loads((ROOT / "artifacts/resolution/retrieval_results.json").read_text(encoding="utf-8")) if (ROOT / "artifacts/resolution/retrieval_results.json").exists() else {}
    full_recs = runs.get(REF, [])
    d5 = (r5.get("golden") or {}).get("D_B2_pair_rr_v3") or {}
    a5 = (r5.get("golden") or {}).get("A_customer_v2") or {}
    gate_hand = (r5.get("gate_handcheck") or {})
    retrieval = {"same_resolution_recall": {"protocol": "reply-side TF-IDF >= 0.5 between the golden row's own historical reply and each substantive KB reply; label-free; scorable on 46 of 197 golden rows",
                                            "phase2_customer_index_gate_v2": {k: a5.get(k) for k in ("recall@1", "recall@3", "recall@5", "mrr", "n_ref")},
                                            "phase5_pair_rerank_gate_v3": {k: d5.get(k) for k in ("recall@1", "recall@3", "recall@5", "mrr", "n_ref")},
                                            "all_phase5_variants_golden": {k: {m: v.get(m) for m in ("recall@5", "mrr", "resolution_bearing@1", "resolution_bearing@3", "sufficient_rate")} for k, v in (r5.get("golden") or {}).items()},
                                            "phase2_variants_golden": {k: {m: v.get(m) for m in ("recall@1", "recall@5", "mrr")} for k, v in (r2.get("golden") or {}).items()}},
                 "resolution_bearing_rank": {"definition": "a substantive reply whose non-question sentences state an instruction or released fix (is_resolution_bearing); a lexical predicate, NOT a relevance label",
                                             "phase2_customer_index": {k: a5.get(k) for k in ("resolution_bearing@1", "resolution_bearing@3", "resolution_bearing@5", "resolution_mrr")},
                                             "phase5_pair_rerank": {k: d5.get(k) for k in ("resolution_bearing@1", "resolution_bearing@3", "resolution_bearing@5", "resolution_mrr")}},
                 "same_intent_retrieval": {"phase2": a5.get("same_intent@5"), "phase5": d5.get("same_intent@5"), "definition": "share of golden rows with >= 1 top-5 item whose weak-keyword intent equals the gold intent"},
                 "evidence_sufficiency_agent_run": {"levels": dict(__import__("collections").Counter(r.evidence_level for r in full_recs)), "sufficient_rate": round(sum(1 for r in full_recs if r.evidence_sufficient) / max(1, len(full_recs)), 4)},
                 "gate_precision_estimate": {"source": "24 DEV cases hand-checked by an AI annotator (Claude), NOT human ground truth", "chosen": gate_hand.get("chosen"), "table": gate_hand.get("table"),
                                             "automatic_judge_precision": "0 for every gate setting (judge limitation, as in Phase 2)"},
                 "coverage": {"kb_rows": 17875, "golden_rows_with_reference": 46, "golden_rows_sufficient_agent_run": sum(1 for r in full_recs if r.evidence_sufficient)},
                 "limitations": ["46 scorable references: recall@5 differences under ~0.1 are not distinguishable", "the TF-IDF judge rewards ask-info replies and cannot see paraphrases",
                                 "resolution-bearing is a lexical predicate over the reply, not a judgement that the reply fits the query", "gate precision is AI-annotated on 24 dev cases; the golden set was never used for calibration",
                                 "the KB and golden are dominated by the Nov-2017 autocorrect burst: nearly every STRONG verdict is that bug"]}
    (EV / "retrieval_report.json").write_text(json.dumps(retrieval, indent=1), encoding="utf-8")

    # ---- 5. rubric + manifest ------------------------------------------------------------------------------------
    (EV / "judge_rubric.json").write_text(json.dumps({"rubric_version": RUBRIC_VERSION, "prompt_versions": {"absolute": JUDGE_PROMPT_VERSION, "pairwise": PAIR_PROMPT_VERSION}, "rubric": {k: {"question": v["question"], "anchors": {str(a_): b for a_, b in v["anchors"].items()}} for k, v in RUBRIC.items()}}, indent=1), encoding="utf-8")
    manifest["runtime_seconds"] = round(time.perf_counter() - t_all, 1)
    manifest["systems"] = systems
    manifest["judge_rows"] = len(judge_rows)
    manifest["pairwise_rows"] = len(pair_rows)
    manifest["human_study"] = agreement.get("status")
    (EV / "reproduction_manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(f"headline: intent macro-F1 {fmt(headline['intent_macro_f1'])}, escalation recall {fmt(headline['escalation_recall'])}, safe auto rate {fmt(headline['safe_auto_handle_rate'])}")
    print(f"judge rows {len(judge_rows)}, pairwise rows {len(pair_rows)}, human study: {agreement.get('status')}, runtime {manifest['runtime_seconds']} s")
    try:
        from scripts.phase6 import e_narrative  # noqa: F401
    except Exception:  # noqa: BLE001
        pass
    narr = ROOT / "scripts/phase6/e_narrative.py"
    if narr.exists():
        subprocess.run([sys.executable, str(narr)], check=False, cwd=ROOT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
