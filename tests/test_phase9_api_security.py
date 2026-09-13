"""Phase 9 API security tests: authentication boundary (401/403/valid), production profile, rate limits (429 + Retry-After),
readiness detail, no secrets in configuration, and redacted error logging. The agent is never loaded (fast, no model)."""
import logging

import pytest
from fastapi.testclient import TestClient

from resolveai.api.app import create_app
from resolveai.api.auth import TokenAuthenticator
from resolveai.api.service import AgentService
from resolveai.api.settings import ApiSettings

OPERATOR = "op-token-0123456789-abcdefghijklmnopqrstuvwxyz"
READER = "reader-token-0123456789-abcdefghijklmnopqrstuv"
BODY = {"conversation": [{"role": "customer", "text": "my battery drains fast"}]}


def app_for(tmp_path, required=True, env=None, **over):
    settings = ApiSettings.for_profile("test", trace_dir=tmp_path / "traces", auth_required=required, **over)
    auth = TokenAuthenticator.from_env(required, env if env is not None else {"RESOLVEAI_API_TOKEN": OPERATOR, "RESOLVEAI_READ_TOKEN": READER})
    return TestClient(create_app(settings, AgentService(settings), auth))


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_missing_and_invalid_credentials_get_the_same_401(tmp_path):
    c = app_for(tmp_path)
    for headers in ({}, bearer("wrong-token-wrong-token-wrong-token-wrong"), {"Authorization": "Basic abc"}):
        r = c.post("/api/v1/resolve", json=BODY, headers=headers)
        assert r.status_code == 401 and r.json()["error_code"] == "unauthorized"
        assert r.headers["www-authenticate"].startswith("Bearer") and r.json()["request_id"]
    assert c.get("/api/v1/traces").status_code == 401
    assert c.get("/api/v1/config").status_code == 401


def test_valid_credentials_pass_and_scopes_are_enforced(tmp_path):
    c = app_for(tmp_path)
    r = c.post("/api/v1/resolve", json=BODY, headers=bearer(OPERATOR))
    assert r.status_code == 503 and r.json()["error_code"] == "agent_not_ready"   # authenticated; the agent is simply not loaded in this test
    assert c.get("/api/v1/traces", headers=bearer(READER)).status_code == 200
    r = c.post("/api/v1/resolve", json=BODY, headers=bearer(READER))
    assert r.status_code == 403 and r.json()["error_code"] == "forbidden"
    assert c.get("/api/v1/traces", headers={"X-API-Key": OPERATOR}).status_code == 200


def test_authentication_runs_before_the_body_is_validated(tmp_path):
    c = app_for(tmp_path)
    r = c.post("/api/v1/resolve", content=b"{not json", headers={"Content-Type": "application/json"})
    assert r.status_code == 401, "an unauthenticated caller must not learn anything from validation errors"


def test_health_is_public_and_readiness_detail_needs_credentials(tmp_path):
    c = app_for(tmp_path)
    assert c.get("/api/v1/health").status_code == 200
    anon = c.get("/api/v1/ready").json()
    assert set(anon["components"]["agent"]) == {"ok"}, "anonymous readiness exposes only booleans"
    detail = c.get("/api/v1/ready", headers=bearer(READER)).json()
    assert "state" in detail["components"]["agent"]


def test_auth_disabled_profile_acts_as_anonymous(tmp_path):
    c = app_for(tmp_path, required=False, env={})
    assert c.get("/api/v1/traces").status_code == 200
    assert c.post("/api/v1/resolve", json=BODY).status_code == 503


def test_production_profile_requires_a_strong_token():
    with pytest.raises(ValueError):
        TokenAuthenticator.from_env(True, {})
    with pytest.raises(ValueError):
        TokenAuthenticator.from_env(True, {"RESOLVEAI_API_TOKEN": "short"})
    with pytest.raises(ValueError):
        TokenAuthenticator.from_env(True, {"RESOLVEAI_READ_TOKEN": READER})   # a read-only token cannot run the service
    s = ApiSettings.for_profile("production")
    assert s.auth_required and not s.expose_docs
    with pytest.raises(ValueError):
        create_app(s, AgentService(s), TokenAuthenticator.from_env(False, {}))


def test_token_comparison_uses_digests_and_rejects_prefixes():
    a = TokenAuthenticator.from_env(True, {"RESOLVEAI_API_TOKEN": OPERATOR})
    assert a.authenticate(OPERATOR).name == "operator"
    assert a.authenticate(OPERATOR[:-1]) is None and a.authenticate(OPERATOR + "x") is None and a.authenticate("") is None
    assert OPERATOR not in repr(a)


def test_rate_limit_returns_429_with_retry_after_per_principal(tmp_path):
    c = app_for(tmp_path, read_rate_limit_per_minute=2)
    assert c.get("/api/v1/traces", headers=bearer(READER)).status_code == 200
    assert c.get("/api/v1/traces", headers=bearer(READER)).status_code == 200
    r = c.get("/api/v1/traces", headers=bearer(READER))
    assert r.status_code == 429 and r.json()["error_code"] == "rate_limited" and int(r.headers["retry-after"]) >= 1
    assert c.get("/api/v1/traces", headers=bearer(OPERATOR)).status_code == 200, "limits are per principal"


def test_failed_authentication_attempts_are_rate_limited(tmp_path):
    c = app_for(tmp_path, auth_failures_per_minute=3)
    codes = [c.get("/api/v1/traces", headers=bearer("x" * 40)).status_code for _ in range(5)]
    assert codes[:3] == [401, 401, 401] and codes[3] == 429


def test_configuration_never_exposes_tokens_or_keys(tmp_path, monkeypatch):
    from resolveai import config

    monkeypatch.setattr(config, "LLM_API_KEY", "SENTINEL_LLM_KEY_VALUE_0123456789")
    c = app_for(tmp_path)
    body = c.get("/api/v1/config", headers=bearer(OPERATOR)).text
    assert "SENTINEL" not in body and OPERATOR not in body and READER not in body
    assert '"required":true' in body.replace(" ", "") and "process-local" in body


def test_unexpected_errors_are_logged_redacted(tmp_path, caplog):
    settings = ApiSettings.for_profile("test", trace_dir=tmp_path / "traces")
    app = create_app(settings, AgentService(settings), TokenAuthenticator.from_env(False, {}))

    @app.get("/api/v1/boom")
    def boom():
        raise RuntimeError("customer wrote jane.doe@example.com and 555-123-4567")

    with caplog.at_level(logging.ERROR, logger="resolveai.api"):
        r = TestClient(app, raise_server_exceptions=False).get("/api/v1/boom")
    assert r.status_code == 500 and "example.com" not in r.text
    logged = " ".join(rec.getMessage() for rec in caplog.records)
    assert "RuntimeError" in logged and "jane.doe@example.com" not in logged and "555-123-4567" not in logged and "<EMAIL>" in logged
