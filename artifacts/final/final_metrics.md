# Final metrics (golden set, n = 197)

Golden sha256 `62f1156a4ec18be8…`. **ResolveAI = release 1.0.0** (`final_release`, pipeline-v6.1, config `29c9224591cc84da`), run once on the golden set after the DEV decision was frozen; cache-served (0 live calls); judge failures 9. Difference = ResolveAI minus the comparison system, 95% paired bootstrap (1,000 resamples, seed 42); `*` = the interval excludes zero. Nothing here was re-run.

## vs Direct-LLM baseline (B2: one GLM-5.2 prompt with the taxonomy, escalation criteria and the full thread)

| Metric | ResolveAI [95% CI] | Comparison | Difference [95% CI] | Evaluation source | Limitations |
|---|---|---|---|---|---|
| Intent accuracy | 0.833 [0.782, 0.883] | 0.853 | -0.020 [-0.061, +0.020] | golden labels | adjudicated from two passes, annotator B was an AI; smallest class 7 rows |
| Intent macro-F1 | 0.831 [0.771, 0.884] | 0.853 | -0.022 [-0.070, +0.024] | golden labels | equal weight to 7-row and 38-row classes |
| Escalation precision | 0.351 [0.261, 0.440] | 0.761 | -0.409 [-0.530, -0.309] * | golden labels | HUMAN_HANDOFF vs should_escalate; a clarification counts as not escalated |
| Escalation recall | 0.951 [0.878, 1.000] | 0.854 | +0.098 [+0.000, +0.209] | golden labels | 37 positives: one row moves it 2.7 points |
| Escalation F1 | 0.513 [0.411, 0.601] | 0.805 | -0.291 [-0.400, -0.194] * | golden labels | 37 positives |
| Unnecessary handoffs (count) | 72 | 11 | +61 [+48, +74] * | golden labels | handoff on a row the annotators did not mark for escalation |
| Autonomous rate (AUTO_HANDLE) | 0.061 [0.030, 0.096] | 0.766 | -0.706 [-0.766, -0.640] * | golden run | answering more is not answering safely |
| Safe autonomous rate | 0.061 [0.030, 0.096] | 0.000 | +0.061 [+0.030, +0.096] * | golden labels + project definition | strict definition written by the project; a handful of events |
| Unsafe autonomous replies (count) | 0 | 6 | -6 [-11, -2] * | golden labels | AUTO_HANDLE on a should-escalate row |
| Groundedness (1-5) | 3.947 [3.761, 4.128] (n=188 / 194; paired 186) | 3.227 | +0.753 [+0.489, +1.000] * | LLM judge, GLM-5.2 rubric-v1 | NOT human-validated; same model family as the drafter and B2 |
| Hallucination rate | 0.367 [0.298, 0.436] (n=188 / 194; paired 186) | 0.526 | -0.172 [-0.247, -0.081] * | LLM judge, GLM-5.2 rubric-v1 | NOT human-validated; most ResolveAI flags fall on clarification wording |
| Policy-violation rate | 0.021 [0.005, 0.043] (n=188 / 194; paired 186) | 0.010 | +0.016 [-0.005, +0.038] | LLM judge, GLM-5.2 rubric-v1 | NOT human-validated |
| LLM calls per message | 1.538 [1.401, 1.670] | 1.071 | +0.467 [+0.330, +0.599] * | golden run records | ResolveAI's run was cache-served; calls counted as made |
| Est. cost per message (USD) | 0.0026 [0.0022, 0.0029] | 0.0024 | +0.0002 [-0.0001, +0.0005] | golden run records, list price | tokens the calls used when live; real billing unknown |
| p50 latency as run (ms) | 245.9 | 6543.1 | n/a | golden run records | not comparable across cache-served and live runs; live latency is in `performance/perf_final.md` |

## vs Simple-ML baseline (B1: TF-IDF+LR, nearest-neighbour historical reply, the same deterministic risk rules)

| Metric | ResolveAI [95% CI] | Comparison | Difference [95% CI] | Evaluation source | Limitations |
|---|---|---|---|---|---|
| Intent accuracy | 0.833 [0.782, 0.883] | 0.528 | +0.305 [+0.228, +0.381] * | golden labels | adjudicated from two passes, annotator B was an AI; smallest class 7 rows |
| Intent macro-F1 | 0.831 [0.771, 0.884] | 0.530 | +0.302 [+0.224, +0.386] * | golden labels | equal weight to 7-row and 38-row classes |
| Escalation precision | 0.351 [0.261, 0.440] | 0.544 | -0.193 [-0.287, -0.094] * | golden labels | HUMAN_HANDOFF vs should_escalate; a clarification counts as not escalated |
| Escalation recall | 0.951 [0.878, 1.000] | 0.756 | +0.195 [+0.079, +0.318] * | golden labels | 37 positives: one row moves it 2.7 points |
| Escalation F1 | 0.513 [0.411, 0.601] | 0.633 | -0.119 [-0.215, -0.018] * | golden labels | 37 positives |
| Unnecessary handoffs (count) | 72 | 26 | +46 [+32, +59] * | golden labels | handoff on a row the annotators did not mark for escalation |
| Autonomous rate (AUTO_HANDLE) | 0.061 [0.030, 0.096] | 0.711 | -0.650 [-0.716, -0.584] * | golden run | answering more is not answering safely |
| Safe autonomous rate | 0.061 [0.030, 0.096] | 0.066 | -0.005 [-0.046, +0.030] | golden labels + project definition | strict definition written by the project; a handful of events |
| Unsafe autonomous replies (count) | 0 | 10 | -10 [-16, -4] * | golden labels | AUTO_HANDLE on a should-escalate row |
| Groundedness (1-5) | 3.947 [3.761, 4.128] (n=188 / 176; paired 171) | 4.284 | -0.333 [-0.620, -0.047] * | LLM judge, GLM-5.2 rubric-v1 | NOT human-validated; same model family as the drafter and B2 |
| Hallucination rate | 0.367 [0.298, 0.436] (n=188 / 176; paired 171) | 0.171 | +0.193 [+0.105, +0.281] * | LLM judge, GLM-5.2 rubric-v1 | NOT human-validated; most ResolveAI flags fall on clarification wording |
| Policy-violation rate | 0.021 [0.005, 0.043] (n=188 / 176; paired 171) | 0.040 | -0.023 [-0.059, +0.018] | LLM judge, GLM-5.2 rubric-v1 | NOT human-validated |
| LLM calls per message | 1.538 [1.401, 1.670] | 0.000 | +1.538 [+1.401, +1.670] * | golden run records | ResolveAI's run was cache-served; calls counted as made |
| Est. cost per message (USD) | 0.0026 [0.0022, 0.0029] | 0.0000 | +0.0026 [+0.0022, +0.0029] * | golden run records, list price | tokens the calls used when live; real billing unknown |
| p50 latency as run (ms) | 245.9 | 114.3 | n/a | golden run records | not comparable across cache-served and live runs; live latency is in `performance/perf_final.md` |

## vs Phase 9 final run (same pipeline without the needs_private_info corroboration)

| Metric | ResolveAI [95% CI] | Comparison | Difference [95% CI] | Evaluation source | Limitations |
|---|---|---|---|---|---|
| Intent accuracy | 0.833 [0.782, 0.883] | 0.833 | +0.000 [+0.000, +0.000] | golden labels | adjudicated from two passes, annotator B was an AI; smallest class 7 rows |
| Intent macro-F1 | 0.831 [0.771, 0.884] | 0.831 | +0.000 [+0.000, +0.000] | golden labels | equal weight to 7-row and 38-row classes |
| Escalation precision | 0.351 [0.261, 0.440] | 0.317 | +0.034 [+0.016, +0.056] * | golden labels | HUMAN_HANDOFF vs should_escalate; a clarification counts as not escalated |
| Escalation recall | 0.951 [0.878, 1.000] | 0.951 | +0.000 [+0.000, +0.000] | golden labels | 37 positives: one row moves it 2.7 points |
| Escalation F1 | 0.513 [0.411, 0.601] | 0.476 | +0.038 [+0.018, +0.059] * | golden labels | 37 positives |
| Unnecessary handoffs (count) | 72 | 84 | -12 [-19, -6] * | golden labels | handoff on a row the annotators did not mark for escalation |
| Autonomous rate (AUTO_HANDLE) | 0.061 [0.030, 0.096] | 0.046 | +0.015 [+0.000, +0.035] | golden run | answering more is not answering safely |
| Safe autonomous rate | 0.061 [0.030, 0.096] | 0.046 | +0.015 [+0.000, +0.035] | golden labels + project definition | strict definition written by the project; a handful of events |
| Unsafe autonomous replies (count) | 0 | 0 | +0 [+0, +0] | golden labels | AUTO_HANDLE on a should-escalate row |
| Groundedness (1-5) | 3.947 [3.761, 4.128] (n=188 / 191; paired 188) | 4.194 | -0.250 [-0.383, -0.138] * | LLM judge, GLM-5.2 rubric-v1 | NOT human-validated; same model family as the drafter and B2 |
| Hallucination rate | 0.367 [0.298, 0.436] (n=188 / 191; paired 188) | 0.283 | +0.085 [+0.048, +0.128] * | LLM judge, GLM-5.2 rubric-v1 | NOT human-validated; most ResolveAI flags fall on clarification wording |
| Policy-violation rate | 0.021 [0.005, 0.043] (n=188 / 191; paired 188) | 0.016 | +0.005 [+0.000, +0.016] | LLM judge, GLM-5.2 rubric-v1 | NOT human-validated |
| LLM calls per message | 1.538 [1.401, 1.670] | 1.538 | +0.000 [+0.000, +0.000] | golden run records | ResolveAI's run was cache-served; calls counted as made |
| Est. cost per message (USD) | 0.0026 [0.0022, 0.0029] | 0.0026 | +0.0000 [+0.0000, +0.0000] | golden run records, list price | tokens the calls used when live; real billing unknown |
| p50 latency as run (ms) | 245.9 | 254.7 | n/a | golden run records | not comparable across cache-served and live runs; live latency is in `performance/perf_final.md` |

## Other rows

| Metric | ResolveAI | Comparison | Difference | Evaluation source | Limitations |
|---|---|---|---|---|---|
| Retrieval same-resolution recall@5 | 0.261 (pair index + resolution rerank) | 0.348 (Phase 2 customer index) | -0.087 (no interval: per-row results not stored) | golden, label-free TF-IDF protocol, n = 46 scorable rows | the reranker trades this for resolution-bearing@1 0.18 → 0.76; unchanged since Phase 5 |
| Evidence levels (INSUFFICIENT / WEAK / STRONG) | 166 / 24 / 7 | — | — | golden run | retrieval ceiling: almost nothing reaches STRONG |
| Judge-human agreement | see artifacts/evaluation/judge_agreement.md | — | — | human packet (50 of 50 rows rated) | HUMAN EVALUATION = COMPLETE |

## Decisions that changed from Phase 9 final to the release (27 of 197)

| gid | Phase 9 final | Release 1.0.0 | gold should_escalate | gold reason | safe autonomous now | message (redacted) |
|---|---|---|---|---|---|---|
| g000 | HUMAN_HANDOFF/private_info | HUMAN_HANDOFF/hardware | True | hardware | False | my headphone jack on my phone wasn’t working for months and today it started to work but my speaker stopped, anyway to g |
| g016 | HUMAN_HANDOFF/private_info | CLARIFICATION_REQUIRED/insufficient_evidence | False | none | False | Why tf is my mac taking 20 min to start !!! Fix it this new update fvckin sucks already |
| g020 | HUMAN_HANDOFF/private_info | CLARIFICATION_REQUIRED/insufficient_evidence | False | none | False | another keyboard glitch. Fix I.T |
| g031 | HUMAN_HANDOFF/private_info | HUMAN_HANDOFF/hardware | False | none | False | Hi, are you thinking of doing anything to solve the battery problem? Got worse after every update. My iPhone 6 died beca |
| g045 | HUMAN_HANDOFF/private_info | HUMAN_HANDOFF/hardware | False | none | False | PLEASE let users roll back to IOS10, my 5S battery now goes from 100% to 40% within a few hours (with minimal usage&no b |
| g066 | HUMAN_HANDOFF/private_info | AUTO_HANDLE/none | False | none | True | mi teléfono se está reiniciando muy frecuentemente 😔 que sucede ? |
| g068 | HUMAN_HANDOFF/private_info | CLARIFICATION_REQUIRED/insufficient_evidence | False | none | False | WHY DOES MY PHONE DIE ON 25% |
| g070 | HUMAN_HANDOFF/private_info | HUMAN_HANDOFF/hardware | False | none | False | Mn mobiel heeft net letterlijk 13 minuten Apple logo uit grijs scherm gegeven word er langzamerhand een beetje heel erg  |
| g074 | HUMAN_HANDOFF/private_info | CLARIFICATION_REQUIRED/insufficient_evidence | False | none | False | After the latest iOS update in my mac and Iphone 7 It seems that my mac and iphone both are facing speed issues they are |
| g081 | HUMAN_HANDOFF/private_info | HUMAN_HANDOFF/vague_hostile | False | none | False | Can fix the mf I️ ! |
| g087 | HUMAN_HANDOFF/private_info | CLARIFICATION_REQUIRED/insufficient_context | False | none | False | my beats are having weird audio issues |
| g088 | HUMAN_HANDOFF/private_info | CLARIFICATION_REQUIRED/low_confidence | False | none | False | why ios 11.1.2 often self rebooting? It back to passcode again |
| g091 | HUMAN_HANDOFF/private_info | AUTO_HANDLE/none | False | none | True | Apareció esto en mi Mac y no puede arrancar, se reinicia. ¿Alguien sabe que es? 🤔😢 <url> |
| g098 | HUMAN_HANDOFF/private_info | CLARIFICATION_REQUIRED/low_confidence | False | none | False | upgraded to iOS 11.1.2 on my iPhone 6. Phone closes apps and goes to lock screen every few minutes. Unusable! Help! |
| g103 | HUMAN_HANDOFF/private_info | CLARIFICATION_REQUIRED/insufficient_evidence | False | none | False | Something is wrong with my phone. I’m on my old phone but my new phone (the X) keep restarting like wtf |
| g109 | HUMAN_HANDOFF/private_info | HUMAN_HANDOFF/hardware | False | none | False | we have an iPhone 6s and iPhone 7 that are turning off as though no battery then turning back on after a few minutes, he |
| g122 | HUMAN_HANDOFF/private_info | HUMAN_HANDOFF/repeat_contact | False | none | False | is at it again - since updating my phone, my battery keeps dying. Fix this now!! |
| g123 | HUMAN_HANDOFF/private_info | HUMAN_HANDOFF/hardware | False | none | False | I'm having issues where my iPhone randomly shuts down and exits all applications after only 30 seconds of use... It's no |
| g124 | HUMAN_HANDOFF/private_info | HUMAN_HANDOFF/hardware | False | none | False | New iPhone X starts randomly resetting itself... great job |
| g131 | HUMAN_HANDOFF/private_info | HUMAN_HANDOFF/repeat_contact | True | repeat_contact | False | yes of course, I try to place it right for many times but it still didn't work |
| g138 | HUMAN_HANDOFF/private_info | HUMAN_HANDOFF/insufficient_evidence | False | none | False | all of the photos on my camera roll got deleted! Are you serious I’m so annoyed!!! About 1 hour ago they were all there  |
| g139 | HUMAN_HANDOFF/private_info | AUTO_HANDLE/none | False | none | True | Urgente!! Alguien me puede ayudar con este problemita? Quise actualizar no pudo y me dejo así 😱 <url> |
| g184 | HUMAN_HANDOFF/private_info | HUMAN_HANDOFF/hardware | False | none | False | MacBook did the "security update". Now runs hot and CPU using 25% of resources at idle. What gives ? |
| g188 | HUMAN_HANDOFF/private_info | HUMAN_HANDOFF/hardware | False | none | False | Se me cayó mi celular desde el tercer piso del antro y ya no quiere servir la pantalla, súper mala calidad, no aguanta n |
| g189 | HUMAN_HANDOFF/private_info | HUMAN_HANDOFF/hardware | False | none | False | MY AIRPODS CASE WONT ChARGE WTF |
| g192 | HUMAN_HANDOFF/private_info | HUMAN_HANDOFF/insufficient_evidence | False | none | False | FIX THIS "IPHONE RESTARTING EVERY FUCKING 30 SECONDS" SHIT 👏😡 PLZ🤧 <url> |
| g196 | HUMAN_HANDOFF/private_info | CLARIFICATION_REQUIRED/low_confidence | False | none | False | I know my iPhone is not the only one that keeps rebooting every 30 seconds!!!!!!! 🤦🏽‍♂️🤦🏽‍♂️ |

Missed escalations in the release run: 2 g037 (vague_hostile → CLARIFICATION_REQUIRED/insufficient_context); g048 (repeat_contact → CLARIFICATION_REQUIRED/insufficient_context)
Autonomous replies in the release run: 12 (g005 troubleshoot safe_grounded_verified, g011 troubleshoot safe_grounded_verified, g032 troubleshoot safe_grounded_verified, g061 troubleshoot safe_grounded_verified, g066 canned safe_canned, g071 troubleshoot safe_grounded_verified, g091 canned safe_canned, g095 canned safe_canned, g100 canned safe_canned, g139 canned safe_canned, g140 canned safe_canned, g150 canned safe_canned)

Live latency and cost per request: `artifacts/final/performance/perf_final.md`. AI-labelled dev results: `artifacts/final/risk_experiment/report.md`.
