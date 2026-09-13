# Slice analysis (per system; n = rows in slice)

Slices come from the frozen golden flags (short, multi-turn, seen customer, multi-intent, taxonomy gap, insufficient context, rare intent) and from each system's own outputs (confidence band, evidence sufficiency).

## resolveai_full

| slice | n | intent acc | esc recall (n gold esc) | false esc rate | auto | clarify | handoff | unsafe auto | evidence sufficient |
|---|---|---|---|---|---|---|---|---|---|
| all | 197 | 0.848 | 0.946 (37) | 0.544 | 0.046 | 0.335 | 0.619 | 0 | 0.036 |
| short_message | 45 | 0.689 | 0.667 (3) | 0.643 | 0.044 | 0.311 | 0.644 | 0 | 0.022 |
| normal_message | 152 | 0.895 | 0.971 (34) | 0.508 | 0.046 | 0.342 | 0.612 | 0 | 0.039 |
| first_turn | 149 | 0.846 | 0.917 (24) | 0.488 | 0.04 | 0.403 | 0.557 | 0 | 0.04 |
| multi_turn | 48 | 0.854 | 1.0 (13) | 0.743 | 0.062 | 0.125 | 0.812 | 0 | 0.021 |
| customer_seen_in_kb | 25 | 0.8 | 0.857 (7) | 0.444 | 0.04 | 0.4 | 0.56 | 0 | 0.0 |
| customer_unseen | 172 | 0.855 | 0.967 (30) | 0.556 | 0.047 | 0.326 | 0.628 | 0 | 0.041 |
| multi_intent | 10 | 0.8 | 1.0 (1) | 0.444 | 0.0 | 0.5 | 0.5 | 0 | 0.0 |
| taxonomy_gap | 7 | 1.0 | 1.0 (2) | 0.4 | 0.0 | 0.429 | 0.571 | 0 | 0.0 |
| insufficient_context | 18 | 0.667 | 0.5 (2) | 0.438 | 0.0 | 0.556 | 0.444 | 0 | 0.0 |
| evidence_unavailable | 31 | 0.871 | 1.0 (3) | 0.429 | 0.032 | 0.484 | 0.484 | 0 | 0.0 |
| gold_should_escalate | 37 | 0.865 | 0.946 (37) | None | 0.0 | 0.054 | 0.946 | 0 | 0.0 |
| gold_should_not_escalate | 160 | 0.844 | None (0) | 0.544 | 0.056 | 0.4 | 0.544 | 0 | 0.044 |
| common_intent | 149 | 0.839 | 0.917 (24) | 0.544 | 0.04 | 0.356 | 0.604 | 0 | 0.047 |
| rare_intent | 48 | 0.875 | 1.0 (13) | 0.543 | 0.062 | 0.271 | 0.667 | 0 | 0.0 |
| confidence_HIGH | 53 | 0.925 | 1.0 (5) | 0.583 | 0.094 | 0.283 | 0.623 | 0 | 0.113 |
| confidence_MEDIUM | 106 | 0.849 | 0.957 (23) | 0.542 | 0.028 | 0.34 | 0.632 | 0 | 0.009 |
| confidence_LOW | 38 | 0.737 | 0.889 (9) | 0.483 | 0.026 | 0.395 | 0.579 | 0 | 0.0 |
| evidence_sufficient | 7 | 1.0 | None (0) | 0.286 | 0.714 | 0.0 | 0.286 | 0 | 1.0 |
| evidence_insufficient | 190 | 0.842 | 0.946 (37) | 0.556 | 0.021 | 0.347 | 0.632 | 0 | 0.0 |

## B1_simple_ml

| slice | n | intent acc | esc recall (n gold esc) | false esc rate | auto | clarify | handoff | unsafe auto | evidence sufficient |
|---|---|---|---|---|---|---|---|---|---|
| all | 197 | 0.543 | 0.757 (37) | 0.181 | 0.711 | 0.0 | 0.289 | 9 | 0.0 |
| short_message | 45 | 0.467 | 0.333 (3) | 0.071 | 0.911 | 0.0 | 0.089 | 2 | 0.0 |
| normal_message | 152 | 0.566 | 0.794 (34) | 0.22 | 0.651 | 0.0 | 0.349 | 7 | 0.0 |
| first_turn | 149 | 0.617 | 0.833 (24) | 0.16 | 0.732 | 0.0 | 0.268 | 4 | 0.0 |
| multi_turn | 48 | 0.312 | 0.615 (13) | 0.257 | 0.646 | 0.0 | 0.354 | 5 | 0.0 |
| customer_seen_in_kb | 25 | 0.48 | 0.571 (7) | 0.111 | 0.76 | 0.0 | 0.24 | 3 | 0.0 |
| customer_unseen | 172 | 0.552 | 0.8 (30) | 0.19 | 0.703 | 0.0 | 0.297 | 6 | 0.0 |
| multi_intent | 10 | 0.4 | 1.0 (1) | 0.333 | 0.6 | 0.0 | 0.4 | 0 | 0.0 |
| taxonomy_gap | 7 | 0.0 | 0.5 (2) | 0.0 | 0.857 | 0.0 | 0.143 | 1 | 0.0 |
| insufficient_context | 18 | 0.667 | 0.0 (2) | 0.125 | 0.889 | 0.0 | 0.111 | 2 | 0.0 |
| evidence_unavailable | 31 | 0.581 | 0.667 (3) | 0.107 | 0.839 | 0.0 | 0.161 | 1 | 0.0 |
| gold_should_escalate | 37 | 0.568 | 0.757 (37) | None | 0.243 | 0.0 | 0.757 | 9 | 0.0 |
| gold_should_not_escalate | 160 | 0.537 | None (0) | 0.181 | 0.819 | 0.0 | 0.181 | 0 | 0.0 |
| common_intent | 149 | 0.51 | 0.792 (24) | 0.216 | 0.691 | 0.0 | 0.309 | 5 | 0.0 |
| rare_intent | 48 | 0.646 | 0.692 (13) | 0.057 | 0.771 | 0.0 | 0.229 | 4 | 0.0 |
| evidence_insufficient | 197 | 0.543 | 0.757 (37) | 0.181 | 0.711 | 0.0 | 0.289 | 9 | 0.0 |

## B2_direct_llm

| slice | n | intent acc | esc recall (n gold esc) | false esc rate | auto | clarify | handoff | unsafe auto | evidence sufficient |
|---|---|---|---|---|---|---|---|---|---|
| all | 197 | 0.878 | 0.919 (37) | 0.075 | 0.766 | 0.0 | 0.234 | 3 | 0.0 |
| short_message | 45 | 0.778 | 0.667 (3) | 0.048 | 0.911 | 0.0 | 0.089 | 1 | 0.0 |
| normal_message | 152 | 0.908 | 0.941 (34) | 0.085 | 0.724 | 0.0 | 0.276 | 2 | 0.0 |
| first_turn | 149 | 0.872 | 1.0 (24) | 0.048 | 0.799 | 0.0 | 0.201 | 0 | 0.0 |
| multi_turn | 48 | 0.896 | 0.769 (13) | 0.171 | 0.667 | 0.0 | 0.333 | 3 | 0.0 |
| customer_seen_in_kb | 25 | 0.8 | 0.857 (7) | 0.0 | 0.76 | 0.0 | 0.24 | 1 | 0.0 |
| customer_unseen | 172 | 0.89 | 0.933 (30) | 0.085 | 0.767 | 0.0 | 0.233 | 2 | 0.0 |
| multi_intent | 10 | 0.8 | 1.0 (1) | 0.333 | 0.6 | 0.0 | 0.4 | 0 | 0.0 |
| taxonomy_gap | 7 | 1.0 | 1.0 (2) | 0.4 | 0.429 | 0.0 | 0.571 | 0 | 0.0 |
| insufficient_context | 18 | 0.722 | 1.0 (2) | 0.062 | 0.833 | 0.0 | 0.167 | 0 | 0.0 |
| evidence_unavailable | 31 | 0.871 | 1.0 (3) | 0.0 | 0.903 | 0.0 | 0.097 | 0 | 0.0 |
| gold_should_escalate | 37 | 0.946 | 0.919 (37) | None | 0.081 | 0.0 | 0.919 | 3 | 0.0 |
| gold_should_not_escalate | 160 | 0.863 | None (0) | 0.075 | 0.925 | 0.0 | 0.075 | 0 | 0.0 |
| common_intent | 149 | 0.859 | 0.917 (24) | 0.088 | 0.779 | 0.0 | 0.221 | 2 | 0.0 |
| rare_intent | 48 | 0.938 | 0.923 (13) | 0.029 | 0.729 | 0.0 | 0.271 | 1 | 0.0 |
| evidence_insufficient | 197 | 0.878 | 0.919 (37) | 0.075 | 0.766 | 0.0 | 0.234 | 3 | 0.0 |

## ResolveAI intent calibration (confidence = calibrated top-class probability)

ECE 0.2845 over 197 rows

| bin | n | mean confidence | accuracy |
|---|---|---|---|
| [0.0, 0.2) | 8 | 0.188 | 0.75 |
| [0.2, 0.4) | 60 | 0.308 | 0.75 |
| [0.4, 0.6) | 38 | 0.509 | 0.842 |
| [0.6, 0.8) | 52 | 0.698 | 0.904 |
| [0.8, 1.0] | 39 | 0.905 | 0.949 |

| band | n | accuracy |
|---|---|---|
| HIGH | 53 | 0.925 |
| MEDIUM | 106 | 0.849 |
| LOW | 38 | 0.737 |

Selective prediction (answer only when confidence >= t):

| threshold | coverage | n | accuracy |
|---|---|---|---|
| 0.0 | 1.0 | 197 | 0.848 |
| 0.3 | 0.827 | 163 | 0.877 |
| 0.4 | 0.655 | 129 | 0.899 |
| 0.5 | 0.579 | 114 | 0.904 |
| 0.6 | 0.462 | 91 | 0.923 |
| 0.7 | 0.325 | 64 | 0.938 |
| 0.75 | 0.269 | 53 | 0.925 |
| 0.8 | 0.198 | 39 | 0.949 |
| 0.9 | 0.096 | 19 | 1.0 |