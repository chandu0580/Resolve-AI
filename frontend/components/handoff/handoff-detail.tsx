"use client";

import { Activity, ArrowLeft, MessagesSquare } from "lucide-react";
import Link from "next/link";
import { useMemo } from "react";
import { ButtonLink } from "@/components/ui/button";
import { Advanced, Card, KeyValues, Mono, Notice, PageHeader } from "@/components/ui/card";
import { CopyButton } from "@/components/ui/copy-button";
import { ErrorState, SkeletonRows } from "@/components/ui/states";
import { PriorityBadge } from "@/components/handoff/handoff-queue";
import { DecisionExplanation } from "@/components/decision/decision-explanation";
import { summarizeTraceDecision } from "@/components/trace/trace-decision";
import { TraceTimeline } from "@/components/trace/trace-timeline";
import type { Action, AgentTrace } from "@/lib/api/types";
import type { ErrorInfo } from "@/lib/errors";
import { explainResult, explainTrace } from "@/lib/explain";
import { dateTime, duration, relativeTime, shortId } from "@/lib/format";
import {
  RISK_FLAG_LABELS,
  intentLabel,
  reasonMeta,
} from "@/lib/labels";
import { useStoredResults } from "@/lib/results-store";
import {
  ConversationRow,
  conversationTitle,
  nextActionText,
  queueCategory,
  rowFromStored,
  whyNeedsHuman,
} from "@/lib/rows";
import { useHydrated } from "@/lib/use-hydrated";

function getWhyHumanDetails(row: ConversationRow, packetReason?: string): { headline: string; explanation: string } {
  const code = row.reasonCode;

  if (code === "prompt_injection") {
    return {
      headline: "Prompt injection detected",
      explanation: "Automated handling was stopped because the request raised a security concern. No automated response was sent to the customer.",
    };
  }
  if (code === "safety") {
    return {
      headline: "Security concern",
      explanation: "Automated handling was stopped because the request requires human safety review. No automated response was sent to the customer.",
    };
  }
  if (code === "insufficient_evidence" || code === "no_evidence" || row.evidenceSufficient === false) {
    return {
      headline: "Insufficient historical evidence",
      explanation: "Automated handling was stopped because no proven historical resolution was available. No automated response was sent to the customer.",
    };
  }
  if (code === "human_requested") {
    return {
      headline: "Customer requested human support",
      explanation: "Automated handling was stopped because the customer explicitly asked to speak with a human agent. No automated response was sent to the customer.",
    };
  }
  if (code === "payment_billing") {
    return {
      headline: "Billing or payment inquiry",
      explanation: "Automated handling was stopped because the request involves billing or payment authorization requiring human review. No automated response was sent to the customer.",
    };
  }
  if (code === "account_access" || code === "private_info" || code === "sensitive_action") {
    return {
      headline: "Sensitive account authorization",
      explanation: "Automated handling was stopped because the request requires human authorization and verification of sensitive account credentials. No automated response was sent to the customer.",
    };
  }
  if (code === "repeat_contact" || (row.riskFlags && row.riskFlags.includes("repeat_contact"))) {
    return {
      headline: "Repeat contact threshold reached",
      explanation: "Automated handling was stopped because the customer has contacted support multiple times regarding this issue. No automated response was sent to the customer.",
    };
  }
  if (code === "hardware") {
    return {
      headline: "Hardware & repair diagnostics",
      explanation: "Automated handling was stopped because hardware diagnostics and repair requests require direct human specialist assistance. No automated response was sent to the customer.",
    };
  }
  if (code === "conflicting_evidence") {
    return {
      headline: "Conflicting resolution evidence",
      explanation: "Automated handling was stopped because conflicting historical resolutions were found. No automated response was sent to the customer.",
    };
  }
  if (code === "grounding_failed" || code === "verification_failed") {
    return {
      headline: "Draft verification failed",
      explanation: "Automated handling was stopped because the drafted response did not meet verification safety checks. No automated response was sent to the customer.",
    };
  }
  if (code === "llm_unavailable" || code === "model_timeout") {
    return {
      headline: "Model unavailable",
      explanation: "Automated handling was stopped because the model service timed out or was temporarily unavailable. No automated response was sent to the customer.",
    };
  }
  if (code === "dependency_failure") {
    return {
      headline: "System dependency failed",
      explanation: "Automated handling was stopped because a backend dependency was temporarily unavailable. No automated response was sent to the customer.",
    };
  }
  if (code === "legal_media") {
    return {
      headline: "Legal or media sensitivity",
      explanation: "Automated handling was stopped because the request touches legal or regulatory compliance topics. No automated response was sent to the customer.",
    };
  }
  if (code === "abusive_threatening") {
    return {
      headline: "Content policy violation",
      explanation: "Automated handling was stopped because the request was flagged by content safety policies. No automated response was sent to the customer.",
    };
  }

  return {
    headline: whyNeedsHuman(row),
    explanation: packetReason || "Automated handling was stopped because ResolveAI determined this request requires human review. No automated response was sent to the customer.",
  };
}

export function HandoffDetail({
  traceId,
  trace,
  traceError,
}: {
  traceId: string;
  trace: AgentTrace | null;
  traceError: ErrorInfo | null;
}) {
  const hydrated = useHydrated();
  const stored = useStoredResults().find((s) => s.traceId === traceId);

  const row = useMemo<ConversationRow | null>(() => {
    if (stored) return rowFromStored(stored);
    if (trace) {
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
  }, [stored, trace]);

  if (!hydrated) return <SkeletonRows rows={6} />;

  const packet = stored?.result.handoff ?? null;
  const reason = reasonMeta(row?.reasonCode);
  const title = row
    ? packet?.customer_issue || conversationTitle(row)
    : `Handoff ${shortId(traceId)}`;

  const why = row ? getWhyHumanDetails(row, packet?.reason?.reason) : { headline: "Human handoff required", explanation: "Automated handling was stopped because this request requires human review." };
  const nextAction = row ? nextActionText(row) : "Review case and assist customer";
  const flags = row?.riskFlags.map((f) => RISK_FLAG_LABELS[f] ?? f) ?? [];

  const copyText = row
    ? [
        "HANDOFF SUMMARY",
        "",
        "Customer request",
        title,
        "",
        "Why ResolveAI stopped",
        `${why.headline}. ${why.explanation}`,
        "",
        "Evidence",
        row.evidenceSufficient === true
          ? "Historical resolution pattern available for reference."
          : "Insufficient historical evidence for a safe automatic resolution.",
        "",
        "Risk",
        flags.length ? flags.join(" · ") : "None detected",
        "",
        "Recommended next action",
        nextAction,
      ].join("\n")
    : "";

  const backLink = (
    <div className="mb-4">
      <Link
        href="/handoffs"
        className="inline-flex items-center gap-1.5 text-xs font-medium text-ink-3 hover:text-ink transition-colors"
      >
        <ArrowLeft className="size-3.5" aria-hidden="true" />
        Back to Handoffs
      </Link>
    </div>
  );

  const header = (
    <PageHeader
      eyebrow={
        <div className="flex items-center gap-2">
          <span className="font-semibold text-brand-700">HUMAN HANDOFF</span>
          <PriorityBadge severity={reason.severity} />
        </div>
      }
      title={title}
      description="ResolveAI has prepared this case for human review."
      actions={
        <>
          <ButtonLink href={`/conversations/${traceId}`} icon={MessagesSquare} variant="primary">
            Open conversation
          </ButtonLink>
          <CopyButton text={copyText} label="Copy handoff summary" variant="secondary" />
          <ButtonLink href={`/traces/${traceId}`} icon={Activity} variant="secondary">
            Audit log
          </ButtonLink>
        </>
      }
    />
  );

  const action = stored?.result.action ?? trace?.final_decision;
  if (action && action !== "HUMAN_HANDOFF") {
    return (
      <>
        {backLink}
        {header}
        <Notice tone="info" title="This conversation was not handed off">
          ResolveAI decided {action === "AUTO_HANDLE" ? "to auto-handle it" : "to ask a clarifying question"}, so no handoff packet was created. Open the conversation workspace for the full decision.
        </Notice>
      </>
    );
  }

  if (row) {
    const explanation = stored ? explainResult(stored.result) : trace ? explainTrace(trace) : null;

    return (
      <>
        {backLink}
        {header}
        <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_320px]">
          {/* Main Column: ~70-75% */}
          <div className="min-w-0 space-y-4">
            {/* 1. Case summary */}
            <Card title="Case summary" headingLevel={2}>
              <div className="space-y-3">
                {stored ? (
                  <p className="text-[14px] leading-relaxed text-ink">
                    {stored.result.conversation.message.text}
                  </p>
                ) : (
                  <p className="text-[14px] leading-relaxed text-ink">
                    ResolveAI classified this request as{" "}
                    <span className="font-semibold text-ink">
                      {row.intent ? intentLabel(row.intent) : "an inquiry"}
                    </span>{" "}
                    and routed it to the{" "}
                    <span className="font-semibold text-ink">{queueCategory(row)}</span> queue for human review.
                  </p>
                )}

                <div className="flex flex-wrap items-center gap-3 pt-1 text-[12px] text-ink-3">
                  <span className="inline-flex items-center rounded border border-line bg-subtle px-2 py-0.5 font-medium text-ink-3">
                    Audit record · message text not stored
                  </span>
                  <span>Channel: <span className="text-ink-2">{row.channel || "Support web"}</span></span>
                  <span>Language: <span className="text-ink-2">en-US</span></span>
                </div>

                {packet?.unresolved_questions?.length ? (
                  <div className="border-t border-line/60 pt-3">
                    <h3 className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-ink-3">
                      Unresolved questions
                    </h3>
                    <ul className="list-disc space-y-1 pl-4 text-[13px] text-ink-2">
                      {packet.unresolved_questions.map((q) => (
                        <li key={q}>{q}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}

                {packet?.suggested_opening ? (
                  <div className="border-t border-line/60 pt-3">
                    <h3 className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-ink-3">
                      Suggested opening message
                    </h3>
                    <blockquote className="rounded-md border border-line bg-canvas px-3 py-2 text-[13px] text-ink-2">
                      {packet.suggested_opening}
                    </blockquote>
                  </div>
                ) : null}
              </div>
            </Card>

            {/* 2. Why this needs a human (Hero Card) */}
            <section aria-labelledby="why-human-title" className="rounded-lg border border-line bg-surface p-5 shadow-[0_1px_2px_rgba(15,23,42,0.04)]">
              <div className="text-[11px] font-semibold uppercase tracking-wider text-ink-3">
                <span id="why-human-title">Why this needs a human</span>
              </div>
              <div className="mt-2 flex items-center gap-2">
                <span className="size-2 shrink-0 rounded-full bg-[#D9B4B0]" aria-hidden="true" />
                <h2 className="text-base font-semibold text-ink">
                  {why.headline}
                </h2>
              </div>
              <p className="mt-2 text-[14px] leading-relaxed text-ink-2">
                {why.explanation}
              </p>
            </section>

            {/* 3. What ResolveAI found */}
            <Card title="What ResolveAI found" headingLevel={2}>
              <div className="grid gap-3 sm:grid-cols-3">
                {/* Intent */}
                <div className="rounded-md border border-line bg-canvas/60 p-3.5">
                  <div className="text-[11px] font-semibold uppercase tracking-wider text-ink-3">Intent</div>
                  <div className="mt-1.5 text-[14px] font-medium text-ink">
                    {row.intent ? intentLabel(row.intent) : "Unclassified"}
                  </div>
                  {row.confidence !== null ? (
                    <div className="mt-1 text-[12px] text-ink-3 tabular">
                      {(row.confidence * 100).toFixed(1)}% confidence
                    </div>
                  ) : null}
                </div>

                {/* Evidence */}
                <div className="rounded-md border border-line bg-canvas/60 p-3.5">
                  <div className="text-[11px] font-semibold uppercase tracking-wider text-ink-3">Evidence</div>
                  <div className="mt-1.5 text-[14px] font-medium text-ink">
                    {row.evidenceSufficient === true ? "Sufficient historical evidence" : "Insufficient historical evidence"}
                  </div>
                  <div className="mt-1 text-[12px] text-ink-3">
                    {row.evidenceSufficient === true
                      ? "Historical resolution pattern available for reference."
                      : "Not enough trusted historical evidence for a safe automatic resolution."}
                  </div>
                </div>

                {/* Risk */}
                <div className="rounded-md border border-line bg-canvas/60 p-3.5">
                  <div className="text-[11px] font-semibold uppercase tracking-wider text-ink-3">Risk</div>
                  {flags.length > 0 ? (
                    <ul className="mt-1.5 space-y-1">
                      {flags.map((flag) => (
                        <li key={flag} className="flex items-center gap-1.5 text-[13px] text-ink-2">
                          <span className="size-1.5 shrink-0 rounded-full bg-[#D9B4B0]" aria-hidden="true" />
                          <span>{flag}</span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <div className="mt-1.5 text-[13px] text-ink-3">
                      No active risk signals detected
                    </div>
                  )}
                </div>
              </div>
            </Card>

            {/* 4. Recommended next action */}
            <Card title="Recommended next action" headingLevel={2}>
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="space-y-1">
                  <p className="text-[15px] font-semibold text-ink">{nextAction}</p>
                  <p className="text-[13px] text-ink-3">
                    No automated reply was sent. Review the case and take ownership of the conversation.
                  </p>
                </div>
                <div className="flex shrink-0 flex-wrap items-center gap-2">
                  <ButtonLink href={`/conversations/${traceId}`} icon={MessagesSquare} variant="primary">
                    Open conversation
                  </ButtonLink>
                  <CopyButton text={copyText} label="Copy handoff summary" variant="secondary" />
                </div>
              </div>
            </Card>

            {/* 5. Handoff summary (Support-agent note format) */}
            <Card
              title="Handoff summary"
              description="Structured human-readable brief prepared for support handoff."
              actions={<CopyButton text={copyText} label="Copy summary" variant="secondary" />}
              headingLevel={2}
            >
              <div className="rounded-md border border-line bg-canvas/60 p-4 space-y-3 text-[13px]">
                <div>
                  <span className="block text-[11px] font-semibold uppercase tracking-wider text-ink-3">Customer request</span>
                  <p className="mt-0.5 text-ink font-medium">{title}</p>
                </div>
                <div>
                  <span className="block text-[11px] font-semibold uppercase tracking-wider text-ink-3">Why ResolveAI stopped</span>
                  <p className="mt-0.5 text-ink-2">{why.headline}. {why.explanation}</p>
                </div>
                <div>
                  <span className="block text-[11px] font-semibold uppercase tracking-wider text-ink-3">Evidence</span>
                  <p className="mt-0.5 text-ink-2">
                    {row.evidenceSufficient === true
                      ? "Historical resolution pattern available for reference."
                      : "Insufficient historical evidence for a safe automatic resolution."}
                  </p>
                </div>
                <div>
                  <span className="block text-[11px] font-semibold uppercase tracking-wider text-ink-3">Risk</span>
                  <p className="mt-0.5 text-ink-2">
                    {flags.length ? flags.join(" · ") : "None detected"}
                  </p>
                </div>
                <div>
                  <span className="block text-[11px] font-semibold uppercase tracking-wider text-ink-3">Recommended next action</span>
                  <p className="mt-0.5 text-ink font-medium">{nextAction}</p>
                </div>
              </div>
            </Card>

            {/* 6. Advanced technical & audit details */}
            <Card title="Advanced technical & audit details" headingLevel={2}>
              <p className="text-[13px] text-ink-3">
                Engineering details, policy versions, and execution records for debugging and audit.
              </p>
              <Advanced label="Advanced technical & audit details">
                <div className="space-y-4 pt-2">
                  <KeyValues
                    columns={2}
                    items={[
                      { label: "Trace ID", value: <Mono>{row.traceId}</Mono> },
                      { label: "Request ID", value: <Mono>{row.requestId || "n/a"}</Mono> },
                      { label: "Policy rule", value: <Mono>{row.rule || "n/a"}</Mono> },
                      { label: "Policy version", value: <Mono>{row.policyVersion || "n/a"}</Mono> },
                      {
                        label: "Total latency",
                        value: row.latencyMs ? duration(row.latencyMs) : "under 1s",
                      },
                      ...(row.llmCalls !== null ? [{ label: "Model calls", value: `${row.llmCalls}` }] : []),
                      ...(row.estimatedCostUsd !== null ? [{ label: "Estimated cost", value: `$${row.estimatedCostUsd.toFixed(4)}` }] : []),
                      ...(row.error ? [{ label: "Failure code", value: <span className="text-danger">{row.error}</span> }] : []),
                    ]}
                  />

                  {explanation ? (
                    <div className="pt-2">
                      <DecisionExplanation explanation={explanation} />
                    </div>
                  ) : null}

                  {trace ? (
                    <div className="pt-2">
                      <div className="mb-2 text-xs font-semibold text-ink">Recorded pipeline timeline</div>
                      <TraceTimeline events={trace.events} stageStatus={trace.stage_status} latency={trace.latency_ms} />
                    </div>
                  ) : null}
                </div>
              </Advanced>
            </Card>
          </div>

          {/* Right Rail: ~25-30% */}
          <div className="min-w-0 space-y-4">
            {/* Case */}
            <Card title="Case" headingLevel={3}>
              <div className="divide-y divide-line/60 text-[13px]">
                <div className="flex items-center justify-between py-2">
                  <span className="text-ink-3">Priority</span>
                  <PriorityBadge severity={reason.severity} />
                </div>
                <div className="flex items-center justify-between py-2">
                  <span className="text-ink-3">Queue</span>
                  <span className="font-medium text-ink">{queueCategory(row)}</span>
                </div>
                <div className="flex items-center justify-between py-2">
                  <span className="text-ink-3">Intent</span>
                  <span className="font-medium text-ink">{row.intent ? intentLabel(row.intent) : "Unclassified"}</span>
                </div>
                <div className="flex items-center justify-between py-2">
                  <span className="text-ink-3">Risk</span>
                  <span className={`font-medium ${flags.length ? (reason.severity === "high" ? "text-danger" : "text-ink") : "text-ink"}`}>
                    {flags.length ? (reason.severity === "high" ? "High" : "Elevated") : "Normal"}
                  </span>
                </div>
                <div className="flex items-center justify-between py-2">
                  <span className="text-ink-3">Evidence</span>
                  <span className="font-medium text-ink">
                    {row.evidenceSufficient === true ? "Sufficient" : "Limited"}
                  </span>
                </div>
                <div className="flex items-center justify-between py-2">
                  <span className="text-ink-3">Escalated</span>
                  <span className="font-medium text-ink" title={dateTime(row.startedAt)}>{relativeTime(row.startedAt)}</span>
                </div>
              </div>
            </Card>

            {/* Actions */}
            <Card title="Actions" headingLevel={3}>
              <div className="space-y-2">
                <ButtonLink
                  href={`/conversations/${traceId}`}
                  icon={MessagesSquare}
                  variant="primary"
                  className="w-full justify-center"
                >
                  Open conversation
                </ButtonLink>
                <div className="w-full">
                  <CopyButton text={copyText} label="Copy handoff summary" variant="secondary" />
                </div>
                <ButtonLink
                  href={`/traces/${traceId}`}
                  icon={Activity}
                  variant="ghost"
                  className="w-full justify-center"
                >
                  Audit log
                </ButtonLink>
              </div>
            </Card>
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      {backLink}
      {header}
      {traceError ? <ErrorState error={traceError} retry={<ButtonLink href="/handoffs">Handoffs</ButtonLink>} /> : null}
    </>
  );
}
