/**
 * Typed access to real API responses captured by scripts/phase8/capture_fixtures.py and (release, agent profile, knowledge
 * summary) scripts/verification/capture_console_fixtures.py. Nothing here is hand-written.
 */
import type { AgentProfile, AgentTrace, DemoScenario, EvaluationSummary, KnowledgeSummary, ReleaseEvaluation, ResolveResponse, TraceListResponse } from "@/lib/api/types";
import agentProfile from "./fixtures/agent_profile.json";
import demoScenarios from "./fixtures/demo_scenarios.json";
import evaluationRelease from "./fixtures/evaluation_release.json";
import knowledgeSummary from "./fixtures/knowledge_summary.json";
import errorInputTooLarge from "./fixtures/error_input_too_large.json";
import errorTraceNotFound from "./fixtures/error_trace_not_found.json";
import evaluationSummary from "./fixtures/evaluation_summary.json";
import resolveA from "./fixtures/resolve_A_grounded_auto_handle.json";
import resolveB from "./fixtures/resolve_B_clarification_no_concrete_issue.json";
import resolveC from "./fixtures/resolve_C_account_security_escalation.json";
import resolveD from "./fixtures/resolve_D_insufficient_evidence.json";
import resolveE from "./fixtures/resolve_E_prompt_injection.json";
import resolveF from "./fixtures/resolve_F_llm_unavailable.json";
import resolveG from "./fixtures/resolve_G_known_limitation_over_escalation_by_the_risk_model.json";
import resolveVerify from "./fixtures/resolve_verification_failed.scripted_verifier.json";
import traceA from "./fixtures/trace_A_auto_handle.json";
import traceD from "./fixtures/trace_D_clarification.json";
import tracesList from "./fixtures/traces_list.json";

const as = <T,>(v: unknown) => v as T;

export const fx = {
  autoHandle: as<ResolveResponse>(resolveA),
  clarificationVague: as<ResolveResponse>(resolveB),
  securityHandoff: as<ResolveResponse>(resolveC),
  clarificationInsufficientEvidence: as<ResolveResponse>(resolveD),
  injectionHandoff: as<ResolveResponse>(resolveE),
  llmUnavailable: as<ResolveResponse>(resolveF),
  repeatContactHandoff: as<ResolveResponse>(resolveG),
  verificationFailed: as<ResolveResponse>(resolveVerify),
  traceAuto: as<AgentTrace>(traceA),
  traceClarification: as<AgentTrace>(traceD),
  traces: as<TraceListResponse>(tracesList),
  evaluation: as<EvaluationSummary>(evaluationSummary),
  scenarios: as<DemoScenario[]>(demoScenarios),
  release: as<ReleaseEvaluation>(evaluationRelease),
  agentProfile: as<AgentProfile>(agentProfile),
  knowledge: as<KnowledgeSummary>(knowledgeSummary),
  errorTraceNotFound,
  errorInputTooLarge,
};

export const allResolveFixtures: [string, ResolveResponse][] = [
  ["A auto handle", fx.autoHandle],
  ["B clarification", fx.clarificationVague],
  ["C security handoff", fx.securityHandoff],
  ["D insufficient evidence", fx.clarificationInsufficientEvidence],
  ["E prompt injection", fx.injectionHandoff],
  ["F model unavailable", fx.llmUnavailable],
  ["G repeat contact", fx.repeatContactHandoff],
  ["verification failed", fx.verificationFailed],
];

export function jsonResponse(body: unknown, status = 200, headers: Record<string, string> = {}): Response {
  return new Response(typeof body === "string" ? body : JSON.stringify(body), { status, headers: { "content-type": "application/json", ...headers } });
}
