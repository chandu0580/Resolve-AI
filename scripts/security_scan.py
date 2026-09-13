"""Repository security scan (standard library + git; no external scanners).

  python scripts/security_scan.py

Scope: every file git would commit (tracked + untracked but not ignored).
  1. secret files (.env, *.pem, *.key, id_rsa ...) must not be committable
  2. no committable file contains the ACTUAL secret values from .env (compared in memory; values are never printed)
  3. generic credential patterns (OpenAI/Groq/Google/GitHub/Slack tokens, private keys, long key assignments)
  4. .env.example holds placeholders only
  5. the configured LLM endpoint address from .env does not appear in committable files (infrastructure detail)
  6. trace files (traces/, artifacts/**/traces*/) contain no unredacted PII
  7. no committable file larger than 50 MB
Writes artifacts/phase7/security_scan.json. Exit code 1 if any finding fails.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from resolveai.trust.pii import contains_unredacted_pii  # noqa: E402

BINARY = {".npy", ".faiss", ".png", ".jpg", ".jpeg", ".gif", ".pdf", ".parquet", ".pkl", ".joblib", ".zip", ".gz", ".ico", ".woff", ".woff2"}
SECRET_FILES = re.compile(r"(^|/)(\.env|.*\.pem|.*\.key|id_rsa|id_ed25519|credentials\.json|secrets?\.(json|ya?ml))$")
PATTERNS = {
    "openai_style_key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"),
    "groq_key": re.compile(r"\bgsk_[A-Za-z0-9]{20,}"),
    "google_api_key": re.compile(r"\bAIza[0-9A-Za-z_-]{35}"),
    "github_token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36}"),
    "slack_token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}"),
    "private_key_block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "key_assignment": re.compile(r"(?i)\b(api[_-]?key|secret|access[_-]?token|password)\b\s*[=:]\s*['\"]?[A-Za-z0-9_\-]{24,}"),
}
MAX_BYTES = 50 * 1024 * 1024


def committable() -> list[str]:
    out = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=ROOT, capture_output=True, check=True).stdout
    return sorted({p for p in out.decode("utf-8").split("\0") if p})


def env_values() -> dict[str, str]:
    p = ROOT / ".env"
    vals = {}
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                vals[k.strip()] = v.strip().strip("'\"")
    return vals


# System-generated fields are not customer text: the PII regexes misread ISO timestamps ("2026-09-10T10") as long ids and
# 10-digit runs inside hex trace ids as phone numbers. Every other string in a trace (event data, packets, summaries) is checked.
STRUCTURAL_KEYS = {"trace_id", "request_id", "message_id", "config_hash", "ts", "started_at", "finished_at", "created_at"}


def walk_strings(obj, key=None):
    if isinstance(obj, str):
        if key not in STRUCTURAL_KEYS:
            yield obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from walk_strings(v, k)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk_strings(v, key)


def main() -> int:
    files = committable()
    env = env_values()
    secrets = {k: v for k, v in env.items() if re.search(r"KEY|TOKEN|SECRET|PASSWORD", k) and len(v) >= 12 and v not in ("your_key_here",)}
    endpoint_hosts = {urlparse(v).hostname for k, v in env.items() if k.endswith("BASE_URL") and v}
    endpoint_hosts = {h for h in endpoint_hosts if h and not h.endswith(("api.z.ai", "googleapis.com", "groq.com"))}   # public vendor hosts are documentation, not infrastructure
    findings: list[dict] = []
    total_bytes, largest = 0, []
    for rel in files:
        p = ROOT / rel
        if not p.is_file():
            continue
        size = p.stat().st_size
        total_bytes += size
        largest.append((size, rel))
        if SECRET_FILES.search(rel.replace("\\", "/")):
            findings.append({"check": "secret_file_committable", "file": rel})
        if size > MAX_BYTES:
            findings.append({"check": "file_too_large", "file": rel, "bytes": size})
        if p.suffix.lower() in BINARY or size > 20 * 1024 * 1024:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for name, value in secrets.items():
            if value in text:
                findings.append({"check": "env_secret_value_in_file", "file": rel, "variable": name})   # the value itself is never recorded
        for host in endpoint_hosts:
            if host in text:
                findings.append({"check": "llm_endpoint_address_in_file", "file": rel})
        for name, pat in PATTERNS.items():
            if pat.search(text):
                findings.append({"check": f"pattern:{name}", "file": rel})
    example = ROOT / ".env.example"
    if example.exists():
        for line in example.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                if re.search(r"KEY|TOKEN|SECRET", k) and v.strip() not in ("", "your_key_here"):
                    findings.append({"check": "env_example_not_placeholder", "variable": k.strip()})
    trace_files = sorted(set((ROOT / "traces").rglob("*.jsonl")) | set(ROOT.glob("artifacts/**/traces*/**/*.jsonl")))
    pii_hits, trace_lines = 0, 0
    for tf in trace_files:
        for line in tf.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            trace_lines += 1
            if any(contains_unredacted_pii(s) for s in walk_strings(json.loads(line))):
                pii_hits += 1
                findings.append({"check": "unredacted_pii_in_trace", "file": str(tf.relative_to(ROOT)).replace("\\", "/")})
    largest.sort(reverse=True)
    report = {"committable_files": len(files), "committable_bytes": total_bytes, "committable_mb": round(total_bytes / 1e6, 1),
              "largest_files": [{"file": f, "mb": round(s / 1e6, 2)} for s, f in largest[:10]], "env_secret_variables_checked": sorted(secrets),
              "trace_files_scanned": len(trace_files), "trace_records_scanned": trace_lines, "trace_records_with_pii": pii_hits,
              ".env_committable": ".env" in files, "findings": findings, "passed": not findings}
    out = ROOT / "artifacts" / "phase7" / "security_scan.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "largest_files"}, indent=1))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
