# Evaluation strategy (designed before the model)

The grader's stated position: proof > system. So the harness is designed first and the agent is built to be measured by it.

## What "good" means, per task
| task | good means | primary metric | secondary |
|---|---|---|---|
| intent | the label a trained support agent would assign | macro-F1 on golden set (accuracy is inflated by the dominant intent) | confusion matrix, per-class F1, calibration (ECE) |
| escalation | never auto-handle something a human had to touch; don't escalate what a public reply solves | recall on *should-escalate* (missed escalations are the expensive error) at a fixed precision, plus cost-weighted accuracy (FN cost 3× FP) | rule-attribution breakdown, agreement with brand's historical DM behaviour (as a *weak* reference) |
| reply | correct, grounded, in brand voice, actionable, safe | LLM-judge rubric score (1–5 on 4 dimensions) validated against human | pairwise win-rate vs each baseline, groundedness gate pass rate |

## Golden set (150–250 examples)
- Source: the **temporal holdout** only, so no example can be in the KB.
- Sampling: stratified. ~60% by weak-label intent (so rare intents are present at ≥ 10 each), ~20% multi-turn (non-first-turn with context), ~10% short/ambiguous (< 40 chars), ~10% targeted edge cases found by keyword search: safety language, legal threats, non-English, thanks/closures, abuse.
- Labels per example: `intent`, `should_escalate` (bool), `escalation_reason_category` (safety / private-info / hardware / repeat / vague / none), and optionally a `reference_note` on what a good reply must contain.
- Protocol: label pass 1 blind; pass 2 one day later on a 50-example subset; report self-agreement (κ). Document every rule that had to be added to the labelling guide mid-way.
- The brand's actual reply is stored but is **not** the reference answer (52% are "DM us"); it is used only for the historical-consistency check.

## Baselines
| | intent | reply | escalation |
|---|---|---|---|
| trivial | majority class | the brand's single most common reply ("We'd like to help. DM us…") | always escalate; also never escalate |
| simple | TF-IDF + logistic regression | nearest-neighbour: copy the historical reply of the most similar past message | keyword rules only |
| full agent | embedding LR (+LLM 2nd opinion) | retrieval-grounded LLM draft with gates | policy engine |
Ablations: no retrieval (LLM alone), no outcome-aware rerank, no output gates, no LLM risk flags.

## LLM-as-judge
- Rubric, scored 1–5 each: **correctness** (would this plausibly solve or advance the issue), **groundedness** (consistent with evidence / brand's known steps, no invented facts), **brand fit** (tone, length, no promises), **actionability** (customer knows what to do next). Plus a hard **safety/policy** pass/fail.
- Judge sees: customer message, context, top-3 evidence replies, the candidate reply. It does *not* see which system produced the reply.
- Bias controls: pairwise comparisons are run in both orders (position bias); length is reported alongside scores (verbosity bias); the judge model is the same GLM model, so **self-preference bias is a stated limitation** and the human study is what makes the number credible.
- Human agreement: the author scores 60 replies (20 per system, shuffled, blind) on the same rubric. Report weighted Cohen's κ per dimension and Spearman on the total, plus pairwise-preference agreement. If κ < 0.4 on a dimension, that dimension is dropped from the headline and the reason is reported.

## Statistics
- 1000-sample bootstrap CIs on every headline metric; differences between systems reported with CIs, not just point estimates.
- Golden set size makes anything under ~5 points of F1 indistinguishable; say so.

## Failure analysis
The trace store is the source: filter runs where (judge ≤ 2) or (intent wrong) or (escalation wrong), cluster by rule / intent, read them, write the top-5 modes with real examples and a hypothesis each.

## "What is misleading about my headline number" — known candidates already
1. The always-"DM us" trivial baseline will score decently on brand-fit and safety because it *is* the brand's modal behaviour; the headline must be reported alongside actionability, where it collapses.
2. The judge and the drafter are the same model family.
3. The holdout is 5 days in Nov–Dec 2017, dominated by the iOS 11 "I → A?" bug; intent distribution is a snapshot, not the brand's year.
4. The golden set is labelled by the person who built the taxonomy.
5. ~30% of holdout customers also appear before the cutoff, so retrieval can see "the same person's earlier complaint".
