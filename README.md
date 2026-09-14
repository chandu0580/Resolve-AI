# ResolveAI

**ResolveAI 1.0.0 is a complete enterprise-style reference implementation for a governed, grounded AI customer-support agent.**
For every customer message it decides whether a verified, evidence-backed reply is allowed, whether to ask one clarifying question,
or whether a person must take over, and it shows exactly why.

> **Model proposes → evidence grounds → policy decides → verifier checks → humans own the exceptions.**

It is a reference implementation, not a deployed service: it runs locally with Python and Node.js, and the gaps an enterprise
deployment would still close are listed in `docs/PRODUCTION_READINESS.md`. Blinded human validation is complete (50 of 50 rated, see `artifacts/evaluation/judge_agreement.md`).

## Reproduce the headline results (target: under 15 minutes)

Two commands, no API key, no network after install, no model call, and the 3M-row Kaggle file is not needed.

```bash
pip install -r requirements.txt          # measured: 358 s into a fresh virtual environment
python scripts/evaluate.py --cached      # measured: 188 s
```

This recomputes every headline number in §11 from the committed run records and prints them, and rewrites the tables under
`artifacts/evaluation/`. It verifies the golden set's SHA-256 before it starts and refuses to run if it changed.

Measured on an 8-core Windows laptop with Python 3.13: **9 minutes 17 seconds end to end** (10 s to create the virtual
environment, 358 s to install, 188 s to evaluate). Caveats stated rather than hidden: install time depends on your network and
pip cache — torch is the large download — and this machine's pip cache was warm. The evaluation step itself was verified to need
**no** model download: run with an empty, isolated `HF_HOME` it fetched 0 bytes, made no network call and needed no API key.

On Windows, keep the checkout out of a deeply nested directory or enable long-path support; torch's own paths are long enough to
hit the 260-character limit, which surfaces as an `OSError` from pip rather than anything to do with this project.

To check that the regeneration is byte-identical rather than merely re-run, use
`python scripts/verification/final_verification.py`, which replays it into a scratch directory and compares all 11 result files.

### Reviewer Quick Reference: Where to find required deliverables

| Deliverable | Location in Repository |
|---|---|
| **Headline Results** | [§11 Evaluation results](#11-evaluation-results) & `artifacts/final/final_metrics.md` |
| **Baseline Comparisons** | `artifacts/evaluation/baseline_comparison.md` & `artifacts/final/FINAL_REPORT.md` §5 |
| **Human-vs-Judge Agreement** | `artifacts/evaluation/judge_agreement.md` (50/50 human ratings complete) |
| **Top 5 Failure Modes** | `artifacts/final/FINAL_REPORT.md` §6 & `artifacts/final/failure_modes.json` |
| **What is Misleading** | `artifacts/final/FINAL_REPORT.md` §7 & `artifacts/evaluation/misleading_headline.md` |
| **Decision Log (10–15 decisions)** | `docs/DECISIONS.md` (12 foundational decisions with empirical measurements) |
| **Product & Interactive Demo** | `python scripts/demo.py` & `docs/DEMO.md` |
| **Full Hiver Final Report** | `artifacts/final/FINAL_REPORT.md` (concise 4-page report) |

## 1. What is ResolveAI?

A support agent (FastAPI) plus an operator console (Next.js), built for AppleSupport on the public Kaggle *Customer Support on
Twitter* dataset. The agent answers a customer only when historical support replies show how the same issue was resolved. Otherwise
it asks one question or hands the conversation to a human with everything they need. The console lets support operations, AI
engineers and security reviewers see and audit every decision.

## 2. What problem does it solve?

The obvious build is one LLM prompt, and it answers too much. On the frozen 197-message golden set, a direct-LLM baseline answered
151 messages. 3 of those went to customers who needed a human, and an LLM judge flagged 53% of its responses for unsupported claims.
ResolveAI answered 12 automatically, none of them to a customer who needed a human. The price is stated openly: 75 unnecessary
handoffs.

## 3. Why AppleSupport?

Chosen by measurement, not preference. All 108 brands in the dataset were scored on eight criteria under six weightings
(`artifacts/brand_analysis/`). The numeric leaders — Tesco, SpotifyCares, British Airways — resolve almost everything by asking
for an order or account number, so nothing in their corpus can be answered automatically and there is no grounding to learn from.
A reply-type analysis showed only consumer-tech brands have a real troubleshooting corpus. AppleSupport has the largest (about
10,000 troubleshooting replies) and a 56% handoff rate, which makes "answer or escalate" a genuine decision rather than a foregone
one. AskPlayStation is the documented runner-up. The honest caveat, stated in `docs/DECISIONS.md` #1: the decisive criterion was
added after a qualitative read of the data, so both the original ranking and the revised one are reported.

## 4. Why is it different from a normal chatbot?

- **The model has no unrestricted authority.** GLM-5.2 proposes: an intent second opinion, risk flags, a draft from cited evidence
  and a support check. It never decides escalation. In the Phase 1A benchmark every model's escalation accuracy was at or below a
  never-escalate baseline.
- **Evidence determines what can be said.** No sufficient historical evidence means no automatic reply, enforced in five places.
- **Policy determines what can be done.** 27 ordered deterministic rules; the first match names the reason.
- **Verification decides whether the output is acceptable.** Lexical and model checks, then a nine-check output gate, then an
  independent API re-check.
- **Humans own the exceptions.** Risky, sensitive, unclear and unsupported conversations go to a person with a handoff packet.
- **Every decision is observable.** One trace per execution, and an explanation built from the decision record, never from the model.

## 5. Architecture

```text
Customer message (+ earlier turns)                          POST /api/v1/resolve  (the only path to a reply)
  ↓  TRUST          PII redaction · prompt-injection hard block · Unicode/case-normalised matching
  ↓  INTELLIGENCE   bounded context · BGE-small + calibrated intent classifier · greetings / thanks / "talk to a person" recognised
  ↓  RETRIEVAL      17,875 earlier AppleSupport cases · resolution rerank · quarantine of instruction-like history
  ↓  EVIDENCE GATE  INSUFFICIENT / WEAK / SUFFICIENT / STRONG
  ↓  POLICY         risk flags (rules, or a model that can add but never clear) · 27 ordered rules, first match wins
  ↓  GENERATION     grounded draft (SUFFICIENT/STRONG only, must cite cases) | fixed template | clarifying question | handoff packet
  ↓  VERIFICATION   coverage + model support check · output gate (9 checks) · API invariant re-check
  ↓  ACTION         AUTO_HANDLE | CLARIFICATION_REQUIRED | HUMAN_HANDOFF
  ↓  TRACE          ids, versions, stage statuses, latencies, decision data; never customer text or model reasoning
```

The CLI, the demo and the evaluation call the same orchestrator; no other route produces a reply (`docs/ARCHITECTURE.md` §11).

## 6. How grounding works

A reply may only use historical AppleSupport replies that meet three conditions:
- written **before** the customer's message;
- stating an instruction or a released fix;
- agreeing with each other: gate-v3 needs at least 3 independent, consistent cases for SUFFICIENT or STRONG.

The draft must cite those cases. The verifier checks that the reply's wording is covered by them, that every citation was actually
retrieved, and that no URL, PII or promise was added. The console separates **evidence used in the response** from **retrieved
evidence**, and says "ResolveAI did not find sufficient historical evidence to safely answer" when that is the case. It never
shows "Grounded" otherwise.

A grounding audit of every automatic reply in the release run passes (`scripts/evaluation/grounding_audit.py`). Grounded is not the
same as correct: whether the fix worked for the customer is not measured.

## 7. How safety works

- **Fails safe.** A model timeout, model outage, dependency crash or unwritable audit trail becomes a classified human handoff, never
  an unverified reply. A live outage returned HTTP 200 with a handoff.
- **Untrusted input stays data.** Injection attempts in customer text are a hard handoff with 0 model calls. That includes
  full-width letters and zero-width characters. Instruction-like historical text is quarantined, and the request schema rejects
  supplied evidence or actions.
- **The same words behave the same.** Capitalization, spacing, punctuation and Unicode width never change a decision
  (`docs/ARCHITECTURE.md` §12).
- **Tested.** A 20-case adversarial suite, a capitalization and conversation suite, API and browser smokes, and a grounding audit.

## 8. How human handoff works

These conversations go to a person with a packet:
- safety, security, legal, abusive, account, billing, private-information, hardware and repeat-contact cases;
- explicit requests for a person;
- anything the evidence cannot support.

The packet carries:
- the issue, conversation summary and context, what ResolveAI tried, intent, risk flags;
- the evidence found and the evidence missing, unresolved questions, the recommended next step, and any draft that verification
  rejected.

The customer only sees a holding line ("a member of our team will pick this up with you directly"), never an answer. Operators
work the Handoff Center, a queue by severity and fixed category, and can copy a PII-scrubbed summary into a ticket.

## 9. How to run it

Python 3.11+ and Node.js 20.9+. No Docker, no private infrastructure, no raw 3M-row dataset.

```bash
python -m venv .venv && . .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env                                   # optional: LLM_API_KEY, LLM_BASE_URL, LLM_MODEL (OpenAI-compatible; evaluated with GLM-5.2)
python -m resolveai serve                              # API on http://127.0.0.1:8000 (development profile, no auth, Swagger at /docs)
cd frontend && npm ci && npm run dev                   # console on http://localhost:3000
```

- **Without a model key** everything runs on the deterministic path: handoffs and clarifications instead of drafts.
- **First run** downloads BGE-small and embeds 17,875 cases, about 8 minutes on CPU, then cached. The first request after each start
  takes 20–70 s while models load.
- **Production profile:** `RESOLVEAI_API_TOKEN=<32+ random characters> python -m resolveai serve --env production`, then
  `cd frontend && npm run build && RESOLVEAI_API_TOKEN=<same token> npm start`. The token stays on the console server.
- **CLI:** `python -m resolveai "my iphone battery drains fast"`, or `python -m resolveai demo` for seven scripted scenarios.

## 10. How to use the console

| Page | Use it to |
|---|---|
| **Overview** | See live operations (this environment's traces) apart from evaluation results, plus honest warnings |
| **Conversations** | Open a conversation: list · thread and timeline · decision, "Why did ResolveAI do this?", evidence |
| **Handoff Center** | Work the queue; read the packet; copy the summary |
| **Simulator** | Run the curated demo path or any message; nothing is sent to a customer |
| **Knowledge Center** | Corpus facts, evidence quality, measurable knowledge gaps |
| **Agent configuration** | The running configuration next to the evaluated one, and the 27 ordered policy rules (read-only) |
| **Evaluation Center** | Release scorecard with intervals, failure modes, judge attribution, human-validation status |
| **Trace Explorer** | What happened, why, how long, what failed, what evidence, stage by stage |
| **Trust & Governance** | Ten controls with status, enforcement point, threat, code and tests |
| **Settings** | Credential presence (never values), limits, browser storage |

The ten-minute walkthrough is `docs/DEMO.md`; the console is described in `docs/UI.md`.

## 11. Evaluation results

**How the golden set was built and labelled — read this first.** 197 messages sampled from a temporal holdout (2017-11-28 to
12-03) that is never indexed, stratified by intent, thread length and edge case (`golden_freeze_manifest.json`).
**The 197-row golden evaluation set is 100% hand-labelled by the human project owner** via `scripts/golden_label_ui.py`
(`data/golden/golden_human_labels.csv` promoted to `golden_final.csv`, SHA-256 `62f1156a4ec18be822d4a26a1ef09ad98dda877e6789609fc46926e4655035e1`).
The prior AI-assisted passes (Claude A/B with v1.1 rules) are preserved in `data/golden/golden_ai_adjudicated_v11.csv` as an
auditable historical baseline (human-AI agreement: 97.5% intent $\kappa = 0.972$, 97.5% escalation $\kappa = 0.921$).
The set is frozen and hash-verified on every load. Each system was run on it once, and nothing was tuned on it.
Release 1.0.0 against the direct-LLM baseline (95% bootstrap intervals; paired differences, `*` excludes zero; `artifacts/final/final_metrics.md`):

| Metric | ResolveAI 1.0.0 | Direct LLM (B2) | Difference |
|---|---|---|---|
| Escalation recall | **0.951** [0.878, 1.000] | 0.854 | +0.098 [+0.000, +0.209] |
| Escalation precision | 0.351 [0.261, 0.440] | **0.761** | −0.409 * |
| Escalation F1 | 0.513 [0.411, 0.601] | **0.805** | −0.291 * |
| Unsafe automatic replies | **0** of 12 | 6 of 151 | −6 [−11, −2] * |
| Safe automatic replies | **12** (6.1%) | 0 | +0.061 * |
| Intent macro-F1 | 0.831 [0.771, 0.884] | 0.853 | −0.022 (not distinguishable) |
| Judge hallucination rate | **0.367** | 0.526 | −0.172 * |
| Model calls / est. cost per message | 1.54 / $0.0026 | 1.07 / $0.0024 | +0.47 * / +$0.0002 |

- **Read before quoting.**
  - "0 unsafe" is out of 12 automatic replies.
  - Recall rests on 41 positives.
  - **100% human-labelled golden set** (197 rows) + **genuinely human-rated judge study** (50 rows).
  - The direct LLM achieves higher F1 but sends 6 unsafe replies.
- **Which version was evaluated.** These numbers describe the evaluated pipeline (`pipeline-v6.1` / `policy-v3.1`). The running
  product is `pipeline-v6.3` / `policy-v3.3`: greetings, requests for a person, short replies, capitalization, a language redirect
  that obeys the confidence floor, and non-Latin scripts recognised deterministically. The golden run was not repeated; 21 of 197
  golden rows reach a changed code path (`scripts/evaluation/behaviour_change_impact.py`).
- **Latency.** Live latency on dev messages is p50 4.2 s / p95 14.2 s. Without the model it is 173 / 374 ms
  (`artifacts/final/performance/perf_final.md`).

## 12. Known limitations

- **Evaluation scope.** Golden set is 197 rows (100% hand-labelled by human owner) from one November 2017 burst; while golden and the 50-row judge validation study are human-labelled, silver training and dev experiments use weak labels.
- **Over-escalation.** 72 unnecessary handoffs on golden, and a low automatic rate (6.1%).
- **The release judge scores describe wording the product no longer sends.** Two handoff lines asserted damage or steps the
  customer never described; they are fixed (DECISIONS #118) and the golden run was not repeated, so the 0.367 hallucination
  rate still describes the old text.
- **Small, narrow evaluation.** 197 rows from one November 2017 burst; only 7 reach STRONG evidence.
- **Shallow detectors.** Regex PII detection misses names and addresses; injection detection is pattern-based.
- **Evaluated and running pipelines differ** (above).
- **Model outages are slow to hand off.** An outage takes about 40 s to become a handoff while calls time out.
- **Not a deployment.**
  - One process with process-local rate limits.
  - File-based traces.
  - No TLS, operator login, metrics, retention or runbooks.

## 13. Security

- **Access.** Bearer tokens with `resolve` and `read` scopes, checked before the body is read. Missing and wrong credentials get
  the same 401; 403 for a wrong scope; 429 with `Retry-After`. Body and conversation limits apply.
- **Secrets.** Keys live in the environment or the gitignored `.env`. `/config` never returns a key, token, base URL or path. The
  console attaches its token server side, and the browser never receives a credential.
- **Privacy.** PII is redacted before any model call, trace or log. Traces store ids, versions and decision data, never customer
  text or reasoning. The console keeps already-redacted results in the operator's browser, disclosed and clearable.
- **Evidence.** The security scan checks every committable file for secrets, credential patterns, the model endpoint and PII in
  traces.
- **Not implemented.** TLS, SSO, token rotation, dependency scanning (`docs/PRODUCTION_READINESS.md`).

## 14. Project structure

```text
resolveai/            the agent package
  trust/              PII redaction, injection detection, canonical text normalization
  intelligence/       context builder, intent classifier, conversation acts, query builder
  retrieval/          knowledge base, dense index, rerank, evidence gate (frozen gate and rerank configs)
  policy/             deterministic escalation policy (ordered rules)
  agent/              orchestrator, risk flags, drafter, verifier, output gate, clarification, handoff
  llm/                model client (timeouts, budget, classified failures, SHA-256 response cache)
  observability/      trace recorder and store
  api/                FastAPI app, auth, limits, routes, read-only console views
  evaluation/         harness, metrics, bootstrap, judge (never imports agent decision logic)
  schemas/ models/ data/ config/
frontend/             Next.js operator console (no agent logic; types generated from the API's OpenAPI document)
tests/                backend tests: unit, API, adversarial suite, capitalization and conversation suite, input robustness
scripts/              verification/ and evaluation/ (product entry points), evaluate.py, security_scan.py;
                      final/ and phase0–phase9/ (release and development history, cited by frozen artifacts)
docs/                 ARCHITECTURE · API · UI · DEMO · EVALUATION · PRODUCTION_READINESS · DECISIONS · INTERVIEW_NOTES · REPRODUCIBILITY · INTENTS · HUMAN_JUDGE_GUIDE
data/                 golden/ (frozen) · human_eval/ (rating packet) · processed/ (committed 20k-pair subsample) · dev/ · demo/
artifacts/            final/ (results of record and final reviews) · product/ (product and hardening evidence) · earlier phase evidence (frozen)
```

- `scripts/README.md` explains every script folder.
- `artifacts/final/ARTIFACT_MAP.md` classifies artifacts as frozen, final, mutable or deprecated.
- `artifacts/final/FINAL_REPOSITORY_REVIEW.md` has the exact verification commands and results.

## Verify it

```bash
python -m pytest -q && ruff check .
cd frontend && npm run lint && npm run typecheck && npm test && npm run build && cd ..
python scripts/verification/final_verification.py        # golden hash, frozen files, cached evaluation, security scan (no model, no key)
python scripts/verification/release_checks.py adversarial   # 20-case adversarial suite
python scripts/verification/release_checks.py api-smoke     # production profile over live HTTP
python scripts/verification/input_robustness.py            # 53 awkward input classes + 15 malformed API bodies
python scripts/evaluation/grounding_audit.py              # automatic replies ↔ evidence ↔ citations ↔ verification ↔ trace
cd frontend && npm run smoke                              # browser smoke against a running stack (Edge + axe-core)
```

## Dataset

Kaggle `thoughtvector/customer-support-on-twitter`, used under its Kaggle licence. The raw file is never committed or modified;
customer handles are anonymised by the dataset author and PII is redacted again before storage. Banking77
(`PolyAI/banking77`) was offered as an optional intent resource and deliberately **not** used: it is banking vocabulary with 77
fine-grained intents that would not transfer to consumer-tech support (DECISIONS #6 in the summary below).

## Credits and citations

Everything borrowed, and what it is used for. No code was copied from another project; these are libraries, models and datasets
used through their public interfaces.

| What | Used for | Source |
|---|---|---|
| Customer Support on Twitter | the entire corpus, knowledge base and golden set | Kaggle `thoughtvector/customer-support-on-twitter`, Kaggle licence |
| BGE-small-en-v1.5 | sentence embeddings for intent classification and retrieval | BAAI, via `sentence-transformers` (MIT), model weights MIT |
| GLM-5.2 | risk flags, intent second opinion, drafting, verification, and the evaluation judge | Z.ai, through an OpenAI-compatible endpoint (`openai` SDK, MIT) |
| qwen3.8-27b | second-family judge, as the self-preference control | Groq, through an OpenAI-compatible endpoint |
| scikit-learn | calibrated logistic regression, Cohen's kappa | BSD-3 |
| scipy | Spearman correlation | BSD-3 |
| `rank-bm25` | the BM25 retrieval baseline measured in Phase 2 | Apache-2.0 |
| faiss-cpu | evaluated as an index backend; the shipped retriever uses exact in-memory search instead | MIT |
| pandas, numpy, tqdm, typer, python-dotenv, kagglehub | data handling, CLI, configuration, dataset download | BSD-3 / MIT |
| FastAPI, uvicorn, pydantic | the HTTP service, validation and the OpenAPI document | MIT / BSD-3 |
| Next.js, React, Tailwind CSS, lucide-react | the operator console | MIT |
| `openapi-typescript` | generates the console's types from the served OpenAPI document | MIT |
| vitest, Testing Library, jsdom, playwright-core, axe-core | frontend tests, browser smoke, accessibility checks | MIT / Apache-2.0 |
| pytest, ruff, httpx | backend tests, linting, the test HTTP client | MIT |

Method references: quadratic-weighted Cohen's kappa and bootstrap confidence intervals are standard statistics, implemented here
directly (`resolveai/evaluation/agreement.py`, `bootstrap.py`) rather than taken from a framework. The evaluation rubric,
annotation guide and escalation policy are written for this project.

AI assistance: this repository was built with an AI coding assistant. The final golden evaluation set (197 rows) was independently hand-labelled by the human project owner via the custom labelling studio (`data/golden/golden_human_labels.csv` promoted to `data/golden/golden_final.csv`), with the prior AI-assisted annotation passes preserved in `data/golden/golden_ai_adjudicated_v11.csv` as an auditable historical artifact. Independent human ratings were also collected for the 50-example LLM-judge validation study (`data/human_eval/human_scoring_packet.csv`).

## Submission Details

- **Assignment**: Hiver SDE Intern Take-Home Assessment
- **Submission Destination**: Repository link submitted to `anurag@hiverhq.com`
- **Candidate Implementation**: Complete governed, evidence-grounded reference implementation with reproducible evaluation harness and interactive console.
