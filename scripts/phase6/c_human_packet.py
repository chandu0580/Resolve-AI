"""Phase 6-C: build the blinded human-scoring packet (never fills the human columns).
  python scripts/phase6/c_human_packet.py [n=50]
Stratification (deterministic, seed 42): ResolveAI / simple-ML / direct-LLM responses; autonomous replies, clarifications,
handoffs; judge-scored good and bad responses where scores exist; difficult golden rows (multi-intent, insufficient context,
taxonomy gap, should-escalate). The packet carries a blind example_id only; the mapping example_id -> (gid, system) is
stored separately in data/human_eval/_packet_key.json and must not be opened while scoring.
Writes data/human_eval/human_scoring_packet.csv, data/human_eval/_packet_key.json, data/human_eval/packet_manifest.json
"""
from __future__ import annotations

import csv
import hashlib
import json
import random
import sys
from pathlib import Path

import resolveai  # noqa: F401
from resolveai.evaluation import load_golden
from resolveai.evaluation.judge import BINARY, DIMENSIONS, conversation_block, evidence_block
from resolveai.evaluation.records import read_records

OUT = Path("data/human_eval")
OUT.mkdir(parents=True, exist_ok=True)
RUNS = Path("artifacts/evaluation/runs")
SYSTEMS = ["resolveai_full", "B1_simple_ml", "B2_direct_llm"]
SEED = 42


def main() -> None:
    n_target = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    gold = load_golden().set_index("gid")
    recs = {s: {r.gid: r for r in read_records(RUNS / f"{s}.jsonl")} for s in SYSTEMS if (RUNS / f"{s}.jsonl").exists()}
    judge = {}
    jp = Path("artifacts/evaluation/judge_results.jsonl")
    if jp.exists():
        for x in (json.loads(line) for line in jp.read_text(encoding="utf-8").splitlines() if line.strip()):
            if not x.get("failed") and x.get("judge_model") == "glm-5.2":
                judge[(x["gid"], x["system"])] = x
    rng = random.Random(SEED)
    chosen: list[tuple[str, str]] = []

    def take(cands, k, label):
        cands = [c for c in cands if c not in chosen]
        rng.shuffle(cands)
        picked = cands[:k]
        chosen.extend(picked)
        return [(label, c) for c in picked]

    strata = []
    full = recs.get("resolveai_full", {})
    strata += take([(g, "resolveai_full") for g, r in full.items() if r.action == "AUTO_HANDLE"], 9, "resolveai_auto")
    strata += take([(g, "resolveai_full") for g, r in full.items() if r.action == "CLARIFICATION_REQUIRED"], 6, "resolveai_clarify")
    strata += take([(g, "resolveai_full") for g, r in full.items() if r.action == "HUMAN_HANDOFF"], 5, "resolveai_handoff")
    for s, k in (("B1_simple_ml", 10), ("B2_direct_llm", 10)):
        if s in recs:
            scored = [((g, s), judge[(g, s)]["groundedness"] + judge[(g, s)]["actionability"]) for g in recs[s] if (g, s) in judge]
            if scored:
                scored.sort(key=lambda x: x[1])
                strata += take([c for c, _ in scored[: max(3, len(scored) // 4)]], k // 2, f"{s}_judged_low")
                strata += take([c for c, _ in scored[-max(3, len(scored) // 4):]], k - k // 2, f"{s}_judged_high")
            else:
                strata += take([(g, s) for g in recs[s]], k, f"{s}_random")
    hard = [g for g in gold.index if gold.loc[g].multi_intent or gold.loc[g].insufficient_context or gold.loc[g].taxonomy_gap or gold.loc[g].should_escalate]
    strata += take([(g, s) for g in hard for s in recs], 6, "difficult_rows")
    strata += take([(g, s) for s in recs for g in recs[s]], max(0, n_target - len(chosen)), "random_fill")
    rng.shuffle(strata)
    key, rows = {}, []
    for label, (gid, system) in strata:
        r = recs[system][gid]
        eid = f"ex{hashlib.sha256(f'{SEED}:{gid}:{system}'.encode()).hexdigest()[:8]}"
        key[eid] = {"gid": gid, "system": system, "stratum": label, "action": r.action, "response_kind": r.response_kind}
        rows.append({"example_id": eid, "conversation": conversation_block(r), "evidence": evidence_block(r), "candidate_response": r.response,
                     **{f"human_{d}": "" for d in DIMENSIONS}, **{f"human_{b}": "" for b in BINARY}, "human_notes": ""})
    rows.sort(key=lambda x: x["example_id"])
    with (OUT / "human_scoring_packet.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    (OUT / "_packet_key.json").write_text(json.dumps(key, indent=1), encoding="utf-8")
    from collections import Counter

    (OUT / "packet_manifest.json").write_text(json.dumps({"n": len(rows), "seed": SEED, "systems": dict(Counter(v["system"] for v in key.values())), "strata": dict(Counter(v["stratum"] for v in key.values())),
                                                          "actions": dict(Counter(v["action"] for v in key.values())), "judge_scores_used_for_stratification": bool(judge),
                                                          "packet_sha256": hashlib.sha256((OUT / "human_scoring_packet.csv").read_bytes()).hexdigest(), "human_columns_filled_by": "nobody yet (blank)"}, indent=1), encoding="utf-8")
    print(f"wrote {len(rows)} examples; strata: {dict(Counter(v['stratum'] for v in key.values()))}")


if __name__ == "__main__":
    main()
