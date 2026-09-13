"""Deterministic clarifying questions (no LLM: a question must not invent a diagnosis).

Used when policy permits clarification (non-risky, in-taxonomy issue whose evidence is insufficient or whose message is too
short). Phase 7 makes the questions slot-aware: each intent needs a few details (device, software version, scope, timing,
...); a detail the customer already stated anywhere in their turns is not asked again, and the ClarificationPacket records
both what is missing and what was already provided.
"""
from __future__ import annotations

import re

from resolveai.schemas.core import ClarificationPacket, IntentResult

SLOT_PHRASES = {
    "device": "which device you're using",
    "version": "which software version is installed (Settings > General > About)",
    "app": "which app or service is affected",
    "symptom": "exactly what's happening",
    "timing": "when it started",
    "scope": "whether it happens in one app or everywhere",
    "network": "whether it happens on one network or all of them",
    "word": "whether it happens with one word or everywhere",
    "backup": "whether iCloud Backup or iCloud Photos was on before the change",
    "tried": "what you've already tried",
}
SLOT_QUESTIONS = {
    "device": "Which device model?", "version": "Which software version?", "app": "Which app or service exactly?", "symptom": "What exactly is happening?",
    "timing": "When did it start (before/after an update)?", "scope": "One app or everywhere?", "network": "One network or all networks?",
    "word": "One word or all typing?", "backup": "Was iCloud Backup or iCloud Photos on before the change?", "tried": "What has the customer already tried?",
}
INTENT_SLOTS = {
    "battery_power": ("device", "version", "timing"),
    "performance_crash": ("device", "version", "scope"),
    "keyboard_text_bug": ("version", "word"),
    "connectivity": ("device", "version", "network"),
    "data_loss_sync": ("device", "backup"),
    "apps_services": ("app", "device", "version"),
    "general_complaint": ("device", "symptom"),
}
GENERIC_SLOTS = ("device", "version", "symptom")
OPENERS = {"battery_power": "We'd like to help with the battery.", "keyboard_text_bug": "We'd like to help with the typing issue.",
           "connectivity": "We'd like to help you get connected.", "data_loss_sync": "We'd like to help find your content."}
DEFAULT_OPENER = "We'd like to help."

# Only slots with a reliable surface form are auto-detected; "symptom" and "word" are always asked when the intent needs them.
_DETECT = {
    "device": re.compile(r"\b(iphone|ipad|ipod|macbook|imac|mac ?mini|mac ?pro|mac|apple ?watch|airpods|apple ?tv|homepod)\b", re.I),
    "version": re.compile(r"\b(ios|ipados|macos|watchos|tvos) ?\d+(\.\d+)*|\b(high sierra|sierra|mojave)\b|\b1[0-2]\.\d(\.\d)?\b", re.I),
    "app": re.compile(r"\b(apps?|music|itunes|imessage|messages|facetime|mail|safari|siri|camera|photos|app store|maps|calendar|notes|podcasts|icloud)\b", re.I),
    "timing": re.compile(r"\b(since|after (the |an )?update|started|began|yesterday|today|last (night|week)|this (morning|week))\b", re.I),
    "scope": re.compile(r"\b(every app|all apps|everywhere|whole phone|any app|only in|just in)\b", re.I),
    "network": re.compile(r"\b(any network|all networks|every network|home wi-?fi|cellular|lte|4g|only on)\b", re.I),
    "backup": re.compile(r"\b(backup|backed up|icloud photos|icloud backup)\b", re.I),
}


def _customer_text(bundle) -> str:
    if bundle is None:
        return ""
    return " ".join([bundle.current, bundle.issue_text, *bundle.prior_customer])


def plan(intent: IntentResult | None, bundle) -> tuple[list[str], list[str]]:
    """Returns (missing slots, already provided slots) for this intent and conversation."""
    generic = intent is None or intent.insufficient_context or intent.confidence_band == "LOW"
    slots = GENERIC_SLOTS if generic else INTENT_SLOTS.get(intent.intent, GENERIC_SLOTS)
    text = _customer_text(bundle)
    provided = [s for s in slots if s in _DETECT and _DETECT[s].search(text)]
    missing = [s for s in slots if s not in provided] or ["tried"]
    return missing, provided


def _join(parts: list[str]) -> str:
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]


def clarifying_question(intent: IntentResult | None, bundle=None, escalation=None) -> str:
    if bundle is not None and getattr(bundle, "current", ""):
        text = bundle.current
        if re.search(r"\b(help with (my )?account|account help|help with account)\b", text, re.I):
            return "Are you having trouble signing in, resetting your password, reviewing a charge, or something else?"
        if re.search(r"\b(it('?s)?|device|phone|iphone|everything|something)?\s*broken\b", text, re.I) and not re.search(r"\b(cracked|shattered|broken screen|screen (is )?broken|liquid|water|dropped|bent|damaged port|physical damage|swollen|bulging)\b", text, re.I):
            return "We'd like to help. Could you share a bit more detail about what is broken or what happens when you try to use it?"
    missing, _ = plan(intent, bundle)
    generic = intent is None or intent.insufficient_context or intent.confidence_band == "LOW"
    opener = DEFAULT_OPENER if generic else OPENERS.get(intent.intent, DEFAULT_OPENER)
    return f"{opener} Could you tell us {_join([SLOT_PHRASES[s] for s in missing])}?"


def unresolved_questions(intent: IntentResult | None, bundle) -> list[str]:
    missing, _ = plan(intent, bundle)
    qs = [SLOT_QUESTIONS[s] for s in missing]
    if bundle is not None and bundle.is_short_reply and not bundle.issue_text:
        qs.insert(0, "What is the actual issue? (the message did not state one)")
    return qs


WHY = {
    "insufficient_evidence": "No proven historical resolution matches this issue closely enough to answer it without guessing.",
    "insufficient_context": "The message does not state a concrete issue yet.",
    "low_confidence": "The type of issue is unclear, so an answer could address the wrong problem.",
}


def build_clarification(st, trace_id: str) -> ClarificationPacket:
    from resolveai.agent.explain import evidence_line  # local import: explain depends on the agent state module

    esc, ev, intent = st.escalation, st.evidence, st.intent
    missing, provided = plan(intent, st.bundle)
    code = esc.reason_code if esc else "insufficient_context"
    why = WHY.get(code, esc.reason if esc else "")
    if ev is not None:
        why += f" Evidence gate: {ev.sufficiency_level} ({ev.sufficiency_reason})."
    return ClarificationPacket(reason_code=code, why=why, evidence_level=ev.sufficiency_level if ev else "INSUFFICIENT", evidence_reason=ev.sufficiency_reason if ev else "",
                               missing_information=[SLOT_PHRASES[s] for s in missing], already_provided=provided,
                               question=st.response or clarifying_question(intent, st.bundle, esc), intent_hypothesis=intent.intent if intent else "unknown",
                               intent_confidence=round(intent.confidence, 3) if intent else 0.0, confidence_band=intent.confidence_band if intent else "LOW",
                               alternatives=[t[0] for t in intent.top3[1:]] if intent else [], evidence_summary=evidence_line(ev), trace_id=trace_id,
                               policy_version=esc.policy_version if esc else "")
