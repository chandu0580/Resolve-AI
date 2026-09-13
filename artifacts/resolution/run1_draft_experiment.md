# Resolution-aware drafting A/B (Phase 5-C, DEV)

13 draftable dev cases (gate-v3 sufficient, rules-only policy allows automation); levels {'STRONG': np.int64(13)}.

| metric | A draft-v1 | B draft-v2 |
|---|---|---|
| verifier_block_rate | 0.538 | 0.538 |
| evidence_support_rate | 0.769 | 1.0 |
| llm_unsupported_rate | 0.231 | 0.0 |
| ask_only_rate | 0.077 | 0.0 |
| actionable_resolution_rate | 0.615 | 0.538 |
| mentions_top_cluster_action | 0.769 | 0.538 |
| verified_and_actionable | 0.462 | 0.462 |
| mean_coverage | 0.518 | 0.479 |
| retry_rate | 0.0 | 0.0 |
| latency_ms_p50 | 12865 | 17403 |
| tokens_out_mean | 880.8 | 1229.5 |

Blocking checks A: `{'llm_support_check': np.int64(3), 'evidence_refs': np.int64(2), 'draft_failed': np.int64(2)}`
Blocking checks B: `{'draft_failed': np.int64(6), 'no_pii': np.int64(1)}`

Per-draft records: draft_experiment.jsonl (input to the verifier analysis).