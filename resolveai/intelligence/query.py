"""Deterministic retrieval-query constructor and intent-aware retrieval policy.

Query = bounded context text (issue text + current for short replies, else current) with duplicate tokens removed, plus a
canonical intent phrase ONLY when the classifier is HIGH confidence. No LLM: the transformation is a set of string rules
that are testable and explainable, and an LLM rewrite was not shown to be needed (see Phase 3 benchmark).

Retrieval safety: classifier confidence never discards evidence. Intent is applied as a *boost* by fusing the plain
candidate list with an intent-filtered list (RRF), and only at HIGH/MEDIUM confidence; at LOW confidence retrieval is
unchanged and the ambiguity is marked on the result.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from resolveai.intelligence.context import ContextBundle
from resolveai.retrieval.bm25 import tokenize
from resolveai.schemas.core import IntentResult

CANONICAL = {
    "battery_power": "battery drains fast not charging",
    "performance_crash": "iphone freezes crashes keeps restarting",
    "keyboard_text_bug": "typing letter i autocorrect question mark box",
    "connectivity": "wifi bluetooth cellular not connecting",
    "data_loss_sync": "photos missing icloud backup restore",
    "apps_services": "app not working after update",
    "account_store_repair": "apple id order repair appointment",
    "hardware_damage": "screen broken hardware damaged",
    "general_complaint": "",
    "non_english": "",
    "other": "",
}


PARAPHRASE_EXPANSIONS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(keeps changing what i type|typing wrong words|autocorrect changing words|keyboard changing text|predictive text issue)\b", re.I),
     "keyboard autocorrect text replacement typing issue"),
    (re.compile(r"\b(can.?t connect|won.?t connect|wi-?fi not working|wi-?fi keeps dropping|unable to join network)\b", re.I),
     "wifi network connection settings reset"),
    (re.compile(r"\b(restart (my )?iphone|how do i restart|force restart)\b", re.I),
     "restart iphone turn off side button"),
]


@dataclass(frozen=True)
class QueryPlan:
    text: str
    intent_hint: str | None          # intent used for boosting, or None
    boost: str                       # none | mild | strong
    allowed_intents: tuple[str, ...] # primary + secondary at MEDIUM/HIGH; empty at LOW
    ambiguous: bool


def _dedupe(text: str) -> str:
    seen, out = set(), []
    for w in text.split():
        k = w.lower().strip(".,!?")
        if k and k not in seen:
            seen.add(k)
            out.append(w)
    return " ".join(out)


def build_query(bundle: ContextBundle, intent: IntentResult | None = None, *, use_intent: bool = True) -> QueryPlan:
    raw_base = re.sub(r"\s+", " ", bundle.text_for_retrieval).strip()
    expanded_base = raw_base
    for pat, expansion in PARAPHRASE_EXPANSIONS:
        if pat.search(bundle.current) or pat.search(bundle.text_for_retrieval):
            expanded_base = f"{raw_base} {expansion}"
            break
    base = _dedupe(expanded_base)
    if intent is None or not use_intent or intent.insufficient_context:
        return QueryPlan(text=base, intent_hint=None, boost="none", allowed_intents=(), ambiguous=intent is not None and intent.insufficient_context)
    allowed = tuple([intent.intent] + [s for s in intent.secondary_intents if s != intent.intent])
    if intent.confidence_band == "HIGH":
        phrase = CANONICAL.get(intent.intent, "")
        text = _dedupe(f"{base} {phrase}".strip()) if phrase and len(tokenize(base)) < 12 else base
        return QueryPlan(text=text, intent_hint=intent.intent, boost="strong", allowed_intents=allowed, ambiguous=intent.multi_intent)
    if intent.confidence_band == "MEDIUM":
        return QueryPlan(text=base, intent_hint=intent.intent, boost="mild", allowed_intents=allowed, ambiguous=True)
    return QueryPlan(text=base, intent_hint=None, boost="none", allowed_intents=(), ambiguous=True)
