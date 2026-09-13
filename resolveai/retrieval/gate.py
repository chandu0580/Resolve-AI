"""Deterministic evidence-sufficiency gate.

Not "top similarity > threshold". The gate reads structured signals from the ranked candidates and returns a verdict with a
reason code, in a fixed priority order:
  0. insufficient_query             the query has too few content tokens to retrieve on (bare URL, "fix this", "iPhone 7 Plus")
  1. no_relevant_evidence           nothing retrieved, or top similarity below the relevance floor
  2. weak_similarity                top similarity below the support level
  3. customer_history_risk          supporting evidence is mostly the same customer's own earlier thread (not independent)
  4. ambiguous_intent               retrieved cases do not agree on what the problem is
  5. conflicting_evidence           substantive cases prescribe different actions with no majority
  6. insufficient_resolution_evidence  too few independent substantive supporting cases that state a RESOLUTION
     (action class update/restart/reset/settings/article); clarifying questions do not count as support
  7. strong_consistent_evidence     sufficient = True
Thresholds are tuned on DEVELOPMENT data only (scripts/phase2/run_retrieval_benchmark.py, gate_v2.py) and frozen in
gate_config.json. gate-v2 added rules 0 and the resolution requirement in 6 after a hand-check of gate-v1 verdicts
(artifacts/retrieval/failure_analysis.md); thresholds were re-tuned on DEV afterwards.
"""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

from resolveai.retrieval.bm25 import tokenize
from resolveai.schemas.evidence import EvidenceItem, SufficiencySignals

RESOLUTION_ACTIONS = {"update", "restart", "reset", "settings", "article"}


def content_tokens(query: str) -> int:
    return sum(1 for t in tokenize(query) if not t.startswith("<"))

GATE_VERSION = "gate-v2"
_CONFIG_PATH = Path(__file__).with_name("gate_config.json")


@dataclass(frozen=True)
class GateConfig:
    relevance_floor: float = 0.45     # below: no_relevant_evidence
    support_similarity: float = 0.60  # a candidate counts as support at or above this cosine
    min_support: int = 2              # independent substantive supporting cases required
    min_intent_agreement: float = 0.5 # share of top-k sharing the modal candidate intent
    min_query_tokens: int = 3         # below: insufficient_query
    top_k: int = 5
    version: str = GATE_VERSION

    @classmethod
    def load(cls) -> GateConfig:
        if _CONFIG_PATH.exists():
            d = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
            return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
        return cls()

    def save(self, path: Path = _CONFIG_PATH) -> None:
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")


def signals_from(items: list[EvidenceItem], cfg: GateConfig, query_intent: str | None = None, query: str = "") -> SufficiencySignals:
    top = items[: cfg.top_k]
    sims = [i.quality.semantic_relevance for i in top]
    top_sim = sims[0] if sims else 0.0
    margin = (sims[0] - sims[2]) if len(sims) >= 3 else (sims[0] - sims[-1] if sims else 0.0)
    intents = Counter(i.quality.candidate_intent for i in top)
    modal, modal_n = (intents.most_common(1)[0] if intents else ("", 0))
    agreement = modal_n / len(top) if top else 0.0
    q_agree = (sum(1 for i in top if i.quality.intent_match) / len(top)) if (top and query_intent) else None
    support = [i for i in top if i.substantive and i.quality.semantic_relevance >= cfg.support_similarity and i.quality.action_class in RESOLUTION_ACTIONS]
    same_customer = sum(1 for i in support if i.quality.same_customer)
    independent = [i for i in support if not i.quality.same_customer]
    actions = Counter(i.quality.action_class for i in top if i.substantive)
    conflicting = False
    if sum(actions.values()) >= 2:
        best = actions.most_common(1)[0][1]
        conflicting = len(actions) >= 2 and best / sum(actions.values()) < 0.5
    return SufficiencySignals(
        n_retrieved=len(items), n_relevant=sum(1 for i in items if i.quality.quality != "weak"), query_content_tokens=content_tokens(query), top_similarity=top_sim,
        similarity_margin=margin, intent_agreement=agreement, modal_intent=modal, query_intent_agreement=q_agree,
        support_count=len(independent), resolution_bearing=sum(1 for i in independent if i.outcome == "positive"),
        action_classes=dict(actions), conflicting=conflicting, same_customer_count=same_customer,
    )


def decide(items: list[EvidenceItem], cfg: GateConfig, query_intent: str | None = None, query: str | None = None) -> tuple[bool, str, SufficiencySignals]:
    s = signals_from(items, cfg, query_intent, query or "")
    if query is not None and s.query_content_tokens < cfg.min_query_tokens:
        return False, "insufficient_query", s
    if not items or s.top_similarity < cfg.relevance_floor:
        return False, "no_relevant_evidence", s
    if s.top_similarity < cfg.support_similarity:
        return False, "weak_similarity", s
    if s.same_customer_count and s.same_customer_count >= max(1, s.support_count):
        return False, "customer_history_risk", s
    if s.intent_agreement < cfg.min_intent_agreement:
        return False, "ambiguous_intent", s
    if s.conflicting:
        return False, "conflicting_evidence", s
    if s.support_count < cfg.min_support:
        return False, "insufficient_resolution_evidence", s
    return True, "strong_consistent_evidence", s
