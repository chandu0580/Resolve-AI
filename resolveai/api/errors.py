"""Explicit API errors. Every error body is {error_code, message, request_id, trace_id, details}; no stack traces, no input
echo (validation details carry field locations and types, never the submitted values), no secrets.

400 invalid_json / invalid_conversation / invalid_trace_id   413 payload_too_large / input_too_large   411 length_required
401 unauthorized (missing or invalid credentials)             403 forbidden (valid credentials, missing scope)
404 not_found / trace_not_found                                422 validation_error                     429 rate_limited / agent_busy
500 internal_error / autonomy_invariant_violation              503 agent_not_ready / agent_unavailable

Unexpected exceptions are logged with their type, a PII-redacted and truncated message, and the code locations of the
traceback: exception text can contain fragments of customer input, so raw exception messages and locals never reach the log.
"""
from __future__ import annotations

import logging
import traceback
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from resolveai.trust.pii import redact_pii

log = logging.getLogger("resolveai.api")


class ErrorBody(BaseModel):
    error_code: str
    message: str
    request_id: str
    trace_id: str | None = None
    details: Any = None


class ApiError(Exception):
    def __init__(self, status: int, error_code: str, message: str, *, trace_id: str | None = None, details: Any = None, headers: dict[str, str] | None = None):
        super().__init__(message)
        self.status, self.error_code, self.message, self.trace_id, self.details, self.headers = status, error_code, message, trace_id, details, headers or {}


def request_id_of(request: Request) -> str:
    return str(request.scope.get("state", {}).get("request_id") or "unknown")


def safe_exception_text(exc: BaseException, limit: int = 160) -> str:
    """Exception type plus a redacted, single-line, truncated message: fit for logs and traces."""
    return f"{type(exc).__name__}: {redact_pii(str(exc)).text[:limit]}".replace("\n", " ")


def code_locations(exc: BaseException, limit: int = 6) -> str:
    """Where it failed (file:line in function), without the source lines' runtime values or the exception message."""
    frames = traceback.extract_tb(exc.__traceback__)[-limit:]
    return " <- ".join(f"{f.filename.rsplit('resolveai', 1)[-1]}:{f.lineno} in {f.name}" for f in reversed(frames))


def error_response(request: Request, status: int, code: str, message: str, *, trace_id: str | None = None, details: Any = None, headers: dict[str, str] | None = None) -> JSONResponse:
    rid = request_id_of(request)
    body = ErrorBody(error_code=code, message=message, request_id=rid, trace_id=trace_id, details=details)
    return JSONResponse(status_code=status, content=body.model_dump(), headers={"X-Request-ID": rid, "Cache-Control": "no-store", **(headers or {})})


def _safe_validation_details(errors: list[dict]) -> list[dict]:
    return [{"loc": [str(x) for x in e.get("loc", ())], "type": str(e.get("type", "")), "msg": str(e.get("msg", ""))[:200]} for e in errors[:20]]


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError):
        return error_response(request, exc.status, exc.error_code, exc.message, trace_id=exc.trace_id, details=exc.details, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        errors = exc.errors()
        if any(e.get("type") == "json_invalid" for e in errors):
            return error_response(request, 400, "invalid_json", "The request body is not valid JSON.")
        return error_response(request, 422, "validation_error", "The request does not match the API schema.", details=_safe_validation_details(errors))

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        code = {404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error")
        message = {404: "No such endpoint.", 405: "Method not allowed for this endpoint."}.get(exc.status_code, "The request could not be processed.")
        return error_response(request, exc.status_code, code, message)

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception):
        log.error("unhandled error request_id=%s path=%s error=%s at=%s", request_id_of(request), request.url.path, safe_exception_text(exc), code_locations(exc))
        return error_response(request, 500, "internal_error", "An unexpected error occurred. Quote the request_id when reporting it.")
