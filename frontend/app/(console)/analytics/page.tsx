import type { Metadata } from "next";
import Link from "next/link";
import { Card, PageHeader } from "@/components/ui/card";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { AnalyticsDashboard } from "@/components/analytics/analytics-dashboard";
import { api, load } from "@/lib/api/client";
import { toErrorInfo } from "@/lib/errors";
import { dateTime } from "@/lib/format";
import { liveMetrics } from "@/lib/rows";

export const metadata: Metadata = { title: "Analytics" };

export default async function AnalyticsPage() {
  const traces = await load(api.traces({ limit: 200 })); // the API caps limit at 200
  if (traces.error) {
    return (
      <>
        <PageHeader
          eyebrow="INSIGHTS"
          title="Analytics"
          description="Understand how ResolveAI is handling customer conversations."
        />
        <ErrorState error={toErrorInfo(traces.error)} />
      </>
    );
  }
  const items = traces.data?.items ?? [];
  const m = liveMetrics(items);

  return (
    <>
      <PageHeader
        eyebrow="INSIGHTS"
        title="Analytics"
        description="Understand how ResolveAI is handling customer conversations."
      />

      <div className="mb-6 flex flex-wrap items-center gap-2">
        <span className="rounded border border-info-line bg-info-bg px-2 py-0.5 text-[11px] font-medium tracking-wider text-info uppercase">
          Live operational data
        </span>
        <span className="text-xs text-ink-3">
          {m.n ? `${m.n} conversations, ${dateTime(m.oldest ?? "")} to ${dateTime(m.newest ?? "")}` : "No conversations recorded yet"}
        </span>
        <Link href="/evaluation" className="ml-auto text-xs font-medium text-[#586651] hover:underline">
          Benchmark results are on Evaluation →
        </Link>
      </div>

      {!m.n ? (
        <Card>
          <EmptyState title="No conversations recorded yet">
            Run a conversation through the agent and it will appear here. This page only ever counts what this deployment
            actually handled.
          </EmptyState>
        </Card>
      ) : (
        <AnalyticsDashboard items={items} />
      )}
    </>
  );
}
