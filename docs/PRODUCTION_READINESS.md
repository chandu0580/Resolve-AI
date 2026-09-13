# ResolveAI production readiness (release 1.0.0)

ResolveAI is a self-contained **reference implementation**, not a deployed production system. For each item, the checklist gives:
- whether the implementation is **READY**, **PARTIAL** or **NOT READY** for a real enterprise deployment;
- the evidence the status rests on;
- the limitation that remains;
- the next step.

An item is not marked READY just because a test exists. READY means the behaviour is implemented and measured or tested against
the real code path, and nothing known is missing for this scope. Even READY items were measured on a single-process reference
setup.

Summary: 55 items: 21 READY, 23 PARTIAL, 11 NOT READY. Product Completion 1 added "Product surfaces" (PARTIAL). The final hardening added "Live model outage" (PARTIAL). The final repository pass added "Case and text normalization" (READY) and "Evaluated versus running configuration" (PARTIAL). The PARTIAL and NOT READY items list what an enterprise deployment would still need. Even the READY items were measured on a single-process reference setup, not a deployment.

## Security

| Item | Status | Evidence | Limitation | Next step |
|---|---|---|---|---|
| API authentication | PARTIAL | Bearer tokens compared as SHA-256 digests with `compare_digest`, enforced before the body is read (`resolveai/api/access.py`). The `production` profile refuses to start without a token of 32+ characters. Tests: `tests/test_phase9_api_security.py`. Live production-profile smoke: 401 without or with a wrong token, and 401 before body validation (`artifacts/final/api_smoke.json`, 23 of 23 checks). | Static shared tokens: no per-user identity, rotation, expiry or revocation | An identity provider (OIDC) or signed short-lived tokens |
| Authorization (scopes) | PARTIAL | `resolve` and `read` scopes; a read-only token on `/resolve` gets 403 (unit test and live smoke) | Two coarse scopes; no per-tenant or per-conversation access control | A role model per operator; an audit of who called what |
| Secrets handling | PARTIAL | `.env` gitignored. The security scan compares the real `.env` secret values in memory and finds none in 785 committable files: 0 findings (`artifacts/product/hardening/security_scan.json`, 2026-09-12). Tokens are never logged, traced or returned (the live smoke found 0 tokens and 0 model keys in the server log). | Secrets live in environment variables and `.env`; no secret manager | Secret manager, key rotation |
| Transport security | NOT READY | The API binds to 127.0.0.1 by default | No TLS or HSTS; the console-to-API hop is plain HTTP | TLS at a reverse proxy; network policy between console and API |
| Input validation and limits | READY | `extra=forbid` request schema; body size checked before parsing (411/413); per-message, per-turn, turn-count and total limits (413 with details). The live smoke rejects a spoofed `evidence` field with 422 without echoing it. | — | — |
| Prompt-injection defence | PARTIAL | A deterministic detector checks every turn (hard block, 0 model calls). Retrieved evidence with instruction-like text is quarantined. The model cannot clear a rule flag or bypass verification. Adversarial suite: 20 of 20 pass (`artifacts/final/adversarial_suite.md`) (cases 10–12); the live smoke saw 0 model calls on an injection. | Pattern-based: novel phrasings are contained by the gates, not detected | A red-team set; a classifier-based detector evaluated on dev |
| CORS | READY | Explicit origins; wildcard rejected in every profile; the console uses a same-origin forwarder | — | — |
| Dependency vulnerability scanning | NOT READY | None | Python and npm dependencies are not audited | `pip-audit` / `npm audit` in CI |

## Privacy

| Item | Status | Evidence | Limitation | Next step |
|---|---|---|---|---|
| PII redaction before model, trace and log | PARTIAL | Redaction runs first. The model client and the trace recorder refuse unredacted text, and exception text is redacted before logs. `tests/test_phase9_pii.py` (25 cases); adversarial case 17; the live smoke shows no raw email or phone in the response, trace or server log. | Regex-based: names, street addresses, spelled-out identifiers and lowercase serials are not detected. The frozen corpus still holds 4 KB rows with a number the old pattern missed (evidence is redacted again when served). | NER-based detection; re-process the corpus |
| Trace content minimisation | READY | Traces store ids, versions, statuses, latencies, decision data and failure codes, never customer text or reasoning. Security scan: 0 of 813 trace records contain unredacted PII. | — | — |
| Log redaction | PARTIAL | The access log holds method, path, status, latency and request id. Unhandled errors log type, redacted message and code locations (tested). The live smoke server log had 0 raw PII, tokens or message text. | Third-party library logging is not audited line by line | Structured logging with an allow-list |
| Result storage in the operator's browser | PARTIAL | Only already-redacted API responses (the last 50), clearable and disclosed on the page | localStorage is unencrypted and not tied to an operator | Server-side case storage with access control |
| Data retention | NOT READY | Traces are append-only JSONL files | No retention period, deletion or export policy | Retention policy and a deletion job |

## Reliability

| Item | Status | Evidence | Limitation | Next step |
|---|---|---|---|---|
| Model timeouts, retries, request budget | READY | Client-enforced wall-clock limit per call, one bounded retry, SDK retries disabled, per-request budget (production 45 s). Unit tests plus adversarial cases 13–15 (handoff within bounded time). | A timed-out provider call's thread cannot be killed | Async provider client with cancellation |
| Live model outage | PARTIAL | Final hardening: an API started with an unreachable model endpoint and a model name with no cached responses answered the autocorrect message with HTTP 200 `HUMAN_HANDOFF`, reason `llm_unavailable`, rule `llm_fallback`, risk stage `fallback`, draft stage `fallback` | The handoff took 42 s: connection attempts and retries run until the per-call limits expire, so a customer waits that long during an outage | Circuit breaker that skips model calls after repeated failures |
| Dependency failure handling | READY | Retrieval, embedding, classifier and verifier crashes become a classified `dependency_failure` handoff; an unwritable trace store withholds any automatic reply (`audit_unavailable`); a model outage is a 200 handoff. Tested (`tests/test_phase9_adversarial.py`, suite cases 16 and 20). | — | — |
| Audit trail integrity | READY | A corrupted or truncated trace line no longer takes `/traces` down: it is skipped and counted, and a corrupted record is never served. Found by suite case 20 and fixed; `tests/test_trace_store_corruption.py`. | File-based store; no checksums | Append-only store with integrity checks |
| Concurrency and capacity | PARTIAL | One agent execution at a time, a bounded queue and a queue timeout (429 `agent_busy`) | Single process, no horizontal scaling | Worker pool with per-request usage accounting |
| Startup and readiness | PARTIAL | Background load. `/ready` checks components and never calls the model. Production fails fast without a token. The live smoke became ready in 15 s. | The first agent request after a start is slow: 24 s and 67 s were measured (embedding model and classifier warm-up) | Warm the models during startup, before `/ready` reports ready |
| Console resilience | READY | API-unavailable, timeout, unauthorized, forbidden, rate-limited and invalid-response states (unit tests); browser smoke with the API stopped: 4 routes show "ResolveAI API unavailable", 0 failures, 0 axe violations (`artifacts/final/smoke/smoke_api_down.json`) | — | — |

## Observability

| Item | Status | Evidence | Limitation | Next step |
|---|---|---|---|---|
| Per-request traces | READY | Request and trace ids (body and headers), versions, config hash, stage status (skipped vs fallback), stage latency, model calls, retries, timeouts, errors, budget refusals, classified failures `{category, stage, kind}`; no free text. The listing reads each file backwards and stops at the limit: 200 rows over 20,000 traces in 63 ms p50 (629 ms before the final hardening; `tests/test_final_hardening.py`) | File-based JSONL; no index, retention or integrity checksums | Indexed trace store or an OpenTelemetry exporter |
| Metrics and alerting | NOT READY | None | No metrics, dashboards or alerts on handoff rate, fallback rate or latency | Export counters and latency histograms; alert rules |
| Centralised logging | NOT READY | Local stdout logs | No log shipping or retention | Log pipeline |

## Evaluation

| Item | Status | Evidence | Limitation | Next step |
|---|---|---|---|---|
| Frozen golden set and single runs | READY | Golden sha256 verified before and after every run. Each system was run once: `phase9_final`, then `final_release` after the pre-registered dev decision (`artifacts/final/evaluation/runs/final_release.meta.json`). Earlier results are untouched. | n = 197 | — |
| Pre-registered dev decisions | READY | `artifacts/final/risk_experiment/PREREGISTRATION.md` was written before the run, and its SHA-256 is in the report. The Phase 9 acceptance rule was applied unchanged. | Dev labels are AI-written | Human dev labels (below) |
| Reproducibility of the cached evaluation | READY | `scripts/verification/final_verification.py` re-ran `scripts/evaluate.py --cached` into a scratch folder with no model calls (171.6 s, 2026-09-12). All 11 regenerated result files are byte-identical to the frozen Phase 6 artifacts (`artifacts/product/hardening/cached_eval_check.json`), and nothing frozen is written. | Reproduces from committed run records and judge results only | — |
| Human validation of the LLM judge | NOT READY | `data/human_eval/human_scoring_packet.csv`: 50 rows, **0 rated** | Every groundedness and hallucination number is an unvalidated GLM-5.2 judgement from the drafter's own model family | A human fills the packet per `docs/HUMAN_JUDGE_GUIDE.md`, then `python scripts/evaluate.py --cached` |
| Dev data for decisions | PARTIAL | Phase 9 and 10 risk experiments on 240 dev rows; 76 disagreement rows labelled | Labels are from an AI annotator, not humans | Human-labelled dev set for risk and escalation |
| Statistical power | PARTIAL | 95% bootstrap intervals and paired differences everywhere | 37 escalation positives and 12 automatic replies: most differences are not distinguishable | A larger, stratified, human-labelled evaluation set |

## Grounding

| Item | Status | Evidence | Limitation | Next step |
|---|---|---|---|---|
| Evidence invariant ("no sufficient evidence, no autonomous reply") | READY | Enforced in the policy, the drafter's refusal, the verifier (lexical and model), the output gate and the API re-check. Adversarial tests: empty, weak and contradictory evidence, fabricated references, a hallucinated draft with an approving verifier, a tampered API result. Golden: 0 unsafe of 12 automatic replies. | — | — |
| Groundedness of replies | PARTIAL | Judge groundedness 3.95 [3.76, 4.13] on the release run (Phase 9: 4.19). The change is entirely on changed template wording (`artifacts/final/evaluation/judge_attribution.md`). The 5 troubleshooting replies have judge hallucination 0. | Grounded is not correct; the judge is not human-validated | Outcome tracking; a human review sample |
| Customer-facing template wording | NOT READY | Judge notes on the release run: the hardware handoff line apologises for "damage" when the model's damage flag fired on a battery or reboot complaint (15 flags). The repeat-contact line thanks the customer for "steps you've already tried" (9). Clarifications cite a menu path absent from the evidence. | Templates assert facts the message does not contain. Found on golden, so not reworded against golden. | Neutral templates evaluated on dev with human review |
| Evidence poisoning | PARTIAL | Quarantine of instruction-like evidence (0 of 20,000 corpus rows today; adversarial case 11); evidence re-redaction | Subtle misinformation in historical replies is not detected | Curated knowledge base with provenance review |

## Policy

| Item | Status | Evidence | Limitation | Next step |
|---|---|---|---|---|
| Deterministic, versioned escalation policy | READY | policy-v3.3 (27 ordered rules) names a rule on every decision and trace. The model never decides escalation and cannot clear a rule flag (tested). A test keeps the served rule list equal to the code's order. | — | — |
| Case and text normalization | READY | Capitalization, spacing, punctuation, Unicode width and invisible characters do not change a decision. The classifier's tokenizer lower-cases, rules match a normalised key, and all-caps is no longer a frustration signal. The original text is kept. Tested across five casings for intent, evidence, policy, risk flags, injection, greetings, requests for a person, short replies, API ids and filters, and console search (`tests/test_case_and_conversation.py`, `frontend/tests/product.test.tsx`). | Serial numbers are matched in upper case only, deliberately: a case-insensitive pattern redacted product hashtags in 157 of 20,000 knowledge-base messages | — |
| Evaluated versus running configuration | PARTIAL | Release 1.0.0 was evaluated once with `pipeline-v6.1` / `policy-v3.1`. The running product is `pipeline-v6.3` / `policy-v3.3` (greetings, requests for a person, short replies, capitalization, a language redirect that obeys the confidence floor, and non-Latin scripts recognised deterministically). The Agents page lists the difference and the Overview warns about it. `scripts/evaluation/behaviour_change_impact.py`: 21 of 197 golden rows reach a changed input path. | The golden run was not repeated (single-run protocol), so golden numbers describe v6.1 | Evaluate v6.3 on a fresh, human-labelled set rather than re-running golden |
| Escalation recall | PARTIAL | Golden recall 0.973 [0.912, 1.000] (37 positives, 1 missed: g048) | 37 positives; wide interval | Larger labelled set; dev-evaluated rule variants |
| Over-escalation (unnecessary handoffs) | NOT READY | Golden precision 0.324: 75 unnecessary of 111 handoffs (down from 87 after the pre-registered Phase 10 change). Largest reasons: insufficient_evidence 21, repeat_contact 12, hardware 12. | Humans receive many cases a reply or one question could handle | Human-labelled dev set; a `physical_damage` candidate; non-support templates |

## API

| Item | Status | Evidence | Limitation | Next step |
|---|---|---|---|---|
| Error schema and correlation | READY | One error body `{error_code, message, request_id, trace_id, details}` for every status, including 401/403/429; no input echo; `X-Request-ID` and `X-Trace-ID` headers | — | — |
| Rate limiting | PARTIAL | Resolve, read and failed-authentication limiters with 429 and `Retry-After`: unit tests plus the live smoke (all three limits triggered) | Process-local only; not shared across processes or hosts (stated in `/config`) | Shared limiter store for multi-process deployments |
| Timeouts | READY | Request budget, per-call wall-clock limit, queue timeout, console forwarder timeout | — | — |
| Versioning | PARTIAL | `/api/v1`, OpenAPI document (1.0.0), generated console types with a contract test | No deprecation policy or cross-version compatibility tests | Contract tests in CI |

## Frontend

| Item | Status | Evidence | Limitation | Next step |
|---|---|---|---|---|
| Decision transparency | READY | AUTO-HANDLED / CLARIFICATION / HUMAN HANDOFF with reason, evidence, output gate, verification, packets and trace. "Why did ResolveAI do this?" (decision, reason, evidence, policy, risk, verification, next action) is built from structured data only (`frontend/lib/explain.ts`). Evidence used in the response is separated from retrieved evidence. 122 frontend tests in 15 files. | — | — |
| Product surfaces | PARTIAL | Overview, three-panel Conversations workspace, Handoff Center, Simulator, Knowledge Center, Agent configuration, Evaluation Center, Trace Explorer, Trust & Governance, Settings. Final hardening browser smoke against the auth-enabled API (`artifacts/product/hardening/smoke/smoke_results.json`): 40 route visits, 7 of 7 scenarios, 12 of 12 interactions, 0 failures, 0 axe violations, 0 pages with horizontal overflow on desktop, narrow, tablet and mobile; server-rendered pages answered in 41–376 ms time to first byte after the first (cold, 1.6 s) page. The scenario runs were served from the model response cache. | Read-only views over one process's trace store and committed artifacts; no case assignment, notes or SLA tracking | Server-side case store with assignment and audit |
| Error, auth and rate-limit states | READY | Unit tests for 401/403/404/413/429/timeout/cancelled/invalid response; with no console token, 5 routes show "Not authorized" (`artifacts/product/hardening/smoke/smoke_unauthorized.json`); with the API stopped, 7 routes show "ResolveAI API unavailable" (`smoke_api_down.json`), 0 failures and 0 axe violations in both. Every protected endpoint answered 401 to anonymous and wrong-token calls on the live server; the console forwarder refused the docs path and a traversal attempt (404) and is unit-tested (`frontend/tests/proxy.test.ts`) | — | — |
| Accessibility | PARTIAL | axe-core WCAG 2.1 A/AA on audited pages in the browser smoke; DOM order is reading order in the workspace; keyboard skip link and mobile drawer checked | No manual screen-reader or keyboard-only session | Manual accessibility review |
| Operator login | NOT READY | The console has no user login; the API token lives on the console server (Settings shows only whether it is set) | Anyone who can reach the console can use it | Operator authentication (SSO) in front of the console |

## Performance

| Item | Status | Evidence | Limitation | Next step |
|---|---|---|---|---|
| Latency (measured, dev messages) | PARTIAL | `artifacts/final/performance/perf_final.md`: total p50 / p95: no model 173 / 374 ms and cached model 256 / 635 ms (n = 100 each, on a machine shared with other workloads); live, random dev messages 4.2 / 14.2 s (n = 40); live requests that drafted and verified 10.7 / 26.1 s (n = 8, small sample); 0 timeouts; est. $0.003 per live request at list price | Live model latency dominates, bounded only by the budget; measured on one shared machine with a remote model proxy | Parallelise independent model calls; a faster risk model |
| Throughput | NOT READY | One agent execution at a time | No load test | Load test with concurrent workers |
| Duplicate computation | READY | Query embedding shared between classifier and retrieval; risk call skipped when a handoff is already guaranteed; templates skip the model verifier | — | — |

## Reproducibility

| Item | Status | Evidence | Limitation | Next step |
|---|---|---|---|---|
| Deterministic evaluation and integrity | READY | Seeds, SHA-256 response cache, golden and artifact hashes. `artifacts/final/verification.json`: golden hash verified; 353 frozen files byte-identical to the Phase 10 start snapshot, none added; Phase 7 hash snapshot (115 files) unchanged; cached evaluation identical | — | — |
| Clean-clone reproduction | PARTIAL | Run 1 (fresh venv) failed on the undeclared `rank-bm25` (`clean_env_check.attempt1.md`). Run 2 (fresh venv) passed the install, demo, API, lint, typecheck and build, and found three packaging gaps, all now fixed (`clean_env_check.attempt2.json`). Run 3 checked the fixed file set and passed every step, reusing the interpreter and embedding cache (`clean_env_check.json`). Final hardening, full run (fresh venv, no `.env`, no `.cache`, isolated model cache): install, 319 backend tests (2 skipped), demo, API reply without a model, `npm ci`, lint, typecheck, tests and build passed, but the release verification step failed because `scripts/final/f_final_verification.py` compares against the Phase-10 baseline, which predates the later passes (`artifacts/product/hardening/clean_env_check.json`, `failed_steps`). The verification then passed on a fresh copy with the correct baseline, and the release-readiness pass fixed the cause: `release_checks.py clean-env` now runs the current wrapper in that step (DECISIONS #119) | Same OS and base interpreter; pip and npm download caches may be reused | CI job on a fresh runner |
| Environment pinning | PARTIAL | `requirements.txt`, `requirements-dev.txt`, `frontend/package-lock.json` | Python dependencies are lower-bound pins without hashes | Lock file with hashes (pip-tools / uv) |

## Documentation

| Item | Status | Evidence | Limitation | Next step |
|---|---|---|---|---|
| Architecture, API, UI, evaluation, decisions, demo, interview notes, reports | READY | `docs/ARCHITECTURE.md`, `API.md`, `UI.md`, `EVALUATION.md`, `DECISIONS.md` (#1–#107 with an index by area), `REPRODUCIBILITY.md`, `DEMO.md`, `INTERVIEW_NOTES.md`; `artifacts/final/FINAL_REPORT.md`, `ARTIFACT_MAP.md` | — | — |
| Operational runbooks | NOT READY | None | No incident, token-rotation, backup or on-call procedures | Runbooks for the NOT READY items above |
