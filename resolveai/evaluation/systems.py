"""Runs ResolveAI (full and ablated) on the golden set and converts AgentResult into SystemRecord.

Ablations answer architectural questions; each is one switch on the production agent, nothing is re-tuned:
  full                      the Phase 5 system (RetrieverConfig defaults, policy-v3, risk-v2, draft-v2, verify-v2)
  minus_second_opinion      classifier only, no GLM intent second opinion
  minus_resolution_rerank   Phase 2 retrieval (customer index, substantive-first, gate-v2) instead of pair+rerank+gate-v3
  minus_risk_llm            deterministic risk rules only (no GLM flags)
  minus_retrieval           no evidence at all: the agent can only clarify, hand off or send a template
The verifier is never disabled on the production path; its effect is evaluated offline (ablations.py).
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import pandas as pd

from resolveai.agent import AgentConfig, ResolveAI
from resolveai.evaluation.records import EvidenceSnippet, SystemRecord
from resolveai.intelligence.context import parse_context
from resolveai.retrieval import GateConfig, KnowledgeBase, Retriever, RetrieverConfig
from resolveai.schemas.evidence import EvidenceSet


class NullRetriever:
    """Returns no evidence; keeps the Retriever surface the orchestrator uses."""

    def __init__(self):
        self.cfg = RetrieverConfig()
        self.gate_v3 = None

    def retrieve(self, query: str, **kw) -> EvidenceSet:
        return EvidenceSet(query=query, retriever="none", items=[], n_retrieved=0, n_relevant=0, sufficient=False, sufficiency_reason="no_relevant_evidence",
                           sufficiency_level="INSUFFICIENT", gate_version="none")


@dataclass(frozen=True)
class Ablation:
    name: str
    description: str
    cfg: AgentConfig
    retriever: str = "default"   # default | phase2 | none


ABLATIONS: dict[str, Ablation] = {
    "resolveai_full": Ablation("resolveai_full", "Phase 5 system", AgentConfig(write_traces=False)),
    "minus_second_opinion": Ablation("minus_second_opinion", "no GLM intent second opinion", AgentConfig(write_traces=False, use_second_opinion=False)),
    "minus_resolution_rerank": Ablation("minus_resolution_rerank", "Phase 2 retrieval: customer index, no rerank, gate-v2", AgentConfig(write_traces=False), retriever="phase2"),
    "minus_risk_llm": Ablation("minus_risk_llm", "risk flags from rules only", AgentConfig(write_traces=False, use_risk_llm=False)),
    "minus_retrieval": Ablation("minus_retrieval", "no evidence available", AgentConfig(write_traces=False), retriever="none"),
}


def build_agent(ab: Ablation, kb: KnowledgeBase, llm=None, intents=None) -> ResolveAI:
    if ab.retriever == "phase2":
        retriever = Retriever(kb, RetrieverConfig(paths=("customer",), rerank="none", gate="v2", substantive_first=True), gate=GateConfig.load())
    elif ab.retriever == "none":
        retriever = NullRetriever()
    else:
        retriever = None
    return ResolveAI(kb=kb, retriever=retriever, intents=intents, llm=llm, cfg=ab.cfg)


def to_record(gid: str, row, r, system: str) -> SystemRecord:
    kind = "none"
    if r.action in ("AUTO_HANDLE", "CHANNEL_REDIRECT"):
        kind = "canned" if (r.draft and r.draft.strategy.value == "canned") else "troubleshoot"
    elif r.action == "CLARIFICATION_REQUIRED":
        kind = "clarify"
    else:
        kind = "handoff"
    refs = set(r.evidence_refs)
    ev = [EvidenceSnippet(evidence_id=i.evidence_id, customer_message=i.customer_message, brand_reply=i.brand_reply, cited=i.evidence_id in refs) for i in r.evidence.items]
    failed = r.stage_status.get("execution") == "failed"
    return SystemRecord(gid=gid, system=system, message=row.customer_message, context=row.context or "", intent_pred=r.intent.intent, intent_confidence=round(r.intent.confidence, 4),
                        intent_band=r.intent.confidence_band, escalate_pred=(r.action == "HUMAN_HANDOFF"), action=r.action, response=r.response, response_kind=kind, evidence=ev,
                        evidence_sufficient=r.evidence.sufficient, evidence_level=r.evidence.sufficiency_level, resolution_confidence=r.evidence.resolution_confidence,
                        verified=(r.verification.verified if r.verification else None), evidence_refs=list(r.evidence_refs),
                        risk_flags=[k for k, v in r.risk.model_dump().items() if v is True and k != "is_actionable"], reason_code=r.decision.escalation.reason_code,
                        latency_ms=r.latency_ms, llm_calls=r.usage.llm_calls, live_calls=r.usage.live_calls, tokens_in=r.usage.tokens_in, tokens_out=r.usage.tokens_out,
                        cost_usd=r.usage.estimated_cost_usd, failed=failed, error=r.stage_status.get("execution", "") if failed else "",
                        extra={"second_opinion_applied": r.intent.second_opinion_applied, "stage_status": r.stage_status, "trace_id": r.trace_id, "consistency": r.evidence.consistency,
                               "resolution_clusters": [(c.action_class, c.support_count, round(c.share, 3)) for c in r.evidence.resolution_candidates], "draft_attempts": (r.draft.attempts if r.draft else 0)})


def run_agent(agent: ResolveAI, gold: pd.DataFrame, authors: dict[str, str], system: str, progress=None) -> list[SystemRecord]:
    out = []
    for k, row in enumerate(gold.itertuples()):
        t = time.perf_counter()
        res = agent.resolve(row.customer_message, parse_context(row.context), customer_author=authors.get(row.gid), created_at=row.created_at, message_id=f"{system}_{row.gid}")
        rec = to_record(row.gid, row, res, system)
        rec.latency_ms = round((time.perf_counter() - t) * 1000, 1)
        out.append(rec)
        if progress and (k + 1) % 20 == 0:
            progress(k + 1)
    return out
