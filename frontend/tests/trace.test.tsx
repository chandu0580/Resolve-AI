import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { TraceDecisionView, summarizeTraceDecision } from "@/components/trace/trace-decision";
import { TraceTimeline } from "@/components/trace/trace-timeline";
import { groupTraceEvents } from "@/lib/trace";
import { fx } from "./fixtures";

const STAGES = ["Request", "PII check", "Context", "Intent", "Retrieval", "Evidence gate", "Risk", "Policy", "Draft", "Verification", "Final action", "Trace complete"];

describe("trace timeline", () => {
  it("groups recorded events into the pipeline stages in order", () => {
    const t = fx.traceAuto;
    const groups = groupTraceEvents(t.events, t.stage_status, t.latency_ms);
    expect(groups.map((g) => g.label)).toEqual(STAGES);
    expect(groups.every((g) => g.status === "ok")).toBe(true);
    const intent = groups.find((g) => g.key === "intent")!;
    expect(intent.durationMs).toBeCloseTo(t.latency_ms.intent + t.latency_ms.second_opinion);
    expect(intent.startedAt).toBe(t.events.find((e) => e.name === "intent_predicted")!.ts);
  });

  it("marks skipped and fallback stages from the recorded stage status", () => {
    const skipped = groupTraceEvents(fx.traceClarification.events, fx.traceClarification.stage_status, fx.traceClarification.latency_ms);
    expect(skipped.find((g) => g.key === "draft")!.status).toBe("skipped");
    const fallback = groupTraceEvents([], fx.securityHandoff.stage_status, fx.securityHandoff.latency_ms);
    expect(fallback.find((g) => g.key === "risk")!.status).toBe("fallback");
  });

  it("shows status, duration and time per stage and reveals safe metadata on click", () => {
    const t = fx.traceAuto;
    render(<TraceTimeline events={t.events} stageStatus={t.stage_status} latency={t.latency_ms} />);
    const list = screen.getByRole("list", { name: "Pipeline stages" });
    expect(within(list).getAllByRole("listitem")).toHaveLength(12);
    const policy = screen.getByRole("button", { name: /^Policy/ });
    expect(policy).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(policy);
    expect(policy).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("Policy decided")).toBeInTheDocument();
    expect(screen.getByText("default_auto")).toBeInTheDocument();
    expect(screen.getByText("policy-v3.1")).toBeInTheDocument();
  });

  it("expands every stage at once", () => {
    const t = fx.traceAuto;
    render(<TraceTimeline events={t.events} stageStatus={t.stage_status} latency={t.latency_ms} />);
    fireEvent.click(screen.getByRole("button", { name: "Expand all" }));
    expect(screen.getByText("PII redacted")).toBeInTheDocument();
    expect(screen.getByText("Result returned")).toBeInTheDocument();
  });

  it("reconstructs the decision from a trace alone and says text is not stored", () => {
    const s = summarizeTraceDecision(fx.traceClarification);
    expect(s.action).toBe("CLARIFICATION_REQUIRED");
    expect(s.reasonCode).toBe("insufficient_evidence");
    render(<TraceDecisionView trace={fx.traceClarification} />);
    expect(screen.getByText("Reconstructed from the audit trace")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Decision: Clarification" })).toBeInTheDocument();
    expect(screen.getByText("Battery & power")).toBeInTheDocument();
  });

  it("places Phase 9 failure events on the stage that emitted them, with a failure status", () => {
    const t = fx.traceAuto;
    const failed = {
      name: "model_call_failed" as const,
      ts: t.events[0].ts,
      component: "draft",
      status: "fallback",
      latency_ms: 0,
      data: { stage: "draft", kind: "timeout" },
    };
    const groups = groupTraceEvents([...t.events, failed] as typeof t.events, { ...t.stage_status, draft: "fallback" }, t.latency_ms);
    const draft = groups.find((g) => g.key === "draft")!;
    expect(draft.events.map((e) => e.name)).toContain("model_call_failed");
    expect(draft.status).toBe("fallback");
    expect(groups.find((g) => g.key === "other")).toBeUndefined();
  });
});
