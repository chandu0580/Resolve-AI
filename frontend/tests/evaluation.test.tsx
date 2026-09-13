import { render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { parseMarkdown } from "@/components/ui/markdown";
import { fx } from "./fixtures";

const state = vi.hoisted(() => ({ fail: false }));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const mod = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...mod,
    api: {
      ...mod.api,
      evaluationSummary: () =>
        state.fail
          ? Promise.reject(new mod.ApiError(404, "evaluation_not_available", "Evaluation artifacts are missing.", { requestId: "req-eval" }))
          : Promise.resolve({ data: fx.evaluation, status: 200 }),
      evaluationRelease: () => Promise.resolve({ data: fx.release, status: 200 }),
    },
  };
});

const { default: EvaluationPage } = await import("@/app/(console)/evaluation/page");

describe("evaluation page", () => {
  beforeEach(() => {
    state.fail = false;
  });

  it("carries the frozen golden set warning and the misleading headline link", async () => {
    render(await EvaluationPage());
    expect(screen.getByText("Evaluation results are based on a frozen 197-example golden set.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Read the misleading headline analysis" })).toHaveAttribute("href", "#misleading-headline");
    const section = document.getElementById("misleading-headline")!;
    expect(within(section).getByRole("heading", { name: "What is misleading about the headline numbers" })).toBeInTheDocument();
    expect(section.textContent).toContain("197 rows, 37 escalation positives, 9 autonomous replies.");
  });

  it("shows headline metrics with confidence intervals from the artifacts", async () => {
    render(await EvaluationPage());
    const headline = document.querySelector<HTMLElement>('[aria-label="Headline metrics"]')!;
    expect(headline).toBeTruthy();
    expect(within(headline).getByText("0.854")).toBeInTheDocument();
    expect(within(headline).getByText(/95% CI 0\.(799|800) to 0\.901/)).toBeInTheDocument();
    expect(within(headline).getByText("94.6%")).toBeInTheDocument();
    expect(within(headline).getByText("0")).toBeInTheDocument();
  });

  it("covers intent, escalation, autonomy, retrieval, groundedness, latency, cost and baselines", async () => {
    render(await EvaluationPage());
    for (const name of ["Intent", "Escalation", "Autonomy", "Retrieval", "Groundedness and reply quality", "Latency and cost", "Baselines and ablations", "Statistical uncertainty"]) {
      expect(screen.getByRole("heading", { level: 2, name })).toBeInTheDocument();
    }
    expect(screen.getByText("Pending human ratings")).toBeInTheDocument();
    expect(screen.getAllByText("B2 direct LLM").length).toBeGreaterThan(0);
  });

  it("renders an explicit error state when the artifacts are unavailable", async () => {
    state.fail = true;
    render(await EvaluationPage());
    expect(screen.getByRole("alert")).toHaveTextContent("Evaluation results unavailable");
    expect(screen.getByRole("alert")).toHaveTextContent("req-eval");
  });

  it("parses the evaluation markdown, keeping the document's own list numbering", () => {
    const blocks = parseMarkdown(fx.evaluation.misleading_headline_md!);
    const list = blocks.find((b) => b.kind === "ol");
    expect(list && list.kind === "ol" && list.items.map((i) => i.value).slice(-2)).toEqual([13, 12]);
    const table = parseMarkdown(fx.evaluation.statistical_uncertainty_md!).find((b) => b.kind === "table");
    expect(table && table.kind === "table" && table.header[0]).toBe("system");
  });
});
