/** Groups a trace's recorded events into the pipeline stages shown on the timeline. Pure display logic over recorded data. */
import type { TraceEvent } from "@/lib/api/types";
import { STAGE_ORDER } from "@/lib/labels";

export type StageStatus = "ok" | "skipped" | "fallback" | "error" | "flagged" | "not_recorded";

export interface StageGroup {
  key: string;
  label: string;
  events: TraceEvent[];
  status: StageStatus;
  statusDetail: string | null;
  durationMs: number | null;
  startedAt: string | null;
}

function normalize(raw: string | undefined | null): { status: StageStatus; detail: string | null } {
  if (!raw) return { status: "not_recorded", detail: null };
  if (raw === "ok") return { status: "ok", detail: null };
  if (raw === "skipped") return { status: "skipped", detail: null };
  if (raw === "fallback") return { status: "fallback", detail: null };
  if (raw === "error" || raw === "failed") return { status: "error", detail: null };
  return { status: "flagged", detail: raw };
}

const RANK: Record<StageStatus, number> = { not_recorded: 0, ok: 1, skipped: 1, flagged: 2, fallback: 3, error: 4 };

/** Failure events carry the stage that emitted them in `component`; they belong on that stage's row, not in "Other events". */
const COMPONENT_STAGE: Record<string, string> = { embedding: "intent", intent: "intent", second_opinion: "intent", context: "context", retrieval: "retrieval",
  risk: "risk", policy: "policy", draft: "draft", verification: "verification", output_gate: "decision", trace_store: "complete" };
const FAILURE_EVENTS = new Set(["model_call_failed", "dependency_failed"]);

export function groupTraceEvents(events: TraceEvent[], stageStatus: Record<string, string> = {}, latency: Record<string, number> = {}): StageGroup[] {
  const claimed = new Set<number>();
  const groups = STAGE_ORDER.map((stage) => {
    const evs = events.filter((e, i) => {
      if (FAILURE_EVENTS.has(e.name) ? COMPONENT_STAGE[e.component] === stage.key : stage.events.includes(e.name)) {
        claimed.add(i);
        return true;
      }
      return false;
    });
    // Status: the worst of the recorded stage status and the event statuses.
    let best = { status: "not_recorded" as StageStatus, detail: null as string | null };
    const candidates = [...stage.latencyKeys.map((k) => stageStatus[k]), ...evs.map((e) => e.status)];
    for (const c of candidates) {
      const n = normalize(c);
      if (RANK[n.status] > RANK[best.status] || (best.status === "not_recorded" && n.status !== "not_recorded")) best = n;
    }
    if (best.status === "not_recorded" && evs.length) best = { status: "ok", detail: null };
    const keyed = stage.latencyKeys.filter((k) => typeof latency[k] === "number");
    const durationMs = keyed.length ? keyed.reduce((s, k) => s + latency[k], 0) : evs.length ? evs.reduce((s, e) => s + (e.latency_ms ?? 0), 0) : null;
    return { key: stage.key, label: stage.label, events: evs, status: best.status, statusDetail: best.detail, durationMs, startedAt: evs[0]?.ts ?? null };
  });
  const unclaimed = events.filter((_, i) => !claimed.has(i));
  if (unclaimed.length) {
    groups.push({ key: "other", label: "Other events", events: unclaimed, status: "ok", statusDetail: null, durationMs: null, startedAt: unclaimed[0].ts });
  }
  return groups;
}

export function eventData<T = Record<string, unknown>>(events: TraceEvent[], name: string): T | undefined {
  return events.find((e) => e.name === name)?.data as T | undefined;
}
