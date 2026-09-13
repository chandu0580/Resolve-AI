# Phase 10 risk experiment: targeted `needs_private_info` corroboration (DEV only)

Pre-registration: `PREREGISTRATION.md` (sha256 `9fce79eaf5a9097a…`). 240 DEV rows (holdout, golden excluded); scores on the 76 rows labelled by an **AI annotator, not a human**. Precision, recall and F1 are on that labelled subset only, not estimates for the dev population.

Validity: V0 reproduces Phase 9 on every row: **yes**; rows whose handoff decision changed: 9, all labelled: **yes**; live model calls: 0 (cache hits 406).

| variant | TP | FP (unnecessary handoffs) | FN (missed) | precision | recall | F1 | missed by gold reason |
|---|---|---|---|---|---|---|---|
| V0 production (this run) | 25 | 41 | 1 | 0.379 | 0.962 | 0.543 | {'repeat_contact': 1} |
| **P10 candidate** | 25 | 32 | 1 | 0.439 | 0.962 | 0.602 | {'repeat_contact': 1} |
| Phase 9 V1 (stored run) | 0 | 0 | 26 | None | 0.0 | 0.0 | {'repeat_contact': 22, 'hardware': 3, 'private_info': 1} |
| Phase 9 V2 (stored run) | 3 | 18 | 23 | 0.143 | 0.115 | 0.128 | {'repeat_contact': 20, 'hardware': 3} |
| Phase 9 V3 (stored run) | 24 | 30 | 2 | 0.444 | 0.923 | 0.6 | {'hardware': 1, 'repeat_contact': 1} |
| Phase 9 V4 (stored run) | 3 | 9 | 23 | 0.25 | 0.115 | 0.158 | {'repeat_contact': 20, 'hardware': 3} |

Outcomes over all 240 rows: V0 {'HANDOFF': 153, 'CLARIFY': 85, 'AUTO_CANDIDATE': 2}; P10 {'HANDOFF': 144, 'CLARIFY': 93, 'AUTO_CANDIDATE': 3}

Model-raised `needs_private_info`: 26 of 153 model calls, 0 corroborated by the deterministic rule. Model fallback rate 0.0065.

| check | result |
|---|---|
| no_new_protected_misses | pass |
| at_most_one_new_miss | pass |
| at_least_3_fewer_unnecessary_handoffs | pass |
| fallback_within_5pp | pass |

Δ unnecessary handoffs -9; Δ missed escalations +0; handoffs removed 9 (9 correctly, Wilson 95% [0.701, 1.0]); removed handoffs now {'CLARIFY': 8, 'AUTO_CANDIDATE': 1}; new misses none.

**Decision: accept and enable in the release configuration.**

## Rows whose handoff decision changed

| id | V0 | P10 | gold should_escalate | gold reason | model flags | message (redacted) |
|---|---|---|---|---|---|---|
| 2888444 | HANDOFF/private_info | CLARIFY/low_confidence | False | none | needs_private_info | hey your iPhone X keeps randomly crashing when I’m doing things fix it much appreciated thanks. |
| 2945748 | HANDOFF/private_info | CLARIFY/insufficient_evidence | False | none | needs_private_info | my phone is constantly restarting since the last update, how can this be solved please ???? |
| 491499 | HANDOFF/private_info | CLARIFY/low_confidence | False | none | high_frustration, needs_private_info | ain’t shit! And DEFINITELY isn’t shit!! I’ve had my iPhone 7 Plus for mmm..6 months and every app freezes for 10 minutes |
| 509528 | HANDOFF/private_info | CLARIFY/low_confidence | False | none | needs_private_info | I have two devices keeping reboot like this pic. <url> |
| 539898 | HANDOFF/private_info | AUTO_CANDIDATE/none | False | none | high_impact, needs_private_info | Ini iphone 6s knapa restart terus?? Ganggu kerja!! |
| 539979 | HANDOFF/private_info | CLARIFY/low_confidence | False | none | high_impact, needs_private_info | Oh by the way it’s an iPhone 7 iOS 11.1.2 |
| 568452 | HANDOFF/private_info | CLARIFY/low_confidence | False | none | needs_private_info | Dear , thanks for (apparently) putting me in your beta program for iOS 11. Where do I send a list of the bugs I’ve found |
| 585938 | HANDOFF/private_info | CLARIFY/insufficient_evidence | False | none | needs_private_info | my iPhone 6s crashes every sec #fixmyphone |
| 96921 | HANDOFF/private_info | CLARIFY/insufficient_evidence | False | none | needs_private_info | I trained to get a medal. Can not calculate the activity app 😬 itself was an average of 47.2 |
