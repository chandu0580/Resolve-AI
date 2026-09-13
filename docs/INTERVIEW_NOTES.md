# Interview notes

These are short answers with measured numbers. Sources are named so every claim can be checked. Golden numbers come from the
release run (`artifacts/final/final_metrics.md`, n = 197, 95% bootstrap intervals) unless stated otherwise.

## Quick answers

| Question | Answer (evidence) |
|---|---|
| **Why retrieval?** | Grounding means "how the brand actually resolved this before"; without retrieval there is nothing to verify a draft against or to measure sufficiency with. Removing retrieval cut safe automatic replies from 9 to 4 (ablation). More: question 5. |
| **Why BGE-small?** | All dense configurations sat inside one confidence interval (same-resolution recall@5 about 0.35, n = 46). BGE-small's cosine scale gave usable gate thresholds, retrieval p50 15 ms on CPU, and one encode serves both the classifier and retrieval. More: question 2. |
| **Why a deterministic policy?** | In the Phase 1A benchmark every model's escalation accuracy was at or below a never-escalate baseline (GLM-5.2 56.7% vs 83.3%). Ordered rules name the reason for every decision and can be tested. More: question 4. |
| **Why LLM risk flags?** | Rules alone miss fuzzy signals: the rules-only ablation had escalation recall 0.73 against 0.95 with model flags (DECISIONS #34). The model may add a flag but never clear one, and since release 1.0.0 a model-only `needs_private_info` needs the rule. |
| **Why GLM-5.2?** | Chosen by the Phase 1A benchmark: best intent accuracy (86.7%), 100% reply-format compliance, 0% transport failures; Gemini was unavailable and the Groq free tier rate-limited (DECISIONS #7). It is restricted to five bounded roles. |
| **Why not let the LLM decide escalation?** | It was measured and lost (above), its judgement is not auditable, and the direct-LLM baseline sent 3 of 151 automatic replies to customers who needed a human. It escalates with better precision (0.739 vs 0.324), so the trade-off is stated, not hidden. |
| **Why evidence sufficiency?** | Retrieved is not the same as supportive: only 2,869 of 17,875 historical replies state a fix. The gate grades INSUFFICIENT/WEAK/SUFFICIENT/STRONG; drafting on WEAK evidence raised judge hallucination from 0 to 0.071 offline. |
| **Why verification?** | Plausible drafts can invent steps: the dev verifier audit found 6 truly unsupported drafts among 26 audited. Lexical coverage plus a model support check, then a nine-check output gate, then an independent API re-check. |
| **Why human handoff?** | Abstention is the product: 111 of 197 golden messages went to a human with a packet (issue, context, intent, risk, evidence found and missing, questions, next action). A model outage also becomes a handoff (verified live in the final review). |
| **Why FastAPI?** | The agent, the classifier and the evaluation are Python; FastAPI serves the same Pydantic contracts the agent already uses (DECISIONS #68), validates requests before any agent work, and generates the OpenAPI document the console's types are generated from. One endpoint, `POST /resolve`, because separate draft or decide endpoints would bypass the gates (DECISIONS #66). |
| **Why Next.js?** | A real product surface over the live API, never mocked data (DECISIONS #14). Server components and a same-origin forwarder keep the API token and address on the server; the browser never holds a credential. |
| **Why no LangGraph?** | The pipeline is a DAG with one corrective retry: about 400 lines of explicit Python where every gate is a tested function. No multi-agent state or resume that a framework would pay for (DECISIONS #12). |
| **Why no Docker?** | Out of scope by decision (DECISIONS #13); reproducibility comes from committed inputs, hash-verified artifacts, a cached evaluation that regenerates byte-identical results, and clean-environment checks. A deployment would add packaging. |
| **What failed?** | Reply-side-only retrieval (recall@5 0.0), the multi-intent detector (3 of 44 correct), the 14-boolean risk schema (32.5% fallback), all four Phase 9 risk variants, and customer-facing templates that assert facts (flagged by the judge). All kept on record. More: question 22. |
| **What did you change?** | Release 1.0.0: one pre-registered dev decision (model-only `needs_private_info` needs the rule), golden unnecessary handoffs 87 → 75 with recall unchanged. Product: an operator console that explains every decision from structured data, a Handoff Center, an Evaluation Center with intervals, and a trace listing that reads backwards (200 rows over 20,000 traces: 629 ms → 63 ms p50). Final pass (`pipeline-v6.3`): "THANKS" was handed off while "thanks" was answered, because all-caps raised a frustration flag. Capitalization is now never a signal. A bare greeting no longer triggers a device questionnaire, "can I talk to a human" has its own handoff reason, and short replies such as "still happening" keep the issue they answer. Release-readiness pass (`pipeline-v6.3`): the English-only redirect no longer fires on a LOW-confidence guess (that band was mostly English on 4,000 corpus messages), a non-Latin script is recognised off the characters instead of getting an English clarifying question, and a bare "ok" gets a closing line instead of "You're welcome!". 21 of 197 golden rows reach a changed path; the golden run was not repeated. |
| **What remains imperfect?** | 75 unnecessary handoffs; AI-derived golden labels (though judge validation has 50 of 50 human ratings complete); 197 golden rows from one 2017 burst; regex PII and pattern injection detection; templates that assert facts; the running pipeline (v6.3) is newer than the evaluated one (v6.1); a model outage takes about 40 s to become a handoff; no operator login, TLS or metrics. |
| **How would you scale it?** | Several workers behind a shared rate-limit and queue store; an async model client with cancellation; the second opinion and the risk call in parallel (live p50 4.2 s, p95 14.2 s today); an indexed trace store or OpenTelemetry export; per-tenant knowledge bases; operator SSO; and human labels feeding dev-evaluated policy changes. |

## Detailed answers

### 1. Why this architecture?

Because the obvious alternative, one LLM prompt, answers too much. The direct-LLM baseline answered 151 of 197 golden messages. 3 of
those went to customers who needed a human, and the judge flagged 53% of its responses for unsupported claims. ResolveAI puts the
model **inside** a deterministic decision:
- retrieval measures whether history shows a fix;
- a policy in code decides;
- a verifier and an output gate check every reply;
- the API re-checks the result.

Result: 12 automatic replies, 0 unsafe. Every stage is a function with a test (a 20-case adversarial suite) and a trace event.

### 2. Why BGE-small?

- **Retrieval benchmark (Phase 2).** All dense configurations sat inside one confidence interval: same-resolution recall@5 about
  0.35 on 46 scorable golden rows.
- **Why it won.** BGE-small's cosine scale gave usable evidence-gate thresholds, its retrieval p50 was 15 ms on CPU, and it is 384
  dimensions.
- **Two uses.** The same encoder feeds the intent classifier, so the query is embedded once for both. MiniLM is the documented
  fallback (40% faster to embed, equal recall).
- **What it is not.** It is not the best embedding model; it is the smallest one that met the measured need.

### 3. Why not pure LLM classification?

Honestly, the direct LLM classifies slightly better: macro-F1 0.887 vs 0.854, difference −0.033 [−0.082, +0.014], not
distinguishable. The classifier was kept because:
- it is deterministic, costs no model call (about 55 ms on CPU), and gives calibrated bands (HIGH-band accuracy 0.925, n = 53);
- the LLM second opinion is consulted only at LOW or MEDIUM confidence, and only adopted if it names a top-3 alternative. That step
  raised accuracy from 0.614 to 0.736 in Phase 3;
- removing the second opinion drops intent accuracy to 0.614 but halves model calls (ablation).

### 4. Why a deterministic escalation policy?

- **Phase 1A.** Every model's escalation accuracy was at or below a never-escalate baseline (GLM-5.2: 56.7% vs 83.3%).
- **Auditability.** An ordered rule list names the reason for every decision, and a model can add a risk flag but never clear one
  (tested).
- **Trade-off, measured.** On golden the direct LLM escalates better (F1 0.819 vs 0.486). The deterministic policy buys
  auditability and 0 unsafe replies, and it costs precision.

### 5. Why retrieval?

Grounding means "how the brand actually resolved this before". Without retrieval there is nothing to verify a draft against and
nothing to measure sufficiency with.
- **Ablation.** Removing retrieval cut safe autonomous replies from 9 to 4; only templates were left.
- **Offline.** Drafting on WEAK evidence gave a judge hallucination rate of 0.071, against 0.0 on the 5 STRONG-evidence replies.
- **Honest limit.** The corpus caps it: only 7 of 197 golden messages reach STRONG evidence.

### 6. How do you know replies are grounded?

Mechanism, enforced in five places:
- a draft is written only on SUFFICIENT or STRONG evidence;
- it must cite evidence ids, and the verifier checks lexical evidence coverage, that the cited ids exist, and model support;
- the output gate requires all nine checks;
- the API re-checks independently.

A hallucinated draft with an approving model verifier is still blocked by the deterministic coverage check (tested).

What is measured: the 5 golden troubleshooting replies have judge hallucination 0 (n = 5, too small to generalise), and the dev
verifier audit found 6 truly unsupported drafts among 26. What is not measured: whether the fix solved the customer's problem.
Grounded is not correct.

### 7. What happens when evidence is insufficient?

No draft, ever. If there is no risk and the issue is in the taxonomy, the customer gets one clarifying question. Otherwise a human
gets a handoff packet with the issue, intent, risk flags, evidence summary, unresolved questions and a recommended next action.
On golden, 166 messages had INSUFFICIENT evidence and 24 WEAK. Adversarial cases 3 and 4 (no evidence, contradictory evidence)
test this.

### 8. What happens when the model fails?

The failure is classified and degrades by type:

| Failure | Result |
|---|---|
| Timeout or spent budget | handoff, `model_timeout` |
| Outage or invalid JSON | handoff, `llm_unavailable` (HTTP 200) |
| Risk model fails | deterministic rules only |
| Second opinion fails | classifier intent |
| Retrieval, embedding or verifier crash | handoff, `dependency_failure` |
| Trace unwritable | automatic reply withheld, `audit_unavailable` |

The client owns the timeout: 30 s per call, at most the 45 s request budget, one retry, SDK retries off. Before Phase 9 the SDK's
hidden retries allowed up to 12 attempts for one call. Suite cases 13–16 and 20 test all of this.

### 9. How do you prevent prompt injection?

- **Customer text is data.** A deterministic detector checks every turn; a detection is a hard handoff **before any model call**.
  It flagged 0 of 19,953 historical customer messages.
- **Retrieved history is data.** Instruction-like evidence is quarantined before the gate (0 of 20,000 corpus rows today).
- **Model output is untrusted.** It cannot clear a rule flag, a draft must pass the verifier and the gate, and the policy is code.
- **Tests.** Suite cases 10–12, plus the live API smoke (0 model calls on an injection).
- **Limit.** The detector is pattern-based; unseen phrasings are contained by the gates, not detected.

### 10. How do you prevent PII leakage?

- **Order.** Redaction runs first and produces typed tokens (`<EMAIL>`, `<PHONE>`, `<ORDER_ID>`, `<CARD>`, `<LONG_ID>`).
- **Guards.** The model client refuses unredacted text, and so does the trace recorder. The trace schema forbids text and secret
  keys. Exception text is redacted before logs.
- **Measured:**
  - 813 trace records scanned with 0 unredacted PII;
  - the live API server log held 0 raw emails, phone numbers or message text;
  - the adversarial tests found a real bug (a phone number before a full stop was not redacted); it is fixed and its corpus
    impact measured (4 knowledge-base rows).
- **Limit.** Regex detection misses names, addresses and spelled-out numbers.

### 11. Why is escalation precision low?

Precision is 0.324: 75 of 111 handoffs were unnecessary by the annotators' standard. Where they come from:

| Reason code | Unnecessary handoffs |
|---|---|
| `insufficient_evidence` (mostly non-support messages the policy sends to a human: product questions, suggestions, closures the closure pattern misses) | 21 |
| `repeat_contact` | 12 |
| `hardware` (the model's `physical_damage` flag on battery or reboot complaints) | 12 |
| `vague_hostile` | 8 |
| `payment_billing` | 7 |
| `safety` | 5 |
| `private_info`, `legal_media` | 4 each |

The root cause is design: model-raised flags were hard handoff reasons. The pre-registered Phase 10 fix (the model's
`needs_private_info` now needs the rule) moved golden precision from 0.293 to 0.324 with recall unchanged at 0.973. The policy
still errs toward a human, deliberately.

### 12. Why is the autonomous rate low?

It is 6.1% (12 of 197): 5 grounded troubleshooting replies and 7 non-English redirects. The evidence gate is strict, and the
corpus rarely contains instruction-bearing replies: about half of AppleSupport's replies are "DM us". Only 7 golden messages
reach STRONG evidence, almost all the iOS 11 autocorrect bug. Loosening the gate was not tested on golden. Offline, drafting on
WEAK evidence raised judge hallucination from 0 to 0.071.

### 13. Why does the direct LLM beat ResolveAI on some metrics?

It escalates better (F1 0.819 vs 0.486, precision 0.739 vs 0.324) and classifies slightly better (0.887 vs 0.854). Three reasons:
- it reads the full thread, while ResolveAI uses a bounded context;
- it weighs escalation holistically instead of OR-ing risk flags;
- accuracy metrics do not reward abstention.

It also answered 151 messages without any grounding contract: 3 went to customers who needed a human, 0 qualify as safe under our
definition, and its judge hallucination rate is 0.526. ResolveAI's advantage is confined to grounding, verification and
abstention.

### 14. What is misleading about your headline number?

"Escalation recall 0.973 and 0 unsafe autonomous replies" sounds like a safe, accurate system. The honest reading:
- recall rests on 37 positives, so one row moves it 2.7 points;
- "0 unsafe" is out of 12 automatic replies;
- the golden labels come partly from an AI annotator, and the judge is not human-validated;
- the data is one 2017 Apple burst;
- the direct LLM escalates better.

The honest version: *ResolveAI rarely answers, and when it answers on this dataset it does so from evidence; the price is 75
unnecessary handoffs.* FINAL_REPORT §10 has the full list.

### 15. Why use an LLM judge?

It scales to about 800 structured judgements that no human could produce in the time available, under controls:
- a rubric frozen before scoring, with anchors at every level;
- system identity hidden, and pairwise order seeded;
- failures recorded;
- a second model family scored a subset (groundedness weighted κ 0.822, n = 126).

It is used only to estimate reply quality, never inside an agent decision. Its self-preference is measured: it rates GLM-written
prose +0.67 to +0.84 higher than the second family does.

### 16. Why is human validation important?

The judge shares the drafter's model family, reads template wording as claims, and fails to parse non-uniformly across systems.
The release made the problem concrete: changing 27 decisions moved judge hallucination from 0.283 to 0.367, entirely through
template wording. Until a human scored the 50-row packet, every groundedness or hallucination number was a model's opinion.
Human evaluation of the judge is now **completed** (50 of 50 rated; see `artifacts/evaluation/judge_agreement.md` for Cohen's
weighted kappa and agreement metrics across all dimensions).

### 17. What would you improve with one more week?

1. The 50-row judge human validation is complete; next step: multi-rater evaluation to measure human inter-annotator reliability.
2. Human-label about 200 dev rows for escalation, and re-run the risk experiments on human labels.
3. The two worst fact-asserting templates are already reworded (DECISIONS #118: "sorry about the damage", "the steps you've
   already tried"); evaluate the remaining template wording, including clarification menu paths, on dev with human review.
4. Test a `physical_damage` definition in the risk prompt under the same pre-registered rule, now the largest model-flag source.
5. Let the non-English redirect win over model-flag handoffs for non-English messages (g070, g165, g188), and fix the `dm i sent`
   repeat-contact gap (g048, the one missed escalation). Both evaluated on dev.
6. Measure live draft and verification latency on a larger sample.

### 18. What would you change for production?

- **Security:** TLS, operator SSO, token rotation and a secret manager.
- **Scale:** a shared rate-limit and queue store with several workers, and an async provider client with cancellation (a timed-out
  thread cannot be killed today).
- **Latency:** p50 4.2 s / p95 14.2 s for a random live sample of dev messages (n = 40, 45 s budget, no request reached drafting); requests that drafted and verified live took p50 10.7 s / p95 26.1 s (n = 8, a small sample); without the model a request takes 173 / 374 ms p50 / p95 on a machine that was shared with other workloads. Parallelising the second opinion and the risk call would cut it.
- **Operations:** metrics and alerts (handoff rate, fallback rate, latency), trace retention, NER-based PII detection, dependency
  scanning, and outcome feedback (did the reply solve it).
- **Releases:** a per-release canary evaluation.

`docs/PRODUCTION_READINESS.md` lists 10 NOT READY items.

### 19. How does the trace work?

One `AgentTrace` per execution, appended to a daily JSONL file. It holds:
- request and trace ids, pipeline and component versions, and a config hash;
- request metadata, per-stage status (`ok`, `skipped`, `fallback`, `failed`) and latency;
- model usage (calls, cache hits, tokens, retries, timeouts, errors, budget refusals);
- classified failures, and every decision event (intent, evidence verdict, risk flags, policy rule, output gate).

The schema rejects keys like `raw_text`, `reasoning` and `authorization`, and the recorder refuses PII, so there is no customer text
and no chain-of-thought. If the trace cannot be written, an automatic reply is withheld. The API lists and serves traces, skipping
corrupted lines (a defect found by the final suite and fixed), and the console renders them as a stage timeline.

### 20. Why didn't you use LangGraph?

The agent is a DAG with one corrective retry: about 400 lines of explicit Python in `resolveai/agent/orchestrator.py`, where every
gate is a plain function with a test. There is no multi-agent coordination, long-running state or human-in-the-loop resume that a
framework would pay for. The Phase 0 technology comparison applied a demonstrated-purpose rule, and re-entry triggers are
documented (DECISIONS #12).

### 21. Why didn't you use Docker?

It was out of scope by decision, and there is no deployment target for a container to serve. Reproducibility comes from:
- pinned inputs (committed subsample, golden set, frozen models, run records);
- a hash-verified cached evaluation;
- a clean-clone check that installs a fresh environment with no credentials or caches: three runs, all kept. The first full run from a fresh virtual environment (no `.env`, no caches, no credentials) failed: `rank-bm25` was imported but not declared. The second full run passed the install, the no-key demo, the API, lint, typecheck and build, but exposed three packaging gaps: a `.gitignore` rule hiding the console's Traces pages, a test relying on a local-only file, and a verification bug. After those fixes, a targeted re-check of the committable file set passed every step: pytest, the demo, the final verification, npm ci, lint, typecheck, tests, build and a safe API reply. That re-check reused this machine's Python interpreter and embedding cache, as its report states (`artifacts/final/clean_env_check.json`). A later full fresh-venv run passed 10 of its 11 steps; the failing step was the verification script comparing against a baseline two passes out of date, now fixed (DECISIONS #119).

A real deployment would add packaging.

### 22. What did not work?

- **Retrieval ideas.** Reply-side indexing on its own (recall@5 0.0); intent-boosted retrieval (no recall gain); using conversation
  context for classification (0.609 vs 0.614).
- **Detectors and labels.** The multi-intent detector (44 predicted, 3 correct); tuning the evidence gate against the automatic
  TF-IDF judge (precision 0 at every setting).
- **Risk variants.** The 14-boolean risk schema (32.5% fallback); all four Phase 9 risk variants (rejected under the pre-registered
  rule).
- **Wording.** Phase 7's clarification wording and the Phase 10 hardware handoff line, both flagged by the judge.

All are recorded with numbers, not removed.

### 23. What surprised you?

- **The model's private-info flag never met the rule.** The model raised `needs_private_info` 26 times on dev, and the
  deterministic rule agreed 0 times.
- **Fixing one flag exposed another.** It moved 11 golden handoffs to `hardware` and surfaced a template that apologises for
  "damage" nobody mentioned.
- **Hidden retries.** The OpenAI SDK's own retries sat under ours: up to 12 attempts per call.
- **Salted hashing.** Python's `hash()` is salted per process, which silently broke the first response cache.
- **A misleading profile.** An embedding memo made cached-model requests look faster than no-model ones.
- **Cold start.** The first request after a start takes 24–67 s.
- **An undeclared dependency.** Ten phases of green tests had hidden it. The first clean-clone install failed because `rank_bm25`
  was imported but never declared: every local test passed only because the package happened to be installed.

### 24. Which architectural decision would you reverse?

Treating model-raised risk flags as hard handoff reasons, OR-merged with the rules, from Phase 4 on. That one choice produced most
of the over-escalation: 17 of 41 dev false positives from the private-info flag alone, and now the damage flag. From the start I
would treat model flags as soft signals: each flag either corroborated by a deterministic signal or given a calibrated threshold
on a human-labelled dev set. I would also never let a customer-facing template assert a fact the message did not contain.

### 25. How does the console explain a decision without asking the model?

"Why did ResolveAI do this?" is a pure function (`frontend/lib/explain.ts`) over data the pipeline already produced: the API's
outcome (what happened, why, next step), the evidence gate's level and reason, the policy rule and version, the risk flags, the
verification verdict and the output gate's checks. For a trace it uses only the recorded events. Asking a model to explain itself
would produce a plausible story that nothing guarantees matches the code path; the structured record is what actually decided.

### 26. Why does the console keep live, golden, dev and performance numbers apart?

Because they answer different questions. Live traces show what this environment did, with no ground truth, so live recall or
groundedness cannot be computed and the Overview says "Not measured live". The frozen golden set gives accuracy with intervals
for one release run. Dev experiments chose settings and use AI labels. The performance profile ran on dev requests on a shared
machine. Mixing them would let a demo run look like an evaluation result, so every section carries its dataset label.

### 27. What is a "knowledge gap" in the Knowledge Center?

A measurable signal, not a recommendation: an intent with at least 10 golden conversations where SUFFICIENT or STRONG evidence was
found for at most 10% and at least half went to a human. The rule is fixed in `scripts/evaluation/release_by_intent.py` and shown
on the page with the underlying counts and redacted examples. On the release run it flags 7 intents, which mostly says the
knowledge base rarely contains a stated fix: only 2,869 of 17,875 historical replies are resolution-bearing, and 9,415 only move
the customer to a private channel.
