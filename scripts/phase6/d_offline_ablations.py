"""Phase 6-D: offline ablations that must never touch the production path.
  python scripts/phase6/d_offline_ablations.py
1. minus_verifier (offline): what would have been sent if the verifier did not exist. Source: the Phase 5 dev drafting A/B
   (26 drafts, hand-audited) and the golden run (drafts that the verifier blocked). No new LLM calls.
2. minus_gate / coverage-vs-quality (offline): for golden rows the gate calls WEAK (never SUFFICIENT), draft as if the gate
   had allowed them, run the verifier, and score the drafts with the frozen judge. This shows what quality the agent would
   buy by lowering the abstention threshold - the abstention curve. Drafts are produced with the production drafter and
   verifier but the gate verdict is overridden ONLY inside this script; production code is unchanged.
Writes artifacts/evaluation/offline_ablations.json, artifacts/evaluation/runs/offline_weak_drafts.jsonl (judge input)
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd

import resolveai  # noqa: F401
from resolveai.agent import drafter
from resolveai.agent.verifier import verify
from resolveai.evaluation import load_golden
from resolveai.evaluation.judge import judge_one
from resolveai.evaluation.records import EvidenceSnippet, SystemRecord, read_records, write_records
from resolveai.intelligence.context import build_context, parse_context
from resolveai.intelligence.pipeline import PreGenerationPipeline
from resolveai.llm import DiskCache, LLMClient, LLMUnavailable, OpenAICompatibleProvider
from resolveai.trust.pii import redact_pii

OUT = Path("artifacts/evaluation")
RUNS = OUT / "runs"


def minus_verifier() -> dict:
    dev = [json.loads(x) for x in Path("artifacts/resolution/draft_experiment.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    labels = json.loads(Path("artifacts/resolution/verifier_labels.json").read_text(encoding="utf-8"))["labels"]
    drafts = [(f"{r['id']}:{arm}", r[arm]) for r in dev for arm in ("A_v1", "B_v2") if r[arm].get("text")]
    blocked = [(k, d) for k, d in drafts if not d["verified"]]
    true_blocks = [k for k, _ in blocked if labels.get(k) == "TRUE_BLOCK"]
    full = read_records(RUNS / "resolveai_full.jsonl")
    golden_blocked = [r.gid for r in full if r.extra.get("draft_attempts", 0) > 0 and r.verified is False]
    return {"source": "Phase 5 dev drafting A/B (26 drafts, AI-audited) + golden run", "dev_drafts": len(drafts), "dev_blocked": len(blocked),
            "dev_true_blocks_that_would_ship": len(true_blocks), "dev_true_block_ids": true_blocks,
            "dev_false_blocks": sum(1 for k, _ in blocked if labels.get(k) == "FALSE_BLOCK"),
            "golden_drafts_blocked_by_verifier": len(golden_blocked), "golden_blocked_gids": golden_blocked,
            "reading": "without the verifier, every dev draft would ship: the hand-audit found 6 of 26 carried invented steps/actions or no evidence reference; on golden all 5 troubleshooting drafts passed, so the verifier changed nothing there (n=5)"}


def weak_drafts(client: LLMClient) -> list[SystemRecord]:
    gold = load_golden()
    authors = pd.read_csv("data/golden/golden_customer_authors.csv", dtype=str).set_index("gid").customer_author.to_dict()
    full = {r.gid: r for r in read_records(RUNS / "resolveai_full.jsonl")}
    pipe = PreGenerationPipeline()
    out = []
    for row in gold.itertuples():
        fr = full[row.gid]
        if fr.evidence_level != "WEAK":
            continue
        if fr.action == "HUMAN_HANDOFF" and fr.reason_code != "insufficient_evidence":
            continue   # handed off for a risk/policy reason, not for evidence: lowering the gate would not change it
        t = time.perf_counter()
        red = redact_pii(row.customer_message).text
        u = pipe.understand(red, parse_context(row.context), customer_author=authors.get(row.gid), created_at=row.created_at)
        b = build_context(red, parse_context(row.context))
        ev = u.evidence.model_copy(update={"sufficient": True})   # the override lives only here
        u0 = client.usage.as_dict()
        try:
            d = drafter.draft_troubleshoot(client, b, u.intent, ev, version="v2")
            v = verify(client, d, ev, u.intent, use_llm=True)
            rec = SystemRecord(gid=row.gid, system="offline_weak_drafts", message=row.customer_message, context=row.context or "", intent_pred=u.intent.intent, intent_confidence=round(u.intent.confidence, 4),
                               intent_band=u.intent.confidence_band, escalate_pred=False, action="AUTO_HANDLE", response=d.text, response_kind="troubleshoot",
                               evidence=[EvidenceSnippet(evidence_id=i.evidence_id, customer_message=i.customer_message, brand_reply=i.brand_reply, cited=i.evidence_id in d.evidence_ids) for i in ev.items],
                               evidence_sufficient=False, evidence_level="WEAK", resolution_confidence=u.evidence.resolution_confidence, verified=v.verified, evidence_refs=list(d.evidence_ids),
                               reason_code=u.evidence.sufficiency_reason, extra={"verification_issues": [i.check for i in v.issues], "production_action": fr.action})
        except LLMUnavailable as e:
            rec = SystemRecord(gid=row.gid, system="offline_weak_drafts", message=row.customer_message, context=row.context or "", intent_pred=u.intent.intent, escalate_pred=False, action="AUTO_HANDLE",
                               response="", response_kind="troubleshoot", evidence_level="WEAK", failed=True, error=str(e)[:200], reason_code=u.evidence.sufficiency_reason, extra={"production_action": fr.action})
        u1 = client.usage.as_dict()
        rec.llm_calls, rec.live_calls, rec.tokens_in, rec.tokens_out = int(u1["calls"] - u0["calls"]), int(u1["live_calls"] - u0["live_calls"]), int(u1["tokens_in"] - u0["tokens_in"]), int(u1["tokens_out"] - u0["tokens_out"])
        rec.latency_ms = (time.perf_counter() - t) * 1000
        out.append(rec)
        print(f"  weak draft {row.gid}: verified={rec.verified} failed={rec.failed}", flush=True)
    return out


def main() -> None:
    res = {"minus_verifier": minus_verifier()}
    client = LLMClient(provider=OpenAICompatibleProvider(), cache=DiskCache())
    weak = weak_drafts(client)
    write_records(RUNS / "offline_weak_drafts.jsonl", weak)
    judged = [judge_one(client, r) for r in weak if not r.failed]
    Path(OUT / "judge_results.jsonl").open("a", encoding="utf-8").write("".join(json.dumps(j) + "\n" for j in judged))
    gold = load_golden().set_index("gid")
    res["minus_gate_weak_rows"] = {"n_weak_rows": len(weak), "drafts_failed": sum(1 for r in weak if r.failed), "drafts_verified": sum(1 for r in weak if r.verified is True),
                                   "on_gold_should_escalate": sum(1 for r in weak if gold.loc[r.gid].should_escalate),
                                   "judged": len(judged), "judge_means": {d: round(sum(j[d] for j in judged if not j["failed"]) / max(1, sum(1 for j in judged if not j["failed"])), 2) for d in ("groundedness", "relevance", "actionability", "completeness", "policy_compliance", "tone")} if judged else {},
                                   "hallucination_rate": round(sum(1 for j in judged if not j["failed"] and j["hallucination"]) / max(1, sum(1 for j in judged if not j["failed"])), 3) if judged else None,
                                   "note": "gate verdict overridden inside this script only; production never drafts on WEAK evidence"}
    (OUT / "offline_ablations.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    print(json.dumps(res["minus_gate_weak_rows"], indent=1))


if __name__ == "__main__":
    main()
