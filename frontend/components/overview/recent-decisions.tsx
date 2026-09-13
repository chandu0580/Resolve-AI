"use client";

import { MessagesSquare } from "lucide-react";
import Link from "next/link";
import { useMemo } from "react";
import { ButtonLink } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/states";
import { ActionBadge } from "@/components/ui/status";
import { DataTable, TD, TH } from "@/components/ui/table";
import type { TraceSummary } from "@/lib/api/types";
import { dateTime, pct, shortId } from "@/lib/format";
import { intentLabel, reasonMeta } from "@/lib/labels";
import { useStoredResults } from "@/lib/results-store";
import { mergeRows } from "@/lib/rows";

export function RecentDecisions({ summaries }: { summaries: TraceSummary[] | null }) {
  const stored = useStoredResults();
  const rows = useMemo(() => mergeRows(summaries, stored).slice(0, 8), [summaries, stored]);
  return (
    <Card
      title="Recent decisions"
      description="Newest first. Open a row for the full decision, evidence and trace."
      actions={
        <ButtonLink href="/conversations" size="sm">
          All conversations
        </ButtonLink>
      }
      bodyClassName="p-0"
    >
      {!rows.length ? (
        <EmptyState icon={MessagesSquare} title="No decisions recorded yet" action={<ButtonLink href="/simulate" variant="primary">Run a demo scenario</ButtonLink>}>
          Run a demo scenario to see ResolveAI decide, with its evidence and trace.
        </EmptyState>
      ) : (
        <DataTable label="Recent decisions" minWidth={760}>
          <thead>
            <tr>
              <th scope="col" className={TH}>Issue</th>
              <th scope="col" className={TH}>Intent</th>
              <th scope="col" className={TH}>Action</th>
              <th scope="col" className={TH}>Confidence</th>
              <th scope="col" className={TH}>Time</th>
              <th scope="col" className={TH}>Trace</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.traceId} className="hover:bg-canvas">
                <td className={`${TD} max-w-72`}>
                  <Link href={`/conversations/${r.traceId}`} className="font-medium text-brand-700 hover:underline">
                    {r.preview ? <span className="line-clamp-1">{r.preview}</span> : `Conversation ${shortId(r.traceId)}`}
                  </Link>
                  <div className="text-xs text-ink-3">{r.action === "AUTO_HANDLE" ? "Answered on evidence" : reasonMeta(r.reasonCode).label}</div>
                </td>
                <td className={TD}>{r.intent ? intentLabel(r.intent) : "n/a"}</td>
                <td className={TD}>{r.action ? <ActionBadge action={r.action} /> : "Failed"}</td>
                <td className={`${TD} tabular`}>{r.confidence !== null ? pct(r.confidence) : "n/a"}</td>
                <td className={`${TD} text-xs whitespace-nowrap text-ink-2 tabular`}>{dateTime(r.startedAt)}</td>
                <td className={TD}>
                  <Link href={`/traces/${r.traceId}`} className="font-mono text-xs text-brand-700 hover:underline" aria-label={`Trace ${r.traceId}`}>
                    {shortId(r.traceId, 10)}
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </DataTable>
      )}
    </Card>
  );
}
