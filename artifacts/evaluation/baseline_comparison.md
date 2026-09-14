# Baseline comparison (golden, n=197, evaluated once per system)

all systems receive the PII-redacted current message and the prior thread turns; ResolveAI truncates context to 2 customer + 1 brand turns, baselines get all turns; only ResolveAI and B1 see historical evidence (the architectural difference under test)

| system | intent acc | intent macro-F1 [95% CI] | esc precision | esc recall [95% CI] | esc F1 | auto | clarify | handoff | safe auto | unsafe auto | grounded auto | judge groundedness | judge hallucination | LLM calls | $/msg | p50 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| resolveai_full | 0.8325 | 0.831 [0.771, 0.884] | 0.3115 | 0.927 [0.838, 1.000] | 0.4663 | 0.0457 | 0.335 | 0.6193 | 9 | 0 | 5 | 4.284 | 0.216 | 1.553 | 0.002608 | 117.3 |
| B0_trivial | 0.0863 | 0.014 [0.009, 0.021] | 0.0 | 0.000 [0.000, 0.000] | 0.0 | 1.0 | 0.0 | 0.0 | 0 | 41 | 0 | 4.985 | 0.0 | 0.0 | 0.0 | 0.0 |
| B0_trivial_always_handoff | 0.0863 | 0.014 [0.009, 0.021] | 0.2081 | 1.000 [1.000, 1.000] | 0.3445 | 0.0 | 0.0 | 1.0 | 0 | 0 | 0 | n/a | n/a | 0.0 | 0.0 | 0.0 |
| B1_simple_ml | 0.5279 | 0.530 [0.455, 0.594] | 0.5439 | 0.756 [0.610, 0.886] | 0.6327 | 0.7107 | 0.0 | 0.2893 | 13 | 10 | 0 | 4.284 | 0.17 | 0.0 | 0.0 | 114.3 |
| B2_direct_llm | 0.8528 | 0.853 [0.793, 0.901] | 0.7609 | 0.854 [0.735, 0.951] | 0.8046 | 0.7665 | 0.0 | 0.2335 | 0 | 6 | 0 | 3.227 | 0.526 | 1.071 | 0.002366 | 6543.1 |
| minus_second_opinion | 0.6041 | 0.608 [0.536, 0.669] | 0.325 | 0.951 [0.875, 1.000] | 0.4845 | 0.0457 | 0.3452 | 0.6091 | 9 | 0 | 5 | n/a | n/a | 0.797 | 0.001734 | 221.4 |
| minus_resolution_rerank | 0.8325 | 0.831 [0.771, 0.884] | 0.3016 | 0.927 [0.838, 1.000] | 0.4551 | 0.0558 | 0.3046 | 0.6396 | 11 | 0 | 7 | n/a | n/a | 1.538 | 0.00253 | 38.9 |
| minus_risk_llm | 0.8325 | 0.831 [0.771, 0.884] | 0.4054 | 0.732 [0.590, 0.857] | 0.5217 | 0.0914 | 0.533 | 0.3756 | 18 | 0 | 5 | n/a | n/a | 0.858 | 0.001053 | 36.4 |
| minus_retrieval | 0.8325 | 0.831 [0.771, 0.884] | 0.3115 | 0.927 [0.838, 1.000] | 0.4663 | 0.0203 | 0.3604 | 0.6193 | 4 | 0 | 0 | n/a | n/a | 1.487 | 0.002478 | 4.3 |

## Paired bootstrap differences (ResolveAI minus system; 95% CI; same resampled rows for both)

| comparison | intent macro-F1 | escalation F1 | escalation recall | safe auto rate |
|---|---|---|---|---|
| resolveai_full_minus_B0_trivial | 0.8169 [0.7551, 0.8706] | 0.4663 [0.366, 0.5556] | 0.9268 [0.8378, 1.0] | 0.0457 [0.0203, 0.0761] |
| resolveai_full_minus_B0_trivial_always_handoff | 0.8169 [0.7551, 0.8706] | 0.1218 [0.0707, 0.167] | -0.0732 [-0.1622, 0.0] | 0.0457 [0.0203, 0.0761] |
| resolveai_full_minus_B1_simple_ml | 0.3017 [0.2239, 0.3857] | -0.1664 [-0.2639, -0.0649] | 0.1707 [0.0303, 0.3062] | -0.0203 [-0.0609, 0.0203] |
| resolveai_full_minus_B2_direct_llm | -0.0217 [-0.0701, 0.0235] | -0.3383 [-0.4452, -0.2442] | 0.0731 [-0.0465, 0.2] | 0.0457 [0.0203, 0.0761] |
| resolveai_full_minus_minus_second_opinion | 0.2231 [0.1584, 0.2935] | -0.0182 [-0.0476, 0.0051] | -0.0244 [-0.0811, 0.0] | 0.0 [0.0, 0.0] |
| resolveai_full_minus_minus_resolution_rerank | 0.0 [0.0, 0.0] | 0.0112 [0.0024, 0.0238] | 0.0 [0.0, 0.0] | -0.0102 [-0.0305, 0.0102] |
| resolveai_full_minus_minus_risk_llm | 0.0 [0.0, 0.0] | -0.0554 [-0.1319, 0.0225] | 0.1951 [0.081, 0.3263] | -0.0457 [-0.0761, -0.0203] |
| resolveai_full_minus_minus_retrieval | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.0254 [0.0051, 0.0508] |

## Blinded pairwise judge (A/B position randomised, seed 42)

| pair | n | win | tie | loss | win rate | x wins when in position A | x wins when in position B | judge failures |
|---|---|---|---|---|---|---|---|---|
| resolveai_full_vs_B1_simple_ml | 197 | 100 | 13 | 84 | 0.508 | 0.447 | 0.563 | 0 |
| resolveai_full_vs_B2_direct_llm | 197 | 63 | 7 | 125 | 0.323 | 0.301 | 0.343 | 2 |

Judge: glm-5.2 (same family as ResolveAI's drafter and the direct-LLM baseline; self-preference risk discussed in judge_agreement.md). B0's canned reply and B1's copied historical replies are not LLM-written.