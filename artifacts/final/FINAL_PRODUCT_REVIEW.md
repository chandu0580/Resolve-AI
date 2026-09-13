# ResolveAI 1.0: final product review

> This review records the state at the end of the product hardening pass. The final repository pass that followed changed live
> behaviour (`pipeline-v6.2`: capitalization, greetings, requests for a person, short replies) and moved the product scripts to
> `scripts/verification/` and `scripts/evaluation/`. The current state and its verification results are in
> `artifacts/final/FINAL_REPOSITORY_REVIEW.md`.

Final product hardening of the ResolveAI 1.0 candidate. No new phase was started, nothing was committed or pushed, and no frozen
evaluation artifact was changed (§11). Scores: `artifacts/final/PRODUCT_SCORECARD.md`.

## 1. Executive summary

**ResolveAI is a governed support-agent system, not an LLM wrapper.** For each customer message it returns exactly one action
(AUTO-HANDLED, CLARIFICATION or HUMAN HANDOFF) with the evidence, the policy rule, the verification result and a trace. The model
proposes; retrieved evidence determines what can be said; a deterministic policy determines what can be done; verification decides
whether a reply is acceptable; humans receive everything uncertain or risky with a complete packet.

What a reviewer can rely on, measured:
- **Grounding holds.** All 12 automatic replies of the release golden run pass the grounding audit (5 drafted replies each citing
  retrieved cases with sufficient evidence and passed verification, 7 fixed templates); 0 were sent to a customer who needed a human.
- **It fails safe.** 20 of 20 adversarial cases pass, including injection through customer text, retrieved evidence and model output;
  a live model outage produced an HTTP 200 human handoff.
- **Boundaries hold.** Every protected endpoint refuses anonymous and wrong-token calls; no token or model key appears in logs,
  reports or the browser.
- **Every decision is explainable in the product.** The console answers why a reply was allowed, what evidence supports it, which
  policy rule allowed it, whether it was verified and what would have caused a handoff, without reading source code.

What a reviewer should not overlook: escalation precision is 0.324 (75 unnecessary handoffs on 197 golden messages), only 6.1% of
messages are answered automatically, the LLM judge is not human-validated (0 of 50 rated), and the system is a single-process
reference product, not an enterprise deployment.

## 2. What the hardening changed

| Review question | Finding | Change |
|---|---|---|
| Trust test: *what would have caused a handoff?* | The explanation said why a reply was allowed but not what would have stopped it | "What would change it" added to every explanation, stated from the ordered policy rules and the output gate; a test keeps the console's rule order equal to the one the API serves |
| Handoff test: *can a human continue without asking again?* | The packet lacked the conversation summary and context | Packet and copied summary now carry the conversation summary and the number of earlier turns |
| Grounding test: *no "grounded" label without support* | The badge checked sufficiency and citations but not that each citation was a retrieved case | "Grounded" now requires every citation to be a retrieved case and sufficient evidence; otherwise "Grounding not confirmed"; grounding audit script added |
| Consistency audit | Banner said "Clarification required" where badges said "Clarification"; a placeholder "OP" avatar; "Try ResolveAI" left on an empty state; internal phase names ("Phase 9 final", "Phase 2") on the evaluation page | One label per action everywhere; placeholder removed; wording changed to "Pre-release run", "Earlier customer-message index", "Development evaluation" |
| Navigation | Detail pages had no way back except the sidebar | Breadcrumbs on conversation, handoff and trace pages |
| Demo readiness | The curated scenarios did not follow the demo story; two demo documents | Curated path reordered to the story; `docs/DEMO.md` is the single ten-minute, twelve-step flow |
| Performance | Listing 200 traces over a 20,000-trace file read the whole 108 MB file: 629 ms p50 | The listing reads backwards from the end and stops at the limit: 63 ms p50 at 20,000 traces, flat from 200 to 20,000 |
| Security | The console forwarder, the only browser path to the API, had no unit tests | `frontend/tests/proxy.test.ts`: disallowed paths never reach the API, browser credentials and cookies are dropped, errors carry no internal detail |
| Model failure | The live outage path was described but never exercised through the API | Verified live with an unreachable model endpoint; documented in the demo |
| Reproducibility | Release checks write into the frozen `artifacts/final/` | `scripts/verification/release_checks.py` and `d_final_product_verification.py` run them unchanged with output redirected |
| Documentation | README did not answer who it is for or what makes it safe up front | README rewritten around the ten questions; interview quick answers; architecture §11 (verified no-bypass flow) |
| Clean-up | A superseded 26 MB screenshot set | Removed; the hardening smoke set replaces it |
| Final UI inspection (after the browser smoke) | The handoff explanation read "Output gate blocked an automatic reply: … PII guard passed, Result complete", which sounds like passed checks blocked the reply | Reworded to "no automatic reply; N of 9 checks not met (…)"; covered by a unit test. This copy change came after the browser smoke; unit tests, lint, typecheck and the build were re-run on it |

Files changed by the hardening:
- **Backend:** `resolveai/api/service.py` (backwards trace reader).
- **Console:** `lib/explain.ts`, `lib/labels.ts`, `lib/handoff-summary.ts`, `components/decision/decision-explanation.tsx`,
  `components/handoff/{handoff-packet,handoff-detail}.tsx`, `components/response/response-panel.tsx`, `components/ui/card.tsx`,
  `components/conversation/conversation-detail.tsx`, `components/simulate/simulator.tsx`, `components/shell/topbar.tsx`,
  `components/overview/recent-decisions.tsx`, `components/evaluation/release.tsx`, `app/evaluation/page.tsx`,
  `app/traces/[traceId]/page.tsx`, `frontend/scripts/smoke.mjs`.
- **Tests:** `tests/test_final_hardening.py`, `frontend/tests/proxy.test.ts`, updates to `product`, `decision`, `trace` and
  `simulator` tests.
- **Scripts:** `scripts/verification/final_verification.py`, `e_grounding_audit.py`, `f_release_checks.py`.
- **Docs:** README, `docs/DEMO.md`, `INTERVIEW_NOTES.md`, `ARCHITECTURE.md`, `UI.md`, `API.md`, `PRODUCTION_READINESS.md`;
  `artifacts/product/PRODUCT_DEMO.md` (pointer); this review and the scorecard.

## 3. Product capabilities

| Surface | What it does |
|---|---|
| Overview | Principle strip; honest warnings computed from served data; LIVE OPERATIONAL DATA and FROZEN GOLDEN SET KPIs kept apart; recent decisions, handoffs and failures; system health; trust status |
| Conversations | Three panels: conversation list · thread, response and pipeline timeline · decision banner, eight-field explanation, handoff packet, evidence used vs retrieved, intent, risk, policy, output gate, run facts |
| Handoff Center | Severity-sorted queue with fixed categories and the reason codes behind them; packet with issue, summary, context, intent, risk, evidence found and missing, questions, next action, rejected draft; PII-scrubbed copy |
| Simulator | Seven curated situations in demo order, all API demo scenarios, free-form input; recorded stage outcomes after each run |
| Knowledge Center | Corpus statistics, evidence quality, provenance and leakage boundary, rule-based knowledge-gap candidates with examples, live coverage |
| Agent configuration | Read-only: model and versions, pipeline ownership, allowed and never-allowed actions, risk configuration, active vs evaluated configuration with differences, the 27 ordered rules |
| Evaluation Center | Release scorecard with intervals and paired differences, failure modes, outcomes by intent, judge attribution, human validation status, dev experiments, latency and cost profile, then the development study |
| Trace Explorer | What happened, why, how long, what failed, what evidence; execution-order timeline with safe metadata; explanation |
| Trust & Governance | Ten controls with status, enforcement point, threat, code and tests; release verification results |
| Settings | Credential presence only, limits and budgets, model and traces, browser storage with clear, known limitations |

## 4. Architecture

```text
Customer → TRUST → INTELLIGENCE → RETRIEVAL → EVIDENCE GATE → POLICY → GENERATION → VERIFICATION → ACTION → TRACE
```

Verified in the review (`docs/ARCHITECTURE.md` §11):
- **One path.** `POST /api/v1/resolve`, the CLI, the demo and the evaluation harness call the same `ResolveAI.resolve`; drafting is
  called only inside the orchestrator after policy; every other route is read-only.
- **Baselines stay offline.** The direct-LLM and simple-ML baselines exist only in `resolveai/evaluation/` and are not reachable
  from the API or console.
- **The API fails closed.** An automatic reply that breaks the evidence invariant is withheld (500).
- **No agent logic in the console.** Its forwarder allows only the API's own endpoints.

## 5. Security

| Check | Result |
|---|---|
| Unauthenticated and wrong-token access (live, auth-enabled server) | 401 for all 9 protected endpoints with no token and with a wrong token (18 of 18); `/health` 200 |
| Authorization, rate limits, docs, logs (production-profile API smoke) | 23 of 23 checks: 403 for a read token on `/resolve`, 429 with `Retry-After` on runs, reads and failed authentication, docs disabled, server log with 0 tokens, 0 keys, 0 raw email, phone or customer text |
| Console forwarder | Docs path and traversal attempt refused (404) live; unit tests: disallowed paths never reach the API, browser `Authorization` and cookies not forwarded, `Set-Cookie` not passed back, no internal address in errors |
| Injection through customer text, retrieved evidence, model output | Adversarial cases 10, 11, 12 pass: hard handoff with 0 model calls; instruction-like evidence quarantined; malicious model output cannot clear a flag or pass verification |
| Injection through trace metadata | Request metadata is schema-validated (`channel` enumerated, `locale` pattern, `customer_id_hash` hex only, unknown fields rejected); the trace schema forbids raw text, hidden reasoning and secret-like keys (`tests/test_api.py`, `tests/test_schemas.py`, `tests/test_phase9_pii.py`) |
| PII | Redaction before any model call, trace or log; 0 unredacted PII in scanned trace records (§11); served examples redacted again; copied handoff summary scrubbed again |
| Secrets | 0 occurrences of the generated API token or the model key in the hardening logs, smoke reports and audit outputs; the console renders credential presence only (smoke-checked); `.env` is gitignored and not committable |
| CORS, browser storage, errors | Explicit origins only (tested); localStorage holds only redacted results, disclosed and clearable; every error state shows a code and correlation ids, never a stack trace |

## 6. Grounding

`python scripts/evaluation/grounding_audit.py` (`artifacts/product/hardening/grounding_audit.json`):

| Source | Automatic replies | Checks | Failed |
|---|---|---|---|
| Release golden run | 12 (5 drafted, 7 templates) | drafted: citations present, each a retrieved case, evidence SUFFICIENT/STRONG, verified; templates: no citations, fixed template text; all: not annotated for escalation | 0 |
| Captured API response (scenario A) | 1 drafted, 3 citations | output gate all passed, citations retrieved, sufficient, verified; its trace records the decision, verification and output gate, retrieved the cited cases, and stores no reply text | 0 |

In the console, "Grounded" appears only when every citation is a retrieved case and the evidence was sufficient; insufficient
evidence is stated in words; retrieved and used evidence are separated. Limit: grounded is not correct, and reply quality is judged
only by an unvalidated LLM.

## 7. Evaluation

Frozen golden set, 197 messages, sha256 `33f4f333ccf10de7f628e57b5567a7930852cdf5b6d4bba872555b96b2bec3a9`, run once per system
(`artifacts/final/final_metrics.md`):
- escalation recall 0.973 [0.912, 1.000]; precision 0.324 [0.232, 0.411]; F1 0.486 [0.370, 0.579];
- 12 automatic replies, 0 unsafe; intent macro-F1 0.854 [0.799, 0.901];
- direct LLM: precision 0.739, F1 0.819, 3 unsafe replies;
- human judge validation 0 of 50.

No golden run was repeated in the hardening, and nothing was tuned against it.

## 8. UX

Browser smoke with Microsoft Edge, axe-core (WCAG 2.1 A/AA) and a production build against the auth-enabled API
(`artifacts/product/hardening/smoke/`):
- **Full:** 40 route visits, 7 of 7 scenarios with the expected decisions, 12 of 12 interactions, 0 axe violations, 0 pages with
  horizontal overflow at 1440, 1180, 834 and 390 px; the only console error is the deliberate 404 page.
- **Without a console token:** 5 routes show "Not authorized".
- **API stopped:** 7 routes show "ResolveAI API unavailable" (the console errors are the expected 502s).

Page performance, time to first byte for server-rendered pages:

| Page | TTFB | DOM nodes |
|---|---|---|
| Overview | 252 ms | 704 |
| Conversations | 219 ms | 1,461 |
| Workspace (p50 of 3) | 90 ms | 1,614 |
| Handoffs | 118 ms | 978 |
| Knowledge | 495 ms (first knowledge summary computation) | 2,054 |
| Traces | 39 ms | 1,291 |
| Trace detail (p50 of 4) | 59 ms | 780 |
| Evaluation | 86 ms (46 KB HTML) | 1,801 |
| Trust | 49 ms | 548 |
| Agents | 67 ms | 949 |
| Settings | 81 ms | 299 |

The first page of a fresh browser (Simulator) took 1.2 s. Scenario runs took 0.4–4.2 s because model responses came from the
response cache. Live model latency is unchanged from the release profile: p50 4.2 s, p95 14.2 s (random dev sample, n = 40).

## 9. Demo

`docs/DEMO.md`: one ten-minute story in twelve steps:
1. product overview;
2. customer request;
3. evidence retrieval;
4. grounded answer;
5. verification;
6. ambiguous request;
7. clarification;
8. risky request;
9. human handoff;
10. trace and audit;
11. evaluation dashboard;
12. trust controls.

It also covers the optional live model-failure setup and a screenshot fallback. The Simulator's curated path follows the same
order.

## 10. Known limitations and remaining production gaps

**Known limitations:**
- 75 unnecessary handoffs.
- A low automatic rate (6.1%).
- The LLM judge is not validated (0 of 50).
- One annotation pass was an AI.
- 197 golden rows from one 2017 burst.
- Some templates assert facts the message does not contain.
- Regex PII and pattern-based injection detection.
- A live model outage takes about 40 s to become a handoff.
- Conversation text survives only in the browser that ran it.
- English only.

**Remaining production gaps** (`docs/PRODUCTION_READINESS.md`: 53 items, 20 READY, 22 PARTIAL, 11 NOT READY):
- Identity and access: no TLS, operator SSO or roles; static tokens without rotation.
- Scale: process-local rate limits and a single worker; no load test.
- Operations: file-based traces without retention; no metrics or alerting; no runbooks.
- Supply chain: no dependency vulnerability scanning.
- Quality: no human validation of the judge.

## 11. Exact verification results

| Check | Command | Result |
|---|---|---|
| Backend tests | `python -m pytest -q` | 320 passed, 1 skipped, 0 failed (215 s) |
| Backend lint | `ruff check resolveai scripts/product tests/...` | all checks passed |
| Frontend tests | `npm test` | 120 of 120 in 15 files |
| Frontend lint | `npm run lint` | 0 problems |
| Frontend typecheck | `npm run typecheck` | clean |
| Frontend build | `npm run build` | succeeds (Next.js 16.3.4, 12 static pages generated; all routes including `/agents` and `/settings`), rebuilt after the last console change |
| Adversarial suite | `scripts/verification/release_checks.py adversarial` | 20 of 20 passed (40.5 s) |
| API smoke (production profile) | `scripts/verification/release_checks.py api-smoke` | 23 of 23 checks passed (58.7 s) |
| Live authorization probes | `curl` against the auth-enabled server | 18 of 18 protected calls refused with 401; forwarder docs and traversal 404 |
| Live model outage | API with unreachable model endpoint | HTTP 200, `HUMAN_HANDOFF`, `llm_unavailable`, rule `llm_fallback` (42 s) |
| Browser smoke, full | `npm run smoke` | 40 routes, 7 of 7 scenarios, 12 of 12 interactions, 0 failures |
| Browser smoke, unauthorized | `SMOKE_MODE=unauthorized` | 5 of 5 routes "Not authorized", 0 failures |
| Browser smoke, API down | `SMOKE_MODE=api-down` | 7 of 7 routes "ResolveAI API unavailable", 0 failures |
| Accessibility | axe-core in the smoke | 0 WCAG 2.1 A/AA violations |
| Grounding audit | `scripts/evaluation/grounding_audit.py` | 13 automatic replies checked, 0 failed |
| Trace listing performance | 200 rows over 200 / 5,000 / 20,000 traces | 61 / 50 / 63 ms p50 (before: 41 / 159 / 629 ms) |
| Clean environment, full run | `scripts/verification/release_checks.py clean-env --base-dir C:/rai_clean` (fresh virtual environment, 763 committable files copied, no `.env`, no `.cache`, isolated model cache, no model credentials; 170 min) | **did not pass.** Passed: venv (25 s), `pip install -r requirements-dev.txt` (584 s), `pytest` 319 passed, 2 skipped (58 min; the extra skip is `tests/test_intelligence.py`, which needs the gitignored, local-only `data/processed/silver_train.csv`), demo without a model key (89 s), API reply without a model (HTTP 200, `CLARIFICATION_REQUIRED`, ready after 18 s), `npm ci`, lint, typecheck, `npm test`, `npm run build`. **Failed:** `scripts/final/f_final_verification.py` (exit 1, 93 min) |
| Clean environment: cause and fix | in-memory recomputation of the release check on the committable file set | the release verification's baseline (Phase 10 snapshot) predates `artifacts/product/`, so its 84 committable files counted as "new files in frozen locations" and the documented command failed on the final repository; all 353 frozen release files were unchanged and none missing. Fixed in `scripts/final/f_final_verification.py`: `artifacts/product/` is an output folder like `artifacts/final/` (it has its own baselines); the two product verification scripts were updated to the new line and all their replacements still match |
| Clean environment: fix confirmed (no cached evaluation) | fresh copy of the 768 committable files outside the repository, `git init`, `python scripts/final/f_final_verification.py --skip-cached-eval` | **passed** (exit 0, 45 s): golden verified (197 rows, same sha256); 353 frozen release files, 0 changed, 0 missing committable, 35 gitignored local-only files absent (counted, not failed), 0 new files in frozen locations; Phase 7 snapshot 115 files, 0 changed, 1 local-only absent; security scan 0 findings over 768 files (82.8 MB) |
| Clean environment: full release verification after the fix | second fresh copy of the 768 committable files, `git init`, no `.env`, no `.cache`, isolated model cache (`HF_HOME`), model credentials removed from the environment; `python scripts/final/f_final_verification.py` | **passed** (exit 0, 337 s): golden verified (197 rows, same sha256); 353 frozen release files, 0 changed, 0 missing committable, 0 new files in frozen locations; Phase 7 snapshot 115 files unchanged; cached evaluation regenerated all 11 result files byte-identical (308 s); security scan 0 findings over 768 files. Scope: the full clean-environment run above was not repeated end to end; its other steps had already passed, and this re-runs the one step that failed, on a clean file copy with the same interpreter |
| Golden set integrity | `scripts/verification/final_verification.py` | verified on load: 197 rows, sha256 `33f4f333ccf10de7f628e57b5567a7930852cdf5b6d4bba872555b96b2bec3a9`, unchanged |
| Frozen artifacts, byte-level | same, against `artifacts/product/hardening/hardening_start_snapshot.json` (taken before any hardening change) | 416 files checked (data/, every artifacts/ folder including the 60 files of artifacts/final/, frozen models and configs): 0 changed, 0 missing, 0 unexpected new files; the only new files in a frozen location are this review and the scorecard, which the prompt requires |
| Phase 7 hash snapshot | same | 115 files: 0 changed, 0 missing; golden matches its freeze manifest |
| Cached evaluation | same (`scripts/evaluate.py --cached`, no model calls) | all 11 regenerated Phase 6 result files byte-identical (299 s) |
| Security scan | same | passed: 0 findings over 765 committable files (82.7 MB); `.env` not committable; checked secret variables `LLM_API_KEY`, `GROQ_API_KEY`, `GEMINI_API_KEY`; 0 of 772 trace records contain unredacted PII |
| Final integrity and security pass, after the last script and report edits | `scripts/verification/final_verification.py --skip-cached-eval` (the earlier full report is kept as `verification_with_cached_eval.json`) | **passed:** golden verified, same sha256; 416 frozen files, 0 changed, 0 missing, 0 unexpected new files; Phase 7 snapshot 115 files unchanged; security scan 0 findings over 769 committable files (82.8 MB), 0 of 772 trace records with PII |

**Git.** The repository has no commits, so `git diff` is empty by construction; `git status` lists every top-level path as untracked.
`.env`, `.cache/`, traces, logs and build output are ignored. Nothing was committed or pushed.
