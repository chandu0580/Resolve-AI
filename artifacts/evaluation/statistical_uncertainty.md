# Statistical uncertainty

Bootstrap: resample the 197 golden rows with replacement 1000 times (numpy default_rng seed 42), recompute the statistic, report the 2.5/97.5 percentiles. Paired comparisons resample the same row indices for both systems. Failed calls stay in every sample. Judge intervals resample the parsed judge rows (judge failures excluded from means but reported).

| system | intent accuracy | intent macro-F1 | escalation recall | escalation F1 | safe auto rate | judge groundedness | judge hallucination |
|---|---|---|---|---|---|---|---|
| resolveai_full | 0.833 [0.782, 0.883] | 0.831 [0.771, 0.884] | 0.927 [0.838, 1.000] | 0.466 [0.366, 0.556] | 0.046 [0.020, 0.076] | 4.284 [4.124, 4.438] | 0.216 [0.160, 0.273] |
| B0_trivial | 0.086 [0.051, 0.127] | 0.014 [0.009, 0.021] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 4.985 [4.965, 5.000] | 0.000 [0.000, 0.000] |
| B0_trivial_always_handoff | 0.086 [0.051, 0.127] | 0.014 [0.009, 0.021] | 1.000 [1.000, 1.000] | 0.344 [0.264, 0.418] | 0.000 [0.000, 0.000] | n/a | n/a |
| B1_simple_ml | 0.528 [0.457, 0.604] | 0.530 [0.455, 0.594] | 0.756 [0.610, 0.886] | 0.633 [0.511, 0.741] | 0.066 [0.035, 0.107] | 4.284 [4.085, 4.460] | 0.171 [0.119, 0.233] |
| B2_direct_llm | 0.853 [0.802, 0.904] | 0.853 [0.793, 0.901] | 0.854 [0.735, 0.951] | 0.805 [0.706, 0.887] | 0.000 [0.000, 0.000] | 3.227 [3.015, 3.438] | 0.526 [0.454, 0.593] |
| minus_second_opinion | 0.604 [0.538, 0.670] | 0.608 [0.536, 0.669] | 0.951 [0.875, 1.000] | 0.484 [0.380, 0.573] | 0.046 [0.020, 0.076] | n/a | n/a |
| minus_resolution_rerank | 0.833 [0.782, 0.883] | 0.831 [0.771, 0.884] | 0.927 [0.838, 1.000] | 0.455 [0.355, 0.543] | 0.056 [0.025, 0.091] | n/a | n/a |
| minus_risk_llm | 0.833 [0.782, 0.883] | 0.831 [0.771, 0.884] | 0.732 [0.590, 0.857] | 0.522 [0.404, 0.635] | 0.091 [0.051, 0.137] | n/a | n/a |
| minus_retrieval | 0.833 [0.782, 0.883] | 0.831 [0.771, 0.884] | 0.927 [0.838, 1.000] | 0.466 [0.366, 0.556] | 0.020 [0.005, 0.041] | n/a | n/a |

Escalation recall rests on 37 gold positives: one more missed escalation moves it by 2.7 points. Safe-auto rates rest on 9 autonomous rows. Intervals that overlap heavily are reported as not distinguishable in the reports.