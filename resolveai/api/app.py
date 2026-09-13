"""FastAPI application factory.

    uvicorn resolveai.api.app:app_factory --factory --host 127.0.0.1 --port 8000
    python -m resolveai serve [--env development|demo|test|production]

Middleware order (outermost first): CORS -> request context (request id, body limit, headers, access log)
-> access control (authentication, scope, rate limit; before the body is read) -> routes.
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from resolveai.api import SERVICE_VERSION
from resolveai.api.access import AccessControlMiddleware
from resolveai.api.auth import TokenAuthenticator
from resolveai.api.errors import install_error_handlers
from resolveai.api.guards import RequestContextMiddleware
from resolveai.api.routes import router
from resolveai.api.service import AgentService
from resolveai.api.settings import ApiSettings

DESCRIPTION = """Production-style reference implementation of an evidence-first AppleSupport agent.

**One canonical endpoint:** `POST /api/v1/resolve` returns exactly one action (`AUTO_HANDLE`, `CLARIFICATION_REQUIRED`,
`HUMAN_HANDOFF`) with the reason, the evidence, the verifier verdict, and the clarification or handoff packet.
Every execution is traced (`GET /api/v1/traces/{trace_id}`). Customer text is untrusted data: it is PII-redacted before any
storage or model call and can never act as an instruction or as evidence. When authentication is enabled, send
`Authorization: Bearer <token>`; `/health` and `/ready` stay public."""

TAGS = [{"name": "agent", "description": "Run the trusted pipeline."}, {"name": "audit", "description": "Traces of past executions."},
        {"name": "operations", "description": "Health, readiness and safe configuration."}, {"name": "evaluation", "description": "Frozen evaluation results and demo scenarios."}]


def create_app(settings: ApiSettings | None = None, service: AgentService | None = None, authenticator: TokenAuthenticator | None = None) -> FastAPI:
    settings = settings or ApiSettings.from_env()
    authenticator = authenticator or TokenAuthenticator.from_env(settings.auth_required, os.environ)   # fails fast when auth is required but no token is set
    if authenticator.required != settings.auth_required:
        raise ValueError("the authenticator and the settings disagree on whether authentication is required")
    service = service or AgentService(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if settings.eager_load and service.state == "not_started":
            service.start_background_load()
        yield

    app = FastAPI(title="ResolveAI API", version=SERVICE_VERSION, description=DESCRIPTION, openapi_tags=TAGS, lifespan=lifespan,
                  docs_url="/docs" if settings.expose_docs else None, redoc_url=None, openapi_url="/openapi.json" if settings.expose_docs else None)
    app.state.service = service
    app.state.settings = settings
    app.state.auth = authenticator
    install_error_handlers(app)
    app.include_router(router)
    app.add_middleware(AccessControlMiddleware)
    app.add_middleware(RequestContextMiddleware, max_body_bytes=settings.max_body_bytes)
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_credentials=False, allow_methods=["GET", "POST"],
                       allow_headers=["Content-Type", "X-Request-ID", "Authorization", "X-API-Key"], expose_headers=["X-Request-ID", "X-Trace-ID", "Retry-After"], max_age=600)
    return app


def app_factory() -> FastAPI:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    return create_app()
