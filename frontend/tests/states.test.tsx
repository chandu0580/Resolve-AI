import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DecisionBanner } from "@/components/decision/decision-banner";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { explainError } from "@/lib/errors";
import { fx } from "./fixtures";

describe("error and empty states", () => {
  it.each([
    ["api_unavailable", "ResolveAI API unavailable"],
    ["timeout", "The agent did not answer in time"],
    ["invalid_response", "Unexpected response"],
    ["trace_not_found", "Trace not found"],
    ["invalid_trace_id", "Invalid trace id"],
    ["evaluation_not_available", "Evaluation results unavailable"],
    ["agent_not_ready", "Agent still loading"],
    ["input_too_large", "Conversation exceeds the configured limits"],
    ["unauthorized", "Not authorized"],
    ["forbidden", "Access not permitted"],
    ["rate_limited", "Too many requests"],
  ])("%s has a specific explanation", (code, title) => {
    expect(explainError({ errorCode: code, message: "m" }).title).toBe(title);
  });

  it("falls back to the API message for unknown codes", () => {
    expect(explainError({ errorCode: "something_new", message: "API said this" })).toMatchObject({ title: "Request failed", description: "API said this" });
  });

  it("renders the error with its code, status and correlation ids", () => {
    render(<ErrorState error={{ status: 404, errorCode: "trace_not_found", message: fx.errorTraceNotFound.message, requestId: "req-9", traceId: "0".repeat(32) }} />);
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("Trace not found");
    expect(alert).toHaveTextContent("trace_not_found · HTTP 404 · request req-9");
    expect(alert).toHaveTextContent("0".repeat(32));
  });

  it("lists validation details", () => {
    render(<ErrorState error={{ status: 413, errorCode: "input_too_large", message: fx.errorInputTooLarge.message, details: fx.errorInputTooLarge.details }} />);
    expect(screen.getByText(fx.errorInputTooLarge.details[0])).toBeInTheDocument();
  });

  it("shows a model outage as a safe handoff rather than an error", () => {
    render(<DecisionBanner outcome={fx.llmUnavailable.outcome} />);
    expect(screen.getByText("Human handoff")).toBeInTheDocument();
    expect(screen.getByText("Model unavailable")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("renders an empty state with its explanation", () => {
    render(<EmptyState title="No traces recorded yet">Traces are written by the API.</EmptyState>);
    expect(screen.getByText("No traces recorded yet")).toBeInTheDocument();
    expect(screen.getByText("Traces are written by the API.")).toBeInTheDocument();
  });
});
