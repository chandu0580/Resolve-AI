"""Prompt-injection boundary. Part of the Trust layer.

Trust model (the three channels never mix):
  CUSTOMER INPUT  untrusted data. It is classified, retrieved on and quoted to the LLM as data; it is never an instruction.
  SYSTEM/POLICY   code: the deterministic policy, the output gate and the prompts. Customer text cannot change them.
  EVIDENCE        only what the retrieval index returns from the historical knowledge base. Text the customer labels as
                  "evidence" is still customer input.

This module adds an explicit, deterministic detector for messages that try to address the model or its configuration.
A detection is a hard block: the second-opinion and risk LLM calls are skipped, nothing is drafted, and the case goes to a
human with reason `prompt_injection`. Patterns are deliberately narrow (phrases that only make sense as attempts to
instruct an AI system) and their false-positive rate on the historical customer messages is measured in
artifacts/phase7/injection_false_positives.json.

Undetected attempts are still contained by the architecture: the policy is code, evidence comes only from the index, a
reply needs sufficient evidence + a passing verifier + the output gate, and the verifier blocks internal/metadata terms.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from resolveai.trust.normalize import normalize_for_matching

PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("override_instructions", re.compile(
        r"\b(ignore|disregard|forget|override|bypass)\s+(all\s+|any\s+|the\s+|your\s+|my\s+)?(previous|prior|above|earlier|preceding|system|original|your|all)\s+"
        r"(instructions?|prompts?|rules|guidelines|directives|messages?)\b|\b(ignore|disregard)\s+(everything|all)\s+(above|before)\b", re.I)),
    ("reveal_configuration", re.compile(r"\b(system|hidden|developer|initial|internal)\s+(prompts?|instructions?|configuration|config|policies)\b", re.I)),
    ("role_override", re.compile(
        r"\b(you are now|from now on,? you|act as|pretend (to be|you are))\b[^.!?\n]{0,40}\b(admin|administrator|developer|root|system|unrestricted|jailbroken|dan)\b", re.I)),
    ("privileged_command", re.compile(r"\b(admin(istrator)?|root|sudo|system)\s+(command|override)s?\b|\b(admin|god)\s+mode\b|^\s*\[?(system|admin|developer|assistant)\]?\s*:", re.I | re.M)),
    ("evidence_spoofing", re.compile(r"\b(use|trust|treat|accept)\b[^.!?\n]{0,30}\b(evidence|knowledge base|source documents?)\b|\[E\d{1,2}\]", re.I)),
    ("secret_request", re.compile(r"\b(api[ _-]?keys?|access tokens?|secret keys?|environment variables|internal (data|information|notes|tools|documents))\b", re.I)),
]


@dataclass(frozen=True)
class InjectionCheck:
    detected: bool
    patterns: list[str] = field(default_factory=list)


def detect_injection(text: str) -> InjectionCheck:
    """Names of the matched pattern families (never the matched text, which stays out of traces).

    Matching runs on a comparison key: NFKC (full-width letters fold to ASCII) with format characters removed (a zero-width space
    cannot split "ignore"); every pattern is case-insensitive. The text itself is not changed."""
    key = normalize_for_matching(text, fold_case=False, collapse_whitespace=False)   # line breaks kept: one pattern is line-anchored
    hits = [name for name, pat in PATTERNS if pat.search(key)]
    return InjectionCheck(detected=bool(hits), patterns=hits)
