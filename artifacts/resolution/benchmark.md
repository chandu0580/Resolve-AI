# ResolveAI golden benchmark (Phase 5, evaluated once)

Golden set, 197 rows. System: `{"retriever": "dense:bge-small:pair+rr+gatev3", "gate": "gate-v3", "policy": "policy-v3", "risk_schema": "compact", "draft": "v2", "second_opinion_policy": "llm_conf_0.7"}`. Wall time 1474 s.

## Actions

| AUTO_HANDLE | CLARIFICATION_REQUIRED | HUMAN_HANDOFF | insufficient evidence |
|---|---|---|---|
| 0.0457 | 0.335 | 0.6193 | 0.9645 |

Evidence levels: `{'INSUFFICIENT': 166, 'WEAK': 24, 'STRONG': 7}`; gate reasons: `{'weak_similarity': 111, 'insufficient_resolution_evidence': 17, 'insufficient_query': 55, 'strong_consistent_evidence': 7, 'weak_resolution_evidence': 7}`; consistency: `{'no_resolution': 177, 'consistent': 20}`
Reason codes: `{'private_info': 35, 'low_confidence': 27, 'repeat_contact': 24, 'none': 10, 'payment_billing': 12, 'account_access': 4, 'insufficient_evidence': 49, 'safety': 9, 'vague_hostile': 8, 'insufficient_context': 9, 'legal_media': 4, 'hardware': 6}`; risk status: `{'ok': 122, 'policy_hard_handoff': 63, 'rules_hard_block': 10, 'fallback': 2}`

## Intent

accuracy 0.8477, macro-F1 0.8538 (second opinion applied on 63 rows)

## Escalation (HUMAN_HANDOFF vs gold should_escalate)

precision 0.2869, recall 0.9459, F1 0.4403; confusion gold x pred `[[73, 87], [2, 35]]`; any non-autonomous action as positive: {'precision': 0.1968, 'recall': 1.0, 'f1': 0.3289}

## Responses

`{"auto_replies": 9, "auto_canned": 4, "auto_troubleshoot": 5, "drafts_generated": 5, "verified_share_of_drafts": 1.0, "mean_evidence_coverage_auto": 0.803, "auto_with_evidence_refs": 5, "ask_only_auto_replies": 0, "redraft_share": 0.2, "verification_issue_counts": {}, "auto_on_gold_should_escalate": 0, "risk_fallbacks": 2}`

## Safety invariants (counts of violations; all must be 0)

`{"auto_without_sufficient_evidence_or_canned": 0, "auto_troubleshoot_without_refs": 0, "auto_unverified": 0, "auto_with_hard_risk_flag": 0, "auto_on_gold_should_escalate": 0, "responses_with_unredacted_pii": 0, "gold_hash_verified": true}`

## Autonomy utility view (sensitivity, not business facts)

counts `{"safe_auto_resolution": 9, "unsafe_auto": 0, "correct_non_autonomous": 37, "unnecessary_non_autonomous": 151}`

| weights | ResolveAI | always-handoff | never-escalate |
|---|---|---|---|
| w=1.0, c=0.1 | -6.1 | -16.0 | 123.0 |
| w=1.0, c=0.3 | -36.3 | -48.0 | 123.0 |
| w=3.0, c=0.1 | -6.1 | -16.0 | 49.0 |
| w=3.0, c=0.3 | -36.3 | -48.0 | 49.0 |
| w=5.0, c=0.1 | -6.1 | -16.0 | -25.0 |
| w=5.0, c=0.3 | -36.3 | -48.0 | -25.0 |

## Phase 4 -> Phase 5

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

## Slices

| slice | n | auto | clarify | handoff | sufficient | intent acc | escalation recall |
|---|---|---|---|---|---|---|---|
| short | 45 | 0.044 | 0.311 | 0.644 | 0.022 | 0.689 | 0.667 |
| multi_turn | 48 | 0.062 | 0.125 | 0.812 | 0.021 | 0.854 | 1.0 |
| multi_intent | 10 | 0.0 | 0.5 | 0.5 | 0.0 | 0.8 | 1.0 |
| insufficient_context | 18 | 0.0 | 0.556 | 0.444 | 0.0 | 0.667 | 0.5 |
| taxonomy_gap | 7 | 0.0 | 0.429 | 0.571 | 0.0 | 1.0 | 1.0 |
| customer_seen_in_kb | 25 | 0.04 | 0.4 | 0.56 | 0.0 | 0.8 | 0.857 |

## Latency (ms) and cost

| stage | p50 | p95 | n |
|---|---|---|---|
| context | 0.2 | 0.5 | 197 |
| intent | 86.4 | 183.1 | 197 |
| second_opinion | 15.5 | 5689.1 | 197 |
| retrieval | 87.6 | 211.4 | 197 |
| risk | 5037.3 | 22032.1 | 197 |
| policy | 0.0 | 0.1 | 197 |
| draft | 0.0 | 0.0 | 197 |
| verification | 0.0 | 0.0 | 197 |
| output_gate | 0.0 | 0.1 | 197 |
| handoff | 0.1 | 0.2 | 122 |
| total | 5855.0 | 25054.8 | 197 |

`{"llm_calls_per_message": 1.553, "live_calls_per_message": 0.873, "cache_hit_rate": 0.4379, "tokens_in_per_message": 326.7, "tokens_out_per_message": 488.5, "estimated_cost_usd_per_message": 0.00189, "fallbacks": 4, "calls_by_action": {"HUMAN_HANDOFF": 1.23, "CLARIFICATION_REQUIRED": 1.94, "AUTO_HANDLE": 3.11}, "wall_seconds": 1474.2, "risk_calls_skipped_by_policy": 63, "risk_calls_skipped_by_rules": 10}`
