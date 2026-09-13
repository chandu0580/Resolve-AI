# Agent latency and cost (golden run)

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

`{"llm_calls_per_message": 2.437, "live_calls_per_message": 1.665, "cache_hit_rate": 0.3167, "tokens_in_per_message": 734.4, "tokens_out_per_message": 1186.6, "estimated_cost_usd_per_message": 0.004532, "fallbacks": 54, "calls_by_action": {"HUMAN_HANDOFF": 2.48, "CLARIFICATION_REQUIRED": 2.43, "AUTO_HANDLE": 2.18}, "wall_seconds": 2205.8}`

Second-opinion calls were cached from Phase 3 (same prompt version); risk, draft and verify calls were live. Costs use GLM-5.2 list price; the proxy's billing is unknown.