# Phase 5 latency and cost (golden run)

| stage | p50 ms | p95 ms | n |
|---|---|---|---|
| context | 0.2 | 0.5 | 197 |
| intent | 86.4 | 183.1 | 197 |
| second_opinion | 15.5 | 5689.1 | 197 |
| retrieval | 87.6 | 211.4 | 197 |
| risk | 5037.3 | 22032.1 | 197 |
| policy | 0.0 | 0.1 | 197 |
| draft | 0.0 | 0.0 | 197 |
| verification | 0.0 | 0.0 | 197 |
| output_gate | 0.0 | 0.1 | 197 |
| handoff | 0.1 | 0.2 | 122 |
| total | 5855.0 | 25054.8 | 197 |

`{"llm_calls_per_message": 1.553, "live_calls_per_message": 0.873, "cache_hit_rate": 0.4379, "tokens_in_per_message": 326.7, "tokens_out_per_message": 488.5, "estimated_cost_usd_per_message": 0.00189, "fallbacks": 4, "calls_by_action": {"HUMAN_HANDOFF": 1.23, "CLARIFICATION_REQUIRED": 1.94, "AUTO_HANDLE": 3.11}, "wall_seconds": 1474.2, "risk_calls_skipped_by_policy": 63, "risk_calls_skipped_by_rules": 10}`

Second-opinion calls were cache hits from Phase 3/4 (same prompt version); risk (v2), draft (v2) and verifier calls were live unless noted. Costs use GLM-5.2 list price; the proxy's billing is unknown.
Short-circuit and structured-output measurements on DEV: short_circuit.json, risk_hardening.json.