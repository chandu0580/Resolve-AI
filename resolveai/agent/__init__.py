"""ResolveAI agent core: understand -> ground -> assess -> decide -> verify -> act or handoff -> observe.
Entry point: ResolveAI(...).resolve(message, context) -> AgentResult."""
from resolveai.agent.orchestrator import AgentConfig, ResolveAI

__all__ = ["AgentConfig", "ResolveAI"]
