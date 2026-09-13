# Reply-side, dual and resolution-reranked retrieval (Phase 5-A)

Same protocol as Phase 2 (same-resolution TF-IDF judge, 46 golden references; DEV 500 for tuning; GOLDEN once per variant). resolution_bearing@k = a substantive reply whose non-question sentences state an instruction or released fix (resolution.is_resolution_bearing) in the top-k. gate_precision_same_resolution_hit@5 is the automatic judge's hit rate among SUFFICIENT cases with a reference; it was 0 for every variant including Phase 2's, as in Phase 2, so the gate is calibrated on hand-checked DEV verdicts (gate_v3_handcheck_sheet.md / gate_v3_handcheck.json).

## DEV (tuning)

| variant | recall@1 | recall@3 | recall@5 | mrr | resolution_bearing@1 | resolution_bearing@3 | resolution_bearing@5 | resolution_mrr | same_intent@5 | sufficient_rate | gate_precision_resolution_bearing@5 | gate_precision_same_resolution_hit@5 | p50 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A_customer_v2 | 0.1791 | 0.194 | 0.209 | 0.1903 | 0.16 | 0.366 | 0.51 | 0.2847 | 0.878 | 0.062 | 0.9032 | 0.0 | 74.9 |
| B_reply_v2 | 0.0149 | 0.0299 | 0.0299 | 0.0224 | 0.108 | 0.214 | 0.34 | 0.1827 | 0.782 | 0.0 | None | None | 15.7 |
| B2_pair_v2 | 0.194 | 0.194 | 0.209 | 0.197 | 0.228 | 0.392 | 0.504 | 0.3237 | 0.834 | 0.022 | 1.0 | 0.0 | 13.9 |
| C_dual_customer_reply_v2 | 0.1194 | 0.2239 | 0.2239 | 0.1692 | 0.138 | 0.296 | 0.412 | 0.2319 | 0.842 | 0.008 | 1.0 | 0.0 | 26.5 |
| C2_dual_customer_pair_v2 | 0.194 | 0.209 | 0.209 | 0.199 | 0.204 | 0.388 | 0.512 | 0.3136 | 0.852 | 0.058 | 0.9655 | 0.0 | 27.3 |
| D_B2_pair_rr_v3__loosest_gate | 0.1642 | 0.194 | 0.209 | 0.1779 | 0.776 | 0.776 | 0.776 | 0.776 | 0.934 | 0.048 | 1.0 | 0.0 | 19.2 |
| D_B2_pair_rr_v3 | 0.1642 | 0.194 | 0.209 | 0.1779 | 0.776 | 0.776 | 0.776 | 0.776 | 0.934 | 0.028 | 1.0 | 0.0 | 57.3 |

## GOLDEN (once)

| variant | recall@1 | recall@3 | recall@5 | mrr | resolution_bearing@1 | resolution_bearing@3 | resolution_bearing@5 | resolution_mrr | same_intent@5 | sufficient_rate | gate_precision_resolution_bearing@5 | gate_precision_same_resolution_hit@5 | p50 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A_customer_v2 | 0.2174 | 0.2826 | 0.3478 | 0.2652 | 0.1777 | 0.3706 | 0.4467 | 0.2765 | 0.6244 | 0.0711 | 0.8571 | 0.0 | 58.2 |
| B_reply_v2 | 0.0 | 0.0 | 0.0 | 0.0 | 0.1168 | 0.2437 | 0.3807 | 0.2024 | 0.5482 | 0.0 | None | None | 11.6 |
| B2_pair_v2 | 0.2391 | 0.3261 | 0.3478 | 0.2844 | 0.2234 | 0.3909 | 0.4721 | 0.3122 | 0.6548 | 0.0457 | 1.0 | 0.0 | 11.8 |
| C_dual_customer_reply_v2 | 0.1957 | 0.2609 | 0.2826 | 0.2337 | 0.1168 | 0.3147 | 0.4569 | 0.2297 | 0.6447 | 0.0051 | 1.0 | 0.0 | 18.0 |
| C2_dual_customer_pair_v2 | 0.2609 | 0.3043 | 0.3478 | 0.2899 | 0.198 | 0.3604 | 0.467 | 0.2909 | 0.6548 | 0.066 | 1.0 | 0.0 | 16.4 |
| D_B2_pair_rr_v3 | 0.1522 | 0.2609 | 0.2609 | 0.1957 | 0.7563 | 0.7563 | 0.7614 | 0.7574 | 0.731 | 0.0305 | 1.0 | None | 12.5 |

Selected dual variant (dev objective R@5 + resolution_bearing@3): `B2_pair_v2`
Frozen reranker weights (coordinate search on DEV, 17 evaluations): `{'w_customer': 0.35, 'w_reply': 0.25, 'w_intent': 0.1, 'w_resolution': 0.2, 'w_quality': 0.05, 'w_outcome': 0.01, 'w_dup': 0.15, 'w_dm': 0.2, 'w_same': 0.3, 'version': 'rerank-v1'}`
Frozen gate-v3: `share0.6_ms3` = `{'support_similarity': 0.85, 'min_support': 3, 'min_top_share': 0.6, 't_weak': 0.35, 't_sufficient': 0.55, 't_strong': 0.75, 'min_query_tokens': 3, 'require_symptom_term': True, 'relevance_floor': 0.55, 'version': 'gate-v3'}`

## Gate-v3 candidates on DEV (hand-checked by an AI annotator)

| candidate | n sufficient | coverage | RESOLVES | PARTIAL | ASK | WRONG | precision (R+P) |
|---|---|---|---|---|---|---|---|
| share0.5_ms2 | 24 | 0.048 | 16 | 3 | 0 | 5 | 0.792 |
| share0.6_ms2 | 22 | 0.044 | 16 | 2 | 0 | 4 | 0.818 |
| share0.7_ms2 | 20 | 0.04 | 15 | 1 | 0 | 4 | 0.8 |
| share0.6_ms3 (chosen) | 14 | 0.028 | 11 | 2 | 0 | 1 | 0.929 |
| share0.7_ms3 | 12 | 0.024 | 10 | 1 | 0 | 1 | 0.917 |

Golden gate levels (final): {"INSUFFICIENT": 173, "WEAK": 18, "STRONG": 6}
Golden consistency (final): {"no_resolution": 172, "consistent": 21, "mixed_resolution": 4}

## Slices (golden, final variant)

| slice | n | recall@5 | resolution_bearing@5 | sufficient |
|---|---|---|---|---|
| short | 45 | 0.0 | 0.7556 | 0.044 |
| multi_turn | 48 | 0.1667 | 0.7917 | 0.021 |
| first_turn | 149 | 0.2941 | 0.7517 | 0.034 |
| customer_seen_in_kb | 25 | 0.0 | 0.64 | 0.0 |
| multi_intent | 10 | 0.0 | 1.0 | 0.0 |
| insufficient_context | 18 | 0.0 | 0.8889 | 0.056 |