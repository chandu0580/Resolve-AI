# Submission checklist

Nothing has been committed, pushed or submitted: the repository owner commits and submits. Items marked `[ ]` need an action from
the owner; every `[x]` names its evidence.

| | Item | Evidence |
|---|---|---|
| [ ] | **Public/private repository access correct** | **Owner action.** There is no remote and no commit yet (`git status`: everything untracked). Create the repository, push, and set access as the assignment requires. `.env` is gitignored and must stay untracked. |
| [x] | README works | The README commands were run on a copy of only the committable files, with no `.env`, caches or credentials, and pass: install, pytest, demo, final verification, npm ci, lint, typecheck, test, build and API start. The first two runs found an undeclared dependency, a `.gitignore` rule hiding the Traces pages and a test relying on a local-only file; all are fixed. The final all-green re-check reused the interpreter and embedding cache (`artifacts/final/clean_env_check.json`). |
| [x] | Assignment requirements covered | See the table below |
| [x] | Golden set included | `data/golden/golden_final.csv` (197 rows, sha256 `33f4f333…`, frozen manifest, annotation guide, adjudication report) |
| [x] | Evaluation harness included | `resolveai/evaluation/`, `scripts/evaluate.py` (`--cached` / `--live`), `scripts/final/b_final_metrics.py` |
| [x] | Baselines included | B0 trivial and always-handoff, B1 simple ML, B2 direct LLM: `artifacts/evaluation/runs/` |
| [x] | LLM judge included | `resolveai/evaluation/judge.py`, frozen rubric `artifacts/evaluation/judge_rubric.json`, judge results for every system |
| [x] | Judge agreement documented | Second-family agreement documented (qwen3.8-27b, n = 126, groundedness weighted κ 0.822). **Judge-human agreement is NOT COMPLETED** (0 of 50 packet rows rated) and is stated as such in `docs/EVALUATION.md` §9, `FINAL_REPORT.md` §1 and §4, and `README.md`. |
| [x] | Failure analysis included | `artifacts/final/FINAL_REPORT.md` §6 (five failure modes with real golden rows); `artifacts/final/failure_modes.json`; `artifacts/evaluation/failure_analysis.md` (Phase 6) |
| [x] | "What is misleading about my headline number" included | `artifacts/final/FINAL_REPORT.md` §7; `artifacts/evaluation/misleading_headline.md` |
| [x] | Decision log included | `docs/DECISIONS.md`: an index by area plus #1–#120 |
| [x] | API works | `artifacts/final/api_smoke.json`: 23 of 23 live checks in the production profile; pytest: 37 API tests pass (`tests/test_api.py`, `tests/test_phase9_api_security.py`) within 460 tests, 0 failed |
| [x] | Frontend works | 122 of 122 vitest tests, ESLint and `tsc` clean, `next build` succeeds; browser smoke against the auth-enabled API (`artifacts/product/hardening/smoke/smoke_results.json`): 40 routes, 7 of 7 scenarios, 12 of 12 interactions, 0 failures, 0 axe violations, 0 horizontal overflow; with no console token, 5 routes show "Not authorized" (`smoke_unauthorized.json`); with the API stopped, 7 routes show "ResolveAI API unavailable" |
| [x] | Demo works | `python -m resolveai demo --no-llm` passes in the clean copy. The browser smoke ran the demo scenarios through the console (7 of 7 matched their expectations), and the walkthrough is in `docs/DEMO.md`. |
| [x] | No secrets | The security scan found 0 findings across 785 committable files: real `.env` values compared in memory, credential patterns, the model endpoint address. `.env` is gitignored and not committable, both `.env.example` files hold placeholders only, and the live smoke server log held 0 tokens and 0 model keys. |
| [x] | No PII | 0 of 813 trace records contain unredacted PII (security scan). The live API smoke found no raw email or phone in the response, trace or server log, and adversarial case 17 checks prompts, traces and results. Limitation: regex detection misses names and addresses. |
| [x] | Reproducible cached evaluation | `scripts/final/f_final_verification.py` confirms that `scripts/evaluate.py --cached` regenerates all 11 result files identically with no model calls. `scripts/final/b_final_metrics.py` recomputes the final table from the committed run records. |
| [x] | Citations present | Every `AUTO_HANDLE` troubleshooting reply carries `response.evidence_refs` (case id, thread, date, rank, similarity). The output gate requires `evidence_refs_exist`, and the API re-check withholds replies with unknown ids. Example in `docs/API.md`. Report sources are cited by artifact path. |
| [x] | Limitations honest | `FINAL_REPORT.md` §7 and §8, `docs/PRODUCTION_READINESS.md` (10+ NOT READY items), `README.md` "Known limitations"; human evaluation reported as not completed everywhere |

## Assignment requirements → where they are met

| Requirement | Where |
|---|---|
| Classify the intent of an inbound message | `resolveai/intelligence/classifier.py` (+ LLM second opinion); taxonomy `docs/INTENTS.md`; golden intent macro-F1 0.854 |
| Draft a reply grounded in how the brand historically resolved similar issues | `resolveai/retrieval/`, `resolveai/agent/drafter.py`, `verifier.py`; `docs/ARCHITECTURE.md` §2 |
| Decide auto-handle vs escalate, with a stated reason | `resolveai/policy/escalation.py` (reason code + rule on every decision); `HandoffPacket` |
| A frozen golden set and an evaluation harness | `data/golden/`, `resolveai/evaluation/`, `docs/EVALUATION.md` |
| Baselines and an LLM judge | B0/B1/B2; GLM-5.2 rubric-v1 judge with a second-family check |
| Failure analysis and the misleading-headline question | `FINAL_REPORT.md` §6–§7 |
| Decision log | `docs/DECISIONS.md` |
| A working product surface | FastAPI (`docs/API.md`) and Next.js console (`docs/UI.md`); demo `docs/DEMO.md` |
| Report of about 6 pages | `artifacts/final/FINAL_REPORT.md` (about 3,600 words including tables) |

## Before submitting (owner)

1. Optionally, fill `data/human_eval/human_scoring_packet.csv` per `docs/HUMAN_JUDGE_GUIDE.md`, then run
   `python scripts/evaluate.py --cached`. This turns "judge agreement: not completed" into a measured result.
2. Review `git status`. `.env`, `.cache/`, `traces/`, `data/raw/` and `frontend/node_modules` must stay untracked (they are
   gitignored).
3. Commit, push, and set repository access.
4. Run `python scripts/final/f_final_verification.py` on the pushed clone if possible.
