# Phase 9 performance profile (DEV messages)

(the same ResolveAI orchestrator the API uses; traces off so disk writes are not measured):
  no_model      AgentConfig(use_llm=False): redaction, context, classifier, retrieval, gate, rules, policy, clarify/handoff
  cached_model  the configured model behind the SHA-256 response cache; one unmeasured warm pass fills the cache, the
                measured pass is served from it (what a cache-served evaluation run measures)
  live_model    the configured model with NO cache and the API's request budget (45 s), n_live fresh messages
Per mode: p50 / p95 / p99 of every stage and of the total, model calls, embedding computations per request.

## no_model (n=60)

| stage | p50 ms | p95 ms | p99 ms |
|---|---|---|---|
| pii_redaction | 0.1 | 0.3 | 0.4 |
| context | 0.1 | 0.4 | 0.6 |
| intent | 49.3 | 92.4 | 133.1 |
| second_opinion | 0.0 | 0.0 | 0.0 |
| retrieval | 63.5 | 96.0 | 120.2 |
| evidence_gate | 0.0 | 0.0 | 0.0 |
| risk | 0.6 | 1.8 | 2.0 |
| policy | 0.0 | 0.0 | 0.1 |
| draft | 0.0 | 0.1 | 0.1 |
| verification | 0.0 | 0.0 | 0.0 |
| output_gate | 0.0 | 0.1 | 0.1 |
| handoff | 0.1 | 0.2 | 0.3 |
| total | 110.1 | 191.2 | 255.1 |

Model calls per request p50/p95: 0.0/0.0; live calls p50/p95: 0.0/0.0; embedding computations per request p50/p95: 2.0/2.0; timeouts 0, retries 0, budget refusals 0; risk stage {'skipped': 60}; actions {'AUTO_HANDLE': 4, 'CLARIFICATION_REQUIRED': 33, 'HUMAN_HANDOFF': 23}

## cached_model (n=60)

| stage | p50 ms | p95 ms | p99 ms |
|---|---|---|---|
| pii_redaction | 0.1 | 0.3 | 0.4 |
| context | 0.1 | 0.5 | 0.6 |
| intent | 55.1 | 106.9 | 128.4 |
| second_opinion | 1.6 | 3.6 | 4.5 |
| retrieval | 61.3 | 143.6 | 157.3 |
| evidence_gate | 0.0 | 0.0 | 0.0 |
| risk | 2.0 | 5.7 | 7.8 |
| policy | 0.0 | 0.0 | 0.1 |
| draft | 0.0 | 0.0 | 0.0 |
| verification | 0.0 | 0.0 | 0.0 |
| output_gate | 0.0 | 0.1 | 0.1 |
| handoff | 0.2 | 0.3 | 0.5 |
| total | 125.7 | 239.6 | 273.5 |

Model calls per request p50/p95: 2.0/3.0; live calls p50/p95: 0.0/0.0; embedding computations per request p50/p95: 2.0/2.0; timeouts 0, retries 0, budget refusals 0; risk stage {'ok': 43, 'skipped': 17}; actions {'HUMAN_HANDOFF': 39, 'CLARIFICATION_REQUIRED': 20, 'AUTO_HANDLE': 1}

## live_model (n=20)

| stage | p50 ms | p95 ms | p99 ms |
|---|---|---|---|
| pii_redaction | 0.1 | 0.4 | 0.5 |
| context | 0.2 | 0.7 | 0.9 |
| intent | 75.6 | 141.5 | 286.0 |
| second_opinion | 1911.4 | 5986.6 | 6766.7 |
| retrieval | 81.6 | 308.0 | 342.2 |
| evidence_gate | 0.0 | 0.0 | 0.0 |
| risk | 535.7 | 5184.7 | 12926.0 |
| policy | 0.0 | 0.1 | 0.2 |
| draft | 0.0 | 0.0 | 0.0 |
| verification | 0.0 | 0.0 | 0.0 |
| output_gate | 0.0 | 0.1 | 0.1 |
| handoff | 0.2 | 0.3 | 0.3 |
| total | 3602.5 | 8102.0 | 14452.6 |

Model calls per request p50/p95: 1.0/3.0; live calls p50/p95: 1.0/3.0; embedding computations per request p50/p95: 2.0/2.0; timeouts 0, retries 0, budget refusals 0; risk stage {'ok': 10, 'skipped': 10}; actions {'HUMAN_HANDOFF': 13, 'CLARIFICATION_REQUIRED': 7}
