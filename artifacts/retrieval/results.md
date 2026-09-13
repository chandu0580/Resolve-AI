# Retrieval benchmark results (Phase 2)

Protocol: relevance = *resolution-match*: a retrieved KB case is relevant iff its brand reply is substantive and its reply-side TF-IDF cosine to the query's OWN historical reply is >= 0.5 (insensitive at 0.4/0.6). Queries whose own reply is a DM handoff, or has no match in the KB at that threshold, have no reference and are excluded from Recall/MRR. DEV = 500 non-golden holdout rows (tuning). GOLDEN = frozen 197, evaluated once per configuration.

Reference coverage on GOLDEN: `{"golden": 197, "substantive_own_reply": 117, "substantive_with_kb_match_at_tau": 46, "substantive_but_unmatchable_in_kb": 71, "dm_or_short_own_reply": 80}` -> Recall/MRR are computed on **46** queries; 95% bootstrap CI on recall@5 for the selected config: **[0.174, 0.457]**. Differences between configurations below are inside that interval.

## Experiment matrix

### DEV (67 queries with reference; default gate)

| config | recall@1 | recall@3 | recall@5 | mrr | same_intent_recall@5 | resolution_bearing_recall@5 | any_substantive@5 | duplicate_result_rate | no_result_rate |
|---|---|---|---|---|---|---|---|---|---|
| bm25 | 0.1642 | 0.1791 | 0.1791 | 0.1692 | 0.874 | 0.168 | 0.92 | 0.048 | 0.0 |
| dense:minilm | 0.194 | 0.209 | 0.209 | 0.199 | 0.878 | 0.16 | 0.908 | 0.058 | 0.0 |
| dense:bge-small | 0.1791 | 0.194 | 0.209 | 0.1896 | 0.878 | 0.156 | 0.908 | 0.062 | 0.0 |
| hybrid:minilm | 0.1642 | 0.1791 | 0.1791 | 0.1716 | 0.888 | 0.166 | 0.912 | 0.058 | 0.0 |
| hybrid:bge-small | 0.1493 | 0.194 | 0.209 | 0.1754 | 0.896 | 0.174 | 0.908 | 0.06 | 0.0 |
| hybrid:minilm+outcome | 0.1642 | 0.1791 | 0.209 | 0.1791 | 0.884 | 0.22 | 0.934 | 0.06 | 0.0 |
| hybrid:bge-small+outcome | 0.1493 | 0.209 | 0.209 | 0.1766 | 0.898 | 0.222 | 0.926 | 0.066 | 0.0 |
| hybrid:bge-small+subst | 0.194 | 0.209 | 0.209 | 0.2015 | 0.886 | 0.342 | 1.0 | 0.106 | 0.0 |
| hybrid:bge-small+outcome+subst | 0.194 | 0.209 | 0.209 | 0.2015 | 0.884 | 0.38 | 1.0 | 0.106 | 0.0 |
| hybrid:minilm+outcome+subst | 0.1791 | 0.194 | 0.209 | 0.1903 | 0.866 | 0.376 | 1.0 | 0.092 | 0.0 |
| dense:bge-small+subst | 0.1791 | 0.194 | 0.209 | 0.1903 | 0.878 | 0.296 | 1.0 | 0.122 | 0.0 |
| dense:minilm+subst | 0.209 | 0.209 | 0.209 | 0.209 | 0.856 | 0.322 | 1.0 | 0.096 | 0.0 |

### GOLDEN (46 queries with reference; evaluated once)

| config | recall@1 | recall@3 | recall@5 | mrr | same_intent_recall@5 | resolution_bearing_recall@5 | any_substantive@5 | duplicate_result_rate | no_result_rate | latency p50/p95 ms |
|---|---|---|---|---|---|---|---|---|---|---|
| bm25 | 0.2391 | 0.2609 | 0.2609 | 0.25 | 0.6244 | 0.1929 | 0.9492 | 0.1117 | 0.0 | 116.2/260.2 |
| dense:minilm | 0.2391 | 0.3043 | 0.3261 | 0.2725 | 0.6701 | 0.1574 | 0.9239 | 0.1218 | 0.0 | 27.7/61.9 |
| dense:bge-small | 0.2174 | 0.2609 | 0.3261 | 0.2533 | 0.6497 | 0.132 | 0.8832 | 0.1421 | 0.0 | 74.1/137.1 |
| hybrid:minilm | 0.2826 | 0.2826 | 0.2826 | 0.2826 | 0.665 | 0.1624 | 0.9442 | 0.1117 | 0.0 | 94.7/192.7 |
| hybrid:bge-small | 0.2826 | 0.3043 | 0.3043 | 0.2935 | 0.6802 | 0.1574 | 0.8985 | 0.1117 | 0.0 | 109.3/230.1 |
| hybrid:minilm+outcome | 0.2826 | 0.2826 | 0.2826 | 0.2826 | 0.6548 | 0.1726 | 0.9442 | 0.1218 | 0.0 | 93.6/195.2 |
| hybrid:bge-small+outcome | 0.2826 | 0.3043 | 0.3043 | 0.2935 | 0.6751 | 0.1574 | 0.9137 | 0.1117 | 0.0 | 91.5/212.3 |
| hybrid:bge-small+subst | 0.2826 | 0.3043 | 0.3043 | 0.2935 | 0.665 | 0.2944 | 1.0 | 0.1777 | 0.0 | 92.3/196.3 |
| hybrid:bge-small+outcome+subst | 0.2826 | 0.3043 | 0.3043 | 0.2935 | 0.665 | 0.2944 | 1.0 | 0.1777 | 0.0 | 91.6/189.1 |
| hybrid:minilm+outcome+subst | 0.2826 | 0.2826 | 0.3043 | 0.287 | 0.6447 | 0.3604 | 1.0 | 0.1777 | 0.0 | 96.0/191.3 |
| dense:bge-small+subst **(final)** | 0.2174 | 0.2826 | 0.3478 | 0.2652 | 0.6244 | 0.2589 | 1.0 | 0.203 | 0.0 | 15.6/42.5 |
| dense:minilm+subst | 0.2609 | 0.3043 | 0.3261 | 0.288 | 0.6294 | 0.2995 | 1.0 | 0.203 | 0.0 | 16.9/50.1 |

RRF k sensitivity (DEV, hybrid:bge-small): `{'20': {'recall@5': 0.209, 'mrr': 0.1766}, '60': {'recall@5': 0.209, 'mrr': 0.1754}, '100': {'recall@5': 0.209, 'mrr': 0.1754}}` -> flat; k=20 kept.

Outcome-aware rerank bonus (with vs without, same config): DEV MRR 0.1791 vs 0.1716 (minilm hybrid), 0.1766 vs 0.1754 (bge hybrid); GOLDEN identical in every pair. **Measured effect: none beyond noise; disabled by default, kept as an explicit, auditable option.**

Substantive-first ordering (structural, not the outcome signal): raises 'any substantive reply in top-5' from 0.91 to 1.00 and, with the gate, is what makes sufficiency verdicts possible; ranking metrics unchanged.

## Difficult slices (GOLDEN, final config, gate-v2)

| slice | n | n_ref | recall@5 | mrr | same_intent_recall@5 | sufficient_rate |
|---|---|---|---|---|---|---|
| customer_seen_in_kb | 25 | 5 | 0.4 | 0.15 | 0.56 | 0.0 |
| short | 45 | 12 | 0.25 | 0.1458 | 0.3778 | 0.0667 |
| multi_turn | 48 | 12 | 0.25 | 0.1208 | 0.375 | 0.0417 |
| first_turn | 149 | 34 | 0.3824 | 0.3162 | 0.7047 | 0.0805 |
| multi_intent | 10 | 1 | 0.0 | 0.0 | 0.5 | 0.0 |
| taxonomy_gap | 7 | 0 | None | None | 0.5714 | 0.0 |
| insufficient_context | 18 | 1 | 0.0 | 0.0 | 0.8333 | 0.0556 |

## Evidence-sufficiency gate

| version | thresholds (support cosine / min support / intent agreement / min query tokens) | GOLDEN sufficient | reasons (GOLDEN) | hand-checked precision of 'sufficient' |
|---|---|---|---|---|
| gate-v1 (tuned on DEV vs automatic judge; no feasible point, strictest fallback) | 0.85 / 3 / 0.4 / - | 24/197 (12.2%) with hybrid:bge-small+subst | {'weak_similarity': 143, 'strong_consistent_evidence': 24, 'conflicting_evidence': 17, 'insufficient_resolution_evidence': 13} | 15/24 usable (62%); 6 degenerate queries, 3 clarify-only evidence |
| **gate-v2** (adds insufficient_query guard + resolution-bearing support; calibrated on hand-checked DEV verdicts) | 0.85 / 3 / 0.4 / 3 | 14/197 (7.1%) | {'weak_similarity': 117, 'insufficient_resolution_evidence': 30, 'conflicting_evidence': 20, 'insufficient_query': 15, 'strong_consistent_evidence': 14, 'ambiguous_intent': 1} | 13/14 usable (93%), 9/14 strictly (64%); 12 of 14 are the iOS-11 keyboard bug |

The automatic same-resolution judge cannot validate the gate: 17 of 24 v1 'sufficient' verdicts were on queries whose own reply was a DM handoff (unscorable), and it scored 0 of the remaining 7 as hits although 5 were usable on inspection. Gate precision is therefore reported from hand-checks (AI annotator, stated) and must be confirmed in the Phase 7 human study.

Hand-check protocol: DEV verdicts under the loosest thresholds (25) labelled usable/weak/no; every stricter grid point selects a subset, so the same labels score every point. Chosen: largest coverage with precision >= 0.75 (none qualified; strictest kept). Calibration grid in `gate_v2.json`.

## Latency and build cost (Windows 11, AMD 8-core, CPU only)

| item | value |
|---|---|
| BM25 index build | 0.5 s |
| MiniLM corpus embedding (17,875 rows), cold | 303 s |
| BGE-small corpus embedding, cold | 483 s |
| both, warm (cache) | 0 s |
| query latency, final dense:bge-small+subst | p50 14.9 ms, p95 34.9 ms, p99 45.1 ms |
| query latency, hybrid (adds BM25) | p50 92.3 ms, p95 196.3 ms |
| query latency, bm25 only | p50 116.2 ms |

Full benchmark wall time: 939 s (with cached embeddings). Reproduce: `python scripts/phase2/run_retrieval_benchmark.py && python scripts/phase2/extra_configs.py && python scripts/phase2/gate_v2_calibrate.py && python scripts/phase2/analyze_retrieval.py`.
