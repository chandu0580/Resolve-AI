/** The UI's type assumptions, checked against real responses captured from the running API. */
import { describe, expect, it } from "vitest";
import { isResolveResponse } from "@/lib/api/validate";
import { STAGE_ORDER } from "@/lib/labels";
import { allResolveFixtures, fx } from "./fixtures";

describe("captured API responses match what the UI renders", () => {
  it.each(allResolveFixtures)("%s is a complete ResolveResponse", (_name, r) => {
    expect(isResolveResponse(r)).toBe(true);
    // Fields that are optional in the generated schema but always serialized by FastAPI.
    expect(Array.isArray(r.response.evidence_refs)).toBe(true);
    expect(Array.isArray(r.evidence.items)).toBe(true);
    expect(Array.isArray(r.evidence.resolution_candidates)).toBe(true);
    expect(Array.isArray(r.conversation.context.turns)).toBe(true);
    expect(typeof r.outcome.output_gate).toBe("object");
    expect(Array.isArray(r.outcome.blocking_checks)).toBe(true);
    expect(r.outcome.action).toBe(r.action);
    if (r.handoff) {
      expect(Array.isArray(r.handoff.alternatives)).toBe(true);
      expect(Array.isArray(r.handoff.unresolved_questions)).toBe(true);
      expect(Array.isArray(r.handoff.historical_examples)).toBe(true);
    }
    if (r.clarification) {
      expect(Array.isArray(r.clarification.missing_information)).toBe(true);
      expect(Array.isArray(r.clarification.already_provided)).toBe(true);
    }
    if (r.verification) expect(Array.isArray(r.verification.issues)).toBe(true);
  });

  it("covers every decision path the UI distinguishes", () => {
    expect(fx.autoHandle.action).toBe("AUTO_HANDLE");
    expect(fx.autoHandle.response.kind).toBe("auto_reply");
    expect(fx.clarificationVague.action).toBe("CLARIFICATION_REQUIRED");
    expect(fx.securityHandoff.outcome.reason_code).toBe("safety");
    expect(fx.injectionHandoff.outcome.reason_code).toBe("prompt_injection");
    expect(fx.llmUnavailable.outcome.reason_code).toBe("llm_unavailable");
    expect(fx.verificationFailed.verification?.verified).toBe(false);
    expect(fx.verificationFailed.handoff?.draft_if_any).toBeTruthy();
  });

  it("rejects bodies that are not a ResolveResponse", () => {
    expect(isResolveResponse(null)).toBe(false);
    expect(isResolveResponse("<html></html>")).toBe(false);
    expect(isResolveResponse({ ...fx.autoHandle, action: "SEND_EMAIL" })).toBe(false);
    const withoutOutcome: Partial<typeof fx.autoHandle> = { ...fx.autoHandle };
    delete withoutOutcome.outcome;
    expect(isResolveResponse(withoutOutcome)).toBe(false);
  });

  it("trace summaries carry the enriched decision fields", () => {
    for (const t of fx.traces.items) {
      expect(t).toHaveProperty("intent");
      expect(t).toHaveProperty("evidence_level");
      expect(Array.isArray(t.risk_flags)).toBe(true);
      expect(t).toHaveProperty("policy_version");
    }
  });

  it("every recorded trace event maps to a timeline stage", () => {
    const known = new Set(STAGE_ORDER.flatMap((s) => s.events));
    for (const e of [...fx.traceAuto.events, ...fx.traceClarification.events]) expect(known.has(e.name)).toBe(true);
  });

  it("traces never contain the customer text", () => {
    const text = JSON.stringify(fx.traceAuto);
    expect(text).not.toContain(fx.autoHandle.conversation.message.text);
  });

  it("demo scenarios and the evaluation summary have the fields the UI reads", () => {
    for (const s of fx.scenarios) {
      expect(s.id).toMatch(/^[A-Z]$/);
      expect(["live", "any", "unavailable"]).toContain(s.llm);
      expect(s.conversation.at(-1)?.role).toBe("customer");
    }
    const e = fx.evaluation;
    expect(e.headline.n).toBe(197);
    expect(e.headline.intent_macro_f1).toHaveProperty("ci_low");
    expect(e.systems.resolveai_full.autonomy).toHaveProperty("unsafe_auto_handle_count");
    expect(typeof e.misleading_headline_md).toBe("string");
    expect(e.provenance?.golden_rows).toBe(197);
  });
});
