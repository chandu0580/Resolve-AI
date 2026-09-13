"""PII detection and redaction. Part of the Trust layer.

Invariant: customer text is redacted BEFORE it is stored, embedded, sent to any LLM/API, or written to a trace.
The raw dataset is never modified; redaction happens on the copy that enters the system.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# Order matters: longer / more specific patterns first so a card number is not half-eaten by the phone rule.
PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("EMAIL", re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")),
    ("ORDER_ID", re.compile(r"\b\d{3}-\d{7}-\d{7}\b")),          # Amazon-style, appears in the data; must precede CARD
    ("CARD", re.compile(r"\b(?:\d[ -]?){13,19}\b")),
    ("LONG_ID", re.compile(r"\b(?=[A-Z0-9-]{10,}\b)(?=[A-Z0-9-]*\d)(?=[A-Z0-9-]*[A-Z])[A-Z0-9-]{10,}\b")),  # serial / IMEI / case ids
    # Phase 9 fix: the old guards (?<![\d.]) / (?![\d.]) refused a number followed by a full stop, so "call 555-123-4567." at the end of a
    # sentence was never redacted (4 processed customer messages and 4 context turns). Only a digit or ".<digit>" (a version) now blocks.
    ("PHONE", re.compile(r"(?<!\d)(?<!\d\.)(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{3}\)?[\s.-]?)\d{3}[\s.-]?\d{4}(?!\d)(?!\.\d)")),
]
TOKEN = re.compile(r"<(EMAIL|ORDER_ID|CARD|LONG_ID|PHONE)>")


@dataclass
class Redaction:
    text: str
    counts: dict[str, int] = field(default_factory=dict)

    @property
    def redacted(self) -> bool:
        return bool(self.counts)


def redact_pii(text: str) -> Redaction:
    """Replace emails, card-like numbers, order ids, long alphanumeric ids and phone numbers with <TYPE> tokens.

    Deliberately conservative: prices ($1,299), times (10:30), iOS versions (11.1.1) and short numbers are untouched.
    Known limitation: street addresses and personal names are not detected (handles are already anonymised in the
    dataset); this is stated in the evaluation docs.
    """
    if not isinstance(text, str) or not text:
        return Redaction("")
    counts: dict[str, int] = {}
    for label, pat in PATTERNS:
        text, n = pat.subn(f"<{label}>", text)
        if n:
            counts[label] = n
    return Redaction(text, counts)


def contains_unredacted_pii(text: str) -> bool:
    """Guard used by traces and LLM calls: True if any PII pattern still matches the text."""
    return any(pat.search(text or "") for _, pat in PATTERNS)


def redacted_error(exc: BaseException, limit: int = 160) -> str:
    """Exception type plus a PII-redacted, single-line, truncated message. Exception text can quote the input that caused it,
    so this is the only form in which an exception message may enter a trace or a log."""
    return f"{type(exc).__name__}: {redact_pii(str(exc)).text[:limit]}".replace("\n", " ")
