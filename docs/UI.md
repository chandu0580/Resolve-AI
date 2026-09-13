# ResolveAI console

The console (`frontend/`, version 1.0.0) is a Next.js operator workspace for the ResolveAI API. It has one job: **make every
decision the agent takes visible and explainable**, and keep people in control of the exceptions. The principle is shown in the
shell and on the Overview:

> **Model proposes · Evidence grounds · Policy decides · Verifier checks · Humans control exceptions**

It contains **no agent logic**. Every decision, packet, metric and piece of evidence on screen was produced by the FastAPI service
or read from committed release artifacts. The console names the codes, lays out the data and shows what a customer would receive.
It never sends anything to a customer.

## Running it

```bash
python -m resolveai serve                     # API on http://127.0.0.1:8000
cd frontend && npm ci
npm run dev                                   # http://localhost:3000   (production: npm run build && npm start)
```

| Variable | Default | Used by |
|---|---|---|
| `RESOLVEAI_API_URL` | `http://127.0.0.1:8000` | server components and the `/api/v1/*` forwarder (server side only) |
| `RESOLVEAI_PROXY_TIMEOUT_MS` | `190000` | forwarder timeout for `/resolve` (live model calls can take tens of seconds) |
| `RESOLVEAI_API_TOKEN` | empty | required when the API requires authentication. Attached server side; never sent to the browser, never rendered (Settings shows only whether it is set). A browser-supplied `Authorization` header is never forwarded. |

Checks:
- `npm run lint`, `npm run typecheck`, `npm test` (Vitest + Testing Library) and `npm run build`.
- `npm run smoke` runs `frontend/scripts/smoke.mjs` against a running stack with the installed Microsoft Edge and axe-core. `SMOKE_OUT=<dir>`
  chooses where results and screenshots go; `SMOKE_MODE=api-down` runs with the API stopped; `SMOKE_MODE=unauthorized` runs a
  console that has no token.
- `npm run gen:api` regenerates `lib/api/schema.d.ts` from the API's OpenAPI document.

## Information architecture

| Group | Page | Route | What it is for | Data |
|---|---|---|---|---|
| Workspace | **Overview** | `/` | Principle strip; honest warnings computed from served data (unnecessary handoffs in the frozen evaluation, human validation pending, unsafe autonomous replies observed or not, failed executions, agent not ready, model off, auth off); **LIVE OPERATIONAL DATA** KPIs (volume, auto-handled, clarification, handoff, evidence sufficiency, average and p50/p95 latency, model calls, estimated cost, failed requests); **FROZEN GOLDEN SET** KPIs with intervals; recent conversations, handoffs and failures; system health; trust status | `/traces`, `/evaluation/release`, `/config`, `/ready` |
| Workspace | **Conversations** | `/conversations`, `/conversations/[traceId]` | List with filters and search in the URL. The workspace has three panels: LEFT conversation list · CENTER conversation timeline (thread, response, pipeline timeline) · RIGHT decision, explanation, handoff packet, evidence, intent/risk/policy/output gate and run facts | `/traces`, `/traces/{id}`, results stored in this browser |
| Operate | **Handoff Center** | `/handoffs`, `/handoffs/[traceId]` | Queue sorted by severity with filters All, Safety, Security, Billing, Account, Technical, Insufficient evidence, Model failure, Other (fixed grouping of reason codes, listed next to the filter); issue, reason, intent, risk, evidence, next action; the packet with evidence found and missing, unresolved questions, the rejected draft and **Copy handoff summary** | `/traces?action=HUMAN_HANDOFF` |
| AI | **Agent Playground** | `/simulate` | A curated seven-step demo path in the order of `docs/DEMO.md` (safe grounded troubleshooting, ambiguous request, risky request with human handoff, insufficient evidence, sensitive or private information, prompt injection, model failure), all API demo scenarios, and a free-form form. After a run: the recorded agent stages, then the full workspace | `/demo/scenarios`, `/resolve`, `/traces/{id}` |
| AI | **Knowledge** | `/knowledge` | Corpus statistics, evidence quality by issue category, provenance and leakage boundary; coverage and knowledge-gap candidates on the frozen golden set with the rule and underlying examples; live evidence coverage (labelled separately); cases retrieved in this browser | `/knowledge/summary`, `/evaluation/release`, `/traces` |
| AI | **Agent** | `/agents` | Read-only: agent status, model and versions, pipeline stages and who decides at each, allowed and never-allowed actions, risk configuration, ACTIVE configuration (agent, retrieval, evidence thresholds, rerank weights) next to the EVALUATION configuration with differences, and the ordered policy and handoff rules. No workflow editor. | `/agent/profile`, `/config` |
| Insights | **Evaluation** | `/evaluation` | Release scorecard with 95% intervals and paired differences against B2, B1 and Phase 9; failure modes; outcomes by intent; judge attribution; human validation status; dev experiments; latency and cost profile; limitations. Then the Phase 6 study (baselines, ablations, judge, uncertainty, misleading-headline analysis), labelled as the pre-release configuration | `/evaluation/release`, `/evaluation/summary` |
| Admin | **Audit Log** | `/traces`, `/traces/[traceId]` | Trace summary (what happened, why, how long, what failed, what evidence), the stage timeline Request → PII check → Context → Intent → Retrieval → Evidence gate → Risk → Policy → Draft → Verification → Final action → Trace complete (in execution order; each stage expands to its safe metadata), the explanation and the trace record | `/traces`, `/traces/{id}` |
| Insights | **Analytics** | `/analytics` | Operational analytics counted from this deployment's audit records only: outcome, intent, handoff-reason and evidence distributions, latency percentiles, model calls and estimated cost. Labelled LIVE OPERATIONAL DATA; empty state when nothing has run | `/traces` |
| Admin | **Trust & Safety** | `/trust` | Ten controls (PII, prompt injection, evidence requirement, policy enforcement, output verification, human handoff, audit traces, authentication, rate limiting and input limits, model-failure handling), each with STATUS in this environment, ENFORCED AT, WHAT IT PROTECTS AGAINST, code and tests; release verification results labelled as release artifacts | `/config`, `/evaluation/release` |
| Admin | **Settings** | `/settings` | Connection and authentication (token presence only), limits and budgets, model and traces, browser storage with a clear action, known limitations | `/config`, `/health`, console server environment |

Terminology is fixed across pages: **AUTO-HANDLED**, **CLARIFICATION**, **HUMAN HANDOFF**, **EVIDENCE**, **POLICY**,
**VERIFICATION**, **RISK**, **TRACE**. The console never says "bot response", "AI answer" or "agent output".

## "Why did ResolveAI do this?"

Every decision view carries an explanation with eight fields: **decision, reason, evidence, policy, risk, verification, what would
change it, next action**. "What would change it" is stated from the ordered policy rules (a console test keeps its rule order equal
to the one the API serves) and the output gate; it is never a prediction. Its heading depends on the action: *Why this response was allowed* (auto-handled), *Why the agent asked for more
information* (clarification), *Why a human was required* (handoff).

It is built by `lib/explain.ts` from structured data only: the API's outcome, the evidence gate's level and reason, the policy rule
and version, risk flags, the verification verdict and the output gate's checks. For a trace-only view it uses the recorded events
and says that evidence text is not stored. No model is ever asked to explain itself, and no chain-of-thought exists to show.

## Evidence first

- **Used versus retrieved.** EVIDENCE USED IN RESPONSE lists exactly the cases an automatic reply cites; RETRIEVED EVIDENCE lists
  the rest, with "Retrieved is not the same as trustworthy".
- **Insufficient evidence.** The panel opens with "ResolveAI did not find sufficient historical evidence to safely answer.", the
  level and the gate's reason, and says retrieved cases are context only.
- **Each case** shows its id and rank, date, the historical customer message and reply, similarity, whether the reply states a
  resolution, the outcome signal, *Why selected* (retrieval signals, issue category, temporal eligibility, same-customer
  exclusion) and *View source* (dataset, row, thread, preprocessing version, knowledge-base hash).
- **Sufficiency** is a four-step scale, drawn differently from intent confidence, so "STRONG evidence" is never read as "95% sure".

## Decisions, verification and handoffs

- **Banner.** AUTO-HANDLED (green), CLARIFICATION (amber) or HUMAN HANDOFF (blue), with the reason, reason code, policy rule and
  version. Status is never colour alone, and badges and banners use the same three labels.
- **Output gate.** All nine checks as met or not met; an automatic reply requires every one.
- **Verification.** "Grounded in N cases · Verified" with links to cited cases, or "Draft blocked by verification" with the
  verifier's issues. "Grounded" appears only when every citation is a retrieved case and the gate judged the evidence sufficient;
  otherwise an automatic reply would read "Grounding not confirmed".
- **Handoff packet.** Severity and queue (a display grouping, stated on the page), recommended next action, redacted issue,
  conversation summary, context (earlier turns), what ResolveAI tried (cases searched, whether a draft was attempted), why,
  intent and alternatives, risk flags, evidence found and evidence missing, unresolved questions, suggested opening, historical
  examples "not verified as a solution for this customer", and the rejected draft. **Copy handoff summary** builds plain text from
  the packet and scrubs e-mail, phone, card, order and long-id patterns again before it reaches the clipboard.
- **Failures.** A model outage, timeout, dependency failure or audit failure appears as the API returns it: a human handoff with
  the named reason. Failure events sit on the stage that emitted them.

## Search, filters and capitalization

- Search boxes (Conversations, Knowledge) compare a folded key (Unicode NFKC, invisible characters removed, lower case), so
  "MY IPHONE", "my iphone" and a full-width "ＭＹ ＩＰＨＯＮＥ" find the same rows; displayed text is never changed.
- URL filters accept any capitalization or separator (`?filter=HIGH-RISK`, `/traces?action=human_handoff`); an unknown value means
  "All". The top-bar search accepts a trace id in upper or lower case.
- The agent behaves the same way: a message typed in capitals gets the same decision (`docs/ARCHITECTURE.md` §12). A bare greeting
  is answered with a short greeting and no retrieval; "can I talk to a human" is a handoff with the reason "Customer asked for a
  person".
- The Overview warns when the running pipeline is newer than the evaluated release, and the Agents page lists the difference.

## Data labels

| Label | Meaning | Where |
|---|---|---|
| LIVE OPERATIONAL DATA | traces this API recorded in this environment; no ground truth | Overview, Knowledge Center |
| FROZEN GOLDEN SET | one run of a configuration on the 197 annotated conversations, with bootstrap intervals | Overview, Evaluation Center, Knowledge Center |
| DEV EXPERIMENTS | pre-registered experiments on the development split (AI labels) | Evaluation Center |
| PERFORMANCE PROFILE | latency and cost on dev requests on one shared machine | Evaluation Center |
| KNOWLEDGE BASE | aggregates over the historical corpus | Knowledge Center |

They are never combined in one number. The live Overview shows "Not measured live" for escalation recall and groundedness.

## Loading, error and empty states

- **Running.** "Running ResolveAI…" shows an elapsed timer and a cancel button. It does not pretend to track stage progress; the
  recorded stage outcomes appear when the response arrives.
- **Errors, each explained with its code, HTTP status and correlation ids, never a stack trace:** 401 not authorized, 403 access
  not permitted, 404 not found, 413 too large, 429 too many requests or agent busy, API unavailable, agent loading or failed,
  timeout, cancelled, invalid response, trace not found, invalid trace id, evaluation unavailable, demo scenarios unavailable, and
  a console render error. A model outage is not an error: it is a handoff.
- **Empty.** With an empty trace store, pages say nothing was processed and show no numbers.

## Security and privacy in the browser

- The browser talks only to the same-origin forwarder, which allows only the API's own endpoints and attaches the token server
  side. No token, key or API address reaches the browser.
- Traces never contain customer text. To reopen a workspace, the already-redacted `/resolve` responses of this browser's runs are
  kept in localStorage (last 50), disclosed and clearable on Settings and the Simulator.
- The clipboard receives only the handoff summary, scrubbed again.
- Settings shows credential presence, never a value.

## Accessibility and responsive behaviour

- Detail pages (conversation, handoff, trace) carry a breadcrumb back to their list.
- Semantic landmarks, a skip link, labelled inputs and visible focus; `aria-expanded`, `aria-controls`, `aria-current`,
  `aria-pressed` and `aria-live` where they apply; DOM order is reading order in the three-panel workspace.
- Meters carry values, charts carry text alternatives, and reduced motion is respected; no animation implies progress that is not
  measured.
- The browser smoke runs axe-core (WCAG 2.1 A/AA) and checks horizontal overflow on desktop, narrow desktop, tablet and mobile.
- Layout: three workspace panels at ≥1280 px (the list collapses into a disclosure below), two at ≥1024 px, one below; the sidebar
  becomes a drawer below 1024 px; wide tables scroll inside their card.

## Known limitations

- **No operator login or roles.** Anyone who can reach the console can use it; the API token lives on the console server.
- **Live metrics are local.** The latest 200 traces of a reference environment, not production traffic.
- **Text is per browser.** Conversation text and evidence are available only in the browser that ran the conversation.
- **No corpus browsing.** The Knowledge Center shows aggregates and retrieved cases, not the whole corpus.
- **Model failure scenario.** Through a live API with a working model, the outage path does not trigger; the CLI demo simulates it.
- **Display grouping.** Handoff severity and queue are a fixed grouping of reason codes, not a triage model.
- **Language.** English only.
