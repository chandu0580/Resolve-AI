"""Phase 6-F: update README.md and docs/DECISIONS.md from the measured evaluation artifacts (run once at the end of Phase 6).
  python scripts/phase6/f_write_docs.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EV = ROOT / "artifacts" / "evaluation"
J = lambda name: json.loads((EV / name).read_text(encoding="utf-8")) if (EV / name).exists() else {}  # noqa: E731


def main() -> None:
    H, BC, AG, PW, MAN, OFF, RQ = J("headline_metrics.json"), J("baseline_comparison.json"), J("judge_agreement.json"), J("pairwise_results.json"), J("reproduction_manifest.json"), J("offline_ablations.json"), J("reply_quality.json")
    S = BC.get("systems", {})
    fmt = lambda ci: f"{ci['point']:.3f} [{ci['ci_low']:.3f}, {ci['ci_high']:.3f}]" if ci else "n/a"  # noqa: E731
    jq = (RQ.get("primary") or {}).get("systems", {})
    human = AG.get("human") or {}
    cross = AG.get("cross_family") or {}
    b1, b2, full = S.get("B1_simple_ml", {}), S.get("B2_direct_llm", {}), S.get("resolveai_full", {})

    # ---------------- README ----------------
    rd = ROOT / "README.md"
    t = rd.read_text(encoding="utf-8")
    t = t.replace("**Project status: Phase 5 of 10 complete**", "**Project status: Phase 6 of 10 complete (evaluation science + judge validation; human study pending)**")
    marker = "## Resolution intelligence (Phase 5)"
    sec = f"""## Evaluation harness (Phase 6)
```bash
python scripts/evaluate.py --cached          # no API calls; verifies golden + artifact hashes, recomputes every headline number (~{MAN.get('runtime_seconds', 0):.0f} s)
python scripts/evaluate.py --live            # re-runs every system, the judge and the offline ablations (needs LLM_API_KEY; hours)
python scripts/phase6/c_human_packet.py      # rebuild the blinded human-scoring packet
```
Headline (golden, n=197, 95% bootstrap CI): intent macro-F1 {fmt(H.get('intent_macro_f1'))}; escalation recall {fmt(H.get('escalation_recall'))}, precision {H.get('escalation_precision')};
AUTO {H.get('auto_handle_rate')} / CLARIFY {H.get('clarification_rate')} / HANDOFF {H.get('handoff_rate')}; safe autonomous resolutions {H.get('safe_auto_handle_count')} (unsafe {H.get('unsafe_auto_handle_count')});
judge groundedness {(H.get('judge') or {}).get('groundedness')} / hallucination rate {H.get('judge_hallucination_rate')} (GLM-5.2 judge, unvalidated by a human until the packet is scored).
Baselines: trivial, TF-IDF+LR + nearest-neighbour reply + rules, and a direct GLM-5.2 prompt (`artifacts/evaluation/baseline_comparison.md`).
**Human study: {human.get('status', 'PENDING_HUMAN_RATINGS')}** - fill `data/human_eval/human_scoring_packet.csv` following `docs/HUMAN_JUDGE_GUIDE.md`, then re-run the cached command.
Read `artifacts/evaluation/misleading_headline.md` before quoting any number above.

"""
    if "## Evaluation harness (Phase 6)" not in t:
        t = t.replace(marker, sec + marker)
    t = t.replace("scripts/phase5/   retrieval/resolution benchmark, risk hardening, drafting A/B, verifier audit, short-circuit, golden run",
                  "scripts/phase5/   retrieval/resolution benchmark, risk hardening, drafting A/B, verifier audit, short-circuit, golden run\nscripts/phase6/   system runs, judge, human packet, offline ablations, narrative reports; scripts/evaluate.py is the entry point")
    t = t.replace("artifacts/        Phase 0 reports, brand ranking, technology comparison, Phase 1A model decision, retrieval/ (Phase 2), intelligence/ (Phase 3), agent/ (Phase 4), resolution/ (Phase 5)",
                  "artifacts/        Phase 0 reports, brand ranking, technology comparison, Phase 1A model decision, retrieval/ (Phase 2), intelligence/ (Phase 3), agent/ (Phase 4), resolution/ (Phase 5), evaluation/ (Phase 6)")
    t = t.replace("docs/             ARCHITECTURE.md, EVALUATION.md, DECISIONS.md", "docs/             ARCHITECTURE.md, EVALUATION.md, DECISIONS.md, HUMAN_JUDGE_GUIDE.md")
    t = t.replace("resolveai/        package: config, schemas, data, trust (PII), models (taxonomy, weak labels, frozen classifier), retrieval (KB,",
                  "resolveai/        package: config, schemas, data, trust (PII), models (taxonomy, weak labels, frozen classifier), evaluation (records, metrics, bootstrap, baselines, judge, slices, agreement, reporting), retrieval (KB,")
    rd.write_text(t, encoding="utf-8")

    # ---------------- DECISIONS ----------------
    pw_b1 = PW.get("resolveai_full_vs_B1_simple_ml", {})
    pw_b2 = PW.get("resolveai_full_vs_B2_direct_llm", {})
    comps = BC.get("paired_differences_vs_resolveai", {})
    d_b2 = comps.get("resolveai_full_minus_B2_direct_llm", {})
    d_rl = comps.get("resolveai_full_minus_minus_risk_llm", {})
    weak = OFF.get("minus_gate_weak_rows", {})
    D = f"""
57. **The proof is separate from the system: one harness, one record format, metrics as pure functions.** `resolveai/evaluation/`
    (records, metrics, bootstrap, baselines, systems, judge, slices, agreement, reporting) never imports agent decision logic; every
    system - ResolveAI, four ablations, three baselines - writes the same SystemRecord so one code path computes every table.
58. **Three baselines, not crippled, with stated information parity.** B0 majority-silver intent + modal "DM us" reply; B1 TF-IDF+LR
    (C chosen on silver dev) + nearest-neighbour historical reply + the same deterministic risk rules ResolveAI uses; B2 one GLM-5.2
    call with the taxonomy and the guide's escalation criteria and the FULL thread (ResolveAI sees a truncated thread). Golden results:
    B1 intent macro-F1 {(b1.get('intent') or {}).get('macro_f1')}, B2 {(b2.get('intent') or {}).get('macro_f1')}, ResolveAI {(full.get('intent') or {}).get('macro_f1')};
    unsafe autonomous replies B1 {(b1.get('autonomy') or {}).get('unsafe_auto_handle_count')}, B2 {(b2.get('autonomy') or {}).get('unsafe_auto_handle_count')}, ResolveAI {(full.get('autonomy') or {}).get('unsafe_auto_handle_count')}.
59. **"Safe autonomous resolution" is strict and deterministic.** AUTO_HANDLE on a row the annotators did not mark for escalation AND
    (a verified troubleshooting reply with evidence references OR the exact intent-appropriate template for a closure/non-English row).
    Copied historical replies and direct-LLM replies never qualify (no grounding contract). ResolveAI {H.get('safe_auto_handle_count')} safe / {H.get('unsafe_auto_handle_count')} unsafe of {H.get('n')}.
60. **Judge rubric frozen before scoring, judge isolated from system identity, A/B order seeded.** rubric-v1 (6 ordinal dimensions with
    anchors at every level, 2 binary), GLM-5.2 at temperature 0, cap 1200 (a 3-draft dev smoke test used up to 859 tokens), strict parsing,
    failures recorded not dropped. The judge shares the drafter's model family (stated risk); qwen3.8-27b via Groq scores a subset as a
    second family. Pairwise ResolveAI vs B1 win/tie/loss {pw_b1.get('win')}/{pw_b1.get('tie')}/{pw_b1.get('loss')}; vs B2 {pw_b2.get('win')}/{pw_b2.get('tie')}/{pw_b2.get('loss')}.
61. **No human rating is fabricated.** The blinded packet ({human.get('n_examples', 0)} examples) and docs/HUMAN_JUDGE_GUIDE.md exist; judge_agreement.md
    says {human.get('status', 'PENDING_HUMAN_RATINGS')} until the owner scores it. Every earlier hand-check is listed as AI annotation in docs/EVALUATION.md.
62. **Uncertainty is reported with every headline number.** 1000x seeded bootstrap; paired resampling for differences; intervals that overlap
    are called not distinguishable. ResolveAI minus B2 direct-LLM: escalation recall {d_b2.get('escalation_recall', {}).get('difference')} [{d_b2.get('escalation_recall', {}).get('ci_low')}, {d_b2.get('escalation_recall', {}).get('ci_high')}],
    safe-auto rate {d_b2.get('safe_auto_rate', {}).get('difference')} [{d_b2.get('safe_auto_rate', {}).get('ci_low')}, {d_b2.get('safe_auto_rate', {}).get('ci_high')}].
63. **Ablations are single switches on the production agent; the verifier and the gate are only removed offline.** Rules-only risk
    (minus_risk_llm) changes safe-auto rate by {d_rl.get('safe_auto_rate', {}).get('difference')} and escalation recall by {d_rl.get('escalation_recall', {}).get('difference')} versus the full system;
    drafting on WEAK evidence offline: {weak.get('n_weak_rows')} rows, {weak.get('drafts_verified')} verified, judge hallucination {weak.get('hallucination_rate')} (the abstention curve).
64. **Two rule bugs found by the evaluation are documented, not patched, in this phase.** `<PHONE>`-style tokens never fire the
    private-info rule (word boundary before `<`), and "dm i sent" misses the repeat-contact rule; both are the golden false negatives.
    The evaluated system is the frozen Phase 5 system; the fixes and regression tests are the first Phase 7 item.
65. **Cached reproduction is the default; live is explicit.** `python scripts/evaluate.py --cached` verifies the golden hash and the
    SHA-256 of every input artifact, recomputes everything in {MAN.get('runtime_seconds')} s with no API call; `--live` re-runs the
    systems, the judge and the offline ablations. Cache-served runs report the tokens their calls consumed live, so cost is comparable; latency is not.
"""
    dp = ROOT / "docs/DECISIONS.md"
    txt = dp.read_text(encoding="utf-8")
    if "57. **The proof is separate" not in txt:
        dp.write_text(txt.rstrip() + "\n" + D, encoding="utf-8")
    print("docs updated; cross-family n =", cross.get("n"), "; judge systems:", list(jq))


if __name__ == "__main__":
    main()
