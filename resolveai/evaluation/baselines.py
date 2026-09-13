"""The three comparison systems. Each one sees the same customer message and the same prior thread turns as ResolveAI
(the raw parsed context; ResolveAI itself truncates to its context-builder limits, so the baselines never see LESS).
None of them is crippled on purpose: the simple-ML baseline re-uses the same silver training data, the same BGE-small
index and the same deterministic risk rules ResolveAI uses; the direct-LLM baseline gets the full taxonomy definitions and
the annotation guide's escalation criteria in its prompt.

BASELINE 0 trivial       majority intent (from silver training labels), the brand's modal "DM us" reply, never escalates
                         (an always-handoff variant is reported alongside for the escalation numbers)
BASELINE 1 simple ML     TF-IDF + logistic regression intent (C chosen on silver DEV), nearest-neighbour historical reply
                         copied verbatim (BGE-small customer index, temporally eligible, not the same customer), escalation =
                         any deterministic risk rule fires OR the predicted intent is account/repair or hardware damage
BASELINE 2 direct LLM    one GLM-5.2 call: message + thread -> {intent, should_escalate, escalation_reason, reply}; no
                         retrieval, no evidence, no verifier, no policy. Failed/invalid calls are recorded as failed rows.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass

import pandas as pd
from pydantic import BaseModel, Field

from resolveai import config
from resolveai.agent import risk
from resolveai.agent.drafter import CANNED, HANDOFF_LINES
from resolveai.evaluation.records import EvidenceSnippet, SystemRecord
from resolveai.intelligence.classifier import MajorityClassifier, TfidfLR, _align  # noqa: F401
from resolveai.intelligence.context import build_context, parse_context
from resolveai.llm import LLMClient, LLMUnavailable
from resolveai.models.taxonomy import INTENT_NAMES, INTENTS
from resolveai.retrieval import KnowledgeBase, Retriever, RetrieverConfig
from resolveai.trust.pii import redact_pii

MODAL_REPLY = "We'd love to help. DM us the details and we'll go from there."   # the brand's modal behaviour (52% of replies are DM handoffs)
RULE_ESCALATE_FLAGS = ("safety_concern", "security_concern", "legal_or_media_threat", "abusive_threatening", "account_access_risk", "payment_billing_risk",
                       "needs_private_info", "physical_damage", "repeat_contact", "sensitive_action_required")
RULE_ESCALATE_INTENTS = {"account_store_repair", "hardware_damage"}
PRICE_PER_M = (1.0, 3.2)
DIRECT_PROMPT_VERSION = "direct-llm-baseline-v1"
ESCALATION_CRITERIA = ("Escalate (should_escalate=true) only when a public tweet cannot resolve it: safety (self-harm, injury, smoke, burns, shock), legal or press threats, "
                       "resolution needs private identifiers (serial, IMEI, Apple ID, order/case/repair number, payment, address), explicit physical damage or a repair/warranty decision, "
                       "the customer explicitly says they already tried the standard steps or contacted support before, or the message is abusive with no actionable symptom. "
                       "Otherwise should_escalate=false. Non-English messages are never escalated. Reasons: safety | legal_media | private_info | hardware | repeat_contact | vague_hostile | none.")


def _turns(context_raw: str) -> list[tuple[str, str]]:
    return [(t.role, t.text) for t in parse_context(context_raw).turns]


def _base(row, system: str, intent: str, action: str, response: str, kind: str, **kw) -> SystemRecord:
    return SystemRecord(gid=row.gid, system=system, message=row.customer_message, context=row.context or "", intent_pred=intent,
                        escalate_pred=(action == "HUMAN_HANDOFF"), action=action, response=response, response_kind=kind, **kw)


# ------------------------------------------------------------------ baseline 0 ---------------------------------------
@dataclass
class TrivialBaseline:
    majority_intent: str
    variant: str = "never_escalate"   # never_escalate | always_handoff

    @classmethod
    def fit(cls, train_labels: list[str], variant: str = "never_escalate") -> TrivialBaseline:
        return cls(MajorityClassifier().fit(None, train_labels).label, variant)

    @property
    def name(self) -> str:
        return "B0_trivial" if self.variant == "never_escalate" else "B0_trivial_always_handoff"

    def run(self, gold: pd.DataFrame) -> list[SystemRecord]:
        out = []
        for row in gold.itertuples():
            t = time.perf_counter()
            if self.variant == "never_escalate":
                rec = _base(row, self.name, self.majority_intent, "AUTO_HANDLE", MODAL_REPLY, "canned")
            else:
                rec = _base(row, self.name, self.majority_intent, "HUMAN_HANDOFF", HANDOFF_LINES["default"], "handoff")
            rec.latency_ms = (time.perf_counter() - t) * 1000
            out.append(rec)
        return out


# ------------------------------------------------------------------ baseline 1 ---------------------------------------
class SimpleMLBaseline:
    name = "B1_simple_ml"

    def __init__(self, kb: KnowledgeBase):
        self.kb = kb
        self.retriever = Retriever(kb, RetrieverConfig(paths=("customer",), rerank="none", gate="v2", substantive_first=True))
        self.clf: TfidfLR | None = None
        self.meta: dict = {}

    def fit(self, train: pd.DataFrame, dev: pd.DataFrame, bands: tuple[str, ...] = ("HIGH", "MEDIUM")) -> SimpleMLBaseline:
        """Same protocol as Phase 3: train on silver rows in the chosen bands, choose C on silver DEV by macro-F1."""
        from sklearn.metrics import f1_score

        tr = train[train.silver_band.isin(bands)]
        best = None
        for C in (0.5, 2.0, 8.0):
            m = TfidfLR(C=C).fit(tr.customer_message.tolist(), tr.silver_intent.tolist())
            P = m.predict_proba(dev.customer_message.tolist())
            pred = [INTENT_NAMES[i] for i in P.argmax(axis=1)]
            f = f1_score(dev.silver_intent.tolist(), pred, average="macro", labels=INTENT_NAMES, zero_division=0)
            if best is None or f > best[1]:
                best = (m, f, C)
        self.clf = best[0]
        self.meta = {"train_rows": int(len(tr)), "bands": list(bands), "C": best[2], "dev_macro_f1_silver": round(float(best[1]), 4), "dev_rows": int(len(dev))}
        return self

    def run(self, gold: pd.DataFrame, authors: dict[str, str]) -> list[SystemRecord]:
        out = []
        P = self.clf.predict_proba(gold.customer_message.tolist())
        for k, row in enumerate(gold.itertuples()):
            t = time.perf_counter()
            intent = INTENT_NAMES[int(P[k].argmax())]
            conf = float(P[k].max())
            red = redact_pii(row.customer_message).text
            b = build_context(red, parse_context(row.context))
            flags = risk.extract_rules(b)
            raised = [f for f in RULE_ESCALATE_FLAGS if getattr(flags, f)]
            ev = self.retriever.retrieve(red, query_intent=None, customer_author=authors.get(row.gid), query_created_at=row.created_at)
            snippets = [EvidenceSnippet(evidence_id=i.evidence_id, customer_message=i.customer_message, brand_reply=i.brand_reply) for i in ev.items]
            if raised or intent in RULE_ESCALATE_INTENTS:
                rec = _base(row, self.name, intent, "HUMAN_HANDOFF", HANDOFF_LINES["default"], "handoff", reason_code=(raised[0] if raised else f"intent:{intent}"))
            elif intent == "non_english":
                rec = _base(row, self.name, intent, "AUTO_HANDLE", CANNED["non_english"], "canned")
            else:
                top = next((i for i in ev.items if i.substantive), None)
                if top is None:
                    rec = _base(row, self.name, intent, "AUTO_HANDLE", MODAL_REPLY, "canned", reason_code="no_substantive_neighbour")
                else:
                    for s in snippets:
                        s.cited = s.evidence_id == top.evidence_id
                    rec = _base(row, self.name, intent, "AUTO_HANDLE", top.brand_reply, "copy", evidence_refs=[top.evidence_id])
            rec.intent_confidence = round(conf, 4)
            rec.evidence = snippets
            rec.risk_flags = raised
            rec.latency_ms = (time.perf_counter() - t) * 1000
            out.append(rec)
        return out


# ------------------------------------------------------------------ baseline 2 ---------------------------------------
class DirectSchema(BaseModel):
    intent: str
    should_escalate: bool = False
    escalation_reason: str = "none"
    reply: str = Field(default="", description="public reply <= 280 chars, or the handoff line if escalating")


class DirectLLMBaseline:
    name = "B2_direct_llm"

    def __init__(self, client: LLMClient):
        self.client = client

    @staticmethod
    def prompt(message: str, context_raw: str) -> list[dict[str, str]]:
        defs = "\n".join(f"- {k}: {v}" for k, v in INTENTS.items())
        thread = "\n".join(f"{r}: {t}" for r, t in _turns(context_raw))
        thread = f"Earlier thread (oldest first):\n{thread}\n\n" if thread else ""
        return [{"role": "system", "content": "You are the AppleSupport Twitter agent. Answer only with the JSON requested."},
                {"role": "user", "content": f"Intents (choose exactly one):\n{defs}\n\n{ESCALATION_CRITERIA}\n\n{thread}Current customer message: {message}\n\n"
                                            "Write the public reply you would send (<= 280 characters, warm and concise, no URLs, no @handles, no promises of refunds or replacements). "
                                            "If you escalate, the reply should tell the customer a team member will follow up directly.\n"
                                            'Return JSON: {"intent": str, "should_escalate": bool, "escalation_reason": str, "reply": str}'}]

    def run(self, gold: pd.DataFrame) -> list[SystemRecord]:
        out = []
        for row in gold.itertuples():
            t = time.perf_counter()
            u0 = self.client.usage.as_dict()
            red = redact_pii(row.customer_message).text
            ctx = "\n".join(f"{r}: {redact_pii(x).text}" for r, x in _turns(row.context or ""))
            try:
                o = self.client.structured(self.prompt(red, ctx), DirectSchema, prompt_version=DIRECT_PROMPT_VERSION, max_tokens=1000)
                intent = o.intent if o.intent in INTENT_NAMES else "general_complaint"
                action = "HUMAN_HANDOFF" if o.should_escalate else "AUTO_HANDLE"
                rec = _base(row, self.name, intent, action, (o.reply or "").strip()[:280], "handoff" if o.should_escalate else "llm_direct", reason_code=o.escalation_reason)
                rec.extra = {"intent_raw": o.intent, "intent_valid": o.intent in INTENT_NAMES}
            except LLMUnavailable as e:
                rec = _base(row, self.name, "general_complaint", "HUMAN_HANDOFF", HANDOFF_LINES["default"], "handoff", failed=True, error=str(e)[:200], reason_code="llm_failed")
            u1 = self.client.usage.as_dict()
            d = {k: u1[k] - u0[k] for k in u1}
            tin, tout = int(d["tokens_in"] + d.get("cached_tokens_in", 0)), int(d["tokens_out"] + d.get("cached_tokens_out", 0))
            rec.llm_calls, rec.live_calls, rec.tokens_in, rec.tokens_out = int(d["calls"]), int(d["live_calls"]), tin, tout
            rec.cost_usd = round((tin * PRICE_PER_M[0] + tout * PRICE_PER_M[1]) / 1e6, 6)
            rec.latency_ms = (time.perf_counter() - t) * 1000
            out.append(rec)
        return out


def load_silver() -> tuple[pd.DataFrame, pd.DataFrame]:
    train = pd.read_csv(config.PROCESSED_DIR / "silver_train.csv", keep_default_na=False)
    dev = pd.read_csv(config.PROCESSED_DIR / "silver_dev.csv", keep_default_na=False)
    return train, dev


def describe() -> dict:
    return {"B0_trivial": "majority silver intent; modal DM reply; never escalates (always-handoff variant for escalation reference)",
            "B1_simple_ml": "TF-IDF+LR (silver train, C on silver dev); nearest-neighbour historical reply (BGE-small customer index); rule escalation",
            "B2_direct_llm": f"GLM-5.2 single call ({DIRECT_PROMPT_VERSION}) with taxonomy definitions + guide escalation criteria + full thread; no retrieval/evidence/verifier",
            "information_parity": "all systems receive the PII-redacted current message and the prior thread turns; ResolveAI truncates context to 2 customer + 1 brand turns, baselines get all turns; only ResolveAI and B1 see historical evidence (the architectural difference under test)"}


def to_json(o) -> str:
    return json.dumps(o, indent=1, default=str)
