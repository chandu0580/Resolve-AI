"use client";

import { Activity, ArrowRight, Inbox } from "lucide-react";
import Link from "next/link";
import { useMemo } from "react";
import { ButtonLink } from "@/components/ui/button";
import { Advanced, Card, PageHeader } from "@/components/ui/card";
import { ErrorState, SkeletonRows } from "@/components/ui/states";
import { ConversationList } from "@/components/conversation/conversation-list";
import { DecisionBadge } from "@/components/conversation/conversations-table";
import { ConversationWorkspace, WorkspaceColumns } from "@/components/conversation/workspace";
import { DecisionExplanation } from "@/components/decision/decision-explanation";
import { TraceFacts, summarizeTraceDecision } from "@/components/trace/trace-decision";
import { TraceTimeline } from "@/components/trace/trace-timeline";
import type { Action, AgentTrace, TraceSummary } from "@/lib/api/types";
import type { ErrorInfo } from "@/lib/errors";
import { explainTrace } from "@/lib/explain";
import { dateTime, relativeTime, shortId } from "@/lib/format";
import { intentLabel } from "@/lib/labels";
import { useStoredResults } from "@/lib/results-store";
import {
  ConversationRow,
  conversationTitle,
  humanReason,
  queueCategory,
  rowFromStored,
  rowFromSummary,
} from "@/lib/rows";
import { useHydrated } from "@/lib/use-hydrated";

export function ConversationDetail({
  traceId,
  trace,
  traceError,
  summaries = null,
}: {
  traceId: string;
  trace: AgentTrace | null;
  traceError: ErrorInfo | null;
  summaries?: TraceSummary[] | null;
}) {
  const hydrated = useHydrated();
  const stored = useStoredResults().find((s) => s.traceId === traceId);

  const row = useMemo<ConversationRow | null>(() => {
    if (stored) return rowFromStored(stored);
    if (trace) {
      const summary = summaries?.find((s) => s.trace_id === traceId);
      if (summary) return rowFromSummary(summary);
      const ts = summarizeTraceDecision(trace);
      const usageList = (trace.usage ?? []) as { calls?: number; estimated_cost_usd?: number }[];
      return {
        traceId: trace.trace_id,
        requestId: trace.request_id ?? "",
        startedAt: trace.started_at,
        action: ((trace.final_decision as Action | null | undefined) ?? ts.action) ?? null,
        reasonCode: ts.reasonCode || null,
        intent: ts.finalIntent ?? null,
        confidence: ts.intent?.confidence ?? null,
        band: ts.intent?.band ?? null,
        evidenceLevel: ts.evidence?.level ?? null,
        evidenceSufficient: ts.evidence?.sufficient ?? null,
        riskFlags: ts.risk?.flags ?? [],
        rule: ts.policy?.rule ?? null,
        policyVersion: ts.policy?.policy_version ?? trace.versions?.policy ?? null,
        latencyMs: (trace.latency_ms as unknown as Record<string, number>)?.total ?? null,
        llmCalls: usageList.reduce((sum, u) => sum + (u.calls ?? 0), 0) || null,
        estimatedCostUsd: usageList.reduce((sum, u) => sum + (u.estimated_cost_usd ?? 0), 0) || null,
        channel: ((trace.request_meta as unknown as Record<string, unknown>)?.channel as string) ?? null,
        error: trace.error ?? null,
        preview: null,
        stored: null,
        inTraceList: true,
      };
    }
    return null;
  }, [stored, trace, summaries, traceId]);

  if (!hydrated) return <SkeletonRows rows={6} />;

  const action: Action | null = (stored?.result.action ?? (trace?.final_decision as Action | undefined) ?? null);
  const list = <ConversationList summaries={summaries} activeTraceId={traceId} />;
  const title = row ? conversationTitle(row) : `Conversation ${shortId(traceId)}`;

  const header = (
    <PageHeader
      breadcrumbs={[{ label: "Conversations", href: "/conversations" }, { label: title }]}
      title={title}
      description={
        stored
          ? "Customer inquiry, evidence citations, AI decision, and execution details."
          : "Review customer request, classified intent, evidence sufficiency, and AI decision."
      }
      actions={
        <>
          {action ? <DecisionBadge action={action} /> : null}
          {action === "HUMAN_HANDOFF" ? (
            <ButtonLink href={`/handoffs/${traceId}`} icon={Inbox}>
              Handoff packet
            </ButtonLink>
          ) : null}
          <ButtonLink href={`/traces/${traceId}`} icon={Activity}>
            Audit log
          </ButtonLink>
        </>
      }
    />
  );

  if (stored) {
    return (
      <>
        {header}
        <ConversationWorkspace result={stored.result} trace={trace} savedAt={stored.savedAt} source={stored.source} list={list} />
      </>
    );
  }

  if (trace && row) {
    const explanation = explainTrace(trace);
    const traceSummary = summarizeTraceDecision(trace);
    const intentText = row.intent ? intentLabel(row.intent) : "Unclassified";
    const reasonText = humanReason(row);
    const hasSufficientEvidence = traceSummary.evidence?.sufficient === true;
    const retrievedCount = traceSummary.retrieval?.n_retrieved ?? traceSummary.retrieval?.evidence_ids?.length ?? 0;

    return (
      <>
        {header}
        <WorkspaceColumns
          list={list}
          center={
            <>
              {/* 1. CUSTOMER REQUEST */}
              <Card title="Customer request" headingLevel={2}>
                <div className="flex flex-col gap-2">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="text-[15px] font-semibold text-ink">{title}</span>
                    <span className="rounded bg-subtle px-2 py-0.5 text-[11px] font-medium text-ink-3">
                      Audit record · Privacy preserved
                    </span>
                  </div>
                  <p className="text-[13px] text-ink-2">
                    Customer message text is never persisted in audit records by privacy design. The request was classified into the{" "}
                    <strong className="font-semibold text-ink">{intentText}</strong> domain.
                  </p>
                  <div className="mt-1 flex flex-wrap items-center gap-4 text-[12px] text-ink-3">
                    <span>
                      Channel: <strong className="font-medium text-ink-2">{row.channel || "Support web"}</strong>
                    </span>
                    <span>
                      Started:{" "}
                      <span title={dateTime(row.startedAt)} className="font-medium text-ink-2">
                        {relativeTime(row.startedAt)}
                      </span>
                    </span>
                  </div>
                </div>
              </Card>

              {/* 2. INTENT & EVIDENCE */}
              <Card title="ResolveAI understanding & evidence" headingLevel={2}>
                <div className="space-y-4">
                  <div className="rounded-md border border-line bg-canvas/40 p-3.5">
                    <div className="text-[11px] font-semibold tracking-wider text-ink-3 uppercase">Classified Intent</div>
                    <div className="mt-1 flex flex-wrap items-center gap-2">
                      <span className="text-[14px] font-medium text-ink">{intentText}</span>
                      {row.confidence !== null ? (
                        <span className="rounded bg-subtle px-2 py-0.5 text-[11.5px] font-semibold text-ink-2 tabular">
                          {(row.confidence * 100).toFixed(1)}% calibrated confidence
                        </span>
                      ) : null}
                    </div>
                  </div>

                  {/* Evidence Presentation */}
                  {hasSufficientEvidence ? (
                    <div className="rounded-md border border-brand-100 bg-brand-50/50 p-3.5">
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <div className="text-[11px] font-semibold tracking-wider text-brand-700 uppercase">Evidence</div>
                          <div className="mt-1 text-[14px] font-medium text-ink">
                            {retrievedCount > 0 ? `${retrievedCount} similar resolved cases` : "Sufficient historical resolution evidence"}
                          </div>
                          <p className="mt-0.5 text-[12.5px] text-ink-2">
                            Historical support cases provide a consistent, instruction-bearing resolution pattern.
                          </p>
                        </div>
                        <Link
                          href={`/traces/${traceId}#retrieval`}
                          className="mt-0.5 inline-flex shrink-0 items-center gap-1 text-[12px] font-medium text-brand-700 hover:underline"
                        >
                          <span>View evidence</span>
                          <ArrowRight className="size-3" aria-hidden="true" />
                        </Link>
                      </div>
                    </div>
                  ) : (
                    <div className="rounded-md border border-line bg-canvas/60 p-3.5">
                      <div className="text-[11px] font-semibold tracking-wider text-ink-3 uppercase">Evidence</div>
                      <div className="mt-1 text-[14px] font-medium text-ink">Needs more evidence</div>
                      <p className="mt-1 text-[12.5px] text-ink-2">
                        ResolveAI could not find enough historical support evidence to safely answer automatically.
                      </p>
                    </div>
                  )}
                </div>
              </Card>

              {/* 3. AI DECISION & OUTCOME */}
              <Card title="AI decision & outcome" headingLevel={2}>
                <div className="space-y-3">
                  <div className="flex flex-wrap items-center gap-3">
                    <DecisionBadge action={row.action} />
                    <span className="text-[13px] font-medium text-ink-2">&rarr; {reasonText}</span>
                  </div>
                  <div className="rounded-md border border-line bg-subtle/50 p-3 text-[13px] text-ink-2">
                    {row.action === "HUMAN_HANDOFF" ? (
                      <div className="flex flex-col gap-2">
                        <p>
                          Escalated to human operator in the <strong>{queueCategory(row)}</strong> queue.
                          Automatic reply withheld to ensure customer safety and answer grounding.
                        </p>
                        <div>
                          <ButtonLink href={`/handoffs/${traceId}`} icon={Inbox} variant="secondary" size="sm">
                            Open handoff packet
                          </ButtonLink>
                        </div>
                      </div>
                    ) : row.action === "CLARIFICATION_REQUIRED" ? (
                      <p>
                        The agent requested clarification from the customer to confirm details before proceeding.
                      </p>
                    ) : (
                      <p>
                        ResolveAI generated an autonomous grounded answer verified against historical evidence.
                      </p>
                    )}
                  </div>
                </div>
              </Card>

              {/* 4. ADVANCED TECHNICAL EXECUTION (Progressive disclosure) */}
              <Card title="Execution details" headingLevel={2}>
                <p className="text-[13px] text-ink-3">
                  Execution completed in {trace.latency_ms && typeof (trace.latency_ms as unknown as Record<string, number>).total === "number"
                    ? `${(trace.latency_ms as unknown as Record<string, number>).total} ms`
                    : "recorded time"}.
                </p>
                <Advanced label="Advanced technical & audit execution details">
                  <div className="space-y-4 pt-1">
                    <TraceFacts trace={trace} />
                    <Card title="Pipeline timeline" description="Recorded stages in execution order." headingLevel={3}>
                      <TraceTimeline events={trace.events} stageStatus={trace.stage_status} latency={trace.latency_ms} />
                    </Card>
                  </div>
                </Advanced>
              </Card>
            </>
          }
          right={
            <>
              {explanation ? <DecisionExplanation explanation={explanation} /> : null}
            </>
          }
        />
      </>
    );
  }

  return (
    <>
      {header}
      {traceError ? <ErrorState error={traceError} retry={<ButtonLink href="/conversations">All conversations</ButtonLink>} /> : null}
    </>
  );
}
