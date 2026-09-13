import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AuditLogView } from "@/components/trace/audit-log-view";
import type { TraceSummary } from "@/lib/api/types";

const mockTraces: TraceSummary[] = [
  {
    trace_id: "9d074d75ecf74eebce771681c0cca15",
    request_id: "1c27716b30181cfd",
    started_at: "2026-09-13T05:59:25.000Z",
    final_decision: "HUMAN_HANDOFF",
    reason_code: "repeat_contact",
    pipeline_version: "pipeline-v5.1",
    latency_ms: 301,
    intent: "keyboard_text_bug",
    evidence_level: "STRONG",
    llm_calls: 0,
  } as unknown as TraceSummary,
  {
    trace_id: "7803a52b359b490ba35176cee3a4f50f",
    request_id: "8371c677ad2717bf",
    started_at: "2026-09-13T05:59:12.000Z",
    final_decision: "AUTO_HANDLE",
    reason_code: "none",
    pipeline_version: "pipeline-v5.1",
    latency_ms: 4,
    intent: "battery_power",
    evidence_level: "STRONG",
    llm_calls: 2,
  } as unknown as TraceSummary,
  {
    trace_id: "ac3f6d23a9e94ce189b6f149c1232d0c",
    request_id: "ac8911b4a0931889",
    started_at: "2026-09-13T05:58:54.000Z",
    final_decision: "CLARIFICATION_REQUIRED",
    reason_code: "insufficient_context",
    pipeline_version: "pipeline-v5.1",
    latency_ms: 14000,
    intent: "account_store_repair",
    evidence_level: "INSUFFICIENT",
    llm_calls: 4,
  } as unknown as TraceSummary,
];

describe("AuditLogView", () => {
  it("renders today's activity summary with accurate counts", () => {
    render(<AuditLogView initialItems={mockTraces} currentAction="" />);

    expect(screen.getByText("Today's activity")).toBeInTheDocument();
    expect(screen.getAllByText("Auto-handled").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Clarifications").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Human handoffs").length).toBeGreaterThan(0);

    // Check count numbers
    expect(screen.getByText("1", { selector: "span.text-emerald-700" })).toBeInTheDocument();
    expect(screen.getByText("1", { selector: "span.text-amber-800" })).toBeInTheDocument();
    expect(screen.getByText("1", { selector: "span.text-brand-700" })).toBeInTheDocument();
  });

  it("renders operator-friendly table columns and human-readable titles without raw UUID titles", () => {
    render(<AuditLogView initialItems={mockTraces} currentAction="" />);

    // Table headers
    expect(screen.getByRole("columnheader", { name: "Conversation" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Time" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Decision" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Reason" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Evidence" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Human involvement" })).toBeInTheDocument();

    // Human-readable conversation titles
    expect(screen.getByText("iPhone keyboard & autocorrect issue")).toBeInTheDocument();
    expect(screen.getByText("Battery performance & charging inquiry")).toBeInTheDocument();
    expect(screen.getByText("Account, store & repair request")).toBeInTheDocument();

    // Plain-English reasons
    expect(screen.getByText("Repeated unresolved request")).toBeInTheDocument();
    expect(screen.getByText("Verified support resolution")).toBeInTheDocument();
    expect(screen.getByText("Request needs more information")).toBeInTheDocument();

    // Human involvement
    expect(screen.getByText("Human required")).toBeInTheDocument();
    expect(screen.getAllByText("AI handled").length).toBeGreaterThan(0);

    // Engineering jargon should NOT be present in the main table headers
    expect(screen.queryByRole("columnheader", { name: /model calls/i })).toBeNull();
    expect(screen.queryByRole("columnheader", { name: /latency/i })).toBeNull();
    expect(screen.queryByRole("columnheader", { name: /pipeline/i })).toBeNull();
  });

  it("filters items when clicking decision filter buttons", async () => {
    const user = userEvent.setup();
    render(<AuditLogView initialItems={mockTraces} currentAction="" />);

    const autoBtn = screen.getByRole("button", { name: "Auto-handled" });
    await user.click(autoBtn);

    expect(screen.getByText("Battery performance & charging inquiry")).toBeInTheDocument();
    expect(screen.queryByText("iPhone keyboard & autocorrect issue")).toBeNull();
    expect(screen.queryByText("Account, store & repair request")).toBeNull();

    const handoffBtn = screen.getByRole("button", { name: "Human handoff" });
    await user.click(handoffBtn);

    expect(screen.getByText("iPhone keyboard & autocorrect issue")).toBeInTheDocument();
    expect(screen.queryByText("Battery performance & charging inquiry")).toBeNull();
  });

  it("filters items by search input", async () => {
    const user = userEvent.setup();
    render(<AuditLogView initialItems={mockTraces} currentAction="" />);

    const searchInput = screen.getByPlaceholderText("Search conversations...");
    await user.type(searchInput, "keyboard");

    expect(screen.getByText("iPhone keyboard & autocorrect issue")).toBeInTheDocument();
    expect(screen.queryByText("Battery performance & charging inquiry")).toBeNull();
    expect(screen.queryByText("Account, store & repair request")).toBeNull();
  });
});
