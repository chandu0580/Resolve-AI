# Input robustness

53 messages through the real agent (no model) and 15 bodies through `POST /api/v1/resolve`. The check is that nothing crashes, every message ends on one of the three product outcomes with a named rule and customer-safe text, and a malformed body is rejected by the schema rather than by an exception.

**Result: PASS** - 0 crashes, 0 contract failures.

| class | case | chars | outcome | rule | evidence | reply |
|---|---|---|---|---|---|---|
| empty | empty string | 0 | CLARIFICATION_REQUIRED | `insufficient_context` | INSUFFICIENT | We'd like to help. Could you tell us which device you're using, which software version is ... |
| empty | single space | 1 | CLARIFICATION_REQUIRED | `insufficient_context` | INSUFFICIENT | We'd like to help. Could you tell us which device you're using, which software version is ... |
| whitespace | spaces and tabs | 9 | CLARIFICATION_REQUIRED | `insufficient_context` | INSUFFICIENT | We'd like to help. Could you tell us which device you're using, which software version is ... |
| whitespace | newlines only | 3 | CLARIFICATION_REQUIRED | `insufficient_context` | INSUFFICIENT | We'd like to help. Could you tell us which device you're using, which software version is ... |
| punctuation | question marks | 3 | CLARIFICATION_REQUIRED | `insufficient_context` | INSUFFICIENT | We'd like to help. Could you tell us which device you're using, which software version is ... |
| punctuation | repeated punctuation | 10 | CLARIFICATION_REQUIRED | `insufficient_context` | INSUFFICIENT | We'd like to help. Could you tell us which device you're using, which software version is ... |
| punctuation | mixed punctuation | 10 | CLARIFICATION_REQUIRED | `insufficient_context` | INSUFFICIENT | We'd like to help. Could you tell us which device you're using, which software version is ... |
| punctuation | single dot | 1 | CLARIFICATION_REQUIRED | `insufficient_context` | INSUFFICIENT | We'd like to help. Could you tell us which device you're using, which software version is ... |
| very_short | one letter | 1 | AUTO_HANDLE | `canned:acknowledgement` | INSUFFICIENT | Thanks for letting us know. If anything else comes up, we're here to help. |
| very_short | two letters | 2 | AUTO_HANDLE | `canned:acknowledgement` | INSUFFICIENT | Thanks for letting us know. If anything else comes up, we're here to help. |
| very_short | help | 4 | CLARIFICATION_REQUIRED | `insufficient_context` | INSUFFICIENT | We'd like to help. Could you tell us which device you're using, which software version is ... |
| very_short | bare yes with no thread | 3 | AUTO_HANDLE | `canned:acknowledgement` | INSUFFICIENT | Thanks for letting us know. If anything else comes up, we're here to help. |
| greeting | hi | 2 | AUTO_HANDLE | `canned:greeting` | INSUFFICIENT | Hi! What can we help you with today? |
| greeting | hey bro | 7 | AUTO_HANDLE | `canned:greeting` | INSUFFICIENT | Hi! What can we help you with today? |
| greeting | good morning | 12 | AUTO_HANDLE | `canned:greeting` | INSUFFICIENT | Hi! What can we help you with today? |
| greeting | thanks | 6 | AUTO_HANDLE | `canned:other` | INSUFFICIENT | You're welcome! If anything else comes up, we're here to help. |
| casing | all lower | 40 | CLARIFICATION_REQUIRED | `evidence_gate` | INSUFFICIENT | We'd like to help with the battery. Could you tell us which software version is installed ... |
| casing | ALL UPPER | 40 | CLARIFICATION_REQUIRED | `evidence_gate` | INSUFFICIENT | We'd like to help with the battery. Could you tell us which software version is installed ... |
| casing | Title Case | 40 | CLARIFICATION_REQUIRED | `evidence_gate` | INSUFFICIENT | We'd like to help with the battery. Could you tell us which software version is installed ... |
| casing | aLtErNaTiNg | 40 | CLARIFICATION_REQUIRED | `evidence_gate` | INSUFFICIENT | We'd like to help with the battery. Could you tell us which software version is installed ... |
| casing | shouting a complaint | 13 | HUMAN_HANDOFF | `account_access` | INSUFFICIENT | To keep your account safe we need to help with this privately. A member of our team will f... |
| casing | lower complaint | 13 | HUMAN_HANDOFF | `account_access` | INSUFFICIENT | To keep your account safe we need to help with this privately. A member of our team will f... |
| casing | mixed complaint | 13 | HUMAN_HANDOFF | `account_access` | INSUFFICIENT | To keep your account safe we need to help with this privately. A member of our team will f... |
| emoji | emoji only | 3 | CLARIFICATION_REQUIRED | `insufficient_context` | INSUFFICIENT | We'd like to help. Could you tell us which device you're using, which software version is ... |
| emoji | emoji with issue | 25 | HUMAN_HANDOFF | `private_info` | INSUFFICIENT | We'd like to look into this with you. Because we'll need some details about your device or... |
| emoji | zwj family sequence | 7 | CLARIFICATION_REQUIRED | `insufficient_context` | INSUFFICIENT | We'd like to help. Could you tell us which device you're using, which software version is ... |
| typos | heavy typos | 49 | AUTO_HANDLE | `canned:non_english` | INSUFFICIENT | We offer support via Twitter in English. You can get help in your preferred language here:... |
| typos | no spaces | 18 | CLARIFICATION_REQUIRED | `insufficient_context` | INSUFFICIENT | We'd like to help. Could you tell us which device you're using, which software version is ... |
| unicode | fullwidth latin | 23 | CLARIFICATION_REQUIRED | `insufficient_context` | INSUFFICIENT | We'd like to help. Could you tell us which device you're using, which software version is ... |
| unicode | combining accents and an RTL mark | 25 | CLARIFICATION_REQUIRED | `evidence_gate` | INSUFFICIENT | We'd like to help with the battery. Could you tell us which device you're using, which sof... |
| unicode | zero-width joiners inside words | 25 | CLARIFICATION_REQUIRED | `evidence_gate` | INSUFFICIENT | We'd like to help with the battery. Could you tell us which device you're using, which sof... |
| unicode | control characters | 25 | CLARIFICATION_REQUIRED | `evidence_gate` | INSUFFICIENT | We'd like to help with the battery. Could you tell us which software version is installed ... |
| non_english | spanish | 49 | AUTO_HANDLE | `canned:non_english` | INSUFFICIENT | We offer support via Twitter in English. You can get help in your preferred language here:... |
| non_english | hindi | 30 | AUTO_HANDLE | `canned:non_latin_script` | INSUFFICIENT | We offer support via Twitter in English. You can get help in your preferred language here:... |
| non_english | japanese | 15 | AUTO_HANDLE | `canned:non_latin_script` | INSUFFICIENT | We offer support via Twitter in English. You can get help in your preferred language here:... |
| non_english | arabic | 21 | AUTO_HANDLE | `canned:non_latin_script` | INSUFFICIENT | We offer support via Twitter in English. You can get help in your preferred language here:... |
| very_long | 4k characters | 4000 | CLARIFICATION_REQUIRED | `evidence_gate` | WEAK | We'd like to help with the battery. Could you tell us what you've already tried? |
| very_long | one long word | 3000 | CLARIFICATION_REQUIRED | `insufficient_context` | INSUFFICIENT | We'd like to help. Could you tell us which device you're using, which software version is ... |
| duplicate | same sentence repeated | 300 | CLARIFICATION_REQUIRED | `low_confidence` | INSUFFICIENT | We'd like to help. Could you tell us which software version is installed (Settings > Gener... |
| duplicate | identical turn repeated in the thread | 23 | CLARIFICATION_REQUIRED | `evidence_gate` | INSUFFICIENT | We'd like to help with the battery. Could you tell us which software version is installed ... |
| quoted_history | quoted brand reply | 72 | CLARIFICATION_REQUIRED | `evidence_gate` | INSUFFICIENT | We'd like to help. Could you tell us whether it happens in one app or everywhere? |
| quoted_history | pasted transcript | 76 | HUMAN_HANDOFF | `private_info` | INSUFFICIENT | We'd like to look into this with you. Because we'll need some details about your device or... |
| short_reply | still happening | 15 | CLARIFICATION_REQUIRED | `evidence_gate` | INSUFFICIENT | We'd like to help with the battery. Could you tell us what you've already tried? |
| short_reply | that didn't work | 16 | CLARIFICATION_REQUIRED | `evidence_gate` | WEAK | We'd like to help with the battery. Could you tell us what you've already tried? |
| short_reply | bare yes in a thread | 3 | CLARIFICATION_REQUIRED | `evidence_gate` | WEAK | We'd like to help with the battery. Could you tell us what you've already tried? |
| injection | direct override | 62 | HUMAN_HANDOFF | `prompt_injection` | INSUFFICIENT | We'd like to help with your device or account. A member of our team will follow up with yo... |
| injection | obfuscated override | 51 | HUMAN_HANDOFF | `prompt_injection` | INSUFFICIENT | We'd like to help with your device or account. A member of our team will follow up with yo... |
| injection | injection after a real issue | 88 | HUMAN_HANDOFF | `prompt_injection` | WEAK | We'd like to help with your device or account. A member of our team will follow up with yo... |
| injection | injection inside quoted history | 50 | HUMAN_HANDOFF | `private_info` | INSUFFICIENT | We'd like to look into this with you. Because we'll need some details about your device or... |
| pii | email and phone | 74 | HUMAN_HANDOFF | `private_info` | INSUFFICIENT | We'd like to look into this with you. Because we'll need some details about your device or... |
| pii | order and serial | 51 | HUMAN_HANDOFF | `payment_billing` | INSUFFICIENT | We'd like to look at this with you. Because it involves your account details, a member of ... |
| human_request | asks for a person | 28 | HUMAN_HANDOFF | `human_requested` | INSUFFICIENT | Of course. A member of our team will pick this up with you directly. |
| safety | safety wording | 44 | HUMAN_HANDOFF | `hardware` | INSUFFICIENT | We'd like to look at this with you. A member of our team will follow up with you directly ... |

## HTTP boundary

| case | status | accepted |
|---|---|---|
| empty text rejected by the schema | 422 | 422 |
| whitespace-only text reaches the agent | 200 | 200 |
| no turns rejected | 422 | 422 |
| missing conversation field | 422 | 422 |
| unknown top-level field rejected | 422 | 422 |
| unknown turn field rejected | 422 | 422 |
| bad role rejected | 422 | 422 |
| last turn must be the customer's | 400 | 400 |
| text over the configured limit | 413 | 413, 422 |
| text over the schema cap | 422 | 422 |
| too many turns | 422 | 422, 413 |
| null conversation | 422 | 422 |
| conversation sent as a string | 422 | 422 |
| raw customer id rejected by the metadata pattern | 422 | 422 |
| bad locale rejected | 422 | 422 |
