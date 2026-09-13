# Intelligence-layer failure analysis (Phase 3)

Classifier: BGE-small + LR (silver-v2, calibrated), message-only. Golden: 197, evaluated once. Errors: 76/197 (accuracy
0.614, macro-F1 0.618). Second opinion (GLM-5.2 at LOW/MEDIUM, adopt if in top-3): 27 of those fixed, 3 new errors.
Per-query records: `per_query_golden_intent.jsonl`, `second_opinion_golden_197.jsonl`; categories: `failure_candidates.json`.

## Top confusions (gold -> predicted)
data_loss_sync -> apps_services 6; other -> account_store_repair 4; apps_services -> keyboard_text_bug 4; apps_services ->
battery_power 3; other -> apps_services 3; general_complaint -> keyboard_text_bug 3; apps_services <-> general_complaint 3+3.

## Failure modes
| # | mode | n (of 76) | example | expected | predicted (conf) | context helped? | GLM 2nd opinion | root cause | proposed improvement |
|---|---|---|---|---|---|---|---|---|---|
| 1 | **Silver-label bias: `other` and `general_complaint` under-represented / mislabelled in training** | 20 (11 other, 9 general) | g028 "When will we get the TV app in the UK?" | other | apps_services (0.59) | no | fixed -> other | silver-v2 has 418 `other` rows (2.3%) and labels product questions as the product's class; the model learns "TV app" = apps_services | LLM-label a small `other`/`general_complaint` slice or add rule seeds for questions/requests ("when will", "any plan to", "can I buy"); second opinion already recovers most |
| 2 | **Short / degenerate messages** | 27 short (<40 chars); 7 short replies in threads | g073 "fix this" (thread about battery) | battery_power | general_complaint (0.58) | yes (B2 got it) but B hurt overall | not adopted (top-3 rule) | nothing to embed; the answer lives in the prior turn, but the classifier was trained on single messages, so any concatenation is out of distribution | train a second head on (issue_text, reply) pairs from KB threads, or route short replies with an issue text to the issue text's cached intent; do not concatenate |
| 3 | **Keyboard-bug over-prediction (dominant class in the November data)** | 11 | g037 "Hi. please help <url>" | general_complaint | keyboard_text_bug (0.31) | no | fixed -> general_complaint | 1,503 silver keyboard rows and the I-glyph everywhere in the corpus pull vague/short messages toward the bug | precision is fine at HIGH band (0.958); enforce the insufficient-context flag: a LOW-band keyboard prediction on a message with < 3 content tokens should fall to general_complaint |
| 4 | **Scope and functional-class boundaries (data_loss vs apps_services, apps vs performance)** | 13 data-loss confusions + 1 scope | g120 "iTunes Library and Playlists" (answer to "which device?") | data_loss_sync | apps_services (0.85, HIGH) | no | not consulted (HIGH) | the message names a product (iTunes) whose class is apps_services; the loss is only in the thread. Guide rule R2/R6 needs the thread | this is the one HIGH-confidence class of error (4 of 48); context-aware training data (mode 2) is the fix; until then HIGH-band predictions on short answers in threads should be capped at MEDIUM |
| 5 | **Multi-intent messages** | 4 of 10 wrong; detector fires on 44 | g114 alarms silent + freezing + buttons | apps_services | hardware_damage (0.30) | no | fixed -> apps_services | several symptoms spread probability mass; the primary is the customer's stated concern ("my alarms are my biggest concern"), a discourse cue the embedding ignores | keep the flag advisory; let the LLM second opinion own multi-intent (it went 0.6 -> 0.7 on the slice); tighten the detector (ratio 0.5 -> 0.7) after a dev check |
| 6 | **Taxonomy-gap rows** | 5 of 7 wrong | g056 "Why isn't my iPad Air updating?" | apps_services (gap flag) | keyboard_text_bug (0.19) | no | fixed | update mechanics has no seed vocabulary; the fallback class is learned from noise | the guide already maps update mechanics/GPS/clipboard to functional classes; add those seeds to the keyword list (v1.2) so silver labels carry them |

## Calibration behaviour (what confidence means)
Golden accuracy by band: HIGH 0.958 (48), MEDIUM 0.613 (75), LOW 0.378 (74). 43 of 76 errors are LOW-band, 4 are HIGH-band.
The LOW band is where the second opinion pays: on the 144 consulted rows the classifier was 0.50, the LLM alone 0.886,
and the fixed adopt-if-in-top-3 policy 0.667. The 28 rows where the LLM was right but outside the classifier's top-3 are the
cost of that conservative policy; loosening it is a Phase-5 decision to be made on dev, not here.

## What context did and did not do
- Context did not improve classification (0.609 vs 0.614; exploratory issue-text variant 0.36 vs 0.41 on short replies).
- Context did improve the *flags*: 15 degenerate messages now return `insufficient_query`/`insufficient_context` instead of a
  confident wrong intent, and the retrieval query for short replies is the prior issue text (variant B), which the retrieval
  benchmark showed is at least as good as the raw message and 2x faster (embedding cache hits).
- Context did not improve retrieval Recall@5 (0.348 -> 0.348 -> 0.326 -> 0.326 across A-D); the intent boost raised same-intent
  Recall@5 from 0.62 to 0.68 without surfacing more same-resolution cases. The Phase-2 ceiling (message-to-message similarity
  cannot reach 22 of 46 references) is untouched by anything in this phase; reply-side indexing remains the lever.

## Latency (uncached, warm process, CPU)
context 0.1 ms; classify 55 ms p50 (BGE encode); query 0.1 ms; retrieve 52 ms p50 (encodes the query again); total 113 ms p50,
193 ms p95; short reply with context 66 ms p50. Second opinion adds ~4.1 s and ~690 tokens per consulted message (73% of golden
messages would be consulted). Embedding the query once for both classifier and retriever would halve the local path.
