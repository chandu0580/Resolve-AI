"""Evidence contracts (Phase 2). Everything the UI, the Trust layer and the evaluation need to know about WHAT was
retrieved, WHY, and whether it is ENOUGH. Customer text is PII-redacted upstream; nothing raw is stored here.

Vocabulary:
- retrieved: candidates returned by the retriever (may be irrelevant).
- relevant:  candidates the engine classifies as operationally relevant (structured signals, not a gold label).
- sufficient: the deterministic gate says the relevant evidence supports an autonomous, grounded response.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Outcome = Literal["positive", "negative", "mixed", "none"]
SufficiencyReason = Literal[
    "strong_consistent_evidence",
    "weak_similarity",
    "insufficient_resolution_evidence",
    "conflicting_evidence",
    "ambiguous_intent",
    "no_relevant_evidence",
    "customer_history_risk",
    "insufficient_query",
    "mixed_resolution",
    "weak_resolution_evidence",
    "not_applicable",          # final product pass: nothing to ground (a bare greeting); retrieval did not run
]
ActionClass = Literal["update", "restart", "reset", "settings", "article", "ask_info", "dm_handoff", "other"]
RetrievalSource = Literal["customer", "reply", "pair", "dual"]
SufficiencyLevel = Literal["INSUFFICIENT", "WEAK", "SUFFICIENT", "STRONG"]
Consistency = Literal["consistent", "mixed_resolution", "no_resolution"]


class EvidenceQuality(BaseModel):
    """Operational classification of one candidate. Signals, not ground truth."""
    semantic_relevance: float = Field(ge=-1, le=1, description="dense cosine between query and candidate customer message")
    lexical_relevance: float = Field(ge=0, description="BM25 score (0 when no lexical overlap)")
    intent_match: bool | None = Field(default=None, description="candidate weak intent == query intent when the query intent is known")
    candidate_intent: str = Field(default="", description="weak (keyword) intent of the candidate; noisy by construction")
    resolution_relevance: bool = Field(default=False, description="substantive reply (not a DM handoff) that states an action")
    action_class: ActionClass = "other"
    temporal_eligible: bool = True
    same_customer: bool = False
    quality: Literal["strong", "usable", "weak"] = "weak"


class EvidenceItem(BaseModel):
    """One historical (customer message -> brand reply) pair with full provenance."""
    evidence_id: str = Field(description="brand_tweet_id of the historical reply (dataset-assigned, deterministic)")
    thread_id: str = Field(description="customer_tweet_id of the historical customer message (thread anchor)")
    source_row_id: str = Field(description="row id inside the shipped subsample: customer_tweet_id")
    customer_message: str
    brand_reply: str
    created_at: str
    outcome: Outcome = "none"
    dm_handoff: bool = False
    substantive: bool = True
    retrieval_method: str = Field(description="bm25 | dense:<model> | hybrid:<model> | hybrid+outcome:<model>")
    retrieval_source: RetrievalSource = Field(default="customer", description="which index surfaced the item: customer (problem similarity), reply (resolution similarity), pair, or dual (both)")
    rank: int = Field(ge=1)
    ranks: dict[str, int] = Field(default_factory=dict, description="rank in each underlying ranked list (bm25, dense)")
    scores: dict[str, float] = Field(default_factory=dict, description="bm25, dense, rrf, outcome_bonus, final")
    quality: EvidenceQuality
    source: dict[str, str] = Field(default_factory=dict, description="dataset provenance: dataset, brand, preprocessing_version, kb_hash")


class ResolutionCandidate(BaseModel):
    """A cluster of historical replies that prescribe the same kind of resolution. Never fabricated: every candidate is the
    text of a real historical reply plus the ids of the replies that agree with it."""
    action_class: ActionClass
    representative_reply: str
    representative_id: str
    evidence_ids: list[str]
    support_count: int
    mean_similarity: float
    positive_outcomes: int = 0
    share: float = Field(ge=0, le=1, description="share of resolution-bearing support this cluster holds")


class SufficiencySignals(BaseModel):
    """Measurable inputs to the gate; exposed so the Trust layer and the UI can inspect the decision."""
    n_retrieved: int
    n_relevant: int
    query_content_tokens: int = Field(default=0, description="content tokens in the query after removing URLs, redaction tokens and stopwords")
    query_symptom_tokens: int = Field(default=0, description="query tokens naming a symptom/feature (gate-v3 specificity guard)")
    top_similarity: float
    similarity_margin: float = Field(description="top-1 cosine minus top-3 cosine")
    intent_agreement: float = Field(ge=0, le=1, description="share of top-k sharing the modal candidate intent")
    modal_intent: str = ""
    query_intent_agreement: float | None = Field(default=None, description="share of top-k matching the query intent, if known")
    support_count: int = Field(description="independent, resolution-bearing substantive cases above the support similarity")
    resolution_bearing: int = Field(description="substantive cases with a positive outcome signal")
    action_classes: dict[str, int] = Field(default_factory=dict)
    conflicting: bool = False
    same_customer_count: int = 0


class EvidenceSet(BaseModel):
    query: str = ""
    query_intent: str | None = None
    retriever: str = ""
    items: list[EvidenceItem] = Field(default_factory=list, description="ranked candidates (retrieved)")
    n_retrieved: int = 0
    n_relevant: int = 0
    sufficient: bool = False
    sufficiency_reason: SufficiencyReason = "no_relevant_evidence"
    sufficiency_level: SufficiencyLevel = "INSUFFICIENT"
    resolution_confidence: float = Field(default=0.0, ge=0, le=1, description="measurable evidence score (not an LLM probability); formula in retrieval/resolution.py")
    consistency: Consistency = "no_resolution"
    resolution_candidates: list[ResolutionCandidate] = Field(default_factory=list, description="resolution clusters, best first")
    signals: SufficiencySignals | None = None
    gate_version: str = ""
    latency_ms: float = 0
    quarantined_ids: list[str] = Field(default_factory=list, description="retrieved items excluded before the gate because their text reads as instructions (Phase 9)")

    @property
    def relevant(self) -> list[EvidenceItem]:
        return [i for i in self.items if i.quality.quality != "weak"]
