# Ablations (golden; each ablation is one switch on the production agent, nothing re-tuned)

| system | intent acc | intent macro-F1 | esc recall | esc precision | auto | clarify | handoff | safe auto | unsafe auto | evidence sufficient | LLM calls | $/msg |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| resolveai_full | 0.8477 | 0.8538 | 0.9459 | 0.2869 | 0.0457 | 0.335 | 0.6193 | 9 | 0 | 0.036 | 1.553 | 0.002608 |
| minus_second_opinion | 0.6142 | 0.6182 | 0.973 | 0.3 | 0.0457 | 0.3452 | 0.6091 | 9 | 0 | 0.036 | 0.797 | 0.001734 |
| minus_resolution_rerank | 0.8477 | 0.8538 | 0.9459 | 0.2778 | 0.0558 | 0.3046 | 0.6396 | 11 | 0 | 0.061 | 1.538 | 0.00253 |
| minus_risk_llm | 0.8477 | 0.8538 | 0.7297 | 0.3649 | 0.0914 | 0.533 | 0.3756 | 18 | 0 | 0.036 | 0.858 | 0.001053 |
| minus_retrieval | 0.8477 | 0.8538 | 0.9459 | 0.2869 | 0.0203 | 0.3604 | 0.6193 | 4 | 0 | 0.000 | 1.487 | 0.002478 |

Paired differences (ResolveAI minus ablation) are in baseline_comparison.json under paired_differences_vs_resolveai.

## Offline: minus verifier (never disabled on the production path)

`{"source": "Phase 5 dev drafting A/B (26 drafts, AI-audited) + golden run", "dev_drafts": 25, "dev_blocked": 11, "dev_true_blocks_that_would_ship": 6, "dev_true_block_ids": ["101285:A_v1", "506568:A_v1", "481855:A_v1", "599108:A_v1", "589479:A_v1", "2977723:A_v1"], "dev_false_blocks": 5, "golden_drafts_blocked_by_verifier": 0, "golden_blocked_gids": [], "reading": "without the verifier, every dev draft would ship: the hand-audit found 6 of 26 carried invented steps/actions or no evidence reference; on golden all 5 troubleshooting drafts passed, so the verifier changed nothing there (n=5)"}`

## Offline: minus gate on WEAK rows (abstention curve)

`{"n_weak_rows": 15, "drafts_failed": 1, "drafts_verified": 10, "on_gold_should_escalate": 0, "judged": 14, "judge_means": {"groundedness": 4.5, "relevance": 4.79, "actionability": 4.21, "completeness": 3.64, "policy_compliance": 4.93, "tone": 4.86}, "hallucination_rate": 0.071, "note": "gate verdict overridden inside this script only; production never drafts on WEAK evidence"}`

Reading: production drafts only on SUFFICIENT/STRONG evidence. Drafting on WEAK evidence would add the rows above; their judge scores and hallucination rate show the quality the gate is protecting.

Judge on WEAK-evidence drafts: n=14, means `{"groundedness": 4.5, "relevance": 4.786, "actionability": 4.214, "completeness": 3.643, "policy_compliance": 4.929, "tone": 4.857}`, hallucination 0.071 vs STRONG-evidence production drafts `{"n": 5, "groundedness": 4.2, "relevance": 5.0, "actionability": 4.0, "completeness": 3.8, "policy_compliance": 5.0, "tone": 4.8, "hallucination": 0.0}`.