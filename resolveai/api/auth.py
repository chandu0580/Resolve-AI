"""API authentication boundary: static bearer tokens with two scopes. Deliberately small (no identity platform).

  RESOLVEAI_API_TOKEN     full access: `resolve` + `read`   (the operator console's server-side forwarder uses this one)
  RESOLVEAI_READ_TOKEN    read only: traces, configuration, evaluation, demo scenarios; POST /resolve answers 403

Callers send `Authorization: Bearer <token>` (or `X-API-Key: <token>`). Tokens are compared as SHA-256 digests with
`hmac.compare_digest` against every configured digest (no early exit), are never logged, never stored in traces and never
returned by any endpoint. Missing or wrong credentials -> 401 `unauthorized` (one message for both, so the API is not an
oracle for which part was wrong); a valid token without the needed scope -> 403 `forbidden`.

Authentication is required in the `production` profile (startup fails without a token) and can be explicitly disabled in
development, demo and test, where every request acts as the `anonymous` principal with all scopes.
"""
from __future__ import annotations

import hashlib
import hmac
from collections.abc import Mapping
from dataclasses import dataclass, field

MIN_TOKEN_CHARS = 32
SCOPE_RESOLVE = "resolve"
SCOPE_READ = "read"


@dataclass(frozen=True)
class Principal:
    name: str
    scopes: frozenset[str]
    authenticated: bool


ANONYMOUS = Principal(name="anonymous", scopes=frozenset({SCOPE_RESOLVE, SCOPE_READ}), authenticated=False)


def _digest(token: str) -> bytes:
    return hashlib.sha256(token.encode("utf-8")).digest()


@dataclass(frozen=True)
class TokenAuthenticator:
    required: bool
    _entries: tuple[tuple[bytes, Principal], ...] = field(default_factory=tuple, repr=False)

    @classmethod
    def from_env(cls, required: bool, environ: Mapping[str, str]) -> TokenAuthenticator:
        entries = []
        for var, name, scopes in (("RESOLVEAI_API_TOKEN", "operator", {SCOPE_RESOLVE, SCOPE_READ}), ("RESOLVEAI_READ_TOKEN", "reader", {SCOPE_READ})):
            token = (environ.get(var) or "").strip()
            if not token:
                continue
            if len(token) < MIN_TOKEN_CHARS:
                raise ValueError(f"{var} must be at least {MIN_TOKEN_CHARS} characters")   # the value itself is never echoed
            entries.append((_digest(token), Principal(name=name, scopes=frozenset(scopes), authenticated=True)))
        if required and not any(SCOPE_RESOLVE in p.scopes for _, p in entries):
            raise ValueError("authentication is required in this profile: set RESOLVEAI_API_TOKEN (at least 32 characters)")
        return cls(required=required, _entries=tuple(entries))

    @property
    def configured(self) -> bool:
        return bool(self._entries)

    def authenticate(self, token: str | None) -> Principal | None:
        """The principal for a presented token, or None. Every digest is compared, so timing does not reveal a partial match."""
        if not token:
            return None
        presented = _digest(token)
        match = None
        for digest, principal in self._entries:
            if hmac.compare_digest(presented, digest) and match is None:
                match = principal
        return match


def presented_token(headers: Mapping[str, str]) -> str | None:
    auth = headers.get("authorization") or ""
    if auth[:7].lower() == "bearer ":
        return auth[7:].strip() or None
    key = headers.get("x-api-key")
    return key.strip() if key else None
