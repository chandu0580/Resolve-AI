# Annotation guide changelog

## v1.0 (frozen 2026-09-10) — used for annotator A pass
No changes during the pass. The following cases were hard under v1.0 and are proposed clarifications for v1.1,
to be adopted only after annotator B's pass and adjudication (so both passes use the same rules):

| gid | issue | proposed rule |
|---|---|---|
| g015, g056 | iOS/iPadOS *update itself* not installing or not automatic | -> `apps_services` (software-update mechanics), not performance_crash |
| g024 | accessory "not supported" message | -> `connectivity` (accessory/peripheral connection) |
| g048 | "check the DM I sent" | intent `other`, but `should_escalate = true`, reason `repeat_contact` (a human must read the DM). Exception to "other is always false". |
| g060 | how-to question about parental controls | `other` with a public article reply; `should_escalate = false` |
| g087 | Beats/AirPods audio quality issue, no physical fault stated | `connectivity` and clarify; `hardware_damage` only if a fault is stated |
| g125 | thread mentions freezing AND the I.T bug; current message is device info | v1.0 rule "keyboard wins" applied. Consider: label the symptom the *brand is actively troubleshooting* in the thread |
| g146, g170 | macOS root-password security bug | -> `apps_services` (OS software issue with a public fix) |
| g153 | complaint about password-reset waiting period | `account_store_repair`, `should_escalate = false` (public explanation suffices) |
| g185 | "has service been down in <city>" | ambiguous Apple services vs cellular; labelled `connectivity`, clarify |
| g186 | customer explicitly refuses DM, symptom is real | labelled `should_escalate = false` with a public factual answer; flag for adjudication |

## Observations for the report
- Escalation label is harder than intent: 46 of 197 escalate; `repeat_contact` is the most frequent reason and
  the most judgement-dependent (what counts as "already tried the standard steps").
- 4 safety cases in 197 (2%): cable smoke, MBP smoke, Watch burn, self-harm hyperbole. All escalate.
- Multi-turn examples often carry the symptom only in context; the current message is "iPhone 7 Plus" or a URL.
