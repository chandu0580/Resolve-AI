"""Security baseline: no secrets in the tree, .env ignored, config never exposes keys, PII guard on traces/LLM."""
import re

from resolveai import config
from resolveai.observability import TraceRecorder
from resolveai.trust.pii import contains_unredacted_pii, redact_pii

ROOT = config.ROOT
KEY_PATTERNS = re.compile(r"sk-[A-Za-z0-9]{16,}|gsk_[A-Za-z0-9]{20,}|AQ\.[A-Za-z0-9_-]{30,}|AIza[0-9A-Za-z_-]{30,}|xoxb-[0-9A-Za-z-]{20,}|ghp_[A-Za-z0-9]{30,}")
SCAN_SUFFIXES = {".py", ".md", ".toml", ".txt", ".json", ".csv", ".yaml", ".yml", ".example", ".cfg", ".ini"}
SKIP_DIRS = {".git", ".cache", "node_modules", ".venv", "traces", "__pycache__"}
SKIP_FILES = {".env"}


def _files():
    for p in ROOT.rglob("*"):
        if p.is_file() and p.suffix in SCAN_SUFFIXES and not (SKIP_DIRS & set(p.parts)) and p.name not in SKIP_FILES and p.stat().st_size < 50_000_000:
            yield p


def test_no_api_keys_in_tracked_files():
    hits = []
    for p in _files():
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if KEY_PATTERNS.search(txt):
            hits.append(str(p.relative_to(ROOT)))
    assert not hits, f"secret-like strings found in: {hits}"


def test_env_is_gitignored_and_example_has_no_secrets():
    gi = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert ".env" in gi and "data/raw/" in gi and ".cache/" in gi
    ex = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert not KEY_PATTERNS.search(ex) and "your_key_here" in ex


def test_config_summary_masks_secret():
    s = config.masked_summary()
    assert s["llm_api_key"] in {"set", "missing"}
    assert config.LLM_API_KEY not in str(s) or not config.LLM_API_KEY


def test_pii_guard_detects_and_redaction_clears():
    raw = "call me on +1 (415) 555-0134 or john@x.com, order 123-4567890-1234567"
    assert contains_unredacted_pii(raw)
    assert not contains_unredacted_pii(redact_pii(raw).text)


def test_trace_refuses_unredacted_pii_and_never_stores_secrets():
    rec = TraceRecorder(message_id="m")
    rec.event("request_received", "api", text_redacted="battery dies, call <PHONE>")
    try:
        rec.event("request_received", "api", text_redacted="call 415-555-0134")
        raise AssertionError("unredacted PII accepted by trace")
    except ValueError:
        pass
    dumped = rec.finish("auto_handle").model_dump_json()
    assert "415-555" not in dumped and (not config.LLM_API_KEY or config.LLM_API_KEY not in dumped)
