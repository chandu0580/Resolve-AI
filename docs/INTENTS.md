# Intent taxonomy contract (v1.1, frozen)

Eleven classes, defined by `data/golden/ANNOTATION_GUIDE.md` v1.1 and implemented in `resolveai/models/taxonomy.py`. The
classifier (`resolveai/intelligence/classifier.py`) outputs `IntentResult`: `intent`, calibrated `confidence`, `top3`
alternatives, `confidence_band` (HIGH/MEDIUM/LOW), `calibration` metadata, `secondary_intents` + `multi_intent`,
`insufficient_context`, `taxonomy_gap`. No hidden reasoning is produced or stored.

| intent | includes | excludes | representative (invented, not golden) | ambiguous boundary |
|---|---|---|---|---|
| battery_power | drain, won't charge, dies at N%, random shutdowns, overheating, won't turn on | accessory charging cables without a device symptom | "battery went 100 to 30 in an hour since 11.1" | vs performance_crash when "dies" means reboots |
| performance_crash | device/OS-wide freeze, lag, reboot loop, stuck on logo, slow after update | a crash confined to one named app | "iPhone keeps restarting every 30 seconds" | vs apps_services (scope) |
| keyboard_text_bug | I -> A?, it -> I.T, question-mark/emoji boxes, autocorrect glitches, the corrupted I-glyph in the text | | "every time I type i it shows A and a box" | vs general_complaint when only "this glitch" is said without the glyph |
| connectivity | Wi-Fi, Bluetooth, cellular/SIM, hotspot, AirDrop, CarPlay, GPS, accessory pairing/"not supported" | | "wifi turns itself back on" | vs apps_services for iTunes Wi-Fi sync (requested resolution decides) |
| data_loss_sync | missing photos/contacts/notes/library, iCloud sync/backup/restore, storage, migration | | "restored from backup and all photos are gone" | vs apps_services when the app is the subject |
| apps_services | one named app/service or OS feature fails (Music, App Store, iMessage, Mail, Safari, Camera, update mechanics, clipboard) | device-wide symptoms | "Apple Music shows a black screen when I open it" | vs performance_crash |
| account_store_repair | Apple ID/2FA/activation lock, orders, billing, store visits, repairs, warranty, appointments | complaints about the policy itself (still this class, escalate=false) | "charged twice for the same subscription" | vs data_loss_sync for iTunes purchases missing |
| hardware_damage | explicit physical damage or fault: cracked/lined screen, liquid, dead touch screen, blown speaker, smoke, burns | accessory issues without a stated fault | "screen has vertical lines after it fell" | vs performance_crash for "screen flickers" |
| general_complaint | venting / "fix it" with no concrete symptom; fallback when no class fits (taxonomy_gap) | anything with a concrete symptom | "iOS 11 is garbage, sort it out" | vs other for non-support rants |
| non_english | message not in English | English with one foreign word | "mi iphone no carga desde ayer" | code-switched tweets |
| other | not a support request: thanks, closures, jokes, product/price questions, feature requests, off-topic | | "when does the iPhone X ship in the UK?" | closures inside a support thread |

## Known taxonomy gaps (recorded on golden with `taxonomy_gap = true`, 7 rows)
OS security-vulnerability questions (macOS root), software-update mechanics, GPS/location, clipboard/shortcut bugs. Rule R4:
no new classes for a few examples; fallback is general_complaint (or the nearest functional class) with the flag set.

## Confidence bands (set on dev calibration, frozen in the model artifact)
| band | threshold | golden accuracy | purpose |
|---|---|---|---|
| HIGH | p >= 0.75 | 0.958 (n=48) | act on the intent: intent-boosted retrieval, intent-specific strategies |
| MEDIUM | p >= 0.40 | 0.613 (n=75) | hint only: mild retrieval boost, keep alternatives visible |
| LOW | otherwise | 0.378 (n=74) | unknown: no intent gating; the policy may escalate on low confidence |
The classifier never decides escalation; bands are inputs to the deterministic policy.

## Multi-intent
`secondary_intents` are alternatives with calibrated probability >= 0.20 and >= 50% of the primary; `multi_intent` is
their presence. On golden this over-fires (44 predicted vs 10 annotated, 3 correct), so the flag is advisory only: it
widens retrieval (allowed intents) and marks ambiguity; it never adds classes and never blocks handling on its own.
