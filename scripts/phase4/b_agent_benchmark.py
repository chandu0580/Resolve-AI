"""Phase 4-B: end-to-end agent benchmark on the frozen golden set (once), plus a no-retrieval canned baseline.
  python scripts/phase4/b_agent_benchmark.py
Writes artifacts/agent/{agent_benchmark.json, agent_benchmark.md, per_query_golden_agent.jsonl, example_traces.jsonl,
handoff_examples.json, latency_report.md}. Real outputs only.
"""
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix, f1_score, precision_recall_fscore_support

import resolveai  # noqa: F401
from resolveai.agent import AgentConfig, ResolveAI
from resolveai.evaluation import load_golden
from resolveai.intelligence.context import parse_context
from resolveai.models.taxonomy import INTENT_NAMES
from resolveai.observability import TraceStore

OUT = Path("artifacts/agent")
OUT.mkdir(parents=True, exist_ok=True)
CANNED_BASELINE = "We'd love to help. DM us the details and we'll go from there."


def main() -> None:
    gold = load_golden()
    authors = pd.read_csv("data/golden/golden_customer_authors.csv", dtype=str).set_index("gid").customer_author.to_dict() if Path("data/golden/golden_customer_authors.csv").exists() else {}
    store = TraceStore(OUT / "traces")
    agent = ResolveAI(cfg=AgentConfig(), trace_store=store)
    recs, t_all = [], time.perf_counter()
    for g in gold.itertuples():
        r = agent.resolve(g.customer_message, parse_context(g.context), customer_author=authors.get(g.gid), created_at=g.created_at, message_id=g.gid)
        recs.append({"gid": g.gid, "gold_intent": g.intent, "gold_escalate": bool(g.should_escalate), "gold_reason": g.escalation_reason, "action": r.action,
                     "intent": r.intent.intent, "band": r.intent.confidence_band, "confidence": r.intent.confidence, "second_opinion": r.intent.second_opinion, "so_applied": r.intent.second_opinion_applied,
                     "evidence_sufficient": r.evidence.sufficient, "evidence_reason": r.evidence.sufficiency_reason, "risk": [k for k, v in r.risk.model_dump().items() if v is True and k != "is_actionable"],
                     "risk_source": r.risk.source, "reason_code": r.decision.escalation.reason_code, "rule": r.decision.escalation.rule, "blocking": r.decision.blocking, "response": r.response,
                     "evidence_refs": r.evidence_refs, "verified": (r.verification.verified if r.verification else None), "coverage": (r.verification.coverage if r.verification else None),
                     "verification_issues": ([i.check for i in r.verification.issues] if r.verification else []), "draft_attempts": (r.draft.attempts if r.draft else 0),
                     "stage_status": r.stage_status, "latency": r.latency, "usage": r.usage.model_dump(), "trace_id": r.trace_id,
                     "slices": {"short": len(g.customer_message) < 40, "multi_turn": int(g.n_context_turns) > 0, "multi_intent": bool(g.multi_intent), "insufficient_context": bool(g.insufficient_context),
                                "taxonomy_gap": bool(g.taxonomy_gap), "customer_seen_in_kb": str(g.customer_seen_in_kb).lower() == "true"}})
    wall = time.perf_counter() - t_all
    (OUT / "per_query_golden_agent.jsonl").write_text("\n".join(json.dumps(x) for x in recs), encoding="utf-8")

    # ---------------- metrics ----------------
    yi, pi = [r["gold_intent"] for r in recs], [r["intent"] for r in recs]
    intent = {"accuracy": round(float(np.mean([a == b for a, b in zip(yi, pi, strict=False)])), 4), "macro_f1": round(float(f1_score(yi, pi, average="macro", labels=INTENT_NAMES, zero_division=0)), 4),
              "second_opinion_applied": sum(r["so_applied"] for r in recs)}
    ye = [r["gold_escalate"] for r in recs]
    pe = [r["action"] == "HUMAN_HANDOFF" for r in recs]
    p, rc, f, _ = precision_recall_fscore_support(ye, pe, average="binary", zero_division=0)
    esc = {"precision": round(float(p), 4), "recall": round(float(rc), 4), "f1": round(float(f), 4), "confusion_gold_x_pred": confusion_matrix(ye, pe, labels=[False, True]).tolist(),
           "note": "positive = HUMAN_HANDOFF; gold positive = should_escalate. CLARIFICATION counts as not-handoff."}
    pe2 = [r["action"] != "AUTO_HANDLE" for r in recs]
    p2, rc2, f2, _ = precision_recall_fscore_support(ye, pe2, average="binary", zero_division=0)
    esc["non_autonomous_as_positive"] = {"precision": round(float(p2), 4), "recall": round(float(rc2), 4), "f1": round(float(f2), 4)}
    for name, pred in (("always_escalate", [True] * len(ye)), ("never_escalate", [False] * len(ye))):
        pp, rr, ff, _ = precision_recall_fscore_support(ye, pred, average="binary", zero_division=0)
        esc[f"baseline_{name}"] = {"precision": round(float(pp), 4), "recall": round(float(rr), 4), "f1": round(float(ff), 4)}
    actions = Counter(r["action"] for r in recs)
    rates = {a: round(actions.get(a, 0) / len(recs), 4) for a in ("AUTO_HANDLE", "CLARIFICATION_REQUIRED", "HUMAN_HANDOFF")}
    rates["insufficient_evidence_rate"] = round(sum(1 for r in recs if not r["evidence_sufficient"]) / len(recs), 4)
    rates["reason_codes"] = dict(Counter(r["reason_code"] for r in recs))
    rates["evidence_reasons"] = dict(Counter(r["evidence_reason"] for r in recs))
    auto = [r for r in recs if r["action"] == "AUTO_HANDLE"]
    drafted = [r for r in recs if r["draft_attempts"] > 0 and r["stage_status"].get("draft") == "ok"]
    resp = {"auto_replies": len(auto), "drafts_generated": len(drafted), "verified_share_of_drafts": round(sum(1 for r in drafted if r["verified"]) / len(drafted), 4) if drafted else None,
            "mean_evidence_coverage_auto": round(float(np.mean([r["coverage"] for r in auto])), 3) if auto else None,
            "auto_with_evidence_refs": sum(1 for r in auto if r["evidence_refs"]), "redraft_share": round(sum(1 for r in drafted if r["draft_attempts"] == 2) / len(drafted), 4) if drafted else None,
            "verification_issue_counts": dict(Counter(i for r in drafted for i in r["verification_issues"])),
            "auto_on_gold_should_escalate": sum(1 for r in auto if r["gold_escalate"]), "policy_compliance_lexical": round(sum(1 for r in auto if not any(i in ("no_url", "no_handle", "no_promise", "no_internal_metadata", "no_pii") for i in r["verification_issues"])) / len(auto), 4) if auto else None}
    baseline = {"canned_reply": CANNED_BASELINE, "escalation": "never (always replies)", "intent": "majority class",
                "note": "message -> canned DM line, no retrieval, no verification; it 'auto-handles' 100% and is safe only because it says nothing"}
    slices = {}
    for s in recs[0]["slices"]:
        rs = [r for r in recs if r["slices"][s]]
        if rs:
            slices[s] = {"n": len(rs), "auto_rate": round(sum(r["action"] == "AUTO_HANDLE" for r in rs) / len(rs), 3), "handoff_rate": round(sum(r["action"] == "HUMAN_HANDOFF" for r in rs) / len(rs), 3),
                         "intent_acc": round(sum(r["intent"] == r["gold_intent"] for r in rs) / len(rs), 3), "escalation_recall": (round(sum(r["action"] == "HUMAN_HANDOFF" for r in rs if r["gold_escalate"]) / max(1, sum(r["gold_escalate"] for r in rs)), 3))}
    lat = {}
    for k in ("context", "intent", "second_opinion", "retrieval", "risk", "policy", "draft", "verification", "output_gate", "handoff", "total"):
        v = [r["latency"].get(k) for r in recs if r["latency"].get(k) is not None]
        if v:
            lat[k] = {"p50": round(float(np.percentile(v, 50)), 1), "p95": round(float(np.percentile(v, 95)), 1), "n": len(v)}
    usage = {"llm_calls_per_message": round(float(np.mean([r["usage"]["llm_calls"] for r in recs])), 3), "live_calls_per_message": round(float(np.mean([r["usage"]["live_calls"] for r in recs])), 3),
             "cache_hit_rate": round(sum(r["usage"]["cache_hits"] for r in recs) / max(1, sum(r["usage"]["llm_calls"] for r in recs)), 4),
             "tokens_in_per_message": round(float(np.mean([r["usage"]["tokens_in"] for r in recs])), 1), "tokens_out_per_message": round(float(np.mean([r["usage"]["tokens_out"] for r in recs])), 1),
             "estimated_cost_usd_per_message": round(float(np.mean([r["usage"]["estimated_cost_usd"] for r in recs])), 6), "fallbacks": sum(r["usage"]["fallbacks"] for r in recs),
             "calls_by_action": {a: round(float(np.mean([r["usage"]["llm_calls"] for r in recs if r["action"] == a])), 2) for a in actions}, "wall_seconds": round(wall, 1)}
    report = {"n": len(recs), "intent": intent, "escalation": esc, "rates": rates, "response": resp, "baseline": baseline, "slices": slices, "latency_ms": lat, "usage": usage}
    (OUT / "agent_benchmark.json").write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")

    # ---------------- examples ----------------
    ex, seen = [], Counter()
    for r in recs:
        if seen[r["action"]] < 3:
            t = store.read(r["trace_id"])
            if t:
                ex.append(t.model_dump())
                seen[r["action"]] += 1
    (OUT / "example_traces.jsonl").write_text("\n".join(json.dumps(x, default=str) for x in ex), encoding="utf-8")
    ho = []
    for r in recs:
        if r["action"] == "HUMAN_HANDOFF" and len(ho) < 6 and r["reason_code"] not in {h["reason"] for h in ho}:
            ho.append({"gid": r["gid"], "reason": r["reason_code"], "trace_id": r["trace_id"]})
    packets = []
    for h in ho:
        g = gold[gold.gid == h["gid"]].iloc[0]
        rr = agent.resolve(g.customer_message, parse_context(g.context), customer_author=authors.get(g.gid), created_at=g.created_at, message_id=g.gid)
        if rr.handoff:
            packets.append({"gid": h["gid"], "packet": rr.handoff.model_dump()})
    (OUT / "handoff_examples.json").write_text(json.dumps(packets, indent=1, default=str), encoding="utf-8")

    # ---------------- markdown ----------------
    L = ["# ResolveAI end-to-end benchmark (Phase 4)", "", f"Golden set, 197 rows, evaluated once with the frozen classifier, gate-v2, policy-v2, output-gate-v1, second-opinion policy `{agent.policy}`. Wall time {wall:.0f} s.", "",
         "## Actions", "", "| AUTO_HANDLE | CLARIFICATION_REQUIRED | HUMAN_HANDOFF | insufficient evidence |", "|---|---|---|---|",
         f"| {rates['AUTO_HANDLE']} | {rates['CLARIFICATION_REQUIRED']} | {rates['HUMAN_HANDOFF']} | {rates['insufficient_evidence_rate']} |", "",
         f"Reason codes: `{rates['reason_codes']}`", f"Evidence gate reasons: `{rates['evidence_reasons']}`", "",
         "## Intent", "", f"accuracy {intent['accuracy']}, macro-F1 {intent['macro_f1']} (second opinion applied on {intent['second_opinion_applied']} rows)", "",
         "## Escalation (HUMAN_HANDOFF vs gold should_escalate)", "", f"precision {esc['precision']}, recall {esc['recall']}, F1 {esc['f1']}; confusion gold x pred `{esc['confusion_gold_x_pred']}`",
         f"Treating any non-autonomous action as positive: {esc['non_autonomous_as_positive']}. Baselines: always-escalate {esc['baseline_always_escalate']}, never-escalate {esc['baseline_never_escalate']}.", "",
         "## Responses", "", f"`{json.dumps(resp)}`", "", "## Baseline (no retrieval)", "", f"`{json.dumps(baseline)}`", "",
         "## Slices", "", "| slice | n | auto | handoff | intent acc | escalation recall |", "|---|---|---|---|---|---|"]
    L += [f"| {s} | {v['n']} | {v['auto_rate']} | {v['handoff_rate']} | {v['intent_acc']} | {v['escalation_recall']} |" for s, v in slices.items()]
    L += ["", "## Latency (ms) and cost", "", "| stage | p50 | p95 | n |", "|---|---|---|---|"] + [f"| {k} | {v['p50']} | {v['p95']} | {v['n']} |" for k, v in lat.items()]
    L += ["", f"`{json.dumps(usage)}`", ""]
    (OUT / "agent_benchmark.md").write_text("\n".join(L), encoding="utf-8")
    (OUT / "latency_report.md").write_text("\n".join(["# Agent latency and cost (golden run)", "", "| stage | p50 ms | p95 ms | n |", "|---|---|---|---|"] + [f"| {k} | {v['p50']} | {v['p95']} | {v['n']} |" for k, v in lat.items()] + ["", f"`{json.dumps(usage)}`", "", "Second-opinion calls were cached from Phase 3 (same prompt version); risk, draft and verify calls were live. Costs use GLM-5.2 list price; the proxy's billing is unknown."]), encoding="utf-8")
    print("\n".join(L[:30]))
    print("usage:", usage)


if __name__ == "__main__":
    main()
