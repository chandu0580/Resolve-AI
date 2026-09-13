import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Sidebar } from "@/components/shell/sidebar";

// Mock next/navigation usePathname
const mockPathname = vi.fn();
vi.mock("next/navigation", () => ({
  usePathname: () => mockPathname(),
}));

describe("Sidebar collapsible navigation", () => {
  it("renders the 4 primary groups and expands only the active group initially", () => {
    mockPathname.mockReturnValue("/overview");
    render(<Sidebar />);

    // Brand and workspace context
    expect(screen.getByText("ResolveAI")).toBeInTheDocument();
    expect(screen.getByText("Apple Support")).toBeInTheDocument();

    // 4 primary categories exist as buttons
    const workspaceBtn = screen.getByRole("button", { name: /workspace/i });
    const aiBtn = screen.getByRole("button", { name: /ai/i });
    const insightsBtn = screen.getByRole("button", { name: /insights/i });
    const governanceBtn = screen.getByRole("button", { name: /governance/i });

    expect(workspaceBtn).toHaveAttribute("aria-expanded", "true");
    expect(aiBtn).toHaveAttribute("aria-expanded", "false");
    expect(insightsBtn).toHaveAttribute("aria-expanded", "false");
    expect(governanceBtn).toHaveAttribute("aria-expanded", "false");

    // Children of Workspace are visible
    expect(screen.getByRole("link", { name: /overview/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /conversations/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /handoffs/i })).toBeInTheDocument();

    // Children of other groups are not rendered
    expect(screen.queryByRole("link", { name: /test the agent/i })).toBeNull();
    expect(screen.queryByRole("link", { name: /evaluation/i })).toBeNull();
    expect(screen.queryByRole("link", { name: /trust & safety/i })).toBeNull();
  });

  it("allows multiple groups to be expanded simultaneously (independent toggle)", () => {
    mockPathname.mockReturnValue("/overview");
    render(<Sidebar />);

    const workspaceBtn = screen.getByRole("button", { name: /workspace/i });
    const aiBtn = screen.getByRole("button", { name: /ai/i });
    const insightsBtn = screen.getByRole("button", { name: /insights/i });
    const governanceBtn = screen.getByRole("button", { name: /governance/i });

    // Initially, Workspace is expanded
    expect(workspaceBtn).toHaveAttribute("aria-expanded", "true");
    expect(aiBtn).toHaveAttribute("aria-expanded", "false");

    // Click AI group - both Workspace and AI are now expanded!
    fireEvent.click(aiBtn);
    expect(workspaceBtn).toHaveAttribute("aria-expanded", "true");
    expect(aiBtn).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("link", { name: /overview/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /test the agent/i })).toBeInTheDocument();

    // Click Insights - Workspace, AI, and Insights are all expanded!
    fireEvent.click(insightsBtn);
    expect(insightsBtn).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("link", { name: /evaluation/i })).toBeInTheDocument();

    // Click Governance - all 4 groups are expanded!
    fireEvent.click(governanceBtn);
    expect(governanceBtn).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("link", { name: /trust & safety/i })).toBeInTheDocument();

    // Click AI to collapse it - other 3 remain expanded
    fireEvent.click(aiBtn);
    expect(aiBtn).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("link", { name: /test the agent/i })).toBeNull();
    expect(workspaceBtn).toHaveAttribute("aria-expanded", "true");
    expect(insightsBtn).toHaveAttribute("aria-expanded", "true");
    expect(governanceBtn).toHaveAttribute("aria-expanded", "true");
  });

  it("marks the active child route with aria-current and active styling", () => {
    mockPathname.mockReturnValue("/simulate");
    render(<Sidebar />);

    // AI should be expanded because /simulate is inside AI
    const aiBtn = screen.getByRole("button", { name: /ai/i });
    expect(aiBtn).toHaveAttribute("aria-expanded", "true");

    const testAgentLink = screen.getByRole("link", { name: /test the agent/i });
    expect(testAgentLink).toHaveAttribute("aria-current", "page");
    expect(testAgentLink.className).toContain("bg-brand-50");
    expect(testAgentLink.className).toContain("text-brand-700");
  });
});
