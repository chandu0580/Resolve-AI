# Phase 9 final evaluation (golden set, n=197)

Golden sha256 `33f4f333ccf10de7f628e57b5567a7930852cdf5b6d4bba872555b96b2bec3a9`. 95% bootstrap intervals (1,000 resamples, seed 42). Baselines and Phase 5 are the frozen Phase 6 runs, re-scored with the same code; Phase 8 and Phase 9 are single runs of the current code.

| metric | Baseline B1 (simple ML) | Baseline B2 (direct LLM) | Phase 5 (evaluated in Phase 6) | Phase 8 = Phase 9 final |
|---|---|---|---|---|
| intent accuracy | 0.543 [0.472, 0.614] | 0.878 [0.827, 0.919] | 0.848 [0.797, 0.898] | 0.848 [0.797, 0.898] |
| intent macro-F1 | 0.550 [0.472, 0.615] | 0.887 [0.835, 0.927] | 0.854 [0.799, 0.901] | 0.854 [0.799, 0.901] |
| escalation precision | 0.491 | 0.739 | 0.287 | 0.293 |
| escalation recall | 0.757 [0.613, 0.889] | 0.919 [0.828, 1.000] | 0.946 [0.862, 1.000] | 0.973 [0.912, 1.000] |
| escalation F1 | 0.596 [0.460, 0.706] | 0.819 [0.719, 0.900] | 0.440 [0.331, 0.530] | 0.450 [0.340, 0.539] |
| missed escalations (FN) | 9 | 3 | 2 | 1 |
| unnecessary escalations (FP) | 29 | 12 | 87 | 87 |
| auto / clarify / handoff | 0.711 / 0.000 / 0.289 | 0.766 / 0.000 / 0.234 | 0.046 / 0.335 / 0.619 | 0.046 / 0.330 / 0.624 |
| safe auto-handle rate | 0.066 [0.035, 0.107] | 0.000 [0.000, 0.000] | 0.046 [0.020, 0.076] | 0.046 [0.020, 0.076] |
| unsafe autonomous replies | 9 | 3 | 0 | 0 |
| grounded auto replies | 0 | 0 | 5 | 5 |
| judge groundedness (1-5) | 4.28 [4.09, 4.46] | 3.23 [3.02, 3.44] | 4.28 [4.12, 4.44] | 4.19 [4.03, 4.36] |
| judge hallucination rate | 0.170 | 0.526 | 0.216 | 0.283 |
| judge policy-violation rate | 0.040 | 0.010 | 0.015 | 0.016 |
| p50 / p95 latency ms (as run) | 114.3 / 197.7 | 6543.1 / 21539.1 | 117.3 / 241.8 | 254.7 / 862.6 |
| model calls per message | 0.0 | 1.071 | 1.553 | 1.538 |
| live model calls per message | 0.0 | 1.071 | 0.0 | 0.0 |
| est. cost per message (USD) | 0.0 | 0.002366 | 0.002608 | 0.002559 |
| failed executions | 0 | 1 | 0 | 0 |

## Paired differences (Phase 9 final minus other; 95% paired bootstrap)

- `phase9_final_minus_resolveai_full`: intent_macro_f1 +0.000 [+0.000, +0.000]; escalation_f1 +0.010 [+0.000, +0.032]; escalation_recall +0.027 [+0.000, +0.091]; safe_auto_rate +0.000 [+0.000, +0.000]
- `phase9_final_minus_B2_direct_llm`: intent_macro_f1 -0.033 [-0.082, +0.014]; escalation_f1 -0.369 [-0.476, -0.277] (excludes 0); escalation_recall +0.054 [-0.045, +0.158]; safe_auto_rate +0.046 [+0.020, +0.076] (excludes 0)

## Decisions that changed from Phase 5 to Phase 9 (2 rows)

| gid | Phase 5 | Phase 9 | gold should_escalate | gold reason |
|---|---|---|---|---|
| g002 | HUMAN_HANDOFF/repeat_contact | HUMAN_HANDOFF/private_info | True | private_info |
| g157 | CLARIFICATION_REQUIRED/low_confidence | HUMAN_HANDOFF/private_info | True | private_info |
