"""Tests for the Golden Set manual labelling manager, validation, and web UI API."""
from __future__ import annotations

import json
import shutil
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd
import pytest

from scripts.golden_label_ui import (
    DEFAULT_GOLDEN_INPUT,
    ESCALATION_REASONS,
    INTENT_NAMES,
    GoldenLabelManager,
    GoldenLabelRequestHandler,
)


@pytest.fixture
def temp_environment(tmp_path):
    """Creates an isolated temporary environment with a copy of golden_final.csv."""
    test_src = tmp_path / "test_golden.csv"
    shutil.copyfile(DEFAULT_GOLDEN_INPUT, test_src)
    test_out = tmp_path / "test_human_labels.csv"
    test_man = tmp_path / "test_manifest.json"
    return test_src, test_out, test_man


def test_manager_initialization(temp_environment):
    src, out, man = temp_environment
    mgr = GoldenLabelManager(input_csv=src, output_csv=out, manifest_path=man)

    assert mgr.total_count == 197
    summary = mgr.get_summary()
    assert summary["total"] == 197
    assert summary["completed_count"] == 0
    assert summary["remaining_count"] == 197
    assert summary["percent_complete"] == 0.0
    assert summary["is_complete"] is False
    assert summary["first_unrated_index"] == 0

    # Verify output file and manifest were created
    assert out.exists()
    assert man.exists()

    manifest = json.loads(man.read_text(encoding="utf-8"))
    assert manifest["total_rows"] == 197
    assert manifest["completed_rows"] == 0
    assert manifest["annotator"] == "human owner"
    assert manifest["schema_version"] == "v1.2 (human-labelled)"


def test_get_item_structure(temp_environment):
    src, out, man = temp_environment
    mgr = GoldenLabelManager(input_csv=src, output_csv=out, manifest_path=man)
    item = mgr.get_item(0)

    assert item["index"] == 0
    assert item["total"] == 197
    assert item["gid"] == "g000"
    assert "customer_message" in item and len(item["customer_message"]) > 0
    assert item["current_labels"]["intent"] is None
    assert item["current_labels"]["should_escalate"] is None
    assert item["current_labels"]["escalation_reason"] is None
    assert item["is_completed"] is False

    # Check AI reference exists as non-anchoring audit metadata
    assert "ai_reference" in item
    assert "intent" in item["ai_reference"]
    assert "should_escalate" in item["ai_reference"]


def test_validation_rules(temp_environment):
    src, out, man = temp_environment
    mgr = GoldenLabelManager(input_csv=src, output_csv=out, manifest_path=man)

    # 1. Invalid intent
    with pytest.raises(ValueError, match="Invalid intent"):
        mgr.save_item(0, {"intent": "invalid_intent_xyz", "should_escalate": False, "escalation_reason": "none"})

    # 2. Missing/invalid should_escalate
    with pytest.raises(ValueError, match="should_escalate is required"):
        mgr.save_item(0, {"intent": "battery_power", "should_escalate": None, "escalation_reason": "none"})

    # 3. Escalate True with missing/none reason
    with pytest.raises(ValueError, match="escalation_reason must be one of"):
        mgr.save_item(0, {"intent": "battery_power", "should_escalate": True, "escalation_reason": "none"})

    # 4. Escalate True with invalid reason
    with pytest.raises(ValueError, match="escalation_reason must be one of"):
        mgr.save_item(0, {"intent": "battery_power", "should_escalate": True, "escalation_reason": "fake_reason"})


def test_valid_save_and_auto_none_reason(temp_environment):
    src, out, man = temp_environment
    mgr = GoldenLabelManager(input_csv=src, output_csv=out, manifest_path=man)

    # Save when should_escalate is False: reason should automatically be 'none'
    summary = mgr.save_item(0, {
        "intent": "performance_crash",
        "should_escalate": False,
        "escalation_reason": "anything_ignored_or_empty",
        "note": "lag after update"
    })

    assert summary["completed_count"] == 1
    assert summary["remaining_count"] == 196
    assert summary["first_unrated_index"] == 1

    item0 = mgr.get_item(0)
    assert item0["is_completed"] is True
    assert item0["current_labels"]["intent"] == "performance_crash"
    assert item0["current_labels"]["should_escalate"] is False
    assert item0["current_labels"]["escalation_reason"] == "none"
    assert item0["current_labels"]["note"] == "lag after update"

    # Save when should_escalate is True with valid reason
    mgr.save_item(1, {
        "intent": "account_store_repair",
        "should_escalate": True,
        "escalation_reason": "private_info",
        "note": "needs serial number"
    })

    item1 = mgr.get_item(1)
    assert item1["is_completed"] is True
    assert item1["current_labels"]["intent"] == "account_store_repair"
    assert item1["current_labels"]["should_escalate"] is True
    assert item1["current_labels"]["escalation_reason"] == "private_info"


def test_persistence_and_backup(temp_environment):
    src, out, man = temp_environment
    mgr = GoldenLabelManager(input_csv=src, output_csv=out, manifest_path=man)

    mgr.save_item(0, {
        "intent": "battery_power",
        "should_escalate": False,
        "escalation_reason": "none"
    })

    # Backup file (.bak) should exist after saving
    bak = out.with_suffix(".bak")
    assert bak.exists()

    # Re-loading manager should resume state
    mgr2 = GoldenLabelManager(input_csv=src, output_csv=out, manifest_path=man)
    assert mgr2.get_summary()["completed_count"] == 1
    assert mgr2.get_item(0)["current_labels"]["intent"] == "battery_power"


def test_api_endpoints(temp_environment):
    src, out, man = temp_environment
    mgr = GoldenLabelManager(input_csv=src, output_csv=out, manifest_path=man)
    GoldenLabelRequestHandler.manager = mgr

    # Bind to random port
    server = ThreadingHTTPServer(("127.0.0.1", 0), GoldenLabelRequestHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        # GET /
        with urlopen(f"http://127.0.0.1:{port}/") as resp:
            assert resp.status == 200
            html = resp.read().decode("utf-8")
            assert "Golden Set Studio" in html

        # GET /api/summary
        with urlopen(f"http://127.0.0.1:{port}/api/summary") as resp:
            assert resp.status == 200
            s = json.loads(resp.read().decode("utf-8"))
            assert s["total"] == 197
            assert s["completed_count"] == 0

        # GET /api/item?index=0
        with urlopen(f"http://127.0.0.1:{port}/api/item?index=0") as resp:
            assert resp.status == 200
            item = json.loads(resp.read().decode("utf-8"))
            assert item["gid"] == "g000"

        # POST /api/save?index=0
        payload = json.dumps({
            "intent": "connectivity",
            "should_escalate": True,
            "escalation_reason": "hardware",
            "note": "broken antenna port"
        }).encode("utf-8")
        req = Request(
            f"http://127.0.0.1:{port}/api/save?index=0",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urlopen(req) as resp:
            assert resp.status == 200
            s = json.loads(resp.read().decode("utf-8"))
            assert s["completed_count"] == 1

        # Check update via API
        with urlopen(f"http://127.0.0.1:{port}/api/item?index=0") as resp:
            item = json.loads(resp.read().decode("utf-8"))
            assert item["current_labels"]["intent"] == "connectivity"
            assert item["current_labels"]["should_escalate"] is True
            assert item["current_labels"]["escalation_reason"] == "hardware"

    finally:
        server.shutdown()
        server.server_close()
