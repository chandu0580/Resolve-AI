import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ClarificationView } from "@/components/clarification/clarification-view";
import { fx } from "./fixtures";

describe("clarification packet", () => {
  it("explains why it is unsafe to resolve and what is missing", () => {
    const c = fx.clarificationVague.clarification!;
    render(<ClarificationView result={fx.clarificationVague} />);
    expect(screen.getByText("Why it is unsafe to resolve now")).toBeInTheDocument();
    expect(screen.getByText(c.why)).toBeInTheDocument();
    for (const m of c.missing_information) expect(screen.getByText(m)).toBeInTheDocument();
    expect(screen.getByText("Nothing yet")).toBeInTheDocument();
    expect(screen.getByText(c.question)).toBeInTheDocument();
    expect(screen.getByText("Issue not stated")).toBeInTheDocument();
  });

  it("shows details the customer already provided, so the question does not re-ask them", () => {
    const c = fx.clarificationInsufficientEvidence.clarification!;
    render(<ClarificationView result={fx.clarificationInsufficientEvidence} />);
    for (const p of c.already_provided) expect(screen.getByText(p)).toBeInTheDocument();
    expect(screen.getByText("No proven resolution")).toBeInTheDocument();
    expect(screen.getByText(/Battery & power/)).toBeInTheDocument();
  });

  it("renders nothing without a clarification packet", () => {
    const { container } = render(<ClarificationView result={fx.autoHandle} />);
    expect(container).toBeEmptyDOMElement();
  });
});
