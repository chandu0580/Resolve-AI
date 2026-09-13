"""Phase 2 post-hoc analysis: bootstrap CIs, reference-coverage breakdown, retrieval-depth ceiling, and failure
categorisation with real examples. Reads the benchmark artifacts; writes artifacts/retrieval/analysis.json and a
draft of failure_analysis.md (examples + counts; hypotheses are written by hand on top).
  python scripts/phase2/analyze_retrieval.py
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

import numpy as np

import resolveai  # noqa: F401
from resolveai import config
from resolveai.data.clean import is_dm_handoff

sys.path.insert(0, str(Path(__file__).parent))
from run_retrieval_benchmark import golden_queries  # noqa: E402

OUT = Path("artifacts/retrieval")
RNG = np.random.default_rng(config.SEED)
PROFANE = re.compile(r"\b(fuck|shit|damn|wtf|crap|suck|ass)\b", re.I)


def boot_ci(flags: list[bool], n: int = 1000) -> tuple[float, float]:
    if not flags:
        return (float("nan"), float("nan"))
    a = np.array(flags, dtype=float)
    idx = RNG.integers(0, len(a), size=(n, len(a)))
    m = a[idx].mean(axis=1)
    return (round(float(np.percentile(m, 2.5)), 3), round(float(np.percentile(m, 97.5)), 3))


def main() -> None:
    res = json.loads((OUT / "results.json").read_text(encoding="utf-8"))
    man = json.loads((OUT / "experiment_manifest.json").read_text(encoding="utf-8"))
    final = man["selected"]["config"]
    recs = [json.loads(line) for line in (OUT / "per_query_golden.jsonl").read_text(encoding="utf-8").splitlines()]
    g = golden_queries().set_index("gid")
    by = {r["qid"]: r for r in recs}

    # 1. reference coverage: why a query has no reference
    n_sub = int(sum(1 for r in g.brand_reply if not is_dm_handoff(r) and len(r) >= 60))
    n_ref = sum(1 for r in recs if r["has_ref"])
    coverage = {"golden": len(recs), "substantive_own_reply": n_sub, "substantive_with_kb_match_at_tau": n_ref,
                "substantive_but_unmatchable_in_kb": n_sub - n_ref, "dm_or_short_own_reply": len(recs) - n_sub}

    # 2. CIs for the selected config and the dense/bm25 baselines
    cis = {}
    for name in res["golden"]:
        rr = None
        # recompute per-query hit flags only for the selected config (records exist); others use summary point estimates
        if name == final:
            ref = [r for r in recs if r["has_ref"]]
            rr = {k: boot_ci([bool(r["hit_rank"]) and r["hit_rank"] <= k for r in ref]) for k in (1, 3, 5)}
            rr["sufficient_rate"] = boot_ci([r["sufficient"] for r in recs])
            rr["gate_precision"] = boot_ci([bool(r["hit_rank"]) and r["hit_rank"] <= 5 for r in ref if r["sufficient"]])
        cis[name] = rr

    # 3. failure categorisation on the selected config (queries with a reference but no hit@5)
    misses = [r for r in recs if r["has_ref"] and not (r["hit_rank"] and r["hit_rank"] <= 5)]
    cats: dict[str, list[str]] = {k: [] for k in ("very_short", "lexical_mismatch", "semantic_mismatch", "ambiguous_intent", "multi_intent", "rare_intent",
                                                  "contradictory_cases", "noisy_language", "customer_specific", "taxonomy_gap", "insufficient_context", "deep_rank_only")}
    intent_counts = Counter(g.intent)
    for r in misses:
        q = g.loc[r["qid"]]
        msg = q.customer_message
        if len(msg) < 40:
            cats["very_short"].append(r["qid"])
        if all(a == 0 for a in r.get("top_scores", [])) or r["n_retrieved"] == 0:
            cats["lexical_mismatch"].append(r["qid"])
        if r["top_cos"] and max(r["top_cos"]) < 0.6:
            cats["semantic_mismatch"].append(r["qid"])
        if r["reason"] == "ambiguous_intent" or r["intent_agreement"] < 0.5:
            cats["ambiguous_intent"].append(r["qid"])
        if bool(q.multi_intent):
            cats["multi_intent"].append(r["qid"])
        if intent_counts[q.intent] <= 8:
            cats["rare_intent"].append(r["qid"])
        if r["conflicting"]:
            cats["contradictory_cases"].append(r["qid"])
        if PROFANE.search(msg) or sum(1 for ch in msg if ord(ch) > 0x2000) >= 3:
            cats["noisy_language"].append(r["qid"])
        if bool(q.customer_seen_in_kb) or q.intent == "account_store_repair":
            cats["customer_specific"].append(r["qid"])
        if bool(q.taxonomy_gap):
            cats["taxonomy_gap"].append(r["qid"])
        if bool(q.insufficient_context):
            cats["insufficient_context"].append(r["qid"])
        if r["hit_rank"] and r["hit_rank"] > 5:
            cats["deep_rank_only"].append(r["qid"])
    uncategorised = [r["qid"] for r in misses if not any(r["qid"] in v for v in cats.values())]

    # 4. gate behaviour by slice and by reason on golden
    gate = {"reasons": Counter(r["reason"] for r in recs), "sufficient_by_intent": {}}
    for it in sorted(set(g.intent)):
        rs = [r for r in recs if g.loc[r["qid"]].intent == it]
        gate["sufficient_by_intent"][it] = {"n": len(rs), "sufficient": round(sum(r["sufficient"] for r in rs) / len(rs), 3)}
    suff_hits = [r for r in recs if r["sufficient"] and r["has_ref"]]
    gate["precision_hit@5_given_sufficient"] = round(sum(1 for r in suff_hits if r["hit_rank"] and r["hit_rank"] <= 5) / len(suff_hits), 3) if suff_hits else None
    gate["sufficient_without_reference"] = sum(1 for r in recs if r["sufficient"] and not r["has_ref"])

    analysis = {"selected": final, "reference_coverage": coverage, "bootstrap_ci_95": cis, "failure_categories": {k: len(v) for k, v in cats.items()},
                "failure_examples": {k: v[:6] for k, v in cats.items()}, "uncategorised_misses": uncategorised, "n_misses": len(misses), "gate": gate}
    (OUT / "analysis.json").write_text(json.dumps(analysis, indent=2, default=str), encoding="utf-8")

    # 5. draft failure_analysis.md with real examples (hypotheses added by hand afterwards)
    L = ["# Retrieval failure analysis (draft with real examples; see hypotheses section)", "",
         f"Selected configuration: `{final}`. Golden queries: {len(recs)}. With a usable reference: {n_ref}. Misses (reference exists, no hit in top-5): {len(misses)}.", "",
         "## Reference coverage", "", f"`{json.dumps(coverage)}`", "", "## Failure categories (a miss can belong to several)", "",
         "| category | n | example gids |", "|---|---|---|"]
    for k, v in cats.items():
        L.append(f"| {k} | {len(v)} | {', '.join(v[:5])} |")
    L += ["", "## Representative misses", ""]
    seen = set()
    for k, v in cats.items():
        for qid in v[:2]:
            if qid in seen:
                continue
            seen.add(qid)
            q, r = g.loc[qid], by[qid]
            L += [f"### {qid} [{k}] intent={q.intent} short={bool(q.short)} seen_in_kb={bool(q.customer_seen_in_kb)}",
                  f"- customer: {q.customer_message[:220]}", f"- own reply: {q.brand_reply[:200]}",
                  f"- top-5 actions: {r['top_actions']} cos={r['top_cos']} gate={r['reason']} first_relevant_rank={r['hit_rank']}", ""]
    L += ["## Gate behaviour on golden", "", f"reasons: `{dict(gate['reasons'])}`", f"precision P(hit@5 | sufficient): {gate['precision_hit@5_given_sufficient']}",
          f"sufficient verdicts on queries without a usable reference: {gate['sufficient_without_reference']}", "",
          "| intent | n | sufficient rate |", "|---|---|---|"] + [f"| {k} | {v['n']} | {v['sufficient']} |" for k, v in gate["sufficient_by_intent"].items()]
    (OUT / "failure_analysis_draft.md").write_text("\n".join(L), encoding="utf-8")
    print(json.dumps({k: analysis[k] for k in ("reference_coverage", "failure_categories", "n_misses", "uncategorised_misses")}, indent=1))
    print("CIs:", json.dumps(cis[final]))
    print("gate:", json.dumps({k: (dict(v) if isinstance(v, Counter) else v) for k, v in gate.items() if k != "sufficient_by_intent"}))


if __name__ == "__main__":
    main()
