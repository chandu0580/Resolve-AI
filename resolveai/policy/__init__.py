"""Deterministic policy: escalation rules. Owns the automation decision; the LLM never decides here."""
from resolveai.policy.escalation import CONFIDENCE_FLOOR, decide

__all__ = ["CONFIDENCE_FLOOR", "decide"]
