"use client";

import { ArrowRight, CircleHelp, RotateCcw, ShieldAlert, TriangleAlert, UserRound } from "lucide-react";
import Link from "next/link";
import { useMemo, type ElementType } from "react";
import { EmptyState } from "@/components/ui/states";
import type { TraceSummary } from "@/lib/api/types";
import { useStoredResults } from "@/lib/results-store";
import { conversationTitle, mergeRows } from "@/lib/rows";
import { relativeTime } from "@/lib/format";
import { intentLabel } from "@/lib/labels";

const DECISION_STYLE: Record<string, string> = {
  AUTO_HANDLE: "bg-success-bg text-success",
  CLARIFICATION_REQUIRED: "bg-warning-bg text-warning",
  HUMAN_HANDOFF: "bg-danger-bg text-danger",
};
const DECISION_LABEL: Record<string, string> = {
  AUTO_HANDLE: "Auto-handled",
  CLARIFICATION_REQUIRED: "Needs review",
  HUMAN_HANDOFF: "Human handoff",
};

/**
 * Recent conversations, in the shape an operator reads: what was asked, what the agent understood, what it decided, when.
 * Rows this browser ran show the customer's own words; audit-only rows are named by intent, because customer text is never
 * stored in the audit log.
 */
export function RecentConversations({ summaries }: { summaries: TraceSummary[] | null }) {
  const stored = useStoredResults();
  const rows = useMemo(() => mergeRows(summaries, stored).slice(0, 5), [summaries, stored]);
  return (
    <section aria-labelledby="recent-h" className="rounded-xl border border-line bg-surface">
      <header className="flex items-end justify-between gap-3 px-5 pt-4 pb-3">
        <div>
          <h2 id="recent-h" className="text-[17px] font-semibold text-ink">
            Recent conversations
          </h2>
        </div>
        <Link href="/conversations" className="inline-flex shrink-0 items-center gap-1.5 text-[13px] font-medium text-ink-2 hover:text-ink">
          View all <ArrowRight className="size-3.5" aria-hidden="true" />
        </Link>
      </header>
      {rows.length ? (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] border-collapse text-left">
            <thead>
              <tr className="border-y border-line bg-canvas/60">
                {["Conversation", "Intent", "Decision", "Time", ""].map((h) => (
                  <th key={h} scope="col" className="px-5 py-2 text-[11px] font-medium tracking-wide text-ink-3 uppercase">
                    {h || <span className="sr-only">Open</span>}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {rows.map((r) => (
                <tr key={r.traceId} className="hover:bg-canvas/60">
                  <td className="max-w-md px-5 py-3">
                    <Link href={`/conversations/${r.traceId}`} className="line-clamp-1 text-[13px] font-medium text-ink hover:text-brand-700">
                      {conversationTitle(r)}
                    </Link>
                  </td>
                  <td className="px-5 py-3">
                    <span className="rounded-md bg-subtle px-2 py-0.5 text-[12px] text-ink-2">{r.intent ? intentLabel(r.intent) : "Unclassified"}</span>
                  </td>
                  <td className="px-5 py-3">
                    {r.action ? (
                      <span className={`rounded-md px-2 py-0.5 text-[12px] font-medium ${DECISION_STYLE[r.action]}`}>{DECISION_LABEL[r.action]}</span>
                    ) : (
                      <span className="rounded-md bg-danger-bg px-2 py-0.5 text-[12px] font-medium text-danger">Failed</span>
                    )}
                  </td>
                  <td className="px-5 py-3 text-[12px] whitespace-nowrap text-ink-3">{relativeTime(r.startedAt)}</td>
                  <td className="px-5 py-3 text-right">
                    <Link href={`/conversations/${r.traceId}`} className="text-[12px] font-medium text-brand-700 hover:underline">
                      Open
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="px-5 pb-5">
          <EmptyState title="No conversations yet">Send a message through the customer agent and it will appear here.</EmptyState>
        </div>
      )}
    </section>
  );
}

/** Categories an operator would act on, counted from the real audit records — never a triage model. */
export function NeedsAttention({ summaries }: { summaries: TraceSummary[] | null }) {
  const items = summaries ?? [];
  const SENSITIVE = new Set(["safety", "account_access", "payment_billing", "private_info", "legal_media", "prompt_injection", "abusive_threatening"]);
  const groups: { icon: ElementType; label: string; n: number; href: string }[] = [
    { icon: UserRound, label: "Human handoffs", n: items.filter((t) => t.final_decision === "HUMAN_HANDOFF").length, href: "/handoffs" },
    { icon: TriangleAlert, label: "Needs clarification", n: items.filter((t) => t.final_decision === "CLARIFICATION_REQUIRED").length, href: "/conversations?filter=clarification" },
    { icon: ShieldAlert, label: "Sensitive requests", n: items.filter((t) => t.reason_code && SENSITIVE.has(t.reason_code)).length, href: "/trust" },
    { icon: RotateCcw, label: "Repeated failed attempts", n: items.filter((t) => (t.risk_flags ?? []).includes("repeat_contact")).length, href: "/handoffs" },
    { icon: CircleHelp, label: "Unclear requests", n: items.filter((t) => t.reason_code === "insufficient_context" || t.reason_code === "low_confidence").length, href: "/conversations?filter=clarification" },
  ];
  return (
    <section aria-labelledby="attention-h" className="rounded-xl border border-line bg-surface p-5">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 id="attention-h" className="text-[15px] font-semibold text-ink">
          Needs attention
        </h2>
        <Link href="/handoffs" className="text-[12px] font-medium text-ink-2 hover:text-ink">
          View all
        </Link>
      </div>
      <ul className="space-y-1">
        {groups.map(({ icon: Icon, label, n, href }) => (
          <li key={label}>
            <Link href={href} className="flex items-center gap-2.5 rounded-lg px-2 py-2 hover:bg-canvas">
              <Icon className={`size-4 shrink-0 ${n ? "text-brand-700" : "text-ink-3"}`} aria-hidden="true" />
              <span className="min-w-0 flex-1 truncate text-[13px] text-ink-2">{label}</span>
              <span className={`shrink-0 text-[13px] font-semibold tabular ${n ? "text-ink" : "text-ink-3"}`}>{n}</span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
