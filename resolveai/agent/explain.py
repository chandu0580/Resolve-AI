"""Operator-facing explanations: WHAT the agent did, WHY, on WHAT evidence, and WHAT happens next.

Built deterministically from the typed state (decision, escalation rule, output-gate checks, verification, handoff and
clarification packets). No LLM and no free-text reasoning: every sentence is assembled from recorded fields, so it can
be audited against the trace.
"""
from __future__ import annotations

from resolveai.agent.state import AgentState
from resolveai.schemas.core import DecisionSummary, EvidenceRef
from resolveai.schemas.evidence import EvidenceSet


def citations(st: AgentState) -> list[EvidenceRef]:
    """The historical cases an autonomous troubleshooting reply was drafted from, with provenance and rank metadata."""
    if st.draft is None or st.evidence is None:
        return []
    by_id = {i.evidence_id: i for i in st.evidence.items}
    refs = []
    for eid in st.draft.evidence_ids:
        it = by_id.get(eid)
        if it is None:
            continue
        refs.append(EvidenceRef(evidence_id=it.evidence_id, thread_id=it.thread_id, source_row_id=it.source_row_id, created_at=it.created_at, rank=it.rank,
                                similarity=round(it.quality.semantic_relevance, 3), retrieval_source=it.retrieval_source, action_class=it.quality.action_class,
                                resolution_bearing=it.quality.resolution_relevance, outcome=it.outcome))
    return refs


def evidence_line(ev: EvidenceSet | None) -> str:
    if ev is None or not ev.items:
        return "No historical evidence was retrieved."
    top = ev.signals.top_similarity if ev.signals else ev.items[0].quality.semantic_relevance
    clusters = ", ".join(f"{c.action_class} x{c.support_count}" for c in ev.resolution_candidates[:3]) or "none"
    return (f"{len(ev.items)} similar historical cases retrieved; top similarity {top:.2f}; evidence {ev.sufficiency_level} ({ev.sufficiency_reason}); "
            f"resolution clusters: {clusters}; resolution confidence {ev.resolution_confidence:.2f}.")


def build_summary(st: AgentState) -> DecisionSummary:
    d, esc = st.decision, st.escalation
    action = d.action if d else "HUMAN_HANDOFF"
    reason_code = esc.reason_code if esc else "output_gate"
    rule = esc.rule if esc else "gate_default"
    policy_version = esc.policy_version if esc else ""
    blocking = list(d.blocking) if d else []
    ev_line = evidence_line(st.evidence)
    if action == "AUTO_HANDLE" and st.draft is not None and st.draft.strategy.value == "canned":
        return DecisionSummary(action=action, what_happened=f"Sent a fixed template ({rule}).", why=esc.reason if esc else "", evidence_basis="Templates make no product claims and need no evidence.",
                               next_step="No further action unless the customer replies.", reason_code=reason_code, rule=rule, policy_version=policy_version)
    if action == "AUTO_HANDLE":
        cov = st.verification.coverage if st.verification else 0.0
        basis = "; ".join(f"{c.evidence_id} ({c.action_class}, similarity {c.similarity:.2f}, rank {c.rank})" for c in st.citations) or "none"
        return DecisionSummary(action=action, what_happened=f"Answered automatically with a verified reply grounded in {len(st.citations)} historical case(s).",
                               why=f"{esc.reason if esc else ''} Evidence {st.evidence.sufficiency_level if st.evidence else ''}; verifier passed (evidence coverage {cov:.2f}); every output-gate check passed.",
                               evidence_basis=f"Cited cases: {basis}. {ev_line}", next_step="Send the reply; re-open the case if the customer reports the fix did not work.",
                               reason_code=reason_code, rule=rule, policy_version=policy_version)
    if action == "CLARIFICATION_REQUIRED":
        c = st.clarification
        asks = ", ".join(c.missing_information) if c and c.missing_information else "a description of the issue"
        return DecisionSummary(action=action, what_happened="Asked the customer one clarifying question instead of answering.",
                               why=(c.why if c else (esc.reason if esc else "")), evidence_basis=ev_line,
                               next_step=f"Wait for the customer's reply ({asks}); the same pipeline runs again with the added detail.",
                               reason_code=reason_code, rule=rule, policy_version=policy_version)
    why = esc.reason if esc else "Execution did not reach the policy stage."
    if esc is not None and esc.decision == "auto_handle" and blocking:
        why = f"The policy allowed automation but the output gate blocked the reply: {', '.join(blocking)}."
    next_step = st.handoff.recommended_next_action if st.handoff else "Review the thread and respond manually."
    return DecisionSummary(action="HUMAN_HANDOFF", what_happened="Handed the case to a human agent with a handoff packet; no autonomous answer was sent.", why=why,
                           evidence_basis=ev_line, next_step=next_step, reason_code=reason_code, rule=rule, policy_version=policy_version, blocking_checks=blocking)
