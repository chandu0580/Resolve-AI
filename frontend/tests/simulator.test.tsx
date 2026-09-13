import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Simulator } from "@/components/simulate/simulator";
import { ApiError, api } from "@/lib/api/client";
import { STORAGE_KEY } from "@/lib/results-store";
import { fx } from "./fixtures";

vi.mock("@/lib/api/client", async (importOriginal) => {
  const mod = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...mod, api: { ...mod.api, resolve: vi.fn(), trace: vi.fn() } };
});

function renderSimulator() {
  return render(<Simulator scenarios={fx.scenarios} scenariosError={null} maxMessageChars={2000} model="glm-5.2" />);
}

describe("Try ResolveAI simulator", () => {
  beforeEach(() => {
    vi.mocked(api.resolve).mockReset();
    vi.mocked(api.trace).mockReset().mockResolvedValue({ data: fx.traceAuto, status: 200 });
  });

  it("is clearly labelled as a simulation and lists the API's demo scenarios", () => {
    renderSimulator();
    expect(screen.getByText("Simulation")).toBeInTheDocument();
    expect(screen.getByText(/Nothing is sent to any customer or channel/)).toBeInTheDocument();
    for (const s of fx.scenarios) expect(screen.getByRole("heading", { name: s.title })).toBeInTheDocument();
  });

  it("validates the message before calling the API", () => {
    renderSimulator();
    fireEvent.click(screen.getByRole("button", { name: "Analyze" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Enter the customer message to analyze.");
    expect(api.resolve).not.toHaveBeenCalled();
  });

  it("shows honest loading while running, then the full result, and stores it in this browser", async () => {
    let finish!: (v: unknown) => void;
    vi.mocked(api.resolve).mockReturnValue(new Promise((resolve) => (finish = resolve)) as never);
    renderSimulator();
    fireEvent.change(screen.getByLabelText("Customer message"), { target: { value: fx.autoHandle.conversation.message.text } });
    fireEvent.click(screen.getByRole("button", { name: "Analyze" }));

    expect(screen.getByRole("status")).toHaveTextContent("Analyzing request\u2026");
    expect(screen.getByText(/Reviewing intent, evidence, and safety boundaries/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Analyze" })).toBeDisabled();
    expect(screen.queryByText("Policy")).not.toBeInTheDocument();

    await act(async () => finish({ data: fx.autoHandle, status: 200 }));

    expect(vi.mocked(api.resolve).mock.calls[0][0]).toEqual({ conversation: [{ role: "customer", text: fx.autoHandle.conversation.message.text }], metadata: { channel: "web" } });
    expect(screen.getByRole("heading", { name: "Generated response" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: /Decision: Auto-handled/ })).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "Agent stages for this run" })).toHaveTextContent("Evidence gate");
    expect(JSON.parse(localStorage.getItem(STORAGE_KEY)!)[0].traceId).toBe(fx.autoHandle.trace_id);
  });

  it("runs a demo scenario through /resolve and compares expected with actual", async () => {
    const scenario = fx.scenarios.find((s) => s.id === "C")!;
    vi.mocked(api.resolve).mockResolvedValue({ data: fx.securityHandoff, status: 200 });
    renderSimulator();
    await act(async () => fireEvent.click(screen.getByRole("button", { name: `Run scenario C: ${scenario.title}` })));
    expect(vi.mocked(api.resolve).mock.calls[0][0].conversation).toEqual(scenario.conversation);
    expect(screen.getByRole("list", { name: "Expected versus actual" })).toHaveTextContent("Decision is human handoff");
    expect(screen.getByRole("button", { name: "Copy handoff summary" })).toBeInTheDocument();
  });

  it("offers the seven curated demo situations, mapped to API scenarios or a curated message", async () => {
    vi.mocked(api.resolve).mockResolvedValue({ data: fx.injectionHandoff, status: 200 });
    renderSimulator();
    const path = screen.getByRole("list", { name: "Curated demo path" });
    expect(path.querySelectorAll(":scope > li")).toHaveLength(7);
    const scenarioE = fx.scenarios.find((s) => s.id === "E")!;
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Run curated scenario 6: Prompt injection" })));
    expect(vi.mocked(api.resolve).mock.calls[0][0].conversation).toEqual(scenarioE.conversation);
  });

  it("shows an explicit error when the API is unavailable", async () => {
    vi.mocked(api.resolve).mockRejectedValue(new ApiError(502, "api_unavailable", "The ResolveAI API is not reachable."));
    renderSimulator();
    fireEvent.change(screen.getByLabelText("Customer message"), { target: { value: "hello" } });
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Analyze" })));
    expect(screen.getByRole("alert")).toHaveTextContent("ResolveAI API unavailable");
  });

  it("refuses to render a response that is not a ResolveResponse", async () => {
    vi.mocked(api.resolve).mockResolvedValue({ data: { hello: "world" }, status: 200 } as never);
    renderSimulator();
    fireEvent.change(screen.getByLabelText("Customer message"), { target: { value: "hello" } });
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Analyze" })));
    expect(screen.getByRole("alert")).toHaveTextContent("Unexpected response");
    expect(localStorage.getItem(STORAGE_KEY)).toBeNull();
  });
});
