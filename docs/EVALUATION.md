# Evaluation

How ResolveAI is evaluated, what each number rests on, and what it does not show. Final numbers are in
`artifacts/final/final_metrics.md`; the interpretation, including "what is misleading about the headline number", is in
`artifacts/final/FINAL_REPORT.md`.

## 1. Evidence categories (never mixed)

| Category | What it is | Size | Labelled by | Used for | Never used for |
|---|---|---|---|---|---|
| **GOLDEN** | `data/golden/golden_final.csv`, frozen and hash-verified on every load | 197 messages (37 should-escalate) | two annotation passes (A: Claude; **B: an isolated AI annotator, not a human**), adjudicated by deterministic rules (guide v1.1) | every headline metric; each system run once | tuning, prompt or threshold selection |
| **DEV** | holdout messages that are not golden (asserted) | 240–1,800 rows depending on the experiment | — | every design decision (retrieval, gate, classifier, risk, drafting) | headline claims |
| **AI-LABELLED** | dev labels written by an AI annotator: gate-v3 calibration (24), verifier audit (12), silver noise check (60), Phase 9/10 risk rows (76) | small | Claude, blind to the variants | choosing between candidates under pre-registered rules | human ground truth |
| **HUMAN-LABELLED** | `data/human_eval/human_scoring_packet.csv` | 50 blinded responses | a human (**completed: 50 of 50 rated**) | judge-human agreement (see `artifacts/evaluation/judge_agreement.md`) | — |
| **LLM-JUDGE** | GLM-5.2 on frozen rubric-v1; qwen3.8-27b as a second family on a 126-response subset | per run | a model | reply-quality estimates (groundedness, hallucination, policy) | any agent decision; any claim of human-level quality |
| **DIRECT-LLM BASELINE** | B2: one GLM-5.2 prompt with the taxonomy, escalation criteria and the full thread | golden | — | the main comparison | — |
| **RESOLVEAI** | release 1.0.0 run (`final_release`), plus the earlier single runs `resolveai_full` (Phase 5 system) and `phase9_final` | golden | — | final results; paired comparisons | — |

## 2. The invariant, as measured

**NO SUFFICIENT EVIDENCE → NO AUTONOMOUS CUSTOMER REPLY.**

On the golden set, the release made 12 automatic replies:
- 5 were verified troubleshooting replies with evidence references, all on STRONG evidence;
- 7 were fixed templates for non-English messages;
- 0 went to a row the annotators marked for escalation.

"Safe" means an automatic reply on a row not marked for escalation that is either a verified, referenced troubleshooting reply or
the correct template. It does **not** mean the customer's problem was solved; no outcome data exists. The invariant itself is
proven by tests at every layer (`tests/test_phase9_adversarial.py`, `tests/test_final_adversarial_suite.py`), not by the golden
count.

## 3. The golden set

- **Source:** the temporal holdout only (2017-11-28 to 2017-12-03). No golden row is in the retrieval index, and every KB row is
  earlier (`tests/test_leakage.py`).
- **Sampling:** stratified by weak-label intent (at least 8 per intent, the keyboard-bug burst capped at 20). It includes 40
  multi-turn, 20 short and 20 edge-case rows; strata were hidden from annotators.
- **Labels:** `intent` (11 classes, `docs/INTENTS.md`), `should_escalate` and `escalation_reason`. Metadata: `taxonomy_gap` (7
  rows) and `insufficient_context`.
- **Agreement of the two passes before adjudication:** intent 92.9% (Cohen's κ 0.920), should_escalate 96.4% (κ 0.885). **This is
  consistency under the annotation guide between two AI passes, not human-human agreement.** The 21 disagreements were resolved by
  seven deterministic rules (R1–R7, `data/golden/ADJUDICATION_REPORT.md`).
- **Freeze:** `data/golden/golden_freeze_manifest.json`, sha256 `33f4f333…`.

## 4. Protocol: one run per system

| Run | System | When | Live model calls | Source |
|---|---|---|---|---|
| `B0_trivial`, `B0_trivial_always_handoff`, `B1_simple_ml`, `B2_direct_llm` | baselines | Phase 6 | B2 live | `artifacts/evaluation/runs/` |
| `resolveai_full` + ablations | Phase 5 system (policy-v3) | Phase 6 | cached | `artifacts/evaluation/runs/` |
| `phase9_final` | Phase 9 system (pipeline-v6.0) | Phase 9, after the dev decision was frozen | 0 | `artifacts/phase9/evaluation/runs/` |
| `final_release` | **release 1.0.0** (pipeline-v6.1: model-only `needs_private_info` needs the rule) | Phase 10, after the pre-registered dev decision | 0 | `artifacts/final/evaluation/runs/` |

- **Run once.** Every golden run happened once. The Phase 9 and Phase 10 scripts refuse to run again or overwrite.
- **Hash checks.** The golden hash is verified before and after each run.
- **Response cache.** Model calls go through the SHA-256 response cache, so unchanged prompts replay recorded responses, and the
  live-call count is recorded.
- **No tuning on golden.** No threshold, prompt or rule was chosen on the golden set. Where a golden result revealed a problem
  (the Phase 7 clarification wording, the Phase 10 hardware handoff line), it is reported and left for dev evaluation.
- **Evaluated versus running pipeline.** The final product pass changed live behaviour after `final_release`. The running product
  is `pipeline-v6.3` / `policy-v3.3`:
  - greetings get a template without retrieval;
  - explicit requests for a person are handed off;
  - thanks and bare acknowledgements are separated;
  - short replies are classified with the issue they answer;
  - capitalization and repeated "!" are no longer frustration signals;
  - the English-only redirect obeys the same confidence floor as every other automatic path, so a LOW-confidence "non-English"
    guess asks the customer to restate instead (measured on 4,000 corpus messages: that band was mostly English);
  - a message whose letters are mostly outside the Latin script is recognised deterministically and gets the language redirect
    instead of an English clarifying question;
  - a bare acknowledgement ("ok", "yes") gets its own closing line instead of "You're welcome!";
  - the `hardware` and `repeat_contact` handoff lines no longer assert damage or steps the customer never described, so the
    release hallucination rate of 0.367 was measured on wording the product no longer sends (DECISIONS #118).

  The changes were driven by product requirements and tested on synthetic messages, not chosen on golden, and the golden run was
  **not** repeated. `scripts/evaluation/behaviour_change_impact.py` reports, without a model or the annotations, which golden rows
  reach a changed input path: 21 of 197 (6 lose a capitals- or "!"-only frustration flag, 12 are short replies now classified with
  their issue, 3 are LOW-confidence "non-English" guesses that no longer get the redirect, 1 is a non-Latin script that now does;
  0 greetings, requests for a person, closures or injection changes). The numbers in §6 therefore describe `pipeline-v6.1`.
  Those 21 rows may decide differently today.

## 5. Metric definitions

| Metric | Definition |
|---|---|
| Intent accuracy, macro-F1 | predicted vs adjudicated intent over 11 classes; macro-F1 weights every class equally |
| Escalation precision / recall / F1 | `HUMAN_HANDOFF` vs `should_escalate`; a clarification counts as not escalated |
| Unnecessary handoffs | handoffs on rows not marked for escalation |
| Autonomous rate | share of `AUTO_HANDLE` |
| Safe autonomous rate | see §2 (deterministic, defined by the project) |
| Unsafe autonomous replies | `AUTO_HANDLE` on a row marked for escalation |
| Judge groundedness (1–5), hallucination and policy-violation rates | rubric-v1, parsed judge rows only; failures reported |
| Retrieval same-resolution recall@5 | label-free: a retrieved reply with TF-IDF ≥ 0.5 to the row's own historical reply; scorable on 46 golden rows |
| Uncertainty | 1,000 bootstrap resamples of the golden rows (seed 42); paired resampling for differences; overlapping intervals are called not distinguishable |
| Cost | tokens × GLM-5.2 list price; cache-served runs count the tokens the calls used when live |

## 6. Final results (golden, release 1.0.0 vs the direct-LLM baseline)

From `artifacts/final/final_metrics.md`. Difference = ResolveAI − B2, 95% paired bootstrap; `*` = the interval excludes zero.

| Metric | ResolveAI 1.0.0 [95% CI] | B2 direct LLM | Difference | Source |
|---|---|---|---|---|
| Intent macro-F1 | 0.854 [0.799, 0.901] | 0.887 | −0.033 [−0.082, +0.014] | golden labels |
| Escalation precision | 0.324 [0.232, 0.411] | 0.739 | −0.415 [−0.533, −0.317] * | golden labels |
| Escalation recall | 0.973 [0.912, 1.000] | 0.919 | +0.054 [−0.045, +0.158] | golden labels |
| Escalation F1 | 0.486 [0.370, 0.579] | 0.819 | −0.333 [−0.443, −0.241] * | golden labels |
| Unnecessary handoffs | 75 | 12 | +63 [+50, +76] * | golden labels |
| Autonomous rate | 0.061 [0.030, 0.096] | 0.766 | −0.706 * | golden run |
| Safe autonomous rate | 0.061 [0.030, 0.096] | 0.000 | +0.061 [+0.030, +0.096] * | golden labels + definition |
| Unsafe autonomous replies | 0 | 3 | −3 [−7, 0] | golden labels |
| Groundedness (1–5) | 3.95 [3.76, 4.13] | 3.23 | +0.75 [+0.49, +1.00] * | LLM judge (not human-validated) |
| Hallucination rate | 0.367 [0.298, 0.436] | 0.526 | −0.172 [−0.247, −0.081] * | LLM judge (not human-validated) |
| LLM calls / cost per message | 1.54 / $0.0026 | 1.07 / $0.0024 | +0.47 * / +$0.0002 | run records, list price |

**Release vs Phase 9 final (same golden rows):**
- Escalation precision rose 0.293 → 0.324 (+0.032 [+0.015, +0.052]), unnecessary handoffs fell 87 → 75 (−12 [−19, −6]), and
  recall was unchanged (0.973).
- Safe autonomous replies rose 9 → 12: three non-English messages now reach the language redirect.
- The judge moved the other way: groundedness −0.25 [−0.38, −0.14], hallucination +0.085 [+0.048, +0.128] (§8).

## 7. Dev risk experiment (AI-labelled, exploratory)

`artifacts/final/risk_experiment/` carries the pre-registration, runs, report and decision.
- **Data:** the same 240 dev rows as Phase 9 and the 76 AI-labelled disagreement rows.
- **Candidate:** a model-raised `needs_private_info` counts only when the deterministic private-info rule fires.
- **Result against V0:** unnecessary handoffs 41 → 32; missed escalations unchanged at 1; 9 handoffs removed, all 9 correctly
  (Wilson 95% [0.70, 1.00]).
- **Checks:** 0 live model calls; V0 reproduced Phase 9 exactly.
- **Decision:** accepted under the Phase 9 rule, applied unchanged.
- **Caveat:** these are AI labels on a dev subset. Precision and recall on that subset (V0 0.379 / 0.962, candidate 0.439 / 0.962)
  are not population estimates.

## 8. The LLM judge

- **Contract:**
  - GLM-5.2 at temperature 0 with rubric-v1 (`artifacts/evaluation/judge_rubric.json`).
  - The judge sees the conversation, the evidence the system had and the candidate response, never the system name. Pairwise A/B
    order is seeded.
  - Parsing is strict, and failures are reported rather than dropped.
- **Known weaknesses:**
  - It shares the model family of the drafter and B2. On 126 responses also scored by qwen3.8-27b, it rated GLM-written B2
    replies higher by +0.67 to +0.84 on relevance, actionability and completeness, while agreeing on non-LLM responses.
  - It reads template wording as factual claims.
  - Its parse failures are not uniform across systems.
- **Release attribution** (`artifacts/final/evaluation/judge_attribution.md`):
  - On the 170 responses whose text did not change, the judge is identical (53 → 53 hallucination flags, 0 flips).
  - All of the change is on the 27 changed responses (0 → 16 flags). 10 are the hardware handoff line ("We're sorry to hear about
    the damage… repair options"), sent where the model's `physical_damage` flag fired on a battery or reboot complaint. The rest are
    the clarification menu path "Settings > General > About", not present in the evidence, and the repeat-contact line "Thanks for
    the steps you've already tried".
  - These are real template-wording defects. They were found on golden, so they were not reworded against golden (FINAL_REPORT §9).
- **Human validation: NOT COMPLETED.** Every groundedness and hallucination figure is an unvalidated model judgement.

## 9. Human study status

`data/human_eval/human_scoring_packet.csv` holds 50 blinded, stratified responses; 0 are rated. A human fills the `human_*`
columns per `docs/HUMAN_JUDGE_GUIDE.md`, without opening `_packet_key.json`, then runs `python scripts/evaluate.py --cached`;
`judge_agreement.md` then reports per-dimension weighted κ and Spearman. Until then, **HUMAN EVALUATION = NOT COMPLETED**, and no
AI annotation is described as human evaluation anywhere in the repository.

## 10. Retrieval

- **Same-resolution recall@5:** 0.261 with the release pair index and resolution rerank, vs 0.348 for the Phase 2 customer index
  (46 scorable rows; not distinguishable). The reranker trades this for resolution-bearing@1: 0.18 → 0.76.
- **Evidence levels on golden:** INSUFFICIENT 166, WEAK 24, STRONG 7, SUFFICIENT 0. Nearly every STRONG verdict is the iOS 11
  autocorrect bug.
- **Gate-v3 precision:** 0.93 on 14 AI-labelled dev verdicts.

Source: `artifacts/evaluation/retrieval_report.json`.

## 11. Latency and cost

- **Golden runs are cache-served,** so their latency is not live latency.
- **Live profile:** `artifacts/final/performance/perf_final.md` (dev messages, no cache, 45 s budget) holds the no-model, cached
  and live figures, the tokens and cost per request, and whether drafting and verification ran live.

## 12. Where AI annotation was used (complete inventory)

AI annotation was used in these places. None is human ground truth.
- Annotator B for the golden set.
- Outcome-regex precision check (Phase 2).
- Gate-v2 dev hand-checks (Phase 2).
- Silver-label noise check (Phase 3).
- Second-opinion smoke labels (Phase 3).
- Autonomous-reply hand-checks (Phases 4 and 5).
- Gate-v3 calibration labels (Phase 5, 24 dev cases).
- Verifier block audit (Phase 5, 12 drafts).
- Risk disagreement labels (Phases 9 and 10, 76 dev rows).

## 13. History of measured systems

| Phase | Where | What it measured |
|---|---|---|
| 2 | `artifacts/retrieval/results.md` | retrieval configurations; gate-v2 |
| 3 | `artifacts/intelligence/classifier_results.md` | classifier (golden macro-F1 0.618 alone, 0.736 accuracy with the second opinion) |
| 4 | `artifacts/agent/agent_benchmark.md` | first end-to-end agent (AUTO 5.1%, 2.44 model calls per message) |
| 5 | `artifacts/resolution/benchmark.md` | resolution intelligence, gate-v3, drafting A/B |
| 6 | `artifacts/evaluation/` | harness, baselines, judge, ablations (the Phase 5 system) |
| 9 | `artifacts/phase9/evaluation/final_metrics.md` | Phase 9 final run |
| 10 | `artifacts/final/final_metrics.md` | release 1.0.0 |

Numbers in earlier reports describe earlier systems and are not current.
