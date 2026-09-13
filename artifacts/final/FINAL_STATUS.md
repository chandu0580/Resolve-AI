# Final status

## PROJECT STATUS

Phase 10 of 10 is complete. ResolveAI is a **final reference release**: a production-style reference implementation of an
evidence-grounded support agent. It is **not** a deployed production service; see `docs/PRODUCTION_READINESS.md`. No further
phase exists.

## FINAL VERSION

**ResolveAI 1.0.0**

## BACKEND VERSION

- **Package and API:** `resolveai` 1.0.0, HTTP API `v1`.
- **Pipeline and policy:** `pipeline-v6.1` · `policy-v3.1` · `output-gate-v1`.
- **Retrieval:** `gate-v3` · `rerank-v1` · retrieval `dense:bge-small:pair+rr+gatev3`.
- **Prompts:** `risk-flags-v2` (model-only `needs_private_info` requires the deterministic rule) · `draft-v2` · `verify-v2` ·
  `intent-second-opinion-v1`.
- **Model and classifier:** GLM-5.2 through an OpenAI-compatible endpoint; classifier artifact hash `2d194e7e704f`.

## FRONTEND VERSION

`resolveai-console` 1.0.0: Next.js 16.3.4, React 19.3.0, TypeScript, Tailwind CSS.

## TEST COUNTS

| Suite | Result |
|---|---|
| Backend (pytest) | 459 tests: 459 passed, 1 skipped, 0 failed (2026-09-12; `artifacts/final/backend_junit.xml` holds the release run); includes the 20-case adversarial suite and 37 API tests |
| Adversarial suite (20 scenarios) | 20 of 20 scenarios pass (`artifacts/final/adversarial_suite.md`); pytest runs the same cases (`tests/test_final_adversarial_suite.py`) |
| Frontend (vitest) | 122 of 122 tests in 15 files (vitest; `artifacts/final/frontend_junit.xml` holds the release run); ESLint 0 problems, `tsc --noEmit` clean, `next build` succeeds |
| Lint / typecheck | ruff clean; ESLint 0 problems; `tsc --noEmit` clean |
| API live smoke (production profile) | 23 of 23 checks passed (`artifacts/final/api_smoke.json`) |
| Browser smoke (Edge + axe-core) | 3 modes, 0 failures, 0 axe violations, 0 horizontal overflow: logged in, 40 routes, 7 of 7 scenarios and 12 of 12 interactions; no token, 5 routes "Not authorized"; API stopped, 7 routes "API unavailable" (`artifacts/product/hardening/smoke/`) |
| Clean-clone reproduction | fixed file set passes every step (pytest, demo, verification, npm ci, lint, typecheck, test, build, API) in a targeted clean-copy re-check that reused the interpreter and embedding cache. The earlier full fresh-venv runs found and led to the fixes for an undeclared dependency, a `.gitignore` rule hiding the console's Traces pages and a test relying on a local-only file (`artifacts/final/clean_env_check*.json|md`) |

## SECURITY RESULT

**PASS.** The security scan (`artifacts/final/security_scan.json`) covered 785 committable files with 0 findings; `.env` is not committable, and 0 of 813 trace records contain unredacted PII. The live API smoke passed 23 of 23 checks: 401, 403 and 429, authentication before validation, no input echo, and 0 tokens, keys or raw customer text in the server log. The adversarial suite passed 20 of 20. Not implemented: TLS, SSO, token rotation and dependency scanning (`docs/PRODUCTION_READINESS.md`).

## EVALUATION RESULT

Golden set, release 1.0.0, run once. 95% bootstrap intervals; differences are paired against the direct-LLM baseline B2
(`artifacts/final/final_metrics.md`).

| Metric | ResolveAI 1.0.0 | B2 direct LLM |
|---|---|---|
| Intent macro-F1 | 0.854 [0.799, 0.901] | 0.887 (difference not distinguishable) |
| Escalation recall | 0.973 [0.912, 1.000] | 0.919 |
| Escalation precision | 0.324 [0.232, 0.411] | 0.739 (B2 better, interval excludes 0) |
| Escalation F1 | 0.486 [0.370, 0.579] | 0.819 (B2 better, interval excludes 0) |
| Safe / unsafe automatic replies | 12 / 0 | 0 / 3 |
| Judge hallucination rate (unvalidated) | 0.367 | 0.526 |

- **Release vs Phase 9 final:** unnecessary handoffs 87 → 75 (−12 [−19, −6]), recall unchanged, judge hallucination 0.283 → 0.367
  (attributed to template wording).
- **Cached evaluation reproduction:** all 11 regenerated result files are identical to the frozen artifacts (`artifacts/final/verification.json`).
- **Live latency:** live p50 4.2 s / p95 14.2 s (n = 40 dev messages); drafted-and-verified live requests p50 10.7 s / p95 26.1 s (n = 8); est. $0.003 per live request at list price (`artifacts/final/performance/perf_final.md`).

## HUMAN EVALUATION STATUS

**NOT COMPLETED.** `data/human_eval/human_scoring_packet.csv` has 0 of 50 rows rated. No AI annotation is presented as human
evaluation. Every judge figure is an unvalidated LLM judgement.

## GOLDEN HASH

`33f4f333ccf10de7f628e57b5567a7930852cdf5b6d4bba872555b96b2bec3a9`: verified on load before and after the release run, and again by the final verification (`artifacts/final/verification.json`); 412 of 416 frozen files unchanged since the start of the hardening pass (the other 4 are evaluation reports `scripts/evaluate.py --cached` rewrites, each named with its reason)

## BUILD STATUS

- **Frontend:** `npm run build` succeeds, with lint, typecheck and tests clean.
- **Backend:** ruff clean.
- **API contract:** the OpenAPI document and console types were regenerated for 1.0.0.

## KNOWN LIMITATIONS

- **Evaluation:** human evaluation not completed; the judge is unvalidated and shares the drafter's model family.
- **Over-escalation:** escalation precision 0.324, 75 unnecessary handoffs on golden; the model's `physical_damage` flag and
  non-support messages are the largest sources.
- **Template wording:** customer-facing templates assert facts the message does not contain ("damage", "steps you've already
  tried", a menu path). Found on golden and not reworded against it.
- **Sample size and labels:** 197 golden rows, 37 positives, 12 automatic replies; AI-derived golden and dev labels; one November
  2017 Apple burst; 7 of 197 messages reach STRONG evidence.
- **Detectors:** regex PII detection; pattern-based injection detection.
- **Deployment gaps:** single process with process-local rate limits; no TLS, operator login, metrics, retention or runbooks; cold
  first request.

## SUBMISSION STATUS

**Not submitted.** Nothing has been committed or pushed.

Owner actions (`artifacts/final/SUBMISSION_CHECKLIST.md`):
1. Create or push the repository and set access.
2. Optionally score the human packet.
3. Commit.
