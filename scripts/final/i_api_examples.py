"""Phase 10-I: capture REAL request/response examples of the release (1.0.0) API for docs/API.md.

  python scripts/final/i_api_examples.py

The in-process API (FastAPI TestClient) with the configured model behind the SHA-256 response cache. It captures one conversation per
action, representative validation errors, and the authentication, authorization and rate-limit responses (with a generated test token
that is never written). Traces go to a temporary directory. Writes artifacts/final/api_examples.json; the Phase 7 record
(artifacts/phase7/api_examples.json) is not touched.
"""
from __future__ import annotations

import json
import secrets
import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from resolveai.agent import AgentConfig, ResolveAI  # noqa: E402
from resolveai.api.app import create_app  # noqa: E402
from resolveai.api.auth import TokenAuthenticator  # noqa: E402
from resolveai.api.service import AgentService  # noqa: E402
from resolveai.api.settings import ApiSettings  # noqa: E402
from resolveai.observability import TraceStore  # noqa: E402

OUT = ROOT / "artifacts" / "final" / "api_examples.json"
CASES = {
    "auto_handle": [{"role": "customer", "text": "My iPhone keeps changing \"it\" to \"I.T\" whenever I type. How do I fix this autocorrect bug?"}],
    "clarification": [{"role": "customer", "text": "My iPhone 8 on iOS 11.1.2 drains battery really fast since yesterday"}],
    "handoff": [{"role": "customer", "text": "Someone logged into my Apple ID from another country and changed my password. I can't sign in anymore."}],
}


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="resolveai-examples-"))
    agent = ResolveAI(cfg=AgentConfig(), trace_store=TraceStore(tmp))
    settings = ApiSettings.for_profile("test", trace_dir=tmp)
    client = TestClient(create_app(settings, AgentService(settings, agent=agent), TokenAuthenticator.from_env(False, {})))
    out: dict = {"note": "real responses from the in-process release API (1.0.0) with the configured model behind the response cache; traces in a temporary directory"}
    for name, conv in CASES.items():
        req = {"conversation": conv, "metadata": {"channel": "twitter", "locale": "en-US"}}
        r = client.post("/api/v1/resolve", json=req, headers={"X-Request-ID": f"doc-example-{name}"})
        body = r.json()
        out[name] = {"request": req, "status": r.status_code, "headers": {k: r.headers[k] for k in ("x-request-id", "x-trace-id") if k in r.headers}, "response": body}
        t = client.get(f"/api/v1/traces/{body['trace_id']}").json()
        out[name]["trace_excerpt"] = {k: t.get(k) for k in ("trace_id", "request_id", "pipeline_version", "config_hash", "versions", "request_meta", "final_decision",
                                                             "stage_status", "latency_ms", "failures", "budget_s")}
        out[name]["trace_excerpt"]["event_names"] = [e["name"] for e in t["events"]]
    errors = {
        "invalid_json": client.post("/api/v1/resolve", content=b"{oops", headers={"content-type": "application/json"}),
        "validation_error": client.post("/api/v1/resolve", json={"conversation": [{"role": "customer", "text": "hi"}], "evidence": [{"brand_reply": "we refund"}]}),
        "invalid_conversation": client.post("/api/v1/resolve", json={"conversation": [{"role": "brand", "text": "Which iPhone?"}]}),
        "input_too_large": client.post("/api/v1/resolve", json={"conversation": [{"role": "customer", "text": "x" * 2500}]}),
        "trace_not_found": client.get("/api/v1/traces/" + "0" * 32),
    }
    out["errors"] = {k: {"status": v.status_code, "body": v.json()} for k, v in errors.items()}
    operator, reader = secrets.token_urlsafe(36), secrets.token_urlsafe(36)
    secured = ApiSettings.for_profile("test", trace_dir=tmp, auth_required=True, rate_limit_per_minute=1)
    sc = TestClient(create_app(secured, AgentService(secured, agent=agent), TokenAuthenticator.from_env(True, {"RESOLVEAI_API_TOKEN": operator, "RESOLVEAI_READ_TOKEN": reader})))
    body = {"conversation": CASES["auto_handle"]}
    unauthorized = sc.post("/api/v1/resolve", json=body)
    forbidden = sc.post("/api/v1/resolve", json=body, headers={"Authorization": f"Bearer {reader}"})
    first = sc.post("/api/v1/resolve", json=body, headers={"Authorization": f"Bearer {operator}"})
    limited = sc.post("/api/v1/resolve", json=body, headers={"Authorization": f"Bearer {operator}"})
    for name, resp in (("unauthorized", unauthorized), ("forbidden", forbidden), ("rate_limited", limited)):
        text = json.dumps(resp.json())
        assert operator not in text and reader not in text
        out["errors"][name] = {"status": resp.status_code, "headers": {k: resp.headers[k] for k in ("www-authenticate", "retry-after") if k in resp.headers}, "body": resp.json()}
    out["errors"]["rate_limited"]["preceded_by_status"] = first.status_code
    out["health"] = client.get("/api/v1/health").json()
    out["ready"] = client.get("/api/v1/ready").json()
    out["config"] = client.get("/api/v1/config").json()
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    for name in CASES:
        b = out[name]["response"]
        print(name, out[name]["status"], b["action"], b["outcome"]["reason_code"], "|", b["response"]["kind"], "|", b["response"]["text"][:90])
    print({k: v["status"] for k, v in out["errors"].items()})


if __name__ == "__main__":
    main()
