"""API runtime settings: four profiles (development, demo, test, production) overridden by RESOLVEAI_* environment variables.

Secrets never live here. The LLM key stays in resolveai.config (environment / gitignored .env) and API tokens are read by
resolveai.api.auth; neither is ever returned by any endpoint. Wildcard CORS is rejected in every profile, and the
production profile cannot run without authentication.
"""
from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from resolveai import config

PROFILES: dict[str, dict] = {
    "development": {"cors_origins": ("http://localhost:3000", "http://127.0.0.1:3000"), "use_llm": True, "write_traces": True, "trace_dir": config.ROOT / "traces",
                    "rate_limit_per_minute": 60, "read_rate_limit_per_minute": 600, "max_queue": 4, "eager_load": True, "expose_docs": True, "auth_required": False},
    "demo": {"cors_origins": ("http://localhost:3000",), "use_llm": True, "write_traces": True, "trace_dir": config.ROOT / "traces" / "demo",
             "rate_limit_per_minute": 30, "read_rate_limit_per_minute": 300, "max_queue": 2, "eager_load": True, "expose_docs": True, "auth_required": False},
    "test": {"cors_origins": ("http://localhost:3000",), "use_llm": False, "write_traces": True, "trace_dir": config.CACHE_DIR / "test_traces",
             "rate_limit_per_minute": 10_000, "read_rate_limit_per_minute": 10_000, "max_queue": 8, "eager_load": False, "expose_docs": True, "auth_required": False},
    # A single-process reference deployment behind the console's server-side forwarder: auth on, docs off, tighter limits.
    "production": {"cors_origins": (), "use_llm": True, "write_traces": True, "trace_dir": config.ROOT / "traces",
                   "rate_limit_per_minute": 30, "read_rate_limit_per_minute": 300, "max_queue": 4, "eager_load": True, "expose_docs": False, "auth_required": True,
                   "request_budget_s": 45.0, "queue_timeout_s": 20.0},
}
_BOOLS = {"RESOLVEAI_USE_LLM": "use_llm", "RESOLVEAI_WRITE_TRACES": "write_traces", "RESOLVEAI_EAGER_LOAD": "eager_load", "RESOLVEAI_EXPOSE_DOCS": "expose_docs",
          "RESOLVEAI_AUTH_REQUIRED": "auth_required"}
_INTS = {"RESOLVEAI_RATE_LIMIT_PER_MINUTE": "rate_limit_per_minute", "RESOLVEAI_READ_RATE_LIMIT_PER_MINUTE": "read_rate_limit_per_minute",
         "RESOLVEAI_AUTH_FAILURES_PER_MINUTE": "auth_failures_per_minute", "RESOLVEAI_MAX_QUEUE": "max_queue", "RESOLVEAI_MAX_BODY_BYTES": "max_body_bytes",
         "RESOLVEAI_MAX_MESSAGE_CHARS": "max_message_chars", "RESOLVEAI_MAX_TURN_CHARS": "max_turn_chars", "RESOLVEAI_MAX_TURNS": "max_turns",
         "RESOLVEAI_MAX_TOTAL_CHARS": "max_total_chars"}
_FLOATS = {"RESOLVEAI_REQUEST_BUDGET_S": "request_budget_s", "RESOLVEAI_QUEUE_TIMEOUT_S": "queue_timeout_s"}


@dataclass(frozen=True)
class ApiSettings:
    env: str = "development"
    cors_origins: tuple[str, ...] = ("http://localhost:3000",)
    use_llm: bool = True
    write_traces: bool = True
    trace_dir: Path = config.ROOT / "traces"
    auth_required: bool = False              # production forces True (see __post_init__)
    rate_limit_per_minute: int = 60          # POST /resolve, per principal (or client address when auth is off); in-process sliding window
    read_rate_limit_per_minute: int = 600    # every other authenticated endpoint, same key
    auth_failures_per_minute: int = 30       # failed authentication attempts per client address before 429
    max_queue: int = 4                       # requests allowed to wait for the (single) agent execution slot
    queue_timeout_s: float = 30.0            # longest a request waits for the slot before 429 agent_busy
    request_budget_s: float = 60.0           # wall-clock budget for one agent execution; model calls never start past it
    eager_load: bool = True                  # load the agent in a background thread at startup
    expose_docs: bool = True                 # /docs and /openapi.json
    max_body_bytes: int = 64_000             # rejected before JSON parsing
    max_message_chars: int = 2_000           # the current customer message
    max_turn_chars: int = 2_000              # any earlier turn
    max_turns: int = 20                      # conversation length, current message included
    max_total_chars: int = 12_000            # all turns together

    def __post_init__(self) -> None:
        if self.env not in PROFILES:
            raise ValueError(f"RESOLVEAI_ENV must be one of {sorted(PROFILES)}")
        if self.env == "production" and not self.auth_required:
            raise ValueError("the production profile requires authentication; RESOLVEAI_AUTH_REQUIRED cannot be false")
        for origin in self.cors_origins:
            if origin == "*" or "*" in origin:
                raise ValueError("wildcard CORS origins are not allowed; list the frontend origin explicitly")
            if not origin.startswith(("http://", "https://")):
                raise ValueError(f"CORS origin must be an http(s) URL: {origin!r}")
        for name in ("rate_limit_per_minute", "read_rate_limit_per_minute", "auth_failures_per_minute", "max_queue", "max_body_bytes", "max_message_chars",
                     "max_turn_chars", "max_turns", "max_total_chars"):
            if int(getattr(self, name)) <= 0:
                raise ValueError(f"{name} must be positive")
        for name in ("request_budget_s", "queue_timeout_s"):
            if not float(getattr(self, name)) > 0:
                raise ValueError(f"{name} must be positive")

    @classmethod
    def for_profile(cls, env: str, **overrides) -> ApiSettings:
        env = (env or "").strip().casefold()   # profile names are canonical lower case: "Production" and "PRODUCTION" mean production
        if env not in PROFILES:
            raise ValueError(f"RESOLVEAI_ENV must be one of {sorted(PROFILES)}")
        return cls(env=env, **{**PROFILES[env], **overrides})

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> ApiSettings:
        e = os.environ if environ is None else environ
        over: dict = {}
        if e.get("RESOLVEAI_CORS_ORIGINS"):
            over["cors_origins"] = tuple(x.strip() for x in e["RESOLVEAI_CORS_ORIGINS"].split(",") if x.strip())
        if e.get("RESOLVEAI_TRACE_DIR"):
            over["trace_dir"] = Path(e["RESOLVEAI_TRACE_DIR"])
        for key, field_name in _BOOLS.items():
            if key in e:
                v = e[key].strip().lower()
                if v not in ("1", "0", "true", "false", "yes", "no"):
                    raise ValueError(f"{key} must be a boolean")
                over[field_name] = v in ("1", "true", "yes")
        for key, field_name in _INTS.items():
            if key in e:
                over[field_name] = int(e[key])
        for key, field_name in _FLOATS.items():
            if key in e:
                over[field_name] = float(e[key])
        return cls.for_profile(e.get("RESOLVEAI_ENV", "development"), **over)

    def public_view(self) -> dict:
        """Safe to return from /config: no secrets, no tokens, no absolute filesystem paths."""
        try:
            trace_dir = str(self.trace_dir.resolve().relative_to(config.ROOT.resolve())).replace("\\", "/")
        except ValueError:
            trace_dir = "(outside repository)"
        return {"env": self.env, "cors_origins": list(self.cors_origins), "use_llm": self.use_llm, "write_traces": self.write_traces, "trace_store": {"kind": "jsonl files", "dir": trace_dir},
                "auth": {"required": self.auth_required, "scheme": "bearer token"},
                "rate_limit_per_minute": self.rate_limit_per_minute, "read_rate_limit_per_minute": self.read_rate_limit_per_minute, "rate_limit_scope": "process-local (not shared across processes)",
                "max_queue": self.max_queue, "queue_timeout_s": self.queue_timeout_s, "request_budget_s": self.request_budget_s, "docs_enabled": self.expose_docs,
                "limits": {"max_body_bytes": self.max_body_bytes, "max_message_chars": self.max_message_chars, "max_turn_chars": self.max_turn_chars,
                           "max_turns": self.max_turns, "max_total_chars": self.max_total_chars}}
