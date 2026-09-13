"""ResolveAI agent core: the explicit execution graph.

    INPUT -> PII REDACTION -> CONTEXT -> INTENT (+ second opinion) -> RETRIEVAL -> EVIDENCE GATE -> RISK FLAGS
          -> ESCALATION POLICY -> DRAFT -> VERIFICATION -> OUTPUT GATE -> AUTO_HANDLE | CLARIFICATION_REQUIRED | HUMAN_HANDOFF
          -> TRACE

Every stage writes a typed result into AgentState and a trace event. Failures are explicit (`stage_status`), never
silent: a failed critical stage routes to HUMAN_HANDOFF through the same output gate. The LLM is used for risk flags,
drafting and verification only; it never decides escalation and never drafts without sufficient evidence.

Phase 9 failure hierarchy (every failure is classified in `trace.failures` with codes only, never free text):
  expected input problem      -> clarification (the policy's clarify rules, unchanged)
  model failure / timeout     -> the stage's deterministic fallback (rules for risk, classifier for intent); if the model was needed
                                 to answer (draft / verify) -> HUMAN_HANDOFF `model_timeout` or `llm_unavailable`, never a reply
  dependency failure          -> HUMAN_HANDOFF `dependency_failure` naming the stage (retrieval, embedding, classifier, ...)
  policy / safety failure     -> HUMAN_HANDOFF (policy rules, unchanged)
  audit trail not writable    -> an automatic reply is withheld: HUMAN_HANDOFF `audit_unavailable`
A request runs under an optional wall-clock budget: no model call starts once it is spent.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import asdict, dataclass, is_dataclass

from resolveai.agent import clarify, drafter, explain, gate, handoff, risk, second_opinion
from resolveai.agent.state import AgentState
from resolveai.agent.verifier import VERIFY_PROMPT_VERSION, verify
from resolveai.intelligence.classifier import ARTIFACT, IntentService
from resolveai.intelligence.context import build_context
from resolveai.intelligence.conversation_acts import is_greeting_only
from resolveai.intelligence.query import build_query
from resolveai.knowledge.procedural import PROCEDURAL_VERSION, PROCEDURES, create_procedural_evidence
from resolveai.llm import Deadline, DiskCache, LLMClient, LLMUnavailable, OpenAICompatibleProvider
from resolveai.observability import TraceRecorder, TraceStore
from resolveai.policy import escalation as policy
from resolveai.retrieval import GateConfig, KnowledgeBase, Retriever, RetrieverConfig
from resolveai.retrieval.dense import Embedder
from resolveai.schemas.core import (
    AgentResult,
    AutomationDecision,
    ConversationContext,
    CustomerMessage,
    DraftResponse,
    EscalationResult,
    IntentResult,
    ResponseStrategy,
    RiskFlags,
    RuntimeVersions,
    UsageSummary,
)
from resolveai.schemas.evidence import EvidenceSet
from resolveai.trust.injection import detect_injection
from resolveai.trust.pii import contains_unredacted_pii, redact_pii, redacted_error

# v6.3 (release-readiness pass): the English-only redirect no longer fires on a LOW-confidence guess, and a bare "ok" gets a
# closing line instead of "you're welcome"; policy-v3.3.
# v6.2 (final product pass, after the release evaluation of v6.1): a bare greeting skips retrieval and model calls; a short reply is
# classified together with the issue it answers; capitalization and punctuation are never risk signals.
# v6.1 (Phase 10): model-only needs_private_info needs the rule. v6.0 (Phase 9): request budget, classified failures, audit guard, quarantine.
PIPELINE_VERSION = "pipeline-v6.3"
PRICE_PER_M = (1.0, 3.2)  # USD per 1M tokens (in, out), GLM-5.2 list price; the proxy's real billing is unknown
TIMEOUT_KINDS = ("timeout", "budget_exhausted")
RISK_PROMPTS = {"compact": risk.RISK_PROMPT_VERSION, "compact_v3": risk.RISK_PROMPT_VERSION_V3, "full": risk.RISK_PROMPT_VERSION_V1}


@dataclass(frozen=True)
class AgentConfig:
    use_llm: bool = True                 # False = deterministic-only run (no risk LLM, no drafting, no verifier, no second opinion)
    use_second_opinion: bool = True
    use_llm_verifier: bool = True
    max_draft_attempts: int = 2
    share_query_embedding: bool = True
    write_traces: bool = True
    risk_short_circuit: bool = True      # Phase 5: skip the risk LLM when the rules-only policy already guarantees a human handoff
    use_risk_llm: bool = True            # False = deterministic risk rules only (evaluation ablation; the rules are the safety floor either way)
    risk_schema: str = "compact"         # compact (v2, default) | compact_v3 | full (v1)
    # flags the model may only raise together with the deterministic rule. Release value decided on DEV by the pre-registered Phase 10
    # experiment (artifacts/final/risk_experiment/decision.json): a model-only needs_private_info was the largest unnecessary-handoff source.
    risk_corroborate: tuple[str, ...] = ("needs_private_info",)
    draft_version: str = "v2"            # v2 (resolution-aware) | v1 (Phase 4)


class ResolveAI:
    def __init__(self, kb: KnowledgeBase | None = None, retriever: Retriever | None = None, intents: IntentService | None = None,
                 llm: LLMClient | None = None, cfg: AgentConfig | None = None, trace_store: TraceStore | None = None):
        cfg = cfg or AgentConfig()
        self.cfg = cfg
        self.kb = kb or KnowledgeBase.build(dense_models=[RetrieverConfig().model], with_bm25=False)
        self.retriever = retriever or Retriever(self.kb, RetrieverConfig(), gate=GateConfig.load())   # RetrieverConfig() = the Phase-5 selected configuration
        self.intents = intents or IntentService()
        self.embedder = Embedder(self.retriever.cfg.model)
        self.llm = None if not cfg.use_llm else (llm if llm is not None else self._default_llm())
        self.traces = trace_store or (TraceStore() if cfg.write_traces else None)
        self.policy = second_opinion.load_policy()
        self.versions = self._runtime_versions()

    @staticmethod
    def _default_llm() -> LLMClient | None:
        try:
            return LLMClient(provider=OpenAICompatibleProvider(), cache=DiskCache())
        except LLMUnavailable:
            return None

    def _runtime_versions(self) -> RuntimeVersions:
        """Component versions + a hash of the effective configuration (agent config, frozen gate/rerank files, classifier artifact,
        prompt versions, model). Recorded on every trace so any decision can be tied to exactly this configuration."""
        r = self.retriever
        rcfg = getattr(r, "cfg", None)
        gate_cfg = getattr(r, "gate_v3", None) if getattr(rcfg, "gate", "") == "v3" else getattr(r, "gate", None)
        weights = getattr(r, "weights", None)
        prompts = {"risk": RISK_PROMPTS.get(self.cfg.risk_schema, self.cfg.risk_schema),
                   "draft": (drafter.DRAFT_PROMPT_VERSION if self.cfg.draft_version == "v2" else drafter.DRAFT_PROMPT_VERSION_V1), "verify": VERIFY_PROMPT_VERSION,
                   "second_opinion": second_opinion.PROMPT_VERSION}
        classifier = hashlib.sha256(ARTIFACT.read_bytes()).hexdigest()[:12] if ARTIFACT.exists() else "missing"
        body = {"pipeline": PIPELINE_VERSION, "policy": policy.POLICY_VERSION, "output_gate": gate.GATE_VERSION, "retrieval": getattr(rcfg, "name", "none"),
                "evidence_gate": getattr(gate_cfg, "version", "none"), "rerank": getattr(weights, "version", "none"), "classifier": classifier, "prompts": prompts,
                "model": self.llm.model if self.llm else None, "agent_config": asdict(self.cfg), "second_opinion_policy": str(self.policy),
                "gate_config": asdict(gate_cfg) if is_dataclass(gate_cfg) else {}, "rerank_weights": asdict(weights) if is_dataclass(weights) else {}}
        return RuntimeVersions(pipeline=PIPELINE_VERSION, policy=policy.POLICY_VERSION, output_gate=gate.GATE_VERSION, retrieval=body["retrieval"], evidence_gate=body["evidence_gate"],
                               rerank=body["rerank"], classifier=classifier, prompts=prompts, model=body["model"],
                               config_hash=hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()[:16])

    # ------------------------------------------------------------------------------------------------------------
    def resolve(self, message: str, context: ConversationContext | None = None, *, customer_author: str | None = None,
                created_at: str | None = None, message_id: str | None = None, request_id: str | None = None, request_meta: dict[str, str] | None = None,
                budget_s: float | None = None) -> AgentResult:
        t_all = time.perf_counter()
        trace_id = uuid.uuid4().hex
        request_id = request_id or trace_id
        # message_id hashes the REDACTED text, so not even a hash of raw identifiers reaches the trace
        rec = TraceRecorder(message_id=message_id or hashlib.sha256(redact_pii(message or "").text.encode()).hexdigest()[:12], trace_id=trace_id, prompt_versions=dict(self.versions.prompts))
        rec.trace.request_id = request_id
        rec.trace.pipeline_version = PIPELINE_VERSION
        rec.trace.config_hash = self.versions.config_hash
        rec.trace.versions = {k: str(v) for k, v in self.versions.model_dump(exclude={"prompts"}).items() if v is not None}
        rec.trace.request_meta = {k: str(v)[:64] for k, v in (request_meta or {}).items() if v is not None and not contains_unredacted_pii(str(v))}
        rec.trace.budget_s = budget_s
        usage0 = self.llm.usage.as_dict() if self.llm else {}
        if self.llm:
            self.llm.deadline = Deadline(budget_s) if budget_s else None
            self.llm.last_failure = None
        rec.event("request_received", "api", has_context=bool(context and context.turns), policy_version=policy.POLICY_VERSION, gate_version=gate.GATE_VERSION, budget_s=budget_s)

        try:
            return self._run(message, context, rec, trace_id, request_id, customer_author, created_at, usage0, t_all)
        finally:
            if self.llm:
                self.llm.deadline = None

    def _run(self, message, context, rec: TraceRecorder, trace_id: str, request_id: str, customer_author, created_at, usage0: dict, t_all: float) -> AgentResult:
        # ---- 1. PII redaction (message + context) --------------------------------------------------------------------
        t = time.perf_counter()
        red = redact_pii(message or "")
        ctx = ConversationContext(turns=[t_.model_copy(update={"text": redact_pii(t_.text).text}) for t_ in (context.turns if context else [])], truncated=bool(context and context.truncated))
        st = AgentState(trace_id=trace_id, message=CustomerMessage(message_id=rec.trace.message_id, text=red.text, pii_counts=red.counts), context=ctx,
                        customer_author=customer_author, created_at=created_at, llm_available=self.llm is not None)
        st.mark("pii_redaction", "ok", (time.perf_counter() - t) * 1000)
        rec.event("pii_redacted", "trust", latency_ms=st.latency_ms["pii_redaction"], pii_counts=red.counts)
        st.request_id = request_id
        st.injection = detect_injection("\n".join([red.text] + [t_.text for t_ in ctx.turns]))   # every turn: caller-supplied brand turns are untrusted too
        rec.event("injection_checked", "trust", detected=st.injection.detected, patterns=st.injection.patterns)

        try:
            self._understand(st, rec)
            self._assess(st, rec)
            self._decide(st, rec)
            self._respond(st, rec)
        except Exception as e:  # noqa: BLE001 — any unexpected failure is explicit, classified and routes to handoff
            stage = st.current_stage or "unknown"
            st.mark("execution", "failed", error=redacted_error(e))
            st.mark(stage, "failed")
            st.failures.append({"category": "dependency_failure", "stage": stage, "kind": type(e).__name__})
            rec.event("dependency_failed", stage, status="failed", stage=stage, error=redacted_error(e))
            st.escalation = EscalationResult(decision="escalate", reason_code="dependency_failure", rule=f"dependency:{stage}", policy_version=policy.POLICY_VERSION,
                                             reason=f"The {stage.replace('_', ' ')} stage failed, so no automatic answer is possible; a human takes over.")
            st.strategy = ResponseStrategy.handoff.value
            st.draft = None
            st.verification = None

        # ---- 11. output gate (final authority) ------------------------------------------------------------------------
        st.current_stage = "output_gate"
        t = time.perf_counter()
        st.decision = gate.output_gate(st)
        st.mark("output_gate", "ok", (time.perf_counter() - t) * 1000)
        rec.event("output_allowed" if st.decision.action == "AUTO_HANDLE" else "decision_made", "output_gate", action=st.decision.action, blocking=st.decision.blocking, gates=st.decision.gates)

        # ---- 12. final response + handoff --------------------------------------------------------------------------
        self._finalize_response(st, rec, trace_id)
        rec.event("response_returned", "api", action=st.decision.action, response_chars=len(st.response), evidence_refs=st.evidence_refs)

        usage = self._usage_delta(usage0)
        total_ms = (time.perf_counter() - t_all) * 1000
        st.latency_ms["total"] = round(total_ms, 2)
        if self.llm:
            rec.usage(self.llm.model, calls=usage.llm_calls, tokens_in=usage.tokens_in, tokens_out=usage.tokens_out, cache_hits=usage.cache_hits, estimated_cost_usd=usage.estimated_cost_usd,
                      retries=usage.retries, timeouts=usage.timeouts, errors=usage.model_errors, fallbacks=usage.fallbacks, budget_exhausted=usage.budget_exhausted)
        rec.trace.stage_status = dict(st.stage_status)
        rec.trace.latency_ms = dict(st.latency_ms)
        rec.trace.failures = list(st.failures)
        trace = rec.finish(final_decision=st.decision.action, error=st.errors.get("execution"))
        self._persist(st, rec, trace, trace_id)
        return self._result(st, usage, total_ms)

    def _finalize_response(self, st: AgentState, rec: TraceRecorder, trace_id: str) -> None:
        if st.decision.action in ("AUTO_HANDLE", "CHANNEL_REDIRECT"):
            st.response = st.draft.text
            st.evidence_refs = list(st.draft.evidence_ids)
            st.citations = explain.citations(st)
        elif st.decision.action == "CLARIFICATION_REQUIRED":
            st.response = clarify.clarifying_question(st.intent, st.bundle, st.escalation)
            st.evidence_refs = []
            st.clarification = clarify.build_clarification(st, trace_id)
            rec.event("clarification_created", "clarify", reason_code=st.clarification.reason_code, missing=st.clarification.missing_information,
                      already_provided=st.clarification.already_provided)
        else:
            st.response = drafter.handoff_line(st.escalation, context=st.context) if st.escalation else drafter.HANDOFF_LINES["default"]
            st.evidence_refs = [i.evidence_id for i in (st.evidence.items if st.evidence else [])[:3]]
            st.citations = []
            t = time.perf_counter()
            st.handoff = handoff.build_handoff(st, trace_id)
            st.mark("handoff", "ok", (time.perf_counter() - t) * 1000)
            rec.event("handoff_created", "handoff", reason_code=st.escalation.reason_code if st.escalation else "output_gate", n_examples=len(st.handoff.historical_examples))

    def _persist(self, st: AgentState, rec: TraceRecorder, trace, trace_id: str) -> None:
        """Every automatic reply must be auditable: if the trace cannot be written, the reply is withheld and a human takes over."""
        if self.traces is None:
            return
        try:
            self.traces.write(trace)
            st.mark("trace", "ok")
        except Exception as e:  # noqa: BLE001 — the store is a dependency like any other
            st.mark("trace", "failed", error=redacted_error(e))
            st.failures.append({"category": "dependency_failure", "stage": "trace_store", "kind": type(e).__name__})
            if st.decision.action == "AUTO_HANDLE":
                esc = EscalationResult(decision="escalate", reason_code="audit_unavailable", rule="audit_trail", policy_version=policy.POLICY_VERSION,
                                       reason="The audit trace could not be written, so the automatic reply was withheld; a human takes over.")
                st.escalation, st.strategy = esc, ResponseStrategy.handoff.value
                st.decision = AutomationDecision(decision="escalate", escalation=esc, gates={**st.decision.gates, "audit_trace_written": False}, autonomous_response_allowed=False,
                                                 action="HUMAN_HANDOFF", gate_version=gate.GATE_VERSION, blocking=[*st.decision.blocking, "audit_trace_written"])
                self._finalize_response(st, rec, trace_id)

    # ------------------------------------------------------------------ stages -----------------------------------------
    def _note_model_failure(self, st: AgentState, rec: TraceRecorder, stage: str) -> str | None:
        """Classify and trace a model failure that the stage already handled with its fallback. Returns the failure kind."""
        kind = self.llm.last_failure if self.llm else None
        if kind:
            st.failures.append({"category": "model_failure", "stage": stage, "kind": kind})
            rec.event("model_call_failed", stage, status="fallback", stage=stage, kind=kind, model=self.llm.model)
            self.llm.last_failure = None
        return kind

    def _understand(self, st: AgentState, rec: TraceRecorder) -> None:
        st.current_stage = "context"
        t = time.perf_counter()
        st.bundle = build_context(st.message.text, st.context)
        st.mark("context", "ok", (time.perf_counter() - t) * 1000)
        rec.event("context_built", "context", latency_ms=st.latency_ms["context"], short_reply=st.bundle.is_short_reply, insufficient_context=st.bundle.insufficient_context,
                  prior_customer_turns=len(st.bundle.prior_customer), prior_brand_turns=len(st.bundle.prior_brand), truncated=st.bundle.truncated)

        greeting = is_greeting_only(st.bundle.current)
        st.current_stage = "embedding"
        t = time.perf_counter()
        # The classifier reads the current message (decided on golden, DECISIONS #25), except a short reply that answers an earlier
        # issue ("still happening", "iphone 15"): on its own it carries no intent, so it is classified together with that issue.
        use_context = st.bundle.is_short_reply and bool(st.bundle.issue_text)
        class_text = st.bundle.text_for_classification if use_context else st.bundle.current
        X = None
        if self.cfg.share_query_embedding:
            X = self.embedder.encode_one(class_text)[None, :]
        st.current_stage = "intent"
        st.intent = self.intents.classify(st.bundle, use_context=use_context, X=X)
        st.mark("intent", "ok", (time.perf_counter() - t) * 1000)
        rec.event("intent_predicted", "intent", latency_ms=st.latency_ms["intent"], intent=st.intent.intent, confidence=st.intent.confidence, band=st.intent.confidence_band,
                  top3=st.intent.top3, multi_intent=st.intent.multi_intent, taxonomy_gap=st.intent.taxonomy_gap)

        is_procedural = bool(st.intent and st.intent.method == "procedural" and st.intent.procedural_id in PROCEDURES)
        st.current_stage = "second_opinion"
        t = time.perf_counter()
        if self.cfg.use_second_opinion and self.llm is not None and not greeting and not is_procedural and not (st.injection and st.injection.detected):   # an injection attempt is never sent to an LLM
            before = st.intent.intent
            st.intent, status = second_opinion.apply(self.llm, st.bundle, st.intent, self.policy)
            st.mark("second_opinion", "ok" if status == "ok" else status, (time.perf_counter() - t) * 1000)
            if status == "fallback":
                self._note_model_failure(st, rec, "second_opinion")
            if status != "skipped":
                rec.event("second_opinion_used", "intent", status=status, latency_ms=st.latency_ms["second_opinion"], policy=self.policy, before=before, after=st.intent.intent,
                          llm_intent=st.intent.second_opinion, applied=st.intent.second_opinion_applied, model=self.llm.model)
        else:
            st.mark("second_opinion", "skipped", 0)

        st.current_stage = "retrieval"
        if greeting and not (st.injection and st.injection.detected):
            # nothing to ground: a greeting is answered by a fixed template, so the knowledge base is not searched
            st.evidence = EvidenceSet(sufficient=False, sufficiency_reason="not_applicable", sufficiency_level="INSUFFICIENT")
            st.mark("retrieval", "skipped", 0)
            st.mark("evidence_gate", "skipped", 0)
            rec.event("retrieval_skipped", "retrieval", status="skipped", reason="greeting")
            return

        if is_procedural and not (st.injection and st.injection.detected):
            proc = PROCEDURES[st.intent.procedural_id]
            st.evidence = create_procedural_evidence(proc, st.bundle.current)
            st.mark("retrieval", "ok", 0.5)
            st.mark("evidence_gate", "ok", 0)
            rec.event("retrieval_completed", "retrieval", latency_ms=0.5, n_retrieved=1, evidence_ids=[proc.source_reference],
                      top_similarity=1.0, retriever="trusted_procedural")
            rec.event("evidence_evaluated", "evidence_gate", sufficient=st.evidence.sufficient, reason=st.evidence.sufficiency_reason,
                      gate_version=st.evidence.gate_version, level=st.evidence.sufficiency_level, resolution_confidence=1.0, consistency="consistent",
                      resolution_clusters=[{"action": proc.action_class, "support": 3, "share": 1.0, "ids": [proc.source_reference]}],
                      support_count=3, conflicting=False)
            return
        t = time.perf_counter()
        st.plan = build_query(st.bundle, st.intent)
        rec.event("retrieval_started", "retrieval", query_chars=len(st.plan.text), boost=st.plan.boost, allowed_intents=list(st.plan.allowed_intents))
        qv = None
        if self.cfg.share_query_embedding and st.plan.text == class_text:
            qv = X[0] if X is not None else None
        elif self.cfg.share_query_embedding:
            qv = self.embedder.encode_one(st.plan.text)
        st.evidence = self.retriever.retrieve(st.plan.text, query_intent=(None if st.intent.insufficient_context else st.intent.intent), customer_author=st.customer_author,
                                              query_created_at=st.created_at, allowed_intents=st.plan.allowed_intents, boost=st.plan.boost, query_vec=qv)
        st.mark("retrieval", "ok", (time.perf_counter() - t) * 1000)
        rec.event("retrieval_completed", "retrieval", latency_ms=st.latency_ms["retrieval"], n_retrieved=st.evidence.n_retrieved, evidence_ids=[i.evidence_id for i in st.evidence.items],
                  top_similarity=(st.evidence.signals.top_similarity if st.evidence.signals else None), retriever=st.evidence.retriever)
        quarantined = list(getattr(st.evidence, "quarantined_ids", []) or [])
        if quarantined:
            rec.event("evidence_quarantined", "retrieval", status="flagged", evidence_ids=quarantined, count=len(quarantined))
        st.mark("evidence_gate", "ok", 0)
        rec.event("evidence_evaluated", "evidence_gate", sufficient=st.evidence.sufficient, reason=st.evidence.sufficiency_reason, gate_version=st.evidence.gate_version,
                  level=st.evidence.sufficiency_level, resolution_confidence=st.evidence.resolution_confidence, consistency=st.evidence.consistency,
                  resolution_clusters=[{"action": c.action_class, "support": c.support_count, "share": c.share, "ids": c.evidence_ids} for c in st.evidence.resolution_candidates],
                  support_count=(st.evidence.signals.support_count if st.evidence.signals else 0), conflicting=(st.evidence.signals.conflicting if st.evidence.signals else False))

    def _assess(self, st: AgentState, rec: TraceRecorder) -> None:
        st.current_stage = "risk"
        t = time.perf_counter()
        # Skip the LLM when deterministic rules already raise a hard block: the policy outcome cannot change and the call
        # would only cost ~5-10 s. The rules-only flags are marked as such in the trace.
        rules_flags = risk.extract_rules(st.bundle)
        if st.injection and st.injection.detected and not rules_flags.prompt_injection:
            rules_flags = rules_flags.model_copy(update={"prompt_injection": True})   # detected in a turn outside the bounded context window
        rules_only, skip_reason = rules_flags.any_hard_block(), "rules_hard_block"
        if not rules_only and is_greeting_only(st.bundle.current):
            rules_only, skip_reason = True, "greeting"   # a bare greeting carries no risk a model could add; the rules still run
        if not rules_only and self.cfg.risk_short_circuit and st.intent is not None:
            # Phase 5: the LLM can only add flags, so when the rules-only policy already yields a non-clarifiable
            # escalation the handoff is guaranteed and the call is skipped (measured in artifacts/resolution/latency_report.md).
            rules_only, skip_reason = policy.hard_handoff_guaranteed(st.intent, rules_flags, st.context, st.evidence, st.bundle.current), "policy_hard_handoff"
        st.risk, status = risk.extract(None if (rules_only or not self.cfg.use_risk_llm) else self.llm, st.bundle, st.evidence, schema=self.cfg.risk_schema,
                                       corroborate=frozenset(self.cfg.risk_corroborate))
        if rules_flags.prompt_injection and not st.risk.prompt_injection:
            st.risk = st.risk.model_copy(update={"prompt_injection": True})
        if rules_only:
            status = skip_reason
        elif not self.cfg.use_risk_llm:
            status = "rules_only_config"
        # Phase 9: a deliberately skipped model call is `skipped`; only a failed model call is `fallback` (the two were conflated before)
        stage_status = "ok" if status.startswith("ok") else ("fallback" if status == "fallback" else "skipped")
        st.mark("risk", stage_status, (time.perf_counter() - t) * 1000)
        if status == "fallback":
            self._note_model_failure(st, rec, "risk")
        raised = [k for k, v in st.risk.model_dump().items() if v is True and k != "is_actionable"]
        rec.event("risk_flags_extracted", "risk", status=status, latency_ms=st.latency_ms["risk"], source=st.risk.source, flags=raised, model=(self.llm.model if (self.llm and not rules_only) else None),
                  schema=self.cfg.risk_schema)

    def _decide(self, st: AgentState, rec: TraceRecorder) -> None:
        st.current_stage = "policy"
        t = time.perf_counter()
        st.escalation = policy.decide(st.intent, st.risk, st.context, st.evidence, None, llm_available=self.llm is not None, message=st.bundle.current)
        st.strategy = drafter.choose_strategy(st.intent, st.evidence, st.escalation)
        st.mark("policy", "ok", (time.perf_counter() - t) * 1000)
        rec.event("escalation_decided", "policy", decision=st.escalation.decision, reason_code=st.escalation.reason_code, rule=st.escalation.rule,
                  policy_version=st.escalation.policy_version, clarification_allowed=st.escalation.clarification_allowed, strategy=st.strategy)

    def _model_escalation(self, st: AgentState, kind: str | None) -> None:
        timeout = kind in TIMEOUT_KINDS
        st.escalation = st.escalation.model_copy(update={
            "decision": "escalate", "reason_code": "model_timeout" if timeout else "llm_unavailable", "rule": "llm_fallback",
            "reason": ("The model did not answer within the request's time budget; escalating rather than replying without a verified draft." if timeout
                       else "The drafting model was unavailable; escalating rather than replying without a draft.")})

    def _respond(self, st: AgentState, rec: TraceRecorder) -> None:
        """Drafting happens ONLY when the policy allowed automation; the evidence invariant is enforced here and re-checked
        by the output gate. Verification failure -> one corrective redraft -> escalate. A verifier that could not run (model
        failure or timeout) is not a verification failure: it escalates at once without spending the budget on a redraft."""
        st.current_stage = "draft"
        if st.strategy == ResponseStrategy.canned.value:
            t = time.perf_counter()
            st.draft = DraftResponse(text=drafter.canned_text(st.intent, st.escalation), strategy=ResponseStrategy.canned, evidence_ids=[], model="template", prompt_version="canned-v3")
            st.verification = verify(None, st.draft, st.evidence, st.intent, use_llm=False)
            st.mark("draft", "ok", (time.perf_counter() - t) * 1000)
            st.mark("verification", "ok", 0)
            rec.event("draft_generated", "drafter", strategy="canned", model="template")
            rec.event("response_verified", "verifier", verified=st.verification.verified, severity=st.verification.severity, method=st.verification.method)
            return

        proc = PROCEDURES.get(st.intent.procedural_id or "") if (st.intent and st.intent.method == "procedural") else None
        if proc and st.strategy == ResponseStrategy.troubleshoot.value:
            t = time.perf_counter()
            st.draft = DraftResponse(text=proc.response_template, strategy=ResponseStrategy.troubleshoot, evidence_ids=[proc.source_reference], model="trusted_procedural", prompt_version=PROCEDURAL_VERSION)
            st.verification = verify(None, st.draft, st.evidence, st.intent, use_llm=False)
            st.mark("draft", "ok", (time.perf_counter() - t) * 1000)
            st.mark("verification", "ok", 0)
            rec.event("draft_generated", "drafter", strategy="troubleshoot", model="trusted_procedural", procedure=proc.id)
            rec.event("response_verified", "verifier", verified=st.verification.verified, severity=st.verification.severity, method=st.verification.method)
            return

        if st.strategy != ResponseStrategy.troubleshoot.value:
            st.mark("draft", "skipped", 0)
            st.mark("verification", "skipped", 0)
            return
        if not st.evidence.sufficient:  # evidence invariant, defence in depth (policy already refused)
            st.mark("draft", "skipped", 0, error="evidence insufficient; drafting refused")
            st.mark("verification", "skipped", 0)
            st.escalation = st.escalation.model_copy(update={"decision": "escalate", "reason_code": "insufficient_evidence", "rule": "evidence_invariant", "reason": "Drafting refused: evidence insufficient."})
            return
        if self.llm is None:
            st.mark("draft", "fallback", 0, error="LLM unavailable")
            st.mark("verification", "skipped", 0)
            st.escalation = st.escalation.model_copy(update={"decision": "escalate", "reason_code": "llm_unavailable", "rule": "llm_fallback", "reason": "The drafting model was unavailable; escalating rather than replying without a draft."})
            st.failures.append({"category": "model_failure", "stage": "draft", "kind": "not_configured"})
            rec.event("fallback", "drafter", status="fallback", reason="llm_unavailable")
            return
        corrective = None
        for attempt in range(1, self.cfg.max_draft_attempts + 1):
            st.current_stage = "draft"
            t = time.perf_counter()
            try:
                st.draft = drafter.draft_troubleshoot(self.llm, st.bundle, st.intent, st.evidence, corrective=corrective, version=self.cfg.draft_version)
            except LLMUnavailable as e:
                st.mark("draft", "fallback", (time.perf_counter() - t) * 1000, error=redacted_error(e))
                st.mark("verification", "skipped", 0)
                st.draft = None
                kind = e.kind if e.kind != "transport" or not self.llm.last_failure else self.llm.last_failure
                self.llm.last_failure = kind
                self._note_model_failure(st, rec, "draft")
                self._model_escalation(st, kind)
                rec.event("fallback", "drafter", status="fallback", reason=kind, attempt=attempt)
                return
            st.mark("draft", "ok", (time.perf_counter() - t) * 1000)
            rec.event("draft_generated", "drafter", latency_ms=st.latency_ms["draft"], attempt=attempt, model=self.llm.model, evidence_refs=st.draft.evidence_ids, chars=len(st.draft.text),
                      prompt_version=st.draft.prompt_version, ask_only=drafter.is_ask_only(st.draft.text))
            st.current_stage = "verification"
            t = time.perf_counter()
            self.llm.last_failure = None
            st.verification = verify(self.llm, st.draft, st.evidence, st.intent, use_llm=self.cfg.use_llm_verifier)
            st.mark("verification", "ok", (time.perf_counter() - t) * 1000)
            rec.event("response_verified", "verifier", latency_ms=st.latency_ms["verification"], verified=st.verification.verified, severity=st.verification.severity,
                      method=st.verification.method, issues=[i.check for i in st.verification.issues], coverage=st.verification.coverage, attempt=attempt)
            if st.verification.verified:
                return
            kind = self._note_model_failure(st, rec, "verification")
            if kind:
                st.mark("verification", "fallback")
                self._model_escalation(st, kind)
                return
            corrective = "; ".join(f"{i.check}: {i.detail}" for i in st.verification.issues if i.severity == "blocking")[:400]
        st.escalation = st.escalation.model_copy(update={"decision": "escalate", "reason_code": "verification_failed", "rule": "verifier",
                                                         "reason": "The generated reply could not be verified against the evidence after a corrective retry; escalating."})

    # ------------------------------------------------------------------ helpers ----------------------------------------
    def _usage_delta(self, before: dict) -> UsageSummary:
        if not self.llm:
            return UsageSummary()
        now = self.llm.usage.as_dict()
        d = {k: now[k] - before.get(k, 0) for k in now}
        # tokens/cost = what this message would cost live: live tokens + the tokens the cached completions consumed when they were live
        tin, tout = int(d["tokens_in"] + d.get("cached_tokens_in", 0)), int(d["tokens_out"] + d.get("cached_tokens_out", 0))
        cost = (tin * PRICE_PER_M[0] + tout * PRICE_PER_M[1]) / 1e6
        return UsageSummary(llm_calls=int(d["calls"]), live_calls=int(d["live_calls"]), cache_hits=int(d["cache_hits"]), tokens_in=tin, tokens_out=tout,
                            estimated_cost_usd=round(cost, 6), fallbacks=int(d["fallbacks"]), retries=int(d.get("retries", 0)), timeouts=int(d.get("timeouts", 0)),
                            model_errors=int(d.get("errors", 0)), budget_exhausted=int(d.get("budget_exhausted", 0)))

    def _result(self, st: AgentState, usage: UsageSummary, total_ms: float) -> AgentResult:
        return AgentResult(trace_id=st.trace_id, request_id=st.request_id, clarification=st.clarification, citations=list(st.citations), summary=explain.build_summary(st),
                           versions=self.versions, action=st.decision.action, response=st.response, message=st.message, context=st.context,
                           intent=st.intent or IntentResult(intent="general_complaint", confidence=0.0, confidence_band="LOW", insufficient_context=True),
                           risk=st.risk or RiskFlags(source="fallback"), evidence=st.evidence or __import__("resolveai.schemas.evidence", fromlist=["EvidenceSet"]).EvidenceSet(),
                           evidence_refs=st.evidence_refs, draft=st.draft, verification=st.verification, decision=st.decision, handoff=st.handoff, answer=st.response,
                           policy_version=policy.POLICY_VERSION, stage_status=dict(st.stage_status), latency=dict(st.latency_ms), usage=usage, llm_calls=usage.llm_calls, latency_ms=round(total_ms, 2))
