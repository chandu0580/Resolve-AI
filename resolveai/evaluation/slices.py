"""Slice definitions over golden rows (gold flags) and over system records (confidence band, evidence level)."""
from __future__ import annotations

from collections import Counter

import pandas as pd

from resolveai.evaluation.records import SystemRecord

SHORT_CHARS = 40


def gold_slices(gold: pd.DataFrame) -> dict[str, set[str]]:
    """Row-level slices from the frozen golden set only (no system output)."""
    counts = Counter(gold.intent)
    rare = {k for k, v in counts.items() if v <= 14}
    s = {
        "all": set(gold.gid),
        "short_message": set(gold[gold.customer_message.str.len() < SHORT_CHARS].gid),
        "normal_message": set(gold[gold.customer_message.str.len() >= SHORT_CHARS].gid),
        "first_turn": set(gold[gold.n_context_turns.astype(int) == 0].gid),
        "multi_turn": set(gold[gold.n_context_turns.astype(int) > 0].gid),
        "customer_seen_in_kb": set(gold[gold.customer_seen_in_kb.astype(str).str.lower() == "true"].gid),
        "customer_unseen": set(gold[gold.customer_seen_in_kb.astype(str).str.lower() != "true"].gid),
        "multi_intent": set(gold[gold.multi_intent].gid),
        "taxonomy_gap": set(gold[gold.taxonomy_gap].gid),
        "insufficient_context": set(gold[gold.insufficient_context].gid),
        "evidence_unavailable": set(gold[gold.evidence_unavailable].gid),
        "gold_should_escalate": set(gold[gold.should_escalate].gid),
        "gold_should_not_escalate": set(gold[~gold.should_escalate].gid),
        "common_intent": set(gold[~gold.intent.isin(rare)].gid),
        "rare_intent": set(gold[gold.intent.isin(rare)].gid),
    }
    return s


def record_slices(recs: list[SystemRecord]) -> dict[str, set[str]]:
    """Slices that depend on the evaluated system's own outputs (reported per system)."""
    s = {
        "confidence_HIGH": {r.gid for r in recs if r.intent_band == "HIGH"},
        "confidence_MEDIUM": {r.gid for r in recs if r.intent_band == "MEDIUM"},
        "confidence_LOW": {r.gid for r in recs if r.intent_band == "LOW"},
        "evidence_sufficient": {r.gid for r in recs if r.evidence_sufficient},
        "evidence_insufficient": {r.gid for r in recs if not r.evidence_sufficient},
    }
    return {k: v for k, v in s.items() if v}


def slice_table(recs: list[SystemRecord], gold: pd.DataFrame, slices: dict[str, set[str]]) -> list[dict]:
    g = gold.set_index("gid")
    rows = []
    for name, gids in slices.items():
        rs = [r for r in recs if r.gid in gids]
        if not rs:
            continue
        n = len(rs)
        acc = sum(1 for r in rs if r.intent_pred == g.loc[r.gid].intent) / n
        pos = [r for r in rs if g.loc[r.gid].should_escalate]
        esc_recall = (sum(1 for r in pos if r.escalate_pred) / len(pos)) if pos else None
        neg = [r for r in rs if not g.loc[r.gid].should_escalate]
        false_esc = (sum(1 for r in neg if r.escalate_pred) / len(neg)) if neg else None
        auto = [r for r in rs if r.action == "AUTO_HANDLE"]
        rows.append({"slice": name, "n": n, "intent_accuracy": round(acc, 3), "escalation_recall": (round(esc_recall, 3) if esc_recall is not None else None), "n_gold_escalate": len(pos),
                     "false_escalation_rate": (round(false_esc, 3) if false_esc is not None else None), "auto_rate": round(len(auto) / n, 3), "clarify_rate": round(sum(1 for r in rs if r.action == "CLARIFICATION_REQUIRED") / n, 3),
                     "handoff_rate": round(sum(1 for r in rs if r.action == "HUMAN_HANDOFF") / n, 3), "unsafe_auto": sum(1 for r in auto if g.loc[r.gid].should_escalate),
                     "evidence_sufficient_rate": round(sum(1 for r in rs if r.evidence_sufficient) / n, 3)})
    return rows
