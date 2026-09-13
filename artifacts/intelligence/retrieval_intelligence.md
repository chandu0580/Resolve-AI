# Intent-aware retrieval (Phase 3-C)

Same protocol and retriever as Phase 2 (dense BGE-small, substantive-first, gate-v2). Variants: A raw message; B bounded context; C B + intent boost (RRF fusion, never discards); D C + canonical intent phrase at HIGH confidence.

## DEV (67 refs)

| variant | recall@1 | recall@3 | recall@5 | mrr | same_intent_recall@5 | resolution_bearing_recall@5 | any_substantive@5 | sufficient_rate | duplicate_result_rate | latency p50/p95 ms |
|---|---|---|---|---|---|---|---|---|---|---|
| A_raw | 0.1791 | 0.194 | 0.209 | 0.1903 | 0.878 | 0.296 | 1.0 | 0.062 | 0.122 | 31.8/65.0 |
| B_context | 0.1791 | 0.194 | 0.209 | 0.1903 | 0.854 | 0.282 | 1.0 | 0.062 | 0.114 | 15.6/62.8 |
| C_context_intent | 0.1791 | 0.209 | 0.209 | 0.1915 | 0.774 | 0.27 | 0.994 | 0.046 | 0.108 | 13.5/32.9 |
| D_context_intent_query | 0.1791 | 0.209 | 0.209 | 0.1915 | 0.762 | 0.252 | 1.0 | 0.052 | 0.122 | 64.8/137.0 |

## GOLDEN (46 refs; once)

| variant | recall@1 | recall@3 | recall@5 | mrr | same_intent_recall@5 | resolution_bearing_recall@5 | any_substantive@5 | sufficient_rate | duplicate_result_rate | latency p50/p95 ms |
|---|---|---|---|---|---|---|---|---|---|---|
| A_raw | 0.2174 | 0.2826 | 0.3478 | 0.2652 | 0.6244 | 0.2589 | 1.0 | 0.0711 | 0.203 | 34.3/62.5 |
| B_context | 0.2174 | 0.2826 | 0.3478 | 0.2652 | 0.6497 | 0.2487 | 1.0 | 0.0812 | 0.1929 | 14.4/52.1 |
| C_context_intent | 0.2174 | 0.3043 | 0.3261 | 0.2663 | 0.6701 | 0.2437 | 1.0 | 0.0711 | 0.1827 | 13.3/29.8 |
| D_context_intent_query | 0.2174 | 0.3043 | 0.3261 | 0.2663 | 0.6802 | 0.2386 | 0.9949 | 0.0609 | 0.1827 | 83.9/184.5 |

## Slices (GOLDEN recall@5 / sufficient rate)

| slice | A_raw | B_context | C_context_intent | D_context_intent_query |
|---|---|---|---|---|
| customer_seen_in_kb | 0.4 / 0.0 | 0.4 / 0.04 | 0.4 / 0.04 | 0.4 / 0.04 |
| short | 0.25 / 0.0667 | 0.25 / 0.1111 | 0.25 / 0.0889 | 0.25 / 0.0889 |
| multi_turn | 0.25 / 0.0417 | 0.25 / 0.0833 | 0.1667 / 0.0833 | 0.1667 / 0.0625 |
| first_turn | 0.3824 / 0.0805 | 0.3824 / 0.0805 | 0.3824 / 0.0671 | 0.3824 / 0.0604 |
| multi_intent | 0.0 / 0.0 | 0.0 / 0.0 | 0.0 / 0.0 | 0.0 / 0.0 |
| taxonomy_gap | None / 0.0 | None / 0.0 | None / 0.0 | None / 0.0 |
| insufficient_context | 0.0 / 0.0556 | 0.0 / 0.0556 | 0.0 / 0.0556 | 0.0 / 0.0556 |

## Stage latency (GOLDEN, variant D, ms)

p50: {'context': 0.24, 'classify': 1.62, 'query': 0.08, 'retrieve': 81.97}
p95: {'context': 0.68, 'classify': 2.68, 'query': 0.14, 'retrieve': 182.08}
