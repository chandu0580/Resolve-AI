"use client";

import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  HelpCircle,
  ShieldAlert,
  Sparkles,
  UserCheck,
  UserRound,
  Zap,
} from "lucide-react";
import { useState } from "react";
import type { SupportConversation } from "./inbox-seed-data";
import { duration, usd } from "@/lib/format";
import { intentLabel, reasonMeta } from "@/lib/labels";

interface InboxAiPanelProps {
  conversation: SupportConversation;
  isAnalyzing: boolean;
  onTakeOver: () => void;
}

export function InboxAiPanel({
  conversation,
  isAnalyzing,
  onTakeOver,
}: InboxAiPanelProps) {
  const [showEvidence, setShowEvidence] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);

  const res = conversation.resolveResponse;
  const isHumanActive =
    conversation.isHumanHandled || conversation.status === "HUMAN_HANDLING";

  // Derive display status
  const getDisplayStatus = () => {
    if (isAnalyzing) return "ANALYZING";
    if (isHumanActive) return "HUMAN_HANDLING";
    if (conversation.status === "RESOLVED") return "RESOLVED";
    if (conversation.status === "NEEDS_HUMAN") return "HUMAN_HANDOFF";
    if (conversation.status === "NEEDS_CLARIFICATION") return "CLARIFICATION";
    return "AI_HANDLING";
  };

  const status = getDisplayStatus();

  // Intent & Confidence
  const intentName = res
    ? intentLabel(res.intent.intent)
    : conversation.subject.includes("autocorrect")
    ? "Keyboard & text input bug"
    : conversation.subject.includes("password")
    ? "Account & security access"
    : conversation.subject.includes("battery")
    ? "Battery & power drainage"
    : "Support troubleshooting";

  const confidence = res ? Math.round((res.intent.confidence ?? 0.88) * 100) : 94;
  const band = res?.intent.confidence_band ?? "HIGH";

  // Cited historical cases
  const evidenceItems = res?.evidence.items ?? [];
  const citedRefs = res?.response.evidence_refs ?? [];
  const citedCases =
    evidenceItems.filter((e) => citedRefs.some((r) => r.evidence_id === e.evidence_id)) || [];

  return (
    <div className="flex h-full flex-col border-l border-line bg-surface overflow-y-auto">
      {/* Sidebar Header */}
      <div className="border-b border-line px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sparkles className="size-4 text-brand-600" />
          <h2 className="text-[12px] font-bold tracking-wider text-ink-3 uppercase">
            ResolveAI
          </h2>
        </div>

        {/* Product Status Pill */}
        {status === "ANALYZING" ? (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-brand-50 border border-brand-100 px-2.5 py-0.5 text-[11px] font-medium text-brand-700">
            <span className="size-1.5 animate-pulse rounded-full bg-brand-600" />
            Analyzing
          </span>
        ) : status === "HUMAN_HANDLING" ? (
          <span className="inline-flex items-center gap-1 rounded-full border border-info-line bg-info-bg px-2.5 py-0.5 text-[11px] font-medium text-info">
            <UserCheck className="size-3 text-info" />
            Human handling
          </span>
        ) : status === "AI_HANDLING" ? (
          <span className="inline-flex items-center gap-1 rounded-full border border-brand-100 bg-brand-50 px-2.5 py-0.5 text-[11px] font-medium text-brand-700">
            <CheckCircle2 className="size-3 text-brand-600" />
            AI handling
          </span>
        ) : status === "CLARIFICATION" ? (
          <span className="inline-flex items-center gap-1 rounded-full border border-warning-line bg-warning-bg px-2.5 py-0.5 text-[11px] font-medium text-warning">
            <HelpCircle className="size-3 text-warning" />
            Needs clarification
          </span>
        ) : status === "HUMAN_HANDOFF" ? (
          <span className="inline-flex items-center gap-1 rounded-full border border-danger-line bg-danger-bg px-2.5 py-0.5 text-[11px] font-medium text-danger">
            <ShieldAlert className="size-3 text-danger" />
            Needs human
          </span>
        ) : (
          <span className="inline-flex items-center gap-1 rounded-full border border-line bg-subtle px-2.5 py-0.5 text-[11px] font-medium text-ink-3">
            Resolved
          </span>
        )}
      </div>

      <div className="flex-1 p-4 space-y-4 divide-y divide-line/70">
        {/* SECTION 1: UNDERSTANDING */}
        <div className="space-y-2">
          <p className="text-[11px] font-bold tracking-wider text-ink-3 uppercase">
            Understanding
          </p>

          <div className="rounded-lg border border-line/80 bg-canvas/60 p-3 space-y-2">
            <div>
              <span className="text-[11px] text-ink-3">Classified Intent</span>
              <p className="text-[13px] font-semibold text-ink">{intentName}</p>
            </div>

            <div className="flex items-center justify-between border-t border-line/60 pt-2">
              <span className="text-[11px] text-ink-3">Confidence</span>
              <span className="inline-flex items-center gap-1.5 text-[12px] font-medium text-ink">
                <span
                  className={`size-2 rounded-full ${
                    band === "HIGH" ? "bg-brand-600" : band === "MEDIUM" ? "bg-warning" : "bg-danger"
                  }`}
                />
                {band} ({confidence}%)
              </span>
            </div>

            {res?.risk.summary && (
              <div className="border-t border-line/60 pt-2">
                <span className="text-[11px] text-ink-3">Summary</span>
                <p className="mt-0.5 text-[12px] leading-relaxed text-ink-2">
                  {res.risk.summary}
                </p>
              </div>
            )}
          </div>
        </div>

        {/* SECTION 2: EVIDENCE */}
        <div className="pt-4 space-y-2">
          <div className="flex items-center justify-between">
            <p className="text-[11px] font-bold tracking-wider text-ink-3 uppercase">
              Evidence
            </p>
            <span className="text-[11px] font-medium text-ink-3">
              {citedCases.length > 0 ? `${citedCases.length} verified cases` : "3 historical cases"}
            </span>
          </div>

          <div className="rounded-lg border border-line/80 bg-canvas/60 p-3 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[12px] font-medium text-ink">
                {res?.evidence.sufficiency_level === "STRONG" || !res
                  ? "Strong historical grounding"
                  : res?.evidence.sufficiency_level === "WEAK"
                  ? "Weak historical support"
                  : "Insufficient evidence"}
              </span>
              <span className="rounded bg-brand-50 border border-brand-100 px-1.5 py-0.5 text-[10px] font-semibold text-brand-700">
                {res?.evidence.sufficiency_level || "STRONG"}
              </span>
            </div>

            <p className="text-[11px] leading-relaxed text-ink-3">
              Replies must match verified AppleSupport troubleshooting resolutions that predate the customer query.
            </p>

            {citedCases.length > 0 && (
              <div className="pt-1">
                <button
                  type="button"
                  onClick={() => setShowEvidence(!showEvidence)}
                  className="flex items-center gap-1 text-[12px] font-medium text-brand-700 hover:underline"
                >
                  {showEvidence ? <ChevronDown className="size-3.5" /> : <ChevronRight className="size-3.5" />}
                  {showEvidence ? "Hide cited cases" : "View cited historical cases"}
                </button>

                {showEvidence && (
                  <div className="mt-2 space-y-2 border-t border-line/70 pt-2">
                    {citedCases.map((c) => (
                      <div
                        key={c.evidence_id}
                        className="rounded border border-line bg-surface p-2 text-[11px] space-y-1"
                      >
                        <div className="flex items-center justify-between font-mono text-[10px] text-brand-700">
                          <span>Case #{c.evidence_id}</span>
                          <span>
                            Relevance:{" "}
                            {c.quality?.semantic_relevance
                              ? Math.round(c.quality.semantic_relevance * 100)
                              : 88}
                            %
                          </span>
                        </div>
                        <p className="line-clamp-2 text-ink-2">{c.brand_reply}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* SECTION 3: DECISION & REASON */}
        <div className="pt-4 space-y-2">
          <p className="text-[11px] font-bold tracking-wider text-ink-3 uppercase">
            Decision
          </p>

          {status === "AI_HANDLING" ? (
            <div className="rounded-lg border border-brand-100 bg-brand-50/50 p-3 space-y-1.5">
              <div className="flex items-center gap-1.5 text-[13px] font-semibold text-brand-700">
                <CheckCircle2 className="size-4 text-brand-600" />
                Resolve automatically
              </div>
              <p className="text-[12px] leading-relaxed text-ink-2">
                Relevant historical resolution found with sufficient grounding and no safety concerns.
              </p>
            </div>
          ) : status === "CLARIFICATION" ? (
            <div className="rounded-lg border border-warning-line bg-warning-bg/60 p-3 space-y-1.5">
              <div className="flex items-center gap-1.5 text-[13px] font-semibold text-warning">
                <HelpCircle className="size-4 text-warning" />
                Ask for clarification
              </div>
              <p className="text-[12px] leading-relaxed text-ink-2">
                Symptom is ambiguous. ResolveAI asks one targeted question rather than guessing.
              </p>
            </div>
          ) : status === "HUMAN_HANDLING" ? (
            <div className="rounded-lg border border-info-line bg-info-bg/50 p-3 space-y-1.5">
              <div className="flex items-center gap-1.5 text-[13px] font-semibold text-info">
                <UserRound className="size-4 text-info" />
                Assigned to Support team
              </div>
              <p className="text-[12px] leading-relaxed text-ink-2">
                Human takeover is active. AI will not send autonomous replies in this thread.
              </p>
            </div>
          ) : (
            /* Human Handoff */
            <div className="rounded-lg border border-danger-line bg-danger-bg/50 p-3 space-y-2">
              <div className="flex items-center gap-1.5 text-[13px] font-semibold text-danger">
                <ShieldAlert className="size-4 text-danger" />
                Human handoff required
              </div>
              <p className="text-[12px] font-medium text-ink-2">
                Reason:{" "}
                <span className="text-danger">
                  {conversation.handoffReason || "Policy security escalation"}
                </span>
              </p>

              <div className="border-t border-danger-line/60 pt-2 text-[11px] text-ink-2 space-y-1">
                <p className="font-semibold text-ink">Handoff prepared with:</p>
                <div className="grid grid-cols-2 gap-1 text-[10px] text-ink-3">
                  <span>✓ Conversation history</span>
                  <span>✓ Issue summary</span>
                  <span>✓ Detected intent</span>
                  <span>✓ Risk signals</span>
                  <span>✓ Relevant evidence</span>
                  <span>✓ Next action</span>
                </div>
              </div>

              {!isHumanActive && (
                <div className="pt-1">
                  <button
                    type="button"
                    onClick={onTakeOver}
                    className="w-full inline-flex items-center justify-center gap-1.5 rounded-md bg-danger py-1.5 text-[12px] font-semibold text-surface hover:opacity-90 transition-opacity"
                  >
                    <UserCheck className="size-3.5" />
                    Take over conversation
                  </button>
                </div>
              )}
            </div>
          )}
        </div>

        {/* SECTION 4: ADVANCED DISCLOSURE */}
        <div className="pt-4">
          <button
            type="button"
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="flex w-full items-center justify-between text-[11px] font-semibold text-ink-3 hover:text-ink transition-colors"
          >
            <span>Advanced / Audit details</span>
            {showAdvanced ? <ChevronDown className="size-3.5" /> : <ChevronRight className="size-3.5" />}
          </button>

          {showAdvanced && (
            <div className="mt-2.5 rounded-lg border border-line bg-canvas p-3 text-[11px] space-y-2 font-mono text-ink-3">
              <div className="flex justify-between">
                <span>Trace ID:</span>
                <span className="truncate max-w-[160px]">{res?.trace_id || conversation.traceId || "trace-local"}</span>
              </div>
              <div className="flex justify-between">
                <span>Pipeline:</span>
                <span>{res?.versions.pipeline || "pipeline-v6.3"}</span>
              </div>
              <div className="flex justify-between">
                <span>Policy rule:</span>
                <span>{res?.outcome.rule || "policy-v3.3"}</span>
              </div>
              <div className="flex justify-between">
                <span>Total latency:</span>
                <span>{res ? duration(res.latency_ms.total) : "cached"}</span>
              </div>
              <div className="flex justify-between">
                <span>Model calls:</span>
                <span>{res ? `${res.usage.llm_calls} (${usd(res.usage.estimated_cost_usd)})` : "0 ($0.00)"}</span>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
