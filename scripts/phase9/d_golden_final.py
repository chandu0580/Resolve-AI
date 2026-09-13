"""Phase 9-D: the FINAL golden evaluation, run ONCE per system after every dev decision was frozen. Nothing here is tuned.

  python -u scripts/phase9/d_golden_final.py run phase8_config     # the Phase 8 decision logic on the current code (risk-flags-v2, no corroboration)
  python -u scripts/phase9/d_golden_final.py run phase9_final      # the frozen Phase 9 configuration (artifacts/phase9/risk/frozen_config.json)
  python -u scripts/phase9/d_golden_final.py judge phase9_final    # frozen rubric-v1 GLM judge on that run's responses
  python    scripts/phase9/d_golden_final.py report                # Baseline / Phase 5 / Phase 8 / Phase 9 comparison with bootstrap CIs

Guarantees:
- the golden hash is verified before and after every run (load_golden); the frozen Phase 6 artifacts under artifacts/evaluation are
  READ ONLY here; every output goes to artifacts/phase9/evaluation/;
- an existing run or judge file is never overwritten (earlier results are not silently replaced);
- model calls go through the same SHA-256 response cache as Phase 6, so unchanged prompts replay the recorded responses and only
  prompts that changed (or failed in the original run) are sent live; the live-call count is recorded in each run's meta file.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from resolveai.agent import AgentConfig, ResolveAI  # noqa: E402
from resolveai.agent.orchestrator import PIPELINE_VERSION  # noqa: E402
from resolveai.evaluation import load_golden  # noqa: E402
from resolveai.evaluation.judge import judge_one  # noqa: E402
from resolveai.evaluation.records import read_records, write_records  # noqa: E402
from resolveai.evaluation.reporting import gold_map, judge_summary, load_judge, paired_comparisons, system_report  # noqa: E402
from resolveai.evaluation.systems import run_agent  # noqa: E402
from resolveai.llm import DiskCache, LLMClient, OpenAICompatibleProvider  # noqa: E402
from resolveai.retrieval import KnowledgeBase, RetrieverConfig  # noqa: E402

FROZEN = ROOT / "artifacts" / "evaluation"                 # Phase 6 (Phase 5 system + baselines): read only
OUT = ROOT / "artifacts" / "phase9" / "evaluation"
RUNS = OUT / "runs"
FROZEN_CONFIG = ROOT / "artifacts" / "phase9" / "risk" / "frozen_config.json"
BASELINES = ["B0_trivial", "B0_trivial_always_handoff", "B1_simple_ml", "B2_direct_llm"]
COLUMNS = [("Baseline B1 (simple ML)", "B1_simple_ml", "frozen"), ("Baseline B2 (direct LLM)", "B2_direct_llm", "frozen"), ("Phase 5 (evaluated in Phase 6)", "resolveai_full", "frozen"),
           ("Phase 8 configuration", "phase8_config", "phase9"), ("Phase 8 = Phase 9 final", "phase9_final", "phase9")]
# Why there is normally no separate Phase 8 run: Phase 8 changed no agent decision (UI only), and the Phase 9 dev experiment rejected every
# risk candidate, so the frozen Phase 9 decision configuration IS the Phase 8 one. The Phase 9 hardening changes (request budget, failure
# classification, evidence quarantine, sentence-end phone redaction, evidence re-redaction) change no golden input: 0 golden messages or
# contexts match the corrected phone pattern and 0 corpus rows match the injection detector. Running `phase8_config` separately would
# re-run the same configuration on the same inputs, so the column is only filled if that run exists.


def agent_config(system: str) -> dict:
    if system == "phase8_config":
        return {}
    if system == "phase9_final":
        if not FROZEN_CONFIG.exists():
            raise SystemExit("artifacts/phase9/risk/frozen_config.json is missing: freeze the dev decision before the final golden run")
        cfg = json.loads(FROZEN_CONFIG.read_text(encoding="utf-8"))
        return {"risk_schema": cfg["risk_schema"], "risk_corroborate": tuple(cfg["risk_corroborate"])}
    raise SystemExit(f"unknown system {system}")


def cmd_run(system: str) -> None:
    RUNS.mkdir(parents=True, exist_ok=True)
    path = RUNS / f"{system}.jsonl"
    if path.exists():
        raise SystemExit(f"{path} already exists; the final golden run is not repeated or overwritten")
    over = agent_config(system)
    gold = load_golden()
    authors = pd.read_csv(ROOT / "data/golden/golden_customer_authors.csv", dtype=str).set_index("gid").customer_author.to_dict()
    kb = KnowledgeBase.build(dense_models=[RetrieverConfig().model], with_bm25=False)
    llm = LLMClient(provider=OpenAICompatibleProvider(), cache=DiskCache())
    agent = ResolveAI(kb=kb, llm=llm, cfg=AgentConfig(write_traces=False, **over))
    t0 = time.perf_counter()
    recs = run_agent(agent, gold, authors, system, progress=lambda k: print(f"  {system}: {k}/{len(gold)}", flush=True))
    write_records(path, recs)
    load_golden()   # re-verify the frozen hash after the run
    meta = {"system": system, "agent_config": {k: list(v) if isinstance(v, tuple) else v for k, v in AgentConfig(write_traces=False, **over).__dict__.items()},
            "pipeline_version": PIPELINE_VERSION, "config_hash": agent.versions.config_hash, "n": len(recs), "failed": sum(r.failed for r in recs),
            "live_calls": int(sum(r.live_calls for r in recs)), "model_calls": int(sum(r.llm_calls for r in recs)), "wall_seconds": round(time.perf_counter() - t0, 1),
            "golden_sha256": json.loads((ROOT / "data/golden/golden_freeze_manifest.json").read_text())["sha256"], "run_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    (RUNS / f"{system}.meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(json.dumps(meta, indent=1))


def cmd_judge(system: str) -> None:
    path = OUT / f"judge_{system}.jsonl"
    if path.exists():
        raise SystemExit(f"{path} already exists; not re-judging")
    recs = read_records(RUNS / f"{system}.jsonl")
    client = LLMClient(provider=OpenAICompatibleProvider(), cache=DiskCache())
    rows = []
    for k, rec in enumerate(sorted(recs, key=lambda r: r.gid), start=1):
        rows.append(judge_one(client, rec))
        if k % 25 == 0:
            print(f"  judged {k}/{len(recs)}", flush=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    print(json.dumps({"system": system, "n": len(rows), "failures": sum(r["failed"] for r in rows), "live_calls": client.usage.live_calls, "cache_hits": client.usage.cache_hits}))


def _fmt(ci: dict | None, digits: int = 3) -> str:
    """A bootstrap interval (`point`) or a paired-bootstrap difference (`difference`, with whether it excludes zero)."""
    if not ci:
        return "n/a"
    if "difference" in ci:
        return f"{ci['difference']:+.{digits}f} [{ci['ci_low']:+.{digits}f}, {ci['ci_high']:+.{digits}f}]" + (" (excludes 0)" if ci.get("interval_excludes_zero") else "")
    return f"{ci['point']:.{digits}f} [{ci['ci_low']:.{digits}f}, {ci['ci_high']:.{digits}f}]"


def cmd_report() -> None:
    gold = load_golden()
    gm = gold_map(gold)
    runs: dict[str, list] = {}
    for _, name, src in COLUMNS:
        p = (FROZEN / "runs" if src == "frozen" else RUNS) / f"{name}.jsonl"
        if p.exists():
            runs[name] = read_records(p)
    reports = {s: system_report(recs, gold, gm, n_boot=1000, seed=42) for s, recs in runs.items()}
    judge_rows = [j for j in load_judge(FROZEN / "judge_results.jsonl") if j["system"] in runs]
    for s in ("phase8_config", "phase9_final"):
        jp = OUT / f"judge_{s}.jsonl"
        if jp.exists():
            judge_rows += [json.loads(line) for line in jp.read_text(encoding="utf-8").splitlines() if line.strip()]
    judged = judge_summary(judge_rows, list(runs), gm, runs, n_boot=1000, seed=42)
    comparisons = {}
    if "phase9_final" in runs:
        comparisons = paired_comparisons(runs, gm, "phase9_final", [s for s in ("resolveai_full", "phase8_config", "B2_direct_llm") if s in runs], n_boot=1000, seed=42)
    changed = []
    if "phase9_final" in runs and "resolveai_full" in runs:
        p5 = {r.gid: r for r in runs["resolveai_full"]}
        for r in sorted(runs["phase9_final"], key=lambda x: x.gid):
            old = p5.get(r.gid)
            if old and (old.action != r.action or old.reason_code != r.reason_code):
                g = gm[r.gid]
                changed.append({"gid": r.gid, "phase5": f"{old.action}/{old.reason_code}", "phase9": f"{r.action}/{r.reason_code}", "gold_should_escalate": g["should_escalate"],
                                "gold_reason": g["escalation_reason"], "gold_intent": g["intent"], "message": r.message[:140]})
    evidence = {s: dict(pd.Series([r.evidence_level for r in recs if r.evidence_level]).value_counts()) for s, recs in runs.items() if s not in BASELINES}
    out = {"columns": [c[0] for c in COLUMNS if c[1] in runs], "systems": list(runs), "reports": reports, "judge": judged, "paired_vs_phase9_final": comparisons,
           "action_changes_phase5_to_phase9": changed, "evidence_levels": {s: {k: int(v) for k, v in d.items()} for s, d in evidence.items()},
           "golden_sha256": json.loads((ROOT / "data/golden/golden_freeze_manifest.json").read_text())["sha256"], "n_boot": 1000, "seed": 42}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "final_metrics.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")

    def row(label, fn):
        return f"| {label} | " + " | ".join(fn(s) for _, s, _ in COLUMNS if s in runs) + " |"

    def jmean(s, dim):
        d = judged["systems"].get(s)
        return _fmt(d["bootstrap"].get(dim), 2) if d and d["bootstrap"].get(dim) else "n/a"

    def jrate(s, key):
        d = judged["systems"].get(s)
        return f"{d['rates'][key]:.3f}" if d and d["rates"].get(key) is not None else "n/a"

    heads = [c[0] for c in COLUMNS if c[1] in runs]
    L = ["# Phase 9 final evaluation (golden set, n=197)", "", f"Golden sha256 `{out['golden_sha256']}`. 95% bootstrap intervals (1,000 resamples, seed 42). Baselines and Phase 5 are the frozen "
         "Phase 6 runs, re-scored with the same code; Phase 8 and Phase 9 are single runs of the current code.", "",
         "| metric | " + " | ".join(heads) + " |", "|---|" + "---|" * len(heads),
         row("intent accuracy", lambda s: _fmt(reports[s]["intent"]["bootstrap"]["accuracy"])),
         row("intent macro-F1", lambda s: _fmt(reports[s]["intent"]["bootstrap"]["macro_f1"])),
         row("escalation precision", lambda s: f"{reports[s]['escalation']['precision']:.3f}"),
         row("escalation recall", lambda s: _fmt(reports[s]["escalation"]["bootstrap"]["recall"])),
         row("escalation F1", lambda s: _fmt(reports[s]["escalation"]["bootstrap"]["f1"])),
         row("missed escalations (FN)", lambda s: str(reports[s]["escalation"]["fn"])),
         row("unnecessary escalations (FP)", lambda s: str(reports[s]["escalation"]["fp"])),
         row("auto / clarify / handoff", lambda s: f"{reports[s]['autonomy']['auto_handle_rate']:.3f} / {reports[s]['autonomy']['clarification_rate']:.3f} / {reports[s]['autonomy']['handoff_rate']:.3f}"),
         row("safe auto-handle rate", lambda s: _fmt(reports[s]["autonomy"]["bootstrap"]["safe_auto_handle_rate"])),
         row("unsafe autonomous replies", lambda s: str(reports[s]["autonomy"]["unsafe_auto_handle_count"])),
         row("grounded auto replies", lambda s: str(reports[s]["autonomy"]["grounded_auto_handle_count"])),
         row("judge groundedness (1-5)", lambda s: jmean(s, "groundedness")),
         row("judge hallucination rate", lambda s: jrate(s, "hallucination")),
         row("judge policy-violation rate", lambda s: jrate(s, "policy_violation")),
         row("p50 / p95 latency ms (as run)", lambda s: f"{reports[s]['cost_latency']['p50_latency_ms']} / {reports[s]['cost_latency']['p95_latency_ms']}"),
         row("model calls per message", lambda s: f"{reports[s]['cost_latency']['llm_calls_per_message']}"),
         row("live model calls per message", lambda s: f"{reports[s]['cost_latency']['live_calls_per_message']}"),
         row("est. cost per message (USD)", lambda s: f"{reports[s]['cost_latency']['estimated_cost_usd_per_message']}"),
         row("failed executions", lambda s: str(reports[s]["failed"])), ""]
    if comparisons:
        L += ["## Paired differences (Phase 9 final minus other; 95% paired bootstrap)", ""]
        for k, v in comparisons.items():
            L.append(f"- `{k}`: " + "; ".join(f"{m} {_fmt(ci)}" for m, ci in v.items()))
        L.append("")
    L += [f"## Decisions that changed from Phase 5 to Phase 9 ({len(changed)} rows)", "", "| gid | Phase 5 | Phase 9 | gold should_escalate | gold reason |", "|---|---|---|---|---|"]
    L += [f"| {c['gid']} | {c['phase5']} | {c['phase9']} | {c['gold_should_escalate']} | {c['gold_reason']} |" for c in changed]
    (OUT / "final_metrics.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["run", "judge", "report"])
    ap.add_argument("system", nargs="?")
    a = ap.parse_args()
    if a.command == "run":
        cmd_run(a.system)
    elif a.command == "judge":
        cmd_judge(a.system)
    else:
        cmd_report()
    np.random.seed(0)


if __name__ == "__main__":
    main()
