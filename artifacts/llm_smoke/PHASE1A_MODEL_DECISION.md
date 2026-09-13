# Phase 1A: Model Decision Report

Source: `artifacts/llm_smoke/results.md` + `results.json` + `raw/*.jsonl`, produced by `scripts/phase1/a_llm_smoke.py`
on 2026-09-10. Dev set: 30 hand-labelled KB examples (disjoint from the golden set), 4 tasks each, 120 calls per model,
temperature 0, JSON mode requested on every call. Every number below is measured; nothing is estimated except list prices.

## 1. Models tested
| # | provider | model | outcome |
|---|---|---|---|
| 1 | primary proxy (user's, `http://<private-llm-proxy-host>:4000/v1/`) | glm-5.2 | measured, 120/120 calls |
| 2 | Groq | openai/gpt-oss-120b | measured, 110/120 calls succeeded |
| 3 | Groq | openai/gpt-oss-20b | measured, 99/120 calls succeeded |
| 4 | Groq | qwen/qwen3.8-27b | measured, 119/120 calls succeeded |
| 5 | Gemini | gemini-2.5-flash | **unavailable**: 403 `Your project has been denied access` |
| 6 | Gemini | gemini-3.5-flash-lite | unavailable, same 403 |
| 7 | Gemini | gemini-3.8-flash | unavailable, same 403 |

The Gemini key answered a 1-token probe at ~11:55 and was denied by ~12:20. The key had been pasted into a tracked
template file and a chat transcript shortly before; Google flagging a leaked key is the likely cause. All three keys
should be rotated regardless of this report.

## 2. Availability / successful calls
| model | failure rate | causes |
|---|---|---|
| glm-5.2 | 0.0% | none |
| qwen3.8-27b | 0.8% | 1x 429 output-tokens-per-minute (free tier: 1,000 OTPM) |
| gpt-oss-120b | 8.3% | `json_validate_failed` (reasoning consumed the token budget before a valid JSON doc), 429 TPM (8,000) |
| gpt-oss-20b | 17.5% | `json_validate_failed`, same mechanism, worse |

## 3. Structured-output reliability (schema-valid JSON with the expected keys and value types)
| model | overall | intent | evidence | reply | escalation |
|---|---|---|---|---|---|
| qwen3.8-27b | **99.2%** | 29/30 | 30/30 | 30/30 | 30/30 |
| glm-5.2 | 95.0% | 29/30 | 28/30 | 30/30 | 27/30 |
| gpt-oss-120b | 91.7% | 30/30 | 30/30 | 21/30 | 29/30 |
| gpt-oss-20b | 82.5% | 30/30 | 28/30 | 11/30 | 30/30 |

glm-5.2's misses are JSON that parsed but lacked a required field (3 escalation decisions came back without a valid
`decision`). gpt-oss misses are empty replies: the model spent the budget on hidden reasoning.

## 4. Intent classification (30 examples, 10 intents, majority-class baseline = 20%)
| model | accuracy | errors |
|---|---|---|
| glm-5.2 | **86.7%** (26/30) | d03 I-bug rant -> general_complaint; d11 ghost touch -> hardware_damage; d20 schema miss; d23 "I hate music" -> general_complaint |
| qwen3.8-27b | 83.3% (25/30) | d01, d03 I-bug -> general_complaint; d08 schema miss; d11 -> general_complaint; d20 Snapchat -> performance_crash |
| gpt-oss-120b | 73.3% (22/30) | 8 errors, incl. Spanish tweet -> apps_services (missed non_english) |
| gpt-oss-20b | 70.0% (21/30) | 9 errors, same pattern |

Shared failure mode across all four: abusive one-liners about the "I" bug ("fix this stupid I shit") are labelled
general_complaint instead of keyboard_text_bug. The annotation guide's "keyboard wins whenever the I-bug is
mentioned" rule needs to be in the prompt, and this is an argument for the trained classifier being primary.

## 5. Evidence extraction (steps must cite an evidence number and share >= 40% of their content words with it)
| model | grounded rate | steps extracted / 30 |
|---|---|---|
| qwen3.8-27b | **100%** | 57 |
| gpt-oss-120b | 99.3% | 85 |
| glm-5.2 | 93.3% | 57 |
| gpt-oss-20b | 93.3% | 65 |

All usable. glm-5.2 occasionally paraphrases beyond the evidence; gpt-oss-120b extracts more steps, some marginal.

## 6. Reply drafting (<= 280 chars, no URL, no @handle, no forbidden promise; overlap = share of reply content words found in evidence)
| model | compliance | evidence overlap | note |
|---|---|---|---|
| glm-5.2 | **100%** | 0.454 | warm, on-brand, tends to ask a clarifying question rather than give the step |
| qwen3.8-27b | **100%** | **0.573** | sticks closest to evidence wording |
| gpt-oss-120b | 70% | 0.186 | 9 empty replies |
| gpt-oss-20b | 37% | 0.285 | 19 empty replies |

Qualitative read of glm-5.2 samples: d09 (freezing after update) asks "any app or specific ones?" instead of
offering the restart/update step present in evidence; d10 (earphones shocked the customer) asks "which earphones"
and does not acknowledge injury, although it does flag escalate. Drafting quality is acceptable; the planner must
force a `troubleshoot` strategy when evidence contains steps, and the safety gate must override the draft.

## 7. Escalation / risk reasoning (30 examples; 25 auto_handle, 5 escalate; always-auto baseline = 83.3%)
| model | accuracy | pattern |
|---|---|---|
| gpt-oss-20b | 86.7% | barely above the constant baseline |
| gpt-oss-120b | 80.0% | below baseline |
| qwen3.8-27b | 66.7% | over-escalates 10 auto cases (every I-bug and vague complaint) |
| glm-5.2 | 56.7% | over-escalates 8 auto cases + 3 schema misses; misses d07 (abusive, no symptom) |

**Every model's escalation judgement is at or below a constant "never escalate" baseline.** This is the most
important finding in the report. It validates the Phase 0 architecture: the LLM extracts risk *flags*; a
deterministic policy decides. The LLM must not make the escalation decision.

## 8. Latency (per call, live calls only)
| model | p50 | p95 | max |
|---|---|---|---|
| qwen3.8-27b | **2.5 s** | 6.6 s | 10.5 s |
| gpt-oss-120b | 4.2 s | 5.9 s | 8.0 s |
| gpt-oss-20b | 4.8 s | 6.1 s | 8.1 s |
| glm-5.2 | 5.2 s | 10.3 s | **71.4 s** |

A 4-call pipeline on glm-5.2 is ~20 s per message at p50 and can stall for over a minute.

## 9. Tokens and cost
| model | tokens in / call | tokens out / call | list price in/out per 1M | cost per 100 messages (4 calls each) |
|---|---|---|---|---|
| qwen3.8-27b | 236 | **55** | not published in harness | lowest by tokens (~5x fewer output tokens) |
| gpt-oss-20b | 320 | 307 | $0.10 / $0.50 | $0.06 |
| gpt-oss-120b | 318 | 276 | $0.15 / $0.75 | $0.09 |
| glm-5.2 | 227 | 308 | $1.00 / $3.20 (Z.ai list; proxy billing unknown) | $0.49 |

glm-5.2 and gpt-oss emit ~300 output tokens for ~50-token answers: hidden reasoning is billed. `max_tokens` must
stay >= 600 or replies come back empty (that is exactly what broke gpt-oss).

## 10. Failure cases and malformed outputs
- glm-5.2: 3 escalation responses with no valid `decision` field; 1 intent response with no valid `intent`; 2 evidence
  responses without a `steps` list; one 71 s call. No transport errors.
- gpt-oss-120b/20b: `json_validate_failed` when reasoning exhausts `max_tokens`; empty `reply` strings; Groq 429 at
  8,000 TPM. Not viable for a 3-4k-call evaluation on the free tier.
- qwen3.8-27b: one 429 at 1,000 output tokens/min; one intent value outside the allowed set.
- Gemini: 403 project denied, all calls.
- Harness bug found: cache keys used Python's per-process-salted `hash()`, so a rerun re-called the API instead of
  reading the cache. Fixed in the harness (sha256). The measured numbers are unaffected.

## 11. Recommendation: **glm-5.2** via the primary proxy
Reasons, in order of weight:
1. **Highest intent accuracy (86.7%) and 100% reply compliance** with 0% transport failures. It is the strongest
   measured model on the two tasks the LLM will actually own (understanding and drafting).
2. **Availability for the workload.** The evaluation needs 3-4k calls. The proxy has no observed rate limit;
   Groq's free tier hit 429s inside a 120-call run; Gemini is denied.
3. Its weaknesses are handled by architecture, not by a different model: escalation is deterministic (Section 7),
   latency is mitigated by fewer calls and caching (Section 13), schema misses are handled by a parse-and-retry wrapper.

This agrees with the project owner's directive to use glm-5.2; the point of this report is that the directive is
also what the numbers support, with the caveats stated.

**Comparison summary**
| | model | why |
|---|---|---|
| strongest quality | glm-5.2 | best intent, tied-best compliance, warm brand voice |
| fastest | qwen3.8-27b | p50 2.5 s, 5x fewer output tokens |
| cheapest | qwen3.8-27b by tokens; gpt-oss-20b by published price | but 17.5% failure makes gpt-oss-20b's price meaningless |
| best production trade-off | glm-5.2 given availability; qwen3.8-27b if a paid Groq tier existed | qwen is within 3 points on intent, better grounded, 2x faster, far cheaper, but rate-limited to ~18 calls/min |

## 12. Every step, or selected steps?
Selected steps only:
| agent step | use glm-5.2? | rationale |
|---|---|---|
| intent | **second opinion only**, when the embedding+LR classifier's confidence is below threshold | LLM is 87% on a task where a trained classifier should match it at ~1 ms |
| risk-flag extraction | yes | needs language understanding; flags are consumed by the deterministic policy |
| escalation decision | **no** | measured below the constant baseline; deterministic rules over flags |
| retrieval / rerank | no | embeddings + BM25 + outcome bonus |
| response planning | no | rule-based strategy choice |
| reply drafting | yes | 100% compliant, on-brand |
| output verification | yes, one call, only when evidence contains concrete steps | catches invented steps; skipped for canned/handoff strategies |
| LLM judge (eval) | yes, with disclosure | same-model self-preference bias is a stated limitation; qwen3.8-27b is viable as a second judge on 200 golden replies (~11 min at its rate limit) for a cross-model agreement check |

## 13. Architecture implications
1. **Call budget: target 2 LLM calls per message, not 4.** Merge risk-flag extraction and the intent second-opinion
   into one "understand" call; draft is the second; verifier only when needed. At p50 5.2 s that is ~10 s per message
   instead of ~20 s. Locked decision 9 requires the 2-call vs 3-call ablation; this report sets the default to 2.
2. **Timeouts and fallback.** A 71 s outlier was observed. Per-call timeout 30 s, one retry, then a deterministic
   fallback (canned handoff reply, decision = escalate, reason = `llm_unavailable`). The trace records it.
3. **JSON hardening.** 5% schema misses: parse leniently, validate with pydantic, retry once with the validation error
   in the prompt, then fallback. `max_tokens` >= 600 everywhere because of hidden reasoning tokens.
4. **Cost is dominated by reasoning tokens** (~300 out per call). Cache every call by content hash; the golden-set
   evaluation must be committed to the repo so reproduction is free.
5. **Prompting must encode the guide's boundary rules** (I-bug -> keyboard_text_bug, abusive + no symptom ->
   escalate). All four models failed these without being told.
6. **Security.** The primary endpoint is plain HTTP; the key and customer text travel unencrypted. Acceptable for a
   take-home if stated; not for production. PII redaction before any LLM call is therefore not optional.
7. **Judge independence.** With Gemini gone, the only cross-provider judge is qwen on Groq's rate-limited tier. Plan
   the human-agreement study as the primary credibility source and qwen as a secondary check, not the reverse.

## What this report does not do
It does not change any production code, touch the golden set, or start Phase 1E. Awaiting review.
