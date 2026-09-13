# Leakage risks (things that would make the headline number lie)

Numbers from `scripts/phase0/03_leakage_analysis.py` -> `leakage.json`.

| risk | mechanism | measured | mitigation |
|---|---|---|---|
| **Temporal leakage** | KB contains replies written *after* the evaluated message; retrieval "knows the future" (e.g. the iOS 11.1.1 fix announcement) | id-based split would do this silently (Spearman 0.33) | Strict temporal split; KB cutoff before holdout start. |
| **Customer identity leakage** | Same anonymised customer in KB and holdout; retrieval returns their own earlier thread | 30.2% of holdout-period customers were seen before the cutoff | Report metrics on the full holdout *and* on the customer-disjoint subset. |
| **Template leakage** | 20% of brand replies are verbatim templates; nearest-neighbour baseline "hits" trivially | brand_reply_exact_dup_share = 0.204 | Judge on usefulness, not string similarity; never use BLEU/ROUGE vs the historical reply as a headline. |
| **Reference leakage into judge** | If the judge sees the brand's real reply it anchors on it, and 52% of those are "DM us" | design risk | Judge sees evidence replies (top-3 retrieved) but never the ground-truth reply for that example. |
| **Golden-set contamination** | Golden examples drawn from rows that are also in the KB | design risk | Golden set is sampled only from holdout; assert `golden ∩ kb = ∅` in a test. |
| **Silver-label leakage** | LLM used to silver-label training data is the same model that classifies at inference (LLM second opinion) | design risk | Keep the primary classifier the embedding+LR model; report LLM classifier separately; hand-check 100 silver labels. |
| **Judge self-preference** | Judge model == drafter model | design risk, documented bias in the literature | Human agreement study (kappa) on 60 replies; pairwise judging in both orders. |
| **Query-answer overlap** | Brand reply repeats the customer's words, so lexical retrieval finds the reply from the query | mean overlap 7%, >50% in 0.47% | Negligible; noted. |
| **Multi-turn hindsight** | Non-first-turn examples' context may already contain the brand's diagnosis | 48.8% of inbound are non-first-turn | Context is allowed (it is the real input) but golden multi-turn examples are labelled on the *current* message; report first-turn and multi-turn metrics separately. |
| **Burst-intent dominance** | The 5-day holdout is dominated by one bug; a classifier that says "keyboard bug" for everything scores well on accuracy | top-3 days = 6.5% of all inbound; brand-level bursts larger | Macro-F1 as the headline; stratified golden sampling; report the label distribution. |
