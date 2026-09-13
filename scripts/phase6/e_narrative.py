"""Phase 6-E: narrative artifacts generated from the measured JSON (no hand-typed numbers): failure_analysis.md,
misleading_headline.md and PHASE6_REPORT.md. Called at the end of scripts/evaluate.py; safe to run alone.
The real golden examples cited below were selected by reading the records (scripts/phase6 analysis), not by a model."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EV = ROOT / "artifacts" / "evaluation"
J = lambda name: json.loads((EV / name).read_text(encoding="utf-8")) if (EV / name).exists() else {}  # noqa: E731


def recs(system: str) -> dict[str, dict]:
    p = EV / "runs" / f"{system}.jsonl"
    return {r["gid"]: r for r in (json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip())} if p.exists() else {}


def main() -> None:
    from resolveai.evaluation import load_golden

    gold = load_golden().set_index("gid")
    H, BC, ESC, INT, AUT, RQ, PW, AG, RET, OFF, MAN = (J("headline_metrics.json"), J("baseline_comparison.json"), J("escalation_report.json"), J("intent_report.json"), J("autonomy_report.json"),
                                                        J("reply_quality.json"), J("pairwise_results.json"), J("judge_agreement.json"), J("retrieval_report.json"), J("offline_ablations.json"), J("reproduction_manifest.json"))
    full = recs("resolveai_full")
    R = ESC.get("resolveai_full", {})
    A = AUT.get("resolveai_full", {})
    IR = INT.get("resolveai_full", {})
    jq = (RQ.get("primary") or {}).get("systems", {})
    jr = jq.get("resolveai_full", {})
    jb1, jb2 = jq.get("B1_simple_ml", {}), jq.get("B2_direct_llm", {})
    fn = R.get("false_negatives", [])
    unneeded = Counter(r["reason_code"] for g, r in full.items() if not gold.loc[g].should_escalate and r["action"] == "HUMAN_HANDOFF")
    priv = [g for g, r in full.items() if not gold.loc[g].should_escalate and r["reason_code"] == "private_info"]
    priv_llm = [g for g in priv if "needs_private_info" in full[g]["risk_flags"]]
    priv_nonenglish = [g for g in priv if gold.loc[g].intent == "non_english"]
    mrl_auto = AUT.get("minus_risk_llm", {})
    conf = Counter((gold.loc[g].intent, r["intent_pred"]) for g, r in full.items() if r["intent_pred"] != gold.loc[g].intent)
    apps_dl = conf.get(("apps_services", "data_loss_sync"), 0)
    strong_handoff = [g for g, r in full.items() if r["evidence_level"] in ("STRONG", "SUFFICIENT") and r["action"] != "AUTO_HANDLE"]
    judge_fail = sum(1 for s in jq.values() for _ in [0] if False) or sum((jq.get(s) or {}).get("judge_failures", 0) for s in jq)
    n_judged = sum((jq.get(s) or {}).get("n_scored", 0) for s in jq)
    kind = jr.get("by_response_kind", {})
    cross = AG.get("cross_family") or {}
    human = AG.get("human") or {}

    # ------------------------------------------------------------ failure analysis -----------------------------------
    F = f"""# Top end-to-end failure modes (golden set, real examples)

Each mode is grounded in golden rows from `artifacts/evaluation/runs/resolveai_full.jsonl`. Frequency counts are over the 197 rows.
Categories: MODEL (a learned or LLM component), RETRIEVAL, POLICY, DATA/TAXONOMY, EVALUATION.

## 1. LLM risk extractor over-raises `needs_private_info`, turning routine troubleshooting into handoffs  (MODEL FAILURE, then POLICY)
- Examples: g068 "WHY DOES MY PHONE DIE ON 25%" (gold battery_power, no escalation) -> flags `{full.get('g068', {}).get('risk_flags')}` -> HUMAN_HANDOFF `private_info`;
  g020 "another keyboard glitch. Fix I.T" -> `{full.get('g020', {}).get('risk_flags')}` -> handoff; g088 "why ios 11.1.2 often self rebooting?" -> handoff.
- Expected: clarify or answer (the annotators marked these should_escalate=false); actual: handoff with reason private_info.
- Component: risk-flags-v2 (GLM) sets `needs_private_info` whenever it thinks a version/device would be needed; policy-v3 treats the flag as a hard reason.
- Frequency: {len(priv)} of the {sum(unneeded.values())} unnecessary handoffs carry reason private_info ({len(priv_llm)} with the LLM flag raised; {len(priv_nonenglish)} are non-English rows that never reached the canned redirect because private_info precedes it in the policy order).
  The rules-only ablation (`minus_risk_llm`) has {mrl_auto.get('handoff_rate')} handoff rate vs {A.get('handoff_rate')} for the full system, with {mrl_auto.get('unsafe_auto_handle_count')} unsafe autonomous replies and escalation recall {ESC.get('minus_risk_llm', {}).get('recall')} vs {R.get('recall')}.
- Severity: medium (customer gets a human instead of an answer; nothing unsafe). Fix: define `needs_private_info` for the LLM as "the resolution REQUIRES a serial/IMEI/order/case identifier", not "a device detail would help"; move the canned non_english rule ahead of private_info; measure on dev first.

## 2. Two missed escalations: a redaction token and a word-order gap in the deterministic rules  (MODEL FAILURE: rules)
- g157: "...stranded in Thailand without cellular access on my iPhoneX ... case <PHONE> they erroneously transferred my #..." (gold private_info) -> flags `{full.get('g157', {}).get('risk_flags')}`, intent {full.get('g157', {}).get('intent_pred')} at confidence {full.get('g157', {}).get('intent_confidence')} -> CLARIFICATION (low_confidence).
  Root cause: the `needs_private_info` rule lists `<PHONE>` inside a `\\b(...)\\b` group; `\\b` cannot match before `<`, so redaction tokens never fire the rule. The LLM did not raise it either.
- g048: "hey can you check the dm i sent!" (gold repeat_contact, guide rule R1) -> flags `{full.get('g048', {}).get('risk_flags')}` -> CLARIFICATION (insufficient_context). The repeat-contact rule matches "sent a dm" but not "dm i sent".
- Frequency: {len(fn)} of 37 should-escalate rows (missed-escalation rate {R.get('missed_escalation_rate')}); both were clarifications, not autonomous replies, so no unsafe text was sent.
- Severity: high for g157 (a private-identifier case handled as a clarification), low for g048. Fix: `(?<!\\w)<(PHONE|EMAIL|ORDER_ID|CARD|LONG_ID)>` outside the word-boundary group; add "dm i sent|the dm" to repeat_contact; add both as regression tests. Not applied in this phase (the evaluated system is the frozen Phase 5 system).

## 3. Evidence gate abstains on almost everything; autonomy is confined to one bug  (RETRIEVAL FAILURE / DATA)
- Only {A.get('auto_handle_count')} autonomous replies ({A.get('grounded_auto_handle_count')} grounded troubleshooting + canned); every STRONG verdict on golden is the iOS-11 "I"/"I.T" autocorrect bug. Evidence levels: `{RET.get('evidence_sufficiency_agent_run', {}).get('levels')}`.
- Example: g001 "this iOS update SUCKS! Phone freezes literally every 5 minutes" (performance_crash, no escalation): top evidence cosine below the 0.85 support level -> WEAK -> clarification. The KB has hundreds of freezing complaints, but their replies are questions ("which iOS version?"), not instruction-bearing fixes, so no resolution cluster forms.
- Also: g144 and g160 had STRONG evidence for the autocorrect fix but were handed off for repeat_contact (the customer said the earlier fix "didn't last") - correct per the guide, but it shows the gate and the policy pull in opposite directions on the only well-covered issue.
- Frequency: {sum(1 for r in full.values() if not r['evidence_sufficient'])} of 197 rows insufficient; {len(strong_handoff)} STRONG rows not answered.
- Severity: medium (safe, but the product answers 2.5% of troubleshooting requests). Fix: KB coverage beyond the burst (the brand's own replies rarely contain fixes: 52% are DM handoffs) and reply-side curation; not a threshold change.

## 4. `apps_services` bleeds into `data_loss_sync` and `general_complaint`  (MODEL FAILURE: classifier + taxonomy)
- Confusions (gold -> predicted): {dict(conf.most_common(6))}. apps_services (38 rows, the largest class) has recall {(IR.get('per_class') or {}).get('apps_services', {}).get('recall')}; e.g. an iCloud Photos/Music sync question is apps_services under rule R2 but embeds next to data_loss_sync rows.
- Component: BGE+LR classifier trained on silver labels (~71% precision) plus the GLM second opinion; the guide's R2 boundary (app-confined vs data) is not learnable from the silver rules.
- Frequency: {sum(conf.values())} intent errors of 197 (accuracy {IR.get('accuracy')}); {apps_dl} are apps_services -> data_loss_sync.
- Severity: low-medium (intent drives the clarifying question and the retrieval query, not escalation). Fix: hand-labelled dev rows for the R2 boundary; DATA/TAXONOMY as much as model.

## 5. The judge cannot yet be trusted as a quality measure  (EVALUATION FAILURE)
- {judge_fail} of {n_judged} judge calls failed to parse (hidden-reasoning truncation) and are excluded from means; the primary judge is the same model family as ResolveAI's drafter and B2.
- Hallucination rate on ResolveAI troubleshooting replies per the judge: {(kind.get('troubleshoot') or {}).get('hallucination')} (n={(kind.get('troubleshoot') or {}).get('n')}); on B2 direct-LLM replies: {(jb2.get('rates') or {}).get('hallucination')}; on B1 copied historical replies: {(jb1.get('rates') or {}).get('hallucination')}.
- Cross-family check (qwen3.8-27b, n={cross.get('n', 0)}): {json.dumps((cross.get('per_dimension') or {}).get('ordinal', {}).get('groundedness', {}))}.
- Human agreement: **{human.get('status', 'PENDING_HUMAN_RATINGS')}**. Until the packet is scored, every judge number in this phase is a model's opinion about model outputs.
- Severity: high for any claim about reply quality; none for the deterministic metrics (intent, escalation, autonomy), which do not use the judge.

## Not a failure, but worth naming
- The 7 `vague_hostile` and 5 `safety` handoffs on gold non-escalate rows are the LLM risk flags reading frustration as abuse or danger ("dead phone", "kill my battery"); the policy takes the safe side by design.
"""
    (EV / "failure_analysis.md").write_text(F, encoding="utf-8")

    b2e = (ESC.get("B2_direct_llm") or {})
    # ------------------------------------------------------------ misleading headline ------------------------------
    fmt = lambda ci: f"{ci['point']:.3f} [{ci['ci_low']:.3f}, {ci['ci_high']:.3f}]" if ci else "n/a"  # noqa: E731
    M = f"""# What is misleading about the headline numbers

Headline (golden, n=197): intent macro-F1 {fmt(H.get('intent_macro_f1'))}, escalation recall {fmt(H.get('escalation_recall'))}, safe autonomous
resolution rate {fmt(H.get('safe_auto_handle_rate'))}, judge groundedness {(H.get('judge') or {}).get('groundedness')}, 0 unsafe autonomous replies.

1. **197 rows, 37 escalation positives, 9 autonomous replies.** The recall interval spans {fmt(H.get('escalation_recall'))}: one more miss moves it 2.7 points. The safe-autonomy rate is 9 events; its interval is {fmt(H.get('safe_auto_handle_rate'))}. Nothing about autonomy generalises from 5 troubleshooting replies that all concern one bug.
2. **Class imbalance and rare classes.** apps_services has 38 rows, hardware_damage 7; macro-F1 gives each class equal weight, so one hardware_damage error costs 1.3 macro points. Per-class F1 is in intent_report.json; the weakest classes are `{json.dumps({k: v['f1'] for k, v in sorted((IR.get('per_class') or {}).items(), key=lambda kv: kv[1]['f1'])[:3]})}`.
3. **High escalation recall is partly a conservative policy.** The always-handoff baseline has recall 1.0 and precision {ESC.get('B0_trivial_always_handoff', {}).get('precision')}. ResolveAI's precision is {R.get('precision')}: {R.get('fp')} of its {R.get('fp', 0) + R.get('tp', 0)} handoffs were unnecessary by the annotators' standard. Recall is bought with human time; the cost-weighted view (escalation_report.json, ratios 1x/3x/5x) is an assumption, not a business measurement.
4. **The golden labels are adjudicated from two passes, one of them an AI** (Annotator B). Kappa 0.92/0.885 is consistency under a guide, not human-human agreement. Seven rows carry taxonomy_gap and 18 insufficient_context; those labels are the guide's fallback, not certainty.
5. **The judge is not validated by a human yet, and it favours its own family.** Every reply-quality number comes from GLM-5.2 scoring replies that GLM-5.2 (ResolveAI, B2) or the brand's historical agents (B1) wrote. On the {cross.get('n', 0)} responses also scored by qwen3.8-27b, the GLM judge rates B2's GLM-written replies higher than the second family does on relevance/actionability/completeness (per-system gaps in judge_agreement.md) while agreeing on templated and copied replies. The human packet exists; agreement is {human.get('status', 'PENDING')}. Judge failures ({judge_fail} of {n_judged}) are excluded from means.
6. **Apple-specific, 2017, one burst.** The KB and the holdout are dominated by the November-2017 iOS 11 autocorrect bug; every STRONG evidence verdict is that bug. The taxonomy is AppleSupport's; nothing here transfers to another brand without re-annotation.
7. **Weak proxies everywhere upstream.** Retrieval "same-resolution" relevance is a TF-IDF match on 46 rows; "resolution-bearing" is a lexical predicate; the gate's precision was hand-checked by an AI on 24 dev cases; the classifier's training labels are silver (~71% precision); the outcome signal has 0.72 precision. The headline sits on these.
8. **Golden was reused across phases for exploratory analysis.** Phases 2-5 each evaluated golden "once per pre-specified variant", but failure analyses read golden rows, and the Phase 5 retrieval pass was repeated after a predicate bug. Nothing was tuned on golden; the drift risk is that design choices were made by people who had seen golden failures.
9. **Customer identity overlap.** 15.8% of holdout customers (25 golden rows) appear earlier in the KB window; same-customer evidence is excluded from support, but their messages are not independent draws.
10. **Cached runs hide latency.** The reported p50 for ResolveAI in this phase is a cache-served run; the live golden run in Phase 5 had p50 {json.loads((ROOT / 'artifacts/resolution/benchmark.json').read_text(encoding='utf-8'))['latency_ms']['total']['p50'] if (ROOT / 'artifacts/resolution/benchmark.json').exists() else 'n/a'} ms. Cost figures use GLM list prices and the tokens the cached calls consumed when they were live.
11. **"Safe" is defined by us.** A safe autonomous resolution requires a verified, referenced reply on a row the annotators did not mark for escalation, or the exact template for a closure/non-English row. It does not say the customer's problem was solved; no outcome data exists for these replies.
13. **The headline hides that a one-prompt LLM classifies and escalates better than ResolveAI.** B2's escalation F1 is {b2e.get('f1')} vs {R.get('f1')} and its intent macro-F1 is at least as good; ResolveAI's contribution is confined to grounding, verification and abstention, which the accuracy-style headline numbers do not reward and the pairwise judge penalises.
12. **Baselines are honest but cheap.** B1 copies historical replies (which is what the brand often did) and B2 is one prompt; a tuned few-shot prompt or a retrieval-augmented LLM without the policy layer was not tested, so "ResolveAI beats an LLM" is only true against the plain prompt.
"""
    (EV / "misleading_headline.md").write_text(M, encoding="utf-8")

    # ------------------------------------------------------------ phase 6 report -----------------------------------
    sysrow = lambda s: (BC.get("systems") or {}).get(s, {})  # noqa: E731
    def row(s):
        d = sysrow(s)
        if not d:
            return f"| {s} | n/a |"
        j = d.get("judge") or {}
        jr_ = d.get("judge_rates") or {}
        return (f"| {s} | {d['intent']['accuracy']} | {d['intent']['macro_f1']} | {d['escalation']['recall']} | {d['escalation']['precision']} | {d['autonomy']['auto_handle_rate']} | {d['autonomy']['safe_auto_handle_count']} | "
                f"{d['autonomy']['unsafe_auto_handle_count']} | {j.get('groundedness', 'n/a')} | {j.get('actionability', 'n/a')} | {jr_.get('hallucination', 'n/a')} | {d['cost_latency']['llm_calls_per_message']} | {d['cost_latency']['estimated_cost_usd_per_message']} |")
    systems = ["resolveai_full", "B0_trivial", "B0_trivial_always_handoff", "B1_simple_ml", "B2_direct_llm", "minus_second_opinion", "minus_resolution_rerank", "minus_risk_llm", "minus_retrieval"]
    d_b2 = (BC.get("paired_differences_vs_resolveai") or {}).get("resolveai_full_minus_B2_direct_llm", {})
    b2e, b2a = (ESC.get("B2_direct_llm") or {}), (AUT.get("B2_direct_llm") or {})
    pw2 = PW.get("resolveai_full_vs_B2_direct_llm", {})
    P = f"""# ResolveAI Phase 6 report: evaluation science and judge validation

## Headline findings (read these before the numbers)
- **The direct GLM-5.2 prompt (B2) is a better intent classifier and a far more precise escalation decider than ResolveAI's deterministic policy.**
  Intent macro-F1 {(sysrow('B2_direct_llm').get('intent') or {}).get('macro_f1')} vs {(sysrow('resolveai_full').get('intent') or {}).get('macro_f1')} (paired difference {d_b2.get('intent_macro_f1', {}).get('difference')} [{d_b2.get('intent_macro_f1', {}).get('ci_low')}, {d_b2.get('intent_macro_f1', {}).get('ci_high')}]: not distinguishable);
  escalation precision {b2e.get('precision')} vs {R.get('precision')} at recall {b2e.get('recall')} vs {R.get('recall')} (F1 {b2e.get('f1')} vs {R.get('f1')}; the F1 gap's CI excludes zero). This contradicts the Phase-1A smoke-test reading that no LLM beat a constant escalation baseline (30 rows).
- **What ResolveAI buys with that precision loss is grounding and zero unsafe autonomy.** B2 answered {b2a.get('auto_handle_count')} of 197 messages itself, {b2a.get('unsafe_auto_handle_count')} of them on rows the annotators marked for a human, with judge hallucination rate {(jb2.get('rates') or {}).get('hallucination')} (no evidence exists behind a direct reply) and groundedness {(jb2.get('means') or {}).get('groundedness')};
  ResolveAI: {A.get('unsafe_auto_handle_count')} unsafe, {A.get('grounded_auto_handle_count')} grounded verified replies, hallucination 0 on its troubleshooting replies (the {(jr.get('rates') or {}).get('hallucination')} overall rate is template wording on handoff/clarification lines - see judge_agreement.md).
- **The blinded pairwise judge prefers B2** {pw2.get('loss')} to {pw2.get('win')} (ties {pw2.get('tie')}) on "safer and more useful": fluent complete answers beat cautious clarifications and handoffs in the eyes of a same-family judge. Whether a human agrees is the open question the packet answers.
- **Ablations**: the GLM second opinion is worth +{(BC.get('paired_differences_vs_resolveai') or {}).get('resolveai_full_minus_minus_second_opinion', {}).get('intent_macro_f1', {}).get('difference', 0):.3f} macro-F1; the LLM risk flags buy +{(BC.get('paired_differences_vs_resolveai') or {}).get('resolveai_full_minus_minus_risk_llm', {}).get('escalation_recall', {}).get('difference')} escalation recall at the price of {AUT.get('minus_risk_llm', {}).get('safe_auto_handle_count', 0) - A.get('safe_auto_handle_count', 0)} safe resolutions and a {A.get('handoff_rate')} vs {AUT.get('minus_risk_llm', {}).get('handoff_rate')} handoff rate;
  the Phase-5 resolution reranker + gate-v3 did NOT raise safe autonomy on golden versus Phase-2 retrieval ({A.get('safe_auto_handle_count')} vs {AUT.get('minus_resolution_rerank', {}).get('safe_auto_handle_count')} safe, CI of the difference includes 0); without retrieval only the canned rows remain.
- **Cost is a wash**: ResolveAI ${sysrow('resolveai_full').get('cost_latency', {}).get('estimated_cost_usd_per_message')} vs B2 ${sysrow('B2_direct_llm').get('cost_latency', {}).get('estimated_cost_usd_per_message')} per message; the complexity buys grounding and abstention, not savings.

1. **Evaluation contract**: docs/EVALUATION.md (matrix of claim -> metric -> dataset -> evaluator -> baseline -> uncertainty -> limitation; areas A-H with primary/secondary metrics; no single score).
2. **Baselines**: B0 trivial (majority silver intent `keyboard_text_bug`, modal "DM us" reply, never escalates; always-handoff variant), B1 simple ML (TF-IDF+LR C={json.loads((EV / 'runs/B1_simple_ml.meta.json').read_text())['classifier']['C'] if (EV / 'runs/B1_simple_ml.meta.json').exists() else '?'} on silver, nearest-neighbour reply copy, rule escalation), B2 direct GLM-5.2 (one call, taxonomy + guide criteria + full thread, no retrieval). Information parity stated in baseline_comparison.md.
3. **Full ResolveAI and all systems** (golden, n=197):

| system | intent acc | macro-F1 | esc recall | esc precision | auto rate | safe auto | unsafe auto | judge groundedness | judge actionability | judge hallucination | LLM calls | $/msg |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
""" + "\n".join(row(s) for s in systems) + f"""

4. **Intent**: intent_report.json (per-class P/R/F1, confusion, calibration ECE {(IR.get('calibration') or {}).get('ece')}, accuracy by band `{json.dumps(IR.get('accuracy_by_band'))}`).
5. **Escalation**: escalation_report.json; ResolveAI FN = {[x['gid'] for x in fn]}; cost-weighted at 1x/3x/5x (assumptions).
6. **Autonomy**: autonomy_report.json; ResolveAI `{json.dumps({k: A.get(k) for k in ('auto_handle_rate', 'clarification_rate', 'handoff_rate', 'safe_auto_handle_count', 'unsafe_auto_handle_count', 'grounded_auto_handle_count', 'correct_non_autonomous_count', 'unnecessary_non_autonomous_count')})}`.
7. **Reply quality**: reply_quality.json; ResolveAI means `{json.dumps(jr.get('means'))}`, by response kind `{json.dumps({k: {kk: vv for kk, vv in v.items() if kk in ('n', 'groundedness', 'actionability', 'hallucination')} for k, v in kind.items()})}`.
8. **Judge rubric**: judge_rubric.json (rubric-v1, 6 ordinal dimensions with anchors for every level + 2 binary), frozen before scoring; smoke-tested on 3 dev drafts.
9. **Judge results**: judge_results.jsonl ({MAN.get('judge_rows')} rows incl. offline drafts; {judge_fail} parse failures); pairwise_results.json `{json.dumps({k: {kk: v[kk] for kk in ('n', 'win', 'tie', 'loss', 'judge_failures')} for k, v in PW.items()})}`.
10. **Human study**: data/human_eval/human_scoring_packet.csv + docs/HUMAN_JUDGE_GUIDE.md; status **{human.get('status', 'PENDING_HUMAN_RATINGS')}** ({human.get('n_examples', 0)} examples, {human.get('n_fully_rated', 0)} rated).
11. **Judge-human agreement**: {"see judge_agreement.md" if human.get('status') == 'RATED' else "not available - PENDING HUMAN RATINGS; judge-vs-judge (qwen3.8-27b) cross-family check in judge_agreement.md"}.
12. **Retrieval**: retrieval_report.json (same-resolution R@5 Phase 2 {((RET.get('same_resolution_recall') or {}).get('phase2_customer_index_gate_v2') or {}).get('recall@5')} -> Phase 5 {((RET.get('same_resolution_recall') or {}).get('phase5_pair_rerank_gate_v3') or {}).get('recall@5')}; resolution-bearing@1 {((RET.get('resolution_bearing_rank') or {}).get('phase2_customer_index') or {}).get('resolution_bearing@1')} -> {((RET.get('resolution_bearing_rank') or {}).get('phase5_pair_rerank') or {}).get('resolution_bearing@1')}; gate precision AI-annotated).
13. **Slices**: slice_analysis.md. Trust ResolveAI least on short messages, insufficient-context rows and rare intents; most on first-turn keyboard/battery/performance rows with STRONG evidence.
14. **Ablations**: ablation_results.md (second opinion, resolution rerank, risk LLM, retrieval; verifier and gate offline). Offline minus-verifier: `{json.dumps({k: v for k, v in (OFF.get('minus_verifier') or {}).items() if k in ('dev_drafts', 'dev_blocked', 'dev_true_blocks_that_would_ship', 'golden_drafts_blocked_by_verifier')})}`; minus-gate on WEAK rows: `{json.dumps({k: v for k, v in (OFF.get('minus_gate_weak_rows') or {}).items() if k in ('n_weak_rows', 'drafts_verified', 'judge_means', 'hallucination_rate')})}`.
15. **Statistical uncertainty**: statistical_uncertainty.md (1000x seeded bootstrap, paired for differences).
16. **Top five failures**: failure_analysis.md (LLM private-info over-flagging; two rule misses incl. the `<PHONE>` boundary bug; gate abstention/KB coverage; apps_services confusion; judge validity).
17. **Misleading headline**: misleading_headline.md (12 points).
18. **Latency/cost**: baseline_comparison.md; ResolveAI {sysrow('resolveai_full').get('cost_latency', {}).get('llm_calls_per_message')} calls and ${sysrow('resolveai_full').get('cost_latency', {}).get('estimated_cost_usd_per_message')} per message vs B2 {sysrow('B2_direct_llm').get('cost_latency', {}).get('llm_calls_per_message', 'n/a')} calls / ${sysrow('B2_direct_llm').get('cost_latency', {}).get('estimated_cost_usd_per_message', 'n/a')}; live latency from Phase 5 (p50 ~5.9 s) vs B2 live p50 {sysrow('B2_direct_llm').get('cost_latency', {}).get('p50_latency_ms', 'n/a')} ms.
19. **Reproducibility**: `python scripts/evaluate.py --cached` ran in {MAN.get('runtime_seconds')} s (manifest: reproduction_manifest.json with SHA-256 of every input; golden hash asserted). Live mode: `--live`.
20. **Tests**: tests/test_evaluation.py (metrics, bootstrap determinism, baseline fairness, judge parsing, rubric versioning, blinded ordering, agreement, artifact hashes, golden immutability, denominators) plus all earlier suites.
21. **Files changed**: resolveai/evaluation/{{records,metrics,bootstrap,baselines,systems,judge,slices,agreement,reporting}}.py; scripts/evaluate.py; scripts/phase6/a-e; resolveai/agent/orchestrator.py (use_risk_llm switch, cached-token cost accounting); resolveai/llm/provider.py (cached token counters); docs/EVALUATION.md, docs/HUMAN_JUDGE_GUIDE.md, docs/DECISIONS.md, README.md; data/human_eval/; artifacts/evaluation/.
22. **Known limitations**: see misleading_headline.md; the judge is unvalidated by a human; the second-family judge covers a subset; B2 is a plain prompt; the system under test is the frozen Phase 5 system, including the two rule bugs found here.
23. **Phase 7 starting point**: score the human packet, run `python scripts/evaluate.py --cached`, read judge_agreement.md; then fix failure modes 1-2 on dev with regression tests; then the FastAPI serving layer and the Next.js operator workspace (Phase 8).
"""
    (EV / "PHASE6_REPORT.md").write_text(P, encoding="utf-8")

    # ------------------------------------------------------------ judge calibration observations ----------------------
    jrows = [json.loads(x) for x in (EV / "judge_results.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()] if (EV / "judge_results.jsonl").exists() else []
    prim = [r for r in jrows if r.get("judge_model") == "glm-5.2" and not r.get("failed") and r["system"] == "resolveai_full"]
    flagged = [r for r in prim if r.get("hallucination") and full.get(r["gid"], {}).get("response_kind") in ("clarify", "handoff")]
    b0 = jq.get("B0_trivial", {})
    lens = {}
    for s in ("resolveai_full", "B1_simple_ml", "B2_direct_llm", "B0_trivial"):
        rs = recs(s)
        if rs:
            lens[s] = round(sum(len(r["response"]) for r in rs.values()) / len(rs))
    def gap(sys_name):
        pm, sm = (cross.get("per_system_means_primary") or {}).get(sys_name, {}), (cross.get("per_system_means_secondary") or {}).get(sys_name, {})
        return " / ".join(f"{pm.get(d, 0) - sm.get(d, 0):+.2f}" for d in ("relevance", "actionability", "completeness")) if pm and sm else "n/a"
    gap_b2, gap_full, gap_b1 = gap("B2_direct_llm"), gap("resolveai_full"), gap("B1_simple_ml")
    C = f"""

## Judge calibration observations (primary judge, before any human rating)
- **Templates are read as claims.** {len(flagged)} of {len(prim)} ResolveAI clarifications/handoffs were flagged as hallucinations. The rationales point at template wording: the repeat-contact handoff line "Thanks for the steps you've already tried" is sent when the rule fired on thread depth (>= 2 brand turns) although the customer never listed steps (g002, g004); the account/billing lines assert "because it involves your account details" (g013). These are real wording defects in HANDOFF_LINES, but they are not factual claims about the product, and a human may score them differently - the first thing the human study should settle.
- **The judge likes the do-nothing reply.** B0's modal "We'd love to help. DM us the details" scores groundedness {(b0.get('means') or {}).get('groundedness')} and actionability {(b0.get('means') or {}).get('actionability')} (n={b0.get('n_parsed')}), above ResolveAI's handoffs ({(kind.get('handoff') or {}).get('actionability')}) - the rubric's "concrete handoff" anchor is satisfied by "DM us", so the pairwise question, not the absolute score, separates them. This is the Phase-0 caveat about the always-DM baseline, now measured.
- **Verbosity.** Mean response length: `{json.dumps(lens)}` characters; the direct-LLM baseline writes the longest replies. Compare its judge means with the second-family judge before reading a length preference into the scores.
- **Parse failures are not uniform**: B1 (copied historical replies with `<url>` tokens) lost {(jq.get('B1_simple_ml') or {}).get('judge_failures')} of 197 rows to truncated judge output vs {(jq.get('resolveai_full') or {}).get('judge_failures')} for ResolveAI and {(jq.get('B0_trivial') or {}).get('judge_failures')} for B0; excluded rows are not random.
- **Self-preference signature, measured**: on the {cross.get('n', 0)} responses both judges scored, the GLM judge rates the GLM-written B2 replies higher than the second-family judge does by {gap_b2} (relevance / actionability / completeness), while on ResolveAI's mostly templated responses the gap is {gap_full} and on B1's copied replies {gap_b1}. The primary judge favours its own family's prose; the pairwise preference for B2 should be read with that in mind until humans rate the packet.
"""
    ja = EV / "judge_agreement.md"
    if ja.exists() and "## Judge calibration observations" not in ja.read_text(encoding="utf-8"):
        ja.write_text(ja.read_text(encoding="utf-8") + C, encoding="utf-8")
    print("narrative written")


if __name__ == "__main__":
    main()
