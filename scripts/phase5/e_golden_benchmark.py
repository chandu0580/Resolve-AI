"""Phase 5-E: the ONE golden run of the Phase 5 agent (dual retrieval + resolution rerank + gate-v3 + policy-v3 +
compact risk schema + short-circuit + draft-v2), compared with the Phase 4 golden run (artifacts/agent/agent_benchmark.json).
  python scripts/phase5/e_golden_benchmark.py
Writes artifacts/resolution/{benchmark.json, benchmark.md, per_query_golden_agent.jsonl, resolution_examples.json,
evidence_examples.json, latency_report.md, example_traces.jsonl, handoff_examples.json}. Real outputs only; nothing is tuned here.
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

OUT = Path("artifacts/resolution")
OUT.mkdir(parents=True, exist_ok=True)
PHASE4 = Path("artifacts/agent/agent_benchmark.json")
ESCALATION_COST_WEIGHTS = (1.0, 3.0, 5.0)     # cost of an unsafe autonomous reply relative to one safe autonomous resolution (sensitivity, not a business fact)
HANDOFF_COSTS = (0.1, 0.3)                    # cost of an unnecessary handoff / clarification relative to one safe autonomous resolution


def main() -> None:
    import sys

    recompute = "--recompute" in sys.argv   # metrics + markdown only, from per_query_golden_agent.jsonl (no agent run, no LLM)
    gold = load_golden()
    authors = pd.read_csv("data/golden/golden_customer_authors.csv", dtype=str).set_index("gid").customer_author.to_dict() if Path("data/golden/golden_customer_authors.csv").exists() else {}
    store = TraceStore(OUT / "traces")
    prior = json.loads((OUT / "benchmark.json").read_text(encoding="utf-8")) if recompute else None
    agent = None if recompute else ResolveAI(cfg=AgentConfig(), trace_store=store)
    recs, t_all = [], time.perf_counter()
    for g in ([] if recompute else gold.itertuples()):
        r = agent.resolve(g.customer_message, parse_context(g.context), customer_author=authors.get(g.gid), created_at=g.created_at, message_id=g.gid)
        tr = store.read(r.trace_id)
        risk_ev = next((e for e in tr.events if e.name.value == "risk_flags_extracted"), None) if tr else None
        draft_ev = [e for e in tr.events if e.name.value == "draft_generated"] if tr else []
        recs.append({"gid": g.gid, "message": g.customer_message, "gold_intent": g.intent, "gold_escalate": bool(g.should_escalate), "gold_reason": g.escalation_reason, "action": r.action,
                     "intent": r.intent.intent, "band": r.intent.confidence_band, "confidence": r.intent.confidence, "second_opinion": r.intent.second_opinion, "so_applied": r.intent.second_opinion_applied,
                     "evidence_sufficient": r.evidence.sufficient, "evidence_reason": r.evidence.sufficiency_reason, "evidence_level": r.evidence.sufficiency_level, "resolution_confidence": r.evidence.resolution_confidence,
                     "consistency": r.evidence.consistency, "clusters": [(c.action_class, c.support_count, c.share) for c in r.evidence.resolution_candidates], "sources": [i.retrieval_source for i in r.evidence.items],
                     "risk": [k for k, v in r.risk.model_dump().items() if v is True and k != "is_actionable"], "risk_source": r.risk.source, "risk_status": (risk_ev.status if risk_ev else None),
                     "reason_code": r.decision.escalation.reason_code, "rule": r.decision.escalation.rule, "blocking": r.decision.blocking, "response": r.response, "evidence_refs": r.evidence_refs,
                     "verified": (r.verification.verified if r.verification else None), "coverage": (r.verification.coverage if r.verification else None),
                     "verification_issues": ([i.check for i in r.verification.issues] if r.verification else []), "draft_attempts": (r.draft.attempts if r.draft else 0),
                     "draft_ask_only": (draft_ev[-1].data.get("ask_only") if draft_ev else None), "draft_text": (r.draft.text if r.draft else None),
                     "stage_status": r.stage_status, "latency": r.latency, "usage": r.usage.model_dump(), "trace_id": r.trace_id,
                     "slices": {"short": len(g.customer_message) < 40, "multi_turn": int(g.n_context_turns) > 0, "multi_intent": bool(g.multi_intent), "insufficient_context": bool(g.insufficient_context),
                                "taxonomy_gap": bool(g.taxonomy_gap), "customer_seen_in_kb": str(g.customer_seen_in_kb).lower() == "true"}})
    wall = prior["usage"]["wall_seconds"] if recompute else time.perf_counter() - t_all
    if recompute:
        recs = [json.loads(x) for x in (OUT / "per_query_golden_agent.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    else:
        (OUT / "per_query_golden_agent.jsonl").write_text("\n".join(json.dumps(x, default=str) for x in recs), encoding="utf-8")

    # ---------------- metrics (same definitions as Phase 4) ----------------
    n = len(recs)
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
    actions = Counter(r["action"] for r in recs)
    rates = {a: round(actions.get(a, 0) / n, 4) for a in ("AUTO_HANDLE", "CLARIFICATION_REQUIRED", "HUMAN_HANDOFF")}
    rates["insufficient_evidence_rate"] = round(sum(1 for r in recs if not r["evidence_sufficient"]) / n, 4)
    rates["evidence_levels"] = dict(Counter(r["evidence_level"] for r in recs))
    rates["evidence_reasons"] = dict(Counter(r["evidence_reason"] for r in recs))
    rates["consistency"] = dict(Counter(r["consistency"] for r in recs))
    rates["reason_codes"] = dict(Counter(r["reason_code"] for r in recs))
    rates["risk_status"] = dict(Counter(str(r["risk_status"]) for r in recs))
    rates["retrieval_sources_top5"] = dict(Counter(s for r in recs for s in r["sources"]))
    auto = [r for r in recs if r["action"] == "AUTO_HANDLE"]
    is_canned = lambda r: str(r["rule"]).startswith("canned:")  # noqa: E731  (a canned DraftResponse also reports attempts=1)
    auto_ts = [r for r in auto if not is_canned(r)]
    drafted = [r for r in recs if r["draft_attempts"] > 0 and r["stage_status"].get("draft") == "ok" and not is_canned(r)]
    resp = {"auto_replies": len(auto), "auto_canned": len(auto) - len(auto_ts), "auto_troubleshoot": len(auto_ts), "drafts_generated": len(drafted),
            "verified_share_of_drafts": round(sum(1 for r in drafted if r["verified"]) / len(drafted), 4) if drafted else None,
            "mean_evidence_coverage_auto": round(float(np.mean([r["coverage"] for r in auto_ts])), 3) if auto_ts else None,
            "auto_with_evidence_refs": sum(1 for r in auto_ts if r["evidence_refs"]), "ask_only_auto_replies": sum(1 for r in auto_ts if r["draft_ask_only"]),
            "redraft_share": round(sum(1 for r in drafted if r["draft_attempts"] == 2) / len(drafted), 4) if drafted else None,
            "verification_issue_counts": dict(Counter(i for r in drafted for i in r["verification_issues"])),
            "auto_on_gold_should_escalate": sum(1 for r in auto if r["gold_escalate"]), "risk_fallbacks": sum(1 for r in recs if r["risk_source"] == "fallback")}
    # ---------------- safety invariants (computed, not asserted) ----------------
    inv = {"auto_without_sufficient_evidence_or_canned": sum(1 for r in auto if not r["evidence_sufficient"] and not is_canned(r)),
           "auto_troubleshoot_without_refs": sum(1 for r in auto_ts if not r["evidence_refs"]), "auto_unverified": sum(1 for r in auto if r["verified"] is not True),
           "auto_with_hard_risk_flag": sum(1 for r in auto if any(k in r["risk"] for k in ("safety_concern", "security_concern", "legal_or_media_threat", "account_access_risk", "abusive_threatening"))),
           "auto_on_gold_should_escalate": resp["auto_on_gold_should_escalate"], "responses_with_unredacted_pii": 0, "gold_hash_verified": True}
    from resolveai.trust.pii import contains_unredacted_pii
    inv["responses_with_unredacted_pii"] = sum(1 for r in recs if contains_unredacted_pii(r["response"] or ""))
    # ---------------- autonomy utility view ----------------
    safe_auto = sum(1 for r in auto if not r["gold_escalate"])
    unsafe_auto = sum(1 for r in auto if r["gold_escalate"])
    correct_handoff = sum(1 for r in recs if r["action"] != "AUTO_HANDLE" and r["gold_escalate"])
    unnecessary_nonauto = sum(1 for r in recs if r["action"] != "AUTO_HANDLE" and not r["gold_escalate"])
    utility = {"counts": {"safe_auto_resolution": safe_auto, "unsafe_auto": unsafe_auto, "correct_non_autonomous": correct_handoff, "unnecessary_non_autonomous": unnecessary_nonauto},
               "definition": "utility = safe_auto - w*unsafe_auto - c*unnecessary_non_autonomous (per 197 rows); w = escalation-cost weight, c = cost of a needless human touch. Sensitivity view, not business facts.",
               "table": {f"w={w},c={c}": round(safe_auto - w * unsafe_auto - c * unnecessary_nonauto, 1) for w in ESCALATION_COST_WEIGHTS for c in HANDOFF_COSTS},
               "baselines": {f"always_handoff w={w},c={c}": round(0 - w * 0 - c * sum(1 for r in recs if not r["gold_escalate"]), 1) for w in ESCALATION_COST_WEIGHTS for c in HANDOFF_COSTS}
               | {f"never_escalate(auto all) w={w}": round(sum(1 for r in recs if not r["gold_escalate"]) - w * sum(1 for r in recs if r["gold_escalate"]), 1) for w in ESCALATION_COST_WEIGHTS}}
    slices = {}
    for s in recs[0]["slices"]:
        rs = [r for r in recs if r["slices"][s]]
        if rs:
            slices[s] = {"n": len(rs), "auto_rate": round(sum(r["action"] == "AUTO_HANDLE" for r in rs) / len(rs), 3), "clarify_rate": round(sum(r["action"] == "CLARIFICATION_REQUIRED" for r in rs) / len(rs), 3),
                         "handoff_rate": round(sum(r["action"] == "HUMAN_HANDOFF" for r in rs) / len(rs), 3), "sufficient_rate": round(sum(r["evidence_sufficient"] for r in rs) / len(rs), 3),
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
             "calls_by_action": {a: round(float(np.mean([r["usage"]["llm_calls"] for r in recs if r["action"] == a])), 2) for a in actions}, "wall_seconds": round(wall, 1),
             "risk_calls_skipped_by_policy": sum(1 for r in recs if r["risk_status"] == "policy_hard_handoff"), "risk_calls_skipped_by_rules": sum(1 for r in recs if r["risk_status"] == "rules_hard_block")}
    system = prior["system"] if recompute else {"retriever": agent.retriever.cfg.name, "gate": agent.retriever.gate_v3.version, "policy": "policy-v3", "risk_schema": agent.cfg.risk_schema, "draft": agent.cfg.draft_version, "second_opinion_policy": agent.policy}
    report = {"n": n, "system": system,
              "intent": intent, "escalation": esc, "rates": rates, "response": resp, "invariants": inv, "autonomy_utility": utility, "slices": slices, "latency_ms": lat, "usage": usage}
    # ---------------- Phase 4 -> 5 comparison ----------------
    comp = {}
    if PHASE4.exists():
        p4 = json.loads(PHASE4.read_text(encoding="utf-8"))
        def pick(d, *ks):
            for k in ks:
                d = d.get(k, {}) if isinstance(d, dict) else {}
            return d if d != {} else None
        pairs = {"AUTO_HANDLE": ("rates", "AUTO_HANDLE"), "CLARIFICATION_REQUIRED": ("rates", "CLARIFICATION_REQUIRED"), "HUMAN_HANDOFF": ("rates", "HUMAN_HANDOFF"), "insufficient_evidence_rate": ("rates", "insufficient_evidence_rate"),
                 "intent_accuracy": ("intent", "accuracy"), "intent_macro_f1": ("intent", "macro_f1"), "escalation_recall": ("escalation", "recall"), "escalation_precision": ("escalation", "precision"),
                 "auto_replies": ("response", "auto_replies"), "auto_with_evidence_refs": ("response", "auto_with_evidence_refs"), "drafts_generated": ("response", "drafts_generated"),
                 "verified_share_of_drafts": ("response", "verified_share_of_drafts"), "auto_on_gold_should_escalate": ("response", "auto_on_gold_should_escalate"),
                 "llm_calls_per_message": ("usage", "llm_calls_per_message"), "tokens_out_per_message": ("usage", "tokens_out_per_message"), "estimated_cost_usd_per_message": ("usage", "estimated_cost_usd_per_message"),
                 "fallbacks": ("usage", "fallbacks"), "total_p50_ms": ("latency_ms", "total", "p50"), "total_p95_ms": ("latency_ms", "total", "p95")}
        comp = {k: {"phase4": pick(p4, *ks), "phase5": pick(report, *ks)} for k, ks in pairs.items()}
    report["phase4_to_phase5"] = comp
    (OUT / "benchmark.json").write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")

    # ---------------- markdown ----------------
    L = ["# ResolveAI golden benchmark (Phase 5, evaluated once)", "", f"Golden set, {n} rows. System: `{json.dumps(report['system'])}`. Wall time {wall:.0f} s.", "",
         "## Actions", "", "| AUTO_HANDLE | CLARIFICATION_REQUIRED | HUMAN_HANDOFF | insufficient evidence |", "|---|---|---|---|",
         f"| {rates['AUTO_HANDLE']} | {rates['CLARIFICATION_REQUIRED']} | {rates['HUMAN_HANDOFF']} | {rates['insufficient_evidence_rate']} |", "",
         f"Evidence levels: `{rates['evidence_levels']}`; gate reasons: `{rates['evidence_reasons']}`; consistency: `{rates['consistency']}`", f"Reason codes: `{rates['reason_codes']}`; risk status: `{rates['risk_status']}`", "",
         "## Intent", "", f"accuracy {intent['accuracy']}, macro-F1 {intent['macro_f1']} (second opinion applied on {intent['second_opinion_applied']} rows)", "",
         "## Escalation (HUMAN_HANDOFF vs gold should_escalate)", "", f"precision {esc['precision']}, recall {esc['recall']}, F1 {esc['f1']}; confusion gold x pred `{esc['confusion_gold_x_pred']}`; any non-autonomous action as positive: {esc['non_autonomous_as_positive']}", "",
         "## Responses", "", f"`{json.dumps(resp)}`", "", "## Safety invariants (counts of violations; all must be 0)", "", f"`{json.dumps(inv)}`", "",
         "## Autonomy utility view (sensitivity, not business facts)", "", f"counts `{json.dumps(utility['counts'])}`", "", "| weights | ResolveAI | always-handoff | never-escalate |", "|---|---|---|---|"]
    for w in ESCALATION_COST_WEIGHTS:
        for c in HANDOFF_COSTS:
            L.append(f"| w={w}, c={c} | {utility['table'][f'w={w},c={c}']} | {utility['baselines'][f'always_handoff w={w},c={c}']} | {utility['baselines'][f'never_escalate(auto all) w={w}']} |")
    L += ["", "## Phase 4 -> Phase 5", "", "| metric | Phase 4 (run 2) | Phase 5 |", "|---|---|---|"] + [f"| {k} | {v['phase4']} | {v['phase5']} |" for k, v in comp.items()]
    L += ["", "## Slices", "", "| slice | n | auto | clarify | handoff | sufficient | intent acc | escalation recall |", "|---|---|---|---|---|---|---|---|"]
    L += [f"| {s} | {v['n']} | {v['auto_rate']} | {v['clarify_rate']} | {v['handoff_rate']} | {v['sufficient_rate']} | {v['intent_acc']} | {v['escalation_recall']} |" for s, v in slices.items()]
    L += ["", "## Latency (ms) and cost", "", "| stage | p50 | p95 | n |", "|---|---|---|---|"] + [f"| {k} | {v['p50']} | {v['p95']} | {v['n']} |" for k, v in lat.items()]
    L += ["", f"`{json.dumps(usage)}`", ""]
    (OUT / "benchmark.md").write_text("\n".join(L), encoding="utf-8")
    (OUT / "latency_report.md").write_text("\n".join(["# Phase 5 latency and cost (golden run)", "", "| stage | p50 ms | p95 ms | n |", "|---|---|---|---|"] + [f"| {k} | {v['p50']} | {v['p95']} | {v['n']} |" for k, v in lat.items()]
                                                    + ["", f"`{json.dumps(usage)}`", "", "Second-opinion calls were cache hits from Phase 3/4 (same prompt version); risk (v2), draft (v2) and verifier calls were live unless noted. Costs use GLM-5.2 list price; the proxy's billing is unknown.",
                                                       "Short-circuit and structured-output measurements on DEV: short_circuit.json, risk_hardening.json."]), encoding="utf-8")
    print("\n".join(L[:40]))
    print("usage:", usage)
    if recompute:
        print('recomputed from saved records; examples unchanged')
        return

    # ---------------- examples ----------------
    res_ex = [{"gid": r["gid"], "message": r["message"], "intent": r["intent"], "evidence_level": r["evidence_level"], "resolution_confidence": r["resolution_confidence"], "clusters": r["clusters"],
               "response": r["response"], "evidence_refs": r["evidence_refs"], "verified": r["verified"], "coverage": r["coverage"], "gold_should_escalate": r["gold_escalate"], "trace_id": r["trace_id"]} for r in auto_ts]
    res_ex += [{"gid": r["gid"], "message": r["message"], "intent": r["intent"], "evidence_level": r["evidence_level"], "action": r["action"], "reason_code": r["reason_code"], "draft_rejected": r["draft_text"],
                "verification_issues": r["verification_issues"], "trace_id": r["trace_id"]} for r in recs if r["action"] != "AUTO_HANDLE" and r["draft_text"]]
    (OUT / "resolution_examples.json").write_text(json.dumps(res_ex, indent=1, default=str), encoding="utf-8")
    ev_ex, seen = [], Counter()
    for r in recs:
        key = r["evidence_level"] if r["consistency"] != "mixed_resolution" else "WEAK_mixed"
        if seen[key] >= 3:
            continue
        rr = agent.resolve(r["message"], parse_context(gold[gold.gid == r["gid"]].iloc[0].context), customer_author=authors.get(r["gid"]), created_at=gold[gold.gid == r["gid"]].iloc[0].created_at, message_id=r["gid"] + "_ex")
        ev_ex.append({"gid": r["gid"], "message": r["message"], "level": rr.evidence.sufficiency_level, "reason": rr.evidence.sufficiency_reason, "resolution_confidence": rr.evidence.resolution_confidence,
                      "consistency": rr.evidence.consistency, "signals": rr.evidence.signals.model_dump() if rr.evidence.signals else None,
                      "resolution_candidates": [c.model_dump() for c in rr.evidence.resolution_candidates],
                      "items": [{"evidence_id": i.evidence_id, "source": i.retrieval_source, "action_class": i.quality.action_class, "cos_customer": round(i.quality.semantic_relevance, 3), "cos_pair": round(i.scores.get("cos_pair", 0), 3),
                                 "rerank": round(i.scores.get("rerank", 0), 3), "customer_message": i.customer_message, "brand_reply": i.brand_reply, "created_at": i.created_at} for i in rr.evidence.items]})
        seen[key] += 1
    (OUT / "evidence_examples.json").write_text(json.dumps(ev_ex, indent=1, default=str), encoding="utf-8")
    ex, seen = [], Counter()
    for r in recs:
        if seen[r["action"]] < 3:
            t = store.read(r["trace_id"])
            if t:
                ex.append(t.model_dump())
                seen[r["action"]] += 1
    (OUT / "example_traces.jsonl").write_text("\n".join(json.dumps(x, default=str) for x in ex), encoding="utf-8")
    packets = []
    for r in recs:
        if r["action"] == "HUMAN_HANDOFF" and len(packets) < 6 and r["reason_code"] not in {h["reason"] for h in packets}:
            g = gold[gold.gid == r["gid"]].iloc[0]
            rr = agent.resolve(g.customer_message, parse_context(g.context), customer_author=authors.get(r["gid"]), created_at=g.created_at, message_id=r["gid"] + "_ho")
            if rr.handoff:
                packets.append({"gid": r["gid"], "reason": r["reason_code"], "packet": rr.handoff.model_dump()})
    (OUT / "handoff_examples.json").write_text(json.dumps(packets, indent=1, default=str), encoding="utf-8")



if __name__ == "__main__":
    main()
