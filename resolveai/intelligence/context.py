"""Deterministic, bounded conversation-context builder.

Policy (all limits are constants below, tested in tests/test_intelligence.py):
- keep the current customer message in full (already PII-redacted upstream);
- keep at most MAX_CUSTOMER_TURNS prior customer turns and MAX_BRAND_TURNS prior brand turns, most recent first, each
  truncated to TURN_CHARS; total prior context capped at TOTAL_CHARS;
- drop prior turns that are duplicates of another kept turn or of the current message, and turns with no content tokens
  (a bare <url>, an emoji, "ok");
- the *issue text* is the most recent prior customer turn with >= MIN_ISSUE_TOKENS content tokens: it is what a short
  reply ("yes", "still happening") refers to;
- a *short reply* is a current message with < SHORT_TOKENS content tokens or matching the SHORT_REPLY patterns;
- text for classification/retrieval = current message, plus the issue text only when the current message is short;
  never the whole conversation;
- the builder refuses any turn containing unredacted PII (the guard is the same one the LLM client uses).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from resolveai.retrieval.bm25 import tokenize
from resolveai.schemas.core import ConversationContext, ConversationTurn
from resolveai.trust.pii import contains_unredacted_pii

MAX_CUSTOMER_TURNS = 2
MAX_BRAND_TURNS = 1
TURN_CHARS = 200
TOTAL_CHARS = 600
MIN_ISSUE_TOKENS = 3
SHORT_TOKENS = 4
SHORT_REPLY = re.compile(r"^\s*(yes|no|yeah|yep|nope|ok(ay)?|still (happening|not working|same|broken|nothing)|same (issue|problem|thing)|tried (that|it|everything)|"
                         r"(it |that )?(still )?(doesn.?t|didn.?t|does not|did not|won.?t) work|(it.?s |it is )?still not working|not working|nothing (changed|happened|works)|done|sent|i did|already did|no luck|same here)\b[\s.!?]*$", re.I)
UNIVERSAL_HOWTO = re.compile(
    r"\b(how (do|can|to)|how (do i|can i)|can i|where (do|is)|how to)\b|"
    r"\b(restart|force restart|turn (on|off)|enable|disable|update|screenshot|brightness|low power mode)\b",
    re.I,
)
_SIG = re.compile(r"\s*[\^/~\-]\s?[A-Z]{1,3}\s*$")


def content_tokens(text: str) -> int:
    return sum(1 for t in tokenize(text) if not t.startswith("<"))


def parse_context(raw: str | None) -> ConversationContext:
    """Parse the dataset's 'customer: ...\\nbrand: ...' context column into turns (oldest first)."""
    turns: list[ConversationTurn] = []
    for line in (raw or "").splitlines():
        m = re.match(r"^(customer|brand):\s*(.*)$", line.strip(), re.I)
        if m:
            turns.append(ConversationTurn(role=m.group(1).lower(), text=m.group(2).strip()))
    return ConversationContext(turns=turns)


@dataclass
class ContextBundle:
    current: str
    prior_customer: list[str] = field(default_factory=list)   # most recent first
    prior_brand: list[str] = field(default_factory=list)      # most recent first
    position: int = 0                                          # number of prior turns in the thread (before bounding)
    issue_text: str = ""
    is_short_reply: bool = False
    insufficient_context: bool = False                         # short reply and no issue text available
    truncated: bool = False
    text_for_classification: str = ""
    text_for_retrieval: str = ""

    @property
    def used_context(self) -> bool:
        return bool(self.issue_text) and self.text_for_classification != self.current


def _norm(t: str) -> str:
    return re.sub(r"\s+", " ", t.lower()).strip()


def build_context(current: str, context: ConversationContext | None = None) -> ContextBundle:
    current = _SIG.sub("", (current or "").strip())
    if contains_unredacted_pii(current):
        raise ValueError("context builder received unredacted PII in the current message")
    turns = list(context.turns) if context else []
    for t in turns:
        if contains_unredacted_pii(t.text):
            raise ValueError("context builder received unredacted PII in a prior turn")
    seen = {_norm(current)}
    cust, brand, truncated = [], [], False
    budget = TOTAL_CHARS
    for t in reversed(turns):  # most recent first
        text = _SIG.sub("", t.text.strip())
        if content_tokens(text) == 0 or _norm(text) in seen:
            continue
        if len(text) > TURN_CHARS:
            text, truncated = text[:TURN_CHARS].rstrip() + "…", True
        target, cap = (cust, MAX_CUSTOMER_TURNS) if t.role == "customer" else (brand, MAX_BRAND_TURNS)
        if len(target) >= cap or budget - len(text) < 0:
            truncated = truncated or len(target) >= cap
            continue
        target.append(text)
        seen.add(_norm(text))
        budget -= len(text)
    issue = next((c for c in cust if content_tokens(c) >= MIN_ISSUE_TOKENS), "")
    is_howto = bool(UNIVERSAL_HOWTO.search(current)) and content_tokens(current) >= 2
    short = (content_tokens(current) < SHORT_TOKENS and not is_howto) or bool(SHORT_REPLY.match(current))
    insufficient = short and not issue
    if short and issue:
        cls_text = f"{issue} || reply: {current}"
        ret_text = f"{issue} {current}"
    else:
        cls_text, ret_text = current, current
    return ContextBundle(current=current, prior_customer=cust, prior_brand=brand, position=len(turns), issue_text=issue,
                         is_short_reply=short, insufficient_context=insufficient, truncated=truncated,
                         text_for_classification=cls_text, text_for_retrieval=ret_text)
