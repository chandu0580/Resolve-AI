"""Tests for the local, blinded human evaluation interface."""
import json
import shutil
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd
import pytest

from scripts.human_eval_ui import (
    ALL_HUMAN_COLS,
    BINARY_DIMS,
    DEFAULT_PACKET_PATH,
    HumanEvalRequestHandler,
    ORDINAL_DIMS,
    PacketManager,
)


@pytest.fixture
def temp_packet(tmp_path):
    """Creates a clean, temporary copy of the 50-example packet for safe testing."""
    test_csv = tmp_path / "test_packet.csv"
    shutil.copyfile(DEFAULT_PACKET_PATH, test_csv)
    # Ensure test copy starts with blank human columns so UI lifecycle tests work cleanly
    df = pd.read_csv(test_csv, dtype=str, keep_default_na=False)
    for c in ALL_HUMAN_COLS:
        if c in df.columns:
            df[c] = ""
    df.to_csv(test_csv, index=False)
    return test_csv



def test_packet_loads_and_verifies_blinding(temp_packet):
    mgr = PacketManager(packet_path=temp_packet)
    assert mgr.total_count == 50
    assert mgr.verify_blinding() is True

    summary = mgr.get_summary()
    assert summary["total"] == 50
    assert summary["rated_count"] == 0
    assert summary["percent_complete"] == 0.0
    assert summary["is_complete"] is False
    assert summary["completion_command"] is None
    assert summary["first_unrated_index"] == 0


def test_get_item_structure_is_blinded(temp_packet):
    mgr = PacketManager(packet_path=temp_packet)
    item = mgr.get_item(0)

    # Required fields
    assert "example_id" in item
    assert "conversation" in item
    assert "evidence" in item
    assert "candidate_response" in item
    assert "ratings" in item
    assert item["is_rated"] is False

    # Never exposes system or model names
    assert "system" not in item
    assert "model" not in item
    assert "expected" not in item
    assert "golden" not in item


def test_save_item_validation_and_persistence(temp_packet):
    mgr = PacketManager(packet_path=temp_packet)

    # Valid ratings
    valid_ratings = {
        "groundedness": 4,
        "relevance": 5,
        "actionability": 3,
        "completeness": 4,
        "policy_compliance": 5,
        "tone": 4,
        "hallucination": 0,
        "policy_violation": 0,
        "notes": "Clear, grounded response."
    }
    summary = mgr.save_item(0, valid_ratings)
    assert summary["rated_count"] == 1
    assert summary["percent_complete"] == 2.0
    assert summary["first_unrated_index"] == 1

    # Verify reload from disk preserves ratings and creates backup
    mgr2 = PacketManager(packet_path=temp_packet)
    item0 = mgr2.get_item(0)
    assert item0["is_rated"] is True
    assert item0["ratings"]["groundedness"] == 4
    assert item0["ratings"]["relevance"] == 5
    assert item0["ratings"]["hallucination"] == 0
    assert item0["ratings"]["notes"] == "Clear, grounded response."

    # Backup file should have been generated
    bak_path = temp_packet.with_suffix(".bak")
    assert bak_path.exists()


def test_save_item_rejects_out_of_bounds_values(temp_packet):
    mgr = PacketManager(packet_path=temp_packet)

    with pytest.raises(ValueError, match="between 1 and 5"):
        mgr.save_item(0, {"groundedness": 6})

    with pytest.raises(ValueError, match="between 1 and 5"):
        mgr.save_item(0, {"groundedness": 0})

    with pytest.raises(ValueError, match="must be 0 or 1"):
        mgr.save_item(0, {"hallucination": 2})


def test_completion_indicator_and_command(temp_packet):
    mgr = PacketManager(packet_path=temp_packet)

    # Fill all 50 items with mock ratings to test completion logic
    full_rating = {
        "groundedness": 5,
        "relevance": 5,
        "actionability": 5,
        "completeness": 5,
        "policy_compliance": 5,
        "tone": 5,
        "hallucination": 0,
        "policy_violation": 0,
        "notes": "Test"
    }
    for idx in range(50):
        summary = mgr.save_item(idx, full_rating)

    assert summary["rated_count"] == 50
    assert summary["is_complete"] is True
    assert summary["percent_complete"] == 100.0
    assert summary["first_unrated_index"] is None
    assert summary["completion_command"] == "python scripts/evaluate.py --cached"


def test_http_api_endpoints(temp_packet):
    mgr = PacketManager(packet_path=temp_packet)

    class TestHandler(HumanEvalRequestHandler):
        manager = mgr

    # Bind to ephemeral port
    server = ThreadingHTTPServer(("127.0.0.1", 0), TestHandler)
    host, port = server.server_address

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    base_url = f"http://{host}:{port}"
    try:
        # GET /
        with urlopen(f"{base_url}/") as res:
            assert res.status == 200
            html = res.read().decode("utf-8")
            assert "ResolveAI" in html
            assert "Blinded Review" in html

        # GET /api/status
        with urlopen(f"{base_url}/api/status") as res:
            assert res.status == 200
            data = json.loads(res.read().decode("utf-8"))
            assert data["total"] == 50
            assert data["rated_count"] == 0

        # GET /api/item/0
        with urlopen(f"{base_url}/api/item/0") as res:
            assert res.status == 200
            item = json.loads(res.read().decode("utf-8"))
            assert item["index"] == 0
            assert "candidate_response" in item
            assert "system" not in item

        # POST /api/save
        save_payload = json.dumps({
            "index": 0,
            "ratings": {
                "groundedness": 5,
                "relevance": 5,
                "actionability": 5,
                "completeness": 5,
                "policy_compliance": 5,
                "tone": 5,
                "hallucination": 0,
                "policy_violation": 0,
                "notes": "API test"
            }
        }).encode("utf-8")

        req = Request(f"{base_url}/api/save", data=save_payload, headers={"Content-Type": "application/json"})
        with urlopen(req) as res:
            assert res.status == 200
            updated = json.loads(res.read().decode("utf-8"))
            assert updated["rated_count"] == 1
    finally:
        server.shutdown()
        server.server_close()
