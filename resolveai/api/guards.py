"""Request correlation and resource protection. Deliberately in-process and dependency-free: one service process runs one
agent, so a shared store (Redis) would add infrastructure without a purpose here.

RequestContextMiddleware  request_id (a valid caller X-Request-ID is kept, otherwise generated), body-size limit enforced
                          before JSON parsing, no-store/nosniff headers, one log line per request (never the body).
RateLimiter               per-client sliding window over 60 s.
AgentGate                 one agent execution at a time plus a bounded wait queue; beyond it the API answers 429 at once.
"""
from __future__ import annotations

import json
import logging
import re
import threading
import time
import uuid
from collections import defaultdict, deque
from collections.abc import Iterator
from contextlib import contextmanager

from resolveai.api.errors import ApiError

log = logging.getLogger("resolveai.api")
REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._-]{8,64}$")


class RequestContextMiddleware:
    def __init__(self, app, max_body_bytes: int):
        self.app, self.max_body_bytes = app, max_body_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
        rid = headers.get("x-request-id", "")
        if not REQUEST_ID_RE.fullmatch(rid):
            rid = uuid.uuid4().hex
        scope.setdefault("state", {})["request_id"] = rid
        t0 = time.perf_counter()
        status = {"code": 0}

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
                extra = [(b"x-request-id", rid.encode()), (b"x-content-type-options", b"nosniff"), (b"cache-control", b"no-store")]
                present = {k.lower() for k, _ in message.get("headers", [])}
                message["headers"] = list(message.get("headers", [])) + [(k, v) for k, v in extra if k not in present]
            await send(message)

        try:
            if scope.get("method") in ("POST", "PUT", "PATCH"):
                length = headers.get("content-length")
                if length is None:
                    await self._reject(send_with_headers, rid, 411, "length_required", "A Content-Length header is required.")
                    return
                if not length.isdigit() or int(length) > self.max_body_bytes:
                    await self._reject(send_with_headers, rid, 413, "payload_too_large", f"Request body exceeds {self.max_body_bytes} bytes.")
                    return
            await self.app(scope, receive, send_with_headers)
        finally:
            log.info("request_id=%s method=%s path=%s status=%s latency_ms=%.1f", rid, scope.get("method"), scope.get("path"), status["code"], (time.perf_counter() - t0) * 1000)

    @staticmethod
    async def _reject(send, rid: str, code: int, error_code: str, message: str) -> None:
        body = json.dumps({"error_code": error_code, "message": message, "request_id": rid, "trace_id": None, "details": None}).encode()
        await send({"type": "http.response.start", "status": code, "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
        await send({"type": "http.response.body", "body": body})


class RateLimiter:
    """Sliding 60-second window per client key. In-process only; a multi-process deployment would need a shared store."""

    def __init__(self, per_minute: int, clock=time.monotonic):
        self.per_minute, self.clock = per_minute, clock
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> int | None:
        """Records the hit and returns None when allowed, or the seconds to wait when the limit is reached."""
        now = self.clock()
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] >= 60:
                q.popleft()
            if len(q) >= self.per_minute:
                return max(1, int(60 - (now - q[0])) + 1)
            q.append(now)
            return None


class AgentGate:
    """Serialises agent executions. The agent's LLM usage counters are per instance, so one execution at a time keeps the
    per-request token and cost figures exact; `max_queue` bounds how many requests may wait for the slot."""

    def __init__(self, max_queue: int, queue_timeout_s: float = 30.0):
        self._slots = threading.BoundedSemaphore(max_queue + 1)
        self._run = threading.Lock()
        self.queue_timeout_s = queue_timeout_s

    @contextmanager
    def acquire(self) -> Iterator[None]:
        if not self._slots.acquire(blocking=False):
            raise ApiError(429, "agent_busy", "The agent is processing other requests; retry shortly.", headers={"Retry-After": "5"})
        try:
            # a waiting request never blocks forever behind a slow execution
            if not self._run.acquire(timeout=self.queue_timeout_s):
                raise ApiError(429, "agent_busy", f"No agent slot became free within {self.queue_timeout_s:g} s; retry shortly.", headers={"Retry-After": "5"})
            try:
                yield
            finally:
                self._run.release()
        finally:
            self._slots.release()
