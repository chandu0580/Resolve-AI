"""Conversation acts recognised deterministically: a bare greeting, thanks, a bare acknowledgement, and an explicit request for a
person. They let the policy answer "hi" with a greeting instead of a troubleshooting questionnaire, and route "can I talk to a
human" to a person under its own reason.

Matching runs on resolveai.trust.normalize keys (NFKC, format characters removed, casefolded) with punctuation and emoji removed,
so "hi", "HI", "Hi!!" and a full-width "Ｈｉ" are the same act. The customer's message is never modified. A greeting followed by
a request ("hi, my iphone won't turn on") is not a greeting: only a message that contains nothing but a greeting is.
"""
from __future__ import annotations

import re
import unicodedata

from resolveai.trust.normalize import normalize_for_matching

_NON_WORD = re.compile(r"[^\w\s']+")          # punctuation and emoji (\w is Unicode-aware, so accented letters stay)
_WS = re.compile(r"\s+")
_ADDRESSEE = r"(?:there|all|everyone|team|folks|guys|friends?|bro|bruh|mate|dude|buddy|man|sir|ma'?am|apple|apple ?support|resolve ?ai|support)"
GREETING = re.compile(
    rf"^(?:{_ADDRESSEE} )?(?:hi+|hello+|hey+|hiya|howdy|yo|greetings|good (?:morning|afternoon|evening|day))(?: {_ADDRESSEE})*$")
GRATITUDE = re.compile(
    r"^(?:thank(?:s| you| u)?(?: (?:so|very) much| a lot| again)?|thx|ty|cheers|much appreciated|appreciate it|great|perfect|cool|awesome|got it|will do|"
    r"that (?:worked|fixed it|helped))(?: (?:thanks|thank you))?$")
ACKNOWLEDGEMENT = re.compile(r"^(?:ok(?:ay)?|k|yes|yeah|yep|no|nope|done|sent|sure)$")
HUMAN_REQUEST = re.compile(
    r"\b(?:talk|speak|chat) (?:to|with) (?:a |an |some )?(?:real |live |actual )?(?:human|person|agent|representative|rep|advisor|someone|somebody|specialist|support)\b"
    r"|\b(?:connect|transfer|put) me (?:to|through to|with) (?:a |an )?(?:human|person|agent|representative|someone|support|customer support|helpdesk)\b"
    r"|\b(?:customer support|live agent|helpdesk)\b"
    r"|\b(?:real|live|actual) (?:human|person|agent)\b"
    r"|\b(?:talk|speak) to someone\b"
    r"|\b(?:i )?(?:want|need) (?:a |an )?(?:human|person|real person|live agent)\b"
    r"|\b(?:don'?t|do not) want (?:a |to talk to a )?bot\b"
    r"|\b(?:human|person|representative|support) please\b"
    r"|^(?:human|agent|representative|operator|support)(?: please)?$",
    re.I)


def is_non_latin_script(text: str | None, *, min_letters: int = 6, share: float = 0.5) -> bool:
    """True when most of the message's letters are outside the Latin script (Japanese, Arabic, Hindi, Chinese, Greek, ...).

    The word tokenizer only sees Latin words, so such a message otherwise looks like "no issue stated" and gets an English
    clarifying question. Script is a property of the characters, not a guess, so this is a deterministic rule rather than a
    model prediction; the classifier still handles Latin-script languages (Spanish, French, Portuguese) on its own.
    """
    letters = [c for c in unicodedata.normalize("NFKC", text or "") if c.isalpha()]
    if len(letters) < min_letters:
        return False
    latin = sum(1 for c in letters if "LATIN" in unicodedata.name(c, ""))
    return (len(letters) - latin) / len(letters) >= share


def act_key(text: str | None) -> str:
    """The matching key: normalised, punctuation and emoji removed, whitespace collapsed."""
    return _WS.sub(" ", _NON_WORD.sub(" ", normalize_for_matching(text))).strip()


def is_greeting_only(text: str | None) -> bool:
    return bool(GREETING.match(act_key(text)))


def is_gratitude(text: str | None) -> bool:
    return bool(GRATITUDE.match(act_key(text)))


def is_acknowledgement(text: str | None) -> bool:
    return bool(ACKNOWLEDGEMENT.match(act_key(text)))


def requests_human(text: str | None) -> bool:
    return bool(HUMAN_REQUEST.search(act_key(text)))
