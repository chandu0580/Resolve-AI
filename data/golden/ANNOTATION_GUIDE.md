# Golden-set annotation guide — v1.1

Version history: v1.0 frozen 2026-09-10 and used for both independent passes (A, B). v1.1 adds deterministic rules
R1-R7 derived from the seven systematic disagreement patterns in `AGREEMENT_ANALYSIS.md`, plus four metadata flags.
v1.1 is applied to both label sets by `scripts/phase1/d2_apply_v11.py`; every changed row is listed in
`golden_v11_diff.csv`. Not frozen until the owner reviews that diff.

Brand: AppleSupport. Unit: one customer tweet (plus prior thread turns, if any). Label what a trained AppleSupport
agent would decide, not what the brand historically did (52% of historical replies are "DM us" regardless of merit).

## Label 1: `intent` (exactly one)
| intent | definition |
|---|---|
| battery_power | battery drains, won't charge, dies at N%, random shutdowns, device overheating / "warm" |
| performance_crash | OS/device-wide: freezing, lag, slow, reboots, boot loops, stuck on logo, system-level crashes, after-update slowness |
| keyboard_text_bug | the iOS 11.1 "I" -> "A [?]" autocorrect bug, "it" -> "I.T", question-mark/emoji boxes, any keyboard/autocorrect glitch |
| connectivity | Wi-Fi, Bluetooth, cellular/SIM, hotspot, AirDrop, CarPlay, GPS/location, accessory/peripheral connection ("not supported", pairing) |
| data_loss_sync | photos/contacts/messages/notes/library missing, iCloud sync/backup/restore, storage full, data migration |
| apps_services | a specific app or service fails: Apple Music, App Store, iTunes (incl. sync), iMessage, FaceTime, Mail, Safari, Siri, Camera app, Clock, Phone app, notifications, third-party apps, OS features such as software-update mechanics, clipboard, language settings |
| account_store_repair | Apple ID / password / 2FA / activation lock, orders, delivery, billing/refund, Apple Store or Genius Bar visit, repair status, warranty, AppleCare, appointments |
| hardware_damage | explicit physical damage or physical fault evidence on a device: cracked/black/lined screen, liquid, dead Mac, dead touch screen, blown speaker, smoke, burns |
| general_complaint | support request with no concrete actionable symptom (venting, "fix it", sarcasm), AND the fallback for support requests no intent genuinely fits |
| non_english | message not in English |
| other | not a support request: thanks, closures ("done", "sent"), jokes, product/price/availability questions, praise, suggestions, off-topic |

### Deterministic rules (v1.1)
**R2 — app-confined vs device-wide.** A failure confined to one named app/service/OS feature -> `apps_services`.
A crash/freeze/reboot/lag of the whole device or OS -> `performance_crash`. If the scope is genuinely not stated,
do not infer it; use the broader category `performance_crash`.

**R3 — accessories.** An accessory problem (dongle, cable, EarPods/AirPods/Beats, Watch band) is never
`hardware_damage` by itself. `hardware_damage` requires explicit physical damage or physical fault evidence
(smoke, burn, cracked, dead component). Functional accessory issues take the functional category: connection/pairing
-> `connectivity`; won't charge -> `battery_power`; audio quality with no fault stated -> `connectivity` (clarify).

**R4 — no new intents.** If no intent genuinely fits a support request, use `general_complaint` and set
`taxonomy_gap = true`. Do not stretch a neighbouring intent. Known gaps recorded so far: OS security-vulnerability
questions (macOS root), software-update mechanics, GPS/location, clipboard/shortcuts. Where the v1.1 table above
now names a home for a gap (update mechanics, GPS, clipboard), use it and still set `taxonomy_gap = true`.

**R5 — unseen attachments.** Use only information present in the annotation input (message text + context). Never
infer a symptom from a screenshot/video/link. If the symptom is only in an attachment, label from the words alone
(usually `general_complaint`) and set `insufficient_context = true`. `evidence_unavailable = true` is set
automatically whenever the customer message contains an attachment token (`<url>`).
Exception that is *present in the input*: the corrupted "I" glyph (U+0049 U+FE0F, rendered "I️") appearing in the
customer's own text is itself the keyboard bug manifesting; a message containing that glyph and referring to "this
glitch/bug/fix this" is `keyboard_text_bug`.

**R6 — multiple symptoms.** The primary intent is the issue representing the customer's main requested resolution
or blocker. Do not blindly take the first- or last-mentioned symptom. Ask: what is the customer asking to have
fixed? If several meaningful symptoms are present and the taxonomy cannot hold them independently, set
`multi_intent = true`. Same-bucket symptoms (battery drain + charging) are not multi-intent.

**R7 — meta requests and policy complaints.** Do not infer an underlying issue that is not stated. "Check the DM
I sent" is `other`; a complaint about a policy (password-reset waiting period) is labelled by the policy's domain
(`account_store_repair`) with no inferred account problem. Set `insufficient_context = true`.

Multi-turn: label the current message in light of the context ("still doing it" after a battery thread ->
battery_power). A "customer:" turn in context is assumed to be the same customer unless the current message shows
otherwise ("I have the same problem" = different person).

## Label 2: `should_escalate` (true / false)
`true` = a public tweet cannot resolve this; a human must take it to DM or a case. Escalate when ANY of:
- **safety**: self-harm, threats, medical emergency, burns, smoke, electric shock.
- **legal_media**: lawyer, lawsuit, press, regulator.
- **private_info**: resolution requires serial, IMEI, Apple ID, order/case/repair number, payment, address, appointment.
- **hardware**: explicit physical damage or fault (per R3) or a repair/warranty decision.
- **repeat_contact** (R1): ONLY when the customer explicitly indicates prior attempts or repeated contacts:
  "restarted three times", "tried resets", "I reset network settings", "third time contacting you", "still no
  response from you", "I sent a DM", "went to the store", or explicit completion of a step the brand suggested in
  context. Vague phrases do NOT count: "still happening", "nothing works", "tried everything", "usual tricks", and a
  problem *recurring* ("3rd time this happened") is not an attempt or a contact. A statement of attempts made by a
  different customer in the thread does not count. Structural criterion that also counts: >= 2 brand turns in
  context with no concrete step yet given.
- **vague_hostile**: abusive AND no actionable symptom.
Otherwise `false`. `non_english` is always `false`. `other` is `false` except the R1 explicit-prior-contact case.

## Label 3: `escalation_reason`
`safety | legal_media | private_info | hardware | repeat_contact | vague_hostile | none` (`none` iff should_escalate is false).
**Priority when several apply:** safety > legal_media > private_info > hardware > repeat_contact > vague_hostile.

## Metadata flags (v1.1, boolean, default false)
| flag | meaning |
|---|---|
| taxonomy_gap | no intent genuinely fits; fallback used (R4) |
| insufficient_context | symptom or request not stated in the input text (R5, R7) |
| multi_intent | several meaningful symptoms, taxonomy holds only one (R6) |
| evidence_unavailable | message references an attachment we cannot see (`<url>` present); set automatically |

## Optional `note`: free text for hard cases.

## Annotator protocol
Pass 1 (A) and pass 2 (B) were done independently under v1.0. Provenance: **Annotator B was an isolated AI
annotator, not an independent human; agreement figures must never be described as human-human agreement.**
v1.1 rules are applied to both passes by script; the owner reviews the diff; only then is the gold set frozen.

## Sampling (unchanged, see `scripts/phase1/c_golden_sample.py`)
Temporal holdout only. 120 by weak-label intent (>= 8 each, keyboard bug <= 20), 40 multi-turn, 20 short, 20 edge.
197 sampled. Weak labels are hidden from annotators.
