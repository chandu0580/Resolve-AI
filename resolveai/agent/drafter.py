"""Grounded response drafting. Strategies:
  canned       fixed brand templates (non-English redirect, closures); no LLM
  clarify      deterministic clarifying question per intent (resolveai.agent.clarify); no LLM
  handoff      deterministic warm handoff line per escalation reason; no LLM
  troubleshoot GLM-5.2 drafts ONLY from the supplied evidence, returning machine-readable evidence references
The drafter receives the EvidenceSet, never just the message, and is called only when the policy allowed automation.

draft-v1 (Phase 4): every substantive evidence item, in retrieval order; "if the evidence does not cover the exact case,
ask". Result on golden: verified replies that only asked for device/version although the fix was in the evidence.
draft-v2 (Phase 5, resolution-aware): the resolution candidates (clustered, consistent historical fixes) come first and
are labelled with their support; the model is told to LEAD with the resolution and to ask for a detail only when the
evidence itself asks for it or the fix depends on it. An ask-only draft while a resolution candidate exists is treated
as a defect: one corrective retry asks for the resolution step. The A/B is measured in scripts/phase5/c_draft_experiment.py.
"""
from __future__ import annotations

import re

from pydantic import BaseModel, Field

from resolveai.intelligence.context import ContextBundle
from resolveai.llm import LLMClient, LLMUnavailable
from resolveai.schemas.core import DraftResponse, EscalationResult, EvidenceSet, IntentResult, ResponseStrategy

DRAFT_PROMPT_VERSION = "draft-v2"
DRAFT_PROMPT_VERSION_V1 = "draft-v1"
CANNED = {
    "non_english": "We offer support via Twitter in English. You can get help in your preferred language here: support.apple.com/contact",
    "other": "You're welcome! If anything else comes up, we're here to help.",
    "greeting": "Hi! What can we help you with today?",
    # a bare "ok" / "yes" is not a thank-you, so the closing line must not answer one
    "acknowledgement": "Thanks for letting us know. If anything else comes up, we're here to help.",
}
# a canned rule names its own template; the intent is the fallback for rules that predate the split
CANNED_BY_RULE = {"canned:greeting": "greeting", "canned:acknowledgement": "acknowledgement", "canned:other": "other",
                  "canned:non_english": "non_english", "canned:non_latin_script": "non_english"}
# Every line must hold for EVERY condition that can fire its rule, not just the typical one: `hardware` also fires on a model
# `physical_damage` flag and `repeat_contact` on thread depth alone, so neither may assert damage or steps the customer
# never described. Tested in tests/test_case_and_conversation.py.
HANDOFF_LINES = {
    "safety": "Your safety is our top priority. Please disconnect the device from any charger and stop using it immediately. A specialist is taking this over right away.",
    "prompt_injection": "We'd like to help with your device or account. A member of our team will follow up with you directly.",
    "legal_media": "We hear you. A member of our team will follow up with you directly on this.",
    "abusive_threatening": "We want to help with this. A member of our team will follow up with you directly.",
    "account_access": "To keep your account safe we need to help with this privately. A member of our team will follow up with you directly.",
    "payment_billing": "We'd like to look at this with you. Because it involves your account details, a member of our team will follow up with you directly.",
    "private_info": "We'd like to look into this with you. Because we'll need some details about your device or account, a member of our team will follow up with you directly.",
    "hardware": "We'd like to look at this with you. A member of our team will follow up with you directly about repair options.",
    "repeat_contact": "Thanks for sticking with us on this. A member of our team will pick this up with you directly so we can dig deeper.",
    "human_requested": "Of course. A member of our team will pick this up with you directly.",
    "default": "We'd like to help with this. A member of our team will follow up with you directly.",
}
_ASK_ONLY = re.compile(r"\?\s*$")
_STEP = re.compile(r"\b(settings ?>|go to|tap|toggle|restart|update|updating|reset|reinstall|sign out|back up|hold|press|check|turn (on|off)|force|install)\b", re.I)


class DraftSchema(BaseModel):
    reply: str = Field(description="the public reply, <= 280 characters")
    evidence_refs: list[str] = Field(default_factory=list, description="labels of the evidence items the reply is based on, e.g. ['E1','E3']")
    needs_more_info: bool = False


def choose_strategy(intent: IntentResult, evidence: EvidenceSet, escalation: EscalationResult) -> str:
    if escalation.decision == "auto_handle" and escalation.rule.startswith("canned:"):
        return ResponseStrategy.canned.value
    if escalation.decision == "auto_handle" and evidence.sufficient:
        return ResponseStrategy.troubleshoot.value
    if escalation.decision == "escalate" and escalation.clarification_allowed:
        return ResponseStrategy.clarify.value
    return ResponseStrategy.handoff.value


def canned_text(intent: IntentResult | None, escalation: EscalationResult | None) -> str:
    """The fixed template the canned rule names (greeting, acknowledgement, you're-welcome, language redirect), falling back
    to the intent's template."""
    if escalation is not None and escalation.rule in CANNED_BY_RULE:
        return CANNED[CANNED_BY_RULE[escalation.rule]]
    return CANNED.get(intent.intent if intent else "other", CANNED["other"])


def handoff_line(escalation: EscalationResult, context=None) -> str:
    ctx_turns = getattr(context, "brand_turns", 0) if context else 0
    if ctx_turns > 0 and escalation.reason_code in ("repeat_contact", "human_requested"):
        return "I've passed our full conversation to a support specialist so you won't need to repeat yourself. A team member will pick this up directly."
    return HANDOFF_LINES.get(escalation.reason_code, HANDOFF_LINES["default"])


def is_ask_only(text: str) -> bool:
    """A draft that ends in a question and contains no instruction step."""
    return bool(_ASK_ONLY.search(text.strip())) and not _STEP.search(text)


def _evidence_block(evidence: EvidenceSet) -> tuple[str, dict[str, str]]:
    """v1: substantive, de-duplicated evidence in retrieval order with labels E1..En; returns (text, label->evidence_id)."""
    seen, lines, labels = set(), [], {}
    for it in evidence.items:
        if not it.substantive:
            continue
        key = it.brand_reply.lower().strip()
        if key in seen:
            continue
        seen.add(key)
        label = f"E{len(labels) + 1}"
        labels[label] = it.evidence_id
        lines.append(f"[{label}] customer: {it.customer_message[:160]}\n     brand reply: {it.brand_reply[:240]}")
    return "\n".join(lines), labels


def _resolution_block(evidence: EvidenceSet) -> tuple[str, dict[str, str], bool]:
    """v2: resolution candidates first (representative reply + support), then the remaining substantive items.
    Returns (text, label->evidence_id, has_resolution_candidate)."""
    by_id = {i.evidence_id: i for i in evidence.items}
    seen, lines, labels = set(), [], {}
    has_res = False
    for c in evidence.resolution_candidates:
        rep = by_id.get(c.representative_id)
        if rep is None:
            continue
        key = rep.brand_reply.lower().strip()
        if key in seen:
            continue
        seen.add(key)
        label = f"E{len(labels) + 1}"
        labels[label] = rep.evidence_id
        has_res = True
        lines.append(f"[{label}] RESOLUTION ({c.action_class}; used in {c.support_count} similar case{'s' if c.support_count != 1 else ''}, share {c.share:.0%})\n"
                     f"     customer: {rep.customer_message[:160]}\n     brand reply: {rep.brand_reply[:240]}")
    for it in evidence.items:
        if not it.substantive:
            continue
        key = it.brand_reply.lower().strip()
        if key in seen:
            continue
        seen.add(key)
        label = f"E{len(labels) + 1}"
        labels[label] = it.evidence_id
        lines.append(f"[{label}] other similar case\n     customer: {it.customer_message[:160]}\n     brand reply: {it.brand_reply[:240]}")
    return "\n".join(lines), labels, has_res


def _call(client: LLMClient, msgs: list[dict[str, str]], labels: dict[str, str], version: str, attempts: int) -> DraftResponse:
    out = client.structured(msgs, DraftSchema, prompt_version=version, max_tokens=1000)   # hidden reasoning tokens; 600 truncated 5 of 8 drafts on golden
    refs = [labels[x] for x in out.evidence_refs if x in labels]
    text = re.sub(r"\s+", " ", out.reply).strip()[:280]
    return DraftResponse(text=text, strategy=ResponseStrategy.troubleshoot, evidence_ids=refs, model=client.model, prompt_version=version, attempts=attempts)


def draft_troubleshoot(client: LLMClient, bundle: ContextBundle, intent: IntentResult, evidence: EvidenceSet, *, corrective: str | None = None, version: str = "v2") -> DraftResponse:
    if version == "v1":
        return draft_troubleshoot_v1(client, bundle, intent, evidence, corrective=corrective)
    block, labels, has_res = _resolution_block(evidence)
    if not labels:
        raise LLMUnavailable("no substantive evidence to draft from", kind="no_input")
    ctx = f"\nEarlier customer message: {bundle.issue_text}" if bundle.issue_text else ""
    rules = ("Rules: write ONLY from the evidence replies below; do not invent facts, steps, policies, timelines or actions you have not taken; do not promise refunds or replacements; "
             "do not mention evidence, retrieval, models or internal metadata; do not include URLs or @handles; be concise and warm in AppleSupport's tone; <= 280 characters.\n"
             "Never copy placeholder tokens such as <url>, <EMAIL> or <PHONE>; say 'the steps on our support site' instead. "
             "LEAD with the RESOLUTION step(s) from the highest-support RESOLUTION item, phrased as the brand did. Ask for a detail (device, version) ONLY if the evidence reply "
             "itself asks for it or the step depends on it; never reply with a question alone when a RESOLUTION item exists. If the resolutions differ by device or version, "
             "state the one that matches the customer's message and say which case it applies to.")
    if corrective:
        rules += f"\nYour previous draft was rejected: {corrective}. Fix exactly that."
    msgs = [
        {"role": "system", "content": "You are the AppleSupport Twitter agent. You answer only with the JSON requested."},
        {"role": "user", "content": f"Intent: {intent.intent}.{ctx}\nCurrent customer message: {bundle.current}\n\nEvidence (how AppleSupport resolved similar cases; RESOLUTION items are the proven fixes):\n{block}\n\n{rules}\n"
                                    f'Return JSON: {{"reply": str, "evidence_refs": [labels used, e.g. "E1"], "needs_more_info": bool}}'},
    ]
    attempts = 2 if corrective else 1
    d = _call(client, msgs, labels, DRAFT_PROMPT_VERSION, attempts)
    if has_res and is_ask_only(d.text) and not corrective:
        # ask-only while a proven resolution exists: one bounded corrective retry, then keep whichever came back
        msgs2 = msgs + [{"role": "assistant", "content": d.text}, {"role": "user", "content": "That reply only asks a question. Give the customer the RESOLUTION step from the highest-support item (you may add one short question after it). Return the same JSON."}]
        try:
            d2 = _call(client, msgs2, labels, DRAFT_PROMPT_VERSION + "+resolution", 2)
            if not is_ask_only(d2.text) and d2.evidence_ids:
                return d2
        except LLMUnavailable:
            pass
    return d


def draft_troubleshoot_v1(client: LLMClient, bundle: ContextBundle, intent: IntentResult, evidence: EvidenceSet, *, corrective: str | None = None) -> DraftResponse:
    block, labels = _evidence_block(evidence)
    if not labels:
        raise LLMUnavailable("no substantive evidence to draft from", kind="no_input")
    ctx = f"\nEarlier customer message: {bundle.issue_text}" if bundle.issue_text else ""
    rules = ("Rules: write ONLY from the evidence replies below; do not invent facts, steps, policies, timelines or actions you have not taken; do not promise refunds or replacements; "
             "do not mention evidence, retrieval, models or internal metadata; do not include URLs or @handles; be concise and warm in AppleSupport's tone; "
             "if the evidence does not cover the customer's exact case, ask for the missing detail instead of guessing; <= 280 characters.")
    if corrective:
        rules += f"\nYour previous draft was rejected: {corrective}. Fix exactly that."
    msgs = [
        {"role": "system", "content": "You are the AppleSupport Twitter agent. You answer only with the JSON requested."},
        {"role": "user", "content": f"Intent: {intent.intent}.{ctx}\nCurrent customer message: {bundle.current}\n\nEvidence (how AppleSupport resolved similar cases):\n{block}\n\n{rules}\n"
                                    f'Return JSON: {{"reply": str, "evidence_refs": [labels used, e.g. "E1"], "needs_more_info": bool}}'},
    ]
    return _call(client, msgs, labels, DRAFT_PROMPT_VERSION_V1, 2 if corrective else 1)
