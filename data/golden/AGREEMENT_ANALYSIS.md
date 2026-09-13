# Inter-annotator agreement: golden set v1.0 (197 examples)

**Status: analysis only. No adjudication has been done. Gold set is NOT frozen.**

## Provenance (read this first)
- Annotator A: Claude, labelling in the main project session under guide v1.0 (`scripts/phase1/d_annotatorA_labels.py`).
- Annotator B: Claude, in an isolated agent session that was given only `ANNOTATION_GUIDE.md` and the unlabelled CSV,
  with instructions not to read any other file (`data/golden/annotatorB_labels.py`). It reported 22 rows it found ambiguous.
- Both annotators are the same model family, isolated by context, not two humans. The kappa values below are therefore an
  **upper bound** on what human-human agreement would look like; the disagreement *patterns* are the reliable output.
  A human adjudication pass by the project owner is the step that gives the gold set its credibility.

## Headline numbers (`agreement_report.json`)
| label | agreement | Cohen's kappa | n |
|---|---|---|---|
| intent (11 classes) | 92.9% | **0.920** | 197 |
| should_escalate | 96.4% | **0.885** | 197 |
| escalation_reason, when both escalate | 97.1% | n/a | 34 |

Escalation cross-tab: A=False/B=False 156, A=True/B=True 34, A=True/B=False 4, A=False/B=True 3.
Annotator B escalates 37 (18.8%), A escalates 38 (19.3%).

Agreement by sampling stratum (strata were hidden from both annotators):
| stratum | intent | escalation | n |
|---|---|---|---|
| edge cases | 94.7% | 100% | 19 |
| by intent | 94.1% | 98.3% | 118 |
| multi-turn | 92.5% | **90.0%** | 40 |
| short (< 40 chars) | **85.0%** | 95.0% | 20 |

Short messages are hardest for intent; multi-turn threads are hardest for escalation.

## Disagreements: 21 rows (14 intent-only, 7 escalation-only, 0 both). Full list: `golden_disagreements.csv`.

## Systematic patterns (what the guide does not settle)

### P1. "Already tried the standard steps" is undefined -> 5 of 7 escalation disagreements
g102, g126, g131, g135, g191. A treats "retried many times", "3rd time this happened", "no chance with the usual
tricks" and "updated + apps current, what's next?" as repeat_contact. B counts only explicitly named standard steps
(restart / update / reset / reinstall) and requires the thread to show them. Proposed v1.1 rule: enumerate the standard
steps; a vague "tried everything" counts only if the brand has already given at least one concrete step in context.
This is the single biggest source of escalation noise and will show up again in the deterministic policy.

### P2. App-confined crash vs device-wide crash -> apps_services vs performance_crash
g121 (Phone app), g134 (Safari). Guide lists "app crashes" under performance_crash and "Mail/Safari not working"
under apps_services, so both readings are legal. Proposed rule: crash confined to one named app -> apps_services;
device-wide freeze/reboot/lag -> performance_crash.

### P3. Accessory problems without a stated physical fault -> connectivity vs hardware_damage
g024 (dongle "not supported"), g087 (Beats audio). Guide says hardware_damage "requires a physical fault"; B applied
hardware_damage anyway. Proposed rule: accessories/peripherals with no fault stated -> connectivity, clarify.

### P4. Security-vulnerability questions have no bucket
g146, g170 (macOS root bug). A: apps_services (OS software issue with a public fix). B: other (not a device symptom).
Proposed rule: questions about a known OS bug/vulnerability with a public fix -> apps_services.

### P5. Inferring from unseen media
g063, g085, g113 (screenshot/video only), g077 ("warm and glitchy"). A defaults to general_complaint when the
symptom is only in an attachment; B infers a probable symptom from surrounding words. Proposed rule: do not infer
from media we cannot see; label the words only. Exception: a symptom named in the text wins (g077 "warm" ->
battery_power is B's reading and is arguably correct under the first-concrete-symptom rule).

### P6. Two symptoms in one message: first-mentioned vs primary blocker
g171 (black screen + 2FA blocks appointment), g029 (Cmd+V broken), g148 (Wi-Fi sync to iTunes), g011 (I-glyph
visible in text). The guide says "first concrete symptom"; B sometimes chose the primary blocker or a bucket-fit.
g011 is a genuine catch by B: the corrupted "I" character is in the message text itself, so keyboard_text_bug is
defensible. Proposed: keep first-symptom rule, add "the I-glyph corruption in the text counts as mentioning the bug".

### P7. Meta-requests and policy explanations
g048 ("check the DM I sent"): A escalates (human must read the DM), B does not (no symptom). g153 (password reset
delay): A explains publicly, B escalates (private_info). Both need an explicit line in the guide.

## What annotator B flagged that A did not
B's 22 ambiguous rows overlap A's 10 HARD cases on g015/g056 (software-update bucket), g024, g029, g060, g087, g146,
g153. B additionally questioned g007, g102, g109, g128 (GPS bucket), g152 (mechanical two-turn rule), g157, g171.
Three of B's proposed guide additions (software-update failures, GPS/location, clipboard/shortcut bugs) are
consistent with A's notes and with P2-P4 above.

## Recommendation for adjudication (not executed)
1. Owner reviews the 21 rows in `golden_disagreements.csv` and decides each; where a rule is needed, adopt one of the
   P1-P7 proposals as guide v1.1 and re-apply it to *all* 197 rows, not just the disputed ones.
2. Record every rule adopted in `guide_changelog.md` with the gids it changed.
3. Only then run `python scripts/phase1/d_agreement.py --freeze` on `golden_adjudicated.csv`.
4. In the report, state: kappa 0.92 / 0.885 between two context-isolated AI annotators; human adjudication on 21 rows;
   the P1 threshold is the known soft spot of the escalation label.
