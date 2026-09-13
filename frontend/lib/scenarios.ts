/** Presentation of the API's demo scenarios. The scenarios and their expectations come from GET /api/v1/demo/scenarios. */
import type { DemoScenario, ResolveResponse } from "@/lib/api/types";
import { ACTION_META, reasonMeta } from "@/lib/labels";

export const LLM_REQUIREMENT: Record<DemoScenario["llm"], string> = {
  live: "Needs the live model",
  any: "Runs with or without the model",
  unavailable: "Needs a simulated model outage",
};

export function expectationText(s: DemoScenario): string {
  const parts: string[] = [];
  if (s.expect.action) parts.push(ACTION_META[s.expect.action].label);
  if (s.expect.not_action) parts.push(`not ${ACTION_META[s.expect.not_action].label.toLowerCase()}`);
  if (s.expect.reason_code_in?.length) parts.push(`reason: ${s.expect.reason_code_in.map((r) => reasonMeta(r).label.toLowerCase()).join(" or ")}`);
  if (s.expect.max_llm_calls !== undefined) parts.push(`at most ${s.expect.max_llm_calls} model calls`);
  return parts.join(" · ") || "No declared expectation";
}

export interface ExpectationCheck {
  label: string;
  ok: boolean;
}

/** Compares the actual API result with the scenario's declared expectation (display only; the API decided). */
export function checkExpectation(s: DemoScenario, r: ResolveResponse): ExpectationCheck[] {
  const checks: ExpectationCheck[] = [];
  if (s.expect.action) checks.push({ label: `Decision is ${ACTION_META[s.expect.action].label.toLowerCase()}`, ok: r.action === s.expect.action });
  if (s.expect.not_action) checks.push({ label: `Decision is not ${ACTION_META[s.expect.not_action].label.toLowerCase()}`, ok: r.action !== s.expect.not_action });
  if (s.expect.reason_code_in?.length) checks.push({ label: `Reason is ${s.expect.reason_code_in.join(" or ")}`, ok: s.expect.reason_code_in.includes(r.outcome.reason_code) });
  if (s.expect.max_llm_calls !== undefined) checks.push({ label: `At most ${s.expect.max_llm_calls} model calls`, ok: r.usage.llm_calls <= s.expect.max_llm_calls });
  if (s.expect.has_handoff) checks.push({ label: "Handoff packet present", ok: r.handoff !== null && r.handoff !== undefined });
  if (s.expect.has_clarification) checks.push({ label: "Clarification packet present", ok: r.clarification !== null && r.clarification !== undefined });
  return checks;
}
