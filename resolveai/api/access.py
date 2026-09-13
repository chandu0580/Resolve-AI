"""Access control middleware: authentication, scope check and rate limiting BEFORE the request body is read or validated,
so an unauthenticated caller learns nothing from validation errors and cannot make the service parse large bodies.

  public   GET /api/v1/health, GET /api/v1/ready        (a presented valid token is still recognised; /ready shows detail only then)
  resolve  POST /api/v1/resolve                         scope `resolve`, limit `rate_limit_per_minute`
  read     every other path                             scope `read`,    limit `read_rate_limit_per_minute`

Rate limits are keyed by the authenticated principal, or by client address when authentication is disabled. Failed
authentication attempts are limited per client address. All limiters are in-process sliding windows: a multi-process or
multi-host deployment would need a shared store, which this reference implementation deliberately does not have.
"""
from __future__ import annotations

import json

from resolveai.api.auth import ANONYMOUS, SCOPE_READ, SCOPE_RESOLVE, presented_token

PUBLIC_PATHS = frozenset({"/api/v1/health", "/api/v1/ready"})


def required_scope(method: str, path: str) -> str | None:
    if path.rstrip("/") in PUBLIC_PATHS:
        return None
    if method == "POST" and path.rstrip("/") == "/api/v1/resolve":
        return SCOPE_RESOLVE
    return SCOPE_READ


class AccessControlMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("method") == "OPTIONS":
            await self.app(scope, receive, send)
            return
        state = scope["app"].state
        auth, service = state.auth, state.service
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
        client = (scope.get("client") or ("unknown", 0))[0]
        rid = scope.get("state", {}).get("request_id", "unknown")
        needed = required_scope(scope.get("method", "GET"), scope.get("path", ""))
        token = presented_token(headers)
        principal = auth.authenticate(token) if token else None

        if needed is None:
            scope.setdefault("state", {})["principal"] = principal
            await self.app(scope, receive, send)
            return
        if principal is None:
            if auth.required:
                retry = service.auth_failures.check(f"addr:{client}")
                if retry is not None:
                    await _reject(send, rid, 429, "rate_limited", f"Too many failed authentication attempts; retry in {retry} s.", {"Retry-After": str(retry)})
                    return
                await _reject(send, rid, 401, "unauthorized", "Missing or invalid credentials. Send Authorization: Bearer <token>.", {"WWW-Authenticate": 'Bearer realm="resolveai"'})
                return
            principal = ANONYMOUS
        if needed not in principal.scopes:
            await _reject(send, rid, 403, "forbidden", f"These credentials do not allow '{needed}' operations.", {})
            return
        limiter = service.limiter if needed == SCOPE_RESOLVE else service.read_limiter
        retry = limiter.check(f"principal:{principal.name}" if principal.authenticated else f"addr:{client}")
        if retry is not None:
            await _reject(send, rid, 429, "rate_limited", f"Too many requests; retry in {retry} s.", {"Retry-After": str(retry)})
            return
        scope.setdefault("state", {})["principal"] = principal
        await self.app(scope, receive, send)


async def _reject(send, rid: str, code: int, error_code: str, message: str, extra_headers: dict[str, str]) -> None:
    body = json.dumps({"error_code": error_code, "message": message, "request_id": rid, "trace_id": None, "details": None}).encode()
    headers = [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())] + [(k.lower().encode(), v.encode()) for k, v in extra_headers.items()]
    await send({"type": "http.response.start", "status": code, "headers": headers})
    await send({"type": "http.response.body", "body": body})
