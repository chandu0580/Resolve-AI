# Statistical uncertainty

Bootstrap: resample the 197 golden rows with replacement 1000 times (numpy default_rng seed 42), recompute the statistic, report the 2.5/97.5 percentiles. Paired comparisons resample the same row indices for both systems. Failed calls stay in every sample. Judge intervals resample the parsed judge rows (judge failures excluded from means but reported).

| system | intent accuracy | intent macro-F1 | escalation recall | escalation F1 | safe auto rate | judge groundedness | judge hallucination |
|---|---|---|---|---|---|---|---|
| resolveai_full | 0.848 [0.797, 0.898] | 0.854 [0.799, 0.901] | 0.946 [0.862, 1.000] | 0.440 [0.331, 0.530] | 0.046 [0.020, 0.076] | 4.284 [4.124, 4.438] | 0.216 [0.160, 0.273] |
| B0_trivial | 0.081 [0.046, 0.122] | 0.014 [0.008, 0.020] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 4.985 [4.965, 5.000] | 0.000 [0.000, 0.000] |
| B0_trivial_always_handoff | 0.081 [0.046, 0.122] | 0.014 [0.008, 0.020] | 1.000 [1.000, 1.000] | 0.316 [0.233, 0.385] | 0.000 [0.000, 0.000] | n/a | n/a |
| B1_simple_ml | 0.543 [0.472, 0.614] | 0.550 [0.472, 0.615] | 0.757 [0.613, 0.889] | 0.596 [0.460, 0.706] | 0.066 [0.035, 0.107] | 4.284 [4.085, 4.460] | 0.171 [0.119, 0.233] |
| B2_direct_llm | 0.878 [0.827, 0.919] | 0.887 [0.835, 0.927] | 0.919 [0.828, 1.000] | 0.819 [0.719, 0.900] | 0.000 [0.000, 0.000] | 3.227 [3.015, 3.438] | 0.526 [0.454, 0.593] |
| minus_second_opinion | 0.614 [0.548, 0.680] | 0.618 [0.546, 0.677] | 0.973 [0.909, 1.000] | 0.459 [0.353, 0.544] | 0.046 [0.020, 0.076] | n/a | n/a |
| minus_resolution_rerank | 0.848 [0.797, 0.898] | 0.854 [0.799, 0.901] | 0.946 [0.862, 1.000] | 0.429 [0.322, 0.518] | 0.056 [0.025, 0.091] | n/a | n/a |
| minus_risk_llm | 0.848 [0.797, 0.898] | 0.854 [0.799, 0.901] | 0.730 [0.571, 0.871] | 0.486 [0.354, 0.603] | 0.091 [0.051, 0.137] | n/a | n/a |
| minus_retrieval | 0.848 [0.797, 0.898] | 0.854 [0.799, 0.901] | 0.946 [0.862, 1.000] | 0.440 [0.331, 0.530] | 0.020 [0.005, 0.041] | n/a | n/a |

Escalation recall rests on 37 gold positives: one more missed escalation moves it by 2.7 points. Safe-auto rates rest on 9 autonomous rows. Intervals that overlap heavily are reported as not distinguishable in the reports.