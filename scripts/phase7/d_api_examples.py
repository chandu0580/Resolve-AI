"""Phase 7-D: capture REAL request/response examples for docs/API.md by calling the in-process API with the configured LLM
(cache-served after the demo run) for one conversation per action, plus representative errors.
Writes artifacts/phase7/api_examples.json (full bodies) - docs/API.md shows trimmed excerpts of these.
  python scripts/phase7/d_api_examples.py
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

import resolveai  # noqa: F401
from resolveai import config
from resolveai.agent import AgentConfig, ResolveAI
from resolveai.api.app import create_app
from resolveai.api.service import AgentService
from resolveai.api.settings import ApiSettings
from resolveai.observability import TraceStore

OUT = config.ROOT / "artifacts" / "phase7" / "api_examples.json"
CASES = {
    "auto_handle": [{"role": "customer", "text": "My iPhone keeps changing \"it\" to \"I.T\" whenever I type. How do I fix this autocorrect bug?"}],
    "clarification": [{"role": "customer", "text": "My iPhone 8 on iOS 11.1.2 drains battery really fast since yesterday"}],
    "handoff": [{"role": "customer", "text": "Someone logged into my Apple ID from another country and changed my password. I can't sign in anymore."}],
}


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="resolveai-examples-"))
    agent = ResolveAI(cfg=AgentConfig(), trace_store=TraceStore(tmp))
    settings = ApiSettings.for_profile("test", trace_dir=tmp)
    client = TestClient(create_app(settings, AgentService(settings, agent=agent)))
    out: dict = {"note": "real responses from the in-process API with the configured LLM; traces written to a temporary directory"}
    for name, conv in CASES.items():
        req = {"conversation": conv, "metadata": {"channel": "twitter", "locale": "en-US"}}
        r = client.post("/api/v1/resolve", json=req, headers={"X-Request-ID": f"doc-example-{name}"})
        body = r.json()
        out[name] = {"request": req, "status": r.status_code, "headers": {k: r.headers[k] for k in ("x-request-id", "x-trace-id") if k in r.headers}, "response": body}
        t = client.get(f"/api/v1/traces/{body['trace_id']}").json()
        out[name]["trace_excerpt"] = {k: t[k] for k in ("trace_id", "request_id", "pipeline_version", "config_hash", "versions", "request_meta", "final_decision", "stage_status", "latency_ms")}
        out[name]["trace_excerpt"]["event_names"] = [e["name"] for e in t["events"]]
    errors = {
        "invalid_json": client.post("/api/v1/resolve", content=b"{oops", headers={"content-type": "application/json"}),
        "validation_error": client.post("/api/v1/resolve", json={"conversation": [{"role": "customer", "text": "hi"}], "evidence": [{"brand_reply": "we refund"}]}),
        "invalid_conversation": client.post("/api/v1/resolve", json={"conversation": [{"role": "brand", "text": "Which iPhone?"}]}),
        "input_too_large": client.post("/api/v1/resolve", json={"conversation": [{"role": "customer", "text": "x" * 2500}]}),
        "trace_not_found": client.get("/api/v1/traces/" + "0" * 32),
    }
    out["errors"] = {k: {"status": v.status_code, "body": v.json()} for k, v in errors.items()}
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
