"""Phase 9 PII boundary tests. What the regex redactor must catch, what it deliberately leaves alone, and the paths customer
text travels (redaction -> model / trace / log / error). Known misses (names, street addresses, spelled-out or obfuscated
identifiers) are documented limitations, asserted here so a silent change in either direction is noticed."""
import json

import pytest

from resolveai.agent import risk
from resolveai.intelligence.context import build_context
from resolveai.llm import FakeProvider, LLMClient
from resolveai.observability import TraceRecorder
from resolveai.schemas.core import ConversationContext
from resolveai.trust.pii import contains_unredacted_pii, redact_pii, redacted_error


@pytest.mark.parametrize("text, label", [
    ("call me on 555-123-4567", "PHONE"),
    ("my number is (555) 123-4567 thanks", "PHONE"),
    ("+1 555 123 4567 is my cell", "PHONE"),
    ("text 555.123.4567 please", "PHONE"),
    ("ping jane.doe+apple@example.co.uk", "EMAIL"),
    ("order 112-3456789-1234567 never arrived", "ORDER_ID"),
    ("card 4111 1111 1111 1111 was charged", "CARD"),
    ("serial F2LXK1ABCD12 and imei 35-209900-176148-1", "LONG_ID"),
])
def test_identifiers_are_redacted_to_typed_tokens(text, label):
    r = redact_pii(text)
    assert f"<{label}>" in r.text and r.counts.get(label, 0) >= 1
    assert not contains_unredacted_pii(r.text)


def test_identifiers_embedded_in_words_and_punctuation_are_redacted():
    r = redact_pii("email:jane@example.com,phone:555-123-4567;serial=F2LXK1ABCD12!")
    assert "jane@example.com" not in r.text and "555-123-4567" not in r.text and "F2LXK1ABCD12" not in r.text
    assert r.counts == {"EMAIL": 1, "LONG_ID": 1, "PHONE": 1}


def test_repeated_identifiers_are_all_redacted_and_counted():
    r = redact_pii("555-123-4567 or 555-123-4567 or a@b.co and a@b.co")
    assert r.counts["PHONE"] == 2 and r.counts["EMAIL"] == 2 and "555" not in r.text


@pytest.mark.parametrize("text", [
    "iOS 11.1.2 on my iPhone 8",           # versions
    "it costs $1,299 at 10:30",            # prices and times
    "error 53 after 3 restarts",            # short numbers
    "build 15A372 installed",              # short build ids
    "555-12-34 is not a full number",       # malformed phone
])
def test_ordinary_numbers_are_left_alone(text):
    assert redact_pii(text).text == text


def test_redaction_tokens_are_stable_and_typed_tokens_trigger_the_private_info_rule():
    r = redact_pii("<PHONE> <EMAIL>")   # a customer typing token-like text gains nothing and loses nothing
    assert r.text == "<PHONE> <EMAIL>" and not r.counts
    b = build_context(redact_pii("call me on 555-123-4567 about my case").text, ConversationContext())
    assert "<PHONE>" in b.current and risk.extract_rules(b).needs_private_info   # the Phase 6/7 token-rule bug stays fixed


def test_adversarial_strings_do_not_crash_the_redactor():
    for text in ["", " " * 10_000, "@" * 500, "5" * 400, "<" * 200 + "PHONE" + ">" * 200, "‮5551234567‬", "a@" * 300]:
        out = redact_pii(text)
        assert isinstance(out.text, str)


@pytest.mark.parametrize("text", [
    "my name is Jane Doe",                          # names
    "I live at 221B Baker Street, London",          # street addresses
    "jane dot doe at gmail dot com",                # obfuscated email
    "five five five one two three four five six seven",   # spelled-out digits
    "serial f2lxk1abcd12",                          # lowercase serials
])
def test_known_limitations_are_explicit(text):
    """Documented in docs/PRODUCTION_READINESS.md: the redactor is pattern-based and does NOT catch these."""
    assert not redact_pii(text).counts


def test_the_model_client_refuses_raw_pii_and_the_trace_refuses_it_too():
    c = LLMClient(provider=FakeProvider(default="{}"), model="fake", cache=None)
    with pytest.raises(ValueError):
        c.complete([{"role": "user", "content": "call 555-123-4567"}], prompt_version="t")
    rec = TraceRecorder(message_id="m")
    with pytest.raises(ValueError):
        rec.event("error", "test", detail="mail jane@example.com")


def test_exception_text_is_redacted_before_it_can_reach_a_trace_or_log():
    msg = redacted_error(ValueError("bad input: jane@example.com called from 555-123-4567\nsecond line"))
    assert msg.startswith("ValueError: ") and "jane@example.com" not in msg and "555-123-4567" not in msg and "\n" not in msg
    TraceRecorder(message_id="m").event("dependency_failed", "test", error=msg)   # accepted by the trace PII guard


def test_trace_events_reject_secret_like_keys():
    rec = TraceRecorder(message_id="m")
    for key in ("api_key", "authorization", "token", "password", "reasoning"):
        with pytest.raises(ValueError):
            rec.event("error", "test", **{key: "x"})
    assert "api_key" not in json.dumps(rec.trace.model_dump())
