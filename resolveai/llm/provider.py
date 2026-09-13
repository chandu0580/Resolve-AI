"""LLM provider abstraction.

- `LLMProvider` is the contract. `OpenAICompatibleProvider` talks to any OpenAI-compatible endpoint (GLM via the
  configured proxy today; swapping provider = changing .env). `FakeProvider` is for tests: no network, ever.
- `LLMClient` adds what the agent needs on top of a provider: deterministic SHA-256 caching, a hard wall-clock timeout per
  call, one bounded retry, an optional per-request `Deadline`, structured-output validation against a pydantic schema with
  one corrective retry, PII guard on input, and usage accounting (calls, retries, timeouts, errors, tokens, cache hits). It
  raises `LLMUnavailable` with a failure `kind` so callers apply a deterministic fallback and traces can classify the failure.

Phase 9 hardening: the OpenAI SDK's own retries are disabled (its default of 2 silently multiplied every timeout, so one call
could block for minutes); the client enforces the timeout itself on a worker thread instead of trusting the transport's
per-read timeout; and once the request budget is spent no new call is started.
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel, ValidationError

from resolveai import config
from resolveai.llm.cache import DiskCache, cache_key
from resolveai.trust.pii import contains_unredacted_pii

T = TypeVar("T", bound=BaseModel)

FAILURE_KINDS = ("timeout", "transport", "invalid_output", "budget_exhausted", "not_configured", "no_input")
MIN_CALL_SECONDS = 2.0   # a model call is not started with less than this left in the request budget
_EXECUTOR = cf.ThreadPoolExecutor(max_workers=8, thread_name_prefix="resolveai-llm")


class LLMUnavailable(RuntimeError):
    """Raised after timeout/retry/validation exhaustion. The caller must fall back deterministically. `kind` is one of FAILURE_KINDS."""

    def __init__(self, message: str, kind: str = "transport"):
        super().__init__(message)
        self.kind = kind


class Deadline:
    """Wall-clock budget for one request: each model call gets min(per-call timeout, remaining) and none starts past it."""

    def __init__(self, seconds: float, clock=time.monotonic):
        self.seconds, self._clock = float(seconds), clock
        self._expires = clock() + float(seconds)

    def remaining(self) -> float:
        return self._expires - self._clock()

    @property
    def expired(self) -> bool:
        return self.remaining() <= 0


@dataclass
class Completion:
    content: str
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: float = 0
    cached: bool = False


class LLMProvider(Protocol):
    name: str

    def complete(self, model: str, messages: list[dict[str, str]], *, temperature: float, max_tokens: int, json_mode: bool, timeout_s: float) -> Completion: ...


class OpenAICompatibleProvider:
    name = "openai_compatible"

    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        from openai import OpenAI  # imported lazily so unit tests never need the SDK on the path

        key = api_key if api_key is not None else config.LLM_API_KEY
        if not key:
            raise LLMUnavailable("LLM_API_KEY is not set (copy .env.example to .env)", kind="not_configured")
        # max_retries=0: LLMClient owns the (single, bounded) retry. The SDK default of 2 hid up to two extra full timeouts per attempt.
        self._client = OpenAI(api_key=key, base_url=base_url or config.LLM_BASE_URL, max_retries=0)

    def complete(self, model, messages, *, temperature, max_tokens, json_mode, timeout_s) -> Completion:
        kw: dict[str, Any] = dict(model=model, messages=messages, temperature=temperature, max_tokens=max_tokens, timeout=timeout_s)
        if json_mode:
            kw["response_format"] = {"type": "json_object"}
        t0 = time.perf_counter()
        r = self._client.chat.completions.create(**kw)
        usage = getattr(r, "usage", None)
        return Completion(
            content=r.choices[0].message.content or "",
            tokens_in=getattr(usage, "prompt_tokens", 0) or 0,
            tokens_out=getattr(usage, "completion_tokens", 0) or 0,
            latency_ms=(time.perf_counter() - t0) * 1000,
        )


class FakeProvider:
    """Deterministic provider for tests. `responses` maps a substring of the last user message to content. `sleep_s` simulates a
    slow model; `fail_times` raises `fail_with` for the first N calls."""
    name = "fake"

    def __init__(self, responses: dict[str, str] | None = None, default: str = "{}", fail_times: int = 0, latency_ms: float = 1.0,
                 sleep_s: float = 0.0, fail_with: type[Exception] = TimeoutError):
        self.responses, self.default, self.fail_times, self.latency_ms = responses or {}, default, fail_times, latency_ms
        self.sleep_s, self.fail_with = sleep_s, fail_with
        self.calls = 0

    def complete(self, model, messages, *, temperature, max_tokens, json_mode, timeout_s) -> Completion:
        self.calls += 1
        if self.sleep_s:
            time.sleep(self.sleep_s)
        if self.fail_times > 0:
            self.fail_times -= 1
            raise self.fail_with("simulated provider failure")
        last = messages[-1]["content"]
        content = next((v for k, v in self.responses.items() if k in last), self.default)
        return Completion(content=content, tokens_in=len(last) // 4, tokens_out=len(content) // 4, latency_ms=self.latency_ms)


@dataclass
class Usage:
    calls: int = 0
    live_calls: int = 0
    cache_hits: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: float = 0
    errors: int = 0             # failed provider attempts (any cause)
    fallbacks: int = 0          # structured output still invalid after the corrective retry
    cached_tokens_in: int = 0    # tokens the cached completions consumed when they were live (for cost accounting of cache-served runs)
    cached_tokens_out: int = 0
    retries: int = 0            # provider attempts after the first one
    timeouts: int = 0           # attempts that hit the wall-clock limit
    budget_exhausted: int = 0   # calls refused because the request budget was spent

    def as_dict(self) -> dict[str, float]:
        return self.__dict__.copy()


def _is_timeout(e: Exception) -> bool:
    return isinstance(e, TimeoutError | cf.TimeoutError) or "timeout" in type(e).__name__.lower()


@dataclass
class LLMClient:
    provider: LLMProvider
    model: str = config.LLM_MODEL
    cache: DiskCache | None = field(default_factory=DiskCache)
    timeout_s: float = config.LLM_TIMEOUT_S
    max_retries: int = config.LLM_MAX_RETRIES
    usage: Usage = field(default_factory=Usage)
    deadline: Deadline | None = None        # set per request by the orchestrator; None = only the per-call timeout applies
    last_failure: str | None = None         # kind of the most recent failure, for trace classification

    def _call_timeout(self) -> float:
        if self.deadline is None:
            return self.timeout_s
        remaining = self.deadline.remaining()
        if remaining < MIN_CALL_SECONDS:
            self.usage.budget_exhausted += 1
            self.last_failure = "budget_exhausted"
            raise LLMUnavailable(f"request time budget of {self.deadline.seconds:g} s exhausted", kind="budget_exhausted")
        return min(self.timeout_s, remaining)

    def complete(self, messages: list[dict[str, str]], *, prompt_version: str, temperature: float = config.LLM_TEMPERATURE,
                 max_tokens: int = config.LLM_MAX_TOKENS, json_mode: bool = True, use_cache: bool = True) -> Completion:
        for m in messages:
            if contains_unredacted_pii(m.get("content", "")):
                raise ValueError("refusing to send unredacted PII to the LLM; redact first")
        params = {"temperature": temperature, "max_tokens": max_tokens, "json_mode": json_mode}
        key = cache_key(self.model, prompt_version, messages, params)
        self.usage.calls += 1
        if use_cache and self.cache is not None and (rec := self.cache.get(key)) is not None:
            self.usage.cache_hits += 1
            self.usage.cached_tokens_in += int(rec.get("tokens_in", 0) or 0)
            self.usage.cached_tokens_out += int(rec.get("tokens_out", 0) or 0)
            return Completion(**rec, cached=True)
        last_err: Exception | None = None
        last_kind = "transport"
        for attempt in range(self.max_retries + 1):
            timeout = self._call_timeout()
            if attempt:
                self.usage.retries += 1
            try:
                fut = _EXECUTOR.submit(self.provider.complete, self.model, messages, temperature=temperature, max_tokens=max_tokens, json_mode=json_mode, timeout_s=timeout)
                try:
                    c = fut.result(timeout=timeout)
                except cf.TimeoutError:
                    fut.cancel()   # a call already running cannot be interrupted; its result is discarded
                    raise TimeoutError(f"no model response within {timeout:.1f} s") from None
                self.usage.live_calls += 1
                self.usage.tokens_in += c.tokens_in
                self.usage.tokens_out += c.tokens_out
                self.usage.latency_ms += c.latency_ms
                if self.cache is not None and use_cache:
                    self.cache.put(key, {"content": c.content, "tokens_in": c.tokens_in, "tokens_out": c.tokens_out, "latency_ms": c.latency_ms})
                return c
            except Exception as e:  # noqa: BLE001 — any transport error counts; the caller gets a typed exception
                last_err = e
                self.usage.errors += 1
                if _is_timeout(e):
                    self.usage.timeouts += 1
                    last_kind = "timeout"
                else:
                    last_kind = "transport"
                if attempt < self.max_retries:
                    backoff = min(2 ** attempt, 4) * (0.01 if isinstance(self.provider, FakeProvider) else 1.0)
                    if self.deadline is not None:
                        backoff = min(backoff, max(0.0, self.deadline.remaining() - MIN_CALL_SECONDS))
                    time.sleep(backoff)
        self.last_failure = last_kind
        raise LLMUnavailable(f"{type(last_err).__name__}: {str(last_err)[:200]}", kind=last_kind)

    def structured(self, messages: list[dict[str, str]], schema: type[T], *, prompt_version: str, **kw: Any) -> T:
        """JSON-mode call validated against `schema`. One bounded corrective retry, then LLMUnavailable so the caller
        applies its deterministic fallback. Phase-5 hardening (found by the drafting A/B): (a) the retry shows an EXAMPLE
        SHAPE of the JSON, not the JSON-schema `properties` - GLM answered the schema itself ({"reply": {"type": "string",
        ...}}); (b) when the first answer contains no JSON object at all (the completion was truncated by hidden reasoning)
        the retry drops the useless echo and raises the token cap by 50% (capped at 2000) for that one call."""
        c = self.complete(messages, prompt_version=prompt_version, json_mode=True, **kw)
        try:
            return schema.model_validate(_extract_json(c.content))
        except (ValidationError, ValueError) as first:
            shape = json.dumps(example_shape(schema))
            kw2 = dict(kw)
            if isinstance(first, ValueError) and not isinstance(first, ValidationError):   # no JSON at all: truncation
                fix = messages[:-1] + [{"role": "user", "content": messages[-1]["content"] + f"\n\nAnswer with ONLY the JSON object, nothing else, in this exact shape: {shape}"}]
                kw2["max_tokens"] = min(2000, int(kw.get("max_tokens", config.LLM_MAX_TOKENS) * 1.5))
            else:
                fix = messages + [{"role": "assistant", "content": c.content[:2000]},
                                  {"role": "user", "content": f"Your JSON was invalid: {str(first)[:300]}. Return ONLY a JSON object with real values in this exact shape: {shape}"}]
            c2 = self.complete(fix, prompt_version=prompt_version + "+fix", json_mode=True, **kw2)
            try:
                return schema.model_validate(_extract_json(c2.content))
            except (ValidationError, ValueError) as second:
                self.usage.fallbacks += 1
                self.last_failure = "invalid_output"
                raise LLMUnavailable(f"structured output invalid after retry: {str(second)[:200]}", kind="invalid_output") from second


def example_shape(schema: type[BaseModel]) -> dict[str, Any]:
    """A placeholder JSON object with one value per field, typed from the pydantic JSON schema (not the schema itself)."""
    props = schema.model_json_schema().get("properties", {})
    out: dict[str, Any] = {}
    for name, p in props.items():
        t = p.get("type") or next((a.get("type") for a in p.get("anyOf", []) if a.get("type") and a.get("type") != "null"), "string")
        out[name] = {"string": "...", "boolean": False, "integer": 0, "number": 0.0, "array": [], "object": {}}.get(t, "...")
    return out


def _extract_json(s: str) -> dict[str, Any]:
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", s, re.S)
        if not m:
            raise ValueError("no JSON object in response") from None
        return json.loads(m.group(0))
