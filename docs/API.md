# ResolveAI API (1.0.0)

The API exposes the ResolveAI agent over HTTP. It holds no agent logic of its own: `POST /api/v1/resolve` calls the same
orchestrator as the CLI, the demo and the evaluation harness. This is a production-style reference implementation; it runs locally
with Python and uvicorn and needs no Docker. What a real deployment would still need is listed in `docs/PRODUCTION_READINESS.md`.

Every JSON example below is a real response from the release, captured by `scripts/final/i_api_examples.py`
(`artifacts/final/api_examples.json`) and trimmed. The model responses were served from the response cache. No real token appears
anywhere in this document. The examples were captured from release 1.0.0 as evaluated (`pipeline-v6.1`, `policy-v3.1`); the running
product is `pipeline-v6.3` / `policy-v3.3` (see "Conversation behaviour and text matching"), so live version strings differ.

## Run

```bash
pip install -r requirements.txt
cp .env.example .env                        # LLM_API_KEY / LLM_BASE_URL / LLM_MODEL; without them the agent uses its deterministic fallbacks
python -m resolveai serve                   # development profile: http://127.0.0.1:8000, Swagger UI at /docs, no auth
RESOLVEAI_API_TOKEN=<32+ random characters> python -m resolveai serve --env production   # auth required, docs disabled, 45 s budget
```

The agent loads in a background thread (knowledge base, embeddings, classifier). `/api/v1/health` answers at once, and
`/api/v1/ready` returns 503 until the agent is loaded.

## Authentication

| Profile | Authentication | Notes |
|---|---|---|
| `production` | **required** | Startup fails without `RESOLVEAI_API_TOKEN` (at least 32 characters) or with `RESOLVEAI_AUTH_REQUIRED=false` |
| `development`, `demo`, `test` | disabled explicitly | `RESOLVEAI_AUTH_REQUIRED=true` turns it on; every request then acts as `anonymous` with all scopes |

- **Headers.** Send `Authorization: Bearer <token>` or `X-API-Key: <token>`.
- **Tokens.** `RESOLVEAI_API_TOKEN` grants `resolve` + `read`; `RESOLVEAI_READ_TOKEN` grants `read` only. Tokens are compared as
  SHA-256 digests with `hmac.compare_digest`. They are never logged, traced or returned, and the trace schema rejects
  `authorization`, `token`, `password` and `api_key` keys.
- **Order.** Authentication runs **before** the body is read or validated, so an unauthenticated malformed request gets 401, not
  a validation error.
- **One answer for missing or wrong credentials.** Both return the same 401 with `WWW-Authenticate`, so the API does not reveal
  which one failed.
- **Console.** The console attaches its token server side and never forwards a browser `Authorization` header.

## Authorization

| Method | Path | Scope | Purpose |
|---|---|---|---|
| GET | `/api/v1/health` | public | process liveness, no inference |
| GET | `/api/v1/ready` | public | component readiness (anonymous callers see booleans only); never calls the model |
| POST | `/api/v1/resolve` | **resolve** | run one conversation through the agent |
| GET | `/api/v1/traces` | read | recent traces, newest first (`?limit=&action=`; `action` in any capitalization) |
| GET | `/api/v1/traces/{trace_id}` | read | the audit trace of one execution (32 hex characters, upper or lower case) |
| GET | `/api/v1/config` | read | safe runtime configuration (no keys, base URLs or paths) |
| GET | `/api/v1/evaluation/summary` | read | frozen Phase 6 evaluation artifacts, served as stored |
| GET | `/api/v1/evaluation/release` | read | release 1.0.0 scorecard from `artifacts/final`, grouped by dataset (frozen golden set, dev experiments, performance profile, verification checks); example text PII-redacted |
| GET | `/api/v1/agent/profile` | read | the loaded agent's active configuration next to the evaluated configuration, the ordered policy rules and the allowed actions (no secrets) |
| GET | `/api/v1/knowledge/summary` | read | knowledge-base aggregates: counts, shares, date range, index facts; no message text |
| GET | `/api/v1/demo/scenarios` | read | the seven demo scenarios and their expected outcomes |
| GET | `/docs`, `/openapi.json` | read | interactive docs (disabled in `production`) |

A valid token without the needed scope gets **403 `forbidden`**.

## Request

```json
{
  "conversation": [
    {"role": "customer", "text": "My iPhone keeps changing \"it\" to \"I.T\" whenever I type. How do I fix this autocorrect bug?"}
  ],
  "metadata": {"channel": "twitter", "locale": "en-US"}
}
```

| Field | Type | Rules |
|---|---|---|
| `conversation` | list of `{role, text}` | oldest first; role `customer` or `brand`; **the last turn must be the customer message to handle** |
| `metadata.channel` | enum | `twitter`, `email`, `chat`, `web`, `api`; recorded in the trace |
| `metadata.locale` | string | pattern `xx` or `xx-XX`; recorded in the trace |
| `metadata.timestamp` | ISO datetime | evidence must predate it |
| `metadata.customer_id_hash` | 64 hex chars | SHA-256 of the caller's id; validated, then discarded (never stored, traced or sent to a model) |

- **Unknown fields are rejected** with 422, including any attempt to send `evidence`, `policy` or `system`. Evidence only comes
  from the retrieval index.
- **Request id.** An optional `X-Request-ID` header (8–64 characters of `[A-Za-z0-9._-]`) is kept; otherwise one is generated.
- **Limits.** All checked before any model call:

| Limit | Default | Setting |
|---|---|---|
| Body size (checked before JSON parsing) | 64,000 bytes | `RESOLVEAI_MAX_BODY_BYTES` |
| Current customer message | 2,000 characters | `RESOLVEAI_MAX_MESSAGE_CHARS` |
| Any earlier turn | 2,000 characters | `RESOLVEAI_MAX_TURN_CHARS` |
| Turns | 20 | `RESOLVEAI_MAX_TURNS` |
| All turns together | 12,000 characters | `RESOLVEAI_MAX_TOTAL_CHARS` |

## Response

Every `/resolve` response has these top-level fields. No field contains model reasoning.

| Field | Content |
|---|---|
| `request_id`, `trace_id` | correlation ids, also returned as `X-Request-ID` and `X-Trace-ID` headers |
| `action` | `AUTO_HANDLE`, `CLARIFICATION_REQUIRED` or `HUMAN_HANDOFF` |
| `outcome` | what happened, why, the evidence basis, the next step, `reason_code`, `rule`, `policy_version`, `autonomous_response_allowed`, all nine `output_gate` checks and the `blocking_checks` |
| `response` | `kind`, `text`, `sent_automatically`, `evidence_refs` (citations; only for an automatic reply), `draft_attempts` |
| `intent` | intent, calibrated confidence, band, top-3 alternatives |
| `evidence` | items with provenance, `sufficient`, `sufficiency_level`, `sufficiency_reason`, `resolution_confidence`, `consistency`, clusters, `quarantined_ids` |
| `risk` | risk flags and their source (`rules` or `llm+rules`) |
| `verification` | `verified`, `severity`, `coverage`, `method`, cited ids, issues (null when nothing was drafted) |
| `clarification` / `handoff` | the packet for that action (null otherwise) |
| `conversation` | the conversation **after** PII redaction |
| `versions` | pipeline, policy, output gate, retrieval, evidence gate, rerank, classifier hash, prompt versions, model, `config_hash` |
| `stage_status`, `latency_ms`, `usage` | per-stage status (`ok`, `skipped`, `fallback`, `failed`), per-stage latency, and model calls, cache hits, tokens, estimated cost, retries, timeouts, errors, budget refusals |

## Actions

| Action | `response.kind` | Sent automatically | Packet | `evidence_refs` |
|---|---|---|---|---|
| `AUTO_HANDLE` | `auto_reply` (or `template_reply` for the non-English redirect or a closure) | yes | none | a citation for each cited historical case |
| `CLARIFICATION_REQUIRED` | `clarifying_question` | no | `clarification`: why, missing information, already provided, the question, intent hypothesis | empty |
| `HUMAN_HANDOFF` | `handoff_notice` (a holding line, never an answer) | no | `handoff`: issue, intent and alternatives, risk, reason, evidence summary, historical examples, recommended next action, unresolved questions, suggested opening, rejected draft if any | empty |

## Conversation behaviour and text matching

- **One contract for every message.** Every request still runs the same pipeline and returns exactly one action.
- **Greeting only** ("hi", "Hello!", "hey ResolveAI"): `AUTO_HANDLE`, rule `canned:greeting`, a short fixed greeting;
  `evidence.sufficiency_reason` is `not_applicable`, the retrieval stage is `skipped` and no model is called. A greeting followed by
  a request ("hi, my iphone won't turn on") is handled as the request.
- **Explicit request for a person** ("can I talk to a human"): `HUMAN_HANDOFF`, reason code `human_requested`, after every safety,
  security, account, billing, private-information, hardware and repeat-contact rule.
- **Short replies in a thread** ("still happening", "that didn't work", "iphone 15"): classified together with the earlier issue they
  answer; context never overrides a hard block such as prompt injection.
- **Thanks** is answered with a closing template; a bare "yes" or "no" that answers an open question in the thread is not.
- **Capitalization, width and invisible characters** never change the decision: classification and retrieval are case-insensitive by
  construction, rules match a normalised key, and the original text is kept (`docs/ARCHITECTURE.md` §12).
- **Customer-facing text** (`response.text`) never contains rule names, versions, confidence values, model names, trace ids, evidence
  ids or redaction tokens; those are operator fields elsewhere in the response. `tests/test_case_and_conversation.py` checks it.

## Example: request and AUTO_HANDLE response

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/resolve \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" -H "X-Request-ID: doc-example-auto_handle" \
  -d '{"conversation":[{"role":"customer","text":"My iPhone keeps changing \"it\" to \"I.T\" whenever I type. How do I fix this autocorrect bug?"}],"metadata":{"channel":"twitter","locale":"en-US"}}'
```

```json
{
  "request_id": "doc-example-auto_handle",
  "trace_id": "957e30e635044fe69b875174fc2be03e",
  "action": "AUTO_HANDLE",
  "outcome": {
    "what_happened": "Answered automatically with a verified reply grounded in 3 historical case(s).",
    "why": "Clear 'keyboard_text_bug' issue with grounded troubleshooting steps and no risk flags. Evidence STRONG; verifier passed (evidence coverage 0.71); every output-gate check passed.",
    "evidence_basis": "Cited cases: 2287602 (update, similarity 0.86, rank 2); 2573954 (update, similarity 0.89, rank 1); 2312398 (update, similarity 0.89, rank 3). 5 similar historical cases retrieved; top similarity 0.89; evidence STRONG (strong_consistent_evidence); resolution clusters: update x5; resolution confidence 0.97.",
    "next_step": "Send the reply; re-open the case if the customer reports the fix did not work.",
    "reason_code": "none",
    "rule": "default_auto",
    "policy_version": "policy-v3.1",
    "autonomous_response_allowed": true,
    "output_gate": {
      "policy_allows_automation": true, "no_blocking_risk_flag": true, "intent_confidence_acceptable": true,
      "evidence_sufficient": true, "response_generated": true, "response_verified": true,
      "evidence_refs_exist": true, "pii_guard": true, "schema_valid": true
    },
    "blocking_checks": []
  },
  "response": {
    "kind": "auto_reply",
    "text": "Let's be sure your iPhone has the latest iOS installed. It includes fixes for autocorrect issues. You can check in Settings > General > About. We recommend backing up first, then installing the update. You can find the steps on our support site. Let us know if this helps!",
    "sent_automatically": true,
    "evidence_refs": [
      {"evidence_id": "2287602", "thread_id": "2287603", "source_row_id": "2287603", "created_at": "2017-11-12 01:41:57+00:00", "rank": 2,
       "similarity": 0.862, "retrieval_source": "pair", "action_class": "update", "resolution_bearing": true, "outcome": "none"},
      "... 2 more"
    ],
    "draft_attempts": 1
  },
  "evidence": {
    "sufficient": true, "sufficiency_level": "STRONG", "sufficiency_reason": "strong_consistent_evidence",
    "resolution_confidence": 0.971, "consistency": "consistent", "retriever": "dense:bge-small:pair+rr+gatev3", "quarantined_ids": [],
    "items": "[5 EvidenceItem objects: customer_message, brand_reply, created_at, rank, scores, quality, provenance]"
  },
  "verification": {"verified": true, "severity": "none", "coverage": 0.706, "method": "lexical+llm", "evidence_refs": ["2287602", "2573954", "2312398"]},
  "versions": {
    "pipeline": "pipeline-v6.1", "policy": "policy-v3.1", "output_gate": "output-gate-v1", "retrieval": "dense:bge-small:pair+rr+gatev3",
    "evidence_gate": "gate-v3", "rerank": "rerank-v1", "classifier": "2d194e7e704f",
    "prompts": {"risk": "risk-flags-v2", "draft": "draft-v2", "verify": "verify-v2", "second_opinion": "intent-second-opinion-v1"},
    "model": "glm-5.2", "config_hash": "9bd0d4ce163d6c6d"
  },
  "stage_status": {"pii_redaction": "ok", "context": "ok", "intent": "ok", "second_opinion": "skipped", "retrieval": "ok", "evidence_gate": "ok",
                   "risk": "ok", "policy": "ok", "draft": "ok", "verification": "ok", "output_gate": "ok", "trace": "ok"},
  "usage": {"llm_calls": 3, "live_calls": 0, "cache_hits": 3, "tokens_in": 1344, "tokens_out": 1909, "estimated_cost_usd": 0.007453,
            "fallbacks": 0, "retries": 0, "timeouts": 0, "model_errors": 0, "budget_exhausted": 0}
}
```

**CLARIFICATION_REQUIRED** (`"My iPhone 8 on iOS 11.1.2 drains battery really fast since yesterday"`): reason
`insufficient_evidence`. The question is "We'd like to help with the battery. Could you tell us what you've already tried?", with
`clarification.missing_information: ["what you've already tried"]` and `already_provided: ["device", "version", "timing"]`.

**HUMAN_HANDOFF** (`"Someone logged into my Apple ID from another country and changed my password. I can't sign in anymore."`):
reason `safety`, rule `security`, 0 model calls. The holding line is "Thanks for telling us, and we're sorry you're dealing with
this. A member of our team will take this up with you directly right away." The `handoff` packet carries the summary, issue,
intent and alternatives, risk, reason, evidence summary, historical examples, recommended next action, unresolved questions,
suggested opening, rejected draft (if any), trace id and policy version.

## Errors

Every error has the same body: `{error_code, message, request_id, trace_id, details}`. Error bodies never contain stack traces,
secrets or the submitted values.

| Status | `error_code` | When |
|---|---|---|
| 400 | `invalid_json`, `invalid_conversation`, `invalid_trace_id` | body is not JSON; last turn is not the customer; malformed trace id |
| 401 | `unauthorized` | missing or invalid credentials (with `WWW-Authenticate: Bearer realm="resolveai"`) |
| 403 | `forbidden` | valid credentials without the required scope |
| 404 | `not_found`, `trace_not_found`, `evaluation_not_available` | unknown path or id |
| 411 | `length_required` | POST without Content-Length (chunked bodies are refused before parsing) |
| 413 | `payload_too_large`, `input_too_large` | body over the byte limit; conversation over the configured limits (details name the limit) |
| 422 | `validation_error` | schema violation, including unknown fields; `details` lists field locations and types only |
| 429 | `rate_limited`, `agent_busy` | a rate limit was reached, or no execution slot within the queue timeout (`Retry-After` set) |
| 500 | `internal_error`, `autonomy_invariant_violation` | unexpected failure (redacted log only); an automatic reply failed the API's invariant re-check and was withheld |
| 503 | `agent_not_ready`, `agent_unavailable` | agent still loading or failed to load |

Real examples:

```json
{"status": 401, "headers": {"www-authenticate": "Bearer realm=\"resolveai\""},
 "body": {"error_code": "unauthorized", "message": "Missing or invalid credentials. Send Authorization: Bearer <token>.", "request_id": "eb44b7bb459341cfa2bf71c0571821f6", "trace_id": null, "details": null}}
{"status": 403, "body": {"error_code": "forbidden", "message": "These credentials do not allow 'resolve' operations.", "request_id": "bd9d594414ba49259a6f7bc207754d8a", "trace_id": null, "details": null}}
{"status": 429, "headers": {"retry-after": "60"},
 "body": {"error_code": "rate_limited", "message": "Too many requests; retry in 60 s.", "request_id": "eb09424ba575452b82e69bba38fa7778", "trace_id": null, "details": null}}
{"status": 422, "body": {"error_code": "validation_error", "message": "The request does not match the API schema.", "request_id": "9886d7c95fd049bcbb00f6bd96feacae", "trace_id": null,
 "details": [{"loc": ["body", "evidence"], "type": "extra_forbidden", "msg": "Extra inputs are not permitted"}]}}
{"status": 413, "body": {"error_code": "input_too_large", "message": "The conversation exceeds the configured input limits; nothing was processed.", "request_id": "23406fc05e674d49ac6418a6b5d7318b", "trace_id": null,
 "details": ["customer message has 2500 characters (max 2000)"]}}
```

## Timeouts and time budget

- **Budget.** Every `/resolve` execution runs under `RESOLVEAI_REQUEST_BUDGET_S`: 45 s in `production`, 60 s by default.
- **Per model call.** Each call gets `min(30 s, remaining budget)`, enforced by the client on a worker thread; a call is not started
  with less than 2 s left.
- **Retries.** There is one bounded retry; the OpenAI SDK's own retries are disabled.
- **Queue.** Waiting for the single execution slot is bounded by `RESOLVEAI_QUEUE_TIMEOUT_S` (20 s in `production`, 30 s by
  default), then 429 `agent_busy`.
- **Console.** The console's forwarder has its own timeout (`RESOLVEAI_PROXY_TIMEOUT_MS`, default 190 s).

## Rate limits

Rate limits are in-process sliding 60-second windows. They are **not shared across processes or hosts**, and `/config` says so
(`rate_limit_scope: process-local`).

| Limiter | Default (development / production) | Setting | Key | Response |
|---|---|---|---|---|
| resolve | 60 / 30 per minute | `RESOLVEAI_RATE_LIMIT_PER_MINUTE` | principal, or client address when auth is off | 429 `rate_limited` + `Retry-After` |
| read | 600 / 300 per minute | `RESOLVEAI_READ_RATE_LIMIT_PER_MINUTE` | principal, or client address | 429 `rate_limited` + `Retry-After` |
| failed authentication | 30 per minute | `RESOLVEAI_AUTH_FAILURES_PER_MINUTE` | client address | 429 `rate_limited` + `Retry-After` |
| execution slot | 4 waiting | `RESOLVEAI_MAX_QUEUE`, `RESOLVEAI_QUEUE_TIMEOUT_S` | — | 429 `agent_busy` + `Retry-After` |

## Trace ids and request ids

- **Ids everywhere.** Both ids appear in the response body, in the `X-Request-ID` / `X-Trace-ID` headers and in the trace.
- **Lookup.** `GET /api/v1/traces/{trace_id}` returns the audit trace. Trace ids are validated as 32 hex characters, and the store
  reads only its own directory.
- **Contents.** A trace holds request id, pipeline and component versions, config hash, request metadata (channel, locale), the
  final decision, per-stage status and latency, model usage (calls, cache hits, tokens, retries, timeouts, errors, budget
  refusals), `budget_s`, classified `failures` and the ordered decision events.
- **Never stored:** customer text, evidence text or model reasoning.
- **Corrupted lines.** Unreadable trace lines are skipped and counted by the listing, and a corrupted record is never served.

```json
{"trace_id": "957e30e635044fe69b875174fc2be03e", "request_id": "doc-example-auto_handle", "pipeline_version": "pipeline-v6.1", "config_hash": "9bd0d4ce163d6c6d",
 "request_meta": {"channel": "twitter", "locale": "en-US"}, "final_decision": "AUTO_HANDLE", "failures": [], "budget_s": 60.0,
 "event_names": ["request_received", "pii_redacted", "injection_checked", "context_built", "intent_predicted", "retrieval_started", "retrieval_completed",
                 "evidence_evaluated", "risk_flags_extracted", "escalation_decided", "draft_generated", "response_verified", "output_allowed", "response_returned"]}
```

The captured trace's intent stage took 34.8 s because it was the first request after the agent loaded, which includes model
warm-up. Warm requests take tens of milliseconds without model calls; see `artifacts/final/performance/perf_final.md`.

## Safe failure behaviour

A failure never produces an unguarded reply.

| Failure | HTTP | Result |
|---|---|---|
| Risk model times out, fails or returns invalid JSON | 200 | deterministic rules only (the measured safety floor); risk stage `fallback` |
| Intent second opinion fails | 200 | the classifier's intent |
| Drafting or verifying model times out, or the budget is spent | 200 | `HUMAN_HANDOFF`, reason `model_timeout` |
| Model outage or invalid output while drafting or verifying | 200 | `HUMAN_HANDOFF`, reason `llm_unavailable` |
| Retrieval, embedding, classifier or verifier crash | 200 | `HUMAN_HANDOFF`, reason `dependency_failure`, rule `dependency:<stage>` |
| Trace cannot be written | 200 | an automatic reply is withheld: `HUMAN_HANDOFF`, reason `audit_unavailable` |
| Prompt injection detected | 200 | `HUMAN_HANDOFF`, reason `prompt_injection`, 0 model calls |
| Agent not loaded | 503 | `agent_not_ready` / `agent_unavailable` |
| Unexpected error | 500 | `internal_error`; the log carries the exception type, a redacted message and code locations |

Each failure is recorded as `failures: [{category, stage, kind}]` (codes only) with `model_call_failed` or `dependency_failed`
events.

## The evidence invariant at the API

**NO SUFFICIENT EVIDENCE → NO AUTONOMOUS CUSTOMER REPLY.**

Inside the agent, the output gate allows `AUTO_HANDLE` only when every check passes:
- policy allows automation, and no blocking risk flag is raised;
- intent confidence is acceptable, and evidence is sufficient;
- a draft exists and was verified, and its evidence references exist;
- the reply passes the PII guard and the schema.

The API re-checks these conditions independently (`resolveai/api/presenter.py`). An automatic reply with insufficient evidence,
missing or unknown references, failed verification, a policy block or a hard risk flag returns 500
`autonomy_invariant_violation`; the violation names are recorded and the reply text is not returned. Templates (the language
redirect and closures) need no evidence but must still pass the gate.

## Security notes

- **PII.** Customer text is redacted before storage, embedding, any model call or any trace write. Responses echo only the
  redacted conversation.
- **Prompt injection.** Customer and caller-supplied brand turns are untrusted data. A detection is a hard block before any model
  call. Retrieved historical text that reads as instructions is quarantined (`evidence.quarantined_ids`), and evidence text is
  redacted again.
- **Evidence spoofing.** The request schema forbids extra fields; evidence items are always knowledge-base rows.
- **CORS.** Explicit origins only; wildcards are rejected in every profile.
- **Secrets.** Keys live in the environment or the gitignored `.env`. `/config` never returns a key, a token, the base URL or an
  absolute path.
- **Not implemented** (see `docs/PRODUCTION_READINESS.md`):
  - TLS;
  - per-user identity, token rotation and revocation;
  - a shared rate-limit store;
  - trace retention and encryption at rest.

## Operations

```bash
curl -s http://127.0.0.1:8000/api/v1/health
curl -s http://127.0.0.1:8000/api/v1/ready                                      # anonymous: component booleans only
curl -s -H "Authorization: Bearer <read token>" "http://127.0.0.1:8000/api/v1/traces?limit=20&action=HUMAN_HANDOFF"
curl -s -H "Authorization: Bearer <read token>" http://127.0.0.1:8000/api/v1/traces/<trace_id>
python scripts/verification/release_checks.py api-smoke                          # live checks in the production profile
```

- **Readiness.** `/ready` reports agent state, knowledge-base rows and indexes, the classifier artifact, gate and policy versions,
  trace-store writability, and whether a model is configured. It never contacts the model.
- **Trace listing.** List items carry intent, confidence and band, evidence level, risk flags, policy rule and version, channel,
  model-call count and `estimated_cost_usd` (list-price estimate summed from the trace's usage records; `null` when no model usage
  was recorded), all read from recorded events. The listing reads each day's file backwards from the end and stops at `limit`:
  200 rows over a 20,000-trace (108 MB) file take 63 ms p50, against 629 ms when the file was read whole.
- **Evaluation summary.** `/evaluation/summary` serves the frozen Phase 6 evaluation artifacts as stored.

## Read-only console endpoints

Three endpoints exist only so the console can show release results, configuration and corpus facts. None runs the agent, calls a
model, recomputes a metric or offers another path to a customer reply: `POST /resolve` stays the single agent entry point, and
every automatic reply still passes the evidence gate, policy, verification, output gate and trace.

| Endpoint | Returns | Source | Errors |
|---|---|---|---|
| `GET /api/v1/evaluation/release` | `golden` (FROZEN GOLDEN SET: release metadata, the metric table with 95% intervals and paired differences against B2, B1 and the Phase 9 run, evidence levels, failure modes, judge attribution without response text, human-evaluation status, per-intent outcomes), `dev_experiments` (DEV EXPERIMENTS: the pre-registered risk corroboration decision and scores), `performance` (profile on dev requests), `checks` (adversarial suite, API smoke, verification, clean environment), `limitations`, `provenance` | `artifacts/final/*`, `artifacts/product/release_by_intent.json` | 404 `evaluation_not_available` |
| `GET /api/v1/agent/profile` | `agent` (state, brand, versions, model name and role), `active` (agent config, retrieval config, evidence-gate thresholds, rerank weights, second-opinion policy, request budget), `evaluated` (release run config and `differences` from active), `policy` (version, confidence floor, always-handoff intents, clarifiable gaps, `rules` in check order), `allowed_actions`, `not_allowed` | the loaded agent; `resolveai/policy/escalation.py` `POLICY_RULES`; `final_release.meta.json` | 503 `agent_not_ready` / `agent_unavailable` |
| `GET /api/v1/knowledge/summary` | row counts (substantive, move-to-DM, resolution-bearing), date range, per weak-intent shares, reply action classes, outcome signals, manifest (corpus hash, preprocessing, leakage boundary), index facts, definitions | the loaded knowledge base (computed once, cached in the process) | 503 while the agent loads |

- **Text.** `evaluation/release` serves example golden messages (already public tweets) PII-redacted again and truncated to 240
  characters; the judge's changed-row responses are not served. The other two endpoints return no message text at all.
- **Policy rule list.** `POLICY_RULES` is data next to `decide()`; `tests/test_product_api.py` asserts that it names the same
  rules, in the same order, as the code checks.
