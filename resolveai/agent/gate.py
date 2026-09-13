"""Final deterministic output gate: the last authority on AUTO_HANDLE vs CLARIFICATION_REQUIRED vs HUMAN_HANDOFF.
AUTO_HANDLE requires every check to pass; nothing upstream can bypass it."""
from __future__ import annotations

from resolveai.agent.state import AgentState
from resolveai.schemas.core import AutomationDecision
from resolveai.trust.pii import contains_unredacted_pii

GATE_VERSION = "output-gate-v1"


def output_gate(state: AgentState) -> AutomationDecision:
    esc, ev, intent, risk, ver, draft = state.escalation, state.evidence, state.intent, state.risk, state.verification, state.draft
    strategy = state.strategy or "handoff"
    checks = {
        "policy_allows_automation": bool(esc and esc.decision == "auto_handle"),
        "no_blocking_risk_flag": bool(risk and not risk.any_hard_block()),
        "intent_confidence_acceptable": bool(intent and (intent.confidence_band in ("HIGH", "MEDIUM") or strategy == "canned")),
        "evidence_sufficient": bool(ev and ev.sufficient) or strategy == "canned",
        "response_generated": bool(draft and draft.text),
        "response_verified": bool(ver and ver.verified),
        "evidence_refs_exist": bool(draft and (draft.evidence_ids or strategy == "canned")),
        "pii_guard": bool(draft and not contains_unredacted_pii(draft.text)),
        "schema_valid": bool(intent and ev and risk and esc and draft and ver),
    }
    blocking = [k for k, v in checks.items() if not v]
    if not blocking:
        if esc and esc.rule == "canned:non_latin_script":
            action = "CHANNEL_REDIRECT"
        else:
            action = "AUTO_HANDLE"
    elif esc and esc.clarification_allowed and strategy == "clarify" and risk and not risk.any_hard_block():
        action = "CLARIFICATION_REQUIRED"
    else:
        action = "HUMAN_HANDOFF"
    if esc is None:
        from resolveai.schemas.core import EscalationResult

        esc = EscalationResult(decision="escalate", reason_code="output_gate", reason="Execution did not reach the policy stage.", rule="gate_default")
    return AutomationDecision(decision="auto_handle" if action in ("AUTO_HANDLE", "CHANNEL_REDIRECT") else "escalate", escalation=esc, gates=checks,
                              autonomous_response_allowed=action in ("AUTO_HANDLE", "CHANNEL_REDIRECT"), action=action, gate_version=GATE_VERSION, blocking=blocking)
