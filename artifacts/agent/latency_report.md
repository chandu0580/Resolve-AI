# Agent latency and cost

Numbers from **run 1** (live LLM calls; run 2 re-used 95% cached calls and is not representative of latency). Windows 11, AMD 8-core CPU, GLM-5.2 via the user's proxy.

| stage | p50 ms | p95 ms | n |
|---|---|---|---|
| context | 0.1 | 0.4 | 197 |
| intent | 47.8 | 91.9 | 197 |
| second_opinion | 1.6 | 3.7 | 197 |
| retrieval | 54.8 | 113.3 | 197 |
| risk | 10510.1 | 18802.7 | 197 |
| policy | 0.0 | 0.1 | 197 |
| draft | 0.0 | 0.1 | 197 |
| verification | 0.0 | 0.0 | 197 |
| output_gate | 0.0 | 0.1 | 197 |
| handoff | 0.1 | 0.2 | 108 |
| total | 10874.8 | 25114.2 | 197 |

Run 1 usage: `{"llm_calls_per_message": 2.437, "live_calls_per_message": 1.665, "cache_hit_rate": 0.3167, "tokens_in_per_message": 734.4, "tokens_out_per_message": 1186.6, "estimated_cost_usd_per_message": 0.004532, "fallbacks": 54, "calls_by_action": {"HUMAN_HANDOFF": 2.48, "CLARIFICATION_REQUIRED": 2.43, "AUTO_HANDLE": 2.18}, "wall_seconds": 2205.8}`

Run 2 usage (cached): `{"llm_calls_per_message": 2.31, "live_calls_per_message": 0.117, "cache_hit_rate": 0.9495, "tokens_in_per_message": 42.4, "tokens_out_per_message": 69.8, "estimated_cost_usd_per_message": 0.000266, "fallbacks": 45, "calls_by_action": {"HUMAN_HANDOFF": 2.2, "CLARIFICATION_REQUIRED": 2.43, "AUTO_HANDLE": 2.7}, "wall_seconds": 163.4}`

Reading: the local path (context, classifier, retrieval, policy, gate) is ~100 ms; every LLM call adds ~5 s at p50 and a retry on truncated JSON doubles it. The risk call is now skipped when rules already hard-block; drafting and verification only run for the ~6% of messages that reach a sufficient-evidence auto path. Query embedding sharing: 93.3 -> 89.5 ms p50 on the deterministic path (`embedding_sharing.json`).

Cost uses GLM-5.2 list price ($1.00 / $3.20 per 1M tokens); the proxy's real billing is unknown. Hidden reasoning tokens dominate output tokens (~1,190 out vs ~730 in per message in run 1).