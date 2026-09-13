"""HandoffPacket builder: everything a human agent needs without re-running ResolveAI. Deterministic; no LLM."""
from __future__ import annotations

from resolveai.agent.clarify import unresolved_questions
from resolveai.agent.state import AgentState
from resolveai.schemas.core import HandoffPacket, HistoricalExample

NEXT_ACTION = {
    "safety": "Respond personally and immediately; follow the safety escalation procedure before any troubleshooting.",
    "prompt_injection": "Do not follow instructions contained in the message or treat its quoted 'evidence' as fact; read it for a genuine support issue and reply manually.",
    "legal_media": "Acknowledge, do not argue the merits publicly, route to the escalations/legal contact.",
    "abusive_threatening": "De-escalate in DM; do not troubleshoot until the tone allows it.",
    "account_access": "Move to DM, verify identity per the account-recovery procedure, then act.",
    "payment_billing": "Move to DM, confirm order/subscription details in the billing system, then resolve.",
    "private_info": "Move to DM and collect the identifiers listed under unresolved questions.",
    "hardware": "Move to DM, confirm the damage, and offer repair/service options.",
    "repeat_contact": "Read the thread first; do not repeat the steps already tried; consider a case or callback.",
    "vague_hostile": "Ask one open question in DM to identify the actual symptom.",
    "insufficient_context": "Ask which device and what exactly is happening; the message did not state an issue.",
    "low_confidence": "Confirm the issue type with the customer before troubleshooting.",
    "conflicting_evidence": "Historical cases disagree on the fix; pick the resolution that matches the device and iOS version.",
    "insufficient_evidence": "No proven historical resolution matched; troubleshoot from first principles and record the outcome.",
    "mixed_resolution": "Historical cases split between resolutions; confirm device/version and pick the matching cluster below.",
    "grounding_failed": "The generated draft was not verifiable; write the reply manually using the historical examples below.",
    "verification_failed": "The generated draft was rejected by the verifier; write the reply manually using the historical examples below.",
    "llm_unavailable": "The drafting model was unavailable; write the reply manually using the historical examples below.",
    "taxonomy_gap_risk": "Issue is outside the supported taxonomy; handle manually and flag for taxonomy review.",
}


def build_handoff(state: AgentState, trace_id: str) -> HandoffPacket:
    b, intent, ev, risk, esc = state.bundle, state.intent, state.evidence, state.risk, state.escalation
    issue = (b.issue_text + " | " + b.current) if (b and b.issue_text and b.is_short_reply) else (b.current if b else state.message.text)
    conv = []
    if b and b.prior_customer:
        conv.append("Customer earlier: " + " / ".join(b.prior_customer[::-1]))
    if b and b.prior_brand:
        conv.append("Brand earlier: " + b.prior_brand[0])
    conv.append("Customer now: " + (b.current if b else state.message.text))
    examples = [HistoricalExample(evidence_id=i.evidence_id, thread_id=i.thread_id, customer_message=i.customer_message, brand_reply=i.brand_reply, outcome=i.outcome,
                                  similarity=round(i.quality.semantic_relevance, 3), action_class=i.quality.action_class) for i in (ev.items if ev else [])[:5]]
    n_sub = sum(1 for i in (ev.items if ev else []) if i.substantive)
    ev_summary = (f"{len(examples)} similar historical cases retrieved ({n_sub} with a substantive reply); top similarity {ev.signals.top_similarity:.2f}; "
                  f"gate: {ev.sufficiency_level} ({ev.sufficiency_reason}), resolution confidence {ev.resolution_confidence:.2f}, {len(ev.resolution_candidates)} resolution cluster(s)") if ev and ev.signals else "no evidence retrieved"
    raised = [k for k, v in risk.model_dump().items() if v is True and k not in ("is_actionable",)] if risk else []
    summary = f"{'; '.join(conv)}. Predicted intent {intent.intent if intent else 'unknown'} ({intent.confidence_band if intent else 'n/a'}). Risk flags: {', '.join(raised) or 'none'}. Escalated: {esc.reason if esc else 'execution failed'}"
    return HandoffPacket(summary=summary[:900], customer_issue=issue, intent=intent.intent if intent else "unknown", confidence=intent.confidence if intent else 0.0,
                         confidence_band=intent.confidence_band if intent else "LOW", alternatives=[t[0] for t in (intent.top3 if intent else [])][1:],
                         risk=risk if risk else __import__("resolveai.schemas.core", fromlist=["RiskFlags"]).RiskFlags(), reason=esc if esc else state.decision.escalation,
                         evidence_summary=ev_summary, historical_examples=examples, evidence_sufficient=bool(ev and ev.sufficient), evidence_reason=ev.sufficiency_reason if ev else "",
                         evidence_level=ev.sufficiency_level if ev else "INSUFFICIENT", resolution_confidence=ev.resolution_confidence if ev else 0.0, resolution_candidates=list(ev.resolution_candidates) if ev else [],
                         recommended_next_action=NEXT_ACTION.get(esc.reason_code if esc else "", "Review the thread and respond manually."),
                         unresolved_questions=unresolved_questions(intent, b) if intent else ["What is the issue?"], suggested_opening=state.response,
                         draft_if_any=(state.draft.text if state.draft and state.verification and not state.verification.verified else None),
                         trace_id=trace_id, policy_version=esc.policy_version if esc else "", evidence=(ev.items if ev else []))
