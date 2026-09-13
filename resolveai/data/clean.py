"""Deterministic text normalisation for tweets. PII redaction itself lives in the Trust layer (resolveai.trust.pii)
and is applied here so every stored customer text is already redacted."""
from __future__ import annotations

import html
import re

from resolveai.trust.pii import Redaction, redact_pii  # noqa: F401  (re-exported for callers of the data layer)

_URL = re.compile(r"https?://\S+")
_MENTION = re.compile(r"@\w+")
_WS = re.compile(r"\s+")
# Agent sign-offs used by many brands: "^EC", "/BH", "-SM", "~KB" at the end, and "1/2"-style counters.
_SIGNATURE = re.compile(r"(\s*[\^/~\-]\s?[A-Z]{1,3}\s*$)|(\s*\b\d/\d\s*$)")


def strip_signature(text: str) -> str:
    return _SIGNATURE.sub("", text).rstrip()


def clean_tweet(text: str, *, keep_url_token: bool = True, redact: bool = True) -> str:
    """Normalise one tweet. Customer handles are anonymised numeric ids (@115858) in this dataset, so all
    @-mentions are removed rather than just the brand's. URLs become a token because t.co links are dead."""
    if not isinstance(text, str):
        return ""
    t = html.unescape(text)
    t = _URL.sub(" <url> " if keep_url_token else " ", t)
    t = _MENTION.sub(" ", t)
    t = strip_signature(t)
    if redact:
        t = redact_pii(t).text
    return _WS.sub(" ", t).strip()


def is_dm_handoff(brand_reply: str) -> bool:
    """Did the brand push the customer to a private channel?"""
    t = (brand_reply or "").lower()
    return bool(re.search(r"\bdm\b|direct message|private message|send us a (private )?message", t))


# --- outcome signal ------------------------------------------------------------------------------
# Used ONLY as a retrieval/rerank bonus, never as a ground-truth label (locked decision). Hand-checked precision on
# 50 pairs: positive 0.72 (strict 'resolved' 0.48), negative 1.00 — see data/dev/outcome_check_labelled.csv.
_POS = re.compile(r"\b(thank(s| you)|thx|ty|that worked|it worked|works now|working now|fixed|sorted|solved|resolved|that did it|perfect|got it)\b|👍|🙏", re.I)
_NEG = re.compile(r"\b(still|didn.?t work|doesn.?t work|does not work|not work(ing)?|no luck|same (issue|problem|thing)|already (tried|did|done)|useless|worse|nothing (changed|happened))\b", re.I)


def outcome_from_followup(followup: str | None) -> str:
    """'positive' | 'negative' | 'mixed' | 'none' based on what the customer said after the brand reply."""
    if not followup:
        return "none"
    pos, neg = bool(_POS.search(followup)), bool(_NEG.search(followup))
    if pos and neg:
        return "mixed"
    if pos:
        return "positive"
    if neg:
        return "negative"
    return "none"
