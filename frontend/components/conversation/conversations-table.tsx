"use client";

import {
  CircleCheck,
  Filter,
  MessageCircleQuestionMark,
  MessagesSquare,
  RotateCcw,
  Search,
  UserRound,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { ButtonLink } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/states";
import type { Action, TraceSummary } from "@/lib/api/types";
import { dateTime, relativeTime } from "@/lib/format";
import { INTENT_LABELS, intentLabel } from "@/lib/labels";
import { useStoredResults } from "@/lib/results-store";
import {
  PRIMARY_FILTERS,
  RowFilter,
  conversationSubtitle,
  conversationTitle,
  humanReason,
  isHighRisk,
  matchesFilter,
  matchesQuery,
  mergeRows,
  parseRowFilter,
} from "@/lib/rows";

function syncUrl(filter: RowFilter, query: string) {
  const params = new URLSearchParams(window.location.search);
  if (filter === "all") params.delete("filter");
  else params.set("filter", filter);
  if (query) params.set("q", query);
  else params.delete("q");
  const qs = params.toString();
  window.history.replaceState(null, "", `${window.location.pathname}${qs ? `?${qs}` : ""}`);
}

const SENSITIVE_SET = new Set(["safety", "account_access", "payment_billing", "private_info", "legal_media", "prompt_injection", "abusive_threatening"]);

type SortOption = "newest" | "oldest" | "needs_attention";

interface AdvancedFilters {
  decision: string;
  intent: string;
  risk: string;
  evidence: string;
  confidence: string;
}

const INITIAL_ADVANCED: AdvancedFilters = {
  decision: "all",
  intent: "all",
  risk: "all",
  evidence: "all",
  confidence: "all",
};

export function DecisionBadge({ action }: { action: Action | null }) {
  if (action === "AUTO_HANDLE") {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-md border border-brand-100 bg-brand-50 px-2.5 py-1 text-[12px] font-medium text-brand-700">
        <CircleCheck className="size-3.5 shrink-0 text-brand-600" aria-hidden="true" />
        Auto-handled
      </span>
    );
  }
  if (action === "CLARIFICATION_REQUIRED") {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-md border border-warning-line/70 bg-warning-bg/80 px-2.5 py-1 text-[12px] font-medium text-warning">
        <MessageCircleQuestionMark className="size-3.5 shrink-0 text-warning" aria-hidden="true" />
        Needs clarification
      </span>
    );
  }
  if (action === "HUMAN_HANDOFF") {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-md border border-danger-line/60 bg-danger-bg/80 px-2.5 py-1 text-[12px] font-medium text-danger">
        <UserRound className="size-3.5 shrink-0 text-danger" aria-hidden="true" />
        Human handoff
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 rounded-md border border-line bg-subtle px-2.5 py-1 text-[12px] font-medium text-ink-3">
      Failed
    </span>
  );
}

export function ConversationsTable({
  summaries,
  initialQuery = "",
  initialFilter = "all",
}: {
  summaries: TraceSummary[] | null;
  initialQuery?: string;
  initialFilter?: string;
}) {
  const router = useRouter();
  const stored = useStoredResults();
  const [filter, setFilter] = useState<RowFilter>(parseRowFilter(initialFilter));
  const [query, setQuery] = useState(initialQuery);
  const [sort, setSort] = useState<SortOption>("newest");
  const [showFilters, setShowFilters] = useState(false);
  const [advanced, setAdvanced] = useState<AdvancedFilters>(INITIAL_ADVANCED);

  const rows = useMemo(() => mergeRows(summaries, stored), [summaries, stored]);

  const counts = useMemo(
    () =>
      Object.fromEntries(
        PRIMARY_FILTERS.map((f) => [f.key, rows.filter((r) => matchesFilter(r, f.key)).length])
      ) as Record<RowFilter, number>,
    [rows]
  );

  const activeAdvancedCount = useMemo(() => {
    let n = 0;
    if (advanced.decision !== "all") n++;
    if (advanced.intent !== "all") n++;
    if (advanced.risk !== "all") n++;
    if (advanced.evidence !== "all") n++;
    if (advanced.confidence !== "all") n++;
    return n;
  }, [advanced]);

  const filtered = useMemo(() => {
    return rows.filter((r) => {
      if (!matchesFilter(r, filter)) return false;
      if (!matchesQuery(r, query)) return false;

      // Advanced filters
      if (advanced.decision !== "all" && r.action !== advanced.decision) return false;
      if (advanced.intent !== "all" && r.intent !== advanced.intent) return false;
      if (advanced.risk === "sensitive" && (!r.reasonCode || !SENSITIVE_SET.has(r.reasonCode))) return false;
      if (advanced.risk === "high_risk" && !isHighRisk(r)) return false;
      if (advanced.risk === "normal" && (isHighRisk(r) || (r.reasonCode && SENSITIVE_SET.has(r.reasonCode)))) return false;
      if (advanced.evidence === "sufficient" && r.evidenceSufficient !== true) return false;
      if (advanced.evidence === "insufficient" && r.evidenceSufficient !== false) return false;
      if (advanced.confidence === "high" && r.band !== "HIGH" && (r.confidence === null || r.confidence < 0.8)) return false;
      if (advanced.confidence === "medium" && r.band !== "MEDIUM" && (r.confidence === null || r.confidence < 0.6 || r.confidence >= 0.8)) return false;
      if (advanced.confidence === "low" && r.band !== "LOW" && (r.confidence === null || r.confidence >= 0.6)) return false;

      return true;
    });
  }, [rows, filter, query, advanced]);

  const sorted = useMemo(() => {
    const list = [...filtered];
    if (sort === "oldest") {
      return list.sort((a, b) => Date.parse(a.startedAt) - Date.parse(b.startedAt));
    }
    if (sort === "needs_attention") {
      return list.sort((a, b) => {
        const aAttention = a.action === "HUMAN_HANDOFF" ? 2 : a.action === "CLARIFICATION_REQUIRED" ? 1 : 0;
        const bAttention = b.action === "HUMAN_HANDOFF" ? 2 : b.action === "CLARIFICATION_REQUIRED" ? 1 : 0;
        if (bAttention !== aAttention) return bAttention - aAttention;
        return Date.parse(b.startedAt) - Date.parse(a.startedAt);
      });
    }
    return list.sort((a, b) => Date.parse(b.startedAt) - Date.parse(a.startedAt));
  }, [filtered, sort]);

  const resetAllFilters = () => {
    setFilter("all");
    setQuery("");
    setAdvanced(INITIAL_ADVANCED);
    syncUrl("all", "");
  };

  return (
    <Card bodyClassName="p-0">
      {/* Primary operational filter tabs and search controls */}
      <div className="flex flex-col gap-3 border-b border-line px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap items-center gap-1.5 overflow-x-auto">
          {PRIMARY_FILTERS.map(({ key, label }) => {
            const active = filter === key;
            const count = counts[key] ?? 0;
            return (
              <button
                key={key}
                type="button"
                onClick={() => {
                  setFilter(key);
                  syncUrl(key, query);
                }}
                className={`inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[13px] font-medium transition-colors ${
                  active
                    ? "bg-ink text-surface shadow-xs"
                    : "text-ink-2 hover:bg-subtle hover:text-ink"
                }`}
              >
                <span>{label}</span>
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

        <div className="flex flex-wrap items-center gap-2">
          <div className="relative min-w-[220px] flex-1 sm:w-64">
            <label htmlFor="conversation-search" className="sr-only">
              Search conversations
            </label>
            <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-ink-3" aria-hidden="true" />
            <input
              id="conversation-search"
              type="search"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                syncUrl(filter, e.target.value);
              }}
              placeholder="Search conversations, intents, or customers..."
              className="h-8.5 w-full rounded-md border border-line bg-surface pr-2 pl-8 text-[13px] text-ink placeholder:text-ink-3 focus:border-brand-500"
            />
          </div>

          <div className="flex items-center gap-1.5">
            {/* Sort control */}
            <div className="relative">
              <select
                aria-label="Sort conversations"
                value={sort}
                onChange={(e) => setSort(e.target.value as SortOption)}
                className="h-8.5 rounded-md border border-line bg-surface px-2.5 text-[12px] font-medium text-ink-2 hover:bg-subtle focus:border-brand-500"
              >
                <option value="newest">Sort: Newest activity</option>
                <option value="oldest">Sort: Oldest activity</option>
                <option value="needs_attention">Sort: Needs attention</option>
              </select>
            </div>

            {/* Subtle Filters toggle button */}
            <button
              type="button"
              onClick={() => setShowFilters(!showFilters)}
              aria-expanded={showFilters}
              className={`inline-flex h-8.5 items-center gap-1.5 rounded-md border px-2.5 text-[12px] font-medium transition-colors ${
                showFilters || activeAdvancedCount > 0
                  ? "border-brand-500 bg-brand-50 text-brand-700"
                  : "border-line bg-surface text-ink-2 hover:bg-subtle hover:text-ink"
              }`}
            >
              <Filter className="size-3.5" aria-hidden="true" />
              <span>Filters</span>
              {activeAdvancedCount > 0 ? (
                <span className="flex size-4 items-center justify-center rounded-full bg-brand-600 text-[10px] font-bold text-surface">
                  {activeAdvancedCount}
                </span>
              ) : null}
            </button>
          </div>
        </div>
      </div>

      {/* Collapsible Advanced Filters Drawer */}
      {showFilters ? (
        <div className="border-b border-line bg-canvas/60 p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-[13px] font-semibold text-ink">Detailed filter criteria</h3>
            {activeAdvancedCount > 0 ? (
              <button
                type="button"
                onClick={() => setAdvanced(INITIAL_ADVANCED)}
                className="inline-flex items-center gap-1 text-[12px] font-medium text-brand-700 hover:underline"
              >
                <RotateCcw className="size-3" aria-hidden="true" />
                Reset filters
              </button>
            ) : null}
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            {/* Decision */}
            <div>
              <label htmlFor="filter-decision" className="mb-1 block text-[11px] font-medium text-ink-3 uppercase tracking-wider">
                Decision
              </label>
              <select
                id="filter-decision"
                value={advanced.decision}
                onChange={(e) => setAdvanced((prev) => ({ ...prev, decision: e.target.value }))}
                className="h-8 w-full rounded-md border border-line bg-surface px-2 text-[12px] text-ink focus:border-brand-500"
              >
                <option value="all">All decisions</option>
                <option value="AUTO_HANDLE">Auto-handled</option>
                <option value="CLARIFICATION_REQUIRED">Needs clarification</option>
                <option value="HUMAN_HANDOFF">Human handoff</option>
              </select>
            </div>

            {/* Intent */}
            <div>
              <label htmlFor="filter-intent" className="mb-1 block text-[11px] font-medium text-ink-3 uppercase tracking-wider">
                Intent
              </label>
              <select
                id="filter-intent"
                value={advanced.intent}
                onChange={(e) => setAdvanced((prev) => ({ ...prev, intent: e.target.value }))}
                className="h-8 w-full rounded-md border border-line bg-surface px-2 text-[12px] text-ink focus:border-brand-500"
              >
                <option value="all">All intents</option>
                {Object.entries(INTENT_LABELS).map(([code, name]) => (
                  <option key={code} value={code}>
                    {name}
                  </option>
                ))}
              </select>
            </div>

            {/* Risk */}
            <div>
              <label htmlFor="filter-risk" className="mb-1 block text-[11px] font-medium text-ink-3 uppercase tracking-wider">
                Risk
              </label>
              <select
                id="filter-risk"
                value={advanced.risk}
                onChange={(e) => setAdvanced((prev) => ({ ...prev, risk: e.target.value }))}
                className="h-8 w-full rounded-md border border-line bg-surface px-2 text-[12px] text-ink focus:border-brand-500"
              >
                <option value="all">All risk levels</option>
                <option value="sensitive">Sensitive requests</option>
                <option value="high_risk">High risk</option>
                <option value="normal">Normal</option>
              </select>
            </div>

            {/* Evidence */}
            <div>
              <label htmlFor="filter-evidence" className="mb-1 block text-[11px] font-medium text-ink-3 uppercase tracking-wider">
                Evidence
              </label>
              <select
                id="filter-evidence"
                value={advanced.evidence}
                onChange={(e) => setAdvanced((prev) => ({ ...prev, evidence: e.target.value }))}
                className="h-8 w-full rounded-md border border-line bg-surface px-2 text-[12px] text-ink focus:border-brand-500"
              >
                <option value="all">All evidence levels</option>
                <option value="sufficient">Sufficient</option>
                <option value="insufficient">Insufficient</option>
              </select>
            </div>

            {/* Confidence */}
            <div>
              <label htmlFor="filter-confidence" className="mb-1 block text-[11px] font-medium text-ink-3 uppercase tracking-wider">
                Confidence
              </label>
              <select
                id="filter-confidence"
                value={advanced.confidence}
                onChange={(e) => setAdvanced((prev) => ({ ...prev, confidence: e.target.value }))}
                className="h-8 w-full rounded-md border border-line bg-surface px-2 text-[12px] text-ink focus:border-brand-500"
              >
                <option value="all">All confidence bands</option>
                <option value="high">High band</option>
                <option value="medium">Medium band</option>
                <option value="low">Low band</option>
              </select>
            </div>
          </div>
        </div>
      ) : null}

      {!rows.length ? (
        <EmptyState
          icon={MessagesSquare}
          title="No conversations yet"
          action={
            <ButtonLink href="/simulate" variant="primary">
              Run a demo scenario
            </ButtonLink>
          }
        >
          The API has not recorded any conversations in this environment. Every conversation run through the simulator appears here.
        </EmptyState>
      ) : !sorted.length ? (
        <div className="p-8 text-center">
          <p className="text-[15px] font-medium text-ink">No matching conversations found</p>
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
          <table className="w-full min-w-[760px] border-collapse text-left">
            <thead>
              <tr className="border-b border-line bg-canvas/50">
                <th scope="col" className="px-4 py-2.5 text-[11px] font-semibold tracking-wider text-ink-3 uppercase">
                  Conversation
                </th>
                <th scope="col" className="px-4 py-2.5 text-[11px] font-semibold tracking-wider text-ink-3 uppercase">
                  Intent
                </th>
                <th scope="col" className="px-4 py-2.5 text-[11px] font-semibold tracking-wider text-ink-3 uppercase">
                  Decision
                </th>
                <th scope="col" className="px-4 py-2.5 text-[11px] font-semibold tracking-wider text-ink-3 uppercase">
                  Reason
                </th>
                <th scope="col" className="px-4 py-2.5 text-right text-[11px] font-semibold tracking-wider text-ink-3 uppercase">
                  Updated
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {sorted.map((r) => {
                const title = conversationTitle(r);
                const subtitle = conversationSubtitle(r);
                const reason = humanReason(r);
                return (
                  <tr
                    key={r.traceId}
                    onClick={() => router.push(`/conversations/${r.traceId}`)}
                    className="group cursor-pointer transition-colors hover:bg-subtle/70"
                  >
                    {/* Conversation Column */}
                    <td className="max-w-md px-4 py-3">
                      <Link
                        href={`/conversations/${r.traceId}`}
                        onClick={(e) => e.stopPropagation()}
                        className="line-clamp-1 text-[13.5px] font-semibold text-ink group-hover:text-brand-700"
                      >
                        {title}
                      </Link>
                      <p className="mt-0.5 line-clamp-1 text-[12px] text-ink-3">{subtitle}</p>
                    </td>

                    {/* Intent Column */}
                    <td className="px-4 py-3 whitespace-nowrap">
                      <span className="rounded-md bg-subtle px-2 py-0.5 text-[12px] text-ink-2">
                        {r.intent ? intentLabel(r.intent) : "Unclassified"}
                      </span>
                    </td>

                    {/* Decision Column */}
                    <td className="px-4 py-3 whitespace-nowrap">
                      <DecisionBadge action={r.action} />
                    </td>

                    {/* Reason Column */}
                    <td className="max-w-xs px-4 py-3 text-[13px] text-ink-2">
                      <span className="line-clamp-1">{reason}</span>
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

      {rows.length ? (
        <div className="flex flex-wrap items-center justify-between border-t border-line px-4 py-2.5 text-[12px] text-ink-3">
          <span>
            Showing {sorted.length} of {rows.length} conversations
          </span>
          <span>Audit records never store customer message text. Text previews appear only for sessions run in this browser.</span>
        </div>
      ) : null}
    </Card>
  );
}
