"""Canonical text normalization for MATCHING only.

The customer's original text is never replaced by these forms: it stays the input to redaction, classification, retrieval,
display and the audit trail. These helpers produce comparison keys so that the same words match however they are typed:
- NFKC folds compatibility forms (full-width letters, ligatures, super/subscripts) to their canonical characters;
- format characters (Unicode category Cf: zero-width space and joiners, soft hyphen, byte-order mark, bidirectional marks) are
  removed, so they cannot split a keyword ("ig​nore");
- casefold(), not lower(), makes the comparison case-insensitive across scripts ("STRASSE" and "straße" match);
- runs of whitespace collapse to one space.

Where case carries meaning the comparison stays exact: trace ids (canonical lowercase hex, normalised at the API boundary),
enum codes, and the upper-case serial pattern in trust/pii.py. A case-insensitive serial pattern was measured on the knowledge
base: it newly matched 157 of 20,000 customer messages, almost all product hashtags ("iphone7plus", "ios11update"), so it would
redact product names rather than identifiers.
"""
from __future__ import annotations

import re
import unicodedata

_WS = re.compile(r"\s+")


def strip_format_chars(text: str) -> str:
    return "".join(ch for ch in text if unicodedata.category(ch) != "Cf")


def normalize_for_matching(text: str | None, *, fold_case: bool = True, collapse_whitespace: bool = True) -> str:
    """NFKC, format characters removed, optionally casefolded, whitespace optionally collapsed. A comparison key, never display text.

    Keep `collapse_whitespace=False` for patterns anchored to line starts (the injection detector's fake "system:" line)."""
    t = strip_format_chars(unicodedata.normalize("NFKC", text or ""))
    if fold_case:
        t = t.casefold()
    return _WS.sub(" ", t).strip() if collapse_whitespace else t
