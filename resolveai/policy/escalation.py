"""Escalation policy (policy-v3): deterministic, ordered rules. The LLM never decides here (Phase 1A: every model's
escalation judgement was at or below a constant baseline). Inputs are the classifier result (with confidence band,
multi-intent and taxonomy-gap flags), LLM/rule-extracted risk flags, the evidence gate verdict (with its reason), the
grounding/verification verdict, thread structure and LLM availability. First matching rule wins and is named.

Rule order mirrors the annotation guide's reason priority (safety > legal > private_info > hardware > repeat_contact >
vague_hostile) with the Phase-4 flags interleaved at their natural severity, then system-level reasons (insufficient or
conflicting evidence, grounding failure, low confidence, LLM unavailable).

`clarification_allowed` tells the orchestrator that, when evidence is insufficient for a non-risky, in-taxonomy issue, a
deterministic clarifying question is an acceptable action instead of a human handoff (guide: "clarify" strategy).
"""
from __future__ import annotations

import re

from resolveai.intelligence import conversation_acts as acts
from resolveai.schemas.core import ConversationContext, EscalationResult, EvidenceSet, GroundingResult, IntentResult, RiskFlags

POLICY_VERSION = "policy-v3.4"   # v3.4 (autonomy audit 2026-09-13): canned:non_latin_script moved before private_info to recover ~10 unnecessary handoffs (FM1/P2)
#                                  v3.3 (release-readiness pass): the language redirect obeys the confidence floor; a bare acknowledgement gets its own rule
#                                  v3.2 (final product pass): greeting template, explicit human request, thanks vs bare acknowledgement; v3.1 (Phase 7): prompt_injection hard block
CONFIDENCE_FLOOR = 0.45
ALWAYS_ESCALATE_INTENTS = {"account_store_repair", "hardware_damage"}
CANNED_INTENTS = {"non_english", "other"}
BRAND_TURNS_WITHOUT_PROGRESS = 2
CLARIFIABLE_EVIDENCE_REASONS = {"weak_similarity", "insufficient_query", "insufficient_resolution_evidence", "ambiguous_intent", "no_relevant_evidence",
                                 "weak_resolution_evidence", "mixed_resolution"}   # Phase 5: WEAK gate levels clarify; mixed resolutions are never chosen arbitrarily

POLICY_RULES: list[dict] = [
    {"rule": "safety", "reason_code": "safety", "outcome": "handoff", "when": "Safety concern (injury, smoke, self-harm or threat)."},
    {"rule": "prompt_injection", "reason_code": "prompt_injection", "outcome": "handoff", "when": "The message tries to instruct the assistant, reveal its configuration or supply evidence."},
    {"rule": "security", "reason_code": "safety", "outcome": "handoff", "when": "Possible account security or device compromise."},
    {"rule": "legal", "reason_code": "legal_media", "outcome": "handoff", "when": "Legal action, press or a regulator is mentioned."},
    {"rule": "abusive", "reason_code": "abusive_threatening", "outcome": "handoff", "when": "Abusive or threatening message with no actionable issue."},
    {"rule": "canned:greeting", "reason_code": "none", "outcome": "template_reply", "when": "Only a greeting (\"hi\", \"hello\"): a fixed greeting asking what the customer needs; nothing is retrieved or drafted."},
    {"rule": "canned:non_latin_script", "reason_code": "none", "outcome": "template_reply", "when": "Most of the message's letters are outside the Latin script (Japanese, Arabic, Hindi, ...): fixed language redirect, read off the characters rather than predicted. Checked before sensitive rules so non-Latin messages are never mis-routed via needs_private_info."},
    {"rule": "account_access", "reason_code": "account_access", "outcome": "handoff", "when": "Account access or identity verification is involved."},
    {"rule": "payment_billing", "reason_code": "payment_billing", "outcome": "handoff", "when": "Billing, refund, order or another sensitive account action."},
    {"rule": "private_info", "reason_code": "private_info", "outcome": "handoff", "when": "Account, store or repair issue, or private identifiers are needed (a model-only flag needs the deterministic rule)."},
    {"rule": "hardware", "reason_code": "hardware", "outcome": "handoff", "when": "Hardware damage or a physical-damage flag."},
    {"rule": "repeat_contact", "reason_code": "repeat_contact", "outcome": "handoff", "when": "The customer already tried the standard steps, or the thread is deep without progress."},
    {"rule": "vague_hostile", "reason_code": "vague_hostile", "outcome": "handoff", "when": "Frustrated customer with no concrete symptom."},
    {"rule": "human_requested", "reason_code": "human_requested", "outcome": "handoff", "when": "The customer explicitly asks to talk to a person."},
    {"rule": "canned:other", "reason_code": "none", "outcome": "template_reply", "when": "The customer thanks the team: a fixed \"you're welcome\"."},
    {"rule": "canned:acknowledgement", "reason_code": "none", "outcome": "template_reply", "when": "A bare acknowledgement (\"ok\", \"yes\") that answers no open question in the thread: a fixed closing line."},
    {"rule": "insufficient_context", "reason_code": "insufficient_context", "outcome": "clarify", "when": "The message does not state the issue."},
    {"rule": "other_non_closure", "reason_code": "insufficient_evidence", "outcome": "handoff", "when": "Not a troubleshooting request (product question, suggestion or off-topic)."},
    {"rule": "general_complaint_clarify", "reason_code": "insufficient_context", "outcome": "clarify", "when": "A complaint with no concrete symptom: ask what is happening."},
    {"rule": "taxonomy_gap", "reason_code": "taxonomy_gap_risk", "outcome": "handoff", "when": "Outside the supported taxonomy and carrying risk."},
    {"rule": "low_confidence", "reason_code": "low_confidence", "outcome": "clarify", "when": f"Intent confidence below {CONFIDENCE_FLOOR} or in the LOW band."},
    {"rule": "canned:non_english", "reason_code": "none", "outcome": "template_reply", "when": "Non-English message the classifier is confident about: fixed language redirect template. A LOW-confidence guess is caught by `low_confidence` above and asks the customer to restate instead."},
    {"rule": "conflicting_evidence", "reason_code": "conflicting_evidence", "outcome": "handoff", "when": "Historical cases prescribe different resolutions."},
    {"rule": "evidence_gate", "reason_code": "insufficient_evidence", "outcome": "clarify_or_handoff", "when": "Evidence is not SUFFICIENT or STRONG (clarify when the gap is clarifiable and nothing is high-impact)."},
    {"rule": "grounding_gate", "reason_code": "grounding_failed", "outcome": "handoff", "when": "The drafted reply could not be verified against the evidence."},
    {"rule": "llm_fallback", "reason_code": "llm_unavailable", "outcome": "handoff", "when": "The drafting model was unavailable."},
    {"rule": "default_auto", "reason_code": "none", "outcome": "auto_reply", "when": "Clear issue, sufficient evidence, no risk flags: draft, verify and pass the output gate."},
]

VAGUE_ACCOUNT = re.compile(r"\b(help with (my )?account|account help|help with account)\b", re.I)
VAGUE_BROKEN = re.compile(r"\b(it('?s)?|device|phone|iphone|everything|something)?\s*broken\b", re.I)
PHYSICAL_SIGNALS = re.compile(r"\b(cracked|shattered|broken screen|screen (is )?broken|liquid|water|dropped|bent|damaged port|physical damage|swollen|bulging)\b", re.I)


def _last_brand_turn_is_clarification(ctx: ConversationContext) -> bool:
    brand_turns = [t for t in ctx.turns if t.role == "brand"]
    if not brand_turns:
        return False
    last = brand_turns[-1].text.strip()
    if last.endswith("?"):
        return True
    return bool(re.search(r"\b(could you|can you|are you|let us know|what (is|model|version)|which (model|version)|please share|more detail)\b", last, re.I))


def decide(
    intent: IntentResult,
    risk: RiskFlags,
    context: ConversationContext | None = None,
    evidence: EvidenceSet | None = None,
    grounding: GroundingResult | None = None,
    llm_available: bool = True,
    message: str | None = None,
) -> EscalationResult:
    ctx = context or ConversationContext()

    def E(decision, code, rule, reason, clarify=False):
        return EscalationResult(decision=decision, reason_code=code, rule=rule, reason=reason, policy_version=POLICY_VERSION, clarification_allowed=clarify)

    # ---- hard blocks: a human must respond -------------------------------------------------------------------------
    if risk.safety_concern:
        return E("escalate", "safety", "safety", "Possible safety concern (injury, smoke, self-harm or threat); a human must respond.")
    if risk.prompt_injection:
        return E("escalate", "prompt_injection", "prompt_injection", "The message tries to instruct the assistant, reveal its configuration or supply its own evidence; customer text is never treated as instructions, so a human reviews it.")
    if risk.security_concern:
        return E("escalate", "safety", "security", "Possible account security or device compromise; a human must verify before any advice is given.")
    if risk.legal_or_media_threat:
        return E("escalate", "legal_media", "legal", "Customer mentions legal action, press or a regulator; needs human handling.")
    if risk.abusive_threatening and not risk.is_actionable:
        return E("escalate", "abusive_threatening", "abusive", "Abusive or threatening message with no actionable issue; a human should de-escalate.")
    # ---- a bare greeting needs no troubleshooting (v3.2): matched after every hard block, before intent-based rules ----------
    if message is not None and acts.is_greeting_only(message):
        return E("auto_handle", "none", "canned:greeting", "Greeting only: a fixed greeting asks what the customer needs; nothing is retrieved or drafted.")
    # v3.4: non-Latin messages are redirected before the sensitive-account rules. Script is deterministic (character
    # properties), so it never mis-fires. Moving it here prevents ~10 non-English messages per 197 from being caught
    # by needs_private_info (FM1/P2 from the 2026-09-13 autonomy audit).
    if message is not None and acts.is_non_latin_script(message):
        return E("auto_handle", "none", "canned:non_latin_script", "Non-Latin script: fixed language redirect with no risk.")
    # ---- customer-specific / sensitive: cannot be resolved publicly ----------------------------------------------------
    if risk.account_access_risk:
        return E("escalate", "account_access", "account_access", "Account access or identity verification is involved; must move to a private, verified channel.")
    if risk.payment_billing_risk or risk.sensitive_action_required:
        return E("escalate", "payment_billing", "payment_billing", "Billing, refund, order or account changes need a human with account access.")
    if (intent.intent == "account_store_repair" or risk.needs_private_info) and not (message is not None and VAGUE_ACCOUNT.search(message)):
        return E("escalate", "private_info", "private_info", "Resolving this needs account, order, case or device identifiers that must be shared privately.")
    has_physical_signal = message is not None and bool(PHYSICAL_SIGNALS.search(message))
    is_vague_hardware = message is not None and not has_physical_signal and (
        intent.intent == "hardware_damage"
        or bool(VAGUE_BROKEN.search(message))
        or bool(re.search(r"\b(won.?t|not|doesn.?t)\s*(turn(ing)?\s*on|power(ing)?\s*on)|just died|died\b", message, re.I))
    )

    if (intent.intent == "hardware_damage" or risk.physical_damage) and not is_vague_hardware:
        return E("escalate", "hardware", "hardware", "Physical damage or a repair decision cannot be resolved with a public reply.")
    if risk.repeat_contact or (ctx.brand_turns >= BRAND_TURNS_WITHOUT_PROGRESS and not _last_brand_turn_is_clarification(ctx)):
        return E("escalate", "repeat_contact", "repeat_contact", "Customer has already tried the standard steps or the thread is deep without progress; public troubleshooting is unlikely to help.")
    if not risk.is_actionable and (risk.high_frustration or risk.abusive_threatening):
        return E("escalate", "vague_hostile", "vague_hostile", "Frustrated customer with no concrete symptom; a human should de-escalate and ask questions.")
    if message is not None and acts.requests_human(message):
        return E("escalate", "human_requested", "human_requested", "The customer asked to talk to a person; a member of the team takes over with the conversation so far.")
    # ---- closures: thanks is canned; a bare "yes" / "no" / "ok" only when it is not answering an open question -------------
    if message is not None and acts.is_gratitude(message):
        return E("auto_handle", "none", "canned:other", "The customer is thanking us: a fixed 'you're welcome' with no risk.")
    if message is not None and intent.intent == "other" and acts.is_acknowledgement(message) and not _has_customer_history(ctx):
        # a bare "ok"/"yes" is not a thank-you; the reply must not claim gratitude the customer never expressed
        return E("auto_handle", "none", "canned:acknowledgement", "A bare acknowledgement that answers no open question: a fixed closing line that asserts nothing.")
    # (non-Latin script is now caught before the sensitive-account block above — v3.4 move)
    # ---- understanding quality (a message that states no issue cannot be canned or answered) ------------------------
    if intent.insufficient_context or (message is not None and VAGUE_ACCOUNT.search(message)) or is_vague_hardware:
        return E("escalate", "insufficient_context", "insufficient_context", "The message does not state the issue and the thread does not clarify it.", clarify=True)
    # ---- canned paths: fixed, risk-free responses -------------------------------------------------------------------
    if intent.intent == "other":
        return E("escalate", "insufficient_evidence", "other_non_closure", "Not a troubleshooting request (product question, suggestion or off-topic); no historical evidence can answer it, a human should reply.")
    if intent.intent == "general_complaint" and not intent.insufficient_context:
        # taxonomy: "no concrete actionable symptom" - no evidence can answer it (Phase 5 hand-check: 4 of the 5 wrongly
        # 'sufficient' dev cases were vague complaints); ask for the symptom instead of drafting a fix
        return E("escalate", "insufficient_context", "general_complaint_clarify", "The message states no concrete symptom; asking what exactly is happening before troubleshooting.", clarify=True)
    if intent.taxonomy_gap and (risk.high_impact or risk.high_frustration):
        return E("escalate", "taxonomy_gap_risk", "taxonomy_gap", "The issue is outside the supported taxonomy and carries risk; a human should handle it.")
    if intent.confidence_band == "LOW" or intent.confidence < CONFIDENCE_FLOOR:
        return E("escalate", "low_confidence", "low_confidence", f"Intent confidence {intent.confidence:.2f} is low; unclear what the customer needs.", clarify=True)
    # The language redirect is a terminal, customer-visible action, so it obeys the same confidence floor as every other
    # automatic path. On 4,000 corpus messages the LOW band of this class was mostly English (typos, transliteration, a
    # mention of another country); telling those customers "we only support English" is worse than asking them to restate.
    if intent.intent == "non_english":
        return E("auto_handle", "none", "canned:non_english", "Non-English message: fixed language redirect with no risk.")
    # ---- evidence invariant: no sufficient evidence -> no autonomous response --------------------------------------------
    if evidence is not None and evidence.sufficiency_reason == "conflicting_evidence":
        return E("escalate", "conflicting_evidence", "conflicting_evidence", "Historical cases prescribe different resolutions for this issue; a human should choose.")
    if evidence is not None and not evidence.sufficient:
        return E("escalate", "insufficient_evidence", "evidence_gate", "No sufficiently similar historical resolution was found; a human should handle this rather than an ungrounded reply.",
                 clarify=evidence.sufficiency_reason in CLARIFIABLE_EVIDENCE_REASONS and not risk.high_impact and not intent.multi_intent)
    if grounding is not None and not grounding.grounded:
        return E("escalate", "grounding_failed", "grounding_gate", "The drafted reply could not be verified against historical evidence; escalating instead of sending it.")
    if not llm_available:
        return E("escalate", "llm_unavailable", "llm_fallback", "The drafting model was unavailable; escalating rather than replying without a draft.")
    return E("auto_handle", "none", "default_auto", f"Clear '{intent.intent}' issue with grounded troubleshooting steps and no risk flags.")


def _has_customer_history(ctx: ConversationContext) -> bool:
    return any(t.role == "customer" for t in ctx.turns)


def hard_handoff_guaranteed(intent: IntentResult, rules_risk: RiskFlags, context: ConversationContext | None, evidence: EvidenceSet | None, message: str | None) -> bool:
    """Phase 5 risk short-circuit. The LLM risk extractor can only ADD flags (OR-merge) or clear `is_actionable`; both
    can only move the policy towards escalation. So if the rules-only flags already yield an escalation WITHOUT
    clarification, the final action is a human handoff whatever the LLM says, and the risk call is skipped."""
    e = decide(intent, rules_risk, context, evidence, None, llm_available=True, message=message)
    return e.decision == "escalate" and not e.clarification_allowed

