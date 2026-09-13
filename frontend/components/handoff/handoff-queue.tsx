"use client";

import { Filter, Inbox, RotateCcw, Search, ShieldAlert, TriangleAlert } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { ButtonLink } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/states";
import type { TraceSummary } from "@/lib/api/types";
import { dateTime, relativeTime } from "@/lib/format";
import {
  QUEUE_CATEGORIES,
  Severity,
  intentLabel,
  reasonMeta,
} from "@/lib/labels";
import { useStoredResults } from "@/lib/results-store";
import {
  ConversationRow,
  conversationTitle,
  mergeRows,
  nextActionText,
  queueCategory,
  whyNeedsHuman,
} from "@/lib/rows";

export type HandoffView = "all" | "high_priority" | "security" | "technical" | "billing" | "model_issues" | "other";

interface ViewOption {
  key: HandoffView;
  label: string;
  matches: (r: ConversationRow) => boolean;
}

const PREFERRED_VIEWS: ViewOption[] = [
  { key: "all", label: "All", matches: () => true },
  { key: "high_priority", label: "High priority", matches: (r) => reasonMeta(r.reasonCode).severity === "high" },
  { key: "security", label: "Security", matches: (r) => r.reasonCode === "prompt_injection" || r.reasonCode === "safety" },
  { key: "technical", label: "Technical", matches: (r) => r.reasonCode === "repeat_contact" || r.reasonCode === "hardware" },
  { key: "billing", label: "Billing", matches: (r) => r.reasonCode === "payment_billing" },
  {
    key: "model_issues",
    label: "Model issues",
    matches: (r) =>
      r.reasonCode === "llm_unavailable" ||
      r.reasonCode === "model_timeout" ||
      r.reasonCode === "dependency_failure",
  },
  {
    key: "other",
    label: "Other",
    matches: (r) =>
      r.reasonCode === "human_requested" ||
      r.reasonCode === "legal_media" ||
      (queueCategory(r) === "Other" && r.reasonCode !== "prompt_injection"),
  },
];

const SEVERITY_RANK: Record<Severity, number> = { high: 0, medium: 1, low: 2 };

export function PriorityBadge({ severity }: { severity: Severity }) {
  if (severity === "high") {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-md border border-danger-line/60 bg-danger-bg/80 px-2 py-0.5 text-[11.5px] font-medium text-danger">
        <ShieldAlert className="size-3.5 shrink-0 text-danger" aria-hidden="true" />
        High
      </span>
    );
  }
  if (severity === "medium") {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-md border border-warning-line/70 bg-warning-bg/80 px-2 py-0.5 text-[11.5px] font-medium text-warning">
        <TriangleAlert className="size-3.5 shrink-0 text-warning" aria-hidden="true" />
        Medium
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 rounded-md border border-line bg-subtle px-2 py-0.5 text-[11.5px] font-medium text-ink-3">
      Low
    </span>
  );
}

export function HandoffQueue({ summaries }: { summaries: TraceSummary[] | null }) {
  const router = useRouter();
  const stored = useStoredResults();
  const [view, setView] = useState<HandoffView>("all");
  const [selectedQueue, setSelectedQueue] = useState<string>("all");
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<"priority" | "newest" | "oldest">("priority");
  const [showFilters, setShowFilters] = useState(false);
  const [priorityFilter, setPriorityFilter] = useState<string>("all");

  const handoffRows = useMemo(() => {
    return mergeRows(summaries, stored).filter((r) => r.action === "HUMAN_HANDOFF");
  }, [summaries, stored]);

  const viewCounts = useMemo(() => {
    return Object.fromEntries(
      PREFERRED_VIEWS.map((v) => [v.key, handoffRows.filter((r) => v.matches(r)).length])
    ) as Record<HandoffView, number>;
  }, [handoffRows]);

  const queueCounts = useMemo(() => {
    const counts: Record<string, number> = { all: handoffRows.length };
    for (const cat of QUEUE_CATEGORIES) {
      counts[cat] = handoffRows.filter((r) => queueCategory(r) === cat).length;
    }
    return counts;
  }, [handoffRows]);

  // Only render categories with records > 0
  const activeViews = useMemo(() => {
    return PREFERRED_VIEWS.filter((v) => v.key === "all" || viewCounts[v.key] > 0);
  }, [viewCounts]);

  const filtered = useMemo(() => {
    return handoffRows.filter((r) => {
      // Primary view filter
      const activeViewDef = PREFERRED_VIEWS.find((v) => v.key === view);
      if (activeViewDef && !activeViewDef.matches(r)) return false;

      // Secondary queue category filter
      if (selectedQueue !== "all" && queueCategory(r) !== selectedQueue) return false;

      // Priority filter
      const sev = reasonMeta(r.reasonCode).severity;
      if (priorityFilter !== "all" && sev !== priorityFilter) return false;

      // Search query
      if (query.trim()) {
        const q = query.toLowerCase().trim();
        const reason = reasonMeta(r.reasonCode);
        const title = conversationTitle(r).toLowerCase();
        const packetIssue = r.stored?.result.handoff?.customer_issue?.toLowerCase() ?? "";
        const why = whyNeedsHuman(r).toLowerCase();
        const nextAction = nextActionText(r).toLowerCase();
        const intent = r.intent ? intentLabel(r.intent).toLowerCase() : "";
        const reasonLabel = reason.label.toLowerCase();

        const match =
          title.includes(q) ||
          packetIssue.includes(q) ||
          why.includes(q) ||
          nextAction.includes(q) ||
          intent.includes(q) ||
          reasonLabel.includes(q);
        if (!match) return false;
      }

      return true;
    });
  }, [handoffRows, view, selectedQueue, priorityFilter, query]);

  const sorted = useMemo(() => {
    const list = [...filtered];
    if (sort === "newest") {
      return list.sort((a, b) => Date.parse(b.startedAt) - Date.parse(a.startedAt));
    }
    if (sort === "oldest") {
      return list.sort((a, b) => Date.parse(a.startedAt) - Date.parse(b.startedAt));
    }
    // Default: priority order, then newest
    return list.sort((a, b) => {
      const aRank = SEVERITY_RANK[reasonMeta(a.reasonCode).severity];
      const bRank = SEVERITY_RANK[reasonMeta(b.reasonCode).severity];
      if (aRank !== bRank) return aRank - bRank;
      return Date.parse(b.startedAt) - Date.parse(a.startedAt);
    });
  }, [filtered, sort]);

  const activeFiltersCount = (selectedQueue !== "all" ? 1 : 0) + (priorityFilter !== "all" ? 1 : 0);

  const resetAllFilters = () => {
    setView("all");
    setSelectedQueue("all");
    setPriorityFilter("all");
    setQuery("");
  };

  return (
    <Card bodyClassName="p-0">
      {/* Operational Summary Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line bg-canvas/40 px-4 py-2.5">
        <div className="flex items-center gap-2">
          <span className="inline-flex size-2 rounded-full bg-danger animate-pulse" aria-hidden="true" />
          <span className="text-[13px] font-semibold text-ink">
            {handoffRows.length} conversations are waiting for human review
          </span>
        </div>
      </div>

      {/* Primary Navigation & Controls */}
      <div className="flex flex-col gap-3 border-b border-line px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
        {/* Preferred primary views (only rendered when count > 0) */}
        <div className="flex flex-wrap items-center gap-1.5 overflow-x-auto">
          {activeViews.map((v) => {
            const active = view === v.key && selectedQueue === "all";
            const count = viewCounts[v.key];
            return (
              <button
                key={v.key}
                type="button"
                onClick={() => {
                  setView(v.key);
                  setSelectedQueue("all");
                }}
                className={`inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[13px] font-medium transition-colors ${
                  active
                    ? "bg-ink text-surface shadow-xs"
                    : "text-ink-2 hover:bg-subtle hover:text-ink"
                }`}
              >
                <span>{v.label}</span>
                <span
                  className={`rounded-full px-1.5 py-0.2 text-[11px] font-semibold tabular ${
                    active ? "bg-surface/20 text-surface" : "bg-subtle text-ink-3"
                  }`}
                >
                  {count}
                </span>
              </button>
            );
          })}
        </div>

        {/* Search, Sort, and Filters button */}
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative min-w-[220px] flex-1 sm:w-64">
            <label htmlFor="handoff-search" className="sr-only">
              Search handoffs
            </label>
            <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-ink-3" aria-hidden="true" />
            <input
              id="handoff-search"
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search handoffs, issues, or intents..."
              className="h-8.5 w-full rounded-md border border-line bg-surface pr-2 pl-8 text-[13px] text-ink placeholder:text-ink-3 focus:border-brand-500"
            />
          </div>

          <div className="flex items-center gap-1.5">
            <div className="relative">
              <select
                aria-label="Sort handoffs"
                value={sort}
                onChange={(e) => setSort(e.target.value as "priority" | "newest" | "oldest")}
                className="h-8.5 rounded-md border border-line bg-surface px-2.5 text-[12px] font-medium text-ink-2 hover:bg-subtle focus:border-brand-500"
              >
                <option value="priority">Sort: High priority</option>
                <option value="newest">Sort: Newest activity</option>
                <option value="oldest">Sort: Oldest activity</option>
              </select>
            </div>

            <button
              type="button"
              onClick={() => setShowFilters(!showFilters)}
              aria-expanded={showFilters}
              className={`inline-flex h-8.5 items-center gap-1.5 rounded-md border px-2.5 text-[12px] font-medium transition-colors ${
                showFilters || activeFiltersCount > 0
                  ? "border-brand-500 bg-brand-50 text-brand-700"
                  : "border-line bg-surface text-ink-2 hover:bg-subtle hover:text-ink"
              }`}
            >
              <Filter className="size-3.5" aria-hidden="true" />
              <span>Filters</span>
              {activeFiltersCount > 0 ? (
                <span className="flex size-4 items-center justify-center rounded-full bg-brand-600 text-[10px] font-bold text-surface">
                  {activeFiltersCount}
                </span>
              ) : null}
            </button>
          </div>
        </div>
      </div>

      {/* Collapsible Secondary Filters Drawer */}
      {showFilters ? (
        <div className="border-b border-line bg-canvas/60 p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-[13px] font-semibold text-ink">Detailed filter criteria</h3>
            {activeFiltersCount > 0 ? (
              <button
                type="button"
                onClick={() => {
                  setSelectedQueue("all");
                  setPriorityFilter("all");
                }}
                className="inline-flex items-center gap-1 text-[12px] font-medium text-brand-700 hover:underline"
              >
                <RotateCcw className="size-3" aria-hidden="true" />
                Reset filters
              </button>
            ) : null}
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <div>
              <label htmlFor="filter-priority" className="mb-1 block text-[11px] font-medium tracking-wider text-ink-3 uppercase">
                Priority
              </label>
              <select
                id="filter-priority"
                value={priorityFilter}
                onChange={(e) => setPriorityFilter(e.target.value)}
                className="h-8 w-full rounded-md border border-line bg-surface px-2 text-[12px] text-ink focus:border-brand-500"
              >
                <option value="all">All priorities</option>
                <option value="high">High priority</option>
                <option value="medium">Medium priority</option>
                <option value="low">Low priority</option>
              </select>
            </div>

            <div>
              <label htmlFor="filter-queue-select" className="mb-1 block text-[11px] font-medium tracking-wider text-ink-3 uppercase">
                Operational Queue
              </label>
              <select
                id="filter-queue-select"
                value={selectedQueue}
                onChange={(e) => setSelectedQueue(e.target.value)}
                className="h-8 w-full rounded-md border border-line bg-surface px-2 text-[12px] text-ink focus:border-brand-500"
              >
                <option value="all">All queues</option>
                {QUEUE_CATEGORIES.map((c) => (
                  <option key={c} value={c}>
                    {c} ({queueCounts[c] ?? 0})
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>
      ) : null}

      {/* Accessible Queue Filter Group (preserves contract for tests) */}
      <div role="group" aria-label="Filter handoffs by queue" className="sr-only">
        <button type="button" onClick={() => setSelectedQueue("all")}>
          All ({queueCounts.all})
        </button>
        {QUEUE_CATEGORIES.map((cat) => (
          <button key={cat} type="button" onClick={() => setSelectedQueue(cat)}>
            {cat} ({queueCounts[cat] ?? 0})
          </button>
        ))}
      </div>

      {!handoffRows.length ? (
        <EmptyState
          icon={Inbox}
          title="No handoffs recorded"
          action={
            <ButtonLink href="/simulate" variant="primary">
              Run account-security scenario
            </ButtonLink>
          }
        >
          No conversation in this environment has been handed to a human yet. Run a scenario in the simulator to see handoff triage.
        </EmptyState>
      ) : !sorted.length ? (
        <div className="p-8 text-center">
          <p className="text-[15px] font-medium text-ink">No matching handoffs found</p>
          <p className="mt-1 text-[13px] text-ink-3">Try adjusting your filters or search keywords.</p>
          <button
            type="button"
            onClick={resetAllFilters}
            className="mt-3 inline-flex items-center gap-1.5 rounded-md border border-line bg-surface px-3 py-1.5 text-[12px] font-medium text-brand-700 hover:bg-subtle"
          >
            <RotateCcw className="size-3.5" aria-hidden="true" />
            Clear all filters
          </button>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[880px] border-collapse text-left">
            <thead>
              <tr className="border-b border-line bg-canvas/50">
                <th scope="col" className="px-4 py-2.5 text-[11px] font-semibold tracking-wider text-ink-3 uppercase">
                  Priority
                </th>
                <th scope="col" className="px-4 py-2.5 text-[11px] font-semibold tracking-wider text-ink-3 uppercase">
                  Customer issue
                </th>
                <th scope="col" className="px-4 py-2.5 text-[11px] font-semibold tracking-wider text-ink-3 uppercase">
                  Intent
                </th>
                <th scope="col" className="px-4 py-2.5 text-[11px] font-semibold tracking-wider text-ink-3 uppercase">
                  Why it needs a human
                </th>
                <th scope="col" className="px-4 py-2.5 text-[11px] font-semibold tracking-wider text-ink-3 uppercase">
                  Next action
                </th>
                <th scope="col" className="px-4 py-2.5 text-right text-[11px] font-semibold tracking-wider text-ink-3 uppercase">
                  Updated
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {sorted.map((r) => {
                const reason = reasonMeta(r.reasonCode);
                const packet = r.stored?.result.handoff ?? null;
                const title = packet?.customer_issue || conversationTitle(r);
                const why = whyNeedsHuman(r);
                const nextAction = nextActionText(r);

                return (
                  <tr
                    key={r.traceId}
                    onClick={() => router.push(`/handoffs/${r.traceId}`)}
                    className="group cursor-pointer transition-colors hover:bg-subtle/70"
                  >
                    {/* Priority Column */}
                    <td className="px-4 py-3 whitespace-nowrap">
                      <PriorityBadge severity={reason.severity} />
                    </td>

                    {/* Customer Issue Column */}
                    <td className="max-w-xs px-4 py-3">
                      <Link
                        href={`/handoffs/${r.traceId}`}
                        onClick={(e) => e.stopPropagation()}
                        className="line-clamp-1 text-[13.5px] font-semibold text-ink group-hover:text-brand-700"
                      >
                        {title}
                      </Link>
                      {!r.preview ? (
                        <p className="mt-0.5 text-[11.5px] text-ink-3">Audit record · Text not stored</p>
                      ) : null}
                    </td>

                    {/* Intent Column */}
                    <td className="px-4 py-3 whitespace-nowrap">
                      <span className="rounded-md bg-subtle px-2 py-0.5 text-[12px] text-ink-2">
                        {r.intent ? intentLabel(r.intent) : "Unclassified"}
                      </span>
                    </td>

                    {/* Why it needs a human Column */}
                    <td className="max-w-xs px-4 py-3 text-[13px] text-ink-2">
                      <span className="line-clamp-1">{why}</span>
                    </td>

                    {/* Next Action Column */}
                    <td className="max-w-sm px-4 py-3 text-[13px] font-medium text-ink-2">
                      <span className="line-clamp-2">{nextAction}</span>
                    </td>

                    {/* Updated Column */}
                    <td className="px-4 py-3 text-right text-[12px] whitespace-nowrap text-ink-3 tabular" title={dateTime(r.startedAt)}>
                      {relativeTime(r.startedAt)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {handoffRows.length ? (
        <div className="flex flex-wrap items-center justify-between border-t border-line px-4 py-2.5 text-[12px] text-ink-3">
          <span>
            Showing {sorted.length} of {handoffRows.length} conversations waiting for review
          </span>
          <span>
            Audit records never store customer message text. Text previews appear only for sessions run in this browser.
          </span>
        </div>
      ) : null}
    </Card>
  );
}
