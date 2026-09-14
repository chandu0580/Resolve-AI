# Slice analysis (per system; n = rows in slice)

Slices come from the frozen golden flags (short, multi-turn, seen customer, multi-intent, taxonomy gap, insufficient context, rare intent) and from each system's own outputs (confidence band, evidence sufficiency).

## resolveai_full

| slice | n | intent acc | esc recall (n gold esc) | false esc rate | auto | clarify | handoff | unsafe auto | evidence sufficient |
|---|---|---|---|---|---|---|---|---|---|
| all | 197 | 0.832 | 0.927 (41) | 0.538 | 0.046 | 0.335 | 0.619 | 0 | 0.036 |
| short_message | 45 | 0.667 | 0.5 (4) | 0.659 | 0.044 | 0.311 | 0.644 | 0 | 0.022 |
| normal_message | 152 | 0.882 | 0.973 (37) | 0.496 | 0.046 | 0.342 | 0.612 | 0 | 0.039 |
| first_turn | 149 | 0.839 | 0.889 (27) | 0.484 | 0.04 | 0.403 | 0.557 | 0 | 0.04 |
| multi_turn | 48 | 0.812 | 1.0 (14) | 0.735 | 0.062 | 0.125 | 0.812 | 0 | 0.021 |
| customer_seen_in_kb | 25 | 0.76 | 0.857 (7) | 0.444 | 0.04 | 0.4 | 0.56 | 0 | 0.0 |
| customer_unseen | 172 | 0.843 | 0.941 (34) | 0.551 | 0.047 | 0.326 | 0.628 | 0 | 0.041 |
| multi_intent | 10 | 0.8 | 1.0 (2) | 0.375 | 0.0 | 0.5 | 0.5 | 0 | 0.0 |
| taxonomy_gap | 7 | 1.0 | 1.0 (2) | 0.4 | 0.0 | 0.429 | 0.571 | 0 | 0.0 |
| insufficient_context | 18 | 0.667 | 0.333 (3) | 0.467 | 0.0 | 0.556 | 0.444 | 0 | 0.0 |
| evidence_unavailable | 31 | 0.871 | 0.75 (4) | 0.444 | 0.032 | 0.484 | 0.484 | 0 | 0.0 |
| gold_should_escalate | 41 | 0.805 | 0.927 (41) | None | 0.0 | 0.073 | 0.927 | 0 | 0.0 |
| gold_should_not_escalate | 156 | 0.84 | None (0) | 0.538 | 0.058 | 0.404 | 0.538 | 0 | 0.045 |
| common_intent | 152 | 0.816 | 0.897 (29) | 0.537 | 0.039 | 0.355 | 0.605 | 0 | 0.046 |
| rare_intent | 45 | 0.889 | 1.0 (12) | 0.545 | 0.067 | 0.267 | 0.667 | 0 | 0.0 |
| confidence_HIGH | 53 | 0.906 | 1.0 (6) | 0.574 | 0.094 | 0.283 | 0.623 | 0 | 0.113 |
| confidence_MEDIUM | 106 | 0.84 | 0.96 (25) | 0.531 | 0.028 | 0.34 | 0.632 | 0 | 0.009 |
| confidence_LOW | 38 | 0.711 | 0.8 (10) | 0.5 | 0.026 | 0.395 | 0.579 | 0 | 0.0 |
| evidence_sufficient | 7 | 1.0 | None (0) | 0.286 | 0.714 | 0.0 | 0.286 | 0 | 1.0 |
| evidence_insufficient | 190 | 0.826 | 0.927 (41) | 0.55 | 0.021 | 0.347 | 0.632 | 0 | 0.0 |

## B1_simple_ml

| slice | n | intent acc | esc recall (n gold esc) | false esc rate | auto | clarify | handoff | unsafe auto | evidence sufficient |
|---|---|---|---|---|---|---|---|---|---|
| all | 197 | 0.528 | 0.756 (41) | 0.167 | 0.711 | 0.0 | 0.289 | 10 | 0.0 |
| short_message | 45 | 0.422 | 0.25 (4) | 0.073 | 0.911 | 0.0 | 0.089 | 3 | 0.0 |
| normal_message | 152 | 0.559 | 0.811 (37) | 0.2 | 0.651 | 0.0 | 0.349 | 7 | 0.0 |
| first_turn | 149 | 0.604 | 0.815 (27) | 0.148 | 0.732 | 0.0 | 0.268 | 5 | 0.0 |
| multi_turn | 48 | 0.292 | 0.643 (14) | 0.235 | 0.646 | 0.0 | 0.354 | 5 | 0.0 |
| customer_seen_in_kb | 25 | 0.48 | 0.571 (7) | 0.111 | 0.76 | 0.0 | 0.24 | 3 | 0.0 |
| customer_unseen | 172 | 0.535 | 0.794 (34) | 0.174 | 0.703 | 0.0 | 0.297 | 7 | 0.0 |
| multi_intent | 10 | 0.4 | 1.0 (2) | 0.25 | 0.6 | 0.0 | 0.4 | 0 | 0.0 |
| taxonomy_gap | 7 | 0.0 | 0.5 (2) | 0.0 | 0.857 | 0.0 | 0.143 | 1 | 0.0 |
| insufficient_context | 18 | 0.611 | 0.0 (3) | 0.133 | 0.889 | 0.0 | 0.111 | 3 | 0.0 |
| evidence_unavailable | 31 | 0.581 | 0.5 (4) | 0.111 | 0.839 | 0.0 | 0.161 | 2 | 0.0 |
| gold_should_escalate | 41 | 0.561 | 0.756 (41) | None | 0.244 | 0.0 | 0.756 | 10 | 0.0 |
| gold_should_not_escalate | 156 | 0.519 | None (0) | 0.167 | 0.833 | 0.0 | 0.167 | 0 | 0.0 |
| common_intent | 152 | 0.493 | 0.793 (29) | 0.195 | 0.691 | 0.0 | 0.309 | 6 | 0.0 |
| rare_intent | 45 | 0.644 | 0.667 (12) | 0.061 | 0.778 | 0.0 | 0.222 | 4 | 0.0 |
| evidence_insufficient | 197 | 0.528 | 0.756 (41) | 0.167 | 0.711 | 0.0 | 0.289 | 10 | 0.0 |

## B2_direct_llm

| slice | n | intent acc | esc recall (n gold esc) | false esc rate | auto | clarify | handoff | unsafe auto | evidence sufficient |
|---|---|---|---|---|---|---|---|---|---|
| all | 197 | 0.853 | 0.854 (41) | 0.071 | 0.766 | 0.0 | 0.234 | 6 | 0.0 |
| short_message | 45 | 0.711 | 0.5 (4) | 0.049 | 0.911 | 0.0 | 0.089 | 2 | 0.0 |
| normal_message | 152 | 0.895 | 0.892 (37) | 0.078 | 0.724 | 0.0 | 0.276 | 4 | 0.0 |
| first_turn | 149 | 0.852 | 0.926 (27) | 0.041 | 0.799 | 0.0 | 0.201 | 2 | 0.0 |
| multi_turn | 48 | 0.854 | 0.714 (14) | 0.176 | 0.667 | 0.0 | 0.333 | 4 | 0.0 |
| customer_seen_in_kb | 25 | 0.76 | 0.857 (7) | 0.0 | 0.76 | 0.0 | 0.24 | 1 | 0.0 |
| customer_unseen | 172 | 0.866 | 0.853 (34) | 0.08 | 0.767 | 0.0 | 0.233 | 5 | 0.0 |
| multi_intent | 10 | 0.8 | 1.0 (2) | 0.25 | 0.6 | 0.0 | 0.4 | 0 | 0.0 |
| taxonomy_gap | 7 | 1.0 | 1.0 (2) | 0.4 | 0.429 | 0.0 | 0.571 | 0 | 0.0 |
| insufficient_context | 18 | 0.611 | 0.667 (3) | 0.067 | 0.833 | 0.0 | 0.167 | 1 | 0.0 |
| evidence_unavailable | 31 | 0.839 | 0.75 (4) | 0.0 | 0.903 | 0.0 | 0.097 | 1 | 0.0 |
| gold_should_escalate | 41 | 0.878 | 0.854 (41) | None | 0.146 | 0.0 | 0.854 | 6 | 0.0 |
| gold_should_not_escalate | 156 | 0.846 | None (0) | 0.071 | 0.929 | 0.0 | 0.071 | 0 | 0.0 |
| common_intent | 152 | 0.836 | 0.828 (29) | 0.081 | 0.776 | 0.0 | 0.224 | 5 | 0.0 |
| rare_intent | 45 | 0.911 | 0.917 (12) | 0.03 | 0.733 | 0.0 | 0.267 | 1 | 0.0 |
| evidence_insufficient | 197 | 0.853 | 0.854 (41) | 0.071 | 0.766 | 0.0 | 0.234 | 6 | 0.0 |

## ResolveAI intent calibration (confidence = calibrated top-class probability)

ECE 0.2693 over 197 rows

| bin | n | mean confidence | accuracy |
|---|---|---|---|
| [0.0, 0.2) | 8 | 0.188 | 0.75 |
| [0.2, 0.4) | 60 | 0.308 | 0.717 |
| [0.4, 0.6) | 38 | 0.509 | 0.842 |
| [0.6, 0.8) | 52 | 0.698 | 0.904 |
| [0.8, 1.0] | 39 | 0.905 | 0.923 |

| band | n | accuracy |
|---|---|---|
| HIGH | 53 | 0.906 |
| MEDIUM | 106 | 0.84 |
| LOW | 38 | 0.711 |

Selective prediction (answer only when confidence >= t):

| threshold | coverage | n | accuracy |
|---|---|---|---|
| 0.0 | 1.0 | 197 | 0.832 |
| 0.3 | 0.827 | 163 | 0.859 |
| 0.4 | 0.655 | 129 | 0.891 |
| 0.5 | 0.579 | 114 | 0.895 |
| 0.6 | 0.462 | 91 | 0.912 |
| 0.7 | 0.325 | 64 | 0.922 |
| 0.75 | 0.269 | 53 | 0.906 |
| 0.8 | 0.198 | 39 | 0.923 |
| 0.9 | 0.096 | 19 | 1.0 |