"""Release configuration (Phase 10): the model may raise `needs_private_info` only together with the deterministic private-info rule.

Decided on DEV by the pre-registered experiment in artifacts/final/risk_experiment/ (AI-labelled rows, not human). Every other model flag
still counts on its own, and no model output can clear a flag the rules raised.
"""
from resolveai.agent import AgentConfig, risk
from resolveai.intelligence.context import build_context
from resolveai.schemas.core import ConversationContext

CORROBORATE = frozenset(AgentConfig().risk_corroborate)


def _merge(text: str, raised: set[str]):
    b = build_context(text, ConversationContext())
    rules = risk.extract_rules(b)
    return rules, risk.merge(rules, raised, True, "", b, False, corroborate=CORROBORATE)


def test_release_config_corroborates_only_private_info():
    assert AgentConfig().risk_corroborate == ("needs_private_info",)


def test_a_model_only_private_info_flag_no_longer_forces_a_handoff():
    rules, merged = _merge("my iPhone 6s crashes every few minutes since the update", {"needs_private_info"})
    assert not rules.needs_private_info and not merged.needs_private_info


def test_a_rule_backed_private_info_flag_is_kept():
    rules, merged = _merge("my repair case # is still pending and the phone restarts", {"needs_private_info"})
    assert rules.needs_private_info and merged.needs_private_info
    rules, merged = _merge("stranded without cellular, case <PHONE> transferred my number", set())
    assert merged.needs_private_info, "a redaction token alone still routes to private handling"


def test_other_model_flags_still_count_without_corroboration():
    _, merged = _merge("my screen went black after the update", {"repeat_contact", "physical_damage", "security_concern"})
    assert merged.repeat_contact and merged.physical_damage and merged.security_concern


def test_the_model_cannot_clear_a_rule_flag():
    rules, merged = _merge("I was charged twice for iCloud storage and want a refund", set())
    assert rules.payment_billing_risk and merged.payment_billing_risk
