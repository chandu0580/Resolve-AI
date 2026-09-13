import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ResponsePanel } from "@/components/response/response-panel";
import { fx } from "./fixtures";

describe("response panel", () => {
  it("labels an automatic reply as a grounded, verified, simulated response", () => {
    render(<ResponsePanel result={fx.autoHandle} />);
    expect(screen.getByRole("heading", { name: "Generated response" })).toBeInTheDocument();
    expect(screen.getByText(`Grounded in ${fx.autoHandle.response.evidence_refs.length} cases`)).toBeInTheDocument();
    expect(screen.getByText("Verified")).toBeInTheDocument();
    expect(screen.getByText("Simulated response. Nothing was sent to a customer.")).toBeInTheDocument();
    expect(screen.getByText(fx.autoHandle.response.text)).toBeInTheDocument();
    for (const ref of fx.autoHandle.response.evidence_refs) {
      expect(screen.getByRole("link", { name: new RegExp(ref.evidence_id) })).toHaveAttribute("href", `#evidence-${ref.evidence_id}`);
    }
  });

  it("shows a clarification as a question, not an answer", () => {
    render(<ResponsePanel result={fx.clarificationVague} />);
    expect(screen.getByRole("heading", { name: "Clarification" })).toBeInTheDocument();
    expect(screen.getByText("Question, not an answer")).toBeInTheDocument();
    expect(screen.getByText(fx.clarificationVague.response.text)).toBeInTheDocument();
  });

  it("shows NO CUSTOMER RESPONSE for a handoff and never implies an answer was sent", () => {
    const { container } = render(<ResponsePanel result={fx.securityHandoff} />);
    expect(screen.getByRole("heading", { name: "No customer response: human handoff" })).toBeInTheDocument();
    expect(screen.getByText(/Holding notice a customer would see/)).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/\bwas sent\b(?! to)/i);
  });

  it("shows a draft blocked by verification with the verifier's issues", () => {
    render(<ResponsePanel result={fx.verificationFailed} />);
    expect(screen.getByText("Draft blocked by verification")).toBeInTheDocument();
    expect(screen.getByText(fx.verificationFailed.handoff!.draft_if_any!)).toBeInTheDocument();
    expect(screen.getByText(/a step that is not present in the cited evidence/)).toBeInTheDocument();
  });
});
