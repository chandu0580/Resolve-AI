import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DecisionBanner } from "@/components/decision/decision-banner";
import { DecisionDetails } from "@/components/decision/decision-details";
import { EvidenceSufficiency } from "@/components/decision/evidence-sufficiency";
import { OutputGateChecklist } from "@/components/decision/output-gate";
import { fx } from "./fixtures";

describe("decision rendering", () => {
  it("shows AUTO-HANDLED with the policy rule and version", () => {
    render(<DecisionBanner outcome={fx.autoHandle.outcome} />);
    const banner = screen.getByRole("region", { name: /Decision: Auto-handled/i });
    expect(within(banner).getByText("Auto-handled")).toBeInTheDocument();
    expect(within(banner).getByText("default_auto")).toBeInTheDocument();
    expect(within(banner).getByText("policy-v3.1")).toBeInTheDocument();
    expect(within(banner).getByText(fx.autoHandle.outcome.why)).toBeInTheDocument();
  });

  it("shows HUMAN HANDOFF with a human-readable reason", () => {
    render(<DecisionBanner outcome={fx.securityHandoff.outcome} />);
    expect(screen.getByText("Human handoff")).toBeInTheDocument();
    expect(screen.getByText("Safety or security concern")).toBeInTheDocument();
    expect(screen.getByText("security")).toBeInTheDocument();
  });

  it("shows CLARIFICATION REQUIRED", () => {
    render(<DecisionBanner outcome={fx.clarificationVague.outcome} />);
    expect(screen.getByText("Clarification")).toBeInTheDocument();
    expect(screen.getByText("Issue not stated")).toBeInTheDocument();
  });

  it("renders evidence sufficiency as a four-step scale with an explanation, not as confidence", () => {
    const { container } = render(<EvidenceSufficiency evidence={fx.autoHandle.evidence} />);
    const scale = screen.getByRole("list", { name: "Evidence sufficiency scale" });
    const steps = within(scale).getAllByRole("listitem");
    expect(steps.map((s) => s.textContent)).toEqual(["Insufficient", "Weak", "Sufficient", "Strong"]);
    expect(steps[3]).toHaveAttribute("aria-current", "step");
    expect(screen.getByText(/Several independent historical cases/)).toBeInTheDocument();
    expect(screen.getByText("Consistent resolution across independent cases")).toBeInTheDocument();
    expect(container.textContent).toMatch(/not the model's confidence/);
    expect(container.querySelector("[role=meter]")).toBeNull();
  });

  it("explains insufficient evidence", () => {
    render(<EvidenceSufficiency evidence={fx.clarificationInsufficientEvidence.evidence} />);
    expect(screen.getAllByText("Insufficient").length).toBeGreaterThan(0);
    expect(screen.getByText("Not enough to answer")).toBeInTheDocument();
    expect(screen.getByText("Closest historical cases are not similar enough")).toBeInTheDocument();
  });

  it("lists every output-gate check with text, not colour alone", () => {
    render(<OutputGateChecklist gate={fx.securityHandoff.outcome.output_gate} blocking={fx.securityHandoff.outcome.blocking_checks} />);
    expect(screen.getByText(/Evidence sufficient/)).toHaveTextContent("not met");
    expect(screen.getByText(/Intent confidence acceptable/)).toHaveTextContent("met");
    expect(screen.getAllByRole("listitem")).toHaveLength(Object.keys(fx.securityHandoff.outcome.output_gate).length);
  });

  it("shows intent, risk and policy inputs behind the decision", () => {
    render(<DecisionDetails result={fx.securityHandoff} />);
    expect(screen.getByText("Account, store & repair")).toBeInTheDocument();
    expect(screen.getByText("Security concern")).toBeInTheDocument();
    expect(screen.getByText("Account access")).toBeInTheDocument();
    expect(screen.getByText(/The model never decides whether to escalate/)).toBeInTheDocument();
    expect(screen.getByRole("meter", { name: "Calibrated intent confidence" })).toHaveAttribute("aria-valuetext", "79.8%");
  });
});
