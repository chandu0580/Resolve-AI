"""Risk-flag extraction: deterministic rules always run; GLM-5.2 adds structured flags when available. Flags are
OR-merged (either source can raise a flag; neither can clear one). On LLM failure the rules alone are used and the
source is marked 'fallback'. The flags feed resolveai.policy; they are never the decision.

Phase 5 hardening (risk-flags-v2): the LLM returns a COMPACT object — the list of raised flag names, an `actionable`
bool and a one-line summary — instead of 14 booleans. Fewer output tokens leave more of GLM's completion budget for its
hidden reasoning, which was truncating the v1 JSON ~15% of the time. Parsing is strict: unknown flag names are dropped and
counted, the corrective retry is bounded (one, inside LLMClient.structured), and the deterministic fallback is unchanged.
"""
from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field

from resolveai.intelligence.context import ContextBundle
from resolveai.llm import LLMClient, LLMUnavailable
from resolveai.schemas.core import EvidenceSet, RiskFlags
from resolveai.trust.injection import detect_injection
from resolveai.trust.normalize import normalize_for_matching

RISK_PROMPT_VERSION = "risk-flags-v2"
RISK_PROMPT_VERSION_V1 = "risk-flags-v1"
_R = {
    "safety_concern": re.compile(r"\b(kill myself|suicid|self.?harm|hurt myself|burn(ed|t|ing)? (me|my)|smok(e|ing)|burning smell|caught fire|explod|shock(ed)? me|electrocut|sparks?|overheat(ing|ed)?|extremely hot|burning hot|(swollen|bulg(e|ing)) (battery|phone|device|casing|back)|battery (is )?(swollen|bulg(e|ing))|emergency|911)\b", re.I),
    "security_concern": re.compile(r"\b(hack(ed|er|ing)?|phish|malware|virus|unauthori[sz]ed|compromised|scam|stolen|someone (else )?(is )?(using|logged)|breach)\b", re.I),
    "privacy_concern": re.compile(r"\b(privacy|my (personal )?data|tracking me|leak(ed)?|expos(ed|ing) my)\b", re.I),
    "account_access_risk": re.compile(r"\b(locked out|activation lock|disabled (account|apple id)|can.?t (sign|log) ?in|two.?factor|2fa|verification code|recover (my )?account|reset (my )?password|forgot (my )?passcode|apple id)\b", re.I),
    "payment_billing_risk": re.compile(r"\b(charged|refund|billing|invoice|subscription|payment|purchase[sd]?|order(ed)?|deliver(y|ed)?|shipment|\$\s?\d|£\s?\d|€\s?\d)\b", re.I),
    "legal_or_media_threat": re.compile(r"\b(lawyer|lawsuit|sue|legal action|attorney|consumer (rights|protection)|trading standards|bbb|ftc|journalist|press|regulator)\b", re.I),
    "abusive_threatening": re.compile(r"\b(fuck you|f\*ck you|idiots?|morons?|useless (company|support)|i.?ll (find|come for) you|you (people )?(are )?(all )?(pathetic|garbage|trash))\b", re.I),
    "high_impact": re.compile(r"\b(stranded|urgent(ly)?|asap|deadline|finals?|exam|wedding|flight|business|work (phone|laptop|computer)|can.?t (call|reach) 911|medical)\b", re.I),
    # Phase 7 fix: `\b` cannot match before `<` or after `#`, so redaction tokens and "case #" never fired (found in the Phase 6 failure analysis, golden g157)
    "needs_private_info": re.compile(r"\b(serial|imei|case (number|id)|repair (id|number)|order number|tracking number)\b|\b(case|order) ?#|<(PHONE|EMAIL|ORDER_ID|LONG_ID|CARD)>", re.I),
    "physical_damage": re.compile(r"\b(cracked|shattered|liquid|water damage|dropped|dead (screen|pixel)|black screen|screen (has|with)? ?(lines|flicker)|swollen|bulg(e|ing))\b", re.I),
    "repeat_contact": re.compile(r"\b(already (tried|did|done|reset|restarted|updated|contacted)|tried (that|those|everything|all of)|restarted (it )?(\d+|several|many|multiple) times|(third|3rd|fourth|4th) time|still no (response|reply|answer)|nobody (has )?(replied|responded)|sent (you )?(a )?dm|dm i sent|the dm i|i (did|have done) (a |the )?(reset|restore|restart)|i (reset|restored|restarted|reinstalled|updated) (it|my|the|and)|logged out and (back )?in|reset (network|all) settings|went to (the )?(apple )?store|called (apple|support|you))\b", re.I),
    "sensitive_action_required": re.compile(r"\b(refund|replace(ment)?|cancel (my|the)|delete my|close my account|change my (email|number|address)|new (phone|device) (please|now)|send me a new)\b", re.I),
    # Final product pass: frustration is read from words only. Capitalization ("MY IPHONE IS BROKEN") and repeated "!" used to
    # raise this flag too, so the same message typed in capitals could be handed off as "frustrated, no concrete issue".
    "high_frustration": re.compile(r"\b(fuck|shit|wtf|damn|crap|sucks?|garbage|trash|ridiculous|unacceptable|pathetic|furious|angry|sick of|tired of|fed up)\b", re.I),
}
_ACTIONABLE_MIN_TOKENS = 3
FLAG_NAMES = tuple(_R)
_DEFS = ("safety_concern = injury, smoke, burns, self-harm, emergency. security_concern = hacked/phishing/compromise. privacy_concern = personal data exposure. "
         "account_access_risk = locked out, Apple ID, 2FA, password recovery. payment_billing_risk = charges, refunds, orders, delivery. legal_or_media_threat = lawyer, lawsuit, press, regulator. "
         "abusive_threatening = insults or threats aimed at people. high_impact = stranded/urgent/business-critical. needs_private_info = resolution needs serial/IMEI/order/case ids. "
         "physical_damage = explicit physical damage (cracked, shattered, liquid, swollen battery, dropped, broken hardware). repeat_contact = customer explicitly says they already tried standard steps or contacted support before. "
         "sensitive_action_required = refund/replacement/account change requested. high_frustration = strong anger or profanity.")


class RiskSchema(BaseModel):
    """v1 (Phase 4): one boolean per flag. Kept for the before/after measurement."""
    safety_concern: bool = False
    security_concern: bool = False
    privacy_concern: bool = False
    account_access_risk: bool = False
    payment_billing_risk: bool = False
    legal_or_media_threat: bool = False
    abusive_threatening: bool = False
    high_impact: bool = False
    needs_private_info: bool = False
    physical_damage: bool = False
    repeat_contact: bool = False
    sensitive_action_required: bool = False
    high_frustration: bool = False
    is_actionable: bool = True
    summary: str = ""


class RiskCompact(BaseModel):
    """v2 (Phase 5): only the raised flags. Extra keys are ignored (a v1-shaped answer degrades to 'no flags raised' rather
    than a fallback); unknown names are dropped by `normalise_flags`."""
    model_config = ConfigDict(extra="ignore")
    flags: list[str] = Field(default_factory=list)
    actionable: bool = True
    summary: str = ""


def normalise_flags(names: list) -> tuple[set[str], list[str]]:
    """Returns (known flags, unknown names). Tolerates case/space/dash variants; never invents a flag."""
    known, unknown = set(), []
    for n in names or []:
        key = re.sub(r"[\s\-]+", "_", str(n).strip().lower())
        if key in _R:
            known.add(key)
        elif key in ("is_actionable", "actionable", "not_actionable", ""):
            continue
        else:
            unknown.append(str(n)[:40])
    return known, unknown


def extract_rules(bundle: ContextBundle) -> RiskFlags:
    # comparison key: NFKC and format characters removed; every rule is case-insensitive (re.I)
    text = normalize_for_matching(" ".join([bundle.current] + bundle.prior_customer), fold_case=False)
    flags = {k: bool(p.search(text)) for k, p in _R.items()}
    flags["prompt_injection"] = detect_injection("\n".join([bundle.current, *bundle.prior_customer, *bundle.prior_brand])).detected
    from resolveai.intelligence.context import content_tokens

    flags["is_actionable"] = content_tokens(bundle.current) >= _ACTIONABLE_MIN_TOKENS or bool(bundle.issue_text)
    return RiskFlags(**flags, insufficient_context=bundle.insufficient_context, source="rules", summary="")


def _context_lines(bundle: ContextBundle) -> str:
    ctx = ""
    if bundle.issue_text:
        ctx += f"\nEarlier customer message: {bundle.issue_text}"
    if bundle.prior_brand:
        ctx += f"\nLast brand reply: {bundle.prior_brand[0]}"
    return ctx


def _prompt_v1(bundle: ContextBundle) -> list[dict[str, str]]:
    fields = ", ".join(RiskSchema.model_fields)
    return [
        {"role": "system", "content": "You extract operational risk flags from an AppleSupport customer tweet. Flags only; you do not decide anything. Answer only with JSON."},
        {"role": "user", "content": f"Set each flag to true only when the text clearly supports it. Flags: {fields}.\n{_DEFS} is_actionable = a concrete symptom or request is stated.{_context_lines(bundle)}\n"
                                    f"Current customer message: {bundle.current}\n\nReturn JSON with every flag as true/false and a one-sentence customer-safe summary (no identifiers)."},
    ]


def _prompt_v2(bundle: ContextBundle) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": "You extract operational risk flags from an AppleSupport customer tweet. Flags only; you do not decide anything. Answer only with compact JSON, no explanation."},
        {"role": "user", "content": f"Possible flags: {', '.join(FLAG_NAMES)}.\n{_DEFS}{_context_lines(bundle)}\nCurrent customer message: {bundle.current}\n\n"
                                    f'Return ONLY {{"flags": [names of the flags the text clearly supports, or []], "actionable": true if a concrete symptom or request is stated, "summary": one short customer-safe sentence without identifiers}}.'},
    ]


def _prompt_v3(bundle: ContextBundle) -> list[dict[str, str]]:
    """Phase 9 candidate (risk-flags-v3): the v2 prompt with the three flag definitions the annotation guide makes explicit
    (R1 repeat contact, R3 physical fault, private info) spelled out, because the Phase 7 live runs showed the model raising
    them on vague follow-ups and battery drains. Evaluated on DEV only (scripts/phase9/a_risk_dev_experiment.py)."""
    defs = _DEFS.replace(
        "needs_private_info = resolution needs serial/IMEI/order/case ids. ",
        "needs_private_info = ONLY when resolving it requires the customer's serial, IMEI, order, case, repair or account identifiers. ").replace(
        "physical_damage = explicit physical damage (cracked, shattered, liquid, swollen battery, dropped, broken hardware). ",
        "physical_damage = ONLY explicit physical damage or a physical fault (cracked/shattered/black screen, liquid, swollen battery, dropped device); "
        "battery drain, slow charging, heat without damage and software bugs are NOT physical damage. ").replace(
        "repeat_contact = customer explicitly says they already tried standard steps or contacted support before. ",
        "repeat_contact = ONLY when the customer explicitly names a step they already tried (restarted, reset, updated, restored), says they contacted "
        "support, sent a DM or went to a store; vague phrases such as 'still not working', 'still happening', 'nothing works', 'tried everything' "
        "and a problem that keeps recurring do NOT count. ")
    return [
        {"role": "system", "content": "You extract operational risk flags from an AppleSupport customer tweet. Flags only; you do not decide anything. Answer only with compact JSON, no explanation."},
        {"role": "user", "content": f"Possible flags: {', '.join(FLAG_NAMES)}.\n{defs}{_context_lines(bundle)}\nCurrent customer message: {bundle.current}\n\n"
                                    f'Return ONLY {{"flags": [names of the flags the text clearly supports, or []], "actionable": true if a concrete symptom or request is stated, "summary": one short customer-safe sentence without identifiers}}.'},
    ]


RISK_PROMPT_VERSION_V3 = "risk-flags-v3"
SOFT_FLAGS = frozenset({"repeat_contact", "physical_damage", "needs_private_info"})   # flags whose LLM-only raise is the measured over-escalation source


def llm_opinion(client: LLMClient, bundle: ContextBundle, *, schema: str = "compact", max_tokens: int = 900) -> tuple[set[str], bool, str, list[str]]:
    """The model's raw opinion: (raised flag names, actionable, summary, unknown names dropped). Raises LLMUnavailable."""
    if schema == "full":
        llm = client.structured(_prompt_v1(bundle), RiskSchema, prompt_version=RISK_PROMPT_VERSION_V1, max_tokens=max_tokens)
        return {k for k in FLAG_NAMES if getattr(llm, k)}, llm.is_actionable, llm.summary, []
    prompt, version = (_prompt_v3(bundle), RISK_PROMPT_VERSION_V3) if schema == "compact_v3" else (_prompt_v2(bundle), RISK_PROMPT_VERSION)
    out = client.structured(prompt, RiskCompact, prompt_version=version, max_tokens=max_tokens)
    raised, unknown = normalise_flags(out.flags)
    return raised, bool(out.actionable), out.summary, unknown


def merge(rules: RiskFlags, raised: set[str], actionable: bool, summary: str, bundle: ContextBundle, conflicting: bool, *, corroborate: frozenset[str] = frozenset()) -> RiskFlags:
    """OR-merge rules and model flags. A flag in `corroborate` is taken from the model only when the deterministic rule also fired
    (the model cannot add it alone); every other flag can still be raised by either source, and neither source can clear one."""
    merged = {k: bool(getattr(rules, k)) or (k in raised and (k not in corroborate or bool(getattr(rules, k)))) for k in FLAG_NAMES}
    merged["is_actionable"] = rules.is_actionable and actionable
    merged["prompt_injection"] = rules.prompt_injection   # deterministic only; the LLM never sees this flag
    return RiskFlags(**merged, insufficient_context=bundle.insufficient_context, conflicting_evidence=conflicting, summary=(summary or "")[:200], source="llm+rules")


def extract(client: LLMClient | None, bundle: ContextBundle, evidence: EvidenceSet | None, *, schema: str = "compact", max_tokens: int = 900,
            corroborate: frozenset[str] = frozenset()) -> tuple[RiskFlags, str]:
    """Returns (flags, status) where status is ok | fallback | rules_only. `schema`: compact (v2, default) | compact_v3 | full (v1)."""
    rules = extract_rules(bundle)
    conflicting = bool(evidence is not None and evidence.sufficiency_reason == "conflicting_evidence")
    if client is None:
        return rules.model_copy(update={"conflicting_evidence": conflicting, "source": "rules"}), "rules_only"
    try:
        raised, actionable, summary, unknown = llm_opinion(client, bundle, schema=schema, max_tokens=max_tokens)
    except LLMUnavailable:
        return rules.model_copy(update={"conflicting_evidence": conflicting, "source": "fallback"}), "fallback"
    flags = merge(rules, raised, actionable, summary, bundle, conflicting, corroborate=corroborate)
    return flags, ("ok" if not unknown else "ok_unknown_flags_dropped")
