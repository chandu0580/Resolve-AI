"use client";

import { ChevronDown, ChevronRight, Circle, CircleCheck, CircleX, Minus, ShieldAlert, TriangleAlert } from "lucide-react";
import { useId, useMemo, useState, type ElementType } from "react";
import type { TraceEvent } from "@/lib/api/types";
import { duration, humanize, timeOfDay } from "@/lib/format";
import { EVENT_LABELS } from "@/lib/labels";
import { groupTraceEvents, type StageStatus } from "@/lib/trace";

export const STAGE_STATUS_META: Record<StageStatus, { label: string; icon: ElementType; cls: string }> = {
  ok: { label: "Completed", icon: CircleCheck, cls: "text-success" },
  skipped: { label: "Skipped", icon: Minus, cls: "text-ink-3" },
  fallback: { label: "Fallback", icon: TriangleAlert, cls: "text-warning" },
  error: { label: "Error", icon: CircleX, cls: "text-danger" },
  flagged: { label: "Flagged", icon: ShieldAlert, cls: "text-info" },
  not_recorded: { label: "Not recorded", icon: Circle, cls: "text-ink-3" },
};

function renderValue(v: unknown): string {
  if (v === null || v === undefined) return "null";
  if (typeof v === "number") return Number.isInteger(v) ? String(v) : v.toFixed(4).replace(/0+$/, "").replace(/\.$/, "");
  if (typeof v === "string" || typeof v === "boolean") return String(v);
  if (Array.isArray(v) && v.every((x) => typeof x !== "object" || x === null)) return v.length ? v.join(", ") : "[]";
  return JSON.stringify(v);
}

function EventDetail({ event }: { event: TraceEvent }) {
  const entries = Object.entries(event.data ?? {});
  return (
    <div className="rounded-md border border-line bg-canvas px-3 py-2">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <span className="text-[13px] font-medium text-ink">{EVENT_LABELS[event.name] ?? humanize(event.name)}</span>
        <span className="tabular text-[11px] text-ink-3">
          {timeOfDay(event.ts)} · {duration(event.latency_ms)}
        </span>
      </div>
      <div className="mt-0.5 font-mono text-[11px] text-ink-3">
        {event.name} · component {event.component} · status {event.status}
      </div>
      {entries.length ? (
        <dl className="mt-2 grid gap-x-3 gap-y-0.5 text-xs sm:grid-cols-[max-content_1fr]">
          {entries.map(([k, v]) => (
            <div key={k} className="contents">
              <dt className="font-mono text-ink-3">{k}</dt>
              <dd className="min-w-0 font-mono break-words text-ink-2">{renderValue(v)}</dd>
            </div>
          ))}
        </dl>
      ) : null}
    </div>
  );
}

export function TraceTimeline({
  events,
  stageStatus,
  latency,
  initiallyOpen = [],
}: {
  events: TraceEvent[];
  stageStatus?: Record<string, string>;
  latency?: Record<string, number>;
  initiallyOpen?: string[];
}) {
  const groups = useMemo(() => groupTraceEvents(events, stageStatus, latency), [events, stageStatus, latency]);
  const [open, setOpen] = useState<Set<string>>(() => new Set(initiallyOpen));
  const uid = useId();
  const allOpen = groups.filter((g) => g.events.length).every((g) => open.has(g.key));

  return (
    <div>
      <div className="mb-2 flex justify-end">
        <button
          type="button"
          className="rounded px-1.5 py-1 text-xs font-medium text-ink-2 hover:bg-subtle"
          onClick={() => setOpen(allOpen ? new Set() : new Set(groups.filter((g) => g.events.length).map((g) => g.key)))}
        >
          {allOpen ? "Collapse all" : "Expand all"}
        </button>
      </div>
      <ol className="relative @container" aria-label="Pipeline stages">
        {groups.map((g, i) => {
          const meta = STAGE_STATUS_META[g.status];
          const Icon = meta.icon;
          const expanded = open.has(g.key);
          const panelId = `${uid}-${g.key}`;
          const statusText = g.status === "flagged" && g.statusDetail ? humanize(g.statusDetail) : meta.label;
          return (
            <li key={g.key} className="relative pb-1 pl-7">
              {i < groups.length - 1 ? <span className="absolute top-6 bottom-0 left-[9px] w-px bg-line" aria-hidden="true" /> : null}
              <span className={`absolute top-1.5 left-0 flex size-5 items-center justify-center rounded-full bg-surface ${meta.cls}`} aria-hidden="true">
                <Icon className="size-[18px]" />
              </span>
              <button
                type="button"
                disabled={!g.events.length}
                aria-expanded={g.events.length ? expanded : undefined}
                aria-controls={g.events.length ? panelId : undefined}
                onClick={() =>
                  setOpen((prev) => {
                    const next = new Set(prev);
                    if (next.has(g.key)) next.delete(g.key);
                    else next.add(g.key);
                    return next;
                  })
                }
                className="flex w-full items-center gap-x-2 rounded-md px-2 py-1.5 text-left enabled:hover:bg-subtle disabled:cursor-default"
              >
                <span className="flex min-w-0 flex-1 items-center gap-1.5">
                  {g.events.length ? (
                    expanded ? <ChevronDown className="size-3.5 shrink-0 text-ink-3" aria-hidden="true" /> : <ChevronRight className="size-3.5 shrink-0 text-ink-3" aria-hidden="true" />
                  ) : (
                    <span className="size-3.5 shrink-0" aria-hidden="true" />
                  )}
                  <span className="truncate text-[13px] font-medium text-ink">{g.label}</span>
                </span>
                <span className={`shrink-0 text-xs ${meta.cls}`}>{statusText}</span>
                <span className="w-14 shrink-0 text-right tabular text-xs text-ink-3">{g.durationMs === null ? "" : duration(g.durationMs)}</span>
                <span className="hidden w-28 shrink-0 text-right tabular text-[11px] text-ink-3 @md:inline">{g.startedAt ? timeOfDay(g.startedAt) : ""}</span>
              </button>
              {expanded ? (
                <div id={panelId} className="mt-1 mb-2 ml-2 space-y-1.5">
                  {g.events.map((e, n) => (
                    <EventDetail key={`${e.name}-${n}`} event={e} />
                  ))}
                </div>
              ) : null}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
