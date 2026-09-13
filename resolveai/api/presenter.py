"""AgentResult -> API response, plus the API-level autonomy invariant.

The output gate inside the agent is the authority on AUTO_HANDLE. The API re-checks the same invariant independently before
returning an automatic reply, so a regression anywhere in the agent fails closed (500, reply withheld) instead of shipping
an ungrounded answer.
"""
from __future__ import annotations

from resolveai.api.schemas import ConversationView, OutcomeView, ResolveResponse, ResponseView
from resolveai.schemas.core import AgentResult


def is_template(r: AgentResult) -> bool:
    return r.draft is not None and r.draft.strategy.value == "canned" and r.decision.escalation.rule.startswith("canned:")


def autonomy_violations(r: AgentResult) -> list[str]:
    """Empty unless an AUTO_HANDLE result breaks the evidence invariant."""
    if r.action != "AUTO_HANDLE":
        return []
    v = []
    if r.decision.escalation.decision != "auto_handle" or not r.decision.autonomous_response_allowed:
        v.append("policy_blocks_automation")
    if r.decision.blocking:
        v.append("output_gate_checks_failed")
    if r.risk.any_hard_block():
        v.append("hard_risk_flag_raised")
    if r.verification is None or not r.verification.verified:
        v.append("verification_failed")
    if not r.response.strip():
        v.append("empty_response")
    if not is_template(r):
        if not r.evidence.sufficient:
            v.append("evidence_insufficient")
        known = {i.evidence_id for i in r.evidence.items}
        if not r.evidence_refs or not set(r.evidence_refs) <= known:
            v.append("evidence_refs_missing_or_unknown")
        if not r.citations or {c.evidence_id for c in r.citations} != set(r.evidence_refs):
            v.append("citations_missing")
    return v


def present(r: AgentResult) -> ResolveResponse:
    s = r.summary
    esc = r.decision.escalation
    outcome = OutcomeView(action=r.action, what_happened=s.what_happened if s else r.action, why=s.why if s else esc.reason, evidence_basis=s.evidence_basis if s else "",
                          next_step=s.next_step if s else "", reason_code=esc.reason_code, rule=esc.rule, policy_version=esc.policy_version,
                          autonomous_response_allowed=r.decision.autonomous_response_allowed, output_gate=dict(r.decision.gates), blocking_checks=list(r.decision.blocking))
    if r.action == "AUTO_HANDLE":
        kind = "template_reply" if is_template(r) else "auto_reply"
        response = ResponseView(kind=kind, text=r.response, sent_automatically=True, evidence_refs=list(r.citations) if kind == "auto_reply" else [],
                                draft_attempts=r.draft.attempts if r.draft else 0)
    elif r.action == "CLARIFICATION_REQUIRED":
        response = ResponseView(kind="clarifying_question", text=r.response, sent_automatically=False)
    else:
        response = ResponseView(kind="handoff_notice", text=r.response, sent_automatically=False, draft_attempts=r.draft.attempts if r.draft else 0)
    return ResolveResponse(request_id=r.request_id, trace_id=r.trace_id, action=r.action, outcome=outcome, response=response, intent=r.intent, evidence=r.evidence, risk=r.risk,
                           verification=r.verification, clarification=r.clarification if r.action == "CLARIFICATION_REQUIRED" else None,
                           handoff=r.handoff if r.action == "HUMAN_HANDOFF" else None, conversation=ConversationView(message=r.message, context=r.context),
                           versions=r.versions, stage_status=dict(r.stage_status), latency_ms=dict(r.latency), usage=r.usage)
