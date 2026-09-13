# Baseline comparison (golden, n=197, evaluated once per system)

all systems receive the PII-redacted current message and the prior thread turns; ResolveAI truncates context to 2 customer + 1 brand turns, baselines get all turns; only ResolveAI and B1 see historical evidence (the architectural difference under test)

| system | intent acc | intent macro-F1 [95% CI] | esc precision | esc recall [95% CI] | esc F1 | auto | clarify | handoff | safe auto | unsafe auto | grounded auto | judge groundedness | judge hallucination | LLM calls | $/msg | p50 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| resolveai_full | 0.8477 | 0.854 [0.799, 0.901] | 0.2869 | 0.946 [0.862, 1.000] | 0.4403 | 0.0457 | 0.335 | 0.6193 | 9 | 0 | 5 | 4.284 | 0.216 | 1.553 | 0.002608 | 117.3 |
| B0_trivial | 0.0812 | 0.014 [0.008, 0.020] | 0.0 | 0.000 [0.000, 0.000] | 0.0 | 1.0 | 0.0 | 0.0 | 0 | 37 | 0 | 4.985 | 0.0 | 0.0 | 0.0 | 0.0 |
| B0_trivial_always_handoff | 0.0812 | 0.014 [0.008, 0.020] | 0.1878 | 1.000 [1.000, 1.000] | 0.3162 | 0.0 | 0.0 | 1.0 | 0 | 0 | 0 | n/a | n/a | 0.0 | 0.0 | 0.0 |
| B1_simple_ml | 0.5431 | 0.550 [0.472, 0.615] | 0.4912 | 0.757 [0.613, 0.889] | 0.5957 | 0.7107 | 0.0 | 0.2893 | 13 | 9 | 0 | 4.284 | 0.17 | 0.0 | 0.0 | 114.3 |
| B2_direct_llm | 0.8782 | 0.887 [0.835, 0.927] | 0.7391 | 0.919 [0.828, 1.000] | 0.8193 | 0.7665 | 0.0 | 0.2335 | 0 | 3 | 0 | 3.227 | 0.526 | 1.071 | 0.002366 | 6543.1 |
| minus_second_opinion | 0.6142 | 0.618 [0.546, 0.677] | 0.3 | 0.973 [0.909, 1.000] | 0.4586 | 0.0457 | 0.3452 | 0.6091 | 9 | 0 | 5 | n/a | n/a | 0.797 | 0.001734 | 221.4 |
| minus_resolution_rerank | 0.8477 | 0.854 [0.799, 0.901] | 0.2778 | 0.946 [0.862, 1.000] | 0.4294 | 0.0558 | 0.3046 | 0.6396 | 11 | 0 | 7 | n/a | n/a | 1.538 | 0.00253 | 38.9 |
| minus_risk_llm | 0.8477 | 0.854 [0.799, 0.901] | 0.3649 | 0.730 [0.571, 0.871] | 0.4865 | 0.0914 | 0.533 | 0.3756 | 18 | 0 | 5 | n/a | n/a | 0.858 | 0.001053 | 36.4 |
| minus_retrieval | 0.8477 | 0.854 [0.799, 0.901] | 0.2869 | 0.946 [0.862, 1.000] | 0.4403 | 0.0203 | 0.3604 | 0.6193 | 4 | 0 | 0 | n/a | n/a | 1.487 | 0.002478 | 4.3 |

## Paired bootstrap differences (ResolveAI minus system; 95% CI; same resampled rows for both)

| comparison | intent macro-F1 | escalation F1 | escalation recall | safe auto rate |
|---|---|---|---|---|
| resolveai_full_minus_B0_trivial | 0.8401 [0.7854, 0.887] | 0.4403 [0.3312, 0.5301] | 0.9459 [0.8621, 1.0] | 0.0457 [0.0203, 0.0761] |
| resolveai_full_minus_B0_trivial_always_handoff | 0.8401 [0.7854, 0.887] | 0.1241 [0.077, 0.1662] | -0.0541 [-0.1379, 0.0] | 0.0457 [0.0203, 0.0761] |
| resolveai_full_minus_B1_simple_ml | 0.304 [0.2236, 0.3916] | -0.1554 [-0.2504, -0.0544] | 0.1891 [0.0334, 0.3415] | -0.0203 [-0.0609, 0.0203] |
| resolveai_full_minus_B2_direct_llm | -0.0329 [-0.0823, 0.0137] | -0.379 [-0.4867, -0.2875] | 0.027 [-0.0883, 0.1396] | 0.0457 [0.0203, 0.0761] |
| resolveai_full_minus_minus_second_opinion | 0.2356 [0.1747, 0.3026] | -0.0183 [-0.048, 0.0049] | -0.0271 [-0.0882, 0.0] | 0.0 [0.0, 0.0] |
| resolveai_full_minus_minus_resolution_rerank | 0.0 [0.0, 0.0] | 0.0109 [0.0024, 0.0231] | 0.0 [0.0, 0.0] | -0.0102 [-0.0305, 0.0102] |
| resolveai_full_minus_minus_risk_llm | 0.0 [0.0, 0.0] | -0.0462 [-0.1279, 0.0364] | 0.2162 [0.0882, 0.3715] | -0.0457 [-0.0761, -0.0203] |
| resolveai_full_minus_minus_retrieval | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.0254 [0.0051, 0.0508] |

## Blinded pairwise judge (A/B position randomised, seed 42)

| pair | n | win | tie | loss | win rate | x wins when in position A | x wins when in position B | judge failures |
|---|---|---|---|---|---|---|---|---|
| resolveai_full_vs_B1_simple_ml | 197 | 100 | 13 | 84 | 0.508 | 0.447 | 0.563 | 0 |
| resolveai_full_vs_B2_direct_llm | 197 | 63 | 7 | 125 | 0.323 | 0.301 | 0.343 | 2 |

Judge: glm-5.2 (same family as ResolveAI's drafter and the direct-LLM baseline; self-preference risk discussed in judge_agreement.md). B0's canned reply and B1's copied historical replies are not LLM-written.