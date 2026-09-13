# Intent taxonomy: how it was built

1. Embedded 6,000 random first-turn customer messages from the `kb` split with all-MiniLM-L6-v2.
2. K-means with k=18 (deliberately over-clustered), inspected the 5 messages nearest each centroid.
3. Merged clusters into 10 support intents + `other`:

| clusters | intent | note |
|---|---|---|
| 0, 12 | battery_power | 12 is "battery after iOS 11", 0 is generic battery |
| 2, 14 | performance_crash | freezing / "update ruined my phone" |
| 1, 5, 6, 10 | keyboard_text_bug | the iOS 11.1 "I" -> "A?" bug dominates Nov 2017 |
| 4 | connectivity | wifi/bluetooth toggling |
| 11 | data_loss_sync | photos disappearing |
| 15, 3 (part) | apps_services | Apple Music, notifications |
| 17 | account_store_repair | Apple ID, store visits, orders |
| 16 | hardware_damage | MacBook dying, paid repairs |
| 8, 9, 13 | general_complaint | "fix it <url>", rants with no detail |
| 7 | non_english | Spanish / Portuguese |

**What I chose not to model:** device type (iPhone/Mac/Watch) as a separate axis; it is orthogonal to intent and the reply drafter reads it from the text anyway.

## Labelling guide (used for the golden set)
- Label the *primary actionable problem*. "Battery dies since update and it's slow" -> battery_power (first concrete symptom).
- keyboard_text_bug beats performance_crash when the "I" bug is mentioned at all.
- general_complaint only when no concrete symptom is given. "iOS 11 sucks, fix it" -> general_complaint. "iOS 11 sucks, my phone freezes" -> performance_crash.
- account_store_repair covers anything requiring Apple to look up the customer (orders, ID, repairs).
- hardware_damage requires a physical fault; "phone is broken" with no detail -> general_complaint.
- Multi-turn: label the *current* message in light of the context.
