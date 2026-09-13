"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Bot, ChevronRight, Search } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/states";
import type { TraceSummary } from "@/lib/api/types";
import { dateTime, shortId } from "@/lib/format";
export {
  conversationTitle,
  decisionDisplay,
  formatAuditReason,
  formatEvidenceLabel,
  humanInvolvement,
} from "./audit-log-helpers";

interface AuditLogViewProps {
  initialItems: TraceSummary[];
  currentAction: string;
}

const FILTERS = [
  { key: "", label: "All" },
  { key: "AUTO_HANDLE", label: "Auto-handled" },
  { key: "CLARIFICATION_REQUIRED", label: "Needs clarification" },
  { key: "HUMAN_HANDOFF", label: "Human handoff" },
];

import {
  conversationTitle,
  decisionDisplay,
  formatAuditReason,
  formatEvidenceLabel,
  humanInvolvement,
} from "./audit-log-helpers";

export function AuditLogView({ initialItems, currentAction }: AuditLogViewProps) {
  const router = useRouter();
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedAction, setSelectedAction] = useState(currentAction);

  // Calculate real activity counts from the actual audit dataset
  const counts = useMemo(() => {
    let auto = 0;
    let clarification = 0;
    let handoff = 0;
    for (const item of initialItems) {
      if (item.final_decision === "AUTO_HANDLE") auto++;
      else if (item.final_decision === "CLARIFICATION_REQUIRED") clarification++;
      else if (item.final_decision === "HUMAN_HANDOFF") handoff++;
    }
    return { auto, clarification, handoff };
  }, [initialItems]);

  // Client-side filtering for fast, responsive operations
  const filteredItems = useMemo(() => {
    return initialItems.filter((t) => {
      if (selectedAction && t.final_decision !== selectedAction) return false;
      if (!searchQuery.trim()) return true;

      const q = searchQuery.toLowerCase();
      const title = conversationTitle(t.intent, t.reason_code).toLowerCase();
      const reason = formatAuditReason(t.final_decision, t.reason_code).toLowerCase();
      const intent = (t.intent ?? "").toLowerCase();
      const traceIdShort = shortId(t.trace_id, 8).toLowerCase();

      return title.includes(q) || reason.includes(q) || intent.includes(q) || traceIdShort.includes(q);
    });
  }, [initialItems, selectedAction, searchQuery]);

  return (
    <div className="space-y-4">
      {/* Top Summary Row */}
      <section aria-label="Today's activity" className="rounded-lg border border-line bg-surface px-4 py-3">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="text-xs font-semibold uppercase tracking-wider text-ink-3">
            Today&apos;s activity
          </div>
          <div className="flex flex-wrap items-center gap-4 sm:gap-6 text-xs text-ink">
            <div className="flex items-center gap-1.5">
              <span className="font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-md">
                {counts.auto}
              </span>
              <span className="text-ink-2">Auto-handled</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="font-semibold text-amber-800 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded-md">
                {counts.clarification}
              </span>
              <span className="text-ink-2">Clarifications</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="font-semibold text-brand-700 bg-brand-50 border border-brand-200 px-2 py-0.5 rounded-md">
                {counts.handoff}
              </span>
              <span className="text-ink-2">Human handoffs</span>
            </div>
          </div>
        </div>
      </section>

      {/* Filter Bar */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <nav aria-label="Filter conversations by decision" className="flex flex-wrap gap-1.5">
          {FILTERS.map((f) => {
            const active = f.key === selectedAction;
            return (
              <button
                key={f.key || "all"}
                type="button"
                onClick={() => setSelectedAction(f.key)}
                aria-pressed={active}
                className={`inline-flex h-8 items-center rounded-md px-3 text-xs font-medium transition-colors ${
                  active
                    ? "bg-brand-700 text-white shadow-xs"
                    : "border border-line bg-surface text-ink-2 hover:bg-canvas hover:text-ink"
                }`}
              >
                {f.label}
              </button>
            );
          })}
        </nav>

        {/* Search filter */}
        <div className="relative w-full sm:w-64">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 size-3.5 text-ink-3 pointer-events-none" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search conversations..."
            className="h-8 w-full rounded-md border border-line bg-surface pl-8 pr-3 text-xs text-ink placeholder:text-ink-3 focus:border-brand-600 focus:outline-hidden"
          />
        </div>
      </div>

      {/* Main Audit Table */}
      <Card bodyClassName="p-0 overflow-hidden">
        {!filteredItems.length ? (
          <div className="p-8 text-center">
            <EmptyState
              icon={Bot}
              title={selectedAction || searchQuery ? "No matching conversations found" : "No audit records recorded yet"}
            >
              {selectedAction || searchQuery
                ? "Try adjusting your filter or search criteria."
                : "Audit records are written automatically for every processed customer request."}
            </EmptyState>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-line bg-canvas/80 text-ink-3">
                <tr>
                  <th scope="col" className="px-4 py-2.5 font-medium">Conversation</th>
                  <th scope="col" className="px-3 py-2.5 font-medium whitespace-nowrap">Time</th>
                  <th scope="col" className="px-3 py-2.5 font-medium">Decision</th>
                  <th scope="col" className="px-3 py-2.5 font-medium">Reason</th>
                  <th scope="col" className="px-3 py-2.5 font-medium">Evidence</th>
                  <th scope="col" className="px-3 py-2.5 font-medium">Human involvement</th>
                  <th scope="col" className="sr-only">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line/60 bg-surface">
                {filteredItems.map((t) => {
                  const title = conversationTitle(t.intent, t.reason_code);
                  const reason = formatAuditReason(t.final_decision, t.reason_code);
                  const dec = decisionDisplay(t.final_decision);
                  const ev = formatEvidenceLabel(t.evidence_level, t.final_decision);
                  const human = humanInvolvement(t.final_decision);

                  return (
                    <tr
                      key={t.trace_id}
                      className="group cursor-pointer hover:bg-canvas/40 transition-colors"
                      onClick={() => {
                        router.push(`/traces/${t.trace_id}`);
                      }}
                    >
                      {/* 1. Conversation */}
                      <td className="px-4 py-3">
                        <div className="font-medium text-ink group-hover:text-brand-700 transition-colors">
                          {title}
                        </div>
                        <div className="mt-0.5 text-[11px] text-ink-3">
                          Web chat · Case #{shortId(t.trace_id, 8)}
                        </div>
                      </td>

                      {/* 2. Time */}
                      <td className="px-3 py-3 text-ink-2 tabular whitespace-nowrap">
                        {dateTime(t.started_at)}
                      </td>

                      {/* 3. Decision */}
                      <td className="px-3 py-3 whitespace-nowrap">
                        <Badge tone={dec.tone}>{dec.label}</Badge>
                      </td>

                      {/* 4. Reason */}
                      <td className="px-3 py-3 text-ink-2 max-w-[200px] truncate" title={reason}>
                        {reason}
                      </td>

                      {/* 5. Evidence */}
                      <td className="px-3 py-3 whitespace-nowrap">
                        <Badge tone={ev.tone}>{ev.label}</Badge>
                      </td>

                      {/* 6. Human involvement */}
                      <td className="px-3 py-3 whitespace-nowrap">
                        <span className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-medium ${
                          human.tone === "success"
                            ? "bg-emerald-50 text-emerald-800 border border-emerald-200"
                            : human.tone === "info"
                            ? "bg-sky-50 text-sky-800 border border-sky-200"
                            : "bg-amber-50 text-amber-800 border border-amber-200"
                        }`}>
                          <span className={`size-1.5 rounded-full ${
                            human.tone === "success" ? "bg-emerald-600" : human.tone === "info" ? "bg-sky-600" : "bg-amber-600"
                          }`} />
                          {human.label}
                        </span>
                      </td>

                      {/* Action Chevron */}
                      <td className="px-3 py-3 text-right">
                        <Link
                          href={`/traces/${t.trace_id}`}
                          onClick={(e) => e.stopPropagation()}
                          className="inline-flex items-center text-ink-3 group-hover:text-brand-700 transition-colors"
                          aria-label={`View audit details for ${title}`}
                        >
                          <ChevronRight className="size-4" aria-hidden="true" />
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
