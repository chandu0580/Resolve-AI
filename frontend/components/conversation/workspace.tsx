import { Activity } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";
import { Advanced, Card, KeyValues, Mono } from "@/components/ui/card";
import { ClarificationView } from "@/components/clarification/clarification-view";
import { ConversationThread, UnderstandingCard } from "@/components/conversation/conversation-thread";
import { DecisionBanner } from "@/components/decision/decision-banner";
import { DecisionDetails } from "@/components/decision/decision-details";
import { DecisionExplanation } from "@/components/decision/decision-explanation";
import { EvidencePanel } from "@/components/evidence/evidence-panel";
import { HandoffPacketView } from "@/components/handoff/handoff-packet";
import { ResponsePanel } from "@/components/response/response-panel";
import { TraceTimeline } from "@/components/trace/trace-timeline";
import type { AgentTrace, ResolveResponse } from "@/lib/api/types";
import { explainResult } from "@/lib/explain";
import { dateTime, duration, usd } from "@/lib/format";

export function RunFacts({ result, savedAt, source }: { result: ResolveResponse; savedAt?: string; source?: string }) {
  const v = result.versions;
  const usage = result.usage as typeof result.usage & { retries?: number; timeouts?: number; budget_exhausted?: number };
  return (
    <Card title="This run" headingLevel={3}>
      <KeyValues
        items={[
          ...(savedAt ? [{ label: "Handled", value: dateTime(savedAt), hint: source }] : []),
          { label: "Time taken", value: duration(result.latency_ms.total) },
          { label: "Audit record", value: <Link href={`/traces/${result.trace_id}`} className="text-[13px] font-medium text-brand-700 hover:underline">Open the full audit trail</Link> },
        ]}
      />
      <Advanced>
        <KeyValues
          items={[
            { label: "Trace id", value: <Mono>{result.trace_id}</Mono> },
            { label: "Request id", value: <Mono>{result.request_id}</Mono> },
            {
              label: "Model calls",
              value: `${usage.llm_calls} (${usage.live_calls} live, ${usage.cache_hits} cached)`,
              hint: `Estimated cost ${usd(usage.estimated_cost_usd)} at list price${usage.fallbacks ? ` · ${usage.fallbacks} fallbacks` : ""}`,
            },
            ...(usage.retries || usage.timeouts || usage.budget_exhausted
              ? [
                  {
                    label: "Model reliability",
                    value: `${usage.retries ?? 0} retries · ${usage.timeouts ?? 0} timeouts`,
                    hint: usage.budget_exhausted ? "Some model calls were refused because the request time budget was spent." : undefined,
                  },
                ]
              : []),
            { label: "Pipeline", value: <Mono>{v.pipeline}</Mono> },
            { label: "Evidence gate", value: <Mono>{`${v.evidence_gate} · ${v.rerank}`}</Mono> },
            { label: "Output gate", value: <Mono>{v.output_gate}</Mono> },
            { label: "Model", value: <Mono>{v.model ?? "none"}</Mono> },
            { label: "Config hash", value: <Mono>{v.config_hash}</Mono> },
          ]}
        />
      </Advanced>
    </Card>
  );
}


/**
 * Workspace layout. With a list: LEFT conversation list, CENTER conversation timeline, RIGHT decision, evidence and action.
 * DOM order is the reading order at every width; below xl the list collapses into a disclosure above the timeline.
 */
export function WorkspaceColumns({ list, center, right }: { list?: ReactNode; center: ReactNode; right: ReactNode }) {
  return (
    <div className={`grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(320px,420px)] ${list ? "xl:grid-cols-[250px_minmax(0,1fr)_minmax(340px,420px)]" : ""}`}>
      {list ? <div className="min-w-0 lg:col-span-2 xl:sticky xl:top-20 xl:col-span-1">{list}</div> : null}
      <div className="min-w-0 space-y-4">{center}</div>
      <section aria-label="Decision, evidence and action" className="min-w-0 space-y-4">
        {right}
      </section>
    </div>
  );
}

export function ConversationWorkspace({ result, trace, savedAt, source, list }: { result: ResolveResponse; trace?: AgentTrace | null; savedAt?: string; source?: string; list?: ReactNode }) {
  return (
    <WorkspaceColumns
      list={list}
      center={
        <>
          <ConversationThread result={result} />
          <ResponsePanel result={result} />
          {result.clarification ? <ClarificationView result={result} /> : null}
          <Card
            title="What ResolveAI did"
            description="Autonomous pipeline stages and execution timing."
            actions={
              <Link href={`/traces/${result.trace_id}`} className="inline-flex items-center gap-1 text-xs font-medium text-brand-700 hover:underline">
                <Activity className="size-3.5" aria-hidden="true" /> Full trace
              </Link>
            }
          >
            <p className="text-[13px] text-ink-3">
              Total latency: {duration(result.latency_ms.total)} across {result.usage.llm_calls} model calls.
            </p>
            <Advanced label="Pipeline execution timeline">
              <div className="pt-1">
                {trace ? (
                  <TraceTimeline events={trace.events} stageStatus={trace.stage_status} latency={trace.latency_ms} />
                ) : (
                  <TraceTimeline events={[]} stageStatus={result.stage_status} latency={result.latency_ms} />
                )}
                {!trace ? <p className="mt-2 text-xs text-ink-3">The audit trace could not be loaded. Stage statuses come from the API response.</p> : null}
              </div>
            </Advanced>
          </Card>
        </>
      }
      right={
        <>
          <DecisionBanner outcome={result.outcome} />
          <DecisionExplanation explanation={explainResult(result)} />
          {result.handoff ? <HandoffPacketView result={result} /> : null}
          <EvidencePanel evidence={result.evidence} citedIds={result.response.evidence_refs.map((r) => r.evidence_id)} />
          <DecisionDetails result={result} />
          <UnderstandingCard result={result} />
          <RunFacts result={result} savedAt={savedAt} source={source} />
        </>
      }
    />
  );
}
