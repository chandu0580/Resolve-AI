# Guide v1.1 adjudication report

Provenance: Annotator B was an isolated AI annotator, not an independent human; the v1.0 kappa (intent 0.920, escalation 0.885) must never be described as human-human agreement.

Status: candidate gold (`golden_adjudicated.csv`) produced. **NOT frozen.**

## Rows whose labels changed under v1.1

| gid | field | A (v1.0) | B (v1.0) | v1.1 | rule | disagreement | why |
|---|---|---|---|---|---|---|---|
| g048 | intent | other | other | other | R1,R7 | agreed row changed | 'the dm I sent' is an explicit prior contact; no underlying issue inferred |
| g048 | should_escalate | True | False | True | R1,R7 | resolved | 'the dm I sent' is an explicit prior contact; no underlying issue inferred |
| g048 | escalation_reason | repeat_contact | none | repeat_contact | R1,R7 | resolved | 'the dm I sent' is an explicit prior contact; no underlying issue inferred |
| g102 | should_escalate | False | True | False | R1 | resolved | 'force restart didn't work' was stated by a different customer in the thread ('I have the same problem'); current customer states no attempt |
| g102 | escalation_reason | none | repeat_contact | none | R1 | resolved | 'force restart didn't work' was stated by a different customer in the thread ('I have the same problem'); current customer states no attempt |
| g126 | should_escalate | True | False | False | R1 | resolved | '3rd time you've deleted my library' is a recurrence, not an attempt or a contact; symptom present so not vague_hostile |
| g126 | escalation_reason | repeat_contact | none | none | R1 | resolved | '3rd time you've deleted my library' is a recurrence, not an attempt or a contact; symptom present so not vague_hostile |
| g131 | should_escalate | True | False | True | R1 | resolved | 'I try to place it right for many times' is an explicit prior attempt |
| g131 | escalation_reason | repeat_contact | none | repeat_contact | R1 | resolved | 'I try to place it right for many times' is an explicit prior attempt |
| g135 | should_escalate | False | True | False | R1 | resolved | 'no chance with any of the usual tricks' is vague; no explicit attempt |
| g135 | escalation_reason | none | repeat_contact | none | R1 | resolved | 'no chance with any of the usual tricks' is vague; no explicit attempt |
| g153 | should_escalate | False | True | False | R7 | resolved | policy complaint about reset wait; no account problem stated, none inferred |
| g153 | escalation_reason | none | private_info | none | R7 | resolved | policy complaint about reset wait; no account problem stated, none inferred |
| g191 | should_escalate | True | False | True | R1 | resolved | explicit completion of the brand's suggested step ('all the apps are on their latest version') then 'what's next?' |
| g191 | escalation_reason | repeat_contact | none | repeat_contact | R1 | resolved | explicit completion of the brand's suggested step ('all the apps are on their latest version') then 'what's next?' |
| g011 | intent | general_complaint | keyboard_text_bug | keyboard_text_bug | R5 | resolved | corrupted I-glyph is present in the customer's own text and message refers to 'this glitch' |
| g024 | intent | connectivity | hardware_damage | connectivity | R3 | resolved | accessory 'not supported'; no physical fault stated |
| g029 | intent | apps_services | keyboard_text_bug | apps_services | R2,R4 | resolved | Cmd+V clipboard = OS feature failure; no dedicated bucket |
| g063 | intent | general_complaint | apps_services | general_complaint | R5 | resolved | pop-up is only in the screenshot |
| g077 | intent | performance_crash | battery_power | battery_power | R6 | resolved | 'warm' (overheating) is the only concrete symptom; 'glitchy' is vague |
| g085 | intent | general_complaint | performance_crash | general_complaint | R5 | resolved | symptom only in the video |
| g087 | intent | connectivity | hardware_damage | connectivity | R3 | resolved | Beats audio issue, no physical fault stated -> functional category, clarify |
| g113 | intent | other | general_complaint | other | R5,R7 | resolved | 'Proofreading <url>' states no support request |
| g121 | intent | apps_services | performance_crash | apps_services | R2 | resolved | crash confined to the Phone app |
| g134 | intent | apps_services | performance_crash | apps_services | R2 | resolved | crash confined to Safari |
| g146 | intent | apps_services | other | general_complaint | R4 | resolved | OS security-vulnerability question; no intent genuinely fits |
| g148 | intent | connectivity | apps_services | apps_services | R6 | resolved | requested resolution is iTunes sync, the Wi-Fi is the transport |
| g170 | intent | apps_services | other | general_complaint | R4 | resolved | OS security-vulnerability confirmation; no intent genuinely fits |
| g171 | intent | account_store_repair | hardware_damage | account_store_repair | R6 | resolved | main requested resolution is scheduling a service appointment blocked by 2FA; black screen is secondary; reason by priority |
| g171 | escalation_reason | private_info | hardware | private_info | R6 | resolved | main requested resolution is scheduling a service appointment blocked by 2FA; black screen is secondary; reason by priority |
| g006 | intent | performance_crash | performance_crash | apps_services | R2 | agreed row changed | crash confined to the Settings app (both annotators had performance_crash under v1.0) |

Label disagreements resolved: 29. Agreed rows changed by a v1.1 rule: 2. Metadata-only annotations: 25 rows. Residual unexplained disagreements: 0 (asserted).

## Rule usage

- R1: 6
- R5: 4
- R2: 4
- R7: 3
- R4: 3
- R6: 3
- R3: 2

## Candidate gold summary

- rows: 197
- intent: {'apps_services': 38, 'performance_crash': 26, 'other': 20, 'data_loss_sync': 17, 'account_store_repair': 16, 'battery_power': 16, 'keyboard_text_bug': 16, 'general_complaint': 14, 'connectivity': 14, 'non_english': 13, 'hardware_damage': 7}
- should_escalate = true: 37 (18.8%)
- escalation_reason: {'repeat_contact': 14, 'private_info': 13, 'hardware': 5, 'safety': 4, 'vague_hostile': 1}
- flags: taxonomy_gap=7, insufficient_context=18, multi_intent=10, evidence_unavailable=31