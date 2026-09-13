# Final performance and cost profile (DEV messages)

no_model      AgentConfig(use_llm=False): redaction, context, classifier, retrieval, gate, rules, policy, clarify/handoff
  cached_model  the configured model behind the SHA-256 response cache; an unmeasured warm pass fills the cache, the measured pass replays it
  live_random   NO cache, the production request budget (45 s), n_live random fresh DEV messages: the representative traffic mix
  live_draft    NO cache, 45 s budget, DEV messages selected because the no-model pass found SUFFICIENT or STRONG evidence, the only
                messages that can reach drafting. Conditional on the evidence gate and dominated by one issue, so NOT representative; it
                exists to measure draft and verification latency. If no request drafts, the report says so instead of estimating.
Before every measured pass the embedding memo and the query-vector cache are cleared (the Phase 9 profiler artifact).
Per mode: total and per-stage p50 / p95, p99 only when n >= 100 (otherwise the maximum is shown), model calls, live calls, cache hits,
input and output tokens, estimated cost at the list price the orchestrator uses, and how many requests drafted and verified with the model
(a canned template marks verification "ok" with 0 ms, so a model-verified request is one whose verification stage took time).

| mode | n | total p50 ms | p95 ms | p99 ms (n ≥ 100) | model calls / request (mean) | live calls | cache hit rate | tokens in / out per request (mean) | est. cost / request (mean USD) | drafted + model-verified |
|---|---|---|---|---|---|---|---|---|---|---|
| no_model | 100 | 172.6 | 374.0 | 456.9 | 0.0 | 0 | None | 0.0 / 0.0 | 0.0 | 0 |
| cached_model | 100 | 256.3 | 635.1 | 1127.1 | 1.66 | 0 | 1.0 | 725.4 / 617.7 | 0.002702 | 1 |
| live_random | 40 | 4166.9 | 14210.6 | max 19498.1 | 1.675 | 67 | 0.0 | 738.0 / 698.1 | 0.002972 | 0 |
| live_draft | 20 | 6277.1 | 18224.0 | max 32619.5 | 2.4 | 48 | 0.0 | 935.2 / 1091.0 | 0.004426 | 8 |

## Stage latency p50 / p95 ms

| stage | no_model | cached_model | live_random | live_draft |
|---|---|---|---|---|
| pii_redaction | 0.1 / 0.4 | 0.1 / 0.4 | 0.1 / 0.4 | 0.1 / 0.4 |
| context | 0.2 / 0.6 | 0.2 / 0.7 | 0.1 / 0.5 | 0.1 / 0.5 |
| intent | 84.2 / 189.4 | 109.8 / 281.7 | 77.0 / 111.2 | 106.2 / 238.3 |
| second_opinion | 0.0 / 0.0 | 14.1 / 37.5 | 1279.5 / 6421.0 | 0.0 / 2938.7 |
| retrieval | 97.4 / 198.5 | 124.1 / 246.6 | 74.7 / 231.3 | 106.0 / 274.1 |
| evidence_gate | 0.0 / 0.0 | 0.0 / 0.0 | 0.0 / 0.0 | 0.0 / 0.0 |
| risk | 0.9 / 2.2 | 14.5 / 30.9 | 2413.2 / 12167.4 | 2574.9 / 5871.2 |
| policy | 0.0 / 0.1 | 0.0 / 0.1 | 0.0 / 0.1 | 0.0 / 0.0 |
| draft | 0.0 / 0.0 | 0.0 / 0.0 | 0.0 / 0.0 | 0.0 / 11509.2 |
| verification | 0.0 / 0.0 | 0.0 / 0.0 | 0.0 / 0.0 | 0.0 / 3830.8 |
| output_gate | 0.0 / 0.1 | 0.0 / 0.1 | 0.0 / 0.0 | 0.1 / 0.2 |
| handoff | 0.2 / 0.3 | 0.2 / 0.5 | 0.2 / 0.2 | 0.2 / 0.2 |
| total | 172.6 / 374.0 | 256.3 / 635.1 | 4166.9 / 14210.6 | 6277.1 / 18224.0 |

## Live drafting and verification

Requests that drafted and were verified with the live model: 8 of 20 (selection: {'scanned': 1357, 'selected': 20, 'rule': 'no-model evidence level SUFFICIENT or STRONG'}).
- draft stage p50 / p95: 2992.3 / 9204.1 ms
- verification stage p50 / p95: 1842.0 / 6644.8 ms
- total for those requests p50 / p95: 10669.0 / 26099.7 ms
- small sample (n = 8): an engineering estimate, not a service level

Outcomes: no_model {'CLARIFICATION_REQUIRED': 62, 'HUMAN_HANDOFF': 35, 'AUTO_HANDLE': 3}; cached_model {'HUMAN_HANDOFF': 63, 'CLARIFICATION_REQUIRED': 34, 'AUTO_HANDLE': 3}; live_random {'HUMAN_HANDOFF': 21, 'CLARIFICATION_REQUIRED': 19}; live_draft {'AUTO_HANDLE': 8, 'CLARIFICATION_REQUIRED': 4, 'HUMAN_HANDOFF': 8}
Timeouts / retries / budget refusals: no_model 0/0/0; cached_model 0/0/0; live_random 0/0/0; live_draft 0/0/0

## Measurement conditions (added after the run)

- **Shared machine.** During this profile, processes from another project were running on the same machine: a pytest run, an API
  server and a test harness. CPU-bound stages are therefore slower than in the quiet Phase 9 profile, where the no-model total p50
  was 110 ms (`artifacts/phase9/performance/perf_report.md`).
- **Model stages.** Their latency is dominated by the remote model proxy.
- **Samples.** All live messages are dev messages. `live_draft` is selected by evidence level and is not representative traffic.
