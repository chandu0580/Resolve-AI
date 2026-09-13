"""Keyword weak labels. Used for (a) golden sampling strata, (b) the keyword baseline, (c) candidate-intent signals in
retrieval. They are noisy by construction and are never treated as ground truth."""
from __future__ import annotations

import re

from resolveai.models.taxonomy import KEYWORDS

_ACTION = [
    ("update", re.compile(r"\b(update|updating|upgrade|latest version|ios 1\d|11\.\d)\b", re.I)),
    ("restart", re.compile(r"\b(restart|reboot|power (off|cycle)|force (close|quit|restart)|turn (it )?off and (back )?on)\b", re.I)),
    ("reset", re.compile(r"\b(reset|restore|reinstall|re-install|erase|sign ?out|log ?out)\b", re.I)),
    ("settings", re.compile(r"\b(settings ?>|go to settings|toggle|turn (on|off)|enable|disable|switch (on|off))\b", re.I)),
    ("article", re.compile(r"\b(article|this (link|guide|page)|check (this|out)|take a look|steps here|<url>)\b", re.I)),
    ("dm_handoff", re.compile(r"\bdm\b|direct message|private message|send us a (private )?message", re.I)),
    ("ask_info", re.compile(r"\b(which (device|model|version|ios)|what (device|model|version|ios|happens)|tell us (more|what)|let us know (what|which|if|when)|can you (tell|confirm|share)|could you (tell|confirm|share)|are you (seeing|able|using)|do you (see|have|notice)|have you (tried|restarted|updated))\b", re.I)),
]


def weak_intent(text: str) -> str:
    t = (text or "").lower()
    best, best_n = "general_complaint", 0
    for intent, kws in KEYWORDS.items():
        n = sum(1 for k in kws if k in t)
        if n > best_n:
            best, best_n = intent, n
    return best


def action_class(brand_reply: str) -> str:
    """Operational class of what the brand reply DOES. Priority: concrete actions first, handoff last."""
    for name, pat in _ACTION[:5]:
        if pat.search(brand_reply or ""):
            return name
    for name, pat in _ACTION[5:]:
        if pat.search(brand_reply or ""):
            return name
    return "other"
