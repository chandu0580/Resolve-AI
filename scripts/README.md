# Scripts

Every script runs from the repository root with the project's Python environment. None calls a model unless it says so, and none
writes into a frozen location (`data/`, `artifacts/` outside `artifacts/final/` and `artifacts/product/`, frozen models and configs).

## Product entry points

| Folder / script | Purpose |
|---|---|
| `verification/final_verification.py` | Final integrity check: golden hash, every frozen file byte-identical to the hardening baseline (including `artifacts/final/`), Phase 7 hash snapshot, cached evaluation (11 result files regenerated and compared), security scan. `--snapshot` takes the baseline; `--skip-cached-eval` for a quick pass. |
| `verification/release_checks.py` | Re-runs the release checks with output redirected to `artifacts/product/hardening/`: `adversarial` (20-case suite), `api-smoke` (production profile over live HTTP), `clean-env` (fresh virtual environment). |
| `verification/input_robustness.py` | Every awkward input class (empty, whitespace, punctuation, casing, emoji, typos, Unicode, non-Latin scripts, very long, duplicate, quoted history, injection, PII) through the real agent, plus malformed bodies through `POST /api/v1/resolve`. No model. Writes `artifacts/final/input_robustness.{json,md}`; the same cases run in `tests/test_input_robustness.py`. |
| `verification/capture_console_fixtures.py` | Captures the console's test fixtures for the read-only endpoints from the real in-process API. |
| `verification/verify_product_pass.py` | The product-completion pass's integrity check against its own baseline (kept so that pass's report stays reproducible). |
| `evaluation/release_by_intent.py` | Per-intent outcomes of the single release golden run and the knowledge-gap rule, for the Knowledge Center. |
| `evaluation/grounding_audit.py` | Every automatic reply ↔ evidence ↔ citations ↔ verification ↔ trace, for the release run and captured API responses. |
| `evaluation/behaviour_change_impact.py` | Which golden rows reach a code path changed after the release evaluation (input-level, no model, no labels, no re-run). |
| `evaluate.py` | The evaluation harness (`--cached` replays committed run records without a model). |
| `security_scan.py` | Scans every committable file for secrets, credential patterns, the model endpoint and unredacted PII in traces. It stays at this path because release artifacts and `final/f_final_verification.py` cite it. |

The demo needs no script: `python -m resolveai demo`. The browser smoke is `frontend/scripts/smoke.mjs` (`npm run smoke`).

## Release and development history

These folders are reproducibility evidence, not product code. Frozen artifacts and reports cite their exact paths, so they are
not moved or renamed.

| Folder | What it reproduces |
|---|---|
| `final/` | Release 1.0.0: pre-registered risk experiment, final metrics, performance profile, adversarial suite, API smoke, release verification, golden release run, clean-environment check, API examples, judge attribution, failure modes |
| `phase0/` – `phase9/` | Dataset and brand analysis, golden set construction, retrieval benchmark, intent classifier, second opinion, agent benchmark, resolution intelligence, evaluation harness and judge, API, console fixtures, reliability and security experiments |
