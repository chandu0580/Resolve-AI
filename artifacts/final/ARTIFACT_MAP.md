# Final dependency and artifact map

This map classifies every data file, artifact and document in the repository.
- **FROZEN:** never modified after its phase. The golden hash is verified on every load, and `scripts/final/f_final_verification.py`
  compares every frozen file with the snapshot taken at the start of Phase 10 (`phase10_start_snapshot.json`).
- **FINAL:** the results of record for this submission. Regenerate them only through the named script.
- **HISTORICAL:** final for its own phase but superseded as a source of headline numbers.
- **MUTABLE:** code, tests, docs and runtime state.
- **DEPRECATED:** kept as evidence for a decision; not the current behaviour.
- **KNOWN LIMITATION:** where each open limitation is documented.

## FROZEN

| Path | Content | Produced by | Consumed by |
|---|---|---|---|
| `data/golden/golden_final.csv` (sha256 `33f4f333…`), `golden_freeze_manifest.json`, `ANNOTATION_GUIDE.md`, adjudication files | 197-row golden set: intent, should_escalate, reason; annotator B was an AI | `scripts/phase1/*` | `resolveai/evaluation/golden.py` (hash-checked load), every evaluation |
| `data/processed/apple_pairs.csv`, `dataset_manifest.json` | 18,000 KB + 2,000 holdout pairs, redacted, temporal split | `python -m resolveai.data.ingest` | retrieval index, classifier, dev samples |
| `data/human_eval/human_scoring_packet.csv`, `packet_manifest.json`, `_packet_key.json` | 50 blinded examples; `human_*` columns intentionally empty. The only permitted change is a human filling them. | `scripts/phase6/c_human_packet.py` | `scripts/evaluate.py --cached` (judge-human agreement) |
| `data/dev/phase9_risk_labels.json` | 76 dev labels, **AI annotator** | Phase 9 | `scripts/phase9/b_*`, `scripts/final/a_*` |
| `data/dev/*` (other), `data/demo/scenarios.json` | dev smoke labels; 7 demo scenarios | Phases 3–7 | tests, demo, console |
| `resolveai/models/artifacts/intent_bge_lr.json` | frozen classifier | `scripts/phase3/b_train_eval.py` | `intelligence/classifier.py` |
| `resolveai/retrieval/gate_v3_config.json`, `rerank_weights.json`, `gate_config.json`, `resolveai/agent/second_opinion_policy.json` | frozen gate, rerank and second-opinion policy | Phases 2–5 | retrieval engine, orchestrator |
| `artifacts/evaluation/**` | Phase 6 evaluation of record for the baselines (B0, B1, B2), the Phase 5 system, ablations, judge and pairwise results | `scripts/evaluate.py --live` | `scripts/evaluate.py --cached`, final metrics |
| `artifacts/phase9/evaluation/runs/phase9_final.*`, `judge_phase9_final.jsonl` | the single Phase 9 golden run and its judge (the script refuses a rerun) | `scripts/phase9/d_golden_final.py` | `scripts/final/b_final_metrics.py` |
| `artifacts/final/evaluation/runs/final_release.*`, `judge_final_release.jsonl` | the single golden run of the 1.0.0 release configuration and its judge (the script refuses a rerun) | `scripts/final/g_golden_release.py` | `scripts/final/b_final_metrics.py` |

## FINAL (Phase 10 results of record)

| Path | Content | Script |
|---|---|---|
| `artifacts/final/FINAL_REPORT.md` | the final report | written from the artifacts below |
| `artifacts/final/FINAL_STATUS.md`, `SUBMISSION_CHECKLIST.md` | status and submission checklist | — |
| `artifacts/final/final_metrics.{md,json}` | ResolveAI vs baselines with paired 95% CIs; release vs Phase 9 | `scripts/final/b_final_metrics.py` |
| `artifacts/final/risk_experiment/` | `PREREGISTRATION.md`, `runs.jsonl`, `report.{md,json}`, `decision.json` | `scripts/final/a_private_info_experiment.py` |
| `artifacts/final/performance/perf_final.{md,json}` | no-model / cached / live latency, tokens, cost | `scripts/final/c_perf_final.py` |
| `artifacts/final/adversarial_suite.{md,json}` | 20-case adversarial suite, PASS/FAIL | `scripts/final/d_adversarial_suite.py` (same cases as `tests/test_final_adversarial_suite.py`) |
| `artifacts/final/api_smoke.json` | live HTTP checks in the production profile | `scripts/final/e_api_smoke.py` |
| `artifacts/final/verification.json`, `security_scan.json`, `cached_eval_check.json` | integrity, security scan, cached-evaluation reproduction | `scripts/final/f_final_verification.py` |
| `artifacts/final/backend_junit.xml`, `frontend_junit.xml`, `smoke/` | test and browser-smoke results | pytest, vitest, `frontend/scripts/smoke.mjs` |
| `artifacts/final/clean_env_check.json` | clean-clone reproducibility check (the re-run after the dependency fix) | `scripts/final/h_clean_env_check.py` |
| `artifacts/final/clean_env_check.attempt2.json` | full clean-clone run after the dependency fix. The install, demo, API, lint, typecheck and build passed. It found three more gaps: a `.gitignore` rule hiding the console's Traces pages, a test assuming a local-only file, and a Windows newline bug in the verification script. | `scripts/final/h_clean_env_check.py` |
| `artifacts/final/clean_env_check.attempt1.md` | the first clean-clone run, which failed on an undeclared dependency (`rank-bm25`); kept as evidence | `scripts/final/h_clean_env_check.py` |
| `artifacts/final/phase10_start_snapshot.json` | hash snapshot taken before any Phase 10 change | one-off, recorded in `FINAL_REPORT.md` |

## HISTORICAL (final for their phase; not headline sources)

| Path | Phase | Superseded by |
|---|---|---|
| `artifacts/PHASE0_*`, `brand_analysis/`, `dataset_recon/`, `technology_recon/`, `evaluation_design/`, `architecture/system_architecture.md` | 0 (reconnaissance, brand choice, design) | `docs/ARCHITECTURE.md`, `docs/DECISIONS.md` |
| `artifacts/llm_smoke/` | 1A (model choice) | still the evidence for GLM-5.2 (#7) |
| `artifacts/retrieval/` | 2 (retrieval benchmark, gate-v2) | `artifacts/resolution/` (gate-v3), `final_metrics.md` |
| `artifacts/intelligence/` | 3 (classifier, second opinion) | Phase 6 intent numbers |
| `artifacts/agent/` | 4 (first end-to-end agent) | Phase 5, then Phase 6 |
| `artifacts/resolution/` | 5 (resolution intelligence; the system Phase 6 evaluated) | `artifacts/evaluation/`, `final_metrics.md` |
| `artifacts/phase7/`, `artifacts/phase8/`, `artifacts/phase9/` | 7 (API), 8 (console), 9 (hardening, single final run) | `artifacts/final/` |

Numbers inside historical reports describe the system as it was in that phase. The current numbers are in
`artifacts/final/final_metrics.md` and `FINAL_REPORT.md`.

## MUTABLE

| Path | Notes |
|---|---|
| `resolveai/`, `frontend/`, `tests/`, `scripts/`, `docs/`, `README.md`, `.env.example`, `requirements.txt`, `pyproject.toml` | code and documentation; Phase 10 changes are listed in `verification.json` → `mutable_changes_since_phase10_start` |
| `traces/` | runtime audit traces (gitignored; no customer text) |
| `.cache/embeddings`, `.cache/llm` | embedding cache and SHA-256 model-response cache (gitignored; regenerable) |
| `.env` | local credentials (gitignored; never committed) |

## DEPRECATED (kept as evidence, not current behaviour)

| Item | Why kept | Current |
|---|---|---|
| risk schema `full` (risk-flags-v1), prompt `compact_v3` (risk-flags-v3), Phase 9 corroboration variants V2/V4 | measured and rejected (Phases 5 and 9) | `compact` (risk-flags-v2) + `needs_private_info` corroboration |
| `draft_version="v1"` | drafting A/B (Phase 5) | draft-v2 |
| gate-v2 (`gate_config.json`), BM25 and hybrid retrieval, outcome bonus | Phase 2 benchmarks | gate-v3, dense pair index, bonus off |
| `artifacts/phase8/smoke_results.run1_empty_store.json` | first smoke run against an empty trace store | `artifacts/final/smoke/` |
| Response examples in older reports (`pipeline-v5.1`) | recorded in their phase | `docs/API.md` |
| Running `scripts/security_scan.py` or `scripts/phase7/c_integrity.py` directly | they write the Phase 7 record (`artifacts/phase7/`) | `scripts/final/f_final_verification.py` redirects both to `artifacts/final/` |
| Running `scripts/evaluate.py --cached` in place | it rewrites `artifacts/evaluation/` (identical content unless human ratings were added) | to check reproduction without writing, use `scripts/final/f_final_verification.py` |

## KNOWN LIMITATIONS (where each is documented)

| Limitation | Documented in |
|---|---|
| Human evaluation not completed (0 of 50 rated); judge unvalidated | `FINAL_REPORT.md` §1, §4 and §8; `docs/EVALUATION.md`; README |
| Over-escalation: escalation precision still low | `FINAL_REPORT.md` §5–§7; `docs/PRODUCTION_READINESS.md` |
| Small golden set (197 rows, 37 positives, 12 autonomous replies); AI-derived labels | `FINAL_REPORT.md` §7 |
| One 2017 Apple burst; retrieval ceiling (7 of 197 STRONG) | `FINAL_REPORT.md` §6–§7 |
| Regex PII detection; pattern-based injection detection | `docs/PRODUCTION_READINESS.md` (Privacy, Security) |
| Single process; process-local rate limits; no TLS, operator login, metrics or runbooks | `docs/PRODUCTION_READINESS.md` |
| Live draft/verification latency measured only on a small sample | `artifacts/final/performance/perf_final.md` |
