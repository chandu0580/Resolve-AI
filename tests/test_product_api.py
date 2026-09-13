"""Product Completion 1: read-only console endpoints (/evaluation/release, /agent/profile, /knowledge/summary), the ordered
policy rule list served to the Agents page, and the trace-summary cost field. The knowledge base and classifier are real
(skipped if the artifacts are missing); no model is called."""
import hashlib
import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from resolveai import config
from resolveai.agent import AgentConfig, ResolveAI
from resolveai.api import product
from resolveai.api.app import create_app
from resolveai.api.auth import TokenAuthenticator
from resolveai.api.service import AgentService, summarize_trace
from resolveai.api.settings import ApiSettings
from resolveai.intelligence.classifier import ARTIFACT, IntentService
from resolveai.observability import TraceStore
from resolveai.policy import escalation
from resolveai.retrieval import KnowledgeBase, Retriever, RetrieverConfig, resolution
from resolveai.trust.pii import contains_unredacted_pii

needs_kb = pytest.mark.skipif(not ARTIFACT.exists() or not (config.PROCESSED_DIR / "apple_pairs.csv").exists(), reason="artifact or subsample missing")
needs_release = pytest.mark.skipif(not (product.FINAL_DIR / "final_metrics.json").exists(), reason="release artifacts missing")
GOLDEN_SHA = "33f4f333ccf10de7f628e57b5567a7930852cdf5b6d4bba872555b96b2bec3a9"
OPERATOR = "op-token-0123456789-abcdefghijklmnopqrstuvwxyz"
READER = "reader-token-0123456789-abcdefghijklmnopqrstuv"
ENDPOINTS = ("/api/v1/evaluation/release", "/api/v1/agent/profile", "/api/v1/knowledge/summary")


def bare_app(tmp_path, required=False):
    settings = ApiSettings.for_profile("test", trace_dir=tmp_path / "traces", auth_required=required)
    auth = TokenAuthenticator.from_env(required, {"RESOLVEAI_API_TOKEN": OPERATOR, "RESOLVEAI_READ_TOKEN": READER} if required else {})
    return TestClient(create_app(settings, AgentService(settings), auth))


@pytest.fixture(scope="module")
def parts():
    kb = KnowledgeBase.build(dense_models=[RetrieverConfig().model], with_bm25=False)
    return {"kb": kb, "retriever": Retriever(kb, RetrieverConfig()), "intents": IntentService()}


def build(tmp_path, parts):
    agent = ResolveAI(kb=parts["kb"], retriever=parts["retriever"], intents=parts["intents"], llm=None,
                      cfg=AgentConfig(use_llm=False, use_second_opinion=False), trace_store=TraceStore(tmp_path / "traces"))
    settings = ApiSettings.for_profile("test", trace_dir=tmp_path / "traces")
    service = AgentService(settings, agent=agent)
    return TestClient(create_app(settings, service)), service


def strings_under(obj, keys, key=None):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from strings_under(v, keys, k)
    elif isinstance(obj, list):
        for v in obj:
            yield from strings_under(v, keys, key)
    elif isinstance(obj, str) and key in keys:
        yield obj


# ---------------------------------------------------------------- policy rule list
def test_policy_rules_list_matches_decide_in_order():
    src = Path(escalation.__file__).read_text(encoding="utf-8")
    body = src[src.index("def decide("):src.index("def hard_handoff_guaranteed")]
    returned = re.findall(r'E\("(?:escalate|auto_handle)", "([^"]+)", "([^"]+)"', body)
    assert returned == [(r["reason_code"], r["rule"]) for r in escalation.POLICY_RULES]
    assert all(r["outcome"] in {"handoff", "clarify", "clarify_or_handoff", "template_reply", "auto_reply"} for r in escalation.POLICY_RULES)


# ---------------------------------------------------------------- trace summary cost
def test_trace_summary_sums_estimated_cost_from_usage_records():
    base = {"trace_id": "a" * 32, "started_at": "2026-09-11T00:00:00Z", "events": []}
    row = summarize_trace({**base, "usage": [{"calls": 2, "estimated_cost_usd": 0.001}, {"calls": 1, "estimated_cost_usd": 0.0005}]})
    assert row.llm_calls == 3 and row.estimated_cost_usd == pytest.approx(0.0015)
    assert summarize_trace(base).estimated_cost_usd is None


# ---------------------------------------------------------------- release view (no agent needed)
@needs_release
def test_release_view_serves_frozen_artifacts_separated_by_dataset(tmp_path):
    frozen = product.FINAL_DIR / "final_metrics.json"
    before = hashlib.sha256(frozen.read_bytes()).hexdigest()
    r = bare_app(tmp_path).get("/api/v1/evaluation/release")
    assert r.status_code == 200
    b = r.json()
    stored = json.loads(frozen.read_text(encoding="utf-8"))
    assert b["golden"]["dataset"] == "FROZEN GOLDEN SET" and b["dev_experiments"]["dataset"] == "DEV EXPERIMENTS"
    assert b["golden"]["release"]["golden_sha256"] == GOLDEN_SHA and b["golden"]["release"]["n"] == 197
    assert b["golden"]["table"] == stored["table"], "metrics are served as stored, never recomputed"
    assert b["golden"]["human_evaluation"]["fully_rated_rows"] == stored["human_evaluation"]["fully_rated_rows"]
    assert b["golden"]["failure_modes"]["unnecessary_handoffs"]["total"] == 75
    assert "changed_rows" not in (b["golden"]["judge_attribution"] or {})
    assert b["limitations"]
    for text in strings_under(b, product.TEXT_KEYS):
        assert len(text) <= product.MAX_TEXT and not contains_unredacted_pii(text)
    assert hashlib.sha256(frozen.read_bytes()).hexdigest() == before


def test_product_endpoints_require_authentication_when_enabled(tmp_path):
    c = bare_app(tmp_path, required=True)
    for path in ENDPOINTS:
        r = c.get(path)
        assert r.status_code == 401 and r.json()["error_code"] == "unauthorized"
    headers = {"Authorization": f"Bearer {READER}"}
    r = c.get("/api/v1/agent/profile", headers=headers)
    assert r.status_code == 503 and r.json()["error_code"] in {"agent_not_ready", "agent_unavailable"}
    assert c.get("/api/v1/knowledge/summary", headers=headers).status_code == 503


# ---------------------------------------------------------------- agent profile and knowledge summary (real knowledge base)
@needs_kb
def test_agent_profile_shows_active_and_evaluated_configuration_without_secrets(tmp_path, parts):
    client, _ = build(tmp_path, parts)
    r = client.get("/api/v1/agent/profile")
    assert r.status_code == 200
    b = r.json()
    frozen_gate = json.loads(Path(resolution.__file__).with_name("gate_v3_config.json").read_text(encoding="utf-8"))
    assert all(b["active"]["evidence_gate"][k] == v for k, v in frozen_gate.items() if k in b["active"]["evidence_gate"])
    assert b["policy"]["rules"] == escalation.POLICY_RULES and b["policy"]["version"] == escalation.POLICY_VERSION
    assert [a["action"] for a in b["allowed_actions"]] == ["AUTO_HANDLE", "CLARIFICATION_REQUIRED", "HUMAN_HANDOFF"]
    if product.RELEASE_META.exists():
        evaluated = json.loads(product.RELEASE_META.read_text(encoding="utf-8"))["agent_config"]
        assert b["evaluated"]["agent_config"] == evaluated
        assert {"use_llm", "use_second_opinion"} <= {d["field"] for d in b["evaluated"]["differences"]}
    text = r.text.lower()
    assert "api_key" not in text and "base_url" not in text and str(config.ROOT).lower().replace("\\", "\\\\") not in text
    leaked = bool(config.LLM_API_KEY) and config.LLM_API_KEY.lower() in text
    assert not leaked, "the model credential must never be served"


@needs_kb
def test_knowledge_summary_is_aggregates_only(tmp_path, parts):
    client, _ = build(tmp_path, parts)
    r = client.get("/api/v1/knowledge/summary")
    assert r.status_code == 200
    b = r.json()
    rows = parts["kb"].rows
    assert b["rows"] == len(rows)
    assert b["resolution_bearing"] == int(rows.brand_reply.map(resolution.is_resolution_bearing).sum())
    assert sum(i["rows"] for i in b["by_weak_intent"]) == len(rows)
    assert b["date_range"]["max"] < b["manifest"]["holdout_min_created_at"]
    for message in rows.customer_message[rows.customer_message.str.len() > 40].head(20):
        assert message not in r.text
    for reply in rows.brand_reply[rows.brand_reply.str.len() > 40].head(20):
        assert reply not in r.text


@needs_kb
def test_trace_list_rows_carry_the_cost_field(tmp_path, parts):
    client, _ = build(tmp_path, parts)
    assert client.post("/api/v1/resolve", json={"conversation": [{"role": "customer", "text": "My iPhone battery drains overnight since the update"}]}).status_code == 200
    item = client.get("/api/v1/traces").json()["items"][0]
    assert "estimated_cost_usd" in item and (item["estimated_cost_usd"] is None or item["estimated_cost_usd"] >= 0)
