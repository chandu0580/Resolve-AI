import type { Metadata } from "next";
import { ArrowRight, CircleCheck, MessagesSquare, TriangleAlert, UserRound } from "lucide-react";
import Link from "next/link";
import type { ElementType } from "react";
import { NeedsAttention, RecentConversations } from "@/components/overview/dashboard";
import { Badge } from "@/components/ui/badge";
import { ErrorState } from "@/components/ui/states";
import { api, load } from "@/lib/api/client";
import type { MetricCell, ReleaseEvaluation } from "@/lib/api/types";
import { toErrorInfo } from "@/lib/errors";
import { pct } from "@/lib/format";
import { liveMetrics } from "@/lib/rows";

export const metadata: Metadata = { title: "Overview" };

function greeting(): string {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
}

function StatTile({ icon: Icon, value, label, sub, tone }: { icon: ElementType; value: string; label: string; sub?: string; tone: "brand" | "success" | "warning" | "danger" }) {
  const chip = {
    brand: "bg-brand-50 text-brand-700",
    success: "bg-success-bg text-success",
    warning: "bg-warning-bg text-warning",
    danger: "bg-danger-bg text-danger",
  }[tone];
  return (
    <div className="min-w-0 rounded-xl border border-line bg-surface p-4">
      <dt className="sr-only">{label}</dt>
      <dd>
        <span className={`mb-3 flex size-10 items-center justify-center rounded-lg ${chip}`}>
          <Icon className="size-[18px]" aria-hidden="true" />
        </span>
        <div className="text-[28px] leading-none font-semibold tracking-tight text-ink tabular">{value}</div>
        <div className="mt-1.5 flex items-baseline gap-2">
          <span className="text-[13px] text-ink-2">{label}</span>
          {sub ? <span className="text-[12px] text-ink-3 tabular">{sub}</span> : null}
        </div>
      </dd>
    </div>
  );
}

/** Frozen benchmark figures, served by the API. Never mixed with the live counters above. */
function AiPerformance({ release }: { release: ReleaseEvaluation | null }) {
  const g = release?.golden;
  const cells = g?.table ? (Object.values(g.table)[0] as Record<string, MetricCell>) : undefined;
  const value = (key: string, asPct: boolean) => {
    const c = cells?.[key];
    if (!c || typeof c.resolveai !== "number") return null;
    return asPct ? pct(c.resolveai) : c.resolveai.toFixed(3);
  };
  const metrics = [
    { label: "Intent accuracy", value: value("intent_accuracy", true) },
    { label: "Escalation recall", value: value("escalation_recall", true) },
    { label: "Safe automatic replies", value: value("safe_autonomous_rate", true), sub: "Conservative by design" },
    { label: "Unsafe automatic replies", value: cells?.unsafe_autonomous_count ? String(cells.unsafe_autonomous_count.resolveai) : "0" },
  ];
  if (!g) return null;
  return (
    <section aria-labelledby="perf-h" className="rounded-xl border border-line bg-surface p-5">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <h2 id="perf-h" className="text-[17px] font-semibold text-ink">
            Measured performance
          </h2>
          <Badge tone="neutral">Frozen benchmark · {g.release.n} evaluation examples</Badge>
        </div>
        <Link href="/evaluation" className="inline-flex items-center gap-1 text-[13px] font-medium text-brand-700 hover:underline">
          View full evaluation →
        </Link>
      </div>
      <p className="mb-5 text-[13px] text-ink-3">
        One frozen benchmark run — not live traffic.
      </p>
      <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {metrics.map((m) => (
          <div key={m.label} className="border-line sm:border-l sm:pl-4 sm:first:border-l-0 sm:first:pl-0">
            <dt className="text-[13px] text-ink-3">{m.label}</dt>
            <dd className="mt-1.5 text-[26px] leading-none font-semibold text-ink tabular">{m.value ?? "n/a"}</dd>
            {m.sub ? <div className="mt-1 text-[11px] font-medium text-ink-3">{m.sub}</div> : null}
          </div>
        ))}
      </dl>
    </section>
  );
}

function AgentStatusPanel({
  ready,
  cases,
}: {
  ready: { ready: boolean; components: Record<string, unknown> } | null;
  cases: number | null;
}) {
  const isOnline = ready?.ready ?? false;
  const rows: [string, string][] = [
    ["Knowledge", cases ? "Connected" : "Disconnected"],
    ["Guardrails", "Active"],
    ["System status", isOnline ? "Operational" : "Degraded"],
  ];
  return (
    <section aria-labelledby="agent-h" className="rounded-xl border border-line bg-surface p-5">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 id="agent-h" className="text-[15px] font-semibold text-ink">
          Agent status
        </h2>
        <Badge tone={isOnline ? "success" : "danger"}>{isOnline ? "Online" : "Not ready"}</Badge>
      </div>
      <dl className="space-y-2">
        {rows.map(([k, v]) => (
          <div key={k} className="flex items-baseline justify-between gap-3">
            <dt className="text-[13px] text-ink-3">{k}</dt>
            <dd className="min-w-0 truncate text-right text-[13px] font-medium text-ink">{v}</dd>
          </div>
        ))}
      </dl>
      <Link href="/agents" className="mt-4 inline-flex items-center gap-1 text-[13px] font-medium text-brand-700 hover:underline">
        View agent profile →
      </Link>
    </section>
  );
}

export default async function OverviewPage() {
  const [traces, release, ready, knowledge] = await Promise.all([
    load(api.traces({ limit: 200 })),
    load(api.evaluationRelease()),
    load(api.ready()),
    load(api.knowledgeSummary()),
  ]);
  const items = traces.data?.items ?? null;
  const live = items ? liveMetrics(items) : null;
  const cases = typeof knowledge.data?.rows === "number" ? knowledge.data.rows : null;
  const agentOk = ready.data ? ready.data.ready : false;

  return (
    <>
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-[11px] font-medium tracking-[0.12em] text-ink-3 uppercase">{greeting()}</p>
          <h1 className="mt-2 text-[30px] leading-tight font-semibold tracking-tight text-ink sm:text-[34px]">
            {agentOk ? "Your AI support agent is ready." : "The agent is not ready."}
          </h1>
          <p className="mt-2 text-[14px] text-ink-3">
            Resolving customer requests with historical support context, grounded answers, and human oversight.
          </p>
        </div>
        <Link
          href="/simulate"
          className="inline-flex shrink-0 items-center justify-center gap-1.5 rounded-lg bg-brand-600 px-3.5 py-2 text-[13px] font-medium text-surface shadow-xs hover:bg-brand-700"
        >
          Test the Agent <ArrowRight className="size-3.5" aria-hidden="true" />
        </Link>
      </div>

      {traces.error ? <ErrorState error={toErrorInfo(traces.error)} /> : null}

      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-[11px] font-semibold tracking-wider text-ink-3 uppercase">Live Operations</h2>
      </div>
      <dl aria-label="Live operational counters" className="mb-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatTile icon={MessagesSquare} tone="brand" value={String(live?.n ?? 0)} label="Total conversations" sub={undefined} />
        <StatTile
          icon={CircleCheck}
          tone="success"
          value={String(live?.auto ?? 0)}
          label="Auto-handled"
          sub={live && live.n ? `${pct(live.auto / live.n)} of conversations` : undefined}
        />
        <StatTile
          icon={TriangleAlert}
          tone="warning"
          value={String(live?.clarification ?? 0)}
          label="Needs clarification"
          sub={live && live.n ? `${pct(live.clarification / live.n)} of conversations` : undefined}
        />
        <StatTile
          icon={UserRound}
          tone="danger"
          value={String(live?.handoff ?? 0)}
          label="Human handoff"
          sub={live && live.n ? `${pct(live.handoff / live.n)} of conversations` : undefined}
        />
      </dl>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="min-w-0 space-y-4">
          <RecentConversations summaries={items} />
          <AiPerformance release={(release.data as ReleaseEvaluation | undefined) ?? null} />
        </div>
        <div className="min-w-0 space-y-4">
          <NeedsAttention summaries={items} />
          <AgentStatusPanel ready={ready.data ?? null} cases={cases} />
        </div>
      </div>
    </>
  );
}
