import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { EvidenceCard, selectionReasons } from "@/components/evidence/evidence-card";
import { EvidencePanel, ResolutionCandidates } from "@/components/evidence/evidence-panel";
import { fx } from "./fixtures";

const item = fx.autoHandle.evidence.items[0];

describe("evidence rendering", () => {
  it("shows the historical customer message, the reply, relevance and resolution signal", () => {
    render(<EvidenceCard item={item} cited />);
    expect(screen.getByRole("heading", { name: new RegExp(`Case ${item.evidence_id}`) })).toBeInTheDocument();
    expect(screen.getByText(item.customer_message)).toBeInTheDocument();
    expect(screen.getByText(item.brand_reply)).toBeInTheDocument();
    expect(screen.getByText("Cited in reply")).toBeInTheDocument();
    expect(screen.getByText("Resolution: update")).toBeInTheDocument();
    expect(screen.getByText(item.quality!.semantic_relevance.toFixed(2))).toBeInTheDocument();
  });

  it("expands to explain why the case was selected, and collapses again", () => {
    render(<EvidenceCard item={item} />);
    const toggle = screen.getByRole("button", { name: "Why selected" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText(/Ranked #1 in the question-and-reply index/)).toBeInTheDocument();
    expect(screen.getByText("dense:bge-small:pair+rr+gatev3")).toBeInTheDocument();
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText(/Ranked #1 in the question-and-reply index/)).not.toBeInTheDocument();
  });

  it("shows the source record without exposing embeddings", () => {
    const { container } = render(<EvidenceCard item={item} />);
    fireEvent.click(screen.getByRole("button", { name: "View source" }));
    expect(screen.getByText("kaggle:thoughtvector/customer-support-on-twitter:v10")).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/embedding vector|\[0\.\d+, 0\.\d+/);
  });

  it("states selection reasons only from recorded signals", () => {
    const reasons = selectionReasons(item);
    expect(reasons[0]).toMatch(/^Ranked #1/);
    expect(reasons).toContain("Written before the customer's message.");
    expect(reasons.some((r) => r.includes("states a resolution"))).toBe(true);
  });

  it("marks cited cases in the evidence panel and lists resolution patterns", () => {
    render(<EvidencePanel evidence={fx.autoHandle.evidence} citedIds={fx.autoHandle.response.evidence_refs.map((r) => r.evidence_id)} />);
    expect(screen.getAllByText("Cited in reply")).toHaveLength(fx.autoHandle.response.evidence_refs.length);
    expect(screen.getByText("Update")).toBeInTheDocument();
  });

  it("says plainly when there is no resolution pattern", () => {
    render(<ResolutionCandidates evidence={fx.clarificationInsufficientEvidence.evidence} />);
    expect(screen.getByText(/No resolution pattern/)).toBeInTheDocument();
  });

  it("has a truthful empty state when nothing was retrieved", () => {
    render(<EvidencePanel evidence={{ ...fx.autoHandle.evidence, items: [], resolution_candidates: [] }} />);
    expect(screen.getByText("No evidence retrieved")).toBeInTheDocument();
  });
});
