# Decision log

These are the non-obvious engineering decisions actually made, each with the evidence behind it. Numbers reference artifacts in
this repository. The numbered entries (#1–#120) are the full record, in the order the decisions were made. Numbers are stable
because reports cite them. An entry replaced by a later one says so, and the index below points to the current one.

## The 12 decisions that shaped the system

The assignment asks for 10–15 non-obvious decisions. These are they, each with the measurement that drove it. The index and the
numbered record below are the full working, kept because the reports cite specific entries.

1. **AppleSupport, chosen by measurement, not preference.** All 108 brands scored on eight criteria under six weightings. The
   numeric leaders (Tesco, Spotify, British Airways) resolve by asking for an order number, so nothing is auto-answerable and
   there is nothing to ground in. AppleSupport has ~10k troubleshooting replies and a 56% handoff rate, which makes "answer or
   escalate" a real decision. Honest caveat: the decisive criterion was added after a qualitative read, so both rankings are
   reported. (#1)
2. **11 intents derived from the data, not from Banking77.** Banking77 was offered by the brief and deliberately not used: 77
   fine-grained banking intents do not transfer to consumer tech. The taxonomy came from reading the corpus, and
   `general_complaint` is an explicit fallback rather than a real class. (#6, `docs/INTENTS.md`)
3. **The LLM never decides escalation.** In the Phase-1A benchmark every model's escalation accuracy was at or below a constant
   never-escalate baseline (GLM-5.2: 56.7% vs 83.3%). The model extracts risk flags; 27 ordered deterministic rules decide and
   name the rule that fired. (#6, #35, #48)
4. **No evidence, no answer.** A reply is drafted only from retrieved historical cases that pass an evidence gate, must cite
   them, and is checked by a verifier and a nine-check output gate, then re-checked at the API boundary. The measured cost is a
   6.1% autonomous rate; the measured benefit is 0 unsafe automatic replies against the direct-LLM baseline's 3. (#33, #36, #37)
5. **Retrieval over a customer↔reply pair index, reranked toward replies that resolved.** Reply-only retrieval scored recall@5
   of 0.0. The resolution rerank raised resolution-bearing@1 from 0.18 to 0.76. The "was it resolved" signal is a weak rerank
   bonus, never a label (hand-checked precision 0.72 positive, 1.00 negative). (#5, #18–#22, #42–#49)
6. **Abstention is the product, and it is expensive.** ResolveAI's escalation F1 is 0.486 against the direct-LLM baseline's
   0.819, and humans receive 75 unnecessary handoffs on the golden set. That trade is deliberate and reported everywhere rather
   than hidden behind the recall number. (#33, #55, #104)
7. **One endpoint, `POST /api/v1/resolve`.** The brief suggested separate analyze / draft / decide endpoints; a draft endpoint
   would be a way to get an ungrounded reply out of the system, so there is exactly one path to a response. (#66)
8. **Trust work before product work.** PII is redacted before any storage or model call; prompt injection is a hard block;
   retrieved evidence that reads as instructions is quarantined before it reaches a prompt. 1.3% of tweets contain phone-like
   strings, so this was not optional. (#10, #71, #93–#98)
9. **A single-run golden protocol with pre-registered changes.** Dev decisions were written down before the golden set was
   touched, the release run happened once, and the runner refuses to run twice. Nothing was ever tuned on golden. (#57–#65, #99)
10. **The judge is treated as an instrument under test, not an oracle.** A frozen rubric, a second-family judge as a
    self-preference control (measured: the GLM judge rates GLM-written replies +0.79/+0.84/+0.67 above the second family), and a
    blinded 50-row human packet. **The human ratings do not exist, so judge–human agreement is not reported.** (#15, #101, #117)
11. **AI annotation is never called human evaluation.** Both golden-set passes were AI annotators under a written guide; the
    kappa is reported as consistency under the guide and an upper bound on human agreement. Saying so costs credibility and
    keeps honesty. (#15)
12. **Capitalization, greetings and small talk are product requirements, not polish.** "THANKS" was handed off while "thanks"
    was answered, because all-caps raised a frustration flag. Capitals are now never a signal, matching runs on Unicode-normalised
    keys, and greetings, thanks, acknowledgements and "talk to a person" are deterministic acts. (#108–#118)

## Index by area (context · options · evidence · decision · trade-off)

| Area | Context | Options considered | Evidence | Decision | Trade-off | Entries |
|---|---|---|---|---|---|---|
| Dataset | The assignment requires a real support corpus and a held-out evaluation. | Banking77; Kaggle Customer Support on Twitter | Twitter data has real brand replies to ground in; Banking77 has no replies | Customer Support on Twitter, temporal split by `created_at`, committed 20k-pair subsample | 2017 data, one short holdout burst | #2, #3, #4 |
| Brand | One brand keeps taxonomy and policy coherent. | numeric leaders (Tesco, Spotify, BA); consumer tech | Leaders resolve by collecting identifiers, so nothing is auto-resolvable; AppleSupport has about 10k troubleshooting replies | AppleSupport (runner-up AskPlayStation) | The decisive criterion was added after a qualitative read (stated) | #1 |
| Taxonomy | Intents must be annotatable and useful for routing. | many fine-grained intents; 11 coarse classes | 92.9% agreement between two passes on 11 classes; 7 taxonomy-gap rows | 11 classes, guide v1.1, gap flag instead of new classes | Coarse classes; `general_complaint` is a fallback | `docs/INTENTS.md`, #15 |
| Retrieval | Replies must be grounded in how the brand actually resolved similar issues. | BM25, dense MiniLM, dense BGE-small, hybrid RRF, reply or pair index, vector DB | All non-BM25 configurations within one CI (R@5 about 0.35, n = 46); BGE gave usable gate thresholds; the pair index equals the customer index with one index; the resolution rerank raised resolution-bearing@1 0.18 → 0.76 | Dense BGE-small pair index, resolution rerank, exact in-memory search, gate-v3 | Label-free relevance protocol; 7 of 197 golden rows reach STRONG | #18–#22, #42–#47, #49 |
| Classifier | Intent drives the query, the clarifying question and the policy's confidence input. | TF-IDF+LR, keyword rules, BGE+LR, LLM-only | Golden (Phase 3): BGE+LR macro-F1 0.618 vs TF-IDF+LR 0.550; the GLM second opinion raised accuracy 0.614 → 0.736; the full system reaches accuracy 0.848 (Phase 6) | BGE-small + calibrated LR; GLM second opinion only at LOW/MEDIUM, adopted only if it names a top-3 alternative | B2's one-prompt LLM is slightly better (macro-F1 0.887, not distinguishable) | #23–#31, #38 |
| LLM selection | A model is needed for bounded roles. | GLM-5.2, Gemini (unavailable), Groq models (rate-limited) | Phase 1A benchmark: GLM-5.2 intent accuracy 86.7%, 100% reply compliance, 0% transport failures | GLM-5.2 via an OpenAI-compatible endpoint, restricted to five roles | One vendor family; the judge shares it (self-preference measured) | #7, #8 |
| Grounding | Autonomous replies must not invent fixes. | free LLM answer; RAG answer; evidence-gated draft + verifier | B2 direct LLM: judge hallucination 0.526 and 3 unsafe replies; offline drafts on WEAK evidence: hallucination 0.071; verifier dev audit: 6 of 26 drafts had invented steps | Draft only on SUFFICIENT/STRONG evidence, cite evidence ids, verify lexically and with the model, output gate, API re-check | Low autonomous rate (6.1%) | #33, #36, #37, #53, #54, #69 |
| Policy | Who decides escalation? | LLM decides; LLM flags + deterministic policy | Phase 1A: every model's escalation accuracy at or below a never-escalate baseline | Ordered deterministic rules (policy-v3.1) name the reason; the model cannot clear a rule flag | Rule gaps are code changes; over-escalation from model flags | #6, #35, #48 |
| Risk | Risk signals are fuzzy (frustration, repeat contact, damage). | rules only; model only; rules OR model; corroboration | Rules-only ablation: recall 0.73 vs 0.95; Phase 9 corroborating three flags lost 22 true escalations; Phase 10 corroborating only `needs_private_info`: −9 unnecessary handoffs, 0 new misses on dev; golden −12 | Rules OR model, with `needs_private_info` requiring the rule (release) | Over-escalation remains, now mostly through `physical_damage` | #34, #50, #51, #89, #100 |
| Verification | Drafts can pass as plausible but unsupported. | none; lexical only; model only; both | Dev audit 6 true / 5 false / 1 uncertain blocks; an approving model is overridden by the coverage check (tested) | Lexical gates + model support check, one corrective redraft, then handoff with the draft attached | False blocks cost autonomy | #37, #54 |
| Evaluation | Claims need a frozen set, baselines, uncertainty and honesty about labels. | ad hoc checks; frozen golden + harness + judge + human packet | Bootstrap CIs everywhere; single-run protocol; cached reproduction identical | Frozen golden, three baselines, frozen judge rubric, pre-registered dev decisions, paired bootstrap | AI-derived labels; human study not completed | #57–#65, #88, #99, #101, #102 |
| Security | The API exposes an agent that reads customer text. | open API; OAuth platform; static scoped tokens | Single process; mandate forbids heavy platforms | Bearer tokens with two scopes before body parsing, process-local rate limits, PII redaction first, injection hard block, evidence quarantine, redacted logs | No TLS, SSO, rotation or vulnerability scanning (NOT READY) | #10, #71, #93–#98, #103 |
| Reliability | Model and dependency failures must never produce an ungrounded reply. | SDK retries; asyncio; client-enforced wall clock + budget | SDK hidden retries allowed 12 attempts; adversarial tests N, O, M | Client-owned timeout and budget, classified failures, handoff on failure, audit guard | A timed-out provider thread cannot be killed | #90–#92, #95, #103 |
| API | One contract for every client. | analyze/draft/decide endpoints; one `/resolve` | A draft endpoint would bypass the gates | One `POST /api/v1/resolve`, one error body, request and trace ids, invariant re-check | Clients receive the full result even if they need one field | #66–#70, #74–#77 |
| UI | Operators must see why, not just what. | dashboard mockup; real-API console | Smoke: 29 routes, 7 scenarios, 0 axe violations (Phase 9) | Next.js console with no agent logic; evidence scale ≠ confidence; honest wording | Full text only for this browser's simulations | #14, #81–#87 |
| Trade-offs | Safety vs usefulness. | maximise autonomy; evidence-first | B2 escalation F1 0.819 vs ResolveAI 0.486; unsafe autonomous 3 vs 0 | Evidence-first abstention; report the cost openly | Humans receive 75 unnecessary handoffs on golden | #33, #55, #104 |
| Infrastructure | Keep the project reproducible on a laptop. | Docker, Kubernetes, LangGraph, vector DB, Redis | No demonstrated purpose at this scale | None of them | Multi-process deployment would need a shared store and packaging | #12, #13, #94 |
| Conversation and text | The same words must behave the same, and small talk must not become a questionnaire. | lower-case everything; per-use-case normalization; model-based small-talk detection | No-model agent on five casings: only the all-caps frustration rule changed decisions; a case-insensitive serial pattern redacted product hashtags (157 of 20,000 KB messages) | Canonical matching keys, capitals never a signal, deterministic greeting / thanks / request-for-a-person rules, short replies classified with their issue, the language redirect behind the confidence floor, non-Latin scripts read off the characters (pipeline-v6.3, policy-v3.3) | Live behaviour differs from the evaluated v6.1 on 21 of 197 golden rows' input paths; golden not re-run | #108–#117 |

## Numbered record

1. **One brand, chosen by measurement, not assumption.** All 108 brands were scored on eight criteria under six weightings
   (`artifacts/brand_analysis/`). The numeric leaders (Tesco, SpotifyCares, British Airways) resolve by collecting
   identifiers, which makes auto-handling impossible. A reply-type analysis showed only consumer-tech brands have real
   troubleshooting corpora. AppleSupport won on that criterion with the largest troubleshooting corpus (~10k replies) and a
   56% handoff rate that makes escalation a genuine decision; AskPlayStation is the documented runner-up. We state that the
   decisive criterion was added after a qualitative read.
2. **Banking77 is not used.** It is banking vocabulary with 77 fine-grained intents; it would not transfer to consumer-tech
   support and the primary dataset was sufficient to derive a brand-specific taxonomy from clustering.
3. **Temporal split, never id/row order.** `tweet_id` correlates with time at Spearman 0.33; an id split is a random split
   that lets retrieval see the future (e.g. the iOS 11.1.1 fix). Holdout = final 5 days; KB strictly earlier.
4. **The golden set is isolated and frozen.** Sampled only from the holdout, hash-verified on load, never in any index.
   Evaluation data must not be editable to improve metrics.
5. **Historical-resolution retrieval with an outcome signal.** Grounding replies in how the brand actually resolved similar
   issues is the assignment's second requirement; the customer's next turn gives a weak "was it resolved" signal. It is a
   rerank bonus only: hand-check precision is 0.72 for positive and 1.00 for negative.
6. **Deterministic escalation policy; the LLM does not decide.** In the Phase 1A benchmark every model's escalation accuracy
   was at or below a constant never-escalate baseline (glm-5.2: 56.7% vs 83.3%). The LLM extracts risk flags; ordered rules
   decide and name the rule that fired.
7. **GLM-5.2, restricted to five roles.** Selected by the measured benchmark (best intent accuracy 86.7%, 100% reply
   compliance, 0% transport failures; Gemini was unavailable, Groq free tier rate-limited). Allowed roles: risk flags, intent
   second opinion, drafting, optional verification, judge. It never owns classification, retrieval, ranking or policy.
8. **Two LLM calls on the normal path.** Measured p50 latency is 5.2 s per call with a 71 s outlier; a 4-call pipeline is
   ~20 s per message. Understand + draft is the default; verification only when evidence contains concrete steps.
9. **Timeouts, one retry, deterministic fallback.** A call must never block the agent; on exhaustion the policy escalates
   with reason `llm_unavailable` and the trace records the fallback. *Superseded by #90–#91: a client-owned wall-clock timeout, a per-request budget and classified failures.*
10. **PII redaction before storage and before any LLM call.** Handles are anonymised in the data, but 1.3% of tweets contain
    phone-like strings and 0.2% order-like ids. The primary endpoint is plain HTTP. Redaction is typed and counted; the
    LLM client and trace recorder refuse unredacted text.
11. **SHA-256 cache keys.** Python's `hash()` is salted per process and silently defeated the benchmark cache. Keys are now
    cryptographic over model, prompt version, messages and parameters, and a test proves cross-process stability.
12. **No LangGraph, LlamaIndex, vector database, Ragas, MLflow, LangSmith or Langfuse.** Each was evaluated against a
    demonstrated-purpose rule (`artifacts/technology_recon/technology_comparison.md`): the loop is a DAG with one retry, the
    corpus is 30 MB in memory, the rubric and kappa study are custom by requirement. Re-entry triggers are documented.
13. **No Docker.** Explicitly out of scope: local Python/FastAPI and Node/Next.js execution, `npm run build && npm run start`
    for production validation. Containers would add infrastructure without a demonstrated purpose here.
14. **Next.js/React/TypeScript frontend consuming the real API.** A product surface, not a mockup; never hardcoded results.
15. **Annotator B is an isolated AI, and we say so.** A second human was not available; an isolated agent given only the
    guide is the honest substitute. Kappa (0.920 intent, 0.885 escalation) is reported as consistency under the guide, never
    as human-human agreement; the owner adjudicates disagreements via deterministic rules (guide v1.1).
16. **Silver labels for training, gold for evaluation (planned).** The classifier will train on LLM-labelled KB rows with a
    manual noise check, because hand-labelling thousands of rows is out of budget; the golden set stays untouched. *Superseded by #23–#24: implemented; silver-label precision about 71%.*
17. **Escalation cost is a sensitivity, not a fact.** Missed-escalation cost is reported at 1x, 3x and 5x.

18. **Retrieval configuration chosen by measurement: dense BGE-small, substantive-first, no BM25, no outcome bonus.**
    Ten configurations plus RRF-k and two extra variants were benchmarked on a 500-row dev set and once on the frozen golden
    set (`artifacts/retrieval/results.md`). All non-BM25 configs sit inside one 95% CI on recall@5 (0.17-0.46, n=46);
    the chosen one has the highest golden recall@5 (0.348), the lowest latency (p50 15 ms vs 92 ms for hybrid) and the
    least machinery. Hybrid RRF did not beat its own dense component on MRR in any pairing, so BM25 is kept only as a
    measured baseline. BGE-small over MiniLM: equal recall, BGE's cosine scale gave usable gate thresholds; MiniLM
    remains the documented fallback (40% faster to embed).
19. **Outcome-aware rerank bonus is off by default.** With-vs-without was measured on both sets: identical on golden,
    <= 0.008 MRR on dev. The signal is weak (hand-check precision 0.72) and the bonus is bounded to near-tie reordering;
    it stays as an explicit, auditable option rather than a silent influence.
20. **Substantive-first ordering is a structural rule, not the outcome signal.** Ranking non-DM replies ahead of DM
    handoffs raised "a substantive reply in the top-5" from 0.91 to 1.00 with no change in ranking metrics, and it is
    what allows the sufficiency gate to see resolutions at all. It is stated separately so nobody mistakes it for the
    weak outcome signal.
21. **Evidence-sufficiency gate calibrated on hand-checked dev verdicts, not on the automatic judge.** The automatic
    same-resolution judge cannot score the 70% of queries whose own reply was a DM handoff and misses paraphrased
    resolutions, so tuning against it drove precision to 0 at every grid point. Two failure classes found by inspecting
    verdicts (degenerate queries; clarify-only evidence) became deterministic rules (gate-v2); thresholds were then
    chosen on hand-checked dev verdicts. The checker is an AI annotator and this is stated; the Phase-7 human study is the
    real validation. Result: ~7% of golden queries pass, 13/14 usable on inspection.
22. **Relevance protocol is label-free by design and its limits are stated.** "Same-resolution" relevance (reply-side
    TF-IDF >= 0.5 to the query's own reply) needs no LLM and no hand labels, is independent of every retriever under
    test, and is insensitive to the threshold (0.4/0.5/0.6 identical). Its costs: only 46 of 197 golden queries are
    scorable, and paraphrased resolutions count as misses. Both are reported next to every number.

23. **Intent classifier: BGE-small embedding + logistic regression, temperature-calibrated, trained on silver-v2 labels.**
    Golden (197, once): accuracy 0.6142, macro-F1 0.6182 (95% CI [0.551, 0.677]) vs
    TF-IDF+LR 0.5498, keyword rules 0.5598, majority 0.0137. Selected on a silver-labelled dev set
    (C=4, no class weighting, HIGH+MEDIUM training bands); hyperparameters and the training-band choice were never touched
    after the golden run. Inference is a 384x11 matrix product on a cached embedding (~1 ms) plus one BGE-small encode (~55 ms).
24. **Silver labels are ~71% accurate and we say so.** No human intent labels exist outside golden, so training labels come
    from deterministic rules + keyword votes + BGE prototype similarity (`resolveai/intelligence/silver.py`). A 60-row hand
    check (AI annotator) found silver-v1 at ~58% precision on training rows; three deterministic fixes (word-boundary seeds,
    the I-glyph rule, a stricter non-English vote) raised silver-v2 to ~71% (HIGH band 82%). The dev set is silver-labelled
    too, so dev numbers are consistency-with-silver, not accuracy; the keyword baseline scores 1.0 on dev for that reason.
25. **Bounded context policy: at most 2 prior customer turns and 1 brand turn, 200 chars each, 600 total, de-duplicated,
    PII-guarded; the issue text is the last informative customer turn.** Context feeds the retrieval query and the
    insufficient-context flag. It does NOT feed the classifier by default: on golden, message+context scored
    0.6091 vs 0.6142 message-only, and an exploratory post-hoc variant
    (classify the prior issue text for short replies) was also worse on the 22 short replies (0.36 vs 0.41). The model is
    trained on single messages; concatenated context is out of distribution. Negative result, recorded.
26. **Query construction is deterministic string rules, no LLM.** Issue text + short reply, de-duplicated tokens, a canonical
    intent phrase only at HIGH confidence. It was benchmarked (variant D) and did not improve retrieval, so the phrase is
    kept only as an inspectable option; an LLM rewrite was not tried because no measured need appeared.
27. **Confidence bands from dev calibration: HIGH >= 0.75, MEDIUM >= 0.40.** Temperature 1.5 (dev NLL minimum); dev ECE
    0.0355, golden ECE 0.0774. Golden accuracy by band: HIGH 0.958 (n=48), MEDIUM 0.613 (n=75),
    LOW 0.378 (n=74): a HIGH-band prediction can be acted on; a LOW one cannot. The classifier never decides escalation.
28. **Multi-intent detection is advisory only.** Probability-ratio detection fires on 44 golden rows for 10 annotated
    (3 correct); it widens retrieval and marks ambiguity but never blocks handling or adds classes.
29. **Intent-aware retrieval did not improve Recall@5 and is kept only as a bounded boost.** On golden (46 scorable refs):
    raw 0.3478, context 0.3478, +intent boost 0.3261, +query phrase 0.3261;
    MRR flat at ~0.27. Same-intent Recall@5 rose 0.6244 -> 0.6802, i.e. the boost makes the top-5 look more
    on-topic without surfacing more same-resolution cases. The retriever keeps the boost (widen-not-discard, HIGH/MEDIUM
    only) because it costs nothing and helps the gate's intent-agreement signal; nothing else changed.
30. **GLM-5.2 second opinion: consulted at LOW/MEDIUM confidence, adopted only when it agrees with a top-3 alternative.**
    Golden accuracy 0.6142 -> 0.736 (27 fixed, 3 broken, 144 consulted, 33 applied);
    smoke-dev 0.6 -> 0.8333. It is an explicit, cached, PII-guarded step with a fixed policy; the classifier remains
    primary and the LLM alone on the consulted subset scored 0.8864.
31. **What did not improve results (Phase 3).** Context for classification, the exploratory issue-text variant, intent
    boosting for Recall@5, canonical query phrases, and the probability-ratio multi-intent detector. All are recorded with
    numbers rather than removed silently.

32. **The agent is an explicit execution graph, not a prompt.** `resolveai/agent/orchestrator.py`: PII redaction -> context ->
    intent (+ second opinion) -> retrieval -> evidence gate -> risk flags -> escalation policy -> draft -> verification -> output
    gate -> auto reply / clarification / handoff -> trace. Each stage writes a typed result and a trace event; a failed stage
    is recorded and routed to handoff through the same output gate. No LangGraph: the graph is ~250 lines of readable Python.
33. **Evidence-first invariant is enforced twice.** `policy.decide` refuses automation when `EvidenceSet.sufficient` is false,
    the drafter refuses to run without sufficient evidence, and the output gate re-checks `evidence_sufficient`,
    `evidence_refs_exist` and `response_verified` before AUTO_HANDLE. Tests cover each layer. On golden this yields
    AUTO_HANDLE 5.1%, CLARIFICATION_REQUIRED 36.5%, HUMAN_HANDOFF 58.4%
    (insufficient evidence on 93.9% of messages). A low autonomous rate with no ungrounded reply is the intended trade.
34. **Risk flags are extracted by rules AND GLM-5.2, OR-merged; the policy decides.** Fourteen flags (safety, security,
    privacy, account access, billing, legal, abuse, high impact, private info, damage, repeat contact, sensitive action,
    frustration, actionable). The LLM call is structured, cached, PII-guarded, with a 900-token cap (500 truncated the JSON);
    on failure the rules alone are used and the source is marked `fallback`.
35. **Escalation policy-v2 reason priority:** safety > security > legal > abusive > account access > billing/sensitive action
    > private info > hardware > repeat contact > vague-hostile > canned intents > insufficient context > taxonomy-gap risk
    > low confidence > conflicting evidence > insufficient evidence > grounding/verification > LLM unavailable > auto.
    Clarification is allowed only for non-risky, in-taxonomy issues whose evidence is thin. Golden escalation
    (HUMAN_HANDOFF vs annotated should_escalate): precision 0.3043, recall 0.9459, F1 0.4605 (always-escalate baseline F1 0.3162).
36. **Grounded drafting only from the EvidenceSet, with machine-readable references.** The drafter sees labelled,
    de-duplicated substantive evidence and must return `evidence_refs`; canned, clarification and handoff texts are
    deterministic templates. 12 drafts were generated on golden; 0.8333 passed verification; mean evidence coverage of
    auto replies 0.968.
37. **Verifier = lexical gates + GLM-5.2 support check; one corrective redraft, then escalate.** Lexical: length, no URL,
    no handle, no promises, no internal metadata, no PII/placeholders, evidence references valid, word coverage >= 0.25,
    intent consistency. The LLM check runs only for troubleshooting drafts that pass the lexical gates. Failure is never
    silent: the draft is attached to the handoff packet for a human to reuse or discard.
38. **Second-opinion adoption policy frozen on dev: `llm_conf_0.7`.** Candidates top-3, LOW-any/MEDIUM-top-3, LLM-confidence>=0.7,
    agree-top-2 were scored on the 30 hand-labelled smoke rows (primary) and 120 silver-HIGH dev rows (tie-break):
    smoke accuracies top3 0.8333, low_any_medium_top3 0.9, llm_conf_0.7 0.9333, agree_top2 0.7667. The silver tie-breaker favoured top-3, and 30 rows is thin; the pre-registered rule was followed.
39. **Query embedding is computed once and shared.** Before/after on 40 novel messages (no LLM): total p50 93.3 -> 89.5 ms.
    The gain is small because the retrieval-side encode was already served by the disk cache; kept because it is one
    memo dictionary and removes a duplicate model call from the hot path.
40. **Cost and latency are measured, not assumed.** Golden run: 2.437 LLM calls per message on average ({'HUMAN_HANDOFF': 2.48, 'CLARIFICATION_REQUIRED': 2.43, 'AUTO_HANDLE': 2.18}),
    cache hit rate 0.3167, ~734/1187 tokens in/out, estimated $0.0045 per message at list price; total p50 10874.8 ms, p95 25114.2 ms.
41. **This is a production-style reference implementation, not a deployment.** No Docker, no service mesh, no auth; local
    Python, file-backed traces, a CLI. The contracts (AgentResult, EvidenceSet, HandoffPacket, AgentTrace) are designed
    for the Phase-8 UI to render without change. *Status superseded: authentication and time budgets were added in Phase 9 (#93, #90); there is still no Docker (#13).*

42. **Reply-side indexing on its own is useless and dual fusion adds nothing (negative result, Phase 5).** Golden same-resolution
    R@5: customer index 0.3478, reply index 0.0, pair index 0.3478, dual customer+reply 0.2826, dual customer+pair 0.3478.
    The Phase-2 hypothesis H1 (reply-side indexing is the recall lever) is refuted by measurement. The pair index was selected on the
    dev objective (R@5 + resolution_bearing@3), within noise of customer+pair; kept because it needs one index instead of two.
43. **A reply is "resolution-bearing" only if a non-question sentence states an instruction or a released fix.** The Phase-1 weak
    `action_class` labels "Which iOS 11 version are you running?" as `update`; the first gate-v3 hand-check found half of the
    "resolution clusters" were such questions. `is_resolution_bearing` feeds the reranker, the clusters and `resolution_relevance`.
44. **Resolution clusters are action classes, not reply-text clusters.** Word-overlap clustering split differently-worded `update`
    replies into singletons and called 23 of 30 dev cases "mixed". Every cluster keeps its source ids and a representative reply.
45. **Gate-v3 has four states and never lowers a threshold.** Support similarity stays at the gate-v2 0.85; SUFFICIENT/STRONG need
    >= 3 independent instruction-bearing cases with the top cluster holding >= 0.6 of the support; WEAK (mixed or thin
    resolution evidence) may be clarified, never answered. `resolution_confidence` is a documented formula over measurable signals.
46. **Gate-v3 was calibrated on hand-checked dev verdicts, not the automatic judge.** The TF-IDF same-resolution judge gave 0 gate
    precision for every threshold (as in Phase 2). All 24 dev cases the loosest candidate called sufficient were labelled (AI annotator):
    chosen `share0.6_ms3` precision 0.929 (1 WRONG of 14) vs the loosest 0.792 (5 WRONG of 24).
    The acceptance bar was 0.9 because safe resolution quality is the phase target; coverage 0.028 of dev.
47. **A query must name a symptom.** Vague complaints ("my phone keeps bugging out") retrieved vague historical complaints that the brand
    had answered with the autocorrect workaround, so similarity and consistency were both high. Gate-v3 requires a symptom/feature
    term (classifier canonical terms + common iOS symptom words + the I-glyph forms); product names alone do not count.
48. **`general_complaint` is never auto-handled (policy-v3).** The taxonomy defines it as "no concrete actionable symptom"; 4 of the 5
    WRONG hand-check verdicts were such messages that slipped past the lexicon ("bug", "buggiest"). They get a clarifying question.
49. **Reranker weights are the documented defaults; the outcome bonus is bounded at 0.01.** The dev coordinate search (17 evaluations)
    did not move R@5 or resolution_bearing@3, so nothing was "tuned"; the bonus swing (0.015 score = 0.04 cosine) cannot overturn a
    semantic difference; the outcome regex remains a bonus, never a label. Both metrics reported: resolution_bearing@1 0.1777 -> 0.7563, R@5 0.3478 -> 0.2609.
50. **Risk flags use a compact schema (risk-flags-v2).** On 40 dev messages the 14-boolean schema fell back 32.5% of the time
    (1083.3 output tokens, p50 9129 ms); the list-of-raised-flags schema fell back 0.0% (684.5 tokens, p50 7486 ms).
    A 600-token cap re-introduced 25.0% fallbacks: the output size is the lever, not the cap. The proxy ignores reasoning-off parameters (tested).
    Unknown flag names are dropped and counted; a v1-shaped answer degrades to "no flags", never to a fallback.
51. **The risk LLM is skipped when the rules-only policy already guarantees a non-clarifiable handoff.** The LLM can only add flags,
    so the action cannot change; on 40 dev messages 14 calls were skipped (35.0%), calls per message 2.075 -> 1.7,
    40/40 identical actions; 3 handoffs carry a lower-priority reason code because the LLM's extra flag was never read. Accepted.
52. **Structured-output retries show an example shape, never the JSON schema.** GLM answered the schema itself on the corrective
    retry (8 of 26 drafts failed in A/B run 1); with the example shape and a 1.5x cap on a truncated first answer, 1 of 26 failed in run 2.
53. **Drafts lead with the highest-support resolution cluster (draft-v2).** A/B on the 13 draftable dev cases: ask-only 0.154 -> 0.0,
    actionable 0.692 -> 0.923, verified-and-actionable 0.462 -> 0.615, block rate 0.538 -> 0.385. Mixed resolutions are never
    chosen by the drafter: the gate calls them WEAK and the policy clarifies. Placeholders (`<url>`) are never copied.
54. **Verifier blocks were audited before touching the gates.** 12 blocked dev drafts: 6 true, 5 false, 1 uncertain; every false block
    was the mandated link paraphrase or a verifier outage. The only change is prompt-level (verify-v2 allows the paraphrase);
    outages still block. Lexical gates and the LLM support check stay.
55. **Autonomy is reported as a utility view under several escalation-cost weights, never as a rate.** Golden: `{"safe_auto_resolution": 9, "unsafe_auto": 0, "correct_non_autonomous": 37, "unnecessary_non_autonomous": 151}`;
    the agent beats always-handoff at every weight and never-escalate at every weight >= 1 with unsafe replies priced at w. The weights are assumptions.
56. **Golden was evaluated once with the final Phase 5 system.** AUTO 4.6% / CLARIFY 33.5% / HANDOFF 61.9%;
    evidence levels `{'INSUFFICIENT': 166, 'WEAK': 24, 'STRONG': 7}`; escalation recall 0.9459 (Phase 4: 0.9459); 0 autonomous replies on should-escalate rows;
    LLM calls per message 1.553 (Phase 4: 2.31). Phase 4 -> 5 table in artifacts/resolution/benchmark.md. A first golden pass of the
    retrieval variants ran before the resolution-bearing predicate bug was found by hand-check; it was discarded and nothing was tuned on golden.

57. **The proof is separate from the system: one harness, one record format, metrics as pure functions.** `resolveai/evaluation/`
    (records, metrics, bootstrap, baselines, systems, judge, slices, agreement, reporting) never imports agent decision logic; every
    system - ResolveAI, four ablations, three baselines - writes the same SystemRecord so one code path computes every table.
58. **Three baselines, not crippled, with stated information parity.** B0 majority-silver intent + modal "DM us" reply; B1 TF-IDF+LR
    (C chosen on silver dev) + nearest-neighbour historical reply + the same deterministic risk rules ResolveAI uses; B2 one GLM-5.2
    call with the taxonomy and the guide's escalation criteria and the FULL thread (ResolveAI sees a truncated thread). Golden results:
    B1 intent macro-F1 0.5498, B2 0.8867, ResolveAI 0.8538;
    unsafe autonomous replies B1 9, B2 3, ResolveAI 0.
59. **"Safe autonomous resolution" is strict and deterministic.** AUTO_HANDLE on a row the annotators did not mark for escalation AND
    (a verified troubleshooting reply with evidence references OR the exact intent-appropriate template for a closure/non-English row).
    Copied historical replies and direct-LLM replies never qualify (no grounding contract). ResolveAI 9 safe / 0 unsafe of 197.
60. **Judge rubric frozen before scoring, judge isolated from system identity, A/B order seeded.** rubric-v1 (6 ordinal dimensions with
    anchors at every level, 2 binary), GLM-5.2 at temperature 0, cap 1200 (a 3-draft dev smoke test used up to 859 tokens), strict parsing,
    failures recorded not dropped. The judge shares the drafter's model family (stated risk); qwen3.8-27b via Groq scores a subset as a
    second family. Pairwise ResolveAI vs B1 win/tie/loss 100/13/84; vs B2 63/7/125.
61. **No human rating is fabricated.** The blinded packet (50 examples) and docs/HUMAN_JUDGE_GUIDE.md exist; judge_agreement.md
    says PENDING_HUMAN_RATINGS until the owner scores it. Every earlier hand-check is listed as AI annotation in docs/EVALUATION.md.
62. **Uncertainty is reported with every headline number.** 1000x seeded bootstrap; paired resampling for differences; intervals that overlap
    are called not distinguishable. ResolveAI minus B2 direct-LLM: escalation recall 0.027 [-0.0883, 0.1396],
    safe-auto rate 0.0457 [0.0203, 0.0761].
63. **Ablations are single switches on the production agent; the verifier and the gate are only removed offline.** Rules-only risk
    (minus_risk_llm) changes safe-auto rate by -0.0457 and escalation recall by 0.2162 versus the full system;
    drafting on WEAK evidence offline: 15 rows, 10 verified, judge hallucination 0.071 (the abstention curve).
64. **Two rule bugs found by the evaluation are documented, not patched, in this phase.** `<PHONE>`-style tokens never fire the
    private-info rule (word boundary before `<`), and "dm i sent" misses the repeat-contact rule; both are the golden false negatives.
    The evaluated system is the frozen Phase 5 system; the fixes and regression tests are the first Phase 7 item. *Superseded by #72 (the private-info token rule is fixed). The `dm i sent` repeat-contact gap remains: golden g048 is the one missed escalation in the release.*
65. **Cached reproduction is the default; live is explicit.** `python scripts/evaluate.py --cached` verifies the golden hash and the
    SHA-256 of every input artifact, recomputes everything in 182.7 s with no API call; `--live` re-runs the
    systems, the judge and the offline ablations. Cache-served runs report the tokens their calls consumed live, so cost is comparable; latency is not.

66. **One canonical agent endpoint, `POST /api/v1/resolve`.** The brief suggested separate analyze, draft, decision and simulate endpoints. Each
    would either re-run the whole pipeline or run part of it. A draft endpoint without the evidence gate, risk flags and policy would be a way
    around the invariant, so the single response carries the decision, the evidence and the packets, and clients read what they need.
67. **The API is a thin layer over the one orchestrator.** `AgentService` owns a single `ResolveAI` instance, loaded in a background thread. The CLI
    (`python -m resolveai`), the demo, the evaluation harness and the API all construct the same class, and a test asserts it. The API package
    contains no decision logic.
68. **New contracts go into the existing schemas, not a parallel API schema system.** `ClarificationPacket`, `DecisionSummary`, `EvidenceRef` and
    `RuntimeVersions` live in `schemas/core.py` and are populated by the agent, so the CLI and traces get them too. The API adds only the request
    model and presentation wrappers (`outcome`, `response`).
69. **The API re-checks the autonomy invariant and fails closed.** The output gate is the authority, but an automatic reply that reaches the API
    with insufficient evidence, missing or unknown references, failed verification, a policy block or a hard risk flag returns
    500 `autonomy_invariant_violation`, and the text is withheld. A test forges such a result to prove it.
70. **An LLM outage is a 200 handoff, not a 503.** Model timeouts, invalid JSON and structured-output failures already have deterministic
    fallbacks. The API returns the safe decision with reason `llm_unavailable`. A 503 is reserved for the agent itself not being loaded.
71. **Prompt injection is a deterministic hard block (policy-v3.1).** `trust/injection.py` detects six families of attempts: instruction override,
    configuration reveal, role override, privileged command, evidence spoofing and secret request. It checks every turn, including
    caller-supplied brand turns. A detection skips the second-opinion and risk LLM calls and hands off. The false-positive rate on
    19953 historical customer messages is 0 flagged. Defence in depth stays in place:
    code-owned policy, evidence only from the index, and the verifier plus output gate.
72. **The private-info rule now fires on redaction tokens.** `\b<PHONE>` could never match, so a customer who shared a phone number or case
    number was not routed to private handling (golden g157, found in Phase 6). The fix plus regression tests changes behaviour against the
    evaluated Phase 5 system. Golden was not re-run, to avoid another pass over the frozen set.
73. **Clarifying questions are slot-aware.** The agent no longer asks for a device or software version the customer already stated anywhere in
    their turns. The `ClarificationPacket` lists what is missing and what was already provided. Another behaviour change against the evaluated
    system: wording only, no decisions.
74. **Correlation: `request_id` and `trace_id` are both first-class.** A valid caller `X-Request-ID` is kept, otherwise one is generated. Both ids
    come back in the body and headers. The trace stores the request id, pipeline version, component versions, a config hash (agent config,
    frozen gate and rerank files, classifier artifact hash, prompt versions, model), stage statuses and per-stage latency.
75. **Resource protection is in-process.** It consists of a per-client sliding-window rate limit, one agent execution at a time with a bounded
    queue (429 beyond it), Content-Length required and capped before JSON parsing, and configurable conversation limits checked before any
    model call. Serialising executions keeps per-request token and cost accounting exact. No Redis: one process runs one agent.
76. **Three configuration profiles (development, test, demo) plus `RESOLVEAI_*` overrides.** Wildcard CORS is rejected in every profile, the
    server binds to loopback by default, and `/config` exposes no key, base URL or absolute path.
77. **Health never infers, readiness never calls the LLM.** Readiness checks the loaded agent, knowledge-base rows and indexes, the classifier
    artifact, gate and policy versions, and trace-store writability. It reports the LLM as configured or not without contacting it.
78. **The PII scan of traces excludes system-generated structural fields.** The redaction regexes misread ISO timestamps ("2026-09-10T10") as long
    ids and 10-digit runs in hex trace ids as phone numbers. Every other trace string is scanned. This is a known limitation of the
    regex detector, which also misses names and addresses.
79. **The security scan compares the real `.env` secret values in memory and never prints them.** It also flagged the private LLM endpoint
    address in two Phase 1A reports; the address was replaced with a placeholder.
80. **Live-LLM demo runs exposed the Phase 6 over-escalation in the product.** With the real risk model, "still not working" was flagged as
    repeat contact, although guide rule R1 says vague phrases do not count, and a battery drain was flagged as physical damage. Both became
    handoffs. The behaviour is safe but unhelpful. It was not patched in Phase 7, because the risk prompt is part of the evaluated system and
    a change needs a dev re-evaluation. The demo keeps one such conversation as an explicit known-limitation scenario.
    Demo: 7 of 7 scenarios passed in the saved run.

## Phase 8: operator console

81. **The console holds no agent logic: it names, lays out and simulates.** Every decision, packet, metric and piece of evidence comes from
    the API. `frontend/lib/labels.ts` only maps codes to words. Handoff severity and queue are a display grouping of the policy reason
    code for triage, and the UI labels them as such.
82. **Two additive API changes instead of UI inference.**
    - Trace list items gained intent, intent confidence and band, evidence level and sufficiency, risk flags, policy rule and version,
      channel and model-call count. These are read from events each trace already records.
    - `/evaluation/summary` additionally serves, as stored: the retrieval and reply-quality reports, the judge agreement, the
      misleading-headline and uncertainty markdown, and the golden-set provenance.

    No existing field changed, and the frozen artifacts are read, never rewritten.
83. **Full results live in the browser, not in the trace store.** Traces deliberately never store customer or evidence text. Rather than
    weaken that, the console keeps the last 50 already-redacted `/resolve` responses in localStorage and says so on the page. For
    other traces it shows a view reconstructed from the audit trace, with an explicit notice.
84. **Browser calls go through a same-origin forwarder** (`app/api/v1/[...path]/route.ts`). It keeps the API address on the server, gives
    the console no CORS dependency, and forwards only the API's own endpoints. Status, body and correlation headers pass through
    unchanged.
85. **Response types are generated from OpenAPI and made fully present.** Pydantic defaults make fields optional in the schema, although
    FastAPI always serializes them. The console types every response property as present, and a contract test checks this against
    responses captured from the live API (`scripts/phase8/capture_fixtures.py`). The one scripted fixture, a verifier that rejects the
    draft, says so in its file name.
86. **Evidence sufficiency is a four-step scale; confidence is a meter.** The two are never drawn alike, so an operator does not read "STRONG
    evidence" as "95% sure".
87. **Honest loading and honest KPIs.** A run shows only the elapsed time; stage statuses appear when the API answers. The live overview
    does not show an "unsafe autonomous responses" number, because that needs annotated ground truth; the tile says so and points to
    the evaluation.

## Phase 9: hardening, trust, reliability and final evaluation

88. **Human evaluation stays pending; nothing is fabricated.**
    - Problem: the judge's agreement with humans is still unmeasured.
    - Evidence: `data/human_eval/human_scoring_packet.csv` has 50 rows and 0 filled `human_*` cells.
    - Options: fill it from another model (rejected; it would be AI-AI agreement mislabelled as human), or stop Phase 9 (rejected;
      the rest does not depend on it).
    - Decision: status stays PENDING_HUMAN_RATINGS. The packet, `docs/HUMAN_JUDGE_GUIDE.md` and the agreement code path are
      checked, and the exact remaining step is named: a human fills the packet, then `python scripts/evaluate.py --cached` runs.
89. **The risk-model over-escalation candidates were all rejected on dev; production risk extraction is kept.**
    - Problem: the live risk model escalates vague follow-ups and battery drains (#80).
    - Experiment (`scripts/phase9/a_risk_dev_experiment.py`, DEV only): 240 holdout messages, golden excluded and asserted,
      through the unchanged understanding pipeline.
    - Variants:
      - V0: production;
      - V1: rules only;
      - V2: model-only `repeat_contact`/`physical_damage`/`needs_private_info` need rule corroboration;
      - V3: prompt risk-flags-v3 with the guide's R1/R3/private-info definitions;
      - V4: V3 + V2.
    - The 76 rows where the variants disagree on handoff were labelled blind by an AI annotator (not human) under the guide.
    - The acceptance rule was fixed in `b_risk_dev_metrics.py` before any result existed: no new misses for safety, legal or
      private info; at most one new miss; at least 3 fewer unnecessary handoffs; fallback rate within 5 pp.
    - Result: V0 had 41 unnecessary handoffs and 1 miss. V2 and V4 add 22 misses: the rules miss most explicitly stated prior
      attempts, so corroboration is unsafe. V3 removes 11 unnecessary handoffs (20 of 22 removed correctly, Wilson 95%
      [0.72, 0.98]) but adds 2 misses: a dead iPad and a customer who waited 35 minutes on the phone.
    - Decision: no change (`artifacts/phase9/risk/frozen_config.json`).
    - Trade-off: the over-escalation stays, and the report shows it.
    - The largest false-positive source is the model-only `needs_private_info` flag (17 of 41). No candidate targeted it, and
      that is the next experiment.
90. **The model client owns timeouts and retries.**
    - Problem: the OpenAI SDK defaults to `max_retries=2` under our own retry and the structured-output retry, so one logical
      call could make up to 12 HTTP attempts of 30 s each (the 67 s first request observed in Phase 8).
    - Options: trust the SDK timeout (a per-read timeout does not bound a slow trickle); asyncio cancellation (would rewrite
      the synchronous agent); or a client-enforced wall-clock limit on a worker thread.
    - Decision: SDK retries are off. `LLMClient` runs each attempt on a thread and stops waiting at `min(timeout, remaining
      budget)`. There is one bounded retry, and a per-request `Deadline` refuses to start a call with under 2 s left.
    - Trade-off: a timed-out provider call cannot be killed; its thread finishes in the background and its result is discarded.
91. **Failures are classified and degrade by type.**
    - Codes: `model_timeout` (timeout or budget spent), `llm_unavailable` (outage or invalid output), `dependency_failure` with
      the stage, and `audit_unavailable`. Recorded as `trace.failures [{category, stage, kind}]`, codes only.
    - A failed risk-model call still falls back to the deterministic rules instead of blocking autonomy, because rules-only
      risk is the measured safety floor: the Phase 6 `minus_risk_llm` ablation had 0 unsafe autonomous replies.
    - A verifier that could not run escalates at once instead of spending the budget on a redraft.
92. **Risk stage status separates "skipped" from "fallback".**
    - Problem: a deliberately skipped risk call (rules hard block, guaranteed handoff) was recorded as `fallback`, the same as
      a failed call. The 75 "fallback" rows in the Phase 5 golden run mixed both.
    - Decision: skipped calls are now `skipped`, and only failures are `fallback`. Observability only; no decision changes.
93. **Authentication is static bearer tokens with two scopes, enforced before the body is read.**
    - Options: OAuth/OIDC or an identity platform (out of scope for a single-process reference, and the mandate forbids a
      heavyweight platform); API keys in query strings (leak into logs); middleware tokens.
    - Decision: `RESOLVEAI_API_TOKEN` (resolve + read) and `RESOLVEAI_READ_TOKEN` (read). SHA-256 digests are compared with
      `compare_digest` against every entry.
    - Semantics: one 401 for missing or wrong credentials, 403 for a missing scope. Health is public; readiness is public
      but reduced to booleans. Authentication runs before JSON parsing so validation errors reveal nothing.
    - The `production` profile refuses to start without a 32+ character token and refuses `RESOLVEAI_AUTH_REQUIRED=false`;
      development, demo and test disable auth explicitly.
    - Trade-off: no per-user identity, rotation or revocation list; changing a token needs a restart.
94. **Rate limiting stays in-process and says so.**
    - Decision: three sliding-window limiters (resolve, read, failed authentication) keyed by principal or client address, plus
      a queue timeout on the single agent slot so a waiting request never blocks forever. `/config` reports
      `rate_limit_scope: process-local`.
    - Trade-off: limits are per process; a multi-process deployment would need a shared store. Redis was not added for a
      single process.
95. **No audit trail, no autonomous reply.** If the trace cannot be written, an `AUTO_HANDLE` is converted to a handoff with
    reason `audit_unavailable` and the blocking check `audit_trace_written`. Clarifications and handoffs are still returned with
    `stage_status.trace = failed`. The alternative, returning the reply untraced, would make an automatic answer unauditable.
96. **Retrieved evidence is quarantined and re-redacted.**
    - Problem: retrieved historical text reaches drafting prompts and the console. A poisoned knowledge-base row could carry
      instructions, and the shipped corpus was redacted with the pre-Phase-9 phone pattern.
    - Decision: items whose text matches the injection detector are dropped before the evidence gate (`quarantined_ids`), and
      evidence text is redacted again when items are built.
    - Measurement: 0 of 20,000 corpus rows match the detector, so current results are unchanged. 4 knowledge-base customer
      messages and 4 context entries contain a sentence-end phone or case number the old pattern missed.
    - The frozen processed data is not rewritten; `tests/test_retrieval.py` now pins that measured gap instead of claiming the
      stored rows are clean.
97. **The phone pattern stops refusing numbers at the end of a sentence.**
    - Problem: the adversarial PII test found "call 555-123-4567." unredacted. The guards `(?<![\d.])` / `(?![\d.])` rejected a
      trailing full stop.
    - Decision: only a digit or `.<digit>` blocks a match now.
    - Measurement: 0 golden messages or contexts change; version strings (11.1.2), dates and prices stay untouched (tested).
    - Known gaps are documented, not claimed: names, addresses, spelled-out or obfuscated identifiers, lowercase serials.
98. **Logs never carry raw exception text.** Unhandled API errors log the exception type, a PII-redacted and truncated message,
    and code locations only. Trace error fields use the same redaction, because exception text can quote the input that caused
    it.
99. **The final golden evaluation was run once, and its judge result is reported as a regression, not explained away.**
    - Protocol: `scripts/phase9/d_golden_final.py run phase9_final` ran after `frozen_config.json` was written. Golden hash
      verified before and after; 0 live model calls (cache-served); the script refuses to run again. No separate Phase 8 run:
      Phase 8 changed no decision, the dev decision kept its risk configuration, and the Phase 9 hardening changes alter no
      golden input.
    - Decisions: 2 of 197 changed from Phase 5 (g002, g157), both correct `private_info` escalations from the Phase 7
      token-rule fix. Escalation recall 0.946 → 0.973 [0.912, 1.000] (paired +0.027 [0.000, +0.091]). Unnecessary
      escalations stay at 87. Intent and autonomy are unchanged (9 safe, 0 unsafe).
    - Judge (frozen rubric-v1, GLM-5.2): groundedness 4.28 → 4.19 [4.03, 4.36], hallucination rate 0.216 → 0.283.
    - Attribution: 65 of the 67 responses whose text changed are clarifying questions reworded by the Phase 7 slot-aware
      clarification change, first judged here.
      - On those rows, hallucination flags rose 17 → 29 and groundedness fell 4.09 → 3.86.
      - The 127 identical responses judged in both runs are unchanged (25 → 25 flags, 0 flips). They replayed from the judge
        cache, so they show identical output, not judge stability.
      - Judge variance on the new texts cannot be separated from the wording effect.
    - Decision: report it as a regression introduced in Phase 7. Clarification wording is not changed against golden; it goes
      to Phase 10 as a dev-evaluated item, with human review, because the judge itself is unvalidated.

## Phase 10: final release

100. **The targeted private-info candidate was accepted on dev, under the Phase 9 rule applied unchanged.**
     - Pre-registration: `artifacts/final/risk_experiment/PREREGISTRATION.md`, written before the run; its SHA-256 is in the
       report.
     - Candidate: a model-raised `needs_private_info` counts only when the deterministic private-info rule fires
       (`AgentConfig.risk_corroborate = ("needs_private_info",)`). Nothing else changes.
     - Data: the same 240 dev rows and 76 AI-labelled disagreement rows as Phase 9; no human-labelled dev set exists. V0 reproduced
       Phase 9 on every row, with 0 live model calls.
     - Result:
       - unnecessary handoffs fell from 41 to 32, and missed escalations stayed at 1;
       - 9 handoffs were removed, all correctly (Wilson 95% [0.70, 1.00]): 8 became clarifications and 1 a non-English redirect;
       - the model raised `needs_private_info` on 26 of 153 calls, and the rule agreed on none. In practice the model's flag is now
         ignored, and private handling rests on the rules (redaction tokens, case numbers, serials).
     - Decision: enabled in the release (pipeline-v6.1).
     - Trade-off: a private-info case that the rules cannot see and only the model would catch is now missed. None occurred in the
       dev or golden rows.
101. **The golden set was run once more, for the release configuration, because the pre-registration required it.**
     - `scripts/final/g_golden_release.py` ran after `decision.json` existed. It refuses to rerun and never overwrites
       `phase9_final`. It made 0 live model calls, and the golden hash was verified before and after.
     - Result vs Phase 9 final (paired):
       - unnecessary handoffs 87 → 75 (−12 [−19, −6]);
       - escalation precision 0.293 → 0.324 (+0.032 [+0.015, +0.052]), recall unchanged at 0.973;
       - safe autonomous replies 9 → 12 (three non-English messages now reach the language redirect), unsafe still 0.
     - This is not a second tuning pass: nothing was chosen on golden, and no further golden run follows.
102. **The release's judge regression is attributed and reported, not fixed against golden.**
     - The judge (GLM-5.2, rubric-v1, unvalidated) moved: groundedness 4.19 → 3.95, hallucination rate 0.283 → 0.367. Both paired
       intervals exclude zero.
     - Attribution (`artifacts/final/evaluation/judge_attribution.md`):
       - the 170 unchanged responses score identically (53 → 53 flags, 0 flips); the whole change is on the 27 changed responses
         (0 → 16 flags);
       - 10 of those flags fall on the hardware handoff line "We're sorry to hear about the damage… repair options", sent when the
         model's `physical_damage` flag fired on a battery or reboot complaint;
       - the rest fall on the clarification menu path and the repeat-contact line.
     - Decision: templates that assert facts the message does not contain are a real defect. This one was found through golden
       judge notes, so rewording against golden would be tuning on the evaluation set. The fix is documented as the next action:
       templates that assert nothing beyond the message, evaluated on dev with human review.
103. **A corrupted trace line no longer takes the audit API down.**
     - Found by adversarial suite case 20: one unparseable JSONL line made `GET /api/v1/traces` return 500 (`json.loads` in
       `recent_traces`), and a corrupted matching record raised in `TraceStore.read`.
     - Fix: the listing skips and counts unreadable lines (logged as a count, never echoed), and a corrupted record is never served.
     - Regression tests: `tests/test_trace_store_corruption.py` and suite case 20.
104. **The remaining over-escalation is reported, not traded for recall.**
     - The release golden run has 75 unnecessary handoffs:
       - insufficient_evidence 21, mostly non-support messages and closures without a template;
       - repeat_contact 12;
       - hardware 12, the model's `physical_damage` on battery and reboot complaints, now the largest model-flag source;
       - vague_hostile 8, payment_billing 7, safety 5, private_info 4, legal_media 4, other 2.
     - Options already measured: Phase 9's V3 prompt fixed most `physical_damage` raises but lost two true escalations, and
       corroborating the soft flags with rules loses repeat-contact recall.
     - Next: a human-labelled dev set and a `physical_damage` definition in the prompt, measured under the same pre-registered rule.
105. **Version 1.0.0 marks the final reference release, not production readiness.** Backend and console move to 1.0.0 because
     pipeline-v6.1 changes decisions. `docs/PRODUCTION_READINESS.md` still lists what a deployment lacks.
106. **Test tooling is declared, and a clean-clone check is part of the release.**
     - Problem: `requirements.txt` did not list pytest, so a fresh clone could not run the documented test command.
     - Fix: `requirements-dev.txt` adds pytest, ruff and httpx.
     - Check: `scripts/final/h_clean_env_check.py` copies only committable files into a new directory. It then installs a fresh
       virtual environment with an isolated model cache and no credentials, and runs the tests, the demo, the verification, the
       frontend checks and the API.
     - Finding: the check's first run failed. `resolveai/retrieval/bm25.py` imports `rank_bm25`, which `requirements.txt` never
       declared; the development machine had it installed, so no local test could show the gap. An import audit also found
       `scipy` imported directly but undeclared.
     - Fix: both are now declared. The failed attempt is kept (`artifacts/final/clean_env_check.attempt1.md`).
     - Second finding (`artifacts/final/clean_env_check.attempt2.json`). With a fresh virtual environment the install, the demo,
       the API, lint, typecheck and build all passed on the clean copy. Three problems remained:
       - The root `.gitignore` rule `traces/`, meant for runtime traces, also matched `frontend/app/traces/`. The console's Traces
         pages had never been committable. The rule is now anchored as `/traces/`. This missing directory is what caused the
         clean copy's 12 frontend test failures. With the corrected rule, the committable frontend passes 93 of 93 tests, both
         under the Windows short-name temp path and under a normal path.
       - `tests/test_leakage.py::test_golden_rows_come_from_holdout` fell back to the 2,000-row subsample when the local-only full
         pair file was absent. It now checks the manifest's recorded holdout boundaries.
       - The verification script piped paths to `git check-ignore` in text mode. On Windows every path but the last gained a `\r`,
         so gitignored local-only files looked missing. It now pipes bytes, and treats local-only files in the Phase 7 snapshot the
         same way.
     - Third run: a targeted re-check of the corrected file set (current interpreter and embedding cache reused, stated in the
       report) is `artifacts/final/clean_env_check.json`.
107. **Final verification is non-destructive.**
     - `scripts/final/f_final_verification.py` checks the golden hash and compares every frozen file with the Phase 10 start snapshot.
     - It runs the Phase 7 integrity script, the cached evaluation and the security scan, with their outputs redirected to
       `artifacts/final/`.
     - The older entry points that write frozen records (`scripts/security_scan.py`, `scripts/evaluate.py --cached`) are documented
       rather than rewritten, so earlier phase records stay reproducible.
108. **Capitalization and punctuation are not risk signals (final product pass, pipeline-v6.3).**
     - Problem: the no-model agent was run on the same messages in five casings. Intent, confidence and evidence were identical
       (the BGE tokenizer lower-cases), but `agent/risk.py` raised `high_frustration` for any all-caps word of six or more
       letters and for "!!!". "THANKS" was handed off as "frustrated, no concrete issue" while "thanks" got the closing template,
       and "AGENT PLEASE" was treated as hostile.
     - Decision: frustration is read from words only; the all-caps and exclamation signals are removed.
     - Impact: 6 of 197 golden rows lose a flag raised only by capitals or "!" (input-level check, `scripts/evaluation/behaviour_change_impact.py`;
       the golden run was not repeated).
     - Trade-off: a customer who shouts without angry words is no longer escalated as frustrated.
109. **Matching uses a canonical key; the message itself is never rewritten.**
     - `trust/normalize.py` builds a comparison key: NFKC, Unicode format characters removed, `casefold()`, whitespace collapsed.
       Line breaks are kept where a pattern is line-anchored (the injection detector).
     - Used by injection detection (full-width letters and zero-width characters can no longer hide "ignore your previous
       instructions"), the risk rules and conversation acts. The console's search and URL filters use the same idea
       (`frontend/lib/text.ts`), and the API folds trace ids, the `action` filter and profile names to their canonical form.
     - Exception, measured: serial/IMEI ids stay upper-case only. A case-insensitive pattern newly matched 157 of 20,000
       knowledge-base messages, almost all product hashtags ("iphone7plus", "ios11update"), so it would redact product names.
110. **A bare greeting gets a greeting, not a questionnaire (policy-v3.3, rule `canned:greeting`).**
     - Problem: "hi" retrieved 50 historical cases and returned a clarification asking for device, version and symptom.
     - Decision: a message that contains only a greeting (any case, punctuation, emoji or addressee) is answered with a fixed
       greeting. Retrieval, the second opinion and the risk-model call are skipped (evidence reason `not_applicable`). The rule sits
       after every hard block and before the intent-based rules. "hi, my iphone won't turn on" is a support request.
     - Impact: 0 golden rows are greeting-only.
111. **An explicit request for a person is its own handoff reason (`human_requested`); thanks and bare acknowledgements are separated.**
     - Problem: "can I talk to a human" got a device questionnaire. "I want to speak to a real person" was handed off under
       `other_non_closure`, labelled "No proven resolution". A bare "yes" answering an agent question got "You're welcome!".
     - Decision: a deterministic pattern routes explicit requests for a person to a handoff after the safety, security, account,
       billing, private-information, hardware and repeat-contact rules, so a more specific reason still wins. Thanks is always a
       closure; a bare yes/no/ok is a closure only when no earlier customer turn exists.
     - Impact: 0 golden rows are affected.
112. **A short reply is classified with the issue it answers.**
     - Context: the classifier reads the current message by design; on golden, message plus context scored 0.609 against 0.614 for
       the message alone.
     - Problem: the context builder already joined a short reply to its issue, but the orchestrator embedded only the current
       message for the classifier. "still happening" after a battery complaint was classified `other` and handed off as "not a
       troubleshooting request"; "that didn't work" became a keyboard bug.
     - Decision: only when the message is a short reply and the thread has an issue, the classifier reads the builder's issue-plus-reply
       text. Context never overrides a hard block (tested with an injection in a thread). The short-reply patterns also cover
       "(it|that) still doesn't / won't work".
     - Impact: 12 of 197 golden rows are short replies with an issue; widening the patterns changed no golden row. Golden numbers
       describe pipeline-v6.1 (`docs/EVALUATION.md` §4).

### Release-readiness pass (pipeline-v6.3 / policy-v3.3)

113. **The English-only redirect obeys the same confidence floor as every other automatic path.**
     - Problem: `canned:non_english` sat *before* the low-confidence rule, so a LOW-confidence classifier guess sent a terminal,
       customer-visible "we only support English" reply. A typo-heavy English message reached it in testing.
     - Measurement (4,000 corpus messages, no model, not golden): 143 were predicted `non_english` — 47 HIGH, 72 MEDIUM, 24 LOW.
       The HIGH and MEDIUM bands are overwhelmingly real Spanish, French, Portuguese, Italian, German, Turkish and Dutch. The LOW
       band is mostly English ("is this legitimate", "It doesn't happen if the phone is locked", "MacBook Pro 2017 with high
       sierra in French"). The deterministic non-English hard rule corroborated only 26 of 143, so requiring corroboration would
       have broken real non-English handling; the confidence band is the signal that separates them.
     - Decision: move the rule below `low_confidence`. MEDIUM and HIGH keep the redirect; LOW gets the standard clarification.
       Telling an English speaker we cannot serve them is worse than asking a non-English speaker to restate.
     - Alternative rejected: requiring HIGH confidence. That would have removed the redirect from 119 of 143 messages, most of
       them genuinely not English.
     - Impact: 3 of 197 golden rows reach the changed path. Residual, stated: a MEDIUM-confidence typo-heavy English message can
       still get the redirect.
114. **A message written mostly in a non-Latin script is recognised deterministically, not predicted.**
     - Problem: the word tokenizer only sees Latin words, so "iPhoneの電源が入りません" has zero content tokens, looks like "no issue
       stated" and got an English clarifying question the customer cannot read.
     - Decision: `conversation_acts.is_non_latin_script` counts letters outside the Latin script (NFKC, ≥ 6 letters, ≥ 50% share)
       and the policy routes those to the language redirect under its own rule `canned:non_latin_script`, placed after every hard
       block and before `insufficient_context`. Script is a property of the characters, so no confidence floor is needed and no
       model is called. The classifier still handles Latin-script languages.
     - Impact: 1 of 197 golden rows. Emoji-only and very short strings stay below the letter threshold and are unaffected (tested).
115. **A bare acknowledgement is not a thank-you.**
     - Problem: "ok", "k" and "yes" were answered "You're welcome!", which asserts gratitude the customer never expressed — the
       same class of defect as a handoff line apologising for damage nobody mentioned.
     - Decision: a new rule `canned:acknowledgement` with its own template ("Thanks for letting us know…"). "thanks", "got it" and
       "that worked" stay in the gratitude set: after a support reply they do read as appreciation, and moving them would change
       closure behaviour inside threads for no measured gain.
     - Impact: 0 golden rows.
116. **Two evaluation reports are declared volatile rather than silently re-snapshotted.**
     - Problem: `python scripts/evaluate.py --cached` — the command the README tells a reviewer to run — rewrites
       `reproduction_manifest.json` and `PHASE6_REPORT.md` with the run's wall-clock seconds, so the frozen-artifact check failed
       for a reviewer who simply followed the instructions.
     - Decision: `scripts/verification/final_verification.py` carries an `EXPECTED_CHANGED` map naming each such file *and the
       reason*, reported in every verification run. Frozen **inputs** (golden set, run records, judge results, model and gate
       artifacts) are deliberately not in it, so a change to one of those still fails. Re-taking the baseline snapshot was
       rejected: it would have hidden the difference instead of explaining it.
     - Also fixed: `per_system_means` iterated a Python `set`, so the judge-agreement JSON key order varied between runs. Sorted.
       The cached evaluation now regenerates all 11 result files byte-identically (171.6 s).
117. **Judge-human agreement reports disagreement and limitations, not just kappa.**
     - Problem: the harness produced weighted kappa and Spearman but nothing a reader could act on, and no statement of what the
       study cannot show.
     - Decision: the rated path also reports judge-minus-human bias per system (the self-preference question), the rows that
       differ by 2+ points with their golden ids, and how many hallucination/policy-violation cases the judge missed. A
       limitations section prints in **both** states: one rater, that rater is not independent, 50 stratified rows, the judge
       shares a family with two systems under test, agreement is not accuracy, and every other "hand-check" in this project is AI
       annotation.
     - Verification: the rated path was exercised end to end with a synthetic fill in a scratch directory on 2026-09-12; the
       output was deleted and the real packet is still unrated (0 of 50). No fabricated rating exists in the repository.
118. **A handoff line may only state what every condition that fires its rule guarantees.**
     - Problem: `hardware` said "We're sorry to hear about the damage", but the rule also fires on a model `physical_damage`
       flag; `repeat_contact` said "Thanks for the steps you've already tried", but the rule also fires on thread depth alone
       (>= 2 brand turns). The LLM judge flagged both as hallucinations on real golden rows (g002, g004).
     - Earlier decision (Phase 10): report it, do not reword it, because the judge score is not a target.
     - Decision now: reword them anyway, because it is a customer-facing correctness defect, not a metric. "We'd like to look at
       this with you… about repair options" and "Thanks for sticking with us on this". A test asserts no template claims the
       customer described damage or listed steps.
     - Impact: the release judge hallucination rate of 0.367 was measured on the **old** wording; the golden run was not repeated,
       so that number still describes `pipeline-v6.1` (`docs/EVALUATION.md` §4). The defect is fixed in the product and the number
       is left alone rather than being re-measured into a better one.
119. **The clean-copy check verifies against the current baseline, not the Phase-10 one.**
     - Problem: the full fresh-virtual-environment run of 2026-09-11 passed 10 of its 11 steps and failed the verification step.
       The cause was not the repository: `scripts/final/h_clean_env_check.py` runs `scripts/final/f_final_verification.py`, which
       compares against `artifacts/final/phase10_start_snapshot.json` — a baseline that predates the product-completion and
       repository passes, so their legitimate changes are reported as drift.
     - Decision: `scripts/verification/release_checks.py clean-env` now substitutes the current wrapper
       (`scripts/verification/final_verification.py`, hardening baseline, declared exceptions) into that step. The release-era
       script is left untouched so the release evidence stays reproducible.
     - Honesty note: until this pass, several documents said the full clean run "passed every step". It did not. The corrected
       account — 10 of 11, with the failing step named and explained — is now in `FINAL_REPORT.md` §1, `FINAL_ASSIGNMENT_AUDIT.md`
       D1 and `FINAL_RELEASE_CHECKLIST.md` §5.
120. **Running `scripts/security_scan.py` directly rewrites a frozen Phase-7 record; the check declares it instead of hiding it.**
     - Found while re-running the clean-copy check in this pass: the run failed its verification step, and the cause was not the
       repository or the clean copy. `python scripts/security_scan.py`, run on its own, writes
       `artifacts/phase7/security_scan.json` with the **current** committable file set (785 files here, against the baseline's
       782), and that rewritten file was then copied into the clean environment. The verification's own scan is redirected to
       `artifacts/product/hardening/security_scan.json` and never touches the Phase-7 record, so only a direct run does this.
     - Decision: name the file in `EXPECTED_CHANGED` with that reason, exactly like the evaluation reports. The scan's verdict is
       recomputed live on every verification run, so the Phase-7 file is a record of a past run, not an input to anything.
     - Why not restore it: the snapshot stores hashes, not bytes, so the original content is not recoverable — and the current
       content is a true scan of the current repository. Documenting the rewrite beats faking the old bytes.
