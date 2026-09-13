"""Phase 4-C: query-embedding sharing before/after, deterministic path only (no LLM), warm process, novel messages.
  python scripts/phase4/c_latency.py   -> artifacts/agent/embedding_sharing.json
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path

import numpy as np

import resolveai  # noqa: F401
from resolveai.agent import AgentConfig, ResolveAI
from resolveai.retrieval.dense import Embedder

OUT = Path("artifacts/agent")
OUT.mkdir(parents=True, exist_ok=True)
WORDS = ["restarting", "freezing", "draining battery", "losing wifi", "deleting photos", "crashing apps", "typing I wrong", "overheating", "not charging", "lagging"]


def run(share: bool, n: int = 40) -> dict:
    agent = ResolveAI(cfg=AgentConfig(use_llm=False, write_traces=False, share_query_embedding=share))
    agent.resolve("warm up")
    tot, intent, retr = [], [], []
    for i in range(n):
        Embedder._memo.clear()
        r = agent.resolve(f"my iphone {i} keeps {WORDS[i % len(WORDS)]} since the update {uuid.uuid4().hex[:6]}")
        tot.append(r.latency["total"])
        intent.append(r.latency["intent"])
        retr.append(r.latency["retrieval"])
    pct = lambda v, q: round(float(np.percentile(v, q)), 1)  # noqa: E731
    return {"share_query_embedding": share, "n": n, "total_p50": pct(tot, 50), "total_p95": pct(tot, 95), "intent_p50": pct(intent, 50), "retrieval_p50": pct(retr, 50)}


def main() -> None:
    res = {"before": run(False), "after": run(True)}
    res["improvement_total_p50_ms"] = round(res["before"]["total_p50"] - res["after"]["total_p50"], 1)
    res["note"] = "deterministic path (no LLM): context + classifier + retrieval + policy + gate; the shared vector removes one BGE-small encode per message"
    (OUT / "embedding_sharing.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
