"""LLM client tests. No network: FakeProvider only. Live calls are integration tests (RESOLVEAI_INTEGRATION=1)."""
import json
import os
import subprocess
import sys

import pytest
from pydantic import BaseModel

from resolveai.llm import DiskCache, FakeProvider, LLMClient, LLMUnavailable, cache_key

MSGS = [{"role": "system", "content": "s"}, {"role": "user", "content": "classify: battery dies"}]
PARAMS = {"temperature": 0.0, "max_tokens": 700, "json_mode": True}


def test_cache_key_is_sha256_and_stable():
    k = cache_key("glm-5.2", "v1", MSGS, PARAMS)
    assert len(k) == 64 and k == cache_key("glm-5.2", "v1", MSGS, dict(PARAMS))
    assert k != cache_key("glm-5.2", "v2", MSGS, PARAMS) and k != cache_key("other", "v1", MSGS, PARAMS)


def test_cache_key_identical_across_processes_with_different_hash_seeds():
    code = "from resolveai.llm import cache_key; print(cache_key('m','v',[{'role':'user','content':'x'}],{'t':0}))"
    outs = set()
    for seed in ("0", "12345", "random"):
        env = {**os.environ, "PYTHONHASHSEED": seed}
        outs.add(subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, check=True).stdout.strip())
    assert len(outs) == 1, "cache key must not depend on the process hash seed"


class Out(BaseModel):
    intent: str
    confidence: float


def test_client_caches_and_counts_usage(tmp_path):
    prov = FakeProvider(default='{"intent": "battery_power", "confidence": 0.9}')
    c = LLMClient(provider=prov, model="fake", cache=DiskCache(tmp_path))
    a = c.structured(MSGS, Out, prompt_version="v1")
    b = c.structured(MSGS, Out, prompt_version="v1")
    assert a == b == Out(intent="battery_power", confidence=0.9)
    assert prov.calls == 1 and c.usage.calls == 2 and c.usage.cache_hits == 1 and c.usage.live_calls == 1


def test_client_retries_once_then_raises_unavailable(tmp_path):
    prov = FakeProvider(default="{}", fail_times=2)
    c = LLMClient(provider=prov, model="fake", cache=DiskCache(tmp_path), max_retries=1)
    with pytest.raises(LLMUnavailable):
        c.complete(MSGS, prompt_version="v1")
    assert prov.calls == 2 and c.usage.errors == 2


def test_structured_retries_with_validation_error_then_falls_back(tmp_path):
    # first answer lacks 'confidence'; the corrective retry (prompt contains 'Your JSON was invalid') returns a valid one
    prov = FakeProvider(responses={"Your JSON was invalid": '{"intent": "other", "confidence": 0.5}'}, default='{"intent": "other"}')
    c = LLMClient(provider=prov, model="fake", cache=DiskCache(tmp_path))
    assert c.structured(MSGS, Out, prompt_version="v1") == Out(intent="other", confidence=0.5)
    assert prov.calls == 2
    # still invalid after the retry -> LLMUnavailable so the caller falls back deterministically
    prov2 = FakeProvider(default="not json at all")
    c2 = LLMClient(provider=prov2, model="fake", cache=DiskCache(tmp_path / "b"))
    with pytest.raises(LLMUnavailable):
        c2.structured(MSGS, Out, prompt_version="v1")
    assert c2.usage.fallbacks == 1


def test_client_refuses_unredacted_pii(tmp_path):
    c = LLMClient(provider=FakeProvider(), model="fake", cache=DiskCache(tmp_path))
    with pytest.raises(ValueError):
        c.complete([{"role": "user", "content": "my email is a@b.com"}], prompt_version="v1")
    c.complete([{"role": "user", "content": "my email is <EMAIL>"}], prompt_version="v1")  # redacted is fine


def test_extract_json_tolerates_prose_wrapping(tmp_path):
    prov = FakeProvider(default='Sure! {"intent": "other", "confidence": 0.4} hope that helps')
    c = LLMClient(provider=prov, model="fake", cache=DiskCache(tmp_path))
    assert c.structured(MSGS, Out, prompt_version="v1").confidence == 0.4


@pytest.mark.integration
@pytest.mark.skipif(os.getenv("RESOLVEAI_INTEGRATION") != "1", reason="live LLM call; set RESOLVEAI_INTEGRATION=1")
def test_live_endpoint_returns_json():
    from resolveai.llm import OpenAICompatibleProvider

    c = LLMClient(provider=OpenAICompatibleProvider())
    out = c.complete([{"role": "user", "content": 'Return JSON {"ok": true}'}], prompt_version="smoke", use_cache=False)
    assert json.loads(out.content).get("ok") is True
