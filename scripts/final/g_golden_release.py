"""Phase 10-G: the golden evaluation of the RELEASE configuration, run once, because the pre-registered dev decision changed it.

  python -u scripts/final/g_golden_release.py run      # the release agent on the frozen golden set (once; refuses to overwrite)
  python -u scripts/final/g_golden_release.py judge    # the frozen rubric-v1 GLM-5.2 judge on that run's responses (once)

Why this run exists: artifacts/final/risk_experiment/PREREGISTRATION.md fixed in advance that an accepted candidate is enabled in the
release configuration and the golden set is then run ONCE for that configuration as a new run, never overwriting phase9_final. The
candidate was decided on DEV (AI-labelled rows) before this script ran; nothing here is tuned, and the golden run is not repeated.
Configuration: artifacts/final/risk_experiment/decision.json (risk_schema, risk_corroborate). Everything else is the Phase 9 agent.
Guarantees (as scripts/phase9/d_golden_final.py): golden hash verified before and after; the same SHA-256 response cache, so unchanged
prompts replay and only changed prompts go live (live-call count recorded); outputs under artifacts/final/evaluation/ only.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from resolveai.agent import AgentConfig, ResolveAI  # noqa: E402
from resolveai.agent.orchestrator import PIPELINE_VERSION  # noqa: E402
from resolveai.evaluation import load_golden  # noqa: E402
from resolveai.evaluation.judge import judge_one  # noqa: E402
from resolveai.evaluation.records import read_records, write_records  # noqa: E402
from resolveai.evaluation.systems import run_agent  # noqa: E402
from resolveai.llm import DiskCache, LLMClient, OpenAICompatibleProvider  # noqa: E402
from resolveai.retrieval import KnowledgeBase, RetrieverConfig  # noqa: E402

OUT = ROOT / "artifacts" / "final" / "evaluation"
RUNS = OUT / "runs"
DECISION = ROOT / "artifacts" / "final" / "risk_experiment" / "decision.json"
SYSTEM = "final_release"


def release_overrides() -> dict:
    if not DECISION.exists():
        raise SystemExit("artifacts/final/risk_experiment/decision.json is missing: the dev decision must be frozen first")
    d = json.loads(DECISION.read_text(encoding="utf-8"))
    if not d.get("accepted"):
        raise SystemExit("the dev candidate was rejected: the release configuration equals phase9_final, which is already evaluated; nothing to run")
    return {"risk_schema": d["risk_schema"], "risk_corroborate": tuple(d["risk_corroborate"])}


def cmd_run() -> None:
    RUNS.mkdir(parents=True, exist_ok=True)
    path = RUNS / f"{SYSTEM}.jsonl"
    if path.exists():
        raise SystemExit(f"{path} already exists; the release golden run is not repeated or overwritten")
    over = release_overrides()
    cfg = AgentConfig(write_traces=False, **over)
    if AgentConfig().risk_corroborate != cfg.risk_corroborate:
        raise SystemExit("the code's default AgentConfig does not match the frozen release decision; the run would not describe the release")
    gold = load_golden()
    authors = pd.read_csv(ROOT / "data/golden/golden_customer_authors.csv", dtype=str).set_index("gid").customer_author.to_dict()
    kb = KnowledgeBase.build(dense_models=[RetrieverConfig().model], with_bm25=False)
    agent = ResolveAI(kb=kb, llm=LLMClient(provider=OpenAICompatibleProvider(), cache=DiskCache()), cfg=cfg)
    t0 = time.perf_counter()
    recs = run_agent(agent, gold, authors, SYSTEM, progress=lambda k: print(f"  {SYSTEM}: {k}/{len(gold)}", flush=True))
    write_records(path, recs)
    load_golden()
    meta = {"system": SYSTEM, "agent_config": {k: list(v) if isinstance(v, tuple) else v for k, v in cfg.__dict__.items()}, "pipeline_version": PIPELINE_VERSION,
            "config_hash": agent.versions.config_hash, "n": len(recs), "failed": sum(r.failed for r in recs), "live_calls": int(sum(r.live_calls for r in recs)),
            "model_calls": int(sum(r.llm_calls for r in recs)), "wall_seconds": round(time.perf_counter() - t0, 1),
            "golden_sha256": json.loads((ROOT / "data/golden/golden_freeze_manifest.json").read_text())["sha256"], "run_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "decision": "artifacts/final/risk_experiment/decision.json"}
    (RUNS / f"{SYSTEM}.meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(json.dumps(meta, indent=1))


def cmd_judge() -> None:
    path = OUT / f"judge_{SYSTEM}.jsonl"
    if path.exists():
        raise SystemExit(f"{path} already exists; not re-judging")
    recs = read_records(RUNS / f"{SYSTEM}.jsonl")
    client = LLMClient(provider=OpenAICompatibleProvider(), cache=DiskCache())
    rows = []
    for k, rec in enumerate(sorted(recs, key=lambda r: r.gid), start=1):
        rows.append(judge_one(client, rec))
        if k % 25 == 0:
            print(f"  judged {k}/{len(recs)}", flush=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    print(json.dumps({"system": SYSTEM, "n": len(rows), "failures": sum(r["failed"] for r in rows), "live_calls": client.usage.live_calls, "cache_hits": client.usage.cache_hits}))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["run", "judge"])
    a = ap.parse_args()
    cmd_run() if a.command == "run" else cmd_judge()


if __name__ == "__main__":
    main()
