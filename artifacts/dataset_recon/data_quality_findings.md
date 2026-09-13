# Data-quality findings and what each one forces us to do

| # | finding | evidence | consequence for ResolveAI |
|---|---|---|---|
| 1 | `tweet_id` is not chronological | Spearman(id, time) = 0.33 | All splits must be by `created_at`. Never split by id/row. |
| 2 | Customer handles are anonymised to numbers, brand handles are real | 100% / 0% numeric | Strip *all* @mentions in cleaning; they carry no signal. Customer id is still stable, so identity leakage across splits is possible (finding 8). |
| 3 | URLs are t.co redirects, images not included | 22.5% of tweets have a URL; "see screenshot" is common | Replace URLs with a token. Accept that a chunk of issues are under-specified; the planner needs a `clarify` strategy. |
| 4 | HTML entities present | 3.5% | `html.unescape` in cleaning. |
| 5 | Empty / one-word customer turns dominate duplicates | "thank you", "done", "sent", "yes" | Golden set must include closures; the agent needs a cheap `other/closure` path and must not escalate a "thanks". |
| 6 | 3.9k orphan parent references | 0.14% | Truncate context at missing node; flag `context_truncated`. |
| 7 | Mega-threads (max 1,390) and branching (7.9%) | outage/announcement tweets | Pair on direct parent only; ignore siblings; use thread-size medians. |
| 8 | 16% of customers appear in multiple threads; 30% of late-period customers were seen earlier | leakage.json | Report a *customer-disjoint* variant of the headline metric alongside the temporal one. |
| 9 | Brand replies are heavily templated | 20% of brand replies are exact duplicates after normalisation; AppleSupport 52% contain "DM" | The reference reply is a weak target; reply quality must be judged, not string-matched. Trivial "DM us" baseline will look strong on tone. |
| 10 | Brand reply rarely quotes the customer | mean token overlap 7%, >50% overlap in 0.5% | Low risk of the retrieval target leaking the query. |
| 11 | Volume is bursty around product events | top-3 days = 6.5% of all inbound; Apple's Nov 2017 is the iOS 11 "I" bug | Temporal holdout is a snapshot; stratify the golden set by intent so a burst intent doesn't dominate. |
| 12 | Non-English is brand-specific | AmazonHelp 5.7%, most others < 0.1% | Language gate is cheap and necessary; response is a canned redirect. |
| 13 | About half of inbound tweets are non-first turns | 48.8% | Context handling is not optional; multi-turn examples must be in the golden set. |
| 14 | Brand replies signed with agent initials (^EC, /BH, ^SM) | airlines, Spotify, Amazon | Strip the signature in cleaning so the drafter doesn't learn to invent initials. |
| 15 | Outcome is partially observable from the customer's next turn | 29-50% of brand replies get a customer follow-up; 12-32% of those are positive, 5-12% negative (resolution_signal.json) | A weak but real "was this resolved" label exists for 6-10% of pairs; enough to bias retrieval toward replies that worked. |
