"""Phase 5-C: resolution-aware drafting A/B on DEV cases (never golden).
  A = draft-v1 (Phase 4: all substantive evidence, "ask if not covered")
  B = draft-v2 (resolution candidates first, lead with the fix, ask only when the evidence asks; ask-only retry)
Cases: holdout messages (disjoint from golden and from the retrieval dev set) whose evidence passes gate-v3 and whose
rules-only policy would allow automation - i.e. exactly the cases the agent would draft for. Both drafts are verified by
the same verifier (lexical + LLM support check). Per-draft records go to draft_experiment.jsonl for the verifier analysis.
  python scripts/phase5/c_draft_experiment.py [max_cases]
Writes artifacts/resolution/{draft_experiment.json, draft_experiment.jsonl, draft_experiment.md}
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

import resolveai  # noqa: F401
from resolveai import config
from resolveai.agent import drafter, risk
from resolveai.agent.verifier import verify
from resolveai.evaluation import load_golden
from resolveai.intelligence.context import build_context, parse_context
from resolveai.intelligence.pipeline import PreGenerationPipeline
from resolveai.llm import DiskCache, LLMClient, LLMUnavailable, OpenAICompatibleProvider
from resolveai.policy import escalation as policy

OUT = Path("artifacts/resolution")
OUT.mkdir(parents=True, exist_ok=True)
ACTION_WORDS = {"update": r"\b(updat|ios 11|11\.1|11\.2|software)", "restart": r"\b(restart|reboot|turn (it )?off|power)", "reset": r"\breset", "settings": r"\bsettings\b", "article": r"\b(article|steps|link|support page)"}


def candidate_cases(pipe: PreGenerationPipeline, n_pool: int, max_cases: int) -> list[dict]:
    sub = pd.read_csv(config.PROCESSED_DIR / "apple_pairs.csv", keep_default_na=False)
    gold_ids = set(load_golden().customer_tweet_id.astype(int))
    pool = sub[(sub.split == "holdout") & ~sub.customer_tweet_id.isin(gold_ids)].sample(frac=1.0, random_state=config.SEED + 7)
    cases, scanned = [], 0
    for r in pool.itertuples():
        scanned += 1
        u = pipe.understand(r.customer_message, parse_context(r.context), customer_author=(r.customer_author or None), created_at=r.created_at)
        if not u.evidence.sufficient:
            continue
        b = build_context(r.customer_message, parse_context(r.context))
        e = policy.decide(u.intent, risk.extract_rules(b), parse_context(r.context), u.evidence, None, llm_available=True, message=b.current)
        if e.decision != "auto_handle" or e.rule.startswith("canned:"):
            continue
        cases.append({"id": int(r.customer_tweet_id), "message": r.customer_message, "context": r.context, "intent": u.intent.intent, "level": u.evidence.sufficiency_level,
                      "rc": u.evidence.resolution_confidence, "clusters": [(c.action_class, c.support_count, c.share) for c in u.evidence.resolution_candidates], "_u": u, "_b": b})
        if len(cases) >= max_cases or scanned >= n_pool:
            break
    print(f"scanned {scanned} holdout rows -> {len(cases)} draftable cases")
    return cases


def judge_draft(d, ev, intent, client, top_action: str | None) -> dict:
    v = verify(client, d, ev, intent, use_llm=True)
    text = d.text
    return {"text": text, "refs": d.evidence_ids, "attempts": d.attempts, "prompt_version": d.prompt_version, "verified": v.verified, "issues": [f"{i.check}:{i.detail[:120]}" for i in v.issues],
            "blocking": [i.check for i in v.issues if i.severity == "blocking"], "coverage": v.coverage, "method": v.method, "ask_only": drafter.is_ask_only(text),
            "has_step": bool(drafter._STEP.search(text)), "mentions_top_action": bool(top_action and re.search(ACTION_WORDS.get(top_action, r"$^"), text, re.I)),
            "unsupported_claims": next((i.detail for i in v.issues if i.check == "llm_support_check"), ""), "chars": len(text)}


def main() -> None:
    max_cases = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    pipe = PreGenerationPipeline()
    client = LLMClient(provider=OpenAICompatibleProvider(), cache=DiskCache())
    cases = candidate_cases(pipe, n_pool=1500, max_cases=max_cases)
    recs = []
    for c in cases:
        u, b = c.pop("_u"), c.pop("_b")
        top_action = u.evidence.resolution_candidates[0].action_class if u.evidence.resolution_candidates else None
        rec = {k: v for k, v in c.items()} | {"top_action": top_action, "evidence": [{"id": i.evidence_id, "source": i.retrieval_source, "action": i.quality.action_class, "sim": round(i.quality.semantic_relevance, 3), "reply": i.brand_reply} for i in u.evidence.items]}
        for arm, version in (("A_v1", "v1"), ("B_v2", "v2")):
            u0 = client.usage.as_dict()
            t = time.perf_counter()
            try:
                d = drafter.draft_troubleshoot(client, b, u.intent, u.evidence, version=version)
                j = judge_draft(d, u.evidence, u.intent, client, top_action)
            except LLMUnavailable as e:
                j = {"text": None, "error": str(e)[:200], "verified": False, "blocking": ["draft_failed"], "ask_only": False, "has_step": False, "mentions_top_action": False, "coverage": 0.0, "attempts": 0, "refs": [], "issues": [], "unsupported_claims": ""}
            u1 = client.usage.as_dict()
            j |= {"ms": round((time.perf_counter() - t) * 1000), "tokens_out": u1["tokens_out"] - u0["tokens_out"], "calls": u1["calls"] - u0["calls"]}
            rec[arm] = j
        recs.append(rec)
        print(f"[{len(recs)}/{len(cases)}] {c['intent']:18s} {c['level']:10s} A:{'ok' if rec['A_v1']['verified'] else 'BLOCK'} ask={int(rec['A_v1']['ask_only'])}  B:{'ok' if rec['B_v2']['verified'] else 'BLOCK'} ask={int(rec['B_v2']['ask_only'])}")
    (OUT / "draft_experiment.jsonl").write_text("\n".join(json.dumps(r, default=str) for r in recs), encoding="utf-8")

    def summ(arm):
        xs = [r[arm] for r in recs]
        n = len(xs)
        return {"n": n, "draft_failed": sum(1 for x in xs if x.get("text") is None), "verifier_block_rate": round(sum(not x["verified"] for x in xs) / n, 3),
                "evidence_support_rate": round(sum(1 for x in xs if x["verified"] or (x.get("blocking") and "llm_support_check" not in x["blocking"] and "evidence_coverage" not in x["blocking"])) / n, 3),
                "llm_unsupported_rate": round(sum(1 for x in xs if "llm_support_check" in x.get("blocking", [])) / n, 3),
                "ask_only_rate": round(sum(x["ask_only"] for x in xs) / n, 3), "actionable_resolution_rate": round(sum(x["has_step"] for x in xs) / n, 3),
                "mentions_top_cluster_action": round(sum(x["mentions_top_action"] for x in xs) / n, 3), "verified_and_actionable": round(sum(1 for x in xs if x["verified"] and x["has_step"]) / n, 3),
                "mean_coverage": round(float(np.mean([x["coverage"] for x in xs])), 3), "retry_rate": round(sum(1 for x in xs if x.get("attempts", 0) >= 2) / n, 3),
                "blocking_checks": dict(pd.Series([b for x in xs for b in x.get("blocking", [])]).value_counts()) if any(x.get("blocking") for x in xs) else {},
                "latency_ms_p50": round(float(np.percentile([x["ms"] for x in xs], 50))), "tokens_out_mean": round(float(np.mean([x["tokens_out"] for x in xs])), 1), "calls_mean": round(float(np.mean([x["calls"] for x in xs])), 2)}

    out = {"n_cases": len(recs), "levels": dict(pd.Series([r["level"] for r in recs]).value_counts()), "A_v1": summ("A_v1"), "B_v2": summ("B_v2"),
           "protocol": "DEV holdout cases (seed SEED+7) disjoint from golden; same evidence set for both arms; same verifier (lexical + GLM support check); calls include the verifier"}
    (OUT / "draft_experiment.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    cols = ["verifier_block_rate", "evidence_support_rate", "llm_unsupported_rate", "ask_only_rate", "actionable_resolution_rate", "mentions_top_cluster_action", "verified_and_actionable", "mean_coverage", "retry_rate", "latency_ms_p50", "tokens_out_mean"]
    L = ["# Resolution-aware drafting A/B (Phase 5-C, DEV)", "", f"{len(recs)} draftable dev cases (gate-v3 sufficient, rules-only policy allows automation); levels {out['levels']}.", "",
         "| metric | A draft-v1 | B draft-v2 |", "|---|---|---|"] + [f"| {c} | {out['A_v1'][c]} | {out['B_v2'][c]} |" for c in cols]
    L += ["", f"Blocking checks A: `{out['A_v1']['blocking_checks']}`", f"Blocking checks B: `{out['B_v2']['blocking_checks']}`", "", "Per-draft records: draft_experiment.jsonl (input to the verifier analysis)."]
    (OUT / "draft_experiment.md").write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
