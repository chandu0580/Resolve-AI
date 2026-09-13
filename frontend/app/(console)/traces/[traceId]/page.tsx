import type { Metadata } from "next";
import { ChevronDown, EyeOff, FileText, Inbox, MessagesSquare, Shield } from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { ButtonLink } from "@/components/ui/button";
import { Card, PageHeader } from "@/components/ui/card";
import { ErrorState } from "@/components/ui/states";
import { DecisionExplanation } from "@/components/decision/decision-explanation";
import { TraceDecisionView, TraceFacts, summarizeTraceDecision } from "@/components/trace/trace-decision";
import { TraceSummaryCard } from "@/components/trace/trace-summary";
import { TraceTimeline } from "@/components/trace/trace-timeline";
import { conversationTitle, decisionDisplay, formatAuditReason, formatEvidenceLabel, humanInvolvement } from "@/components/trace/audit-log-helpers";
import { api, load } from "@/lib/api/client";
import { toErrorInfo } from "@/lib/errors";
import { explainTrace } from "@/lib/explain";
import { dateTime, shortId } from "@/lib/format";
import { intentLabel, reasonMeta } from "@/lib/labels";

export const metadata: Metadata = { title: "Audit Detail" };

export default async function TracePage({ params }: { params: Promise<{ traceId: string }> }) {
  const { traceId } = await params;
  const trace = await load(api.trace(traceId));

  if (trace.error) {
    return (
      <>
        <PageHeader
          breadcrumbs={[{ label: "Audit Log", href: "/traces" }, { label: `Record #${shortId(traceId, 8)}` }]}
          title={`Audit Record #${shortId(traceId, 8)}`}
        />
        <ErrorState error={toErrorInfo(trace.error)} retry={<ButtonLink href="/traces">Back to Audit Log</ButtonLink>} />
      </>
    );
  }

  const t = trace.data;
  const s = summarizeTraceDecision(t);
  const explanation = explainTrace(t);
  const title = conversationTitle(s.finalIntent ?? t.events.find(e => e.name === "intent_predicted")?.data?.intent as string, s.reasonCode);
  const dec = decisionDisplay(t.final_decision);
  const reason = formatAuditReason(t.final_decision, s.reasonCode);
  const ev = formatEvidenceLabel(s.evidence?.level, t.final_decision);
  const human = humanInvolvement(t.final_decision);
  const evidenceIds = s.retrieval?.evidence_ids ?? [];

  return (
    <>
      <PageHeader
        breadcrumbs={[{ label: "Audit Log", href: "/traces" }, { label: title }]}
        title={title}
        description={`Audit record from ${dateTime(t.started_at)} · Web chat channel · Case #${shortId(t.trace_id, 8)}`}
        actions={
          <>
            <ButtonLink href={`/conversations/${t.trace_id}`} icon={MessagesSquare}>
              Conversation
            </ButtonLink>
            {t.final_decision === "HUMAN_HANDOFF" ? (
              <ButtonLink href={`/handoffs/${t.trace_id}`} icon={Inbox}>
                Handoff packet
              </ButtonLink>
            ) : null}
          </>
        }
      />

      {/* Primary Operator Audit Detail View */}
      <div className="space-y-6">
        {/* Decision & Status Banner */}
        <div className="rounded-lg border border-line bg-surface p-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between border-b border-line pb-3.5">
            <div className="flex items-center gap-2.5">
              <span className="text-xs font-semibold uppercase tracking-wider text-ink-3">Decision:</span>
              <Badge tone={dec.tone}>{dec.label}</Badge>
            </div>
            <div className="flex items-center gap-2 text-xs">
              <span className="text-ink-3">Human involvement:</span>
              <span className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium ${
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
            </div>
          </div>

          <div className="mt-3.5 grid gap-4 sm:grid-cols-2">
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-wider text-ink-3">Reason</div>
              <div className="mt-1 text-sm font-medium text-ink">{reason}</div>
              <p className="mt-0.5 text-xs text-ink-3">
                {s.reasonCode && s.reasonCode !== "none" ? reasonMeta(s.reasonCode).label : "Autonomous reply verified against knowledge"}
              </p>
            </div>

            <div>
              <div className="text-[11px] font-semibold uppercase tracking-wider text-ink-3">Evidence sufficiency</div>
              <div className="mt-1 flex items-center gap-2">
                <Badge tone={ev.tone}>{ev.label}</Badge>
                {evidenceIds.length ? (
                  <span className="text-xs text-ink-2">({evidenceIds.length} support {evidenceIds.length === 1 ? "case" : "cases"} cited)</span>
                ) : null}
              </div>
              <p className="mt-0.5 text-xs text-ink-3">
                {s.evidence?.level ? `${s.evidence.level} support level` : "Evidence assessed at gate"}
              </p>
            </div>
          </div>
        </div>

        {/* Conversation Context & Decision Explanation */}
        <div className="grid items-start gap-4 lg:grid-cols-2">
          {/* Conversation Context */}
          <Card title="Conversation Context">
            <div className="space-y-3">
              <div>
                <div className="text-xs font-semibold uppercase tracking-wider text-ink-3">Inquiry Topic</div>
                <div className="mt-1 text-sm font-medium text-ink">
                  {s.finalIntent ? intentLabel(s.finalIntent) : title}
                </div>
              </div>

              <div className="rounded-md border border-line bg-canvas/60 p-3 text-xs text-ink-2">
                <div className="flex items-center gap-1.5 font-medium text-ink">
                  <EyeOff className="size-3.5 text-ink-3" aria-hidden="true" />
                  Privacy & Data Scrubbing
                </div>
                <p className="mt-1 leading-relaxed text-ink-3">
                  Customer conversation text is redacted for privacy prior to permanent audit logging. Full conversation history is accessible from the active conversation workspace.
                </p>
                <div className="mt-2.5">
                  <Link
                    href={`/conversations/${t.trace_id}`}
                    className="inline-flex items-center gap-1 font-medium text-brand-700 hover:underline"
                  >
                    Open conversation in workspace →
                  </Link>
                </div>
              </div>
            </div>
          </Card>

          {/* Decision Explanation & Next Action */}
          <Card title="Decision Explanation">
            <div className="space-y-3">
              <p className="text-xs leading-relaxed text-ink-2">
                {explanation?.decision ?? (
                  t.final_decision === "AUTO_HANDLE"
                    ? "ResolveAI found verified resolution evidence in Apple Support guides and autonomously delivered a verified solution."
                    : t.final_decision === "CLARIFICATION_REQUIRED"
                    ? "ResolveAI detected missing symptom details and asked a focused clarification question before proceeding."
                    : "ResolveAI could not safely resolve this request automatically, so it was routed to a human teammate."
                )}
              </p>

              <div className="border-t border-line/60 pt-3">
                <div className="text-[11px] font-semibold uppercase tracking-wider text-ink-3">Next Action</div>
                <div className="mt-1 text-xs font-medium text-ink">
                  {explanation?.nextAction ?? (
                    t.final_decision === "HUMAN_HANDOFF"
                      ? "A support teammate should review the conversation in the Handoffs queue."
                      : t.final_decision === "CLARIFICATION_REQUIRED"
                      ? "Awaiting customer response to the clarification question."
                      : "No human action required: customer request was resolved autonomously."
                  )}
                </div>
              </div>

              {t.final_decision === "HUMAN_HANDOFF" ? (
                <div className="pt-1">
                  <Link
                    href={`/handoffs/${t.trace_id}`}
                    className="inline-flex items-center gap-1 text-xs font-semibold text-brand-700 hover:underline"
                  >
                    View handoff packet in queue →
                  </Link>
                </div>
              ) : null}
            </div>
          </Card>
        </div>

        {/* Evidence Details */}
        {evidenceIds.length ? (
          <Card title="Cited Evidence">
            <div className="space-y-2">
              <p className="text-xs text-ink-3">
                Relevant verified support cases referenced during resolution:
              </p>
              <div className="flex flex-wrap gap-2 pt-1">
                {evidenceIds.map((id) => (
                  <span
                    key={id}
                    className="inline-flex items-center gap-1.5 rounded-md border border-line bg-canvas/80 px-2.5 py-1 text-xs font-mono text-ink-2"
                  >
                    <FileText className="size-3 text-brand-700" aria-hidden="true" />
                    Case #{shortId(id, 12)}
                  </span>
                ))}
              </div>
            </div>
          </Card>
        ) : null}

        {/* Advanced Details (Collapsed by default) */}
        <section aria-labelledby="section-advanced-details" className="pt-2">
          <details className="group rounded-lg border border-line bg-surface p-4 transition-all">
            <summary className="flex cursor-pointer items-center justify-between text-sm font-semibold text-ink select-none">
              <div className="flex items-center gap-2">
                <Shield className="size-4 text-brand-700" aria-hidden="true" />
                <span>Advanced details</span>
                <span className="text-xs font-normal text-ink-3">
                  Trace ID, request correlation, execution latency, model telemetry, and pipeline timeline
                </span>
              </div>
              <ChevronDown className="size-4 text-ink-3 transition-transform group-open:rotate-180" aria-hidden="true" />
            </summary>

            <div className="mt-5 space-y-6 border-t border-line pt-5">
              <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,1fr)_420px]">
                <div className="min-w-0 space-y-4">
                  <TraceSummaryCard trace={t} />
                  <Card title="Pipeline timeline" description="Every recorded stage with its status, duration and start time.">
                    <TraceTimeline events={t.events} stageStatus={t.stage_status} latency={t.latency_ms} initiallyOpen={["evidence_gate", "policy", "decision"]} />
                  </Card>
                  <TraceDecisionView trace={t} showTextNotice={false} />
                </div>
                <div className="min-w-0 space-y-4">
                  {explanation ? <DecisionExplanation explanation={explanation} /> : null}
                  <TraceFacts trace={t} />
                </div>
              </div>
            </div>
          </details>
        </section>
      </div>
    </>
  );
}
