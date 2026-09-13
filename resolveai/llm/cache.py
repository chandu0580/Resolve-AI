"""Deterministic LLM response cache.

Contract: the cache key is SHA-256 over (model, prompt_version, messages, parameters). Python's built-in hash() is
salted per process and MUST NOT be used (it silently defeated the cache in the Phase 1A benchmark). Keys are stable
across processes, machines and Python versions, which is what makes evaluation runs reproducible from a committed cache.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from resolveai import config


def cache_key(model: str, prompt_version: str, messages: list[dict[str, str]], params: dict[str, Any]) -> str:
    payload = {"model": model, "prompt_version": prompt_version, "messages": messages, "params": params}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class DiskCache:
    def __init__(self, root: Path | None = None):
        self.root = root or (config.CACHE_DIR / "llm")
        self.root.mkdir(parents=True, exist_ok=True)
        self.hits = 0
        self.misses = 0

    def _path(self, key: str) -> Path:
        return self.root / key[:2] / f"{key}.json"

    def get(self, key: str) -> dict[str, Any] | None:
        p = self._path(key)
        if p.exists():
            self.hits += 1
            return json.loads(p.read_text(encoding="utf-8"))
        self.misses += 1
        return None

    def put(self, key: str, record: dict[str, Any]) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
