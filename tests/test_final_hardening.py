"""Final product hardening: the backwards trace reader behind GET /traces, and newest-first listing across files. No agent, no model."""
import json

from fastapi.testclient import TestClient

from resolveai.api.app import create_app
from resolveai.api.service import AgentService, reverse_lines
from resolveai.api.settings import ApiSettings


def test_reverse_lines_matches_a_full_read_at_every_block_size(tmp_path):
    p = tmp_path / "t.jsonl"
    lines = ['{"a": 1}', "", '{"text": "café — \U0001F600"}', '{"b": ' + "9" * 300 + "}", "last line without newline"]
    p.write_bytes("\n".join(lines).encode("utf-8"))
    expected = list(reversed(p.read_text(encoding="utf-8").split("\n")))
    for block in (1, 2, 3, 7, 64, 1 << 16):
        assert list(reverse_lines(p, block=block)) == expected, block


def test_trace_listing_is_newest_first_across_files_and_stops_at_the_limit(tmp_path):
    d = tmp_path / "traces"
    d.mkdir()

    def trace(i):
        return json.dumps({"trace_id": f"{i:032x}", "started_at": f"2026-09-{10 + i // 100:02d}T00:00:{i % 60:02d}Z", "events": [], "final_decision": "HUMAN_HANDOFF"})

    (d / "2026-09-10.jsonl").write_text("\n".join(trace(i) for i in range(0, 100)) + "\n", encoding="utf-8")
    (d / "2026-09-11.jsonl").write_text("\n".join(trace(i) for i in range(100, 150)) + "\n{corrupted line\n", encoding="utf-8")
    s = ApiSettings.for_profile("test", trace_dir=d)
    items = TestClient(create_app(s, AgentService(s))).get("/api/v1/traces?limit=60").json()["items"]
    ids = [int(t["trace_id"], 16) for t in items]
    assert ids == list(range(149, 89, -1)), "newest first, the corrupted line skipped, the older file continued"
