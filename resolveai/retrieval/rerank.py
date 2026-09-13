"""Outcome-aware reranking: a SMALL, explicit bonus on top of the fused rank score.

The outcome signal is weak (hand-checked precision: positive 0.72, negative 1.00). It is therefore:
- never the primary relevance score,
- never a gold label,
- bounded so it cannot overturn strong lexical/semantic evidence: the maximum total bonus equals the RRF score gap between
  rank 1 and rank ~3 at k=60 (about 0.0005), i.e. it reorders near-ties only,
- exposed per item in `scores["outcome_bonus"]` so its contribution is auditable.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OutcomeBonus:
    positive: float = 0.0004      # substantive reply followed by a positive customer turn
    substantive: float = 0.0002   # substantive (non-DM) reply, regardless of follow-up
    negative: float = -0.0003     # customer said it did not work
    dm_handoff: float = -0.0002   # pure handoff line: nothing to ground on
    enabled: bool = True

    def bonus(self, *, outcome: str, substantive: bool, dm_handoff: bool) -> float:
        if not self.enabled:
            return 0.0
        b = 0.0
        if substantive:
            b += self.substantive
            if outcome == "positive":
                b += self.positive
        if outcome == "negative":
            b += self.negative
        if dm_handoff:
            b += self.dm_handoff
        return b


def apply_bonus(candidates: list[dict], bonus: OutcomeBonus) -> list[dict]:
    """candidates: dicts with keys rrf, outcome, substantive, dm_handoff, doc. Adds outcome_bonus and final; re-sorts."""
    for c in candidates:
        c["outcome_bonus"] = bonus.bonus(outcome=c["outcome"], substantive=c["substantive"], dm_handoff=c["dm_handoff"])
        c["final"] = c["rrf"] + c["outcome_bonus"]
    return sorted(candidates, key=lambda c: (-c["final"], c["doc"]))
