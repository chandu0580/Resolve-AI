"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { ArrowUpRight, Filter, Layers, RotateCcw } from "lucide-react";
import type { TraceSummary } from "@/lib/api/types";
import { duration, usd } from "@/lib/format";
import { intentLabel, reasonMeta } from "@/lib/labels";
import { liveMetrics } from "@/lib/rows";

interface AnalyticsDashboardProps {
  items: TraceSummary[];
}

const share = (part: number, total: number) => (total ? `${((part / total) * 100).toFixed(1)}%` : "0.0%");

export function AnalyticsDashboard({ items }: AnalyticsDashboardProps) {
  // Filter state
  const [dateRange, setDateRange] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [issueFilter, setIssueFilter] = useState<string>("all");

  // All distinct issues available in raw audit records
  const availableIssues = useMemo(() => {
    const set = new Set<string>();
    for (const t of items) {
      if (t.intent) {
        set.add(intentLabel(t.intent));
      }
    }
    return Array.from(set).sort();
  }, [items]);

  // Max timestamp in data for relative date filtering
  const latestTimestamp = useMemo(() => {
    if (!items.length) return 0;
    const timestamps = items.map((t) => (t.started_at ? Date.parse(t.started_at) : 0)).filter((n) => !isNaN(n) && n > 0);
    return timestamps.length ? Math.max(...timestamps) : 0;
  }, [items]);

  // Filtered traces based on user selections
  const filteredItems = useMemo(() => {
    return items.filter((t) => {
      // 1. Date Range
      if (dateRange !== "all" && t.started_at) {
        const time = Date.parse(t.started_at);
        if (!isNaN(time)) {
          const hoursAgo = (latestTimestamp - time) / (1000 * 60 * 60);
          if (dateRange === "24h" && hoursAgo > 24) return false;
          if (dateRange === "7d" && hoursAgo > 24 * 7) return false;
          if (dateRange === "30d" && hoursAgo > 24 * 30) return false;
        }
      }

      // 2. Status
      if (statusFilter === "auto" && t.final_decision !== "AUTO_HANDLE") return false;
      if (statusFilter === "clarification" && t.final_decision !== "CLARIFICATION_REQUIRED") return false;
      if (statusFilter === "handoff" && t.final_decision !== "HUMAN_HANDOFF") return false;
      if (statusFilter === "failed" && !t.error && t.final_decision) return false;

      // 3. Issue
      if (issueFilter !== "all") {
        const currentIssue = t.intent ? intentLabel(t.intent) : "Other / not a support request";
        if (currentIssue !== issueFilter) return false;
      }

      return true;
    });
  }, [items, dateRange, statusFilter, issueFilter, latestTimestamp]);

  const isFiltered = dateRange !== "all" || statusFilter !== "all" || issueFilter !== "all";

  const handleResetFilters = () => {
    setDateRange("all");
    setStatusFilter("all");
    setIssueFilter("all");
  };

  // Operational metrics calculated on filtered records
  const m = useMemo(() => liveMetrics(filteredItems), [filteredItems]);

  // Outcomes breakdown
  const outcomes = useMemo(() => {
    return [
      { key: "auto", label: "AI resolved", count: m.auto, pct: share(m.auto, m.n), color: "#586651", link: "/conversations" },
      { key: "clarification", label: "Clarification required", count: m.clarification, pct: share(m.clarification, m.n), color: "#D99B26", link: "/conversations" },
      { key: "handoff", label: "Human handoff", count: m.handoff, pct: share(m.handoff, m.n), color: "#687364", link: "/handoffs" },
    ];
  }, [m]);

  // Top Customer Issues
  const topIssues = useMemo(() => {
    const counts = new Map<string, number>();
    for (const t of filteredItems) {
      const label = t.intent ? intentLabel(t.intent) : "Other / not a support request";
      counts.set(label, (counts.get(label) ?? 0) + 1);
    }
    return [...counts.entries()].sort((a, b) => b[1] - a[1]);
  }, [filteredItems]);

  // Why AI Handed Off (handoff reasons)
  const topReasons = useMemo(() => {
    const counts = new Map<string, number>();
    for (const t of filteredItems) {
      if (t.final_decision === "HUMAN_HANDOFF" && t.reason_code) {
        const label = reasonMeta(t.reason_code).label;
        counts.set(label, (counts.get(label) ?? 0) + 1);
      }
    }
    return [...counts.entries()].sort((a, b) => b[1] - a[1]);
  }, [filteredItems]);

  // Resolution Trend by Day (chronological grouping)
  const trendBuckets = useMemo(() => {
    const dayMap = new Map<string, { dateLabel: string; auto: number; clarification: number; handoff: number; total: number; timestamp: number }>();
    for (const t of filteredItems) {
      if (!t.started_at) continue;
      const d = new Date(t.started_at);
      if (isNaN(d.getTime())) continue;
      const dateKey = d.toISOString().slice(0, 10);
      const dateLabel = d.toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
      const current = dayMap.get(dateKey) ?? { dateLabel, auto: 0, clarification: 0, handoff: 0, total: 0, timestamp: d.getTime() };
      if (t.final_decision === "AUTO_HANDLE") current.auto++;
      else if (t.final_decision === "CLARIFICATION_REQUIRED") current.clarification++;
      else if (t.final_decision === "HUMAN_HANDOFF") current.handoff++;
      current.total++;
      dayMap.set(dateKey, current);
    }
    return Array.from(dayMap.entries())
      .sort((a, b) => a[1].timestamp - b[1].timestamp)
      .map(([, v]) => v);
  }, [filteredItems]);

  const maxTrendTotal = useMemo(() => {
    if (!trendBuckets.length) return 1;
    return Math.max(...trendBuckets.map((b) => b.total), 1);
  }, [trendBuckets]);

  // Advanced technical metrics (evidence levels)
  const evidenceLevels = useMemo(() => {
    const counts = new Map<string, number>();
    for (const t of filteredItems) {
      const lvl = t.evidence_level ?? "None / unverified";
      counts.set(lvl, (counts.get(lvl) ?? 0) + 1);
    }
    return [...counts.entries()].sort((a, b) => b[1] - a[1]);
  }, [filteredItems]);

  return (
    <div className="space-y-8">
      {/* 2. COMPACT FILTER ROW */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-line bg-surface p-3 shadow-xs">
        <div className="flex flex-wrap items-center gap-2.5">
          <span className="flex items-center gap-1.5 text-xs font-semibold text-ink uppercase tracking-wider pl-1">
            <Filter className="h-3.5 w-3.5 text-ink-3" />
            Filter
          </span>

          {/* Date range filter */}
          <select
            id="analytics-filter-date"
            aria-label="Filter by date range"
            value={dateRange}
            onChange={(e) => setDateRange(e.target.value)}
            className="rounded-lg border border-line bg-canvas/70 px-2.5 py-1 text-xs font-medium text-ink hover:border-line-strong focus:border-[#586651] focus:outline-none"
          >
            <option value="all">Date: All time</option>
            <option value="24h">Date: Last 24 hours</option>
            <option value="7d">Date: Last 7 days</option>
            <option value="30d">Date: Last 30 days</option>
          </select>

          {/* Conversation status filter */}
          <select
            id="analytics-filter-status"
            aria-label="Filter by conversation status"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="rounded-lg border border-line bg-canvas/70 px-2.5 py-1 text-xs font-medium text-ink hover:border-line-strong focus:border-[#586651] focus:outline-none"
          >
            <option value="all">Status: All statuses</option>
            <option value="auto">Status: AI resolved</option>
            <option value="clarification">Status: Clarification required</option>
            <option value="handoff">Status: Human handoff</option>
            <option value="failed">Status: Failed executions</option>
          </select>

          {/* Issue filter */}
          <select
            id="analytics-filter-issue"
            aria-label="Filter by customer issue"
            value={issueFilter}
            onChange={(e) => setIssueFilter(e.target.value)}
            className="rounded-lg border border-line bg-canvas/70 px-2.5 py-1 text-xs font-medium text-ink hover:border-line-strong focus:border-[#586651] focus:outline-none max-w-56 truncate"
          >
            <option value="all">Issue: All customer issues</option>
            {availableIssues.map((issue) => (
              <option key={issue} value={issue}>
                {issue}
              </option>
            ))}
          </select>

          {isFiltered && (
            <button
              onClick={handleResetFilters}
              className="flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-[#586651] hover:bg-[#586651]/10 transition-colors"
            >
              <RotateCcw className="h-3 w-3" />
              Reset filters
            </button>
          )}
        </div>

        <div className="text-xs text-ink-3">
          Showing <strong className="text-ink">{filteredItems.length}</strong> of {items.length} conversations
        </div>
      </div>

      {/* 3. PRIMARY KPI ROW */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        {/* A. Conversations handled */}
        <div className="rounded-xl border border-line bg-surface p-4 shadow-xs">
          <span className="text-xs font-medium text-ink-3 uppercase tracking-wider">Conversations handled</span>
          <div className="mt-1.5 text-2xl font-bold tracking-tight text-ink">{m.n}</div>
          <p className="mt-0.5 text-xs text-ink-3">Total customer messages</p>
        </div>

        {/* B. AI resolved */}
        <div className="rounded-xl border border-line bg-surface p-4 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-ink-3 uppercase tracking-wider">AI resolved</span>
            <Link href="/conversations" title="View resolved conversations" className="text-ink-3 hover:text-[#586651]">
              <ArrowUpRight className="h-3.5 w-3.5" />
            </Link>
          </div>
          <div className="mt-1.5 text-2xl font-bold tracking-tight text-[#586651]">{share(m.auto, m.n)}</div>
          <p className="mt-0.5 text-xs text-ink-3">
            {m.auto} of {m.n} handled autonomously
          </p>
        </div>

        {/* C. Human handoffs */}
        <div className="rounded-xl border border-line bg-surface p-4 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-ink-3 uppercase tracking-wider">Human handoffs</span>
            <Link href="/handoffs" title="View human handoffs" className="text-ink-3 hover:text-[#586651]">
              <ArrowUpRight className="h-3.5 w-3.5" />
            </Link>
          </div>
          <div className="mt-1.5 text-2xl font-bold tracking-tight text-ink">{share(m.handoff, m.n)}</div>
          <p className="mt-0.5 text-xs text-ink-3">
            {m.handoff} of {m.n} escalated to human
          </p>
        </div>

        {/* D. Failed executions */}
        <div className="rounded-xl border border-line bg-surface p-4 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-ink-3 uppercase tracking-wider">Failed executions</span>
            {m.failed > 0 ? (
              <Link href="/traces" title="View audit log" className="text-danger hover:underline">
                <ArrowUpRight className="h-3.5 w-3.5" />
              </Link>
            ) : null}
          </div>
          <div className={`mt-1.5 text-2xl font-bold tracking-tight ${m.failed > 0 ? "text-danger" : "text-ink"}`}>
            {m.failed}
          </div>
          <p className="mt-0.5 text-xs text-ink-3">{m.failed > 0 ? "Inspect in audit log" : "Zero system errors"}</p>
        </div>

        {/* E. Median response time */}
        <div className="rounded-xl border border-line bg-surface p-4 shadow-xs">
          <span className="text-xs font-medium text-ink-3 uppercase tracking-wider">Median response time</span>
          <div className="mt-1.5 text-2xl font-bold tracking-tight text-ink">
            {m.medianLatencyMs === null ? "n/a" : duration(m.medianLatencyMs)}
          </div>
          <p className="mt-0.5 text-xs text-ink-3">Typical reply turnaround</p>
        </div>

        {/* F. P95 response time */}
        <div className="rounded-xl border border-line bg-surface p-4 shadow-xs">
          <span className="text-xs font-medium text-ink-3 uppercase tracking-wider">P95 response time</span>
          <div className="mt-1.5 text-2xl font-bold tracking-tight text-ink">
            {m.p95LatencyMs === null ? "n/a" : duration(m.p95LatencyMs)}
          </div>
          <p className="mt-0.5 text-xs text-ink-3">95% of customer messages</p>
        </div>
      </div>

      {/* OPERATIONAL VISUALIZATION SECTIONS */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* 4. AI RESOLUTION TREND */}
        <div className="rounded-xl border border-line bg-surface p-5 shadow-xs space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h2 className="text-sm font-semibold text-ink">AI resolution trend</h2>
              <p className="text-xs text-ink-3">Volume distribution across recorded dates</p>
            </div>
            <div className="flex items-center gap-3 text-xs">
              <span className="flex items-center gap-1 text-ink-2">
                <span className="h-2 w-2 rounded-full bg-[#586651]" />
                AI resolved
              </span>
              <span className="flex items-center gap-1 text-ink-2">
                <span className="h-2 w-2 rounded-full bg-[#D99B26]" />
                Clarification
              </span>
              <span className="flex items-center gap-1 text-ink-2">
                <span className="h-2 w-2 rounded-full bg-[#687364]" />
                Human handoff
              </span>
            </div>
          </div>

          {trendBuckets.length >= 2 ? (
            <div className="pt-2">
              <div className="flex h-44 items-end gap-3 border-b border-line pb-2">
                {trendBuckets.map((bucket) => {
                  const autoH = (bucket.auto / maxTrendTotal) * 100;
                  const clarH = (bucket.clarification / maxTrendTotal) * 100;
                  const handH = (bucket.handoff / maxTrendTotal) * 100;

                  return (
                    <div key={bucket.dateLabel} className="group relative flex flex-1 flex-col items-center h-full justify-end">
                      {/* Tooltip on hover */}
                      <div className="pointer-events-none absolute -top-12 z-10 hidden rounded bg-ink px-2 py-1 text-[11px] text-white shadow-md group-hover:block whitespace-nowrap">
                        <span className="font-semibold">{bucket.dateLabel}</span>: {bucket.total} total ({bucket.auto} AI, {bucket.clarification} Clarify, {bucket.handoff} Handoff)
                      </div>

                      {/* Stacked bar */}
                      <div className="w-full max-w-12 flex flex-col justify-end overflow-hidden rounded-t-sm">
                        {handH > 0 && <div style={{ height: `${handH}%` }} className="bg-[#687364] w-full" />}
                        {clarH > 0 && <div style={{ height: `${clarH}%` }} className="bg-[#D99B26] w-full" />}
                        {autoH > 0 && <div style={{ height: `${autoH}%` }} className="bg-[#586651] w-full" />}
                      </div>
                    </div>
                  );
                })}
              </div>
              <div className="flex gap-3 pt-2 text-center text-xs text-ink-3">
                {trendBuckets.map((b) => (
                  <span key={b.dateLabel} className="flex-1 truncate">
                    {b.dateLabel} ({b.total})
                  </span>
                ))}
              </div>
            </div>
          ) : (
            <div className="rounded-lg border border-line bg-canvas/50 p-6 text-center">
              <Layers className="mx-auto h-6 w-6 text-ink-3 mb-2" />
              <p className="text-xs font-semibold text-ink">Limited time-series history</p>
              <p className="text-xs text-ink-3 mt-1 max-w-md mx-auto">
                {m.n} conversation{m.n === 1 ? "" : "s"} recorded across {trendBuckets.length} time interval. Full trend visualization renders automatically as conversations span multiple calendar days.
              </p>
              {trendBuckets.length === 1 && (
                <div className="mt-4 inline-flex items-center gap-4 rounded-md border border-line bg-surface px-4 py-2 text-xs">
                  <span className="font-semibold text-ink">{trendBuckets[0].dateLabel}</span>
                  <span className="text-[#586651]">{trendBuckets[0].auto} AI resolved</span>
                  <span className="text-[#D99B26]">{trendBuckets[0].clarification} Clarifications</span>
                  <span className="text-[#687364]">{trendBuckets[0].handoff} Handoffs</span>
                </div>
              )}
            </div>
          )}
        </div>

        {/* 5. SUPPORT OUTCOMES */}
        <div className="rounded-xl border border-line bg-surface p-5 shadow-xs space-y-4">
          <div>
            <h2 className="text-sm font-semibold text-ink">Support outcomes</h2>
            <p className="text-xs text-ink-3">Overall breakdown between autonomous resolution, clarification, and handoff</p>
          </div>

          {/* Segmented horizontal distribution bar */}
          <div className="h-3.5 w-full overflow-hidden rounded-full bg-canvas flex shadow-inner">
            {m.n > 0 ? (
              outcomes.map((o) => (
                <div
                  key={o.key}
                  style={{ width: `${(o.count / m.n) * 100}%`, backgroundColor: o.color }}
                  title={`${o.label}: ${o.count} (${o.pct})`}
                  className="h-full transition-all"
                />
              ))
            ) : (
              <div className="h-full w-full bg-canvas" />
            )}
          </div>

          {/* Outcome metric columns */}
          <div className="grid grid-cols-3 gap-3 pt-2">
            {outcomes.map((o) => (
              <div key={o.key} className="rounded-lg border border-line bg-canvas/50 p-3 flex flex-col justify-between">
                <div>
                  <div className="flex items-center gap-1.5 text-xs font-semibold text-ink">
                    <span className="h-2 w-2 rounded-full shrink-0" style={{ backgroundColor: o.color }} />
                    <span className="truncate">{o.label}</span>
                  </div>
                  <div className="mt-2 text-xl font-bold tracking-tight text-ink">{o.pct}</div>
                  <p className="text-xs text-ink-3 mt-0.5">{o.count} conversations</p>
                </div>
                <Link
                  href={o.link}
                  className="mt-3 inline-flex items-center gap-1 text-[11px] font-medium text-[#586651] hover:underline"
                >
                  View cases <ArrowUpRight className="h-3 w-3" />
                </Link>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* SECOND OPERATIONAL ROW: REASONS & ISSUES */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* 6. WHY AI HANDED OFF */}
        <div className="rounded-xl border border-line bg-surface p-5 shadow-xs space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold text-ink">Why AI handed off</h2>
              <p className="text-xs text-ink-3">Root causes behind human escalation in this environment</p>
            </div>
            <Link href="/handoffs" className="text-xs font-medium text-[#586651] hover:underline flex items-center gap-1">
              All handoffs <ArrowUpRight className="h-3 w-3" />
            </Link>
          </div>

          {topReasons.length > 0 ? (
            <div className="divide-y divide-line">
              {topReasons.map(([reason, count]) => {
                const maxCount = topReasons[0][1] || 1;
                return (
                  <Link
                    key={reason}
                    href="/handoffs"
                    className="group flex items-center justify-between py-2.5 hover:bg-canvas/50 px-1 rounded transition-colors"
                  >
                    <div className="min-w-0 flex-1 pr-4">
                      <div className="flex items-center justify-between text-xs mb-1">
                        <span className="font-semibold text-ink group-hover:text-[#586651] transition-colors truncate">
                          {reason}
                        </span>
                        <span className="font-medium text-ink tabular pl-2">{count}</span>
                      </div>
                      <div className="h-1.5 w-full rounded-full bg-canvas overflow-hidden">
                        <div
                          className="h-full rounded-full bg-[#687364]"
                          style={{ width: `${(count / maxCount) * 100}%` }}
                        />
                      </div>
                    </div>
                    <span className="text-xs text-ink-3 tabular w-12 text-right shrink-0">
                      {share(count, m.handoff)}
                    </span>
                  </Link>
                );
              })}
            </div>
          ) : (
            <p className="text-xs text-ink-3 py-6 text-center">No human handoffs recorded in this filter view.</p>
          )}
        </div>

        {/* 7. TOP CUSTOMER ISSUES */}
        <div className="rounded-xl border border-line bg-surface p-5 shadow-xs space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold text-ink">Top customer issues</h2>
              <p className="text-xs text-ink-3">Customer contact volume grouped by topic</p>
            </div>
            <Link href="/conversations" className="text-xs font-medium text-[#586651] hover:underline flex items-center gap-1">
              View conversations <ArrowUpRight className="h-3 w-3" />
            </Link>
          </div>

          {topIssues.length > 0 ? (
            <div className="divide-y divide-line">
              {topIssues.map(([issue, count]) => {
                const maxCount = topIssues[0][1] || 1;
                return (
                  <Link
                    key={issue}
                    href="/conversations"
                    className="group flex items-center justify-between py-2.5 hover:bg-canvas/50 px-1 rounded transition-colors"
                  >
                    <div className="min-w-0 flex-1 pr-4">
                      <div className="flex items-center justify-between text-xs mb-1">
                        <span className="font-semibold text-ink group-hover:text-[#586651] transition-colors truncate">
                          {issue}
                        </span>
                        <span className="font-medium text-ink tabular pl-2">{count}</span>
                      </div>
                      <div className="h-1.5 w-full rounded-full bg-canvas overflow-hidden">
                        <div
                          className="h-full rounded-full bg-[#586651]"
                          style={{ width: `${(count / maxCount) * 100}%` }}
                        />
                      </div>
                    </div>
                    <span className="text-xs text-ink-3 tabular w-12 text-right shrink-0">
                      {share(count, m.n)}
                    </span>
                  </Link>
                );
              })}
            </div>
          ) : (
            <p className="text-xs text-ink-3 py-6 text-center">No customer issues recorded in this filter view.</p>
          )}
        </div>
      </div>

      {/* 8. RESPONSE PERFORMANCE */}
      <div className="rounded-xl border border-line bg-surface p-5 shadow-xs space-y-3">
        <div>
          <h2 className="text-sm font-semibold text-ink">Response performance</h2>
          <p className="text-xs text-ink-3">End-to-end reply latency measured across live customer requests</p>
        </div>

        <div className="grid grid-cols-1 divide-y divide-line sm:grid-cols-3 sm:divide-y-0 sm:divide-x border-t border-line pt-3">
          <div className="py-2 sm:px-4 sm:first:pl-0">
            <span className="text-xs font-medium text-ink-3 uppercase tracking-wider">Median response time</span>
            <div className="mt-1 text-2xl font-bold text-ink">
              {m.medianLatencyMs === null ? "n/a" : duration(m.medianLatencyMs)}
            </div>
            <p className="text-xs text-ink-3 mt-0.5">Typical customer wait time</p>
          </div>

          <div className="py-2 sm:px-4">
            <span className="text-xs font-medium text-ink-3 uppercase tracking-wider">P95 response time</span>
            <div className="mt-1 text-2xl font-bold text-ink">
              {m.p95LatencyMs === null ? "n/a" : duration(m.p95LatencyMs)}
            </div>
            <p className="text-xs text-ink-3 mt-0.5">High-percentile latency ceiling</p>
          </div>

          <div className="py-2 sm:px-4 sm:last:pr-0">
            <span className="text-xs font-medium text-ink-3 uppercase tracking-wider">Execution success rate</span>
            <div className="mt-1 text-2xl font-bold text-emerald-700">
              {m.n > 0 ? share(m.n - m.failed, m.n) : "100%"}
            </div>
            <p className="text-xs text-ink-3 mt-0.5">Requests completed without failure</p>
          </div>
        </div>
      </div>

      {/* 10. ADVANCED TECHNICAL DETAILS (COLLAPSED BY DEFAULT) */}
      <div className="border-t border-line pt-4">
        <details className="group rounded-xl border border-line bg-surface p-5 shadow-xs">
          <summary className="cursor-pointer list-none flex items-center justify-between font-semibold text-ink hover:text-[#586651] select-none">
            <div className="flex items-center gap-2.5">
              <span className="text-sm font-semibold text-ink">Advanced</span>
              <span className="rounded-full bg-canvas border border-line px-2 py-0.5 text-[11px] font-normal text-ink-3">
                Model calls, list-price inference estimates & audit references
              </span>
            </div>
            <span className="text-xs text-ink-3 font-medium group-open:rotate-180 transition-transform">▼</span>
          </summary>

          <div className="mt-5 space-y-6 border-t border-line pt-5">
            <div className="grid gap-4 sm:grid-cols-3">
              <div className="rounded-lg border border-line bg-canvas/50 p-3">
                <span className="text-[11px] font-medium text-ink-3 uppercase">Model calls</span>
                <div className="mt-1 text-xl font-bold text-ink">{m.modelCalls}</div>
                <p className="text-[11px] text-ink-3 mt-0.5">
                  {m.n ? `${(m.modelCalls / m.n).toFixed(2)} per conversation` : "0 per conversation"}
                </p>
              </div>

              <div className="rounded-lg border border-line bg-canvas/50 p-3">
                <span className="text-[11px] font-medium text-ink-3 uppercase">Estimated inference cost</span>
                <div className="mt-1 text-xl font-bold text-ink">
                  {m.estimatedCostUsd === null ? "n/a" : usd(m.estimatedCostUsd)}
                </div>
                <p className="text-[11px] text-ink-3 mt-0.5">List price estimate across recorded traces</p>
              </div>

              <div className="rounded-lg border border-line bg-canvas/50 p-3">
                <span className="text-[11px] font-medium text-ink-3 uppercase">Mean latency</span>
                <div className="mt-1 text-xl font-bold text-ink">
                  {m.meanLatencyMs === null ? "n/a" : duration(m.meanLatencyMs)}
                </div>
                <p className="text-[11px] text-ink-3 mt-0.5">Average overall processing time</p>
              </div>
            </div>

            {/* Evidence Available breakdown table */}
            <div>
              <h3 className="text-xs font-semibold text-ink uppercase tracking-wider mb-2">Evidence levels recorded</h3>
              <div className="rounded-lg border border-line overflow-hidden">
                <table className="w-full text-left text-xs">
                  <thead className="bg-canvas border-b border-line text-ink-3 uppercase font-semibold">
                    <tr>
                      <th className="py-2 px-3">Level</th>
                      <th className="py-2 px-3">Share</th>
                      <th className="py-2 px-3 text-right">Count</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line">
                    {evidenceLevels.map(([lvl, n]) => (
                      <tr key={lvl} className="hover:bg-canvas/30">
                        <td className="py-2 px-3 font-medium text-ink">{lvl}</td>
                        <td className="py-2 px-3 text-ink-3 tabular">{share(n, m.n)}</td>
                        <td className="py-2 px-3 text-right font-semibold text-ink tabular">{n}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="flex justify-between items-center text-xs text-ink-3 pt-2">
              <span>Environment: Local process deployment with live memory logging</span>
              <Link href="/traces" className="text-[#586651] font-medium hover:underline flex items-center gap-1">
                View complete audit log in Traces <ArrowUpRight className="h-3 w-3" />
              </Link>
            </div>
          </div>
        </details>
      </div>

      {/* 11. DATA INTEGRITY DISCLOSURE */}
      <p className="text-xs text-ink-3 text-center border-t border-line pt-4">
        Counted from the most recent {items.length} live audit records. This environment runs a single local process, so figures describe local operational activity and test sessions rather than commercial production load.
      </p>
    </div>
  );
}
