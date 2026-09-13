# Phase 8 report: ResolveAI operator console

Phase 8 adds a Next.js console on top of the Phase 7 FastAPI service. Its purpose is to **make the agent's trust decision
visible**. For each conversation the console shows:
- what the customer said and what ResolveAI understood;
- intent, evidence and whether it was sufficient;
- risk, the policy decision, and the generated response with its verification;
- why the case was auto-handled, clarified or escalated;
- the handoff packet and the trace.

It is a reference implementation run locally: there is no Docker, no authentication and no deployment. Phases 1–7 are
unchanged apart from two additive API extensions (section 4).

## 1. UI architecture

```text
browser ──> Next.js 16 console (frontend/)
             ├─ server components ──(RESOLVEAI_API_URL)──> FastAPI /api/v1/*     pages: overview, lists, trace, evaluation, trust
             ├─ client components ──> /api/v1/* forwarder ──> FastAPI            simulator, filters, expanders, copy, agent status
             └─ localStorage: last 50 full /resolve results from this browser    (traces never store customer text)
```

- **No agent logic in the frontend.** Decisions, packets, evidence and metrics all come from the API. `lib/labels.ts` only names
  codes. The handoff severity and queue are a labelled display grouping of reason codes.
- **Stack:** Next.js 16.3.4 (App Router, Turbopack), React 19.3, TypeScript 5.9 (strict), Tailwind CSS 4, and lucide-react for icons.
  Those are the only runtime dependencies besides React. Development tooling is ESLint 9 (next config), Vitest 5 with jsdom and
  Testing Library, openapi-typescript, playwright-core (drives the installed Edge), and axe-core.
- **State:** React state, URL state (conversation filters and search), server fetching with `cache: "no-store"`, and one
  `useSyncExternalStore` localStorage store. There is no global state library.

## 2. Routes

| Route | Content |
|---|---|
| `/` | Live operations KPIs (trace store) and evaluation KPIs (frozen golden set), labelled separately; recent decisions; trust controls |
| `/simulate` | Try ResolveAI: message plus optional earlier turns and channel → `POST /resolve`; demo scenario cards from `GET /demo/scenarios`, expected vs actual |
| `/conversations` | All processed conversations; filters All / Auto handled / Clarification / Human handoff / High risk / Insufficient evidence; search |
| `/conversations/[traceId]` | Three-column workspace, or a view reconstructed from the trace for conversations not run in this browser |
| `/handoffs` | Handoff Center: severity, issue, intent, reason, evidence, created, trace; queues Security / Billing / Account / Hardware / Insufficient evidence / Other |
| `/handoffs/[traceId]` | Handoff packet with Copy handoff summary |
| `/knowledge` | "Historical customer-support corpus": corpus facts from `/ready` and `/config`, and every case retrieved in this browser's runs |
| `/traces`, `/traces/[traceId]` | Audit trail; stage timeline Request → … → Trace complete; decision data; trace record |
| `/evaluation` | Headline, intent, escalation, autonomy, retrieval, groundedness, latency and cost, baselines and ablations, uncertainty, misleading headline |
| `/trust` | Nine implementation controls, with live versions and limits, and where each is enforced |
| `not-found`, `error`, `loading` | 404 page, render-error boundary with retry, loading skeleton |
| `/api/v1/[...path]` | Same-origin forwarder, restricted to the API's own endpoints |

## 3. Design system

- **Tokens** in `app/globals.css` (`@theme`):
  - surfaces: canvas, surface, subtle, line, line-strong;
  - three ink levels;
  - one teal brand ramp;
  - four status tones, each with background and line colours.
- The system font stack means no font download.
- **Primitives** (`components/ui`): Badge, ActionBadge, EvidenceLevelBadge, SeverityBadge, BandBadge, Card, PageHeader,
  KeyValues (container-query stacking), Mono, Notice, Button and ButtonLink, CopyButton, Kpi and KpiGrid, DistributionBar,
  ConfidenceMeter, DataTable (focusable scroll region), FilterChips, EmptyState, ErrorState, Spinner and Markdown (safe renderer
  for the evaluation's own markdown).
- **Decision tones:** auto handle green, clarification amber, handoff blue, high risk red. Every status carries an icon and text.
- **Wording:** "Evidence-gated", "Grounded", "Auditable" and "Human-in-the-loop". The UI never says "fully autonomous",
  "100% accurate" or "hallucination-free". Responses are labelled "Generated response", "Simulated response" or
  "No customer response: human handoff".
- The brand is "ResolveAI — AI Support Operations", an original mark with no third-party branding.

## 4. API integration

- **Inspected first:** README, the Phase 7 report, `docs/API.md`, `api/schemas.py`, the demo scenarios, the trace, agent result,
  evidence and handoff schemas, the evaluation summary route, and the real responses in `artifacts/phase7/api_examples.json`.
- **Types:** `scripts/phase8/export_openapi.py` exports the service's OpenAPI document without loading the agent, and
  `npm run gen:api` generates `lib/api/schema.d.ts`. Response types are made fully present (FastAPI serializes defaulted fields),
  and `tests/api-contract.test.ts` checks this against captured responses. The dictionary endpoints (evaluation summary, config,
  demo scenarios) have hand-written types checked against captured JSON.
- **Client:** `lib/api/client.ts` is the only client. Errors become `ApiError` with the API's `error_code`, `message`,
  `request_id` and `trace_id`, plus console codes `api_unavailable`, `timeout`, `cancelled` and `invalid_response`. `/resolve`
  bodies are structurally validated before rendering.
- **Forwarder:** `app/api/v1/[...path]/route.ts` passes status, body and correlation headers through unchanged. An unreachable
  API answers 502 `api_unavailable` and a timeout answers 504 `timeout`, both in the API's error shape.
- **Additive backend changes** (the data gaps found during inspection; no existing field changed):
  1. `TraceSummary` (list items) gained `intent`, `intent_confidence`, `confidence_band`, `evidence_level`,
     `evidence_sufficient`, `risk_flags`, `rule`, `policy_version`, `channel` and `llm_calls`. They are read from events every
     trace already records (`summarize_trace` in `api/service.py`).
  2. `/evaluation/summary` additionally returns `agreement`, `retrieval`, `reply_quality`, `misleading_headline_md`,
     `statistical_uncertainty_md` and `provenance`. These are read from the frozen artifacts as stored.

  There are two new backend tests, and `docs/API.md` is updated.
- **Fixtures:** `scripts/phase8/capture_fixtures.py` captured real responses from the in-process API with the configured model:
  scenarios A–E and G, F through the demo's simulated outage provider, two traces, the trace list, the evaluation summary,
  config, ready, health and two error bodies. One fixture uses a scripted verifier that rejects the draft, to exercise "Draft
  blocked by verification", and its file name says so.

## 5. Trust UX

- **Decision banner:** AUTO HANDLE, CLARIFICATION REQUIRED or HUMAN HANDOFF, with the human-readable reason, the agent's own "why",
  the reason code, policy rule and policy version.
- **Why this decision:** what happened, why, evidence basis and next step, from the API's `outcome`.
- **Inputs side by side:**
  - Intent: label, calibrated confidence meter, band, alternatives, second opinion.
  - Evidence sufficiency: a four-step scale plus an explanation and gate finding, stated to be "not the model's confidence".
  - Risk: flags with source, red for hard blocks.
  - Policy: "the model never decides whether to escalate".
- **Output gate:** all nine checks with met or not met.
- **Trust controls page:** PII protection, evidence gate, grounding verification, policy enforcement, human handoff,
  traceability, model fallback, prompt-injection defense, and input limits. Each is described as an implementation control
  with its enforcing module, and the page says these are not certifications.
- **Clarification view:** why it is unsafe to resolve now, missing information, what was already provided, the suggested
  question, intent hypothesis and evidence.

## 6. Evidence UX

- **Case card:** rank and case id, date and thread, the historical customer message and support reply, relevance, resolution
  relevance and outcome, with a "Cited in reply" badge.
- **"Why selected"** expander: rank and index, similarity, same or different issue category, whether the reply states a
  resolution, temporal eligibility, same-customer exclusion, retrieval method, rerank score and quality.
- **"View source"** shows the dataset, brand, source row, thread, preprocessing version and KB hash. Embeddings are never shown.
- Resolution patterns (clusters) appear above the cases, with a truthful message when there is no pattern or no evidence.
- **Knowledge explorer:** 17,875 indexed threads from `/ready`, plus every retrieved case with search, a "states a resolution"
  filter and links to the conversations that retrieved it.

## 7. Handoff UX

- **Handoff Center:** a queue sorted by severity, with queue filters and counts.
- **Packet:** severity and queue (labelled as a console grouping), recommended next action, redacted customer issue, why, intent
  and alternatives, risk flags, evidence and summary, unresolved questions, suggested opening, historical examples ("not
  verified as a solution for this customer"), and the blocked draft if any.
- **Copy handoff summary** builds plain text from the packet only; the smoke test verified the clipboard content.
- **Response panel for a handoff:** "No customer response: human handoff", with the holding notice labelled as simulated.
  "Draft blocked by verification" shows the rejected draft and the verifier's issues.

## 8. Trace UX

- **Timeline:** Request → PII redaction → Context → Intent → Retrieval → Evidence gate → Risk → Policy → Draft → Verification →
  Decision → Trace complete.
- **Each stage:** status (Completed, Skipped, Fallback, Flagged, Error or Not recorded, always with an icon and text), duration
  from the trace's per-stage latency, and start time.
- **Clicking a stage** shows every event: name, component, status, latency, timestamp and the recorded safe metadata. Expand
  all is available.
- **Trace record:** ids, times, latency, versions, prompt versions, config hash, channel and locale, and model usage.
- **Reconstructed views:** a conversation or handoff not run in this browser is rebuilt from the trace with an explicit notice,
  because traces never store customer or evidence text.

## 9. Evaluation UX

- **Warning and link:** "Evaluation results are based on a frozen 197-example golden set." appears on the Overview and the
  Evaluation page, along with the golden sha256 and source provenance and a "Read the misleading headline analysis" link
  (anchor `#misleading-headline`).
- **Headline KPIs** with 95% bootstrap CIs: intent macro-F1 0.854; escalation recall 94.6%; safe auto-handle rate 4.6%; unsafe
  autonomous responses 0; judge groundedness 4.28/5; judge hallucination rate 21.6%.
- **Comparisons:**
  - intent and escalation bars across baselines and ablations, with CI whiskers for ResolveAI;
  - the precision/F1 table;
  - autonomy mix plus a safe/unsafe/grounded table with the metric definitions;
  - retrieval same-resolution recall and resolution-bearing rank tables;
  - the gate distribution on golden (166 / 24 / 7) and the gate precision estimate, labelled "AI annotated";
  - the retrieval limitations.
- **Judge section:** judge scores per system with CIs, human agreement **Pending human ratings (0 of 50)**, the second-family
  judge kappa labelled "judge versus judge", and pairwise win/tie/loss.
- **Latency and cost:** a table with the cached-run caveat.
- **Baselines and ablations:** a table.
- **Text sections:** the statistical-uncertainty and misleading-headline markdown are rendered unedited.
- **Overview grounded rate:** "5 of 9 automatic replies were verified and cited evidence; the others were fixed templates". This
  follows the evaluation's own definition of grounded (`evaluation/metrics.py`).
- Nothing is recomputed, and no evaluation artifact was modified (section 15).

## 10. Simulation

- **Try ResolveAI:** a customer message (with a length counter against the API limit), optional earlier turns (customer or
  support) and an optional channel, then **Analyze**, which calls `POST /api/v1/resolve`. The full result renders in the
  workspace, is saved in this browser and links to the workspace and the trace.
- **Labelling:** a "Simulation" notice at the top says nothing is sent to any customer or channel and that results stay in this
  browser. It shows the model name from `/config`.
- **Demo cards:** all seven scenarios come from `GET /api/v1/demo/scenarios`, with the model requirement, customer text and the
  declared expectation. After a run, an "Expected versus actual" row compares the API result with the scenario's declared
  expectations (display only). Scenario F explains that the live API cannot reproduce a model outage while a model is configured.
- **Honest loading:** "Running ResolveAI…" with an elapsed timer, a cancel button, and the sentence "this indicator does not
  track stage progress". The result area scrolls into view when a run starts.
- **Errors:** validation before the call; API unavailable, timeout, rate limited, input too large (with details), invalid
  response, and cancel back to idle.

## 11. Accessibility

- Skip link (verified as the first tab stop), landmarks, one `h1` per page, headed sections, `th scope`, labelled inputs.
- Buttons use stable accessible names with `aria-expanded` and `aria-controls` (evidence, trace stages), `aria-pressed` (filters),
  `aria-current` (navigation, evidence scale), `aria-live` (agent status, copy result, character counter) and `role="alert"`
  (errors).
- Focusable scroll regions for wide tables; visible focus rings; the reduced-motion media query.
- Meters carry values; charts have text alternatives and printed numbers; no status is shown by colour alone.
- **axe-core (WCAG 2.1 A/AA) in Edge:** smoke run 1 found 2 issues (a prohibited `aria-label` on a div; a non-focusable scroll
  region), and both were fixed. Run 2 found 1 issue (contrast of the active-chip count), which was fixed. The final run is in
  section 14.

## 12. Responsive behavior

- **Desktop (1440 px):** the workspace has three columns (conversation · decision and response · evidence and trace).
- **Narrow desktop (1180 px) and tablet (834 px):** two columns led by the decision, or a single column. The sidebar becomes a
  drawer with a menu button; Escape closes it (verified).
- **Mobile (390 px):** a single column. Wide tables scroll inside their card, and the page body never scrolls horizontally.
- Container queries let key/value rows and the timeline adapt to their column rather than the viewport. This fixed label
  wrapping ("defaul t_auto") and timeline overlap found in the run 1 screenshots.
- The smoke test measured horizontal page overflow on every visited page at every size: **0 pages** with overflow in every
  run, including the final run and the API-down run.

## 13. Performance

- **Server components** render every page's data fetch on the server (one to three parallel API calls per page, no
  waterfalls). Client components are limited to interactive parts.
- **No repeated calls:** agent status polls `/ready` only while the agent is not ready; lists filter client-side over one fetch;
  the simulator fetches the trace once after a run.
- **Runtime dependencies:** next, react, react-dom and lucide-react (per-icon imports). Next 16 no longer prints bundle sizes,
  so none are reported.
- **Measured in the browser against the live API** (Edge, smoke run 1, cached model responses), from click to rendered result:
  scenario A 525 ms, B 1.5 s, C 1.1 s, D 4.2 s, E 3.6 s, G 1.5 s, and a new billing message 1.3 s. The first cold agent call
  after a restart took 67 s, dominated by first-time model and embedding warm-up in the agent, not the console.
- The overview's live median latency over the 7 traces was 947 ms.

## 14. Tests

| Suite | Result |
|---|---|
| Frontend unit and component (Vitest, 13 files) | **89 passed, 0 failed** (`artifacts/phase8/frontend_junit.xml`) |
| Backend (pytest, full suite) | **206 passed, 1 skipped** (Phase 7 ended at 204 + 1; +2 new API tests) |
| Lint (ESLint) / typecheck (tsc) | **exit 0, 0 errors, 0 warnings** / **exit 0** |
| Ruff (Phase 8 Python and API changes) | All checks passed |
| Browser smoke, full (`npm run smoke`, Edge 152 + axe, live API) | **Final run: 29 route visits all as expected; 7/7 live runs matched their declared expectations; 7/7 interactions passed; 0 axe violations on 21 audited pages; 0 pages with horizontal overflow; 0 unexpected console errors** (only the intentional 404). Run 1 (`smoke_results.run1_empty_store.json`) additionally verified the empty-store states. |
| Browser smoke, API down (backend stopped) | **4/4 pages show "ResolveAI API unavailable" with the start command; sidebar shows "API unavailable"; 0 axe violations** (`smoke_api_down.json`) |

Live runs in the final smoke (click to rendered result, cached model responses):
- A: auto handle, 569 ms
- B: clarification, 290 ms
- C: security handoff, 465 ms
- D: clarification (insufficient evidence), 329 ms
- E: prompt-injection handoff, 424 ms
- G: repeat-contact handoff, 443 ms
- a new billing message: billing handoff, 350 ms

Frontend tests cover:
- `api-client`: success, correlation headers, POST body, API error bodies, 413 details, unreachable, timeout, cancel, non-JSON,
  readiness 503, `load()`.
- `api-contract`: every captured response is complete; all decision paths exist; validation rejects bad bodies; enriched
  trace summaries; every trace event maps to a stage; traces never contain customer text; scenario and evaluation shapes.
- `decision`: banners for all three actions; the four-step sufficiency scale versus the confidence meter; output-gate text
  labels; intent, risk and policy inputs.
- `evidence`: card content; expand and collapse with `aria-expanded`; why-selected reasons; source without embeddings; cited
  badges; clusters; empty evidence.
- `response`: grounded and verified reply with citation links and the simulated label; clarification; handoff with no
  response; draft blocked by verification.
- `handoff`: severity, queue, next action and questions; summary text; blocked draft in the summary; clipboard copy.
- `clarification`: why, missing, already provided, question; nothing rendered without a packet.
- `trace`: stage grouping and order; skipped and fallback statuses; durations; click to reveal metadata; expand all; trace-only
  reconstruction.
- `evaluation`: frozen-golden warning; misleading-headline link and section; CIs; all sections; human study pending;
  unavailable state; markdown numbering.
- `states`: explanations for API unavailable, timeout, invalid response, trace not found, invalid trace id, evaluation
  unavailable, agent loading and input too large; the unknown-code fallback; codes and ids shown; model outage shown as a
  handoff, not an error; empty state.
- `simulator`: simulation labelling; validation; honest loading, then result and storage; scenario run with expected versus
  actual; API unavailable; invalid response not rendered or stored.
- `rows-store`: store cap, dedupe and corruption handling; merge without invented previews; filters and search; live metrics;
  version sync.
- `proxy-route`: forwarding, pass-through, disallowed paths, API down.

## 15. Build result and integrity

- `npm run build`: **success**. Next.js 16.3.4 (Turbopack) compiled with no TypeScript errors, 13 app routes plus `/icon.svg`
  and the forwarder, all server-rendered on demand.
- `npm run lint` and `npm run typecheck`: exit 0, 0 warnings.
- Integrity (`scripts/phase8/verify_integrity.py`, report `artifacts/phase8/integrity.json`): **passed**.
  - The Phase 7 hash snapshot's 115 files (golden set, evaluation artifacts, earlier phase artifacts, human packet, frozen
    retrieval and classifier configuration) are unchanged.
  - The golden sha256 `33f4f333…` matches the freeze manifest.
  - **No file** in `data/golden`, `data/human_eval`, `data/processed`, `artifacts/evaluation`, `artifacts/phase7`,
    `artifacts/{resolution,agent,intelligence,retrieval}`, `resolveai/retrieval` or `resolveai/models` was modified after
    Phase 8 started.
  - The Phase 7 scripts ran unchanged, with their report paths redirected to `artifacts/phase8/`, so no Phase 7 report was
    overwritten.
- Security scan over every committable file, including `frontend/` (report `artifacts/phase8/security_scan.json`): **passed**.
  - 516 committable files (34.1 MB), `.env` not committable.
  - No real secret value or LLM endpoint address in any file.
  - 738 trace records scanned, 0 with unredacted PII, 0 findings.

## 16. Files changed

**Backend (additive):**
- `resolveai/api/schemas.py`: TraceSummary fields.
- `resolveai/api/service.py`: `summarize_trace`.
- `resolveai/api/routes.py`: evaluation summary keys.
- `tests/test_api.py`: 2 tests.

**Scripts:**
- `scripts/phase8/export_openapi.py`
- `scripts/phase8/capture_fixtures.py`
- `scripts/phase8/verify_integrity.py`

**Frontend (new, `frontend/`):**
- Configuration: `package.json`, `package-lock.json`, `tsconfig.json`, `next.config.ts`, `postcss.config.mjs`,
  `eslint.config.mjs`, `vitest.config.mts`, `.gitignore`, `.env.example`.
- `app/`: `layout.tsx`, `globals.css`, `icon.svg`, `page.tsx`, `loading.tsx`, `error.tsx`, `not-found.tsx`, and the routes
  `simulate`, `conversations`, `conversations/[traceId]`, `handoffs`, `handoffs/[traceId]`, `knowledge`, `traces`,
  `traces/[traceId]`, `evaluation`, `trust` and `api/v1/[...path]/route.ts`.
- `components/`:
  - `ui/`: badge, status, card, button, copy-button, kpi, meter, markdown, states, table.
  - `shell/`: app-shell, sidebar, topbar, agent-status, nav, runtime.
  - `decision/`: decision-banner, decision-details, evidence-sufficiency, intent-summary, output-gate, risk-flags.
  - `evidence/`: evidence-card, evidence-panel.
  - `response/`: response-panel.
  - `handoff/`: handoff-packet, handoff-queue, handoff-detail.
  - `clarification/`: clarification-view.
  - `trace/`: trace-timeline, trace-decision.
  - `conversation/`: conversation-thread, conversations-table, conversation-detail, workspace.
  - `simulate/`: simulator.
  - `knowledge/`: knowledge-explorer.
  - `evaluation/`: bars.
  - `overview/`: recent-decisions.
  - `trust/`: trust-controls.
- `lib/`:
  - `api/`: `client.ts`, `types.ts`, `validate.ts`, generated `schema.d.ts`, `openapi.json`.
  - `labels.ts`, `format.ts`, `errors.ts`, `results-store.ts`, `rows.ts`, `trace.ts`, `scenarios.ts`, `handoff-summary.ts`,
    `use-hydrated.ts`, `version.ts`.
- `tests/`: 13 test files, `setup.ts`, `fixtures.ts`, and 18 captured fixture JSON files.
- `scripts/smoke.mjs`.

**Docs:**
- `README.md`: status, frontend and backend setup, environment, running both, demo, routes, architecture, repository map. It
  also fixes the tripled `scripts/phase7` and `phase7/` lines.
- `docs/UI.md`: new.
- `docs/API.md`: trace list fields, evaluation summary keys.
- `docs/DECISIONS.md`: #81–87.

**Artifacts:**
- `artifacts/phase8/PHASE8_REPORT.md`
- `smoke_results.json` (final run), `smoke_results.run1_empty_store.json`, `smoke_api_down.json`
- `frontend_junit.xml`, `integrity.json`, `security_scan.json`
- `screenshots/*.png`

**Not modified:** the golden set, `data/human_eval`, `artifacts/evaluation/*`, Phase 1–7 artifacts, agent, policy, gate,
retrieval and prompts. Runtime traces under `traces/` are gitignored. Nothing was committed.

## 17. Screenshots

All screenshots are in `artifacts/phase8/screenshots/`, captured by `scripts/smoke.mjs` in headless Edge against the running
stack. Full-page captures flatten sticky bars so they are not painted mid-page.

Visual inspection checked:
- empty states;
- workspace A (auto handle, including expanded evidence and policy stage);
- D (clarification);
- handoff C (packet);
- trace-only C;
- overview with data;
- knowledge explorer;
- evaluation;
- the loading state;
- tablet and mobile.

Issues found in those images and fixed:
- sidebar background ending at viewport height;
- the simulator's single long scenario column;
- policy key/value words broken mid-token in narrow cards;
- timeline label and status overlap in the 380–400 px column;
- the running indicator rendering below the fold.

| Screenshot | Shows |
|---|---|
| `empty-overview.png`, `empty-conversations.png`, `empty-knowledge.png` | Truthful empty states before any conversation existed (run 1, empty trace store) |
| `simulate-empty.png`, `simulate-running.png` | Scenario cards; honest loading state |
| `simulate-result-A-auto-handle.png` | AUTO HANDLE: grounded, verified simulated response with citations |
| `simulate-result-C-security-handoff.png` | HUMAN HANDOFF: security, packet, no customer response |
| `simulate-result-D-clarification.png` | CLARIFICATION REQUIRED: insufficient evidence, slot-aware question |
| `simulate-result-custom-billing.png` | New message through the live API → billing handoff |
| `overview.png` | Live versus evaluation KPIs, recent decisions, trust controls |
| `conversations.png`, `conversations-filter-handoff.png` | List with filters (URL state) |
| `conversation-A-workspace.png`, `conversation-A-workspace-expanded.png` | Three-column workspace; evidence "why selected" and policy stage expanded |
| `conversation-D-clarification.png` | Clarification workspace |
| `conversation-C-trace-only.png` | Reconstructed-from-trace view in a fresh browser |
| `handoffs.png`, `handoff-C-detail.png` | Handoff Center; handoff packet |
| `knowledge.png` | Historical customer-support corpus and retrieved cases |
| `traces.png`, `trace-A-timeline.png`, `trace-E-injection.png` | Audit trail; timelines (auto; prompt-injection handoff with flagged risk stage) |
| `evaluation.png`, `evaluation-misleading-headline.png` | Evaluation page; misleading headline section |
| `trust.png` | Trust controls |
| `error-unknown-trace.png`, `error-invalid-trace-id.png`, `error-404.png` | Error states |
| `tablet-*.png`, `narrow-*.png`, `mobile-*.png`, `mobile-navigation-open.png` | Responsive layouts and the navigation drawer |
| `api-down-*.png` | API unavailable states with the backend stopped |

## 18. Known limitations

- There is no authentication or roles; the profile avatar is a placeholder. Everything is single-process and local.
- Live operations KPIs cover only the latest 200 traces of a local reference environment, not production traffic. Unsafe
  autonomous responses cannot be measured live (no ground truth), and the tile says so.
- Conversation and evidence text is available only for runs in the same browser (localStorage, last 50). Other traces show a
  reconstructed decision view.
- The API has no corpus-browsing endpoint, so the knowledge explorer shows retrieved cases only.
- Scenario F (model outage) cannot be reproduced through the live API while a model is configured. The console shows its note,
  and `python -m resolveai demo` simulates it.
- The live risk model's over-escalation (Phase 7 decision #80) is visible in the UI, for example scenario G ("still not
  working") becomes a repeat-contact handoff. It is shown, not hidden or patched.
- Handoff severity and queue are a display grouping of reason codes, not a triage model.
- The judge is still not human-validated (`data/human_eval/human_scoring_packet.csv` unfilled). The UI says "Pending human
  ratings" everywhere.
- The smoke test drives the installed Edge (playwright-core, `channel: "msedge"`); on a machine without Edge, set another
  channel.
- There is no automated visual-regression baseline; screenshots are inspected manually. English only.

## 19. Exact Phase 9 starting point

**State**
- The backend `resolveai` 0.7.0 API (policy-v3.1, gate-v3, pipeline-v5.1, glm-5.2) serves the console `frontend/` 0.8.0.
- Checks: backend 206 passed, 1 skipped; frontend lint, typecheck, tests, build and browser smoke as in section 14.
- Nothing has been committed; the user commits.

**Run**
- `python -m resolveai serve`
- `cd frontend && npm install && npm run build && npm start` (or `npm run dev`)
- Open http://localhost:3000 → Try ResolveAI.

**Verify**
- `python -m pytest -q`
- `cd frontend && npm run lint && npm run typecheck && npm test && npm run build`
- With both servers running: `npm run smoke`
- `python scripts/phase8/verify_integrity.py`

**Open items carried forward (not started)**
- Human judge ratings are still PENDING.
- The risk-model over-escalation needs a dev re-evaluation before any change.
- No authentication.
- No persistence of conversation text beyond the browser.

Phase 9 work begins only with its own mandate. No Phase 9 work was started in Phase 8.
