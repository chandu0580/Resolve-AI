# ResolveAI end-to-end benchmark (Phase 4)

Golden set, 197 rows, evaluated once with the frozen classifier, gate-v2, policy-v2, output-gate-v1, second-opinion policy `llm_conf_0.7`. Wall time 2206 s.

## Actions

| AUTO_HANDLE | CLARIFICATION_REQUIRED | HUMAN_HANDOFF | insufficient evidence |
|---|---|---|---|
| 0.0863 | 0.3655 | 0.5482 | 0.9391 |

Reason codes: `{'hardware': 5, 'low_confidence': 33, 'private_info': 13, 'repeat_contact': 22, 'llm_unavailable': 5, 'payment_billing': 15, 'account_access': 8, 'insufficient_evidence': 41, 'safety': 9, 'vague_hostile': 8, 'none': 17, 'insufficient_context': 4, 'legal_media': 4, 'conflicting_evidence': 9, 'verification_failed': 2, 'abusive_threatening': 2}`
Evidence gate reasons: `{'weak_similarity': 135, 'insufficient_resolution_evidence': 26, 'strong_consistent_evidence': 12, 'conflicting_evidence': 17, 'insufficient_query': 7}`

## Intent

accuracy 0.8325, macro-F1 0.8423 (second opinion applied on 60 rows)

## Escalation (HUMAN_HANDOFF vs gold should_escalate)

precision 0.3241, recall 0.9459, F1 0.4828; confusion gold x pred `[[87, 73], [2, 35]]`
Treating any non-autonomous action as positive: {'precision': 0.2056, 'recall': 1.0, 'f1': 0.341}. Baselines: always-escalate {'precision': 0.1878, 'recall': 1.0, 'f1': 0.3162}, never-escalate {'precision': 0.0, 'recall': 0.0, 'f1': 0.0}.

## Responses

`{"auto_replies": 17, "drafts_generated": 19, "verified_share_of_drafts": 0.8947, "mean_evidence_coverage_auto": 1.0, "auto_with_evidence_refs": 1, "redraft_share": 0.1053, "verification_issue_counts": {"llm_support_check": 2}, "auto_on_gold_should_escalate": 0, "policy_compliance_lexical": 1.0}`

## Baseline (no retrieval)

`{"canned_reply": "We'd love to help. DM us the details and we'll go from there.", "escalation": "never (always replies)", "intent": "majority class", "note": "message -> canned DM line, no retrieval, no verification; it 'auto-handles' 100% and is safe only because it says nothing"}`

## Slices

| slice | n | auto | handoff | intent acc | escalation recall |
|---|---|---|---|---|---|
| short | 45 | 0.089 | 0.556 | 0.667 | 1.0 |
| multi_turn | 48 | 0.104 | 0.792 | 0.812 | 1.0 |
| multi_intent | 10 | 0.0 | 0.4 | 0.7 | 1.0 |
| insufficient_context | 18 | 0.0 | 0.556 | 0.667 | 0.5 |
| taxonomy_gap | 7 | 0.0 | 0.714 | 1.0 | 1.0 |
| customer_seen_in_kb | 25 | 0.08 | 0.56 | 0.8 | 1.0 |

## Latency (ms) and cost

| stage | p50 | p95 | n |
|---|---|---|---|
| context | 0.1 | 0.4 | 197 |
| intent | 47.8 | 91.9 | 197 |
| second_opinion | 1.6 | 3.7 | 197 |
| retrieval | 54.8 | 113.3 | 197 |
| risk | 10510.1 | 18802.7 | 197 |
| policy | 0.0 | 0.1 | 197 |
| draft | 0.0 | 0.1 | 197 |
| verification | 0.0 | 0.0 | 197 |
| output_gate | 0.0 | 0.1 | 197 |
| handoff | 0.1 | 0.2 | 108 |
| total | 10874.8 | 25114.2 | 197 |

`{"llm_calls_per_message": 2.437, "live_calls_per_message": 1.665, "cache_hit_rate": 0.3167, "tokens_in_per_message": 734.4, "tokens_out_per_message": 1186.6, "estimated_cost_usd_per_message": 0.004532, "fallbacks": 54, "calls_by_action": {"HUMAN_HANDOFF": 2.48, "CLARIFICATION_REQUIRED": 2.43, "AUTO_HANDLE": 2.18}, "wall_seconds": 2205.8}`
