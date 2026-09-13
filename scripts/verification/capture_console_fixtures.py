"""Product-1: capture console test fixtures for the new read-only endpoints from the REAL API (in process). Nothing is hand-written.

  python scripts/verification/capture_console_fixtures.py

Runs create_app with the real knowledge base, classifier and frozen artifacts (model calls disabled, traces to a temporary
directory) and writes the JSON bodies of GET /api/v1/evaluation/release, /agent/profile and /knowledge/summary to
frontend/tests/fixtures/. No model is called and nothing frozen is written.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from fastapi.testclient import TestClient  # noqa: E402

from resolveai.agent import AgentConfig, ResolveAI  # noqa: E402
from resolveai.api.app import create_app  # noqa: E402
from resolveai.api.service import AgentService  # noqa: E402
from resolveai.api.settings import ApiSettings  # noqa: E402
from resolveai.observability import TraceStore  # noqa: E402

OUT = ROOT / "frontend" / "tests" / "fixtures"
ENDPOINTS = {"evaluation_release.json": "/api/v1/evaluation/release", "agent_profile.json": "/api/v1/agent/profile", "knowledge_summary.json": "/api/v1/knowledge/summary"}


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        traces = Path(tmp) / "traces"
        settings = ApiSettings.for_profile("test", trace_dir=traces)
        agent = ResolveAI(cfg=AgentConfig(use_llm=False), trace_store=TraceStore(traces))
        client = TestClient(create_app(settings, AgentService(settings, agent=agent)))
        for name, path in ENDPOINTS.items():
            r = client.get(path)
            if r.status_code != 200:
                print(f"{path} answered {r.status_code}")
                return 1
            (OUT / name).write_text(json.dumps(r.json(), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
            print("wrote", (OUT / name).relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
