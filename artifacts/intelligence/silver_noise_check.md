# Silver-label noise check

60 TRAIN rows (20 per band under silver-v1, seed 42) hand-labelled under guide v1.1 by Claude (AI annotator). Labels fixed before any silver revision; v2 is scored on the same rows.

## silver-v1

| band | precision | n |
|---|---|---|
| HIGH | 0.65 | 20 |
| MEDIUM | 0.35 | 20 |
| LOW | 0.4 | 20 |

Estimated precision over all train rows: 0.52; over the HIGH+MEDIUM rows used for training: 0.58.

Examples of wrong silver labels:

- `2303444` [HIGH] silver=non_english human=data_loss_sync: thanks for your update which erased all my music (seed 'el ' matched inside an English word)
- `1585322` [HIGH] silver=non_english human=keyboard_text_bug: I️ I️ I️ WANT ANSWERS (glyph counted as non-ASCII)
- `1924716` [HIGH] silver=battery_power human=other: rip a flap of skin off switching the charger cord (joke; 'charg' seed)
- `2852306` [LOW] silver=general_complaint human=battery_power: help! My iPhone won't turn on

## silver-v2

| band | precision | n |
|---|---|---|
| HIGH | 0.818 | 22 |
| LOW | 0.308 | 26 |
| MEDIUM | 0.333 | 12 |

Estimated precision over all train rows: 0.549; over the HIGH+MEDIUM rows used for training: 0.711.

Examples of wrong silver labels:

- `2261581` [LOW] silver=general_complaint human=performance_crash: What’s wrong with the iPhone period? Mine keep glitching and it’s making me mad🤦🏽‍♀️ <url>
- `1924716` [LOW] silver=general_complaint human=other: Anyone else rip a flap of skin off their fingers when switching out the charger extension cord? No? Just me that’s incompetent? 😫
- `2774292` [LOW] silver=general_complaint human=data_loss_sync: Understandable. I was using Microsoft Word. My laptop updated to the newest system and when it came back on, my work was gone! Interesting thing is that it reco
- `1979944` [LOW] silver=general_complaint human=performance_crash: ay man yall wrong for freezing my phone and deleting all my messages!
- `2299868` [HIGH] silver=performance_crash human=apps_services: Only podcasts were effected. I was using the second to most recent version, I updated after it happened in the vain hopes it was a glitch an update could fix. I
- `1681698` [HIGH] silver=connectivity human=other: , iOS needs a way to turn off cellular data roaming while in airplane mode.
- `1657754` [LOW] silver=general_complaint human=keyboard_text_bug: Hi only like 1/2 my emojis are loading since the update cc
- `2303444` [LOW] silver=general_complaint human=data_loss_sync: Dear - thanks for your #iphone #ios update which now not only made my phone work even worse but also erased all my music. #killingme

## What changed in v2
- word-boundary seed matching (v1: `el ` matched inside `cancel `, `la ` inside `formula `)
- corrupted I-glyph -> keyboard_text_bug (guide v1.1 rule R5)
- non_english vote needs two non-English function words; the glyph is not counted as non-ASCII
- `won't turn on` / `dead phone` -> battery_power

Coverage HIGH+MEDIUM: v1 67.6% (precision ~0.58) -> v2 60.0% (precision ~0.71); HIGH only: 8,403 rows at ~0.82.