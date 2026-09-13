# Resolution-aware drafting A/B (Phase 5-C, DEV)

13 draftable dev cases (gate-v3 sufficient, rules-only policy allows automation); levels {'STRONG': np.int64(13)}.

| metric | A draft-v1 | B draft-v2 |
|---|---|---|
| verifier_block_rate | 0.538 | 0.385 |
| evidence_support_rate | 0.615 | 0.692 |
| llm_unsupported_rate | 0.308 | 0.308 |
| ask_only_rate | 0.154 | 0.0 |
| actionable_resolution_rate | 0.692 | 0.923 |
| mentions_top_cluster_action | 0.846 | 0.923 |
| verified_and_actionable | 0.462 | 0.615 |
| mean_coverage | 0.564 | 0.655 |
| retry_rate | 0.0 | 0.0 |
| latency_ms_p50 | 36 | 19691 |
| tokens_out_mean | 162.1 | 1602.5 |

Blocking checks A: `{'llm_support_check': np.int64(4), 'evidence_refs': np.int64(2), 'evidence_coverage': np.int64(1)}`
Blocking checks B: `{'llm_support_check': np.int64(4), 'draft_failed': np.int64(1)}`

Per-draft records: draft_experiment.jsonl (input to the verifier analysis).