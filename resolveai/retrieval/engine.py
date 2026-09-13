"""Retrieval engine: the single entry point the agent, the API and the benchmark use.

    retriever = Retriever(kb, RetrieverConfig())
    evidence = retriever.retrieve(query, query_intent=..., customer_author=..., query_created_at=...)

Phase 2: dense (BGE-small) / BM25 / hybrid over the CUSTOMER-message index, substantive-first, gate-v2.
Phase 5: dual-path retrieval (customer index + reply/pair index fused by RRF with explicit provenance per item),
resolution-centred reranking, resolution clusters + consistency, resolution confidence and the four-state gate-v3.
Every Phase-2 option remains selectable so both configurations run on the same protocol.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from resolveai.retrieval.dense import Embedder
from resolveai.retrieval.fusion import rrf
from resolveai.retrieval.gate import GateConfig, decide
from resolveai.retrieval.kb import KnowledgeBase
from resolveai.retrieval.rerank import OutcomeBonus, apply_bonus
from resolveai.retrieval.resolution import GateV3Config, RerankWeights, decide_v3, is_resolution_bearing, rerank
from resolveai.schemas.evidence import EvidenceItem, EvidenceQuality, EvidenceSet
from resolveai.trust.pii import redact_pii

QUALITY_STRONG = 0.70
QUALITY_USABLE = 0.55
NON_RESOLUTION_CLASSES = ("other", "dm_handoff", "ask_info")


@dataclass(frozen=True)
class RetrieverConfig:
    """Defaults = the configuration selected by the Phase 5 benchmark (artifacts/resolution/retrieval_results.md,
    docs/DECISIONS.md). Phase-2 options (bm25/hybrid, customer-only, gate-v2) remain available as measured alternatives."""
    method: str = "dense"                  # bm25 | dense | hybrid   (BM25 applies to the customer path only)
    model: str = "BAAI/bge-small-en-v1.5"  # dense model (ignored for bm25)
    paths: tuple[str, ...] = ("pair",)     # dense representations searched: customer | reply | pair; >1 => RRF fusion. Dev-selected: pair (customer+pair dual within noise)
    rrf_k: int = 20
    candidate_k: int = 50                  # depth of each ranked list before fusion
    top_k: int = 5
    outcome_bonus: OutcomeBonus = field(default_factory=lambda: OutcomeBonus(enabled=False))  # measured: no effect
    substantive_first: bool = True         # structural lever (not the outcome signal): substantive replies before DM handoffs
    rerank: str = "resolution"             # none | resolution   (resolution reranker replaces substantive_first + bonus)
    gate: str = "v3"                       # v2 | v3

    @property
    def name(self) -> str:
        slug = Embedder(self.model).slug if self.method != "bm25" else ""
        base = {"bm25": "bm25", "dense": f"dense:{slug}", "hybrid": f"hybrid:{slug}"}[self.method]
        return (base + ":" + "+".join(self.paths) + ("+outcome" if self.outcome_bonus.enabled else "")
                + ("+subst" if self.substantive_first and self.rerank == "none" else "") + ("+rr" if self.rerank == "resolution" else "") + f"+gate{self.gate}")


class Retriever:
    def __init__(self, kb: KnowledgeBase, cfg: RetrieverConfig, gate: GateConfig | None = None, gate_v3: GateV3Config | None = None,
                 weights: RerankWeights | None = None):
        self.kb, self.cfg = kb, cfg
        self.gate = gate or GateConfig.load()
        self.gate_v3 = gate_v3 or GateV3Config.load()
        self.weights = weights or RerankWeights.load()
        if cfg.method != "bm25":
            for p in cfg.paths:
                kb.dense_index(cfg.model, p)
            self.embedder = Embedder(cfg.model)
        self._qcache: dict[str, np.ndarray] = {}

    # ---- ranked lists -----------------------------------------------------------------------------
    def _query_vec(self, query: str) -> np.ndarray:
        if query not in self._qcache:
            self._qcache[query] = self.embedder.encode_one(query)
        return self._qcache[query]

    def _candidates(self, query: str, query_vec: np.ndarray | None = None, query_intent: str | None = None, customer_author: str | None = None) -> list[dict]:
        cfg, kb = self.cfg, self.kb
        lists: dict[str, list[int]] = {}
        bm25_scores: dict[int, float] = {}
        if cfg.method in ("bm25", "hybrid"):
            hits = kb.bm25.search(query, cfg.candidate_k)
            lists["bm25"] = [d for d, _ in hits]
            bm25_scores = dict(hits)
        qv = None
        if cfg.method in ("dense", "hybrid"):
            qv = query_vec if query_vec is not None else self._query_vec(query)
            for p in cfg.paths:
                hits = kb.dense_index(cfg.model, p).search(qv, cfg.candidate_k)
                lists[p] = [d for d, _ in hits]
        if len(lists) > 1:
            fused = rrf(lists, k=cfg.rrf_k)
        else:
            name = next(iter(lists), "none")
            fused = [(d, 1.0 / (cfg.rrf_k + r), {name: r}) for r, d in enumerate(next(iter(lists.values()), []), start=1)]
        docs = [d for d, _, _ in fused]
        if not docs:
            return []
        if qv is None:
            qv = self._fallback_vec(query)
        # per-path cosines for EVERY candidate (a candidate found only on the reply path still gets its customer-side score)
        cos = {"customer": kb.dense_index(cfg.model if qv is not None and cfg.method != "bm25" else self._fallback_model, "customer").cosine(qv, docs)}
        for p in ("reply", "pair"):
            if p in cfg.paths:
                cos[p] = kb.dense_index(cfg.model, p).cosine(qv, docs)
        rows = kb.rows
        out = []
        for k, (d, score, ranks) in enumerate(fused):
            r = rows.iloc[d]
            srcs = [n for n in ranks if n in ("customer", "reply", "pair")]
            source = "dual" if len(srcs) > 1 else (srcs[0] if srcs else "customer")
            cc = float(min(1.0, max(-1.0, float(cos["customer"][k]))))
            out.append(dict(doc=d, rrf=float(score), ranks=ranks, bm25=float(bm25_scores.get(d, 0.0)), dense=cc, cos_customer=cc,
                            cos_reply=float(cos["reply"][k]) if "reply" in cos else 0.0, cos_pair=float(cos["pair"][k]) if "pair" in cos else 0.0,
                            source=source, outcome=str(r.outcome), substantive=bool(r.substantive), dm_handoff=bool(r.dm_handoff), reply=str(r.brand_reply),
                            weak_intent=str(r.weak_intent), action_class=str(r.action_class),
                            same_customer=bool(customer_author) and str(r.customer_author) == str(customer_author)))
        if cfg.rerank == "resolution":
            out = rerank(out, self.weights, query_intent)
            for c in out:
                c["final"], c["outcome_bonus"] = c["rerank"], 0.0
            return out
        out = apply_bonus(out, cfg.outcome_bonus)
        if cfg.substantive_first:
            # stable partition: substantive candidates keep their fused order and move ahead of non-substantive ones
            out = [c for c in out if c["substantive"]] + [c for c in out if not c["substantive"]]
        return out

    def _intent_boost(self, cands: list[dict], allowed: tuple[str, ...], strength: str) -> list[dict]:
        """Widen-not-discard: fuse the plain ranking with the ranking restricted to allowed intents (RRF). 'mild' gives the
        filtered list half weight by fusing it at rank+k offset; 'strong' fuses at equal weight. Candidates never drop out."""
        if strength == "none" or not allowed:
            return cands
        plain = [c["doc"] for c in cands]
        filtered = [c["doc"] for c in cands if c["weak_intent"] in allowed]
        if not filtered:
            return cands
        k = self.cfg.rrf_k if strength == "strong" else self.cfg.rrf_k * 3
        fused = rrf({"plain": plain, "intent": filtered}, k=k)
        by = {c["doc"]: c for c in cands}
        out = []
        for d, score, ranks in fused:
            c = dict(by[d])
            c["final"] = float(score)
            c["ranks"] = {**c.get("ranks", {}), **{f"boost_{n}": r for n, r in ranks.items()}}
            out.append(c)
        return out

    _fallback_model: str = ""

    def _fallback_vec(self, query: str) -> np.ndarray:
        """BM25-only mode still reports a semantic relevance signal for the gate, using MiniLM if available."""
        from resolveai.retrieval.dense import SUPPORTED

        m = SUPPORTED["minilm"]
        self.kb.dense_index(m, "customer")
        self._fallback_model = m
        return Embedder(m).encode_one(query)

    # ---- public API -------------------------------------------------------------------------------
    def retrieve(self, query: str, *, query_intent: str | None = None, customer_author: str | None = None,
                 query_created_at: pd.Timestamp | str | None = None, allowed_intents: tuple[str, ...] = (), boost: str = "none",
                 query_vec: np.ndarray | None = None) -> EvidenceSet:
        """query_vec: a precomputed L2-normalised embedding of `query` (shared with the classifier); computed here if absent."""
        t0 = time.perf_counter()
        qts = pd.to_datetime(query_created_at, utc=True) if query_created_at is not None else None
        cands = self._intent_boost(self._candidates(query, query_vec, query_intent, customer_author), allowed_intents, boost)
        rows, src = self.kb.rows, self.kb.source()
        items: list[EvidenceItem] = []
        for rank, c in enumerate(cands[: self.cfg.top_k], start=1):
            r = rows.iloc[c["doc"]]
            eligible = self.kb.temporally_eligible(c["doc"], qts)
            q = EvidenceQuality(
                semantic_relevance=c["dense"], lexical_relevance=c["bm25"],
                intent_match=(r.weak_intent == query_intent) if query_intent else None, candidate_intent=str(r.weak_intent),
                resolution_relevance=bool(r.substantive) and r.action_class not in NON_RESOLUTION_CLASSES and is_resolution_bearing(str(r.brand_reply)),
                action_class=str(r.action_class), temporal_eligible=eligible, same_customer=c["same_customer"],
                quality=("strong" if c["dense"] >= QUALITY_STRONG and r.substantive else "usable" if c["dense"] >= QUALITY_USABLE else "weak"),
            )
            items.append(EvidenceItem(
                evidence_id=str(int(r.brand_tweet_id)), thread_id=str(int(r.customer_tweet_id)), source_row_id=str(int(r.customer_tweet_id)),
                # Phase 9: historical text is redacted again on the way out. The shipped corpus was redacted with the pre-Phase-9 phone pattern,
                # which missed numbers at the end of a sentence; evidence reaches prompts, handoff packets and the console.
                customer_message=redact_pii(str(r.customer_message)).text, brand_reply=redact_pii(str(r.brand_reply)).text, created_at=str(r.created_at),
                outcome=str(r.outcome), dm_handoff=bool(r.dm_handoff), substantive=bool(r.substantive),
                retrieval_method=self.cfg.name, retrieval_source=c["source"], rank=rank, ranks=c["ranks"],
                scores={"bm25": c["bm25"], "dense": c["dense"], "cos_reply": c["cos_reply"], "cos_pair": c["cos_pair"], "rrf": c["rrf"],
                        "outcome_bonus": c.get("outcome_bonus", 0.0), "rerank": c.get("rerank", 0.0), "final": c["final"]},
                quality=q, source=src,
            ))
        items = [i for i in items if i.quality.temporal_eligible]
        # Phase 9 trust boundary: retrieved historical text is DATA. An item whose text reads as instructions to an AI system is
        # excluded before the gate, so poisoned knowledge-base content can neither count as support nor reach a drafting prompt.
        # Measured on the shipped corpus: 0 of 20,000 customer messages and 0 of 20,000 replies match, so current results are unchanged.
        from resolveai.trust.injection import detect_injection

        quarantined = [i.evidence_id for i in items if detect_injection(f"{i.customer_message}\n{i.brand_reply}").detected]
        if quarantined:
            items = [i for i in items if i.evidence_id not in set(quarantined)]
        if self.cfg.gate == "v3":
            g = decide_v3(items, self.gate_v3, query_intent, query)
            es = EvidenceSet(query=query, query_intent=query_intent, retriever=self.cfg.name, items=items, n_retrieved=len(cands), n_relevant=g["signals"].n_relevant,
                             sufficient=g["sufficient"], sufficiency_reason=g["reason"], sufficiency_level=g["level"], resolution_confidence=g["confidence"],
                             consistency=g["consistency"], resolution_candidates=g["candidates"], signals=g["signals"], gate_version=self.gate_v3.version)
        else:
            ok, reason, sig = decide(items, self.gate, query_intent, query)
            es = EvidenceSet(query=query, query_intent=query_intent, retriever=self.cfg.name, items=items, n_retrieved=len(cands), n_relevant=sig.n_relevant,
                             sufficient=ok, sufficiency_reason=reason, sufficiency_level=("SUFFICIENT" if ok else "INSUFFICIENT"), signals=sig, gate_version=self.gate.version)
        es.latency_ms = (time.perf_counter() - t0) * 1000
        es.quarantined_ids = quarantined
        return es
