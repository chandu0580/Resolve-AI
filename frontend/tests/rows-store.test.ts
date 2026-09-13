import { describe, expect, it } from "vitest";
import pkg from "@/package.json";
import { MAX_RESULTS, STORAGE_KEY, clearResults, getStoredResult, loadResults, saveResult } from "@/lib/results-store";
import { isHighRisk, liveMetrics, matchesFilter, matchesQuery, mergeRows, rowFromStored } from "@/lib/rows";
import { CONSOLE_VERSION } from "@/lib/version";
import { fx } from "./fixtures";

describe("local result store", () => {
  it("saves, finds and clears full results", () => {
    saveResult(fx.autoHandle, "test");
    expect(getStoredResult(fx.autoHandle.trace_id)?.result.action).toBe("AUTO_HANDLE");
    clearResults();
    expect(loadResults()).toEqual([]);
  });

  it("keeps at most the configured number of results, newest first, without duplicates", () => {
    for (let i = 0; i < MAX_RESULTS + 5; i++) saveResult({ ...fx.autoHandle, trace_id: `t${i}` }, "test");
    saveResult({ ...fx.autoHandle, trace_id: "t3" }, "again");
    const all = loadResults();
    expect(all).toHaveLength(MAX_RESULTS);
    expect(all[0].traceId).toBe("t3");
    expect(all.filter((r) => r.traceId === "t3")).toHaveLength(1);
  });

  it("ignores corrupted storage", () => {
    localStorage.setItem(STORAGE_KEY, "{not json");
    expect(loadResults()).toEqual([]);
  });
});

describe("conversation rows", () => {
  it("merges trace summaries with local results and never invents a preview", () => {
    const stored = saveResult(fx.traces.items[0].trace_id === fx.autoHandle.trace_id ? fx.autoHandle : { ...fx.autoHandle, trace_id: fx.traces.items[0].trace_id }, "test");
    const rows = mergeRows(fx.traces.items, [stored]);
    expect(rows).toHaveLength(fx.traces.items.length);
    expect(rows.find((r) => r.traceId === stored.traceId)?.preview).toBe(fx.autoHandle.conversation.message.text);
    expect(rows.filter((r) => r.traceId !== stored.traceId).every((r) => r.preview === null)).toBe(true);
  });

  it("filters by decision, risk and evidence, and searches text and ids", () => {
    const rows = mergeRows(fx.traces.items, []);
    const count = (a: string) => fx.traces.items.filter((t) => t.final_decision === a).length;
    expect(rows.filter((r) => matchesFilter(r, "auto"))).toHaveLength(count("AUTO_HANDLE"));
    expect(rows.filter((r) => matchesFilter(r, "handoff"))).toHaveLength(count("HUMAN_HANDOFF"));
    expect(rows.filter((r) => matchesFilter(r, "insufficient_evidence"))).toHaveLength(fx.traces.items.filter((t) => t.evidence_sufficient === false).length);
    expect(rows.some((r) => matchesFilter(r, "high_risk"))).toBe(true);
    expect(rows.filter((r) => matchesQuery(r, rows[0].traceId.slice(0, 12)))).toHaveLength(1);
    expect(isHighRisk(rowFromStored({ traceId: "x", savedAt: "2026-01-01T00:00:00Z", source: "t", result: fx.securityHandoff }))).toBe(true);
    expect(isHighRisk(rowFromStored({ traceId: "y", savedAt: "2026-01-01T00:00:00Z", source: "t", result: fx.autoHandle }))).toBe(false);
  });

  it("computes live metrics only from recorded traces", () => {
    const m = liveMetrics(fx.traces.items);
    expect(m.n).toBe(fx.traces.items.length);
    expect(m.auto + m.clarification + m.handoff).toBe(m.n);
    expect(liveMetrics([])).toMatchObject({ n: 0, medianLatencyMs: null, oldest: null });
  });

  it("keeps the console version in step with package.json", () => {
    expect(CONSOLE_VERSION).toBe(pkg.version);
  });
});
