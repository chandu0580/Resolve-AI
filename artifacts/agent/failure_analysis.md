# Agent failure analysis (Phase 4)

Two golden runs are reported. Run 1 (`run1/`) exposed three defects; run 2 (top-level files) is the corrected agent. Both
are real outputs; run 2 was cache-served for 95% of calls, so cost and latency are quoted from run 1.

| | run 1 | run 2 (final) | what changed |
|---|---|---|---|
| AUTO_HANDLE | 17 (8.6%) | 10 (5.1%) | `other` is canned only for closures; product questions/suggestions now hand off |
| CLARIFICATION_REQUIRED | 72 (36.6%) | 72 (36.6%) | |
| HUMAN_HANDOFF | 108 (54.8%) | 115 (58.4%) | |
| troubleshooting drafts attempted / failed JSON | 8 / 5 | 8 / 3 | draft token cap 600 -> 1000 |
| auto replies with evidence refs | 1 | 3 | |
| escalation recall / precision | 0.946 / 0.324 | 0.946 / 0.304 | |
| auto reply on a should-escalate row | 0 | 0 | |

## Failure modes with real examples
| # | mode | evidence | example | root cause | status |
|---|---|---|---|---|---|
| 1 | **Canned closure sent to a product question** | run 1: g028 "When will we get the TV app in the UK?", g119 "Is the 9.7 iPad Pro no longer available?", g057 (feature request), g190 (suggestion) all answered "You're welcome!" | the `other` class is heterogeneous (closures AND questions) and policy-v2 canned the whole class | fixed: canned only when the message matches the closure pattern; every other `other` hands off with reason `insufficient_evidence` (rule `other_non_closure`). Tested. |
| 2 | **Structured-output truncation** | run 1: 5 of 8 drafts and 31 of 197 risk extractions fell back; run 2: 3 and 29 | GLM-5.2 spends hidden reasoning tokens inside the completion budget; 500/600-token caps cut the JSON mid-object | caps raised to 900 (risk) / 1000 (draft) / 800 (verify). Risk still falls back 15% of the time: the rules-only flags are used and marked `fallback`; the policy never depends on the LLM being present. Remaining lever: a smaller JSON (fewer flags per call) or a reasoning-off parameter if the proxy exposes one. |
| 3 | **Over-escalation** | 80 of 160 should-not-escalate rows handed off (precision 0.30) | 94% of messages fail the evidence gate (135 weak similarity); the evidence-first invariant converts "no proven resolution" into handoff or clarification by design | intended in this phase; the cost is a 5% autonomous rate. Levers are in retrieval (reply-side indexing, Phase 2 H1) and a richer clarification policy, not in loosening the gate. |
| 4 | **Two should-escalate rows clarified instead of handed off** | g111 "iCloud not working… Yes, I reset and logged out and in" (gold: repeat_contact) and g118 abusive OS rant (gold: vague_hostile) | g111: the repeat-contact rule needs "already/tried/reset" phrasing; "Yes, I reset and logged out" is a bare statement the regex and the LLM both missed. g118: the LLM risk call fell back and the rules' abuse pattern requires second-person insults; "shit quality control… buggy shitty" is frustration, not abuse, under the rules | two of 37; the recall cost of deterministic rules. Fix candidates: add "I reset" / "logged out and in" to the repeat-contact rule; treat high_frustration + is_actionable=False as vague_hostile when the classifier says general_complaint (already policy) — g118 was classified as performance_crash instead. |
| 5 | **Verified drafts that only ask for information** | run 2 auto replies g043, g144 ask for device/iOS version although the retrieved evidence contains the 11.1.1 workaround; g073 ("fix this" in a battery thread) asks device/version | the drafter follows "if the evidence does not cover the exact case, ask" and the evidence set mixes ask-info replies with resolutions; the verifier accepts questions | safe but low-value autonomy. Lever: prefer resolution-bearing evidence (action class update/restart/…) in the draft block and penalise ask-only drafts when a resolution is available. |
| 6 | **Verifier rejects supported drafts (false blocks)** | g005 and g090 drafts blocked by `llm_support_check` in both runs | the support-check LLM judged the paraphrased workaround as unsupported; lexical coverage was fine | conservative by design; the rejected draft is attached to the handoff packet (`draft_if_any`) for the human. |
| 7 | **Risk-LLM latency dominates** | run 1: risk p50 10.5 s, total p50 10.9 s / p95 25 s | one GLM call (plus a retry on truncation) per message | mitigated: the LLM is skipped when rules already hard-block (10 rows in run 2). Further levers: run risk only when the policy outcome can change (evidence sufficient or clarification possible), or merge risk extraction into the second-opinion call. |

## Hand-check of the 10 autonomous replies (run 2; AI annotator)
7 canned (4 non-English redirects, 3 closures): all appropriate. 3 troubleshooting replies: all safe, on-brand, grounded in a cited
historical reply, no invented steps, no promises, no PII; all three ask for device/version rather than giving the fix (mode 5).
0 of 10 would need to be recalled. This is not a quality score; that is the Phase-7 judge + human study.

## What the invariant bought
Across 394 golden executions (both runs) the agent produced 0 ungrounded customer-facing replies and 0 autonomous replies on
rows annotated as needing a human; every non-autonomous outcome carries a reason code and, for handoffs, a packet with the
retrieved evidence. The price is that 95% of traffic still goes to a human or a clarifying question.
