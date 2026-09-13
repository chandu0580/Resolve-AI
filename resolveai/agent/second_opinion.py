"""GLM-5.2 intent second opinion with a FROZEN adoption policy (selected on development data by
scripts/phase4/a_second_opinion_policy.py and stored in second_opinion_policy.json). Consulted only at LOW/MEDIUM band.
The LLM never decides escalation; it can only change the intent label under the adoption rule."""
from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from resolveai.intelligence.context import ContextBundle
from resolveai.llm import LLMClient, LLMUnavailable
from resolveai.models.taxonomy import INTENT_NAMES, INTENTS
from resolveai.schemas.core import IntentResult

PROMPT_VERSION = "intent-second-opinion-v1"   # identical to Phase 3 so cached calls are reused
_POLICY_PATH = Path(__file__).with_name("second_opinion_policy.json")
POLICIES = ("top3", "low_any_medium_top3", "llm_conf_0.7", "agree_top2")
INTENT_LIST = "\n".join(f"- {k}: {v}" for k, v in INTENTS.items())


class Opinion(BaseModel):
    intent: str = Field(description="one of the intent names")
    confidence: float = Field(ge=0, le=1)


def load_policy() -> str:
    if _POLICY_PATH.exists():
        return json.loads(_POLICY_PATH.read_text(encoding="utf-8")).get("policy", "top3")
    return "top3"


def consult(client: LLMClient, bundle: ContextBundle) -> Opinion | None:
    ctx = f"\nEarlier customer message: {bundle.issue_text}" if bundle.issue_text else ""
    if bundle.prior_brand:
        ctx += f"\nLast brand reply: {bundle.prior_brand[0]}"
    msgs = [{"role": "system", "content": "You classify AppleSupport customer tweets into exactly one intent. Answer only with the JSON requested."},
            {"role": "user", "content": f"Intents:\n{INTENT_LIST}\n\nRules: label the customer's main requested resolution; the corrupted 'I' glyph or 'I.T' means keyboard_text_bug; "
                                        f"a crash confined to one app is apps_services, device-wide is performance_crash; accessories without physical fault are not hardware_damage; "
                                        f"no concrete symptom -> general_complaint; not a support request -> other.{ctx}\nCurrent customer message: {bundle.current}\n\n"
                                        f'Return JSON: {{"intent": <name>, "confidence": <0-1>}}'}]
    try:
        o = client.structured(msgs, Opinion, prompt_version=PROMPT_VERSION, max_tokens=400)
        return o if o.intent in INTENT_NAMES else None
    except LLMUnavailable:
        return None


def adopt(policy: str, base: IntentResult, opinion: Opinion | None) -> tuple[str, bool, bool]:
    """Returns (final_intent, applied, disagreement). Disagreement = the LLM named an intent outside the top-3."""
    if opinion is None or opinion.intent == base.intent:
        return base.intent, False, False
    top3 = [t[0] for t in base.top3]
    in_top3 = opinion.intent in top3
    if policy == "top3":
        return (opinion.intent, True, False) if in_top3 else (base.intent, False, True)
    if policy == "low_any_medium_top3":
        if base.confidence_band == "LOW":
            return opinion.intent, True, not in_top3
        return (opinion.intent, True, False) if in_top3 else (base.intent, False, True)
    if policy == "llm_conf_0.7":
        return (opinion.intent, True, not in_top3) if opinion.confidence >= 0.7 else (base.intent, False, not in_top3)
    if policy == "agree_top2":
        return (opinion.intent, True, False) if opinion.intent in top3[:2] else (base.intent, False, True)
    return base.intent, False, not in_top3


def apply(client: LLMClient | None, bundle: ContextBundle, base: IntentResult, policy: str | None = None) -> tuple[IntentResult, str]:
    """Consult at LOW/MEDIUM; returns (possibly updated IntentResult, status ok|skipped|fallback)."""
    if client is None or base.confidence_band == "HIGH" or base.insufficient_context:
        return base, "skipped"
    op = consult(client, bundle)
    if op is None:
        return base, "fallback"
    final, applied, disagree = adopt(policy or load_policy(), base, op)
    upd = {"second_opinion": op.intent, "second_opinion_applied": applied}
    if applied:
        upd["intent"] = final
        # keep the calibrated confidence honest: an adopted opinion is at most MEDIUM band unless the LLM agreed with the top-1
        upd["confidence_band"] = "MEDIUM" if base.confidence_band == "LOW" else base.confidence_band
    if disagree:
        upd["multi_intent"] = True
        upd["secondary_intents"] = list(dict.fromkeys([*base.secondary_intents, op.intent]))
    return base.model_copy(update=upd), "ok"
