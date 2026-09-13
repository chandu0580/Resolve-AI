# ResolveAI: final report (release 1.0.0)

Every number comes from a committed artifact, named beside it. Golden results are from `artifacts/final/final_metrics.md`
(n = 197, 95% bootstrap, 1,000 resamples, seed 42) unless stated. Detail lives in `docs/` and `artifacts/`; this report is the
argument.

## 1. Executive summary

ResolveAI is an evidence-grounded support agent for AppleSupport. Every customer message gets exactly one action — `AUTO_HANDLE`
(a verified reply citing historical cases), `CLARIFICATION_REQUIRED` (one question), or `HUMAN_HANDOFF` (a packet for a person).
Deterministic code decides whether a reply is allowed; the LLM only assists. It is a reference implementation with a FastAPI
service and a Next.js console, not a deployed system.

**Results (release 1.0.0, golden set, run once)**

- **Strengths:** escalation recall 0.973 [0.912, 1.000]; **0 unsafe automatic replies out of 12**, all 12 safe (6.1% of
  messages); intent macro-F1 0.854 [0.799, 0.901].
- **Where the one-prompt direct-LLM baseline wins:** escalation F1 0.819 vs 0.486 (−0.333 [−0.443, −0.241]) and precision 0.739
  vs 0.324. It also sent 3 unsafe replies, with a judge hallucination rate of 0.526.
- **Release change:** a pre-registered dev experiment removed the model-only private-info escalation; unnecessary handoffs fell
  87 → 75 (−12 [−19, −6]) with recall unchanged. It exposed a template apologising for "damage" nobody mentioned, raising the
  unvalidated judge's hallucination rate 0.283 → 0.367 entirely on template wording. The wording is fixed (DECISIONS #118); the
  golden run was **not** repeated, so 0.367 describes text the product no longer sends.
- **No human labels anywhere.** Both golden-set annotation passes were AI annotators under a written guide, and 0 of the 50 judge
  packet rows are rated. Judge–human agreement is therefore not reported.

**Verification (2026-09-12).** Backend 459 tests passed / 1 skipped; frontend 122 of 122 with lint, typecheck and build clean;
adversarial suite 20 of 20; live API smoke 23 of 23; browser smoke in 3 modes, 0 failures, 0 accessibility violations; input
robustness 53 message classes + 15 malformed bodies, 0 crashes; security scan 0 findings over 785 files, 0 of 813 trace records
with PII; cached evaluation regenerates all 11 result files byte-identically; golden hash unchanged. A clean copy of the 785
committable files (no `.env`, caches or credentials) passed all 9 steps in 478 s. Details: `FINAL_RELEASE_CHECKLIST.md`.

## 2. Problem framing

The data is the Kaggle *Customer Support on Twitter* dataset. AppleSupport was chosen by measurement over all 108 brands: the
numeric leaders (Tesco, Spotify, British Airways) resolve by collecting identifiers, so nothing is auto-answerable and there is
nothing to ground in, while AppleSupport has ~10k troubleshooting replies (DECISIONS #1).

**What "good" means for this brand.** AppleSupport answers in public, where a wrong troubleshooting reply is visible to everyone
and about half the brand's own replies are "DM us" rather than fixes. So "good" is not reply volume. It is: never send a public
answer the brand's own history does not support; when evidence is thin, ask one useful question; when the case is risky,
sensitive or unclear, hand a person everything they need. An unnecessary handoff costs human minutes. A confident wrong answer
costs trust, publicly. The system is built around that asymmetry.

**What I chose not to build, and why.**

- **A chat loop.** One message plus its thread in, one decision out. Multi-turn state would double the surface with no way to
  evaluate it on a corpus where most threads are two or three turns.
- **Fine-tuning.** The classifier is a calibrated logistic regression over frozen embeddings. With ~200 labelled rows,
  fine-tuning would fit the labels, not the task, and make error analysis unreadable.
- **An agent framework, vector database, Docker or experiment tracker.** Each was checked against a demonstrated-purpose rule
  (`artifacts/technology_recon/`): the pipeline is a DAG with one retry, the corpus is 30 MB in memory, and the rubric and kappa
  study are custom by requirement. Re-entry triggers are written down.
- **Banking77.** Offered by the brief as an optional intent resource; 77 fine-grained banking intents do not transfer to
  consumer-tech support, so the taxonomy came from reading this corpus.
- **Maximising autonomy.** The corpus supports a grounded public answer for a minority of issues. Chasing autonomy means
  answering without evidence — the failure mode the system exists to prevent.
- **A deployment.** No TLS, SSO, metrics or multi-tenancy; `docs/PRODUCTION_READINESS.md` lists all 55 items with status.

**Data contract.** 18,000 knowledge-base and 2,000 holdout pairs, split by `created_at`; the holdout is 2017-11-28 to 12-03 and
every knowledge-base row is earlier. PII is redacted before storage. The 197-row golden set is sampled from the holdout only,
frozen, hash-verified, and never indexed.

## 3. The system

One API call, `POST /api/v1/resolve`, returns the action, reason code and policy rule, the evidence with provenance, risk flags,
verification, a clarification or handoff packet, versions, per-stage status, latency, usage and a `trace_id`. The console renders
that data and holds no agent logic.

One orchestrator of ~400 lines — no agent framework — shared by API, CLI, demo and evaluation: PII redaction and a
prompt-injection hard block (no model call) → bounded context → BGE-small + calibrated logistic-regression intent, with an LLM
second opinion only at LOW/MEDIUM confidence and only if it names a top-3 alternative → pair-index retrieval over 17,875 earlier
cases with a resolution rerank and quarantine of instruction-like text → **evidence gate** → risk flags (rules OR model; the
model can add but never clear) → **deterministic policy**, ordered rules, first match names the reason → grounded draft that must
cite evidence ids → verifier → **nine-check output gate** → action → trace. Six stages can stop an automatic reply
(`docs/ARCHITECTURE.md` §2).

**Grounding.** *No sufficient evidence → no autonomous reply*, enforced in five places — policy, drafter refusal, verifier,
output gate, and an independent API re-check — each covered by an adversarial test. An approving model verifier cannot rescue a
hallucinated draft, because the deterministic coverage check blocks it; fabricated citations and a tampered API result are both
withheld. STRONG or SUFFICIENT needs ≥3 independent instruction-bearing cases whose top resolution cluster holds ≥60% of support
(hand-checked precision 0.93 on 14 AI-labelled dev verdicts). On golden: 166 INSUFFICIENT, 24 WEAK, 7 STRONG — all 7 the same iOS
11 autocorrect bug, and the 5 grounded replies came from them. Drafting on WEAK evidence (offline) gave a judge hallucination
rate of 0.071 against 0.0 for the STRONG replies; the dev verifier audit blocked 6 truly unsupported drafts out of 26.

**Escalation.** Ordered code: safety > injection > security > legal > abuse > account > billing > private info > hardware >
repeat contact > frustration without a symptom > templates > clarification > evidence > automatic. Phase 1A showed every model's
escalation accuracy at or below a never-escalate baseline, so the model only supplies flags. The pre-registered Phase 10
experiment (DEV only, 76 AI-labelled rows) made a model-raised `needs_private_info` count only when the deterministic rule fires:
unnecessary handoffs 41 → 32 at equal recall, so it shipped. A detail worth knowing: the model raised that flag 26 times and the
rule agreed 0 times, so private handling now rests entirely on rules (`artifacts/final/risk_experiment/`).

## 4. Evaluation methodology

Evidence categories are never mixed (`docs/EVALUATION.md` §1): **golden** (197 rows, 37 should-escalate; two annotation passes,
**both AI annotators**, κ 0.920 intent / 0.885 escalation measuring consistency under the guide, never human agreement);
**dev** (all design decisions); **AI-labelled** (gate calibration, verifier audit, risk rows); **human** (the 50-row judge packet:
**0 rated**); **LLM judge** (GLM-5.2, frozen rubric-v1, with qwen3.8-27b as a second family on 126 responses); **baselines**
(B0 trivial and always-handoff; B1 TF-IDF+LR with nearest-neighbour reply and the same rules; B2 one GLM-5.2 prompt with the
taxonomy, escalation criteria and full thread).

Each system runs on golden once; the scripts refuse to re-run and the hash is checked before and after. Model calls replay from a
SHA-256 cache, so the golden runs made 0 live calls. Metrics are pure functions over run records; differences use a paired
bootstrap on the same rows. Escalation means `HUMAN_HANDOFF` vs `should_escalate`, so a clarification counts as not escalated.
"Safe autonomous" means an automatic reply on a non-escalate row that is either verified and referenced or the correct template.

## 5. Results vs baselines

| Golden metric | **ResolveAI 1.0.0** | B2 direct LLM | B1 simple ML | ResolveAI − B2 (paired) |
|---|---|---|---|---|
| Intent accuracy / macro-F1 | 0.848 / 0.854 | **0.878 / 0.887** | 0.543 / 0.550 | −0.030 / −0.033 [−0.082, +0.014] |
| Escalation precision | 0.324 | **0.739** | 0.491 | −0.415 [−0.533, −0.317] * |
| Escalation recall | **0.973** | 0.919 | 0.757 | +0.054 [−0.045, +0.158] |
| Escalation F1 | 0.486 | **0.819** | 0.596 | −0.333 [−0.443, −0.241] * |
| Unnecessary / missed escalations | 75 / 1 | 12 / 3 | 29 / 9 | |
| Automatic replies (rate) | 12 (0.061) | 151 (0.766) | 140 (0.711) | |
| Safe / unsafe automatic replies | **12 / 0** | 0 / 3 | 13 / 9 | safe rate +0.061 [+0.030, +0.096] * |
| Judge groundedness (unvalidated) | 3.95 [3.76, 4.13] | 3.23 | 4.28 | +0.75 [+0.49, +1.00] * |
| Judge hallucination (unvalidated) | 0.367 | 0.526 | 0.171 | −0.172 [−0.247, −0.081] * |
| Model calls / est. cost per message | 1.54 / $0.0026 | 1.07 / $0.0024 | 0 / 0 | +0.47 * / +$0.0002 |

`*` = the interval excludes zero.

**B2 is the better classifier and escalator.** ResolveAI's advantage is confined to grounding and abstention: it answers far
less, and nothing it answers goes to a customer who needed a human. **B1 has a lower hallucination rate** because it copies real
historical replies — and still sends 9 unsafe ones. Ablations (Phase 6): rules-only risk has recall 0.730 with 18 safe and 0
unsafe replies; removing retrieval drops safe replies 9 → 4; removing the second opinion drops intent accuracy to 0.614.

**Latency and cost** (`performance/perf_final.md`, dev messages, one CPU process, a shared machine): no model 173 / 374 ms p50/p95;
cached 256 / 635 ms; live random dev messages 4,167 / 14,211 ms at 1.68 calls and $0.0030; live evidence-selected 6,277 / 18,224 ms
at 2.40 calls and $0.0044. 0 timeouts, retries or budget refusals. Cost uses GLM-5.2 list prices; real billing is unknown. The
first request after a start takes 24–67 s while models warm up, and golden runs were cache-served, so their latency is not live.

## 6. Failure analysis

The five most important remaining failure modes, with real golden rows from the release run
(`failure_modes.json`, `evaluation/judge_attribution.md`).

**F1 — A model-raised damage flag becomes a hardware handoff.** g045: *"PLEASE let users roll back to IOS10, my 5S battery now
goes from 100% to 40% within a few hours…"* Annotators: no escalation. Actual: `HUMAN_HANDOFF/hardware`, with the then-current
text *"We're sorry to hear about the damage… repair options"*. **Hypothesis:** the model raises `physical_damage` for battery and
reboot complaints, the policy treats model flags as hard reasons, and the template asserted damage regardless of the message.
**Impact:** 12 of 75 unnecessary handoffs; the template drew 15 judge hallucination flags; Dutch (g070) and Spanish (g188)
messages hit the hardware rule before the language redirect. **Status:** the template is reworded to assert nothing the rule
establishes (DECISIONS #118); the *flag* is unchanged because Phase 9's damage-aware prompt lost 2 true escalations on dev. The
golden run was not repeated, so these numbers describe the old text. **Next:** human-labelled dev set, then a `physical_damage`
definition under the same pre-registered rule.

**F2 — Non-support messages go to humans.** g028 *"When will we get the TV app in the UK?"*; g025 *"…Problem fixed :)"* →
`HUMAN_HANDOFF/insufficient_evidence`. **Hypothesis:** rule `other_non_closure` — product questions, suggestions and closures the
closure pattern misses cannot be answered from troubleshooting evidence, so the policy routes them to a person. **Impact:** 21
unnecessary handoffs, the largest single reason code. Harmless to the customer, wasteful for the team. **Why not fixed:** it needs
response templates for non-support messages, a product decision, and a dev evaluation. **Next:** a dev-evaluated acknowledgement
template and a broader closure pattern.

**F3 — A missed escalation from a rule wording gap.** g048 *"hey can you check the dm i sent!"* → `CLARIFICATION_REQUIRED`
instead of a repeat-contact handoff. **Hypothesis:** the rule matches "sent a dm" but not "dm i sent", and the risk model raised
nothing. **Impact:** the single missed escalation, worth 2.7 recall points. **Why not fixed:** it was found *on golden*, and a
golden-driven rule edit would be tuning on the evaluation set. **Next:** rule variants with dev regression examples.

**F4 — Autonomy is capped by the corpus, not by thresholds.** g074 *"After the latest iOS update… my mac and iPhone 7… facing
speed issues"* → `CLARIFICATION_REQUIRED/insufficient_evidence`. **Hypothesis:** historical replies to slowdowns are questions or
DM requests, not instructions, so no resolution cluster forms. **Impact:** 7 of 197 messages reach STRONG, all the same
autocorrect bug; autonomy is 6.1%. **Why not fixed:** loosening the gate trades grounding for coverage — offline WEAK-evidence
drafts hallucinated at 0.071. The lever is data, not thresholds. **Next:** a curated knowledge base beyond the November 2017
burst, with outcome labels.

**F5 — The judge is unvalidated and reads templates as claims.** g016's clarification *"…which software version is installed
(Settings > General > About)…"* was flagged hallucinated because the menu path is not in the evidence. Release hallucination rose
0.283 → 0.367: the 170 unchanged responses scored identically (53 → 53 flags) while 27 changed responses went from 0 to 16.
**Hypothesis:** the judge shares the drafter's model family — it rates GLM prose +0.67 to +0.84 higher than a second family does —
and scores template wording as factual claims. **Impact:** every groundedness and hallucination number is a model's opinion.
**Mitigation:** attribution analysis, a second-family subset, and deterministic metrics that never use the judge. **Next:** score
the 50-row packet and report weighted κ per dimension. This needs human raters and is the project's largest open gap.

## 7. What is misleading about my headline number?

**The strongest number:** *"Escalation recall 0.973 and zero unsafe autonomous replies."*

**How it could be misread:** "ResolveAI catches 97% of cases needing a human and never gives a customer a bad answer — it is
ready to automate AppleSupport's Twitter queue."

**The honest reading.** On one frozen set of 197 tweets from one week of 2017, ResolveAI answered only 12 messages. It was not
wrong on those, and it sent 75 people to a human who did not need one. A single prompt to the same model escalates more
accurately. Nothing here measures whether any answer fixed anything.

Why the number misleads:

- **Sample size.** 197 examples, **37 escalation positives**: one more miss moves recall 2.7 points; the interval is
  [0.912, 1.000].
- **Tiny autonomy.** **12 automatic replies** — 5 grounded troubleshooting replies about one bug plus 7 language redirects. "0
  unsafe" is 0 of 12, safe-rate interval [0.030, 0.096].
- **Recall is partly bought with conservatism.** An always-handoff system has recall 1.0 and precision 0.188; ResolveAI's
  precision is 0.324.
- **Class imbalance.** Macro-F1 weights a 7-row class (`hardware_damage`) like a 38-row class (`apps_services`).
- **No human labels.** Both golden annotation passes and all dev risk labels were written by AI; no agreement figure is
  human-human, and 0 of 50 judge rows are rated.
- **Judge limits.** Same family as the drafter, self-preference measured, templates read as claims, 9 parse failures.
- **Temporal and domain limits.** A 5-day November 2017 holdout dominated by the iOS 11 autocorrect bug; the knowledge base is
  the preceding weeks of one brand. Nothing transfers to another brand or year without re-annotation.
- **Retrieval ceiling.** Autonomy is structural: 7 of 197 messages have STRONG evidence.
- **The baseline wins the accuracy metrics:** escalation F1 0.819 vs 0.486, intent macro-F1 0.887 vs 0.854.
- **Groundedness is not correctness.** A reply faithful to a 2017 fix can still be wrong for this customer; no outcome data
  exists.
- **Safety is not usefulness.** A handoff is safe and often unhelpful; the pairwise judge preferred B2's responses 125 to 63.
- **"Safe coverage" is our own definition.** B2 answered 151 messages and 0 were "safe" under it, because it has no grounding
  contract. ResolveAI answered 12, all safe. This project wrote that definition.

## 8. Known limitations

**Evaluation:** no human evaluation; AI-derived golden and dev labels; 37 escalation positives and 12 automatic replies; one 2017
burst; reply quality measured only by an unvalidated same-family judge. **Quality:** escalation precision 0.324 (75 unnecessary
handoffs); the two worst fact-asserting templates are reworded and tested but clarification menu paths are not reviewed; the
model's private-info flag is effectively unused; autonomy capped at 6.1% by corpus coverage; grounded replies are not
outcome-validated. **Security and privacy:** regex PII detection (names and addresses missed); pattern-based injection detection;
static tokens, no TLS, operator login or vulnerability scanning. **Operations:** single process with process-local rate limits; a
timed-out provider thread cannot be killed; no metrics, alerting, retention or runbooks; 24–67 s cold start.

## 9. What I would do with one more week

1. **Human study:** score the 50-row packet, report judge–human agreement, and re-read every judge number through it.
2. **Human-labelled dev set:** ~200 escalation labels; re-run the Phase 9 and 10 risk candidates against them.
3. **Templates:** neutral handoff and clarification wording asserting nothing beyond the message, dev-evaluated with human review.
4. **`physical_damage`:** a prompt definition or corroboration candidate under the same pre-registered rule; let the non-English
   redirect precede model-flag handoffs; fix the `dm i sent` gap. All dev-first.
5. **Live latency:** a larger live sample exercising drafting and verification; parallelise the second opinion and the risk call.
6. **Hardening:** operator authentication in front of the console, TLS, dependency scanning in CI.
