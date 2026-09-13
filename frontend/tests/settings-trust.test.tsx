import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SettingsDashboard } from "@/components/settings/settings-dashboard";
import { TrustDashboard } from "@/components/trust/trust-dashboard";
import { fx } from "./fixtures";
import type { HealthResponse, KnowledgeSummary, ReleaseEvaluation, RuntimeConfig } from "@/lib/api/types";

const mockConfig = (over: { auth?: boolean; traces?: boolean; llm?: boolean } = {}) =>
  ({
    service: {
      env: "development",
      write_traces: over.traces ?? true,
      trace_store: { kind: "jsonl", dir: "traces" },
      rate_limit_per_minute: 60,
      max_queue: 4,
      docs_enabled: true,
      auth: { required: over.auth ?? false, scheme: "bearer" },
      limits: { max_body_bytes: 64000, max_message_chars: 2000, max_turn_chars: 2000, max_turns: 20, max_total_chars: 12000 },
    },
    llm: { configured: true, enabled: over.llm ?? true, model: "gpt-4o", provider: "openai", temperature: 0, timeout_s: 30, max_retries: 1 },
    embedding_model: "text-embedding-3-small",
    brand: "Apple Support",
    agent_state: "loaded",
  }) as unknown as RuntimeConfig;

describe("SettingsDashboard", () => {
  const dummyHealth: HealthResponse = {
    status: "ok",
    version: "1.0.0",
    env: "development",
    service: "resolveai",
    uptime_s: 120,
  };

  it("renders the 5 primary sections with enterprise operational controls", () => {
    render(
      <SettingsDashboard
        config={mockConfig()}
        health={dummyHealth}
        knowledge={fx.knowledge as unknown as KnowledgeSummary}
        tokenPresent={true}
      />
    );

    // 1. AI Agent Section
    expect(screen.getByRole("heading", { name: "AI Agent" })).toBeInTheDocument();
    expect(screen.getByText("Agent status")).toBeInTheDocument();
    expect(screen.getByText("Default behavior")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Online" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Paused" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Resolve automatically" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ask before resolving" })).toBeInTheDocument();
    expect(screen.getByText("Customer asks for a human")).toBeInTheDocument();
    expect(screen.getByText("Safety or security concern")).toBeInTheDocument();

    // 2. Support Channels
    expect(screen.getByRole("heading", { name: "Support Channels" })).toBeInTheDocument();
    expect(screen.getByText("Web chat")).toBeInTheDocument();
    expect(screen.getByText("Connected")).toBeInTheDocument();

    // 3. Knowledge
    expect(screen.getByRole("heading", { name: "Knowledge" })).toBeInTheDocument();
    expect(screen.getByText("Knowledge sources")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /manage knowledge/i })).toHaveAttribute("href", "/knowledge");

    // 4. Human Handoff
    expect(screen.getByRole("heading", { name: "Human Handoff" })).toBeInTheDocument();
    expect(screen.getByText("Primary Support Queue")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /view handoffs queue/i })).toHaveAttribute("href", "/handoffs");

    // 5. Workspace
    expect(screen.getByRole("heading", { name: "Workspace" })).toBeInTheDocument();
    expect(screen.getByText("Support brand")).toBeInTheDocument();
    expect(screen.getByText("Current environment")).toBeInTheDocument();

    // 6. Advanced Section is present
    expect(screen.getByText("Advanced")).toBeInTheDocument();
  });

  it("toggles agent status and default behavior buttons", async () => {
    const user = userEvent.setup();
    render(
      <SettingsDashboard
        config={mockConfig()}
        health={dummyHealth}
        knowledge={fx.knowledge as unknown as KnowledgeSummary}
        tokenPresent={false}
      />
    );

    const pausedBtn = screen.getByRole("button", { name: "Paused" });
    await user.click(pausedBtn);
    expect(pausedBtn).toHaveAttribute("aria-pressed", "true");

    const reviewBtn = screen.getByRole("button", { name: "Ask before resolving" });
    await user.click(reviewBtn);
    expect(reviewBtn).toHaveAttribute("aria-pressed", "true");
  });
});

describe("TrustDashboard", () => {
  it("renders the 3 summary metrics and 6 clean safeguard cards", () => {
    render(
      <TrustDashboard
        config={mockConfig()}
        release={fx.release as unknown as ReleaseEvaluation}
      />
    );

    // Summary banner
    expect(screen.getByText("AI safety")).toBeInTheDocument();
    expect(screen.getByText("6 safeguards active")).toBeInTheDocument();
    expect(screen.getByText("Automatic replies")).toBeInTheDocument();
    expect(screen.getByText("Human oversight")).toBeInTheDocument();

    // 6 Clean Safeguards
    expect(screen.getByRole("heading", { name: "Human handoff" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Grounded responses" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Privacy protection" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Prompt injection protection" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Response verification" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "AI failure fallback" })).toBeInTheDocument();

    // Checks key descriptions
    expect(screen.getByText(/hands conversations to a human when the request is unsafe/i)).toBeInTheDocument();
    expect(screen.getByText(/only sends an automatic answer when it has sufficient verified support evidence/i)).toBeInTheDocument();
    expect(screen.getByText(/sensitive customer information is protected before it reaches ai processing/i)).toBeInTheDocument();
    expect(screen.getByText(/attempts to override the agent's instructions or safety boundaries are blocked/i)).toBeInTheDocument();
    expect(screen.getByText(/if verification fails: human handoff/i)).toBeInTheDocument();
    expect(screen.getByText(/falls back to a human handoff/i)).toBeInTheDocument();

    // Advanced section contains release verification and technical controls
    expect(screen.getByText("Advanced verification")).toBeInTheDocument();
    expect(screen.getByText("Release 1.0.0 verification")).toBeInTheDocument();
  });
});
