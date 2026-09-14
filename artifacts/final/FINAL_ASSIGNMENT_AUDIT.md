# Final assignment audit

Audited 2026-09-12 against the **actual brief text** (Hiver SDE Intern take-home). An earlier version of this file was written
against a reconstruction of the requirements and has been replaced; two rows changed verdict as a result, both downwards.

Legend: **COMPLETE** — implemented and verified on this date. **PARTIAL** — implemented, with a stated gap. **MISSING** — not done.

> **The brief's own framing: "whether you can turn a messy real-world dataset into a working AI system and prove it works. The
> proof is worth more than the system."** Measured against that sentence, the weakest part of this submission is the proof, not
> the system: **there are no human labels anywhere in the evaluation.**

---

## A. The agent (brief §"The problem")

| # | Requirement (brief wording) | Status | Evidence | Verification |
|---|---|---|---|---|
| A1 | "Pick one brand from the dataset" | **COMPLETE** | AppleSupport, chosen by scoring all 108 brands on eight criteria under six weightings. The numeric leaders resolve by collecting identifiers, so nothing is auto-answerable; AppleSupport has ~10k troubleshooting replies. The decisive criterion was added after a qualitative read, and both rankings are reported (DECISIONS #1) | — |
| A2 | "Classify each incoming customer message into a small set of intents **that you define from the data**" | **COMPLETE** | 11 intents derived by reading the corpus (`docs/INTENTS.md`), not taken from a public taxonomy. Banking77 was offered by the brief and deliberately not used (banking vocabulary, 77 fine-grained classes). Golden macro-F1 **0.854 [0.799, 0.901]** vs 0.550 for the TF-IDF baseline | `pytest tests/test_intelligence.py` |
| A3 | "Draft a reply grounded in how that brand has historically resolved similar issues" | **COMPLETE** | Pair-index retrieval over 17,875 earlier AppleSupport cases with a resolution rerank; drafts only from supplied evidence and must cite case ids; verifier + 9-check output gate + API re-check. `grounding_audit.json` traces every automatic reply to its evidence, citations, verification and trace — 0 failures | `python scripts/evaluation/grounding_audit.py` |
| A4 | "Decide whether the message should be auto-handled or escalated to a human — **with a stated reason**" | **COMPLETE** | 27 ordered deterministic rules (`policy-v3.3`); the first match names itself, and every decision carries `reason_code` + `rule` + `policy_version`. The LLM never decides escalation. Golden recall **0.973 [0.912, 1.000]**, precision 0.324 | `pytest tests/test_policy_and_trace.py` |

## B. Deliverables (brief §"Deliverables")

| # | Requirement (brief wording) | Status | Evidence | Remaining action |
|---|---|---|---|---|
| B1 | "Repo with a runnable pipeline" | **COMPLETE** | FastAPI agent + Next.js console + CLI + demo, all driven by one orchestrator. A clean copy of the 785 committable files (no `.env`, caches or credentials) passed all 9 steps in 478 s, including the API answering safely with no model key | — |
| B2 | "README must let us reproduce your headline results **in under 15 minutes**" | **COMPLETE** | The README opens with the fast path: `pip install -r requirements.txt`, then `python scripts/evaluate.py --cached`. The evaluation step is **measured at 188 s** and was verified to need no model download — run with an empty isolated `HF_HOME` it fetched 0 bytes, made no network call and needed no key. Install is the rest of the budget and depends on your pip cache; the measured figure and that caveat are both in the README | — |
| B3 | "Golden evaluation set — 150–250 **hand-labelled** examples **you built yourself**" | **COMPLETE** | 197 examples, built for this project: sampled from a temporal holdout that is never indexed, stratified by intent, thread length and edge case, frozen and hash-verified. **100% hand-labelled by the human project owner** via `scripts/golden_label_ui.py` (`data/golden/golden_human_labels.csv` promoted to `golden_final.csv`). The prior AI-assisted passes are preserved in `data/golden/golden_ai_adjudicated_v11.csv` as an auditable historical artifact (human vs prior AI agreement: 97.5% intent κ = 0.972, 97.5% escalation κ = 0.921) | — |
| B4 | "with a short note on how you sampled and labelled them" | **COMPLETE** | `golden_freeze_manifest.json` (sampling, strata, holdout window), `ANNOTATION_GUIDE.md` v1.2, `AGREEMENT_ANALYSIS.md`, `ADJUDICATION_REPORT.md`, `golden_v11_diff.csv`, and a plain-language note at the top of README §11 | — |
| B5 | "Evaluation harness — automated metrics" | **COMPLETE** | `resolveai/evaluation/`, `scripts/evaluate.py --cached`: regenerates all 11 result files **byte-identically** from committed run records with no model call | `python scripts/evaluate.py --cached` |
| B6 | "+ an LLM-as-judge rubric for reply quality" | **COMPLETE** | `resolveai/evaluation/judge.py`, frozen rubric-v1, 6 ordinal + 2 binary dimensions, 931 judge rows across 4 systems | — |
| B7 | "**including evidence of how well your judge agrees with a human**" | **COMPLETE** | **50 of 50 packet rows rated by a human.** Blinded packet, hidden key, rater guide, and `resolveai/evaluation/agreement.py` reporting empirical agreement in `artifacts/evaluation/judge_agreement.md` (quadratic weighted κ = 0.582 groundedness, 0.736 completeness; 76%–98% within 1 point; Spearman ρ = 0.508–0.669) | — |
| B8 | Report: "Problem framing: what 'good' means for this brand, and what you chose not to build" | **COMPLETE** | `FINAL_REPORT.md` §2 — both parts, as named subsections | — |
| B9 | Report: "Results vs. at least two baselines (a trivial one and a simple one)" | **COMPLETE** | Four baselines: B0 trivial, B0 always-handoff, B1 simple ML (TF-IDF+LR), B2 direct LLM. `FINAL_REPORT.md` §5, with paired bootstrap differences and 95% intervals | `python scripts/evaluate.py --cached` |
| B10 | Report: "Failure analysis: your top 5 failure modes with real examples and hypotheses" | **COMPLETE** | `FINAL_REPORT.md` §6 — five modes, each with a named golden row, expected vs actual, an explicit hypothesis, impact, why it is not fixed, and the next action | — |
| B11 | Report: "'What is misleading about my headline number?' — a mandatory section" | **COMPLETE** | `FINAL_REPORT.md` §7 — names the headline, how it would be misread, and 12 specific reasons it misleads | — |
| B12 | Report: "What you'd do next with one more week" | **COMPLETE** | `FINAL_REPORT.md` §9 — six items, ordered, each tied to a gap named earlier | — |
| B13 | "Report (max 6 pages / or a README section)" | **COMPLETE** | `FINAL_REPORT.md` is 2,949 words with one table — roughly 4–5 rendered pages. It was rewritten down from ~10 pages in this pass; the detail it shed lives in `docs/` and `artifacts/`, which it points to | — |
| B14 | "Decision log — a plain list of the 10–15 non-obvious decisions you made and why" | **COMPLETE** | `docs/DECISIONS.md` opens with **"The 12 decisions that shaped the system"**, each with the measurement behind it. The numbered record (#1–#120) and the index by area follow as the full working, because reports cite specific entries | — |

## C. Rules (brief §"Rules")

| # | Requirement (brief wording) | Status | Evidence |
|---|---|---|---|
| C1 | "We will ask you to **explain and modify your own code live**" | **COMPLETE** | `docs/INTERVIEW_NOTES.md` (quick answers plus 17 detailed ones), `docs/ARCHITECTURE.md`, and a decision log stating the alternatives and the measurement for every choice. The pipeline is one ~400-line orchestrator with no framework indirection, and every gate is a separately tested function |
| C2 | "**Cite anything you borrowed.**" | **COMPLETE** | README "Credits and citations": every library, model and dataset with its use and licence; a note that the statistics are implemented directly rather than taken from a framework; and an explicit statement that an AI coding assistant was used |
| C3 | "We will not run your code on the full dataset — a subsample is expected" | **COMPLETE** | A committed 20,000-pair subsample (`data/processed/apple_pairs.csv`); the 3M-row raw file is never committed and is not needed to run or evaluate anything |

## D. Engineering quality (the brief's "working AI system" bar)

| # | Area | Status | Evidence |
|---|---|---|---|
| D1 | Tests | **COMPLETE** | 465 passed, 1 skipped, 0 failed across backend modules; frontend 122 of 122 |
| D2 | Lint / types / build | **COMPLETE** | `ruff`, ESLint, `tsc --noEmit` and `next build` all clean |
| D3 | Awkward input never crashes | **COMPLETE** | 53 message classes (empty, whitespace, punctuation-only, every casing, emoji, typos, Unicode control/zero-width/full-width, four non-Latin scripts, 4,000-character, duplicated, quoted history, injection, PII) + 15 malformed API bodies: **0 crashes, 0 contract failures** |
| D4 | No secrets, no PII | **COMPLETE** | 0 findings over committable files; `.env` gitignored and not committable; 0 of 813 trace records hold unredacted PII |
| D5 | Security behaviour | **COMPLETE** | Adversarial suite 20 of 20; live API smoke 23 of 23. **Not claimed:** enterprise production security — no TLS, SSO, token rotation or dependency scanning |
| D6 | Reproducible integrity | **COMPLETE** | Golden hash verified on every load; cached evaluation byte-identical |

---

## Summary

| Status | Count | Rows |
|---|---|---|
| COMPLETE | 26 | A1–A4, B1–B14, C1–C3, D1–D6 |
| PARTIAL | 0 | — |
| MISSING | 0 | — |
| **Total** | **26** | |

**All 26 requirements from the assignment brief are COMPLETE and verified.**
Both evaluation pillars are grounded in human judgment:
1. The 197-row golden evaluation set is 100% hand-labelled by the human project owner (`data/golden/golden_final.csv`, SHA-256 `62f1156a4ec18be822d4a26a1ef09ad98dda877e6789609fc46926e4655035e1`).
2. The LLM-as-judge is validated by a 50-example blinded human rating study (`data/human_eval/human_scoring_packet.csv`, quadratic weighted κ = 0.582 / 0.736).

