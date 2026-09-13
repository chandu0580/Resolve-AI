# ResolveAI 1.0.0 — final release status

**Production-style reference implementation for the Hiver SDE Intern take-home assignment.** Not a deployed service and not
production-ready: `docs/PRODUCTION_READINESS.md` lists 55 items, of which 23 are PARTIAL and 11 are NOT READY. Passing tests does
not change that.

Compiled 2026-09-12 at the end of the productization pass. Every figure below was produced on this date on this machine.

## Status summary

| Area | Status | Basis |
|---|---|---|
| Product experience | **READY** | 13 pages, all loading against the live API; engineering detail moved behind "Technical details" disclosures |
| Backend | **READY** | FastAPI, production profile, authentication enforced, running now on `:8000` |
| Frontend | **READY** | Next.js production build, running now on `:3000`, talking to the real backend |
| Tests | **READY** | Backend 467 passed / 1 skipped / 0 failed; frontend 122 of 122 |
| Lint, types, build | **READY** | `ruff`, ESLint, `tsc --noEmit`, `next build` all clean |
| Security | **READY** for a reference implementation; **NOT READY** for production | 0 scan findings over 724 files; 0 of 813 trace records with PII; adversarial 20/20; API smoke 23/23. No TLS, SSO, token rotation or dependency scanning |
| Evaluation | **PARTIAL** | Frozen golden set, four baselines, bootstrap intervals, LLM judge — but **no human labels anywhere** |
| Reproducibility | **READY** | Cached evaluation regenerates all 11 result files byte-identically; measured reproduce path 9 min 17 s; clean copy passes all 9 steps |
| Repository | **READY** | 724 committable files, 55.2 MB; structure matches the target layout |

## Product

Thirteen operator pages, all verified loading against the running backend:

Overview · Conversations · Conversation workspace · Handoffs · Handoff packet · Simulator · Knowledge · Agent · Evaluation ·
Trust · Traces · Audit trail detail · Settings

Navigation groups: **Overview**, then **Operate** (Conversations, Handoffs, Simulator), **Knowledge**, **Agent**, **Govern**
(Evaluation, Trust), **System** (Traces, Settings).

**What changed in this pass.** Engineering identifiers no longer appear in the operator experience. Pipeline and policy version
strings, gate names, configuration hashes, model-call counts and token counts moved behind collapsed "Technical details" and
"Decision reference" disclosures, or to the Traces, Evaluation and Trust pages where they belong. The Overview gained a product
hero and its warnings are now written in operator language rather than version strings. The run card leads with when the
conversation was handled, how long it took, and a link to the audit trail.

## Verification (all re-run 2026-09-12)

| Check | Command | Result |
|---|---|---|
| Backend tests | `python -m pytest -q` | 467 passed, 1 skipped, 0 failed |
| Python lint | `python -m ruff check .` | clean |
| Frontend lint / types / tests / build | `npm run lint` · `typecheck` · `test` · `build` | clean · clean · 122 of 122 · succeeds |
| Input robustness | `python scripts/verification/input_robustness.py` | 53 message classes + 15 malformed bodies, 0 crashes, 0 contract failures |
| Adversarial suite | `python scripts/verification/release_checks.py adversarial` | 20 of 20 |
| Live API smoke (production profile) | `python scripts/verification/release_checks.py api-smoke` | 23 of 23 |
| Browser smoke, signed in | `npm run smoke` | 40 route visits, 7 of 7 scenarios, 12 of 12 interactions, 0 failures, 0 axe violations, 0 horizontal overflow |
| Browser smoke, no console token | `SMOKE_MODE=unauthorized npm run smoke` | 5 routes show "Not authorized", 0 failures |
| Browser smoke, API stopped | `SMOKE_MODE=api-down npm run smoke` | 7 routes show "API unavailable", 0 failures |
| Grounding audit | `python scripts/evaluation/grounding_audit.py` | 12 automatic replies (5 drafted, 7 templates), 0 failures |
| Cached evaluation | inside the verification | all 11 result files byte-identical, 132 s |
| Integrity + security scan | `python scripts/verification/final_verification.py` | passed; golden hash unchanged; 0 undeclared frozen changes; 0 findings over 724 files; 0 of 813 trace records with PII |

**Case-insensitivity.** Every casing group named in the brief produces one identical outcome — action, rule, intent, confidence,
evidence level and reply text — and the customer's original text is preserved untouched for display and audit. Locked by
`tests/test_case_and_conversation.py` (77 tests).

## Evaluation

Frozen golden set: 197 rows, sha256 `33f4f333…`, hash-verified on every load, run once, never tuned against. Four baselines.
95% bootstrap intervals, 1,000 resamples, seed 42.

Headline: escalation recall 0.973 [0.912, 1.000]; 0 unsafe automatic replies out of 12; intent macro-F1 0.854 [0.799, 0.901].
The direct-LLM baseline escalates better (F1 0.819 vs 0.486) and sent 3 unsafe replies. Read `FINAL_REPORT.md` §7 before quoting
any of that.

## Current versions

| Component | Version |
|---|---|
| Release | 1.0.0 |
| Pipeline (running) | `pipeline-v6.3` |
| Policy (running) | `policy-v3.3`, 27 ordered rules |
| Pipeline (evaluated) | `pipeline-v6.1` / `policy-v3.1` — the golden run was **not** repeated; 21 of 197 rows reach a changed input path |
| Evidence gate / rerank / output gate | `gate-v3` / `rerank-v1` / `output-gate-v1` |
| Model | GLM-5.2 through an OpenAI-compatible endpoint |

## Repository structure

```
ResolveAI/
├── resolveai/          agent · api · config · data · evaluation · intelligence · llm
│                       models · observability · policy · retrieval · schemas · trust
├── frontend/           Next.js operator console (no agent logic)
├── data/               golden/ (frozen) · human_eval/ · processed/ · dev/ · demo/
├── docs/               ARCHITECTURE · API · UI · EVALUATION · DEMO · DECISIONS
│                       PRODUCTION_READINESS · REPRODUCIBILITY · INTERVIEW_NOTES · INTENTS · HUMAN_JUDGE_GUIDE
├── scripts/            verification/ · evaluation/ · evaluate.py · security_scan.py · final/ · phase0–9/
├── tests/              30 backend modules
├── artifacts/          final/ · product/ · evaluation/ · earlier phase evidence
└── README.md · requirements.txt · requirements-dev.txt · pyproject.toml · .env.example · .gitignore
```

724 committable files, 55.2 MB. 29 MB of stale browser-smoke screenshots were dropped from the committable set in this pass
(the smoke's JSON results, which are the actual evidence, are kept); frozen phase evidence was not touched.

## Known limitations

1. **No human labels anywhere in the evaluation.** Both golden-set annotation passes were AI annotators under a written guide,
   and 0 of the 50 judge-packet rows are rated. The brief asks for both. This is the largest gap.
2. **The running pipeline is newer than the evaluated one.** `v6.3` vs `v6.1`; 21 of 197 golden rows reach a changed path; the
   golden run was deliberately not repeated.
3. **Over-escalation.** 75 unnecessary handoffs on golden; autonomy is 6.1%, capped by corpus coverage rather than thresholds.
4. **Small, narrow evaluation.** 197 rows from one November 2017 burst; 37 escalation positives; 7 rows reach STRONG evidence.
5. **Shallow detectors.** Regex PII detection misses names and addresses; injection detection is pattern-based.
6. **The release judge scores describe wording the product no longer sends** (two handoff templates were corrected).
7. **Model outages take about 40 s** to become a handoff while calls time out.
8. **Not a deployment.** One process, process-local rate limits, file-based traces, no TLS, operator login, metrics, retention
   or runbooks.

## Remaining human actions

| # | Action | Effort |
|---|---|---|
| 1 | Rate `data/human_eval/human_scoring_packet.csv` per `docs/HUMAN_JUDGE_GUIDE.md`, then re-run `python scripts/evaluate.py --cached` | 60–90 min |
| 2 | Optionally hand-check golden rows yourself and record it, to address the "hand-labelled" wording | 1–3 h |
| 3 | Commit, push, set repository access, and send the link to anurag@hiverhq.com | 10 min |

## Start and test commands

```bash
# Backend (production profile, authentication required)
RESOLVEAI_ENV=production RESOLVEAI_API_TOKEN=<32+ chars> RESOLVEAI_READ_TOKEN=<32+ chars> python -m resolveai serve --port 8000

# Backend (development profile, no authentication, Swagger at /docs)
python -m resolveai serve

# Frontend
cd frontend && npm ci && RESOLVEAI_API_TOKEN=<same resolve token> npm run start -- --port 3000

# Tests and verification
python -m pytest -q && python -m ruff check .
cd frontend && npm run lint && npm run typecheck && npm test && npm run build
python scripts/evaluate.py --cached
python scripts/verification/final_verification.py
python scripts/verification/release_checks.py adversarial
python scripts/verification/release_checks.py api-smoke
python scripts/verification/input_robustness.py
cd frontend && npm run smoke
```

Nothing has been committed, pushed or published. The repository has no commits and no remote.
