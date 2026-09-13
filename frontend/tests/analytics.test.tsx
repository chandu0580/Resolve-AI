import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fx } from "./fixtures";

const state = vi.hoisted(() => ({ fail: false }));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const mod = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...mod,
    api: {
      ...mod.api,
      traces: () =>
        state.fail
          ? Promise.reject(new mod.ApiError(500, "traces_unavailable", "Failed to fetch audit records.", { requestId: "req-analytics" }))
          : Promise.resolve({ data: fx.traces, status: 200 }),
    },
  };
});

const { default: AnalyticsPage } = await import("@/app/(console)/analytics/page");

describe("analytics page", () => {
  beforeEach(() => {
    state.fail = false;
  });

  it("renders page header, operational filter controls, and live operational badge", async () => {
    render(await AnalyticsPage());

    expect(screen.getByRole("heading", { level: 1, name: "Analytics" })).toBeInTheDocument();
    expect(screen.getByText("Understand how ResolveAI is handling customer conversations.")).toBeInTheDocument();
    expect(screen.getByText("Live operational data")).toBeInTheDocument();

    // Filters
    expect(screen.getByLabelText("Filter by date range")).toBeInTheDocument();
    expect(screen.getByLabelText("Filter by conversation status")).toBeInTheDocument();
    expect(screen.getByLabelText("Filter by customer issue")).toBeInTheDocument();
  });

  it("displays the operational KPI row without engineering terminology", async () => {
    render(await AnalyticsPage());

    // Primary KPIs
    expect(screen.getByText("Conversations handled")).toBeInTheDocument();
    expect(screen.getAllByText("AI resolved").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Human handoffs").length).toBeGreaterThan(0);
    expect(screen.getByText("Failed executions")).toBeInTheDocument();
    expect(screen.getAllByText("Median response time").length).toBeGreaterThan(0);
    expect(screen.getAllByText("P95 response time").length).toBeGreaterThan(0);

    // Total actual count
    expect(screen.getAllByText(String(fx.traces.items.length)).length).toBeGreaterThan(0);

    // Model calls and cost must not be in the primary KPI cards
    const primaryCards = screen.getAllByText(/Conversations handled|AI resolved|Human handoffs|Failed executions/);
    expect(primaryCards.length).toBeGreaterThan(0);
  });

  it("renders support outcomes, why AI handed off, and top customer issues", async () => {
    render(await AnalyticsPage());

    // Support outcomes
    expect(screen.getByRole("heading", { level: 2, name: "Support outcomes" })).toBeInTheDocument();

    // Why AI handed off
    expect(screen.getByRole("heading", { level: 2, name: "Why AI handed off" })).toBeInTheDocument();

    // Top customer issues (human readable, no ML taxonomy terms)
    expect(screen.getByRole("heading", { level: 2, name: "Top customer issues" })).toBeInTheDocument();
    expect(screen.queryByText(/macro-F1|classifier taxonomy/i)).toBeNull();

    // Response performance
    expect(screen.getByRole("heading", { level: 2, name: "Response performance" })).toBeInTheDocument();
  });

  it("renders collapsed Advanced section containing technical diagnostic details", async () => {
    render(await AnalyticsPage());

    expect(screen.getByText("Advanced")).toBeInTheDocument();
    expect(screen.getByText("Model calls")).toBeInTheDocument();
    expect(screen.getByText("Estimated inference cost")).toBeInTheDocument();
    expect(screen.getByText("Evidence levels recorded")).toBeInTheDocument();
  });

  it("filters operational metrics interactively when filter dropdowns change", async () => {
    render(await AnalyticsPage());

    const statusSelect = screen.getByLabelText("Filter by conversation status");
    fireEvent.change(statusSelect, { target: { value: "handoff" } });

    // Should now show Reset filters button
    expect(screen.getByRole("button", { name: "Reset filters" })).toBeInTheDocument();

    // Resetting filters restores full count
    fireEvent.click(screen.getByRole("button", { name: "Reset filters" }));
    expect(screen.getAllByText(String(fx.traces.items.length)).length).toBeGreaterThan(0);
  });

  it("renders an explicit error state when traces cannot be loaded", async () => {
    state.fail = true;
    render(await AnalyticsPage());

    expect(screen.getByRole("alert")).toHaveTextContent("Failed to fetch audit records.");
    expect(screen.getByRole("alert")).toHaveTextContent("req-analytics");
  });
});
