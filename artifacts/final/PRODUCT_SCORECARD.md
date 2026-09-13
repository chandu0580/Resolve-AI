# ResolveAI 1.0 product scorecard

Scored at the end of the final product hardening and reviewed again in the final repository pass
(`artifacts/final/FINAL_REPOSITORY_REVIEW.md`), which changed live behaviour (pipeline-v6.2) without changing any score. **READY** means implemented, tested against the real code path and not known to be
missing anything for this reference product's scope. **PARTIAL** means it works and is evidenced, but a named gap would matter to a
real customer. **NOT READY** means an enterprise deployment would be blocked. No area was marked up because a test exists. Exact
verification numbers are in `artifacts/final/FINAL_PRODUCT_REVIEW.md` §11.

| Area | Score | One line |
|---|---|---|
| Product UX | PARTIAL | A complete, consistent operator workspace that explains every decision; no operator identity, case assignment or notes, and conversation text survives only in the browser that ran it |
| Agent quality | PARTIAL | Catches escalations (recall 0.973) and never answered a customer who needed a human on golden, but sends 75 unnecessary handoffs and answers only 6.1% automatically |
| Grounding | PARTIAL | The evidence invariant is enforced in five places and every automatic reply passes the grounding audit; reply quality is judged only by an unvalidated LLM, and some templates assert facts |
| Safety | PARTIAL | Fails safe on every tested failure (20 of 20 adversarial cases); detectors for PII and injection are shallow and the safety evidence rests on 12 automatic replies |
| Security | PARTIAL | Scoped token auth before the body is read, no secrets in the browser, clean scans; no TLS, SSO, token rotation or dependency scanning |
| Observability | PARTIAL | Every execution is traced and explorable without customer text; no metrics, alerting, central logs or trace retention |
| Evaluation | PARTIAL | Frozen hash-verified golden set, baselines, bootstrap intervals, pre-registered dev decisions, reproducible cached run; human validation not completed and labels partly AI-written |
| Developer experience | PARTIAL | Documented setup, one orchestrator, typed API contract, 440 automated tests and scripted checks; no CI pipeline, and the browser smoke needs a locally installed Microsoft Edge |
| Reproducibility | PARTIAL | Cached evaluation regenerates byte-identical results and integrity is verified; the final clean-environment run exposed a verification bug (fixed and re-verified on a clean copy), and dependency pinning has limits (below) |
| Documentation | READY | README, architecture (with the verified no-bypass flow), API, UI, evaluation, 107 decisions, production readiness, demo and interview notes, checked against the running system in the final review |
| Enterprise readiness | NOT READY | Single process, process-local limits, file-based traces, no TLS, SSO, metrics, retention or runbooks |

> **Re-checked 2026-09-12** in the release-readiness pass. No score moved. The pass closed three customer-facing defects (the
> language redirect firing on a LOW-confidence guess, non-Latin scripts getting an English clarifying question, and a bare "ok"
> answered "You're welcome!"), added an input-robustness suite (53 classes, 0 crashes) and gave the judge-agreement report a
> disagreement analysis and a limitations section. The open requirement is unchanged and is not a scoring question:
> **0 of 50 human judge ratings** (`FINAL_ASSIGNMENT_AUDIT.md` B5).

## Why each PARTIAL or NOT READY

### Product UX: PARTIAL
- **Works:** ten pages with one vocabulary (AUTO-HANDLED, CLARIFICATION, HUMAN HANDOFF); a three-panel conversation workspace; an
  eight-field explanation built from structured data (including *what would change it*); evidence used separated from evidence
  retrieved; a Handoff Center with fixed queues; breadcrumbs; explicit loading, empty and error states; 0 axe WCAG 2.1 A/AA
  violations and no horizontal overflow in the browser smoke.
- **Gap:** no operator login, roles, case assignment, internal notes or SLA tracking; traces never store text, so a conversation's
  text reappears only in the browser that ran it; no manual screen-reader session; English only.

### Agent quality: PARTIAL
- **Works:** escalation recall 0.973 [0.912, 1.000]; 0 unsafe of 12 automatic replies; intent macro-F1 0.854 [0.799, 0.901].
- **Gap:** escalation precision 0.324 [0.232, 0.411], 75 unnecessary handoffs; the direct-LLM baseline escalates better (F1 0.819 vs
  0.486); only 7 of 197 golden messages reach STRONG evidence, so automatic replies are rare (6.1%).

### Grounding: PARTIAL
- **Works:** drafting only on SUFFICIENT or STRONG evidence, mandatory citations, lexical and model verification, a nine-check output
  gate and an API re-check; the grounding audit passes for all 12 automatic replies of the release run (5 drafted, 7 templates) and the
  captured API reply, including its trace; the console never labels an unsupported reply "grounded".
- **Gap:** the judge is not human-validated (0 of 50 rated) and shares the drafter's model family; "grounded" does not mean the fix
  worked; handoff and repeat-contact templates assert facts the message does not contain.

### Safety: PARTIAL
- **Works:** model outage, timeout, malformed or malicious output, verifier crash, corrupted trace store, prompt injection in customer
  text and in retrieved history all end in a safe action (adversarial suite 20 of 20); a live outage produced a handoff, not an error.
- **Gap:** regex PII detection misses names and addresses; injection detection is pattern-based (novel phrasings are contained by the
  gates, not detected); 12 automatic replies and 37 positives are small samples.

### Security: PARTIAL
- **Works:** bearer tokens with two scopes, checked before the body is read, identical 401s, rate limits on runs, reads and failed
  authentication; every protected endpoint refuses anonymous and wrong-token calls; the console attaches its token server side and
  the forwarder allows only API endpoints; 0 tokens or keys in logs, reports or the browser; security scan clean.
- **Gap:** static shared tokens (no rotation, expiry or per-user identity); no TLS; no dependency vulnerability scanning; secrets in
  environment variables, not a secret manager.

### Observability: PARTIAL
- **Works:** one trace per execution with versions, config hash, stage status and latency, model usage, classified failures and
  decision events; a Trace Explorer that answers what, why, how long, what failed and what evidence; trace listing stays at about 60 ms
  for 200 rows over 20,000 traces.
- **Gap:** no metrics, dashboards or alerts on handoff rate, fallback rate or latency; no centralised logging; file-based traces with
  no retention policy or integrity checksums.

### Evaluation: PARTIAL
- **Works:** frozen golden set verified on every load and run once per system; three baselines; paired bootstrap intervals; dev
  decisions pre-registered; the cached evaluation regenerates all 11 result files byte-identical; the console never mixes live, golden,
  dev and performance data.
- **Gap:** human judge validation not completed; one annotation pass was an AI; 197 rows from one 2017 burst. The running product
  (`pipeline-v6.2`: greetings, requests for a person, short replies, capitalization) is newer than the evaluated `pipeline-v6.1`;
  the golden run was not repeated, and 21 of 197 golden rows reach a changed input path (`scripts/evaluation/behaviour_change_impact.py`).

### Developer experience: PARTIAL
- **Works:** one documented setup; generated console types with a contract test; scripts for every release check that never write
  into frozen folders.
- **Gap:** no CI configuration; the first run embeds 17,875 cases (about 8 minutes on CPU); the browser smoke relies on a locally
  installed Microsoft Edge.

### Reproducibility: PARTIAL
- **Works:** committed inputs, hash-verified golden set and frozen artifacts, SHA-256 model response cache, byte-identical cached
  evaluation.
- **Gap:** the final full clean-environment run (fresh venv, no caches or credentials) passed install, backend tests, demo, API and
  every frontend step, but **failed** the documented release verification: its baseline predated `artifacts/product/`. That is now
  fixed and passes on a clean copy of the committable files (review §11). Python dependencies are lower-bound pins without hashes;
  the clean run used the development machine's OS and base interpreter; there is no CI job on a fresh runner.

### Enterprise readiness: NOT READY
One process runs one agent at a time behind a bounded queue; rate limits are process-local; traces are local files; there is no TLS,
SSO, metrics, alerting, retention, runbook, load test or multi-tenant separation. `docs/PRODUCTION_READINESS.md` lists each item with
its next step.
