"""Engineering CLI.  python -m resolveai.agent "my battery drains fast since the update" [--history history.json] [--json] [--no-llm]

history.json: [{"role": "customer", "text": "..."}, {"role": "brand", "text": "..."}]  (oldest first)
--json prints the full AgentResult; otherwise a readable summary. Traces are written to traces/<date>.jsonl.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from resolveai.agent import AgentConfig, ResolveAI
from resolveai.schemas import ConversationContext, ConversationTurn


def render(r) -> str:
    L = [f"TRACE ID      {r.trace_id}", f"REQUEST ID    {r.request_id}", f"ACTION        {r.action}", f"INTENT        {r.intent.intent}  (band {r.intent.confidence_band}, alternatives {[t[0] for t in r.intent.top3[1:]]}"
         + (f", second opinion {r.intent.second_opinion}{' applied' if r.intent.second_opinion_applied else ''}" if r.intent.second_opinion else "") + ")",
         f"CONFIDENCE    {r.intent.confidence:.3f}  calibrated={r.intent.calibrated}  multi_intent={r.intent.multi_intent}  insufficient_context={r.intent.insufficient_context}",
         f"EVIDENCE      {len(r.evidence.items)} retrieved, level={r.evidence.sufficiency_level} ({r.evidence.sufficiency_reason}), resolution_confidence={r.evidence.resolution_confidence:.2f}, consistency={r.evidence.consistency}"]
    for it in r.evidence.items[:3]:
        L.append(f"   [{it.evidence_id}] {it.retrieval_source:8s} cos={it.quality.semantic_relevance:.2f} {it.quality.action_class:9s} {'substantive' if it.substantive else 'handoff   '} | {it.brand_reply[:90]}")
    for c in r.evidence.resolution_candidates[:3]:
        L.append(f"   RESOLUTION {c.action_class:9s} support={c.support_count} share={c.share:.2f} ids={c.evidence_ids[:3]} | {c.representative_reply[:80]}")
    raised = [k for k, v in r.risk.model_dump().items() if v is True and k != "is_actionable"]
    L += [f"RISK FLAGS    {raised or 'none'}  (source {r.risk.source})",
          f"DECISION      {r.decision.escalation.decision}  reason={r.decision.escalation.reason_code}  rule={r.decision.escalation.rule}  policy={r.policy_version}",
          f"              gate blocking: {r.decision.blocking or 'none'}",
          f"RESPONSE      {r.response}",
          f"VERIFICATION  {'n/a' if r.verification is None else f'verified={r.verification.verified} severity={r.verification.severity} coverage={r.verification.coverage} method={r.verification.method} issues={[i.check for i in r.verification.issues]}'}",
          f"EVIDENCE REFS {r.evidence_refs}",
          f"LATENCY ms    {r.latency}",
          f"USAGE         calls={r.usage.llm_calls} cache_hits={r.usage.cache_hits} tokens={r.usage.tokens_in}/{r.usage.tokens_out} est_cost=${r.usage.estimated_cost_usd:.5f}"]
    if r.handoff:
        L += ["HANDOFF       next action: " + r.handoff.recommended_next_action, "              unresolved: " + "; ".join(r.handoff.unresolved_questions)]
    if r.clarification:
        L += ["CLARIFY       missing: " + "; ".join(r.clarification.missing_information), "              already provided: " + (", ".join(r.clarification.already_provided) or "none")]
    if r.citations:
        L += ["CITATIONS     " + "; ".join(f"{c.evidence_id} (thread {c.thread_id}, {c.created_at[:10]}, rank {c.rank}, similarity {c.similarity:.2f})" for c in r.citations)]
    if r.summary:
        L += ["WHAT          " + r.summary.what_happened, "WHY           " + r.summary.why, "NEXT          " + r.summary.next_step]
    if r.versions:
        L += [f"VERSIONS      pipeline={r.versions.pipeline} policy={r.versions.policy} evidence_gate={r.versions.evidence_gate} model={r.versions.model} config_hash={r.versions.config_hash}"]
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m resolveai.agent")
    ap.add_argument("message", nargs="?", help="customer message (or use --input)")
    ap.add_argument("--history", help="JSON file with prior turns [{role, text}]")
    ap.add_argument("--input", help="JSON file {message, history?, customer_author?, created_at?}")
    ap.add_argument("--json", action="store_true", help="print the full AgentResult as JSON")
    ap.add_argument("--no-llm", action="store_true", help="run without any LLM (deterministic fallbacks)")
    ap.add_argument("--no-traces", action="store_true")
    a = ap.parse_args(argv)
    payload = json.loads(Path(a.input).read_text(encoding="utf-8")) if a.input else {}
    message = a.message or payload.get("message")
    if not message:
        ap.error("a message is required")
    hist = payload.get("history") or (json.loads(Path(a.history).read_text(encoding="utf-8")) if a.history else [])
    ctx = ConversationContext(turns=[ConversationTurn(role=t["role"], text=t["text"]) for t in hist])
    agent = ResolveAI(cfg=AgentConfig(use_llm=not a.no_llm, write_traces=not a.no_traces))
    r = agent.resolve(message, ctx, customer_author=payload.get("customer_author"), created_at=payload.get("created_at"))
    print(r.model_dump_json(indent=1) if a.json else render(r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
