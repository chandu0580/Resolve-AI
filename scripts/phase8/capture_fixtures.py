"""Phase 8: capture REAL API responses as frontend test fixtures (frontend/tests/fixtures). Nothing is hand-written.

  python scripts/phase8/capture_fixtures.py

- Demo scenarios A-E and G are run through the in-process API with the configured LLM (cache-served after the demo run).
- Scenario F runs through the same API with the demo's simulated-outage provider, i.e. the real fallback path.
- One verification-failure response uses a scripted verifier that rejects the draft (the only way to exercise that path
  deterministically); its file name says so.
Traces go to a temporary directory; the repository trace store is not touched.
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from resolveai.agent import AgentConfig, ResolveAI  # noqa: E402
from resolveai.agent.verifier import VERIFY_PROMPT_VERSION  # noqa: E402
from resolveai.api.app import create_app  # noqa: E402
from resolveai.api.service import AgentService  # noqa: E402
from resolveai.api.settings import ApiSettings  # noqa: E402
from resolveai.demo import UnavailableProvider  # noqa: E402
from resolveai.llm import LLMClient  # noqa: E402
from resolveai.observability import TraceStore  # noqa: E402

OUT = ROOT / "frontend" / "tests" / "fixtures"


class RejectingVerifierClient(LLMClient):
    """The configured model for every call except the grounding verifier, which rejects the draft (to exercise 'draft blocked')."""

    def structured(self, messages, schema, *, prompt_version, **kw):
        if prompt_version == VERIFY_PROMPT_VERSION:
            self.usage.calls += 1
            return schema(supported=False, unsupported_claims=["a step that is not present in the cited evidence"], invented_steps=True, off_topic=False)
        return super().structured(messages, schema, prompt_version=prompt_version, **kw)


def client_for(agent, tmp: Path) -> TestClient:
    settings = ApiSettings.for_profile("test", trace_dir=tmp)
    return TestClient(create_app(settings, AgentService(settings, agent=agent)))


def save(name: str, obj) -> None:
    (OUT / f"{name}.json").write_text(json.dumps(obj, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print("wrote", name)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="resolveai-fixtures-"))
    live = ResolveAI(cfg=AgentConfig(), trace_store=TraceStore(tmp))
    api = client_for(live, tmp)
    scenarios = api.get("/api/v1/demo/scenarios").json()
    save("demo_scenarios", scenarios)
    for sc in scenarios:
        if sc["llm"] == "unavailable":
            continue
        r = api.post("/api/v1/resolve", json={"conversation": sc["conversation"], "metadata": {"channel": "web", "locale": "en-US"}}, headers={"X-Request-ID": f"fixture-{sc['id']}"})
        save(f"resolve_{sc['id']}_{re.sub(r'[^a-z]+', '_', sc['title'].lower()).strip('_')}", r.json())
        if sc["id"] == "A":
            save("trace_A_auto_handle", api.get(f"/api/v1/traces/{r.json()['trace_id']}").json())
        if sc["id"] == "D":
            save("trace_D_clarification", api.get(f"/api/v1/traces/{r.json()['trace_id']}").json())
    outage = ResolveAI(kb=live.kb, retriever=live.retriever, intents=live.intents, llm=LLMClient(provider=UnavailableProvider(), model="simulated-outage", cache=None, max_retries=0),
                       cfg=AgentConfig(), trace_store=TraceStore(tmp))
    f = next(s for s in scenarios if s["id"] == "F")
    save("resolve_F_llm_unavailable", client_for(outage, tmp).post("/api/v1/resolve", json={"conversation": f["conversation"]}, headers={"X-Request-ID": "fixture-F"}).json())
    rejecting = ResolveAI(kb=live.kb, retriever=live.retriever, intents=live.intents, llm=RejectingVerifierClient(provider=live.llm.provider, model=live.llm.model),
                          cfg=AgentConfig(), trace_store=TraceStore(tmp))
    a = next(s for s in scenarios if s["id"] == "A")
    save("resolve_verification_failed.scripted_verifier", client_for(rejecting, tmp).post("/api/v1/resolve", json={"conversation": a["conversation"]}, headers={"X-Request-ID": "fixture-verify"}).json())
    save("traces_list", api.get("/api/v1/traces?limit=20").json())
    save("evaluation_summary", api.get("/api/v1/evaluation/summary").json())
    save("ready", api.get("/api/v1/ready").json())
    save("config", api.get("/api/v1/config").json())
    save("health", api.get("/api/v1/health").json())
    save("error_trace_not_found", api.get("/api/v1/traces/" + "0" * 32).json())
    save("error_input_too_large", api.post("/api/v1/resolve", json={"conversation": [{"role": "customer", "text": "x" * 2500}]}).json())


if __name__ == "__main__":
    main()
