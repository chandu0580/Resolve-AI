# ResolveAI 1.0.0: final repository review

**Positioning.** ResolveAI 1.0.0 is a complete enterprise-style reference implementation for a governed, grounded AI
customer-support agent. It is not production-ready: `docs/PRODUCTION_READINESS.md` lists 55 items (21 READY, 23 PARTIAL, 11 NOT
READY), and passing tests does not change that.

**Scope of this pass.** A repository audit, then only justified fixes:
- capitalization and text normalization;
- greetings, requests for a person and short replies;
- console search and filters;
- script organization, documentation, and the full verification suite.

No new phase was started. The architecture, FastAPI backend and Next.js console were kept, and no framework or Docker was added.
The evidence gate, deterministic policy, verifier, trust layer and human handoff were not weakened. Nothing was tuned on the golden
set, no evaluation result was fabricated, and nothing was committed or pushed.

> **Superseded in part on 2026-09-12.** A later release-readiness pass ran a full assignment audit, added an input-robustness
> suite and fixed three more product defects (`pipeline-v6.3` / `policy-v3.3`). Its results are in
> `FINAL_ASSIGNMENT_AUDIT.md` and `FINAL_RELEASE_CHECKLIST.md`; the test counts, file counts and rule counts below were refreshed
> where they are still quoted as current, and the structural findings stand.

## 1. Final architecture

```text
Customer → TRUST → INTELLIGENCE → RETRIEVAL → EVIDENCE GATE → POLICY → GENERATION → VERIFICATION → ACTION → TRACE
           model proposes · evidence grounds · policy decides · verifier checks · humans own the exceptions
```

- **One path to a reply.** `POST /api/v1/resolve`, the CLI, the demo and the evaluation harness call the same `ResolveAI.resolve`;
  drafting is called only inside the orchestrator after the policy allows it.
- **Read-only routes.** Every other route only reads.
- **Baselines stay offline.** The direct-LLM and simple-ML baselines exist only in `resolveai/evaluation/`.
- **Audited in this pass.** `grep` of every `.resolve(` call and drafter call, plus the route table (`docs/ARCHITECTURE.md` §11).
- **Invariants still hold** (tests):
  - no automatic reply without sufficient evidence;
  - no citation that was not retrieved;
  - the model cannot clear a rule flag or bypass verification or the output gate;
  - an automatic reply breaking the invariant is withheld by the API.
- **Covered by:**
  - `tests/test_final_adversarial_suite.py` (malicious model output, retrieved injection, spoofed evidence);
  - `tests/test_api.py` (spoofed evidence field, invariant re-check);
  - `tests/test_case_and_conversation.py` (spoofed `action` field, context cannot override a hard block).

## 2. Audit findings and what was done

| Finding (measured) | Classification | Action |
|---|---|---|
| The no-model agent on five casings of 7 messages: intent, confidence, retrieval and evidence identical (the BGE tokenizer lower-cases). One case-dependent rule: `_SHOUTING` (all-caps word of 6+ letters) and `!!!` raised `high_frustration`. "THANKS" was handed off while "thanks" got the closing template, and "AGENT PLEASE" was treated as hostile. | defect | Removed both signals; frustration is read from words (DECISIONS #108) |
| "hi", "HELLO", "good morning" retrieved 50 cases and returned a device/version questionnaire | UX defect | Greeting-only rule `canned:greeting`: fixed greeting, retrieval, second opinion and risk-model call skipped (#110) |
| "can I talk to a human" got a questionnaire; "I want to speak to a real person" was handed off as "No proven resolution"; "yes" answering an agent question got "You're welcome!" | UX defect | `human_requested` handoff reason; thanks vs bare acknowledgement separated (#111) |
| "still happening" after a battery complaint was classified `other` and handed off as "not a support request"; "that didn't work" became a keyboard bug. The context builder joined short replies to their issue, but the orchestrator embedded only the current message for the classifier. | defect | A short reply with an issue is classified with the issue text; short-reply patterns cover "(it) still doesn't work" (#112) |
| Injection detection could be split by zero-width characters or full-width letters | hardening gap | Canonical matching key (NFKC, format characters removed) for injection, risk rules and conversation acts; original text untouched (#109) |
| PII serial pattern is upper-case only | kept by decision | A case-insensitive version newly matched 157 of 20,000 knowledge-base messages, almost all product hashtags ("iphone7plus"); documented and pinned by a test |
| API: an upper-case trace id returned 400; `?action=auto_handle` returned 422; `--env PRODUCTION` was rejected | inconsistency | Canonical forms at the boundary (lowercase hex id, upper-case enum, lower-case profile) |
| Console: URL filters were exact-case; search lower-cased but did not fold Unicode width or invisible characters | inconsistency | `frontend/lib/text.ts` `foldForMatch`; `parseRowFilter`; traces `?action=` normalised |
| Product scripts sat in one `scripts/product/` folder with letter prefixes | organization | Moved to `scripts/verification/` and `scripts/evaluation/` with descriptive names; `scripts/README.md` added |
| `frontend/artifacts/product/hardening/behaviour_change_impact.json`: an outdated duplicate written to a relative path during this pass's first impact check | temporary output | Removed |
| Tests pinned `policy-v3.1` literally | brittle test | Pinned to the constant, or updated to `policy-v3.2` where the version itself is asserted |

### Case-sensitivity decisions by use case

| Use case | Decision |
|---|---|
| Intent classification, dense retrieval | no change needed: the tokenizer lower-cases (identical token ids verified) |
| BM25, weak labels, verifier, resolution checks, clarification slots, closure matching | already lower-cased or `re.I` |
| Injection detection | NFKC + format characters removed + `re.I`; line breaks kept (a line-anchored pattern) |
| Risk rules | NFKC + format characters removed + `re.I`; capitals and "!" never a signal |
| Greetings, thanks, acknowledgements, requests for a person | NFKC + casefold + punctuation/emoji removed |
| PII email, phone, card, order id | already case-insensitive by construction |
| PII serial / IMEI / case id | exact upper case, by measured decision |
| Signature initials stripping (`^JD` at the end of a tweet) | exact case, correct: brand signatures are initials |
| Model output (risk flag names, intent labels, evidence labels) | flag names already normalised; intent labels validated against the taxonomy; unknown labels dropped |
| API trace id, `action`, profile names | canonical form |
| Auth scheme, header names | already case-insensitive |
| Console search, filters | folded key; displayed text unchanged |

## 3. Behaviour change after the evaluation, stated plainly

- **Evaluated versus running.** Release 1.0.0 was evaluated once on the frozen golden set with `pipeline-v6.1` / `policy-v3.1`. The
  running product is now `pipeline-v6.2` / `policy-v3.2`.
- **Not re-run.** The golden run was **not** repeated: the single-run protocol stands, and re-running to check a fix would start
  tuning on golden.
- **What was measured instead.** `scripts/evaluation/behaviour_change_impact.py` reports, from the customer messages and threads
  only (no model, no annotations), which golden rows reach a changed input path:
  - 6 lose a capitals- or "!"-only frustration flag;
  - 12 are short replies now classified with their issue;
  - 0 are greetings, requests for a person, closures or injection-normalization changes.

  That is 21 of 197 rows.
- **What this means.** The golden numbers describe v6.1, and those 18 rows may decide differently today.
- **Where this is shown.** The Agents page lists the pipeline difference, the Overview shows a warning, and `docs/EVALUATION.md`
  §4, `docs/PRODUCTION_READINESS.md` and the scorecard state it.

## 4. UX improvements (this pass)

- **Agent behaviour.**
  - A greeting gets "Hi! What can we help you with today?".
  - "can I talk to a human" gets "Of course. A member of our team will pick this up with you directly." and a handoff packet.
  - Short replies keep their thread.
  - Capitals change nothing.
- **Console.**
  - Search and URL filters ignore capitalization, width and invisible characters.
  - The handoff packet shows "What ResolveAI tried" (cases searched, whether a draft was attempted and rejected).
  - The Overview warns when the running pipeline is newer than the evaluated one.
  - The Agents page lists that difference.
  - New labels: "Customer asked for a person", "No evidence needed: greeting only", "Retrieval skipped: nothing to look up".
- **Customer-visible text.** A test checks that replies across ten representative messages contain none of: rule names, versions,
  confidence values, model or retrieval terms, evidence ids or redaction tokens. Replies are at most 280 characters.

## 5. API improvements (this pass)

- **Single agent endpoint.** `POST /api/v1/resolve` remains the only agent endpoint; no route was added.
- **Case-insensitive identifiers.** Trace ids and the `action` filter accept any capitalization; profile names accept any
  capitalization in `--env` and `RESOLVEAI_ENV`.
- **New schema values.**
  - Reason code `human_requested`.
  - Evidence sufficiency reason `not_applicable` (greeting).
  - Trace event `retrieval_skipped`.
  - OpenAPI document and console types regenerated.
- **Spoofed actions rejected.** A request that supplies `action` is rejected with 422 (tested).
- **Unchanged stable contracts.** Malformed payloads, missing fields, wrong types, empty and over-long messages, Unicode,
  unauthorized, forbidden, rate-limited, model timeout, model unavailable and trace failure all keep their stable contracts, covered
  by the existing API, security, reliability and adversarial tests. No stack trace reaches a response.

## 6. Final folder structure

```text
/                     README.md · pyproject.toml · requirements.txt · requirements-dev.txt · .env.example · .gitignore
resolveai/            api · agent · intelligence · retrieval · models · policy · trust · llm · observability · evaluation · data · schemas · config
frontend/             Next.js operator console (app · components · lib · tests · scripts)
tests/                28 backend test modules
scripts/              verification/ · evaluation/ · evaluate.py · security_scan.py · README.md
                      final/ · phase0/ … phase9/  (release and development history, cited by frozen artifacts)
docs/                 ARCHITECTURE · API · UI · DEMO · EVALUATION · PRODUCTION_READINESS · DECISIONS · INTERVIEW_NOTES · REPRODUCIBILITY · INTENTS · HUMAN_JUDGE_GUIDE
data/                 golden/ · human_eval/ · demo/ · dev/ · processed/ (committed subsample; raw data gitignored)
artifacts/            final/ · product/ (product and hardening evidence) · earlier phase evidence (frozen)
```

Deviations from the target structure, and why:
- **`scripts/security/` not created.** `scripts/security_scan.py` stays at its path because frozen release artifacts and
  `scripts/final/f_final_verification.py` cite it.
- **`scripts/demo/` not created.** The demo is `python -m resolveai demo`.
- **`scripts/final/` and `scripts/phase*/` not moved.** Frozen artifacts cite their exact paths.
- **`artifacts/verification/` not created.** Any new folder under `artifacts/` is a new file in a frozen location for the release
  verification; verification outputs live in `artifacts/product/hardening/`.
- **Earlier phase artifact folders not renamed or merged.** They are hash-frozen evidence; moving them would break the integrity
  checks that prove they are unchanged.

## 7. Files moved, removed and retained

**Moved** (references updated in README, docs, scripts, frontend fixtures comment and the product reports):

| From | To |
|---|---|
| `scripts/product/a_release_by_intent.py` | `scripts/evaluation/release_by_intent.py` |
| `scripts/product/e_grounding_audit.py` | `scripts/evaluation/grounding_audit.py` |
| `scripts/product/b_capture_console_fixtures.py` | `scripts/verification/capture_console_fixtures.py` |
| `scripts/product/c_verify_product.py` | `scripts/verification/verify_product_pass.py` |
| `scripts/product/d_final_product_verification.py` | `scripts/verification/final_verification.py` |
| `scripts/product/f_release_checks.py` | `scripts/verification/release_checks.py` |

The JSON verification records written before the move (`artifacts/product/verification.json`,
`artifacts/product/hardening/verification*.json`) keep the old paths as recorded; they are historical outputs and were not
rewritten. After the move, the moved evaluation scripts were re-run from their new paths:
- `behaviour_change_impact.py`: same counts;
- `grounding_audit.py`: passed;
- `release_by_intent.py`: its served JSON is byte-identical (sha256 prefix `a281968c4eff0994` before and after).

**Removed:**
- `scripts/product/` (empty after the move);
- `frontend/artifacts/` (the stray duplicate above).

**Added:**
- `resolveai/trust/normalize.py`, `resolveai/intelligence/conversation_acts.py`;
- `tests/test_case_and_conversation.py`;
- `frontend/lib/text.ts`;
- `scripts/evaluation/behaviour_change_impact.py`, `scripts/README.md`;
- `artifacts/product/hardening/behaviour_change_impact.json`;
- this review.

**Intentionally retained:**
- **Underscore-prefixed files** (`artifacts/phase7/_pre_phase7_hashes.json`, `artifacts/resolution/_dev_state.json`,
  `data/human_eval/_packet_key.json`): frozen evidence or a key the tests read. Their names look temporary; they are not.
- **Smoke screenshots** (`artifacts/product/hardening/smoke/screenshots/`, now gitignored): illustrative output of the browser
  smoke, overwritten by this pass's run. Earlier phases committed screenshots the same way.
- **`artifacts/product/verify_product_pass` outputs and `scripts/verification/verify_product_pass.py`:** they keep the product
  pass's report reproducible. That script checks against the product-pass baseline, which predates the final reports in
  `artifacts/final/`, so it is not expected to pass on today's tree; `final_verification.py` is the current check.

## 8. Security verification

| Area | Check | Result |
|---|---|---|
| Authentication and authorization | live probes; production-profile API smoke; `tests/test_phase9_api_security.py` | 18 of 18 unauthenticated or wrong-token calls to protected endpoints refused (401); a read-only token on `/resolve` gets 403; `/health` is the only public data route |
| Rate limits | API smoke | 429 with `Retry-After` on agent runs, reads and failed authentication |
| Malformed and spoofed payloads | `tests/test_api.py`, `tests/test_case_and_conversation.py` | unknown fields rejected (spoofed `evidence`, spoofed `action`: 422, not echoed); wrong types, empty and over-long input rejected before the agent runs |
| Prompt injection: customer text | adversarial case 10; case suite | hard handoff with 0 model calls in any capitalization, in full-width letters, and with a zero-width character inside a keyword |
| Prompt injection: retrieved evidence | adversarial case 11 | instruction-like historical text quarantined before the evidence gate |
| Model output trying to override policy | adversarial cases 12–13 | malicious or malformed model output cannot clear a flag, fabricate a citation or pass verification |
| Context overriding a hard block | case suite | an injection sent inside a thread is still a `prompt_injection` handoff |
| Trace metadata | request schema; trace schema tests | metadata fields validated (enumerated channel, locale pattern, hex-only customer hash); traces reject raw text, reasoning and secret-like keys |
| Secrets in logs and outputs | in-memory comparison, values never printed | 0 occurrences of the generated API token and 0 of the model key in 39 of this pass's logs, smoke reports, the outage response, the verification records and the final reports; API smoke server log: 0 tokens, 0 keys, 0 raw email, phone or customer text |
| Secrets in the browser | forwarder unit tests; Settings smoke check | the token is attached server-side, a browser `Authorization` header and cookies are never forwarded, Settings renders credential presence only |
| Error leakage | API tests; forwarder tests | one error body with code and correlation ids; no stack trace; an unreachable upstream returns no internal address |
| Security scan | `scripts/security_scan.py` via `final_verification.py` | passed: 0 findings over 785 committable files (84.9 MB); `.env` not committable; 0 of 813 trace records contain unredacted PII |

Not verified by this pass (unchanged gaps): TLS, SSO, token rotation, dependency vulnerability scanning, and manual screen-reader or
penetration testing.

## 9. Test results

| Check | Command | Result |
|---|---|---|
| Backend tests | `python -m pytest -q` | 459 passed, 1 skipped, 0 failed; the skip is the live-model integration test (`RESOLVEAI_INTEGRATION=1`) |
| Capitalization and conversation suite | `python -m pytest tests/test_case_and_conversation.py` | 69 passed (unit, no-model agent and API tests; included in the 459 above) |
| Input robustness | `python scripts/verification/input_robustness.py` and `python -m pytest tests/test_input_robustness.py` | 53 message classes + 15 malformed API bodies: 0 crashes, 0 contract failures; 69 tests passed |
| Lint (Python) | `ruff check .` | all checks passed |
| Frontend lint / typecheck | `npm run lint` · `npm run typecheck` | 0 problems · clean |
| Frontend tests | `npm test` | 122 of 122 in 15 files |
| Frontend build | `npm run build` | succeeds |
| Adversarial suite | `python scripts/verification/release_checks.py adversarial` | 20 of 20 passed |
| API smoke (production profile) | `python scripts/verification/release_checks.py api-smoke` | 23 of 23 passed; server log: 0 tokens, 0 keys, 0 raw email, phone or customer text |
| Grounding audit | `python scripts/evaluation/grounding_audit.py` | 13 automatic replies checked (12 release: 5 drafted, 7 templates; 1 captured API reply with its trace), 0 failed |
| Documented policy-rule count | `python -m pytest tests/test_manifests.py` | every committed "N ordered rules" mention equals `len(POLICY_RULES)` |
| Behaviour-change impact | `python scripts/evaluation/behaviour_change_impact.py` | 21 of 197 golden rows reach a changed input path |
| Browser smoke, full (auth-enabled API, production build, Edge + axe-core) | `frontend/scripts/smoke.mjs` via the smoke runner | 40 route visits, 7 of 7 scenarios with the expected decisions, 12 of 12 interactions, 0 failures, 0 WCAG 2.1 A/AA violations, 0 pages with horizontal overflow at 1440, 1180, 834 and 390 px; the only console error is the deliberate 404 page |
| Browser smoke, console without a token | `SMOKE_MODE=unauthorized` | 5 of 5 routes show "Not authorized", 0 failures, 0 axe violations |
| Browser smoke, API stopped | `SMOKE_MODE=api-down` | 7 of 7 routes show "ResolveAI API unavailable", 0 failures, 0 axe violations (the console errors are the expected 502s) |
| Live authorization probes | `curl` against the auth-enabled API | all 9 protected endpoints refused with 401 without a token and with a wrong token (18 of 18); `/health` 200; the console forwarder refused `/api/v1/docs` and a `..%2F` traversal with 404 |
| Live model outage | API with an unreachable model endpoint and an uncached model name | HTTP 200 `HUMAN_HANDOFF`, reason `llm_unavailable`, rule `llm_fallback`, risk and draft stages `fallback`, after 42.8 s |
| Golden set integrity | `python scripts/verification/final_verification.py` | verified on load: 197 rows, sha256 `33f4f333ccf10de7f628e57b5567a7930852cdf5b6d4bba872555b96b2bec3a9`, unchanged |
| Frozen files, byte level | same, against `artifacts/product/hardening/hardening_start_snapshot.json` (data/, every artifacts/ folder including `artifacts/final/`, frozen models and configs) | 416 checked: 0 changed, 0 missing, 0 unexpected new files. Four evaluation reports that `scripts/evaluate.py --cached` rewrites are listed separately, each with its reason; frozen *inputs* are not exempt |
| Phase 7 hash snapshot | same | 115 files: 0 changed, 0 missing (same four declared exceptions); golden matches its freeze manifest |
| Cached evaluation | same (`scripts/evaluate.py --cached`, no model calls) | all 11 regenerated evaluation result files byte-identical (171.6 s) |
| Release evaluation runs and decision records | covered by the frozen-file check | `artifacts/final/evaluation/runs/`, `final_metrics.json`, `risk_experiment/decision.json` and every earlier run record unchanged |

**Evaluation integrity.** No golden run was repeated and nothing was tuned on the golden set. The only golden access in this pass
was `scripts/evaluation/behaviour_change_impact.py` (messages and threads only, no annotations, no model) and the existing grounding
audit and per-intent report, which read the committed release run.

## 10. Remaining limitations

- Human validation of the LLM judge not completed (0 of 50); one annotation pass was an AI; 197 golden rows from one 2017 burst.
- 75 unnecessary handoffs and a 6.1% automatic rate on golden; templates that assert facts.
- The running pipeline (v6.2) is newer than the evaluated one (v6.1); the golden run was not repeated (§3).
- Regex PII detection (names, addresses and lower-case serials are missed); pattern-based injection detection.
- A live model outage takes about 40 s to become a handoff.
- The full clean-environment run was done in the previous pass (10 of 11 steps passed; the verification step failed on a stale baseline, since fixed — DECISIONS #119). It was **not**
  repeated after this pass's changes. This pass verified with the full test suite, both smokes, the adversarial suite and the
  integrity check on this machine.
- Not a deployment:
  - one process, process-local rate limits, file-based traces;
  - no TLS, operator SSO or roles, metrics, alerting, retention, runbooks or dependency scanning;
  - no load test.

## 11. Run ResolveAI

```bash
python -m venv .venv && . .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env                                     # optional model credentials
python -m resolveai serve                                # API  http://127.0.0.1:8000
cd frontend && npm ci && npm run dev                     # console http://localhost:3000
```

## 12. Verify ResolveAI

```bash
python -m pytest -q
ruff check .
cd frontend && npm run lint && npm run typecheck && npm test && npm run build && cd ..
python scripts/verification/final_verification.py            # golden hash, frozen files, Phase 7 snapshot, cached evaluation, security scan
python scripts/verification/release_checks.py adversarial
python scripts/verification/release_checks.py api-smoke
python scripts/evaluation/grounding_audit.py
python scripts/evaluation/behaviour_change_impact.py
cd frontend && npm run smoke                                 # needs the API and a built console running; see docs/UI.md
```

## 13. Git status

The repository has no commits, so `git diff` is empty by construction and `git status --porcelain` lists 13 untracked top-level
paths; 778 files are committable (777 at the full verification, plus the saved copy of that verification report).
A last quick pass after the final report edits (`final_verification.py --skip-cached-eval`) passed: golden unchanged, 416 frozen
files unchanged with no unexpected new files, Phase 7 snapshot unchanged, security scan 0 findings over 778 files, 0 trace records
with PII. Nothing was committed, pushed, published or made public.

| Path | Classification | Notes |
|---|---|---|
| `README.md`, `pyproject.toml`, `requirements.txt`, `requirements-dev.txt`, `.gitignore`, `.env.example` | KEEP · PRODUCT / DOCUMENTATION | `.env.example` holds names only, no values |
| `resolveai/` | KEEP · PRODUCT | agent package (82 files) |
| `frontend/` (app, components, lib, scripts, configs, lockfile) | KEEP · PRODUCT | `node_modules/`, `.next/`, `next-env.d.ts`, `tsconfig.tsbuildinfo` are IGNORE (generated) |
| `frontend/tests/` | KEEP · TEST | fixtures captured from the real API |
| `tests/` | KEEP · TEST | 28 modules |
| `scripts/verification/`, `scripts/evaluation/`, `scripts/evaluate.py`, `scripts/security_scan.py`, `scripts/README.md` | KEEP · PRODUCT (verification tooling) | |
| `scripts/final/`, `scripts/phase0/`–`scripts/phase9/` | KEEP · REPRODUCIBILITY ARTIFACT | cited by frozen artifacts |
| `docs/` | KEEP · DOCUMENTATION | 11 documents |
| `data/golden/`, `data/human_eval/`, `data/demo/`, `data/dev/`, `data/processed/apple_pairs.csv` and manifests | KEEP · REPRODUCIBILITY ARTIFACT (frozen) | `data/raw/` and the full or silver-train pair files are IGNORE (large or local-only) |
| `artifacts/final/` | KEEP · REPRODUCIBILITY ARTIFACT (results of record) + the three final reports | |
| `artifacts/product/` | KEEP · REPRODUCIBILITY ARTIFACT | product and hardening evidence, including 62 smoke screenshots (about 27 MB) |
| earlier `artifacts/*` phase folders | KEEP · REPRODUCIBILITY ARTIFACT (frozen) | underscore-prefixed files there are evidence, not temporary |
| `.env`, `.cache/`, `traces/`, `.pytest_cache/`, `.ruff_cache/`, `resolveai.egg-info/`, `__pycache__/`, `artifacts/**/_*.log` | IGNORE | gitignored; `.env` confirmed not committable by the scan |
| `scripts/product/`, `frontend/artifacts/` | REMOVE (done) | emptied by the move; stray duplicate |

## 14. Recommended path for a reviewer

1. `README.md` §1–§8: what it is, why AppleSupport, why it is not a chatbot, how grounding, safety and handoff work (5 minutes).
2. Run it (README §9), open the console, and follow `docs/DEMO.md` (10 minutes). Try `hi`, `MY IPHONE IS NOT TURNING ON` and
   `can I talk to a human`.
3. `docs/ARCHITECTURE.md` §1–§2 and §11–§12: the contract, the invariant, the verified no-bypass flow, text normalization.
4. `docs/EVALUATION.md` and the console's Evaluation Center: results with intervals, and what is misleading about them.
5. `docs/PRODUCTION_READINESS.md` and `artifacts/final/PRODUCT_SCORECARD.md`: what is and is not ready.
6. `docs/DECISIONS.md` (#108–#112 for this pass) and `docs/INTERVIEW_NOTES.md` for the reasoning behind each choice.
