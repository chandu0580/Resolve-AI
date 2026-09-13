# Phase 10 risk experiment: pre-registration

This file was written on 2026-09-11, before `scripts/final/a_private_info_experiment.py` first ran. No result for this candidate
existed at the time. The report records this file's SHA-256, so any later edit can be detected.

## Question

The largest measured source of unnecessary handoffs is the risk model raising `needs_private_info` with no deterministic
private-info signal: 17 of 41 unnecessary handoffs on the Phase 9 dev rows. Can that source be removed without losing real
escalations?

## Data

- **Rows:** the 240 Phase 9 DEV rows (holdout messages, golden excluded and asserted, seed 51), through the unchanged production
  understanding pipeline and the same SHA-256 response cache.
- **Labels:** `data/dev/phase9_risk_labels.json`, 76 rows, written by an **AI annotator, not a human**. No human-labelled dev set
  exists in this repository. The result is therefore exploratory evidence, not a human-validated decision.
- **Golden set:** not read.

## Candidate (exactly one)

**P10:** production (V0), except that a model-raised `needs_private_info` counts only when the deterministic private-info rule
fired on the same message (`AgentConfig.risk_corroborate = ("needs_private_info",)`). The prompt, the model call, every other
flag and the policy are unchanged.

Not tested, and why:
- **Phase 9's V3 prompt plus this corroboration.** Its flags are a subset of V3's, so it keeps V3's two new missed escalations and
  fails rule 2 by construction.
- **Threshold, prompt or policy-order changes.** They would be tuning, not the targeted test named at the end of Phase 9.

## Measurements

Unless stated otherwise, measurements are on the 76 labelled rows.
- **Counts:** TP, FP (unnecessary handoffs) and FN (missed escalations).
- **Rates:** precision, recall and F1 on the labelled subset. These are not estimates for the dev population, because rows where
  every variant agrees are unlabelled.
- **Changes:** new missed escalations with their gold reasons; handoffs removed and the share correctly removed (Wilson 95%);
  where removed handoffs go (clarification or automatic-reply candidate).
- **Over all 240 rows:** automatic-reply candidates and the model fallback rate.
- **Not measurable on dev:** safe autonomous resolutions, because dev has no drafting or verification labels. The count of
  automatic-reply candidates is reported instead.

## Validity checks (before any decision)

1. The recomputed V0 must reproduce the stored Phase 9 V0 outcome on each row. Mismatches are reported.
2. Every row where P10 and V0 differ on handoff must already carry a label. If one does not, no decision is made and no new label
   is created.

## Acceptance rule (Phase 9's rule, unchanged)

P10 is ACCEPTED only if all of these hold:
1. no new missed escalation whose gold reason is `safety`, `legal_media` or `private_info`;
2. at most one new missed escalation in total;
3. at least 3 fewer unnecessary handoffs than V0;
4. a model fallback rate no more than 5 percentage points above production. This holds by construction, because both variants
   use the same call.

## Consequences fixed in advance

- **Rejected:** the production configuration stays unchanged (`risk_corroborate = ()`), and nothing runs on the golden set.
- **Accepted:**
  - the candidate is frozen in `artifacts/final/risk_experiment/decision.json` and enabled in the release configuration;
  - the golden set is then run once for that configuration as a new run, never overwriting `phase9_final`;
  - that run is reported next to Phase 9 final, with the dev labels' AI provenance stated.
