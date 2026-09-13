"""Phase 9-A: risk-model over-escalation, measured on DEV only (never the golden set).

  python -u scripts/phase9/a_risk_dev_experiment.py [n] [--workers 4]

Question: does the LLM risk extractor escalate cases a public reply or a clarifying question could handle, which flags cause it,
and can a candidate change remove those escalations without losing real ones?

Protocol (pre-registered before any result was seen; the acceptance rule is applied by b_risk_dev_metrics.py):
  sample  n holdout messages that are NOT golden rows (asserted), fresh seed SEED+9; the production understanding pipeline runs
          unchanged (redaction, context, classifier, intent second opinion, retrieval, evidence gate)
  V0  production: rules OR risk-flags-v2 model flags                    (Phase 8 behaviour)
  V1  deterministic rules only                                          (the safety floor; Phase 6 ablation)
  V2  V0, but the soft flags repeat_contact / physical_damage / needs_private_info count from the model only when the rule agrees
  V3  rules OR risk-flags-v3 model flags (guide R1/R3/private-info definitions spelled out in the prompt)
  V4  V3 with the V2 corroboration
  Rows where the rules-only policy already guarantees a handoff skip the model, exactly as production does (identical in all variants).
  Policy decision per variant: deterministic policy-v3.1 on (intent, flags, context, evidence).
Rows whose handoff/no-handoff outcome differs between any two variants form the disagreement set; they are labelled for
should_escalate under data/golden/ANNOTATION_GUIDE.md v1.1 by an AI annotator (NOT a human) in data/dev/phase9_risk_labels.json.
Writes artifacts/phase9/risk/dev_runs.jsonl and artifacts/phase9/risk/dev_run_summary.json.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from resolveai import config  # noqa: E402
from resolveai.agent import risk, second_opinion  # noqa: E402
from resolveai.evaluation import load_golden  # noqa: E402
from resolveai.intelligence.classifier import IntentService  # noqa: E402
from resolveai.intelligence.context import build_context, parse_context  # noqa: E402
from resolveai.intelligence.query import build_query  # noqa: E402
from resolveai.llm import DiskCache, LLMClient, LLMUnavailable, OpenAICompatibleProvider  # noqa: E402
from resolveai.policy import escalation as policy  # noqa: E402
from resolveai.retrieval import KnowledgeBase, Retriever, RetrieverConfig  # noqa: E402
from resolveai.retrieval.dense import Embedder  # noqa: E402
from resolveai.schemas.core import ConversationContext, ConversationTurn  # noqa: E402
from resolveai.trust.injection import detect_injection  # noqa: E402
from resolveai.trust.pii import redact_pii  # noqa: E402

OUT = ROOT / "artifacts" / "phase9" / "risk"
VARIANTS = ("V0", "V1", "V2", "V3", "V4")


def dev_rows(n: int) -> pd.DataFrame:
    sub = pd.read_csv(config.PROCESSED_DIR / "apple_pairs.csv", keep_default_na=False)
    gold_ids = set(load_golden().customer_tweet_id.astype(str))
    pool = sub[(sub.split == "holdout") & ~sub.customer_tweet_id.astype(str).isin(gold_ids)]
    rows = pool.sample(n=n, random_state=config.SEED + 9).reset_index(drop=True)
    assert not set(rows.customer_tweet_id.astype(str)) & gold_ids, "golden rows leaked into the dev sample"
    return rows


def outcome(e) -> str:
    if e.decision == "auto_handle":
        return "AUTO_CANDIDATE"
    return "CLARIFY" if e.clarification_allowed else "HANDOFF"


_LOCK = __import__("threading").Lock()


def understand(row, intents: IntentService, embedder: Embedder, retriever: Retriever, llm: LLMClient, so_policy: str, lock=_LOCK) -> dict:
    """The embedder, classifier and retriever are not thread-safe (concurrent model initialisation fails), so they run under
    `lock`; only the model calls run concurrently."""
    msg = redact_pii(row.customer_message).text
    ctx = parse_context(row.context)
    ctx = ConversationContext(turns=[ConversationTurn(role=t.role, text=redact_pii(t.text).text) for t in ctx.turns])
    b = build_context(msg, ctx)
    with lock:
        X = embedder.encode_one(b.current)[None, :]
        intent = intents.classify(b, X=X)
    inj = detect_injection("\n".join([b.current, *b.prior_customer, *b.prior_brand])).detected
    so_status = "skipped"
    if not inj:
        intent, so_status = second_opinion.apply(llm, b, intent, so_policy)
    plan = build_query(b, intent)
    with lock:
        qv = X[0] if plan.text == b.current else embedder.encode_one(plan.text)
        ev = retriever.retrieve(plan.text, query_intent=(None if intent.insufficient_context else intent.intent), customer_author=row.customer_author,
                                query_created_at=row.created_at, allowed_intents=plan.allowed_intents, boost=plan.boost, query_vec=qv)
    return {"bundle": b, "ctx": ctx, "intent": intent, "evidence": ev, "second_opinion": so_status}


def model_opinion(llm: LLMClient, bundle, schema: str) -> dict:
    t = time.perf_counter()
    try:
        raised, actionable, summary, unknown = risk.llm_opinion(llm, bundle, schema=schema)
        return {"status": "ok", "raised": sorted(raised), "actionable": actionable, "summary": summary, "unknown": unknown, "ms": round((time.perf_counter() - t) * 1000)}
    except LLMUnavailable as e:
        return {"status": "fallback", "raised": [], "actionable": True, "summary": "", "unknown": [], "error": str(e)[:120], "ms": round((time.perf_counter() - t) * 1000)}


def run_row(row, parts: dict) -> dict:
    u = understand(row, parts["intents"], parts["embedder"], parts["retriever"], parts["llm"], parts["so_policy"])
    b, ctx, intent, ev = u["bundle"], u["ctx"], u["intent"], u["evidence"]
    rules = risk.extract_rules(b)
    conflicting = ev.sufficiency_reason == "conflicting_evidence"
    guaranteed = rules.any_hard_block() or policy.hard_handoff_guaranteed(intent, rules, ctx, ev, b.current)
    ops = {}
    if not guaranteed:
        ops["v2"] = model_opinion(parts["llm"], b, "compact")
        ops["v3"] = model_opinion(parts["llm"], b, "compact_v3")
    flags = {}
    rules_c = rules.model_copy(update={"conflicting_evidence": conflicting})
    for v in VARIANTS:
        if guaranteed or v == "V1":
            flags[v] = rules_c
            continue
        op = ops["v2"] if v in ("V0", "V2") else ops["v3"]
        if op["status"] != "ok":
            flags[v] = rules_c
            continue
        corroborate = risk.SOFT_FLAGS if v in ("V2", "V4") else frozenset()
        flags[v] = risk.merge(rules, set(op["raised"]), op["actionable"], op["summary"], b, conflicting, corroborate=corroborate)
    decisions = {}
    for v, f in flags.items():
        e = policy.decide(intent, f, ctx, ev, None, llm_available=True, message=b.current)
        decisions[v] = {"outcome": outcome(e), "reason_code": e.reason_code, "rule": e.rule, "flags": sorted(k for k, val in f.model_dump().items() if val is True and k != "is_actionable")}
    return {"customer_tweet_id": str(row.customer_tweet_id), "message": b.current, "context": row.context, "intent": intent.intent, "intent_band": intent.confidence_band,
            "insufficient_context": intent.insufficient_context, "second_opinion": u["second_opinion"], "evidence_level": ev.sufficiency_level, "evidence_reason": ev.sufficiency_reason,
            "rules_flags": sorted(k for k, val in rules.model_dump().items() if val is True and k != "is_actionable"), "model_skipped_hard_handoff": guaranteed,
            "opinions": ops, "decisions": decisions}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("n", nargs="?", type=int, default=240)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    rows = dev_rows(a.n)
    kb = KnowledgeBase.build(dense_models=[RetrieverConfig().model], with_bm25=False)
    parts = {"retriever": Retriever(kb, RetrieverConfig()), "intents": IntentService(), "embedder": Embedder(RetrieverConfig().model),
             "llm": LLMClient(provider=OpenAICompatibleProvider(), cache=DiskCache()), "so_policy": second_opinion.load_policy()}
    print(f"loaded in {time.perf_counter() - t0:.0f}s; running {len(rows)} dev rows", flush=True)
    # understanding is CPU-bound and not thread-safe in the embedder: run it serially, fan the model calls out
    records = []
    with cf.ThreadPoolExecutor(max_workers=a.workers) as pool:
        futures = {pool.submit(run_row, r, parts): k for k, r in enumerate(rows.itertuples())}
        for k, fut in enumerate(cf.as_completed(futures), start=1):
            records.append(fut.result())
            if k % 20 == 0:
                print(f"  {k}/{len(rows)} ({time.perf_counter() - t0:.0f}s)", flush=True)
    records.sort(key=lambda r: r["customer_tweet_id"])
    with (OUT / "dev_runs.jsonl").open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    summary = {"n": len(records), "seed": config.SEED + 9, "model_skipped_hard_handoff": sum(r["model_skipped_hard_handoff"] for r in records), "variants": {}}
    for v in VARIANTS:
        summary["variants"][v] = {"outcomes": dict(Counter(r["decisions"][v]["outcome"] for r in records)), "reasons": dict(Counter(r["decisions"][v]["reason_code"] for r in records))}
    for schema in ("v2", "v3"):
        ops = [r["opinions"][schema] for r in records if schema in r["opinions"]]
        ms = [o["ms"] for o in ops if o["status"] == "ok"]
        summary[f"model_{schema}"] = {"calls": len(ops), "fallback_rate": round(sum(o["status"] != "ok" for o in ops) / max(1, len(ops)), 4),
                                       "latency_ms_p50": float(np.percentile(ms, 50)) if ms else None, "latency_ms_p95": float(np.percentile(ms, 95)) if ms else None,
                                       "flag_counts": dict(Counter(f for o in ops for f in o["raised"]))}
    disagree = [r["customer_tweet_id"] for r in records if len({r["decisions"][v]["outcome"] == "HANDOFF" for v in VARIANTS}) > 1]
    summary["disagreement_rows"] = len(disagree)
    summary["wall_seconds"] = round(time.perf_counter() - t0, 1)
    (OUT / "dev_run_summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
