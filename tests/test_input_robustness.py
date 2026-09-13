"""The awkward-input contract, as a test: the cases in `scripts/verification/input_robustness.py` must never crash and must
always land on one of the three product outcomes with a named policy rule and customer-safe text.

The script is the reporting form (it writes `artifacts/final/input_robustness.{json,md}`); this keeps the same cases in the
suite so a regression fails CI rather than a report. No model is called.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from resolveai import config
from resolveai.agent import AgentConfig, ResolveAI
from resolveai.intelligence import conversation_acts as acts
from resolveai.intelligence.classifier import ARTIFACT

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("input_robustness", ROOT / "scripts" / "verification" / "input_robustness.py")
probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(probe)

needs_kb = pytest.mark.skipif(not ARTIFACT.exists() or not (config.PROCESSED_DIR / "apple_pairs.csv").exists(), reason="artifact or subsample missing")


@pytest.fixture(scope="module")
def agent():
    return ResolveAI(cfg=AgentConfig(use_llm=False, write_traces=False))


@needs_kb
@pytest.mark.parametrize(("cls", "label", "message", "turns"), probe.CASES, ids=[f"{c}-{lbl}" for c, lbl, _, _ in probe.CASES])
def test_awkward_input_never_crashes_and_always_decides(agent, cls, label, message, turns):
    r = agent.resolve(message, probe.ctx(turns))
    assert r.action in probe.ACTIONS
    assert r.decision.escalation.rule, "every decision names the policy rule that made it"
    assert (r.response or "").strip(), "every outcome has customer-facing text"
    assert not probe.INTERNAL.search(r.response), f"internal wording reached the customer: {r.response!r}"
    if r.action == "AUTO_HANDLE" and r.draft is not None and r.draft.strategy != "canned":
        assert r.evidence_refs and r.citations, "a drafted automatic reply must cite its evidence"


@needs_kb
@pytest.mark.parametrize(("cls", "label", "body", "expected"), probe.API_CASES, ids=[lbl for _, lbl, _, _ in probe.API_CASES])
def test_malformed_bodies_are_rejected_by_the_schema(agent, tmp_path, cls, label, body, expected):
    from fastapi.testclient import TestClient

    from resolveai.api.app import create_app
    from resolveai.api.service import AgentService
    from resolveai.api.settings import ApiSettings

    settings = ApiSettings.for_profile("test", trace_dir=tmp_path / "traces")
    client = TestClient(create_app(settings, AgentService(settings, agent=agent)))
    resp = client.post("/api/v1/resolve", json=body)
    assert resp.status_code in expected
    assert resp.status_code < 500, "a bad request must never become a server error"
    assert not probe.LEAK.search(resp.text), "the error body must not leak an internal path or traceback"


def test_a_non_latin_script_message_is_recognised_without_a_model():
    """Script is read off the characters, so this rule needs no confidence floor and no model call."""
    for text in ("iPhoneの電源が入りません", "هاتفي الآيفون لا يعمل",
                 "मेरा आईफोन चालू नहीं हो रहा है"):
        assert acts.is_non_latin_script(text), text
    for text in ("my iphone won't turn on", "mi iphone no enciende despues de la actualizacion",
                 "Mein iPhone lädt nicht mehr", "iOS 11 の bug", "\U0001f621\U0001f621\U0001f621", ""):
        assert not acts.is_non_latin_script(text), text
