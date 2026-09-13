# Product Completion Prompt 1: report

ResolveAI 1.0.0 was turned into a coherent AI customer-support product on its existing architecture: FastAPI agent, Next.js
console, the single `POST /api/v1/resolve` pipeline, the evidence invariant, the deterministic policy and human handoff.
No new phase was started. No Docker, Kubernetes or orchestration framework was added. Nothing was tuned on the golden set, nothing
was committed or pushed.

The principle is visible in the shell, on the Overview, the Agents pipeline and the explanation panels:
**model proposes · evidence grounds · policy decides · verifier checks · humans control exceptions.**

## 1. What changed and why

### Backend (additive, read-only)

| Change | Why |
|---|---|
| `resolveai/api/product.py` + routes `GET /api/v1/evaluation/release`, `/agent/profile`, `/knowledge/summary` | The Evaluation Center, Agents and Knowledge Center needed release results, configuration and corpus facts. They read committed artifacts, the loaded agent and the knowledge base; none runs the agent, calls a model, recomputes a metric or creates another path to a reply. Scope `read`; 401 without a token. |
| `TraceSummary.estimated_cost_usd` (`schemas.py`, `service.py`) | The Overview's "estimated cost" KPI; summed from the usage the trace already records. |
| `POLICY_RULES` in `resolveai/policy/escalation.py` | The Agents page lists the 27 ordered rules. It is data next to `decide()`; a test asserts it names the same rules in the same order, so it cannot drift silently. `decide()` itself is unchanged. |
| `scripts/evaluation/release_by_intent.py` → `artifacts/product/release_by_intent.json` | Per-intent outcomes of the single release run (no model, no new golden run) and the fixed knowledge-gap rule. Example messages redacted again. |
| `scripts/verification/capture_console_fixtures.py` | Console test fixtures for the new endpoints captured from the real in-process API, not hand-written. |
| `scripts/verification/verify_product_pass.py` | Runs the release verification unchanged except for its baseline (`product_start_snapshot.json`, which also freezes `artifacts/final/`) and its output folder. |

`/resolve` remains the only agent entry point, and every automatic reply still passes the evidence gate, policy, verification,
output gate and trace. The proxy allowlist gained exactly the three read-only paths.

### Console

| Area | Change |
|---|---|
| Shell | Navigation regrouped: Operate (Overview, Conversations, Handoffs, Simulator), Knowledge & agents (Knowledge, Agents), Govern (Evaluations, Traces, Trust & Governance), System (Settings); page titles; principle line in the sidebar; operator placeholder no longer claims "no authentication". |
| Overview | Principle strip; honest warnings computed from served data; LIVE OPERATIONAL DATA KPIs (volume, auto-handled, clarification, handoff, evidence sufficiency, average/p50/p95 latency, model calls, estimated cost, failed requests, and "Not measured live" for recall and groundedness); FROZEN GOLDEN SET KPIs with intervals from the release; recent decisions, handoffs and failures; system health; trust status. |
| Conversations | Three-panel workspace: LEFT conversation list, CENTER thread, response and pipeline timeline, RIGHT decision banner, explanation, handoff packet, evidence, intent/risk/policy/output gate, run facts. Trace-only view in the same layout. |
| Explanation | `lib/explain.ts` + `DecisionExplanation`: decision, reason, evidence, policy, risk, verification, next action, with the headings WHY THIS RESPONSE WAS ALLOWED / WHY THE AGENT ASKED FOR MORE INFORMATION / WHY A HUMAN WAS REQUIRED. From structured data only; shown in the workspace, Handoff detail and Trace Explorer. |
| Evidence | EVIDENCE USED IN RESPONSE separated from RETRIEVED EVIDENCE; "ResolveAI did not find sufficient historical evidence to safely answer." with the gate's reason; "Retrieved is not the same as trustworthy". |
| Handoff Center | Filters All, Safety, Security, Billing, Account, Technical, Insufficient evidence, Model failure, Other from reason codes (security rule distinguished), with the codes behind each queue shown; risk and next-action columns; packet shows evidence found and missing and the rejected draft; copied summary scrubbed for PII again. |
| Knowledge Center | Corpus statistics, evidence quality by issue category, provenance and leakage boundary; knowledge-gap candidates on the frozen golden set with the rule and inspectable examples; live coverage labelled separately; retrieved cases from this browser. |
| Agents | Read-only: status, model and versions, pipeline and who decides, allowed and never-allowed actions, risk configuration, ACTIVE vs EVALUATION configuration with differences, ordered policy rules. |
| Evaluation Center | Release scorecard with 95% intervals and paired differences vs B2, B1 and Phase 9; failure modes; outcomes by intent; judge attribution; human validation status; dev experiments; latency and cost profile; limitations. The Phase 6 study follows, labelled as the pre-release configuration. |
| Trace Explorer | Trace summary (what happened, why, how long, what failed, what evidence), stage labels "PII check" and "Final action" in the real execution order, explanation. |
| Trust & Governance | Ten controls with STATUS (from the running configuration), ENFORCED AT, WHAT IT PROTECTS AGAINST, code and tests; release verification results labelled as release artifacts. |
| Settings | Connection and authentication (token presence only), limits and budgets, model and traces, browser storage with clear action, known limitations. |
| Simulator | Curated seven-situation demo path mapped to API scenarios A–F plus one curated private-information message; recorded agent stages after each run. |
| Terminology and errors | AUTO-HANDLED / CLARIFICATION / HUMAN HANDOFF everywhere; explanations added for 404 `not_found`, `method_not_allowed`, `auth_required`, `length_required`, `payload_too_large`, `demo_not_available`, `cancelled`, `http_error`, `client_error`. |

### Docs

`README.md` (What ResolveAI is / is not, how an interaction flows, how grounding works, how humans stay in control, how to run
locally, how to evaluate, updated test counts), `docs/UI.md` (rewritten for the product IA), `docs/API.md` (three read-only
endpoints, `estimated_cost_usd`), `docs/ARCHITECTURE.md` (operator console section), `docs/DEMO.md` (new names, pointer to the
product demo), `docs/PRODUCTION_READINESS.md` (frontend rows, new "Product surfaces" PARTIAL item), `docs/INTERVIEW_NOTES.md`
(questions 25–27). `artifacts/product/PRODUCT_DEMO.md`: the ten-minute demo.

## 2. Files

**Added:**
- `resolveai/api/product.py`
- `scripts/evaluation/release_by_intent.py`, `b_capture_console_fixtures.py`, `c_verify_product.py`
- `tests/test_product_api.py`
- `frontend/app/agents/page.tsx`, `frontend/app/settings/page.tsx`
- `frontend/components/conversation/conversation-list.tsx`, `decision/decision-explanation.tsx`, `evaluation/release.tsx`,
  `settings/browser-storage.tsx`, `shell/principle.tsx`, `trace/trace-summary.tsx`
- `frontend/lib/explain.ts`
- `frontend/tests/product.test.tsx`, `frontend/tests/fixtures/{evaluation_release,agent_profile,knowledge_summary}.json`
- `artifacts/product/`: `product_start_snapshot.json`, `release_by_intent.json`, `smoke/`, verification reports, this report,
  `PRODUCT_DEMO.md`

**Modified:**
- `resolveai/api/routes.py`, `schemas.py`, `service.py`; `resolveai/policy/escalation.py` (list only)
- `frontend/app/api/v1/[...path]/route.ts`, `app/page.tsx`, `app/conversations/[traceId]/page.tsx`, `app/evaluation/page.tsx`,
  `app/knowledge/page.tsx`, `app/simulate/page.tsx`, `app/traces/page.tsx`, `app/traces/[traceId]/page.tsx`, `app/trust/page.tsx`
- `frontend/components/conversation/{workspace,conversation-detail}.tsx`, `decision/decision-details.tsx`,
  `evidence/evidence-panel.tsx`, `handoff/{handoff-queue,handoff-packet,handoff-detail}.tsx`, `shell/{nav.ts,sidebar,topbar}.tsx`,
  `simulate/simulator.tsx`, `trace/trace-decision.tsx`, `trust/trust-controls.tsx`
- `frontend/lib/{labels,rows,errors,handoff-summary}.ts`, `lib/api/{client,types}.ts`, regenerated `lib/api/openapi.json` and
  `schema.d.ts`
- `frontend/tests/{fixtures.ts,decision,evaluation,simulator,trace}.test.tsx`, `frontend/scripts/smoke.mjs`
- the docs listed above

**Not touched:** `data/`, `artifacts/final/`, every earlier `artifacts/*` folder, `resolveai/models/`, the frozen gate, rerank and
second-opinion configuration, and the agent's decision logic.

## 3. Tests

| Check | Result |
|---|---|
| Backend `python -m pytest -q` | 318 passed, 1 skipped, 0 failed (243 s); includes `tests/test_product_api.py` (7 tests: rule order, cost field, release view served as stored and PII-free, 401 on all three endpoints, 503 while loading, profile without secrets, knowledge summary without text) |
| Backend `ruff check` (changed and new files) | clean |
| Frontend `npm run lint` | 0 problems |
| Frontend `npm run typecheck` | clean |
| Frontend `npm test` | 109 of 109 in 14 files (new `product.test.tsx`: explanation headings and fields, trace explanation, evidence split and insufficient notice, queue mapping and filters, PII scrub of the copied summary, ten trust controls and honest statuses, IA and titles, trace summary, live metrics, release scorecard intervals and dataset labels; curated simulator path) |
| Frontend `npm run build` | succeeds; routes include `/agents` and `/settings` |

## 4. Security checks

- **No secrets to the browser.** Tokens are attached only by the console server; the proxy allowlist forwards only API endpoints
  and never a browser `Authorization` header. Settings renders credential presence only; the smoke asserts no token value in
  the page.
- **Smoke logs.** The API log, both console logs, the three smoke logs and the three smoke reports contain the generated API
  token 0 times and the model key 0 times (checked in memory, values never printed).
- **Endpoints.** The three new endpoints answer 401 without a token and 200 with one on the live auth-enabled server; tests
  assert no `api_key`, base URL, absolute path or model key in the profile, and no knowledge-base text in the summary.
- **PII.** Served example messages are redacted again and truncated; the copied handoff summary is scrubbed again in the browser;
  traces still store no customer text.
- **Errors.** Every error state shows code, status and correlation ids, never a stack trace.

## 5. Integrity and reproducibility

`python scripts/verification/verify_product_pass.py` (346 s; `artifacts/product/verification.json`), exit code 0:

| Check | Result |
|---|---|
| Golden set | verified on load: 197 rows, sha256 `33f4f333ccf10de7f628e57b5567a7930852cdf5b6d4bba872555b96b2bec3a9`, unchanged |
| Frozen artifacts vs `product_start_snapshot.json` | 413 files checked (data/, every artifacts/ folder **including artifacts/final/**, frozen models and configs): 0 changed, 0 missing, 0 new files in frozen locations |
| Phase 7 hash snapshot | 115 files: 0 changed, 0 missing; golden matches its freeze manifest |
| Cached evaluation | `scripts/evaluate.py --cached` regenerated all 11 Phase 6 result files, all byte-identical (333 s, no model calls) |
| Security scan | passed: 0 findings over 747 committable files (81.5 MB); `.env` not committable; 0 of 763 trace records contain unredacted PII |

- **Size.** The committable size rose from 54.4 MB at release to 81.5 MB. About 26 MB was the 62 full-page smoke screenshots of this
  pass; the final product hardening replaced them with its own set (`artifacts/product/hardening/smoke/screenshots/`) and removed
  these. The JSON smoke reports above are kept.
- **Mutable-change list.** The product snapshot hashed only frozen files, so the report's "mutable changes" section lists every
  code and doc file as added; section 2 above is the actual change list.
- **No new golden run.** The golden set was not run again; every release number shown in the console comes from the committed
  release artifacts.

## 6. UI checks

Browser smoke with Microsoft Edge and axe-core against the auth-enabled API and the production build
(`artifacts/product/smoke/`):

| Mode | Result |
|---|---|
| Full (console with server token) | 40 route visits including `/agents` and `/settings`, 7 of 7 scenarios (A, B, C, D, E, G, custom billing) with the expected decisions, 12 of 12 interactions (conversation filter, evidence expand, trace stage expand, explanation heading, evidence used vs retrieved, conversation list, handoff Security filter, copy handoff summary, no token in Settings, trace-id search, skip link, mobile drawer), 0 axe WCAG 2.1 A/AA violations, 0 pages with horizontal overflow at 1440, 1180, 834 and 390 px. One console error: the deliberate 404 page. |
| Unauthorized (console without token) | 5 routes (`/`, `/traces`, `/simulate`, `/agents`, `/knowledge`) show "Not authorized"; 0 failures, 0 axe violations |
| API down | 7 routes (`/`, `/traces`, `/evaluation`, `/simulate`, `/agents`, `/settings`, `/trust`) show "ResolveAI API unavailable"; sidebar shows the API as unavailable; 0 failures, 0 axe violations. Console errors are the expected 502s from the stopped API. |

The scenario runs took 0.4–1.1 s because model responses were served from the local response cache; they demonstrate the UI
paths, not live latency (live latency is in the Evaluation Center's performance profile).

## 7. Known limitations

- **Evaluation is unchanged and small.** 197 golden conversations, 37 escalation positives, 12 automatic replies; human judge
  validation 0 of 50; second-annotator risk labels from an AI annotator.
- **Over-escalation remains.** 75 unnecessary handoffs; the product now shows it prominently rather than fixing it.
- **Live metrics are local.** Up to 200 traces from one reference process; not production traffic.
- **Per-browser text.** Conversation text reappears only in the browser that ran it (traces store none).
- **Display groupings.** Handoff queues and severities are fixed groupings of reason codes, not triage.
- **Knowledge gaps are a rule on small counts.** A signal to inspect, not a recommendation.
- **Model-failure scenario.** Not reproducible through a live API with a working model; the CLI demo simulates it.
- **Configuration hashes.** The Agents page shows the runtime config hash and the evaluation run's recorded hash; they are
  computed over different inputs, so only the listed field differences should be compared.
- **Accessibility.** Automated axe checks only; no manual screen-reader session.

## 8. Remaining production gaps

Unchanged by this work and listed in `docs/PRODUCTION_READINESS.md` (52 items: 20 READY, 21 PARTIAL, 11 NOT READY):
- no operator login, roles or per-operator audit;
- no TLS;
- static shared tokens without rotation;
- process-local rate limits;
- file-based traces without retention;
- no metrics or alerting;
- no dependency vulnerability scanning;
- no load test;
- customer-facing template wording that asserts facts;
- no runbooks;
- no human validation of the judge.

The console is a reference product workspace, not a deployed service.
