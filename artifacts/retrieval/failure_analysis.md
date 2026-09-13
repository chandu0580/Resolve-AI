# Retrieval failure analysis (Phase 2)

Final configuration: `dense:bge-small+subst` with gate-v2. Golden queries: 197. Queries with a usable reference
(substantive own reply AND a same-resolution case exists in the KB): 46. Misses (reference exists, no hit in top-5): 32.
Categories below overlap; counts from `analysis.json`; examples are real golden rows (PII already redacted).

## The ceiling comes first
Before categorising misses: the retrieval-depth curve for dense BGE on the 46 reference queries is
recall@1 0.22, @5 0.33, @10 0.37, @50 0.41, @100 0.48, @200 0.52, and 22 of 46 are never found within 200 candidates.
The same-resolution reply exists in the KB but the *customer message* attached to it is phrased too differently for
message-to-message similarity to surface it. Every ranking improvement below rank 5 is therefore worth at most a few
points; the large gain requires indexing something other than the customer message alone (see hypotheses H1, H2).

## Failure categories (32 misses)
| category | n | what it looks like | example |
|---|---|---|---|
| contradictory historical cases | 12 | top-5 substantive replies prescribe different actions (update vs reset vs ask a question); no majority | g000 speaker/headphone-jack: replies ask iOS version, link an article, ask for details |
| very short message | 10 | < 40 chars; embedding has nothing to anchor on | g028 "When will we get the TV app in the UK?"; g047 "Thank you" (matches other thanks, but the reference reply is a different closure template) |
| ambiguous intent | 9 | retrieved cases split across intents | g058 billing alert + can't download: neighbours are half account, half App Store |
| noisy Twitter language | 9 | profanity / emoji / slang around the symptom | g005 "fix the fcking I problem…": top-5 are all correct keyboard-bug workarounds, but the judge counts it a miss because the own reply says "update to 11.1.2" in different words -> judge false negative, not a retrieval failure |
| customer-specific | 7 | account / order / repair cases whose resolution needs private data | g019 account recovery since Nov 20: KB replies are generic Apple-ID articles |
| multiple symptoms | 1 | Face ID + freezes + touch sensitivity | g089: neighbours match each symptom separately |
| rare intent | 1 | hardware_damage has 7 golden rows and few substantive KB replies | g000 |
| insufficient context | 1 | "dear god please help me <url>" | g169: cosine 0.96 with other "help me <url>" tweets; gate says conflicting |
| lexical mismatch | 0 | every miss still had top cosine >= 0.6 | |
| semantic mismatch | 0 | | |
| taxonomy gap | 0 | (taxonomy-gap rows have no reference at all: 0 of 7) | |
| uncategorised | 1 | g024 dongle "not supported" | neighbours are generic accessory questions |

Slices (recall@5 on reference queries; sufficient rate on all): first-turn 0.38 / 8.1%; multi-turn 0.25 / 4.2%;
short 0.25 / 6.7%; customer-seen-in-KB 0.40 / 0%; multi-intent 0.0 / 0%; insufficient-context 0.0 / 5.6%.
Multi-turn queries lose because the current message is often a bare answer ("iPhone 7 Plus", "10.2.1") whose symptom
lives in the context we do not yet feed to the retriever.

## Gate failure modes found by hand-checking verdicts
| mode | found in | fixed by |
|---|---|---|
| degenerate queries: bare `<url>`, "fix this", "iPhone 7 Plus", "10.2.1" sit at cosine 1.0 with other degenerate messages and pass every similarity test | 6 of 24 gate-v1 verdicts | gate-v2 rule `insufficient_query` (< 3 content tokens) |
| evidence made of clarifying questions ("which iOS version?") counted as support | 3 of 24 | gate-v2: support requires a resolution action class (update/restart/reset/settings/article) |
| template dominance: 12 of 14 gate-v2 'sufficient' verdicts are the iOS-11 keyboard bug, whose 1,087 identical workaround replies form a dense cluster | structural | not a bug, but it means "sufficient" today mostly means "this is the keyboard bug" |
| wrong template on a look-alike message: g135 (camera focus on 11.2) matched keyboard-bug 11.1.1 replies | 1 of 14 | needs intent gating with a real classifier (Phase 3) |

## Hypotheses (ranked by expected gain)
- **H1. Index the reply side, not only the message side.** The reply that resolves a query is often lexically close to the
  query's own resolution but attached to a differently-worded customer message. Adding a second dense list over
  `customer_message + brand_reply` (or reply-only) and fusing by RRF attacks the 22/46 "never found" cases directly.
- **H2. Feed context to the retriever for multi-turn queries.** Concatenate the last customer turn(s) when the current
  message has < N content tokens. Expected to lift the multi-turn slice (0.25) and cut `insufficient_query` verdicts.
- **H3. Gate on classified intent, not on candidate weak intents.** With the Phase-3 classifier, require candidate
  intent == query intent for support; kills the g135 class of error and the ambiguous-intent misses.
- **H4. Template-aware deduplication.** 17.8% of top-5 lists contain duplicate reply text. Collapse identical replies
  before ranking so the top-5 carries five *distinct* resolutions; increases the chance of a same-resolution hit and
  gives the drafter variety.
- **H5. The automatic judge is too strict and unscorable for DM references.** Replace reply-side TF-IDF at 0.5 with a
  human-judged relevance set on ~60 queries in Phase 7; until then, hand-checks are the only gate validation.
- **H6. Short and noisy messages need a clarify strategy, not retrieval.** For < 3 content tokens the correct agent
  action is a clarifying question; the gate already routes these to `insufficient_query`.

## What this means for the agent (Phases 3-5)
Autonomous responses will be rare at first (~7% of golden queries pass the gate) and concentrated on the keyboard bug;
most traffic goes to clarify or handoff. That is the intended behaviour of "no sufficient evidence -> no autonomous
response" on this dataset, and the numbers above are the baseline the later phases must beat with H1-H4.
