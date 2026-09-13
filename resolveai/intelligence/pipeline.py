"""Pre-generation pipeline (Phase 3 architecture):
    conversation -> Context Builder -> Intent Classifier -> Query Constructor -> BGE-small Retrieval -> Evidence Gate
No LLM call, no customer-facing generation, no escalation decision happens here. Returns everything the later Trust layer
and policy need, with per-stage latency.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import pandas as pd

from resolveai.intelligence.classifier import IntentService
from resolveai.intelligence.context import ContextBundle, build_context
from resolveai.intelligence.query import QueryPlan, build_query
from resolveai.retrieval import GateConfig, KnowledgeBase, Retriever, RetrieverConfig
from resolveai.schemas.core import ConversationContext, EvidenceSet, IntentResult


@dataclass
class Understanding:
    bundle: ContextBundle
    intent: IntentResult
    plan: QueryPlan
    evidence: EvidenceSet
    latency_ms: dict[str, float] = field(default_factory=dict)

    @property
    def total_ms(self) -> float:
        return sum(self.latency_ms.values())


class PreGenerationPipeline:
    def __init__(self, kb: KnowledgeBase | None = None, retriever: Retriever | None = None, intents: IntentService | None = None):
        self.kb = kb or KnowledgeBase.build(dense_models=[RetrieverConfig().model], with_bm25=False)
        self.retriever = retriever or Retriever(self.kb, RetrieverConfig(), gate=GateConfig.load())
        self.intents = intents or IntentService()

    def understand(self, message: str, context: ConversationContext | None = None, *, customer_author: str | None = None,
                   created_at: pd.Timestamp | str | None = None) -> Understanding:
        lat: dict[str, float] = {}
        t = time.perf_counter()
        bundle = build_context(message, context)
        lat["context_ms"] = (time.perf_counter() - t) * 1000
        t = time.perf_counter()
        intent = self.intents.classify(bundle)
        lat["classify_ms"] = (time.perf_counter() - t) * 1000
        t = time.perf_counter()
        plan = build_query(bundle, intent)
        lat["query_ms"] = (time.perf_counter() - t) * 1000
        t = time.perf_counter()
        evidence = self.retriever.retrieve(plan.text, query_intent=(intent.intent if not intent.insufficient_context else None), customer_author=customer_author,
                                           query_created_at=created_at, allowed_intents=plan.allowed_intents, boost=plan.boost)
        lat["retrieve_ms"] = (time.perf_counter() - t) * 1000
        return Understanding(bundle=bundle, intent=intent, plan=plan, evidence=evidence, latency_ms={k: round(v, 2) for k, v in lat.items()})
