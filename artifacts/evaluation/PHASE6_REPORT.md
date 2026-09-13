# ResolveAI Phase 6 report: evaluation science and judge validation

## Headline findings (read these before the numbers)
- **The direct GLM-5.2 prompt (B2) is a better intent classifier and a far more precise escalation decider than ResolveAI's deterministic policy.**
  Intent macro-F1 0.8867 vs 0.8538 (paired difference -0.0329 [-0.0823, 0.0137]: not distinguishable);
  escalation precision 0.7391 vs 0.2869 at recall 0.9189 vs 0.9459 (F1 0.8193 vs 0.4403; the F1 gap's CI excludes zero). This contradicts the Phase-1A smoke-test reading that no LLM beat a constant escalation baseline (30 rows).
- **What ResolveAI buys with that precision loss is grounding and zero unsafe autonomy.** B2 answered 151 of 197 messages itself, 3 of them on rows the annotators marked for a human, with judge hallucination rate 0.526 (no evidence exists behind a direct reply) and groundedness 3.227;
  ResolveAI: 0 unsafe, 5 grounded verified replies, hallucination 0 on its troubleshooting replies (the 0.216 overall rate is template wording on handoff/clarification lines - see judge_agreement.md).
- **The blinded pairwise judge prefers B2** 125 to 63 (ties 7) on "safer and more useful": fluent complete answers beat cautious clarifications and handoffs in the eyes of a same-family judge. Whether a human agrees is the open question the packet answers.
- **Ablations**: the GLM second opinion is worth +0.236 macro-F1; the LLM risk flags buy +0.2162 escalation recall at the price of 9 safe resolutions and a 0.6193 vs 0.3756 handoff rate;
  the Phase-5 resolution reranker + gate-v3 did NOT raise safe autonomy on golden versus Phase-2 retrieval (9 vs 11 safe, CI of the difference includes 0); without retrieval only the canned rows remain.
- **Cost is a wash**: ResolveAI $0.002608 vs B2 $0.002366 per message; the complexity buys grounding and abstention, not savings.

1. **Evaluation contract**: docs/EVALUATION.md (matrix of claim -> metric -> dataset -> evaluator -> baseline -> uncertainty -> limitation; areas A-H with primary/secondary metrics; no single score).
2. **Baselines**: B0 trivial (majority silver intent `keyboard_text_bug`, modal "DM us" reply, never escalates; always-handoff variant), B1 simple ML (TF-IDF+LR C=8.0 on silver, nearest-neighbour reply copy, rule escalation), B2 direct GLM-5.2 (one call, taxonomy + guide criteria + full thread, no retrieval). Information parity stated in baseline_comparison.md.
3. **Full ResolveAI and all systems** (golden, n=197):

| system | intent acc | macro-F1 | esc recall | esc precision | auto rate | safe auto | unsafe auto | judge groundedness | judge actionability | judge hallucination | LLM calls | $/msg |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| resolveai_full | 0.8477 | 0.8538 | 0.9459 | 0.2869 | 0.0457 | 9 | 0 | 4.284 | 2.928 | 0.216 | 1.553 | 0.002608 |
| B0_trivial | 0.0812 | 0.0137 | 0.0 | 0.0 | 1.0 | 0 | 37 | 4.985 | 3.782 | 0.0 | 0.0 | 0.0 |
| B0_trivial_always_handoff | 0.0812 | 0.0137 | 1.0 | 0.1878 | 0.0 | 0 | 0 | n/a | n/a | n/a | 0.0 | 0.0 |
| B1_simple_ml | 0.5431 | 0.5498 | 0.7568 | 0.4912 | 0.7107 | 13 | 9 | 4.284 | 3.142 | 0.17 | 0.0 | 0.0 |
| B2_direct_llm | 0.8782 | 0.8867 | 0.9189 | 0.7391 | 0.7665 | 0 | 3 | 3.227 | 4.077 | 0.526 | 1.071 | 0.002366 |
| minus_second_opinion | 0.6142 | 0.6182 | 0.973 | 0.3 | 0.0457 | 9 | 0 | n/a | n/a | n/a | 0.797 | 0.001734 |
| minus_resolution_rerank | 0.8477 | 0.8538 | 0.9459 | 0.2778 | 0.0558 | 11 | 0 | n/a | n/a | n/a | 1.538 | 0.00253 |
| minus_risk_llm | 0.8477 | 0.8538 | 0.7297 | 0.3649 | 0.0914 | 18 | 0 | n/a | n/a | n/a | 0.858 | 0.001053 |
| minus_retrieval | 0.8477 | 0.8538 | 0.9459 | 0.2869 | 0.0203 | 4 | 0 | n/a | n/a | n/a | 1.487 | 0.002478 |

4. **Intent**: intent_report.json (per-class P/R/F1, confusion, calibration ECE 0.2845, accuracy by band `{"HIGH": {"n": 53, "accuracy": 0.925}, "MEDIUM": {"n": 106, "accuracy": 0.849}, "LOW": {"n": 38, "accuracy": 0.737}}`).
5. **Escalation**: escalation_report.json; ResolveAI FN = ['g048', 'g157']; cost-weighted at 1x/3x/5x (assumptions).
6. **Autonomy**: autonomy_report.json; ResolveAI `{"auto_handle_rate": 0.0457, "clarification_rate": 0.335, "handoff_rate": 0.6193, "safe_auto_handle_count": 9, "unsafe_auto_handle_count": 0, "grounded_auto_handle_count": 5, "correct_non_autonomous_count": 37, "unnecessary_non_autonomous_count": 151}`.
7. **Reply quality**: reply_quality.json; ResolveAI means `{"groundedness": 4.284, "relevance": 3.361, "actionability": 2.928, "completeness": 2.567, "policy_compliance": 4.485, "tone": 4.376}`, by response kind `{"handoff": {"n": 119, "groundedness": 4.33, "actionability": 2.53, "hallucination": 0.218}, "clarify": {"n": 66, "groundedness": 4.17, "actionability": 3.53, "hallucination": 0.242}, "troubleshoot": {"n": 5, "groundedness": 4.2, "actionability": 4.0, "hallucination": 0.0}, "canned": {"n": 4, "groundedness": 5.0, "actionability": 3.5, "hallucination": 0.0}}`.
8. **Judge rubric**: judge_rubric.json (rubric-v1, 6 ordinal dimensions with anchors for every level + 2 binary), frozen before scoring; smoke-tested on 3 dev drafts.
9. **Judge results**: judge_results.jsonl (931 rows incl. offline drafts; 27 parse failures); pairwise_results.json `{"resolveai_full_vs_B1_simple_ml": {"n": 197, "win": 100, "tie": 13, "loss": 84, "judge_failures": 0}, "resolveai_full_vs_B2_direct_llm": {"n": 197, "win": 63, "tie": 7, "loss": 125, "judge_failures": 2}}`.
10. **Human study**: data/human_eval/human_scoring_packet.csv + docs/HUMAN_JUDGE_GUIDE.md; status **RATED** (50 examples, 50 rated).
11. **Judge-human agreement**: see judge_agreement.md.
12. **Retrieval**: retrieval_report.json (same-resolution R@5 Phase 2 0.3478 -> Phase 5 0.2609; resolution-bearing@1 0.1777 -> 0.7563; gate precision AI-annotated).
13. **Slices**: slice_analysis.md. Trust ResolveAI least on short messages, insufficient-context rows and rare intents; most on first-turn keyboard/battery/performance rows with STRONG evidence.
14. **Ablations**: ablation_results.md (second opinion, resolution rerank, risk LLM, retrieval; verifier and gate offline). Offline minus-verifier: `{"dev_drafts": 25, "dev_blocked": 11, "dev_true_blocks_that_would_ship": 6, "golden_drafts_blocked_by_verifier": 0}`; minus-gate on WEAK rows: `{"n_weak_rows": 15, "drafts_verified": 10, "judge_means": {"groundedness": 4.5, "relevance": 4.79, "actionability": 4.21, "completeness": 3.64, "policy_compliance": 4.93, "tone": 4.86}, "hallucination_rate": 0.071}`.
15. **Statistical uncertainty**: statistical_uncertainty.md (1000x seeded bootstrap, paired for differences).
16. **Top five failures**: failure_analysis.md (LLM private-info over-flagging; two rule misses incl. the `<PHONE>` boundary bug; gate abstention/KB coverage; apps_services confusion; judge validity).
17. **Misleading headline**: misleading_headline.md (12 points).
18. **Latency/cost**: baseline_comparison.md; ResolveAI 1.553 calls and $0.002608 per message vs B2 1.071 calls / $0.002366; live latency from Phase 5 (p50 ~5.9 s) vs B2 live p50 6543.1 ms.
19. **Reproducibility**: `python scripts/evaluate.py --cached` ran in 129.3 s (manifest: reproduction_manifest.json with SHA-256 of every input; golden hash asserted). Live mode: `--live`.
20. **Tests**: tests/test_evaluation.py (metrics, bootstrap determinism, baseline fairness, judge parsing, rubric versioning, blinded ordering, agreement, artifact hashes, golden immutability, denominators) plus all earlier suites.
21. **Files changed**: resolveai/evaluation/{records,metrics,bootstrap,baselines,systems,judge,slices,agreement,reporting}.py; scripts/evaluate.py; scripts/phase6/a-e; resolveai/agent/orchestrator.py (use_risk_llm switch, cached-token cost accounting); resolveai/llm/provider.py (cached token counters); docs/EVALUATION.md, docs/HUMAN_JUDGE_GUIDE.md, docs/DECISIONS.md, README.md; data/human_eval/; artifacts/evaluation/.
22. **Known limitations**: see misleading_headline.md; the judge is unvalidated by a human; the second-family judge covers a subset; B2 is a plain prompt; the system under test is the frozen Phase 5 system, including the two rule bugs found here.
23. **Phase 7 starting point**: score the human packet, run `python scripts/evaluate.py --cached`, read judge_agreement.md; then fix failure modes 1-2 on dev with regression tests; then the FastAPI serving layer and the Next.js operator workspace (Phase 8).
