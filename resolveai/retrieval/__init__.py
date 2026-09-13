"""Historical-resolution retrieval: the evidence layer. Phase 2: BM25 + dense (MiniLM / BGE-small) fused by RRF, outcome-aware
rerank bonus, deterministic sufficiency gate (gate-v2). Phase 5: customer / reply / pair representations, resolution-centred
reranking, resolution clusters, consistency, resolution confidence and the four-state gate-v3.
Entry point: resolveai.retrieval.engine.Retriever."""
from resolveai.retrieval.engine import Retriever, RetrieverConfig
from resolveai.retrieval.gate import GateConfig
from resolveai.retrieval.kb import KnowledgeBase
from resolveai.retrieval.rerank import OutcomeBonus
from resolveai.retrieval.resolution import GateV3Config, RerankWeights

__all__ = ["GateConfig", "GateV3Config", "KnowledgeBase", "OutcomeBonus", "RerankWeights", "Retriever", "RetrieverConfig"]
