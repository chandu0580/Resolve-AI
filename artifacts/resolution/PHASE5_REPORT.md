# ResolveAI Phase 5 report: resolution intelligence and trust optimisation

## 1. Objective and what changed
Phase 4 ended with a safe but mostly non-autonomous agent: evidence was insufficient for 93.9% of golden messages and the
few autonomous replies only asked for device/version. Phase 5 attacked the evidence layer and the trust path without lowering
a single threshold: reply-side/pair/dual retrieval, a resolution-centred reranker, resolution clusters with provenance and a
consistency verdict, a measurable resolution confidence, the four-state gate-v3 (INSUFFICIENT / WEAK / SUFFICIENT / STRONG),
policy-v3, a resolution-aware drafter, a compact risk schema, a risk-call short-circuit, a hardened structured-output retry,
a verifier block analysis and an autonomy utility view. Primary target: SAFE RESOLUTION QUALITY, not automation rate.

## 2. Retrieval: reply-side, pair, dual and reranked (DEV tuning, GOLDEN once)
| variant (golden, n=197, 46 same-resolution references) | R@5 | MRR | resolution-bearing@1 | @3 | sufficient |
|---|---|---|---|---|---|
| A customer index, gate-v2 (Phase 2 default) | 0.3478 | 0.2652 | 0.1777 | 0.3706 | 0.0711 |
| B reply index | 0.0 | 0.0 | 0.1168 | 0.2437 | 0.0 |
| B2 pair index | 0.3478 | 0.2844 | 0.2234 | 0.3909 | 0.0457 |
| C dual customer+reply (RRF) | 0.2826 | 0.2337 | 0.1168 | 0.3147 | 0.0051 |
| C2 dual customer+pair (RRF) | 0.3478 | 0.2899 | 0.198 | 0.3604 | 0.066 |
| D pair + resolution rerank + gate-v3 (selected on dev) | 0.2609 | 0.1957 | 0.7563 | 0.7563 | 0.0305 |

Reading: the reply-side index on its own finds no same-resolution case (Phase-2 hypothesis H1 refuted); pair and dual variants equal
the customer index; the resolution reranker puts a genuine instruction-bearing reply at rank 1 for 75.6% of
golden messages (from 17.8%) at the cost of same-resolution R@5 (0.3478 -> 0.2609), because
the Phase-2 judge's references include ask-info replies that the reranker demotes by design. Weights: the dev grid was flat
(17 evaluations), defaults frozen in `rerank_weights.json` (outcome bonus weight 0.01, bounded).
GENERAL vs RESOLUTION relevance is now explicit on every evidence item (`cos_customer` vs `cos_pair`/`cos_reply`, `resolution_relevance`, `retrieval_source`).

## 3. Resolution clusters, consistency, confidence and gate-v3
- Clusters = action classes (update / restart / reset / settings / article) over instruction-bearing replies above the 0.85
  support similarity, excluding the same customer; every cluster carries its source ids (`ResolutionCandidate`).
- `resolution_confidence = 0.30*top_share + 0.25*min(1, support/3) + 0.25*top_similarity + 0.20*(1-conflict) - 0.30*customer_history - 1.0*insufficient_query`
  (measurable, not an LLM probability).
- Gate-v3 frozen (`share0.6_ms3`): `{"support_similarity": 0.85, "min_support": 3, "min_top_share": 0.6, "t_weak": 0.35, "t_sufficient": 0.55, "t_strong": 0.75, "min_query_tokens": 3, "require_symptom_term": true, "relevance_floor": 0.55, "version": "gate-v3"}`. Support similarity stays at the gate-v2 level; the specificity guard is new.
- Calibration: the automatic judge gave 0 precision for every threshold (as in Phase 2), so all 24 dev cases the loosest
  candidate called sufficient were hand-checked (AI annotator; rubric in `gate_v3_handcheck.json`):

| candidate | n sufficient (dev 500) | RESOLVES | PARTIAL | WRONG | precision (R+P) |
|---|---|---|---|---|---|
| share0.5_ms2 | 24 | 16 | 3 | 5 | 0.792 |
| share0.6_ms2 | 22 | 16 | 2 | 4 | 0.818 |
| share0.7_ms2 | 20 | 15 | 1 | 4 | 0.8 |
| share0.6_ms3 (chosen) | 14 | 11 | 2 | 1 | 0.929 |
| share0.7_ms3 | 12 | 10 | 1 | 1 | 0.917 |

Golden (once) with the frozen gate, retrieval benchmark protocol (raw message as query, weak-keyword intent; the agent run in section 8 uses the classifier and query construction, hence slightly different counts): levels `{'INSUFFICIENT': 173, 'WEAK': 18, 'STRONG': 6}`, consistency `{'no_resolution': 172, 'consistent': 21, 'mixed_resolution': 4}`, reasons `{'weak_similarity': 107, 'insufficient_query': 66, 'insufficient_resolution_evidence': 9, 'weak_resolution_evidence': 8, 'strong_consistent_evidence': 6, 'mixed_resolution': 1}`.

## 4. Resolution-aware drafting (A/B on dev, n=13 draftable cases; thin, stated)
| metric | A draft-v1 | B draft-v2 |
|---|---|---|
| verifier block rate | 0.538 | 0.385 |
| ask-only rate | 0.154 | 0.0 |
| actionable resolution rate | 0.692 | 0.923 |
| mentions top cluster action | 0.846 | 0.923 |
| verified AND actionable | 0.462 | 0.615 |
| mean evidence coverage | 0.564 | 0.655 |
| draft failures | 0 | 1 |

Run 1 (before the structured-output fix) had 2 + 6 draft failures (0.538 / 0.538 block rates); it is kept as `run1_draft_experiment.*`.
Only 13 holdout messages pass gate-v3 and the rules-only policy, so the A/B is directional: v2 removes ask-only drafts and raises
actionable, verified drafts; it also costs more output tokens (162.1 vs 1602.5 incl. verifier; v1 was cache-served in run 2).

## 5. Verifier block analysis (dev drafts)
12 of 26 drafts blocked: TRUE_BLOCK 6, FALSE_BLOCK 5, UNCERTAIN 1
(by check: `{"llm_support_check": {"FALSE_BLOCK": 5, "TRUE_BLOCK": 3}, "evidence_refs": {"TRUE_BLOCK": 2}, "evidence_coverage": {"TRUE_BLOCK": 1}, "draft_failed": {"UNCERTAIN": 1}}`; passed sample 12/12 TRUE_PASS). Every false block was either the
mandated link paraphrase ("the steps on our support site") or a verifier outage. Conservative change: verify-v2 names the paraphrase as
allowed; outages still block. The true blocks were invented steps ("check your keyboard settings"), invented actions ("DM us"), missing references, or
ask-only drafts with no evidence overlap - exactly what the verifier exists for.

## 6. Risk extraction hardening (dev, n=40, live calls)
| schema | fallback rate | retry rate | output tokens | p50 ms | p95 ms |
|---|---|---|---|---|---|
| v1 full 14-boolean, cap 900 | 0.325 | 0.425 | 1083.3 | 9129 | 23620 |
| v2 compact, cap 900 | 0.0 | 0.2 | 684.5 | 7486 | 24318 |
| v2 compact, cap 600 | 0.25 | 0.425 | 700.4 | 9150 | 17266 |

v1/v2 agreement on 27 rows: Jaccard 0.848, exact match 0.704. The proxy ignores reasoning-off parameters
(tested), so the output size is the lever; raising or lowering the cap alone is not.

## 7. Risk-call short-circuit (dev, n=40)
Skipped 14/40 risk calls (35.0%); LLM calls per message 2.075 -> 1.7;
risk stage p50 7288 ms live. Behaviour: 40/40 identical actions, 37/40 identical reason codes
(the three differences are handoffs whose named reason moved to the rules' reason because the LLM's extra flag was never extracted).
Structured-output retry hardening: example shape instead of the JSON schema (GLM had answered the schema), 1.5x cap on a truncated first answer.

## 8. Golden run (once) and Phase 4 -> 5 comparison
| metric | Phase 4 (run 2) | Phase 5 |
|---|---|---|
| AUTO_HANDLE | 0.0508 | 0.0457 |
| CLARIFICATION_REQUIRED | 0.3655 | 0.335 |
| HUMAN_HANDOFF | 0.5838 | 0.6193 |
| insufficient_evidence_rate | 0.9391 | 0.9645 |
| intent_accuracy | 0.8325 | 0.8477 |
| intent_macro_f1 | 0.8423 | 0.8538 |
| escalation_recall | 0.9459 | 0.9459 |
| escalation_precision | 0.3043 | 0.2869 |
| auto_replies | 10 | 9 |
| auto_with_evidence_refs | 3 | 5 |
| drafts_generated | 12 | 5 |
| verified_share_of_drafts | 0.8333 | 1.0 |
| auto_on_gold_should_escalate | 0 | 0 |
| llm_calls_per_message | 2.31 | 1.553 |
| tokens_out_per_message | 69.8 | 488.5 |
| estimated_cost_usd_per_message | 0.000266 | 0.00189 |
| fallbacks | 45 | 4 |
| total_p50_ms | 118.1 | 5855.0 |
| total_p95_ms | 277.7 | 25054.8 |

Evidence levels on golden: `{'INSUFFICIENT': 166, 'WEAK': 24, 'STRONG': 7}`; gate reasons `{'weak_similarity': 111, 'insufficient_resolution_evidence': 17, 'insufficient_query': 55, 'strong_consistent_evidence': 7, 'weak_resolution_evidence': 7}`; consistency `{'no_resolution': 177, 'consistent': 20}`; risk status `{'ok': 122, 'policy_hard_handoff': 63, 'rules_hard_block': 10, 'fallback': 2}`.
Escalation: precision 0.2869, recall 0.9459, F1 0.4403 (HUMAN_HANDOFF vs gold); any non-autonomous action as positive {'precision': 0.1968, 'recall': 1.0, 'f1': 0.3289}.
Intent accuracy 0.8477, macro-F1 0.8538.

## 9. Safety invariants (computed on the golden run; all must be 0)
`{"auto_without_sufficient_evidence_or_canned": 0, "auto_troubleshoot_without_refs": 0, "auto_unverified": 0, "auto_with_hard_risk_flag": 0, "auto_on_gold_should_escalate": 0, "responses_with_unredacted_pii": 0, "gold_hash_verified": true}`
- No sufficient evidence -> no autonomous factual response (auto_without_sufficient_evidence_or_canned).
- Every autonomous troubleshooting reply has evidence refs and passed verification (auto_troubleshoot_without_refs, auto_unverified).
- Hard rules cannot be bypassed by the LLM (auto_with_hard_risk_flag); the LLM only adds flags.
- No autonomous reply on a row annotated should-escalate (auto_on_gold_should_escalate).
- PII never reaches an LLM or a trace (client refuses; tests) and none appears in responses (responses_with_unredacted_pii).
- Golden immutable (hash-verified load), no future information (temporal eligibility on every index; test), no hidden reasoning stored (traces hold ids, scores and verdicts only).

## 10. Autonomy utility view (sensitivity, not business facts)
counts `{"safe_auto_resolution": 9, "unsafe_auto": 0, "correct_non_autonomous": 37, "unnecessary_non_autonomous": 151}`; utility = safe_auto - w*unsafe_auto - c*unnecessary_non_autonomous.

| weights | ResolveAI (Phase 5) | always-handoff | never-escalate |
|---|---|---|---|
| w=1.0, c=0.1 | -6.1 | -16.0 | 123.0 |
| w=1.0, c=0.3 | -36.3 | -48.0 | 123.0 |
| w=3.0, c=0.1 | -6.1 | -16.0 | 49.0 |
| w=3.0, c=0.3 | -36.3 | -48.0 | 49.0 |
| w=5.0, c=0.1 | -6.1 | -16.0 | -25.0 |
| w=5.0, c=0.3 | -36.3 | -48.0 | -25.0 |

The agent beats always-handoff at every weight because it has 9 safe autonomous resolutions and 0 unsafe ones; never-escalate
is a trap that only looks good when unsafe replies are cheap. The headline "autonomy" is small and the cost of every needless human touch dominates.

## 11. Cost and latency (golden run)
`{"llm_calls_per_message": 1.553, "live_calls_per_message": 0.873, "cache_hit_rate": 0.4379, "tokens_in_per_message": 326.7, "tokens_out_per_message": 488.5, "estimated_cost_usd_per_message": 0.00189, "fallbacks": 4, "calls_by_action": {"HUMAN_HANDOFF": 1.23, "CLARIFICATION_REQUIRED": 1.94, "AUTO_HANDLE": 3.11}, "wall_seconds": 1474.2, "risk_calls_skipped_by_policy": 63, "risk_calls_skipped_by_rules": 10}`
Stage latency (p50/p95 ms): context 0.2/0.5, intent 86.4/183.1, second_opinion 15.5/5689.1, retrieval 87.6/211.4, risk 5037.3/22032.1, policy 0.0/0.1, draft 0.0/0.0, verification 0.0/0.0, output_gate 0.0/0.1, handoff 0.1/0.2, total 5855.0/25054.8.
The Phase 4 column in the comparison table is run 2, which was 95% cache-served (p50 118 ms, $0.00027); the like-for-like live
comparison is Phase 4 run 1: 2.437 calls, 1.665 live calls, $0.004532 per message, total p50 10874.8 ms / p95 25114.2 ms,
risk p50 10510.1 ms -> Phase 5: 1.553 calls, 0.873 live calls, $0.00189 per message, total p50 5855.0 ms / p95 25054.8 ms,
risk p50 5037.3 ms (63 risk calls skipped by the policy short-circuit, 10 by the rules). Fallbacks 54 -> 4.

## 12. What is misleading about the headline numbers
1. Autonomy rate is not quality: 4.6% AUTO includes 4 canned closures/redirects; only 5 are troubleshooting replies.
2. Every hand-check in this phase (gate calibration, verifier review) is an AI annotator's reading, not a human study; the numbers are directional.
3. The drafting A/B has n=13; a 1-case change moves a rate by 7.7 points.
4. The same-resolution judge is TF-IDF on 46 references; it cannot see paraphrases and rewards ask-info replies. Its 0 gate precision is a judge limitation as much as a gate one.
5. The golden set is a 5-day burst dominated by the iOS 11 autocorrect bug; nearly every STRONG verdict is that bug. Coverage on other issues is unmeasured.
6. Escalation precision is low by design (evidence-first); recall is the number that matters and it is unchanged.
7. Golden was evaluated once with the final system, but the retrieval variants were also evaluated on golden in a first (predicate-bugged) run that was discarded after the hand-check exposed the bug; nothing was tuned on golden.
8. Latency p50 includes cache hits; live p50 for risk is 7288 ms and for a draft ~19691 ms. The Phase 4 comparison column is a cache-served run; section 11 gives the live-vs-live numbers.
9. The first report of this golden run counted the four canned replies as troubleshooting drafts and showed two invariant counters at 4; the counting was fixed and the report recomputed from the saved records (failure analysis #15). The agent was not re-run.
10. Phase 4 -> 5 moved 6 rows from clarification to handoff (33.5% vs 36.5% clarify; 61.9% vs 58.4% handoff): the general_complaint rule and the stricter gate trade clarification for handoff on vague messages; escalation precision fell from 0.304 to 0.287 while recall stayed 0.946.

## 13. Next steps (not started; Phase 6+)
Customer-disjoint specificity model instead of a lexicon; a reply-quality judge (LLM + human agreement) for the drafts; KB coverage beyond the
autocorrect burst; measure verify-v2 on dev; the evaluation harness with the LLM judge (Phase 1I / 7); the operator workspace (Phase 8).

Decision log entries: docs/DECISIONS.md #42-#56.
