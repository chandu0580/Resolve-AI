# Phase 0 self-review

Written after re-checking the artifacts against the data. Verdict first, then evidence.

**Verdict: Phase 0 is fit to build on, with four things to fix before Phase 1 and three claims that
need to be softened in the report.** The brand recommendation survives scrutiny. The technology decisions
are defensible. The evaluation design is the strongest part. The weakest part is that some criteria were
sharper in the write-up than in the data.

## What holds up
| claim | re-check | result |
|---|---|---|
| AppleSupport has the largest troubleshooting corpus and a real auto/escalate mix | reran the reply-type regexes with Apple-specific tokens removed | numbers unchanged for every brand; not a vocabulary artefact |
| Retail/airline brands resolve by collecting identifiers | read 4 random pairs per brand + regex data-gather share 16-29% vs Apple's troubleshooting 9.6% | holds |
| Temporal split is mandatory | Spearman(tweet_id, time) = 0.33 | holds |
| Customer-identity leakage is material | 30% of late-window customers seen earlier | holds |
| A "resolved" outcome signal is derivable | 29% of Apple replies get a follow-up, 21% of those positive, 10% negative | holds, but see weakness 3 |
| No framework passes the demonstrated-purpose test | agent loop is a 10-step DAG with one retry; corpus is 30 MB | holds |

## Weaknesses found (fix before or during Phase 1)
1. **Intent-diversity criterion is mostly noise.** `cluster_entropy` ranges 0.951-0.992 across all brands because
   k-means equalises cluster sizes. The 0.20 weight was effectively carried by `embedding_spread` alone.
   Fix: drop entropy, or replace with silhouette-based topic separation. Say so in the report.
2. **Criterion added after the fact.** Auto-resolvability was introduced in stage 3 after the numeric ranking
   didn't match the qualitative read. A sceptical grader will call this "adding criteria until Apple won".
   Defence is real (task 3 of the brief makes auto-resolvability a requirement, and the regex is brand-neutral),
   but the honest framing is: *the stage-1 criteria were incomplete; stage 3 is the criterion that matters most
   for this assignment; AskPlayStation wins it and Apple is second.* Report both.
3. **Resolution-signal regex is crude.** "great", "perfect" count as positive; sarcasm ("great, still broken")
   is scored positive. Only use the signal as a rerank *bonus*, never as a label, and hand-check 50 in Phase 1.
4. **PII assumption was wrong.** The profile says customers are anonymised; true for handles, but 1.3% of tweets
   contain phone-number-like strings and 0.2% of inbound contain order-number-like strings (emails ~0).
   Many phone hits will be prices/timestamps, but the Trust layer still needs an input PII redactor,
   and traces must store redacted text. Not in the architecture doc; add it.
5. **Code hygiene in `01_dataset_profile.py`.** The root-walking loop contains a dead conditional expression
   left from debugging. It works, but it is exactly the kind of line an interviewer points at. Clean it.
6. **Banking77 not addressed.** The brief offers it as an optional intent resource. Decision should be explicit:
   not used, because it is banking vocabulary with 77 fine-grained intents and would not transfer to consumer
   tech. One line in the decision log.
7. **Cost/latency budget missing.** The architecture makes 3-4 LLM calls per message (risk flags, draft,
   verifier, optional second-opinion). For 200 golden examples x 4 systems x judge, that is roughly 3-4k calls
   per full eval. Fine with caching, but the number should be stated and the 15-minute reproduction claim
   depends on the cache being committed.
8. **Cost weights are asserted.** "Missed escalation costs 3x a false escalation" is a reasonable prior, not a
   measurement. Present it as a stated assumption and show the metric at 1x and 5x too.

## Claims to soften in the report
- "Highest intent diversity" -> "diverse by embedding spread; entropy criterion uninformative".
- "Objective ranking" -> "explicit, reproducible ranking with stated weights; the decisive criterion was added
  after a qualitative read, and both stages are reported".
- "Outcome-aware retrieval makes historical resolution literal" -> "biases retrieval toward replies that were
  followed by a positive customer message, a weak but real signal".

## Gaps that are acceptable for now
- No LLM smoke test yet (model id unresolved). First action of Phase 1.
- No golden-set power analysis beyond "under ~5 F1 points is noise at n=200". Adequate for the brief.
- threads.parquet (261 MB) kept locally as the intermediate for scripts 02-06. Regenerable; gitignored.

## Recommended Phase 1 entry order
1. LLM smoke test (model id, JSON mode, latency, cost per call).
2. Ingestion v2: outcome labels, signature stripping, PII redaction, temporal split, subsample.
3. Retrieval test MiniLM vs bge-small; hybrid + outcome rerank.
4. Golden-set sampling and labelling (starts early because it gates everything downstream).
5. Silver labels -> classifier -> baselines.
6. Agent loop + Trust layer + traces.
7. Harness, judge, human-agreement study, report.
