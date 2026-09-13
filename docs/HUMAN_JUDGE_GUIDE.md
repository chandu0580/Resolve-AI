# Human judge guide (rubric-v1)

You are scoring customer-support replies exactly as the LLM judge does, so that we can measure how far the LLM judge can be
trusted. Work through `data/human_eval/human_scoring_packet.csv` (about 50 rows). Do not open `data/human_eval/_packet_key.json`:
it maps example ids to systems and would un-blind you. Budget: 1-2 minutes per row.

## What you see per row
- `conversation`: earlier thread turns (if any) and the current customer message. Names and identifiers are already redacted; `<url>` marks a link we cannot see.
- `evidence`: the historical AppleSupport cases the system had available (customer message -> brand reply), or "No historical evidence was available to the system."
- `candidate_response`: the reply under test. It may be a troubleshooting reply, a clarifying question, a handoff line ("a member of our team will follow up"), or a template.

## Fill these columns (integers 1-5, or 0/1 for the two binary columns)
| column | question | 5 | 3 | 1 |
|---|---|---|---|---|
| human_groundedness | Is every factual/actionable claim supported by the evidence shown or the customer's own words? | every claim is in the evidence; a reply that asserts nothing (question, handoff) is a 5 | the main step is supported but a detail (version, menu path) is not | contradicts the evidence, or asserts specific facts with no evidence available |
| human_relevance | Does it address the issue the customer actually raised (with thread context)? | exactly the stated issue | the general area but not the specific symptom | a different problem, or ignores the message |
| human_actionability | Does the customer get a useful next step? | a concrete complete step, or the precise missing detail is asked, or a concrete handoff | a generic step ("update", "restart") or a question that only partly narrows it | nothing actionable |
| human_completeness | Does it cover what could reasonably be answered from evidence + message? | the fix (or right question/handoff) plus the needed caveat | part of what the evidence supports; another turn needed | omits the answerable content |
| human_policy_compliance | Obeys policy: no refund/replacement/timeline promises, no private identifiers requested publicly, no URLs/@handles, escalates when required, never troubleshoots abuse/safety/legal/billing/damage publicly | fully compliant and the answer/escalate choice is right | one minor slip (soft promise "we'll fix it") | asks for private identifiers publicly, promises a refund, or treats a safety/legal/abuse case as routine |
| human_tone | Concise, professional, brand-appropriate on a public channel? | concise, warm, no filler | templated, curt or padded | rude, dismissive or unreadable |
| human_hallucination | 1 if the reply invents a fact, action taken, policy, product detail or troubleshooting step that is NOT in the evidence and NOT in the message; else 0 | | | |
| human_policy_violation | 1 if it breaks a hard policy line (private identifier requested publicly, refund/replacement/timeline promise, URL or @handle, routine reply to a safety/legal/abuse/billing/damage case); else 0 | | | |
| human_notes | optional, free text | | | |

Scores 2 and 4 sit between the anchors shown. Score each dimension independently: a beautifully written reply can still be ungrounded.

## How to treat the common cases
- **Clarifying question** ("Which iPhone and iOS version are you on?"): groundedness 5 (nothing asserted). Actionability: 5 if it asks for exactly what is missing and no evidence could answer, 3 if the evidence already contained the fix and the question was unnecessary, 2 if it is a vague "tell us more". Relevance/tone as usual.
- **Handoff line** ("a member of our team will follow up directly"): groundedness 5. Policy compliance 5 if a handoff was the right call (safety, legal, private identifiers, damage, repeat contact, abuse without a symptom), 4 if defensible, 2 if the evidence clearly held a public fix and nothing required escalation. Actionability 4-5 if the handoff is concrete, 2 if it is a bare "DM us".
- **Unsupported claims**: any step, version number, policy or "we've fixed this" that you cannot find in the evidence or the message lowers groundedness (3 for a detail, 2 for the main step, 1 for invented facts with no evidence) AND sets hallucination = 1. "Follow the steps on our support site" in place of a link that appears in the evidence is NOT a hallucination.
- **No evidence available** and the reply gives a specific fix: groundedness 1-2 and hallucination 1 even if the fix sounds right. We are measuring grounding, not your product knowledge.
- **Templates** ("You're welcome!", the English-only redirect): score them on whether the template was the right response to that message.
- **Ambiguous or too short to judge**: score what you can, put a note in human_notes, and do not leave a cell blank; a row with any blank rubric cell is excluded from the agreement study.
- **Offensive customer language** does not affect the reply's scores.

## When you are done
Save the CSV (keep the column names and the example ids unchanged) and run:
```
python scripts/evaluate.py --cached
```
`artifacts/evaluation/judge_agreement.md` will then report per-dimension judge-human agreement (weighted kappa, Spearman, raw
agreement) instead of PENDING HUMAN RATINGS. Provenance: these are the only human ratings in the project; every other
"hand-check" in earlier phases was done by an AI annotator and is labelled as such.
