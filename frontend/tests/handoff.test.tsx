import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { HandoffPacketView } from "@/components/handoff/handoff-packet";
import { handoffSummaryText } from "@/lib/handoff-summary";
import { fx } from "./fixtures";

describe("handoff packet", () => {
  afterEach(() => vi.restoreAllMocks());

  it("shows severity, queue, reason, next action and unresolved questions", () => {
    render(<HandoffPacketView result={fx.securityHandoff} />);
    const h = fx.securityHandoff.handoff!;
    expect(screen.getByText("High")).toBeInTheDocument();
    expect(screen.getByText("Queue: Security")).toBeInTheDocument();
    expect(screen.getByText(h.recommended_next_action)).toBeInTheDocument();
    expect(screen.getByText(h.customer_issue)).toBeInTheDocument();
    for (const q of h.unresolved_questions) expect(screen.getByText(q)).toBeInTheDocument();
    expect(screen.getByText(/not verified as a solution for this customer/)).toBeInTheDocument();
    expect(screen.getByText(/The agent does not produce them/)).toBeInTheDocument();
  });

  it("builds a plain-text summary from the packet only", () => {
    const text = handoffSummaryText(fx.securityHandoff);
    const h = fx.securityHandoff.handoff!;
    expect(text).toContain(`Trace: ${h.trace_id}`);
    expect(text).toContain("safety; rule security; policy-v3.1");
    expect(text).toContain("Security concern, Account access");
    expect(text).toContain(`Recommended next action: ${h.recommended_next_action}`);
    expect(text).toContain("no automatic reply was given");
    expect(handoffSummaryText(fx.autoHandle)).toBe("");
  });

  it("includes the blocked draft in the summary when verification failed", () => {
    expect(handoffSummaryText(fx.verificationFailed)).toContain("Blocked draft (do not send without review)");
  });

  it("copies the handoff summary to the clipboard", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    render(<HandoffPacketView result={fx.securityHandoff} />);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Copy handoff summary" }));
    });
    expect(writeText).toHaveBeenCalledWith(handoffSummaryText(fx.securityHandoff));
    expect(screen.getByRole("button", { name: "Copied" })).toBeInTheDocument();
  });
});
