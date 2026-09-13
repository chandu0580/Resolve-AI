"use client";

import Link from "next/link";
import { useMemo } from "react";
import { ActionBadge } from "@/components/ui/status";
import type { TraceSummary } from "@/lib/api/types";
import { dateTime, relativeTime, shortId } from "@/lib/format";
import { intentLabel, reasonMeta } from "@/lib/labels";
import { useStoredResults } from "@/lib/results-store";
import { conversationTitle, mergeRows } from "@/lib/rows";

const LIMIT = 30;

function Items({ summaries, activeTraceId }: { summaries: TraceSummary[] | null; activeTraceId: string }) {
  const stored = useStoredResults();
  const rows = useMemo(() => mergeRows(summaries, stored).slice(0, LIMIT), [summaries, stored]);
  if (!rows.length) return <p className="px-3 py-4 text-[13px] text-ink-3">No other conversations recorded.</p>;
  return (
    <ul className="divide-y divide-line">
      {rows.map((r) => {
        const active = r.traceId === activeTraceId;
        return (
          <li key={r.traceId}>
            <Link
              href={`/conversations/${r.traceId}`}
              aria-current={active ? "page" : undefined}
              className={`block px-3 py-2.5 hover:bg-canvas ${active ? "bg-brand-50/70 shadow-[inset_3px_0_0_var(--color-brand-600)]" : ""}`}
            >
              <div className="flex items-center justify-between gap-2">
                {r.action ? <ActionBadge action={r.action} /> : <span className="text-xs text-danger">Failed</span>}
                <span className="font-mono text-[11px] text-ink-3">{shortId(r.traceId)}</span>
              </div>
              <p className="mt-1 line-clamp-2 text-[13px] text-ink">{conversationTitle(r)}</p>
              <p className="mt-0.5 text-[11px] text-ink-3">
                {r.intent ? intentLabel(r.intent) : "Intent n/a"}
                {r.action && r.action !== "AUTO_HANDLE" ? ` · ${reasonMeta(r.reasonCode).label}` : ""}
              </p>
              <p className="text-[11px] text-ink-3 tabular" title={dateTime(r.startedAt)}>{relativeTime(r.startedAt)}</p>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

/** LEFT panel of the conversation workspace: recent conversations (trace summaries plus results stored in this browser). */
export function ConversationList({ summaries, activeTraceId }: { summaries: TraceSummary[] | null; activeTraceId: string }) {
  return (
    <nav aria-label="Conversations" className="min-w-0">
      <div className="hidden overflow-hidden rounded-lg border border-line bg-surface xl:block">
        <div className="flex items-baseline justify-between border-b border-line px-3 py-2.5">
          <h2 className="text-sm font-semibold text-ink">Conversations</h2>
          <Link href="/conversations" className="text-xs font-medium text-brand-700 hover:underline">
            All
          </Link>
        </div>
        <div className="max-h-[calc(100vh-11rem)] overflow-y-auto">
          <Items summaries={summaries} activeTraceId={activeTraceId} />
        </div>
      </div>
      <details className="rounded-lg border border-line bg-surface xl:hidden">
        <summary className="cursor-pointer px-3 py-2.5 text-sm font-semibold text-ink">Other conversations</summary>
        <div className="max-h-96 overflow-y-auto border-t border-line">
          <Items summaries={summaries} activeTraceId={activeTraceId} />
        </div>
      </details>
    </nav>
  );
}
