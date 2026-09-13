# Phase 9 risk over-escalation: DEV results

Dev rows: 240 (holdout, golden excluded). Rows where the variants disagree on handoff: 76, all labelled for `should_escalate` by an AI annotator under the annotation guide v1.1 (**not human labels**).

| variant | handoffs (all rows) | TP | FP (unnecessary) | FN (missed) | missed by reason |
|---|---|---|---|---|---|
| V0 | 153 | 25 | 41 | 1 | {'repeat_contact': 1} |
| V1 | 87 | 0 | 0 | 26 | {'repeat_contact': 22, 'hardware': 3, 'private_info': 1} |
| V2 | 108 | 3 | 18 | 23 | {'repeat_contact': 20, 'hardware': 3} |
| V3 | 141 | 24 | 30 | 2 | {'hardware': 1, 'repeat_contact': 1} |
| V4 | 99 | 3 | 9 | 23 | {'repeat_contact': 20, 'hardware': 3} |

| candidate | Δ unnecessary handoffs | Δ missed | removed handoffs (correctly removed, 95% Wilson) | fallback rate | accepted |
|---|---|---|---|---|---|
| V2 | -23 | 22 | 45 (23, (0.37, 0.65)) | 0.0065 | no: at_most_one_new_miss |
| V3 | -11 | 1 | 22 (20, (0.722, 0.975)) | 0.0131 | no: at_most_one_new_miss |
| V4 | -32 | 22 | 55 (33, (0.468, 0.719)) | 0.0131 | no: at_most_one_new_miss |

**Selected: none (production behaviour kept)**

False-positive patterns of production (V0) on the labelled rows:

- private_info <- model-only flags ['needs_private_info']: 7
- repeat_contact <- model-only flags ['repeat_contact']: 5
- private_info <- model-only flags ['high_impact', 'needs_private_info']: 5
- private_info <- model-only flags ['needs_private_info', 'physical_damage']: 4
- hardware <- model-only flags ['physical_damage']: 3
- payment_billing <- model-only flags ['payment_billing_risk']: 2
- payment_billing <- model-only flags ['needs_private_info', 'sensitive_action_required']: 1
- payment_billing <- model-only flags ['high_frustration', 'sensitive_action_required']: 1
- safety <- model-only flags ['high_frustration', 'safety_concern']: 1
- taxonomy_gap_risk <- model-only flags ['high_frustration']: 1
- safety <- model-only flags ['high_frustration', 'privacy_concern', 'security_concern']: 1
- account_access <- model-only flags ['account_access_risk', 'high_frustration']: 1
- safety <- model-only flags ['high_impact', 'security_concern']: 1
- private_info <- model-only flags ['needs_private_info', 'repeat_contact']: 1
- account_access <- model-only flags ['account_access_risk']: 1
- private_info <- model-only flags ['abusive_threatening', 'needs_private_info', 'physical_damage']: 1
- vague_hostile <- model-only flags []: 1
- payment_billing <- model-only flags ['high_frustration', 'payment_billing_risk', 'repeat_contact']: 1
- insufficient_evidence <- model-only flags ['high_impact']: 1
- payment_billing <- model-only flags ['high_frustration', 'physical_damage', 'repeat_contact', 'sensitive_action_required']: 1
- payment_billing <- model-only flags ['high_frustration', 'high_impact', 'needs_private_info', 'physical_damage', 'repeat_contact', 'sensitive_action_required']: 1
