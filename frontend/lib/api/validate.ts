/** Minimal structural check of a /resolve response before the UI renders it (catches proxies, HTML error pages, version skew). */
import type { ResolveResponse } from "@/lib/api/types";

const ACTIONS = new Set(["AUTO_HANDLE", "CLARIFICATION_REQUIRED", "HUMAN_HANDOFF"]);

export function isResolveResponse(value: unknown): value is ResolveResponse {
  if (!value || typeof value !== "object") return false;
  const v = value as Record<string, unknown>;
  const outcome = v.outcome as Record<string, unknown> | undefined;
  const response = v.response as Record<string, unknown> | undefined;
  const evidence = v.evidence as Record<string, unknown> | undefined;
  const conversation = v.conversation as Record<string, unknown> | undefined;
  return (
    typeof v.trace_id === "string" &&
    typeof v.request_id === "string" &&
    ACTIONS.has(v.action as string) &&
    !!outcome &&
    outcome.action === v.action &&
    !!response &&
    typeof response.text === "string" &&
    !!evidence &&
    Array.isArray(evidence.items) &&
    !!conversation &&
    typeof conversation.message === "object" &&
    typeof v.intent === "object" &&
    typeof v.risk === "object" &&
    typeof v.versions === "object"
  );
}
