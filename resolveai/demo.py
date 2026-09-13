"""Demo scenarios (synthetic messages, no real customer data), run through the SAME ResolveAI orchestrator the API uses.

    python -m resolveai demo              # live LLM where a scenario needs it (answers are cached after the first run)
    python -m resolveai demo --no-llm     # deterministic path only; scenarios needing the LLM report SKIP
    python -m resolveai demo --save       # also write artifacts/phase7/demo_results.json

Scenario F simulates a provider outage with a provider that always raises, and no cache, so the fallback path is real.
"""
from __future__ import annotations

import argparse
import json
import sys
import time

from resolveai import config
from resolveai.agent import AgentConfig, ResolveAI
from resolveai.llm import LLMClient
from resolveai.llm.provider import Completion
from resolveai.observability import TraceStore
from resolveai.schemas.core import AgentResult, ConversationContext, ConversationTurn

SCENARIOS = config.DATA_DIR / "demo" / "scenarios.json"
RESULTS = config.ROOT / "artifacts" / "phase7" / "demo_results.json"


class UnavailableProvider:
    """Simulated outage: every call fails the way a network/provider error would."""
    name = "simulated_outage"

    def complete(self, model, messages, *, temperature, max_tokens, json_mode, timeout_s) -> Completion:
        raise ConnectionError("simulated provider outage")


def load_scenarios() -> list[dict]:
    return json.loads(SCENARIOS.read_text(encoding="utf-8"))


def check(sc: dict, r: AgentResult) -> list[str]:
    exp, fails = sc["expect"], []
    if "action" in exp and r.action != exp["action"]:
        fails.append(f"action {r.action} != {exp['action']}")
    if "not_action" in exp and r.action == exp["not_action"]:
        fails.append(f"action must not be {exp['not_action']}")
    if "reason_code_in" in exp and r.decision.escalation.reason_code not in exp["reason_code_in"]:
        fails.append(f"reason_code {r.decision.escalation.reason_code} not in {exp['reason_code_in']}")
    if "max_llm_calls" in exp and r.usage.llm_calls > exp["max_llm_calls"]:
        fails.append(f"{r.usage.llm_calls} LLM calls > {exp['max_llm_calls']}")
    if "evidence_sufficient" in exp and r.evidence.sufficient != exp["evidence_sufficient"]:
        fails.append(f"evidence_sufficient {r.evidence.sufficient} != {exp['evidence_sufficient']}")
    if exp.get("has_citations") and not r.citations:
        fails.append("no citations on the automatic reply")
    if exp.get("has_handoff") and r.handoff is None:
        fails.append("no handoff packet")
    if exp.get("has_clarification") and r.clarification is None:
        fails.append("no clarification packet")
    if r.clarification is not None:
        for s in exp.get("question_excludes", []):
            if s.lower() in r.clarification.question.lower():
                fails.append(f"question re-asks provided detail: {s!r}")
    return fails


def build_agents(no_llm: bool, trace_dir) -> tuple[ResolveAI, ResolveAI]:
    store = TraceStore(trace_dir)
    live = ResolveAI(cfg=AgentConfig(use_llm=not no_llm), trace_store=store)
    outage = ResolveAI(kb=live.kb, retriever=live.retriever, intents=live.intents, llm=LLMClient(provider=UnavailableProvider(), model="simulated-outage", cache=None, max_retries=0),
                       cfg=AgentConfig(), trace_store=store)
    return live, outage


def run(no_llm: bool = False) -> list[dict]:
    live, outage = build_agents(no_llm, config.TRACE_DIR / "demo")
    rows = []
    for sc in load_scenarios():
        if sc["llm"] == "live" and live.llm is None:
            rows.append({"id": sc["id"], "title": sc["title"], "status": "SKIP", "why": "needs the LLM (LLM_API_KEY not set or --no-llm)"})
            continue
        agent = outage if sc["llm"] == "unavailable" else live
        *earlier, current = sc["conversation"]
        t0 = time.perf_counter()
        r = agent.resolve(current["text"], ConversationContext(turns=[ConversationTurn(**t) for t in earlier]), request_id=f"demo-{sc['id']}-{int(time.time())}")
        fails = check(sc, r)
        rows.append({"id": sc["id"], "title": sc["title"], "status": "FAIL" if fails else "PASS", "failures": fails, "action": r.action, "reason_code": r.decision.escalation.reason_code,
                     "rule": r.decision.escalation.rule, "evidence_level": r.evidence.sufficiency_level, "llm_calls": r.usage.llm_calls, "latency_ms": round((time.perf_counter() - t0) * 1000),
                     "response": r.response, "citations": [c.evidence_id for c in r.citations], "what_happened": r.summary.what_happened if r.summary else "",
                     "why": r.summary.why if r.summary else "", "next_step": r.summary.next_step if r.summary else "", "trace_id": r.trace_id})
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m resolveai demo")
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--save", action="store_true")
    a = ap.parse_args(argv)
    rows = run(no_llm=a.no_llm)
    if a.save:
        RESULTS.parent.mkdir(parents=True, exist_ok=True)
        RESULTS.write_text(json.dumps({"scenarios": rows, "no_llm": a.no_llm, "passed": sum(r["status"] == "PASS" for r in rows), "failed": sum(r["status"] == "FAIL" for r in rows),
                                       "skipped": sum(r["status"] == "SKIP" for r in rows)}, indent=1), encoding="utf-8")
    if a.json:
        print(json.dumps(rows, indent=1))
    else:
        for r in rows:
            print(f"\n[{r['status']}] {r['id']} {r['title']}")
            if r["status"] == "SKIP":
                print(f"  {r['why']}")
                continue
            print(f"  DECISION  {r['action']}  reason={r['reason_code']}  rule={r['rule']}  evidence={r['evidence_level']}  llm_calls={r['llm_calls']}  {r['latency_ms']} ms")
            print(f"  WHAT      {r['what_happened']}")
            print(f"  WHY       {r['why']}")
            print(f"  RESPONSE  {r['response']}")
            if r["citations"]:
                print(f"  CITES     {r['citations']}")
            print(f"  NEXT      {r['next_step']}")
            print(f"  TRACE ID  {r['trace_id']}")
            for f in r["failures"]:
                print(f"  !! {f}")
    return 1 if any(r["status"] == "FAIL" for r in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
