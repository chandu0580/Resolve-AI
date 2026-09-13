"""Phase 9 reliability tests (no knowledge base, no network): model-call time limits, bounded retries, request budgets,
failure classification, malformed model output, and the risk-flag merge used by the over-escalation experiment."""
import time

import pytest
from pydantic import BaseModel

from resolveai.agent import risk
from resolveai.intelligence.context import build_context
from resolveai.llm import Deadline, FakeProvider, LLMClient, LLMUnavailable
from resolveai.schemas.core import ConversationContext


class Out(BaseModel):
    intent: str
    confidence: float


def client(provider, **kw) -> LLMClient:
    return LLMClient(provider=provider, model="fake", cache=None, **kw)


def test_a_slow_model_call_is_cut_off_by_the_clients_own_wall_clock_limit():
    c = client(FakeProvider(default='{"intent": "other", "confidence": 0.5}', sleep_s=2.0), timeout_s=0.2, max_retries=0)
    t = time.perf_counter()
    with pytest.raises(LLMUnavailable) as e:
        c.complete([{"role": "user", "content": "hi"}], prompt_version="t")
    assert time.perf_counter() - t < 1.5, "the call must not wait for the slow provider"
    assert e.value.kind == "timeout" and c.usage.timeouts == 1 and c.last_failure == "timeout"


def test_retry_is_bounded_and_exhaustion_is_classified():
    prov = FakeProvider(default="{}", fail_times=5, fail_with=ConnectionError)
    c = client(prov, max_retries=1)
    with pytest.raises(LLMUnavailable) as e:
        c.complete([{"role": "user", "content": "hi"}], prompt_version="t")
    assert prov.calls == 2 and c.usage.retries == 1 and c.usage.errors == 2
    assert e.value.kind == "transport"


def test_timeouts_from_the_provider_are_classified_as_timeouts():
    c = client(FakeProvider(default="{}", fail_times=5, fail_with=TimeoutError), max_retries=1)
    with pytest.raises(LLMUnavailable) as e:
        c.complete([{"role": "user", "content": "hi"}], prompt_version="t")
    assert e.value.kind == "timeout" and c.usage.timeouts == 2


def test_malformed_json_after_the_corrective_retry_is_invalid_output():
    c = client(FakeProvider(default="this is not json"), max_retries=0)
    with pytest.raises(LLMUnavailable) as e:
        c.structured([{"role": "user", "content": "classify"}], Out, prompt_version="t")
    assert e.value.kind == "invalid_output" and c.usage.fallbacks == 1 and c.last_failure == "invalid_output"


def test_no_model_call_starts_once_the_request_budget_is_spent():
    now = [0.0]
    prov = FakeProvider(default='{"intent": "other", "confidence": 0.5}')
    c = client(prov, deadline=Deadline(10, clock=lambda: now[0]))
    c.complete([{"role": "user", "content": "first"}], prompt_version="t")
    now[0] = 9.5   # less than MIN_CALL_SECONDS left
    with pytest.raises(LLMUnavailable) as e:
        c.complete([{"role": "user", "content": "second"}], prompt_version="t")
    assert e.value.kind == "budget_exhausted" and prov.calls == 1 and c.usage.budget_exhausted == 1


def test_the_per_call_timeout_never_exceeds_the_remaining_budget():
    now = [0.0]
    seen = {}

    class Recorder(FakeProvider):
        def complete(self, model, messages, **kw):
            seen["timeout_s"] = kw["timeout_s"]
            return super().complete(model, messages, **kw)

    c = client(Recorder(default="{}"), timeout_s=30.0, deadline=Deadline(12, clock=lambda: now[0]))
    now[0] = 4.0
    c.complete([{"role": "user", "content": "x"}], prompt_version="t")
    assert seen["timeout_s"] == pytest.approx(8.0)


def test_the_openai_sdk_retries_are_disabled():
    pytest.importorskip("openai")
    from resolveai.llm import OpenAICompatibleProvider

    p = OpenAICompatibleProvider(api_key="test-key-not-real", base_url="http://127.0.0.1:9/v1")
    assert p._client.max_retries == 0


def test_missing_key_is_classified_not_configured(monkeypatch):
    from resolveai import config
    from resolveai.llm import OpenAICompatibleProvider

    monkeypatch.setattr(config, "LLM_API_KEY", "")
    with pytest.raises(LLMUnavailable) as e:
        OpenAICompatibleProvider(api_key=None)
    assert e.value.kind == "not_configured"


def test_risk_extraction_falls_back_to_rules_when_the_model_times_out():
    b = build_context("my iphone battery drains fast and I was charged twice", ConversationContext())
    flags, status = risk.extract(client(FakeProvider(default="{}", fail_times=9, fail_with=TimeoutError), max_retries=0), b, None)
    assert status == "fallback" and flags.source == "fallback" and flags.payment_billing_risk   # the deterministic floor still holds


def test_corroborated_soft_flags_need_the_rule_but_hard_flags_do_not():
    b = build_context("still not working", ConversationContext())
    rules = risk.extract_rules(b)
    assert not rules.repeat_contact
    loose = risk.merge(rules, {"repeat_contact", "security_concern"}, True, "", b, False)
    strict = risk.merge(rules, {"repeat_contact", "security_concern"}, True, "", b, False, corroborate=risk.SOFT_FLAGS)
    assert loose.repeat_contact and not strict.repeat_contact
    assert strict.security_concern, "corroboration never applies to hard-block flags"
    explicit = build_context("I already restarted it 3 times and it still drains", ConversationContext())
    assert risk.merge(risk.extract_rules(explicit), {"repeat_contact"}, True, "", explicit, False, corroborate=risk.SOFT_FLAGS).repeat_contact


def test_risk_v3_prompt_carries_the_guide_definitions_and_a_distinct_version():
    b = build_context("my phone is slow", ConversationContext())
    text = risk._prompt_v3(b)[1]["content"]
    assert "still not working" in text and "battery drain" in text and "do NOT count" in text
    assert risk.RISK_PROMPT_VERSION_V3 != risk.RISK_PROMPT_VERSION
