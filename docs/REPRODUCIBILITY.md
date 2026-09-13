# Reproducing ResolveAI

Everything runs locally with Python 3.11+ and Node.js 20.9+. No Docker and no private infrastructure are needed. The full
3-million-row Kaggle file is **not** needed: the processed subsample, the golden set, the frozen models and configuration, and
every evaluation run record are in the repository.

## 1. What needs what

| Task | API key | Internet | Time (8-core CPU) |
|---|---|---|---|
| Install | no | yes (pip, npm, first download of the BGE-small embedding model) | about 5–10 min |
| Tests (`pytest`, frontend checks) | no | first run only (embedding model) | about 3 min, plus about 8 min once to embed the knowledge base |
| Cached evaluation (recompute every headline number) | no | no | **measured: 171.6 s** on an 8-core laptop |
| Start the API and console, run the deterministic demo | no (the agent falls back to clarification or handoff) | first run only | 1–2 min to load |
| Live agent: grounded drafts, risk model, second opinion | yes | yes | seconds per message |
| Re-running the golden evaluations or the judge | yes | yes | hours; the final runs refuse to run twice |

**Credentials.** Copy `.env.example` to `.env` and set `LLM_API_KEY`, `LLM_BASE_URL` and `LLM_MODEL` for any OpenAI-compatible
endpoint; the evaluated model is GLM-5.2. `.env` is gitignored, and no key is ever committed or printed. For the
production-profile API, set `RESOLVEAI_API_TOKEN` to at least 32 random characters, in both the API's and the console's
environment.

## 2. Clean setup

```bash
git clone <repository> resolveai && cd resolveai
python -m venv .venv && . .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                  # optional: model credentials
cd frontend && npm ci && cd ..
```

The first command that builds the knowledge base embeds 17,875 historical cases with BGE-small and caches the vectors under
`.cache/embeddings`.

## 3. Run

```bash
python -m resolveai serve                             # API on http://127.0.0.1:8000 (development profile, no auth)
cd frontend && npm run dev                            # console on http://localhost:3000
python -m resolveai demo --no-llm                     # the scripted scenarios through the same orchestrator
python -m resolveai "my iphone battery drains fast since the update"
```

Production-style profile (authentication required, docs disabled, 45 s request budget):

```bash
RESOLVEAI_API_TOKEN=<32+ random chars> python -m resolveai serve --env production
cd frontend && npm run build && RESOLVEAI_API_TOKEN=<same token> npm start
```

## 4. Verify

```bash
python -m pytest -q                                             # backend, including the adversarial and input-robustness suites
python -m ruff check .
cd frontend && npm run lint && npm run typecheck && npm test && npm run build && cd ..
python scripts/verification/final_verification.py               # golden hash, frozen artifacts, Phase 7 snapshot, cached evaluation, security scan
python scripts/verification/input_robustness.py                 # 53 awkward input classes + 15 malformed API bodies
python scripts/verification/release_checks.py adversarial       # the adversarial PASS/FAIL table
python scripts/verification/release_checks.py api-smoke         # live HTTP checks in the production profile
python scripts/evaluation/grounding_audit.py                    # automatic replies <-> evidence <-> citations <-> verification <-> trace
cd frontend && npm run smoke                                    # browser smoke against a running stack (installed Edge + axe-core)
```

`verification/final_verification.py` is **non-destructive**. It runs `scripts/evaluate.py --cached` into a scratch folder,
compares the 11 regenerated result files with the frozen `artifacts/evaluation/` files, and writes only under
`artifacts/product/hardening/`. The release-era entry points it wraps still live in `scripts/final/`; run the `verification/`
wrappers rather than those directly, so nothing writes into a frozen location.

Two commands do write into frozen locations when run directly, which is expected:
- `scripts/evaluate.py --cached` rewrites `artifacts/evaluation/`. The 11 **result** files are byte-identical unless human
  ratings were added; `reproduction_manifest.json` and `PHASE6_REPORT.md` also record the run's wall-clock seconds, so their
  bytes change every time. `final_verification.py` names those two, and the two judge-agreement files, as expected changes with
  their reason — frozen *inputs* (golden set, run records, judge results, model artifacts) are never exempt.
- `scripts/security_scan.py` rewrites the Phase 7 record in `artifacts/phase7/` with the **current** committable file set, so a
  later integrity check reports that file as changed. It is named in `final_verification.py`'s declared-exception list with that
  reason. The verification's own scan is redirected elsewhere and never touches it; only running this command directly does.

## 5. Human judge study (the one open evaluation step)

Fill the `human_*` columns of `data/human_eval/human_scoring_packet.csv` following `docs/HUMAN_JUDGE_GUIDE.md`, without opening
`_packet_key.json`. Then run `python scripts/evaluate.py --cached`, and `artifacts/evaluation/judge_agreement.md` reports
judge-human agreement.

## 6. Experiments by phase (reproduction commands)

Scripts that call the model need a key. Golden-set runs were executed once each, and the final ones refuse to run again.

| Phase | Commands |
|---|---|
| 0 reconnaissance | `python scripts/phase0/01_dataset_profile.py` … `06_auto_resolvability.py` (needs `data/raw/twcs.csv`) |
| Rebuild data (optional, about 5 min) | download `thoughtvector/customer-support-on-twitter` with kagglehub, copy `twcs.csv` to `data/raw/`, then `python -m resolveai.data.ingest && python -m resolveai.data.manifest` |
| 1 model choice, golden set | `scripts/phase1/a_llm_smoke.py`, `c_golden_sample.py`, `d_annotatorA_labels.py`, `d_agreement.py`, `d2_apply_v11.py` |
| 2 retrieval | `python scripts/phase2/run_retrieval_benchmark.py && python scripts/phase2/extra_configs.py && python scripts/phase2/gate_v2_calibrate.py && python scripts/phase2/analyze_retrieval.py` |
| 3 intelligence | `python scripts/phase3/a_silver_labels.py && python scripts/phase3/a2_silver_noise_check.py && python scripts/phase3/b_train_eval.py && python scripts/phase3/c_context_retrieval.py && python scripts/phase3/d_second_opinion.py && python scripts/phase3/e_analyze.py` |
| 4 agent | `python scripts/phase4/a_second_opinion_policy.py && python scripts/phase4/b_agent_benchmark.py && python scripts/phase4/c_latency.py` |
| 5 resolution intelligence | `scripts/phase5/a_retrieval_resolution.py --dev / --final`, `b_risk_hardening.py 40`, `c_draft_experiment.py 40`, `d_verifier_analysis.py`, `f_latency.py 40`, `e_golden_benchmark.py` |
| 6 evaluation harness | `python scripts/evaluate.py --cached` (or `--live`), `scripts/phase6/c_human_packet.py` |
| 7 API | `scripts/phase7/a_injection_false_positives.py`, `b_perf.py`, `c_integrity.py`, `d_api_examples.py` |
| 8 console | `python scripts/phase8/export_openapi.py`, `scripts/phase8/capture_fixtures.py`; `cd frontend && npm run gen:api` |
| 9 hardening | `scripts/phase9/a_risk_dev_experiment.py 240`, `b_risk_dev_metrics.py`, `c_perf_profile.py`, `d_golden_final.py report`, `e_cached_eval_check.py`, `f_verify_integrity.py` |
| 10 final | `scripts/final/a_private_info_experiment.py` (dev), `g_golden_release.py run` and `judge` (once), `b_final_metrics.py`, `c_perf_final.py`, `d_adversarial_suite.py`, `e_api_smoke.py`, `f_final_verification.py`, `h_clean_env_check.py` |
