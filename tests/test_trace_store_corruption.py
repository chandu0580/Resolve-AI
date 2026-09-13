"""A corrupted or truncated trace line must not take the audit trail down.

Found by the Phase 10 adversarial suite (case 20): one unparseable JSONL line made GET /api/v1/traces and GET /api/v1/traces/{id}
return 500. The listing now skips and counts such lines, and a corrupted record is never served.
"""
from resolveai.observability import TraceStore

TID = "0123456789abcdef0123456789abcdef"


def test_a_corrupted_record_is_not_served_and_does_not_raise(tmp_path):
    store = TraceStore(tmp_path)
    (tmp_path / "2026-09-11.jsonl").write_text('{"trace_id":"' + TID + '", this line was truncated\n', encoding="utf-8")
    assert store.read(TID) is None


def test_an_unknown_id_in_a_store_with_garbage_is_simply_not_found(tmp_path):
    store = TraceStore(tmp_path)
    (tmp_path / "2026-09-11.jsonl").write_text("not json at all\n\n{\n", encoding="utf-8")
    assert store.read(TID) is None
