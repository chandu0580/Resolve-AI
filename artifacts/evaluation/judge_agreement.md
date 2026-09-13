# Judge <-> human agreement

50 rated examples joined to primary-judge scores.

| dimension | n | weighted kappa [95% CI] | Spearman rho | exact | within 1 | mean human | mean judge | judge bias |
|---|---|---|---|---|---|---|---|---|
| groundedness | 50 | 0.582 [0.3089, 0.7581] | 0.508 | 0.58 | 0.76 | 4.22 | 3.98 | neutral (-0.24) |
| relevance | 50 | 0.536 [0.273, 0.721] | 0.568 | 0.52 | 0.8 | 4.32 | 3.88 | harsh (-0.44) |
| actionability | 50 | 0.612 [0.442, 0.743] | 0.565 | 0.34 | 0.86 | 3.52 | 3.44 | neutral (-0.08) |
| completeness | 50 | 0.736 [0.5919, 0.835] | 0.76 | 0.54 | 0.94 | 3.3 | 3.22 | neutral (-0.08) |
| policy_compliance | 50 | 0.576 [0.1538, 0.831] | 0.511 | 0.82 | 0.98 | 4.74 | 4.78 | neutral (+0.04) |
| tone | 50 | 0.087 [0.0, 0.262] | 0.258 | 0.56 | 0.94 | 4.98 | 4.48 | harsh (-0.50) |

| binary | n | Cohen kappa [95% CI] | raw agreement | human positive rate | judge positive rate |
|---|---|---|---|---|---|
| hallucination | 50 | 0.442 [0.1228, 0.6922] | 0.78 | 0.26 | 0.28 |
| policy_violation | 50 | 0.0 [0.0, 0.0] | 0.98 | 0.0 | 0.02 |

### Where they disagree

Judge minus human, by system (positive = the judge is more generous than the human):

| system | n | groundedness | relevance | actionability | completeness | policy_compliance | tone |
|---|---|---|---|---|---|---|---|
| B1_simple_ml | 14 | -0.14 | -0.79 | -0.14 | -0.21 | +0.07 | -0.71 |
| B2_direct_llm | 11 | -0.82 | +0.09 | +0.18 | +0.00 | +0.18 | +0.00 |
| resolveai_full | 25 | -0.04 | -0.48 | -0.16 | -0.04 | -0.04 | -0.60 |

The judge shares a model family with ResolveAI's drafter and with B2. If its generosity is larger for those two systems than for B1's copied historical replies, that is a self-preference effect, not a quality difference.

25 of 50 rows differ by 2 or more points on at least one dimension; the largest 12:

| example | system | golden row | dimension | human | judge |
|---|---|---|---|---|---|
| ex0c78db74 | resolveai_full | g157 | relevance | 5 | 2 |
| ex61f3d1f8 | resolveai_full | g094 | relevance | 5 | 2 |
| ex6d588182 | B1_simple_ml | g108 | groundedness | 4 | 1 |
| ex70439bf9 | B2_direct_llm | g194 | groundedness | 5 | 2 |
| exb047608c | B2_direct_llm | g052 | groundedness | 5 | 2 |
| ex04f99ade | B1_simple_ml | g065 | relevance | 4 | 2 |
| ex13e58acd | resolveai_full | g150 | relevance | 5 | 3 |
| ex1a00d908 | B2_direct_llm | g083 | actionability | 3 | 5 |
| ex1cf64bfa | resolveai_full | g103 | groundedness | 3 | 5 |
| ex233b18a5 | B1_simple_ml | g004 | groundedness | 3 | 5 |
| ex23896bca | resolveai_full | g033 | groundedness | 3 | 5 |
| ex30e074ee | resolveai_full | g018 | groundedness | 3 | 5 |

Read these rows in `artifacts/evaluation/judge_human_pairs.csv` before trusting any judge-scored headline.

- **hallucination**: the judge missed 5 case(s) the human flagged and flagged 6 the human did not. A judge that misses hallucination understates the risk of every system it scores.
- **policy_violation**: the judge missed 0 case(s) the human flagged and flagged 1 the human did not. A judge that misses policy_violation understates the risk of every system it scores.

## Cross-family judge check (judge vs judge, NOT human)

126 responses scored by both GLM-5.2 (primary) and qwen3.8-27b (Groq, second family).

| dimension | weighted kappa | Spearman | exact | within 1 | mean primary | mean secondary |
|---|---|---|---|---|---|---|
| groundedness | 0.822 | 0.76 | 0.794 | 0.937 | 4.016 | 4.079 |
| relevance | 0.744 | 0.713 | 0.556 | 0.889 | 3.873 | 3.571 |
| actionability | 0.549 | 0.532 | 0.556 | 0.841 | 3.587 | 3.262 |
| completeness | 0.75 | 0.754 | 0.571 | 0.944 | 3.127 | 2.873 |
| policy_compliance | 0.418 | 0.392 | 0.817 | 0.968 | 4.77 | 4.81 |
| tone | 0.515 | 0.53 | 0.611 | 1.0 | 4.5 | 4.365 |
| hallucination (binary) | kappa 0.818 | raw 0.929 | | | primary rate 0.294 | secondary rate 0.238 |
| policy_violation (binary) | kappa 0.485 | raw 0.968 | | | primary rate 0.024 | secondary rate 0.04 |

Per-system means (primary vs secondary): `{"B1_simple_ml": {"groundedness": 4.33, "relevance": 3.38, "actionability": 3.4, "completeness": 2.88, "policy_compliance": 4.72, "tone": 4.3}, "B2_direct_llm": {"groundedness": 3.44, "relevance": 4.63, "actionability": 4.12, "completeness": 3.6, "policy_compliance": 4.93, "tone": 4.84}, "resolveai_full": {"groundedness": 4.3, "relevance": 3.58, "actionability": 3.23, "completeness": 2.88, "policy_compliance": 4.65, "tone": 4.35}}` vs `{"B1_simple_ml": {"groundedness": 4.5, "relevance": 3.38, "actionability": 3.17, "completeness": 2.83, "policy_compliance": 4.78, "tone": 4.25}, "B2_direct_llm": {"groundedness": 3.16, "relevance": 3.84, "actionability": 3.28, "completeness": 2.93, "policy_compliance": 4.81, "tone": 4.47}, "resolveai_full": {"groundedness": 4.6, "relevance": 3.49, "actionability": 3.33, "completeness": 2.86, "policy_compliance": 4.84, "tone": 4.37}}`
If the primary judge rates GLM-written responses (ResolveAI drafts, B2) higher than the second family does while agreeing on the non-LLM responses (B1 copies, templates), that is the self-preference signature.

## Limitations of this study

These apply whether or not the packet has been rated, and no result above should be quoted without them.

1. **One rater.** The packet is rated by the repository owner alone, so there is no inter-human reliability figure and no way to separate judge error from rater idiosyncrasy. A kappa here measures agreement with *one* person.
2. **The rater is not independent.** The owner built the system under test. The packet is blinded (the system that produced each response is only in `_packet_key.json`), which limits but does not remove that bias.
3. **50 stratified rows, not a random sample.** The packet oversamples handoffs, clarifications, difficult rows and judge-extreme rows (`packet_manifest.json`) so that disagreement is visible at small n. Rates read off it are therefore not estimates of the golden set's rates, and the CIs are wide at n = 50.
4. **The judge shares a family with two systems under test.** GLM-5.2 judges GLM-5.2 drafts (ResolveAI) and the direct-LLM baseline. The cross-family check above is the control; human agreement measures a different thing again.
5. **Agreement is not accuracy.** A judge and a human can agree and both be wrong, particularly on groundedness, where both are reading evidence they cannot verify against Apple's actual policy.
6. **Every other 'hand-check' in this project is AI annotation.** Annotator B, the gate calibration checks and the verifier audit were done by an isolated AI agent and are labelled as such; only this packet's `human_*` columns are human ratings. AI annotation is never reported as human evaluation.


## Judge calibration observations (primary judge, before any human rating)
- **Templates are read as claims.** 42 of 194 ResolveAI clarifications/handoffs were flagged as hallucinations. The rationales point at template wording: the repeat-contact handoff line "Thanks for the steps you've already tried" is sent when the rule fired on thread depth (>= 2 brand turns) although the customer never listed steps (g002, g004); the account/billing lines assert "because it involves your account details" (g013). These are real wording defects in HANDOFF_LINES, but they are not factual claims about the product, and a human may score them differently - the first thing the human study should settle.
- **The judge likes the do-nothing reply.** B0's modal "We'd love to help. DM us the details" scores groundedness 4.985 and actionability 3.782 (n=197), above ResolveAI's handoffs (2.53) - the rubric's "concrete handoff" anchor is satisfied by "DM us", so the pairwise question, not the absolute score, separates them. This is the Phase-0 caveat about the always-DM baseline, now measured.
- **Verbosity.** Mean response length: `{"resolveai_full": 125, "B1_simple_ml": 108, "B2_direct_llm": 218, "B0_trivial": 61}` characters; the direct-LLM baseline writes the longest replies. Compare its judge means with the second-family judge before reading a length preference into the scores.
- **Parse failures are not uniform**: B1 (copied historical replies with `<url>` tokens) lost 21 of 197 rows to truncated judge output vs 3 for ResolveAI and 0 for B0; excluded rows are not random.
- **Self-preference signature, measured**: on the 126 responses both judges scored, the GLM judge rates the GLM-written B2 replies higher than the second-family judge does by +0.79 / +0.84 / +0.67 (relevance / actionability / completeness), while on ResolveAI's mostly templated responses the gap is +0.09 / -0.10 / +0.02 and on B1's copied replies +0.00 / +0.23 / +0.05. The primary judge favours its own family's prose; the pairwise preference for B2 should be read with that in mind until humans rate the packet.
