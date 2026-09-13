"""ResolveAI HTTP service (FastAPI). A thin operational layer around the existing agent: it validates and limits input,
correlates requests with traces, enforces the autonomy invariant a second time, and presents the agent's typed result.
It contains no agent logic. App factory: resolveai.api.app:create_app (uvicorn: resolveai.api.app:app_factory --factory).
Deliberately light: importing this package does not load the agent."""

API_VERSION = "v1"
from resolveai import __version__ as SERVICE_VERSION  # noqa: E402

__all__ = ["API_VERSION", "SERVICE_VERSION"]
