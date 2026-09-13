/**
 * List rows for Conversations, Handoffs and Overview: the API's trace summaries, enriched with the full result when this
 * browser ran the conversation (traces never store customer text). Nothing is inferred beyond what either source recorded.
 */
import type { Action, TraceSummary } from "@/lib/api/types";
import { activeRiskFlags } from "@/lib/handoff-summary";
import { HARD_BLOCK_FLAGS, handoffCategory, intentLabel, reasonMeta, type QueueCategory } from "@/lib/labels";
import type { StoredResult } from "@/lib/results-store";
import { foldForMatch } from "@/lib/text";

export interface ConversationRow {
  traceId: string;
  requestId: string;
  startedAt: string;
  action: Action | null;
  reasonCode: string | null;
  intent: string | null;
  confidence: number | null;
  band: string | null;
  evidenceLevel: string | null;
  evidenceSufficient: boolean | null;
  riskFlags: string[];
  rule: string | null;
  policyVersion: string | null;
  latencyMs: number | null;
  llmCalls: number | null;
  estimatedCostUsd: number | null;
  channel: string | null;
  error: string | null;
  preview: string | null;
  stored: StoredResult | null;
  inTraceList: boolean;
}

/**
 * A readable title for a conversation row. Live rows this browser ran carry the customer's own words; audit-only records
 * never store customer text (by design), so they are named by what the agent understood and decided instead of repeating an
 * apology on every line.
 */
export function conversationTitle(row: ConversationRow): string {
  if (row.preview) return row.preview;
  const intent = row.intent ? intentLabel(row.intent) : null;
  if (intent && row.intent !== "other") return `${intent} request`;
  if (row.action === "HUMAN_HANDOFF" && row.reasonCode) return `${reasonMeta(row.reasonCode).label} — escalated`;
  return "Support conversation";
}

/** Shown once, quietly, where a row has no customer text. */
export const NO_TEXT_NOTE = "Audit record — message text is never stored";

export function rowFromSummary(s: TraceSummary, stored?: StoredResult): ConversationRow {
  return {
    traceId: s.trace_id,
    requestId: s.request_id ?? "",
    startedAt: s.started_at,
    action: (s.final_decision as Action | null | undefined) ?? null,
    reasonCode: s.reason_code ?? null,
    intent: s.intent ?? null,
    confidence: s.intent_confidence ?? null,
    band: s.confidence_band ?? null,
    evidenceLevel: s.evidence_level ?? null,
    evidenceSufficient: s.evidence_sufficient ?? null,
    riskFlags: s.risk_flags ?? [],
    rule: s.rule ?? null,
    policyVersion: s.policy_version ?? null,
    latencyMs: s.latency_ms ?? null,
    llmCalls: s.llm_calls ?? null,
    estimatedCostUsd: s.estimated_cost_usd ?? null,
    channel: s.channel ?? null,
    error: s.error ?? null,
    preview: stored ? stored.result.conversation.message.text : null,
    stored: stored ?? null,
    inTraceList: true,
  };
}

export function rowFromStored(st: StoredResult): ConversationRow {
  const r = st.result;
  return {
    traceId: r.trace_id,
    requestId: r.request_id,
    startedAt: st.savedAt,
    action: r.action,
    reasonCode: r.outcome.reason_code,
    intent: r.intent.intent,
    confidence: r.intent.confidence,
    band: r.intent.confidence_band,
    evidenceLevel: r.evidence.sufficiency_level,
    evidenceSufficient: r.evidence.sufficient,
    riskFlags: activeRiskFlags(r.risk as unknown as Record<string, unknown>),
    rule: r.outcome.rule,
    policyVersion: r.outcome.policy_version,
    latencyMs: r.latency_ms.total ?? null,
    llmCalls: r.usage.llm_calls,
    estimatedCostUsd: r.usage.estimated_cost_usd ?? null,
    channel: null,
    error: null,
    preview: r.conversation.message.text,
    stored: st,
    inTraceList: false,
  };
}

const time = (iso: string) => {
  const t = Date.parse(iso);
  return Number.isNaN(t) ? 0 : t;
};

export function mergeRows(summaries: TraceSummary[] | null, stored: StoredResult[]): ConversationRow[] {
  const byId = new Map(stored.map((s) => [s.traceId, s]));
  const rows = (summaries ?? []).map((s) => rowFromSummary(s, byId.get(s.trace_id)));
  const seen = new Set(rows.map((r) => r.traceId));
  for (const st of stored) if (!seen.has(st.traceId)) rows.push(rowFromStored(st));
  return rows.sort((a, b) => time(b.startedAt) - time(a.startedAt));
}

const SENSITIVE_CODES = new Set(["safety", "account_access", "payment_billing", "private_info", "legal_media", "prompt_injection", "abusive_threatening"]);

export function humanReason(row: ConversationRow): string {
  if (row.action === "AUTO_HANDLE") {
    return "Strong historical evidence";
  }
  if (row.action === "CLARIFICATION_REQUIRED") {
    if (row.reasonCode === "insufficient_context" || row.reasonCode === "low_confidence" || row.reasonCode === "vague") {
      return "Issue details are incomplete";
    }
    if (row.reasonCode) {
      return reasonMeta(row.reasonCode).label;
    }
    return "Issue details are incomplete";
  }
  if (row.action === "HUMAN_HANDOFF") {
    if (row.evidenceSufficient === false || row.reasonCode === "insufficient_evidence" || row.reasonCode === "no_evidence" || row.reasonCode === "conflicting_evidence" || row.reasonCode === "grounding_failed") {
      return "Insufficient evidence";
    }
    if (row.reasonCode === "safety") {
      return "Safety or security concern";
    }
    if (row.reasonCode && SENSITIVE_CODES.has(row.reasonCode)) {
      if (row.reasonCode === "account_access" || row.reasonCode === "payment_billing" || row.reasonCode === "private_info" || row.reasonCode === "sensitive_action") {
        return "Sensitive request";
      }
      return reasonMeta(row.reasonCode).label;
    }
    if (row.riskFlags && row.riskFlags.includes("repeat_contact")) {
      return "Repeated failed attempts";
    }
    if (row.reasonCode) {
      return reasonMeta(row.reasonCode).label;
    }
    return "Human review required";
  }
  return "System exception";
}

export function conversationSubtitle(row: ConversationRow): string {
  if (row.preview) return row.preview;
  if (row.evidenceSufficient === false) return "Needs more evidence";
  if (row.action === "AUTO_HANDLE") return "Historical resolution cited";
  if (row.reasonCode === "safety") return "Safety check required";
  if (row.reasonCode === "account_access" || row.reasonCode === "payment_billing") return "Requires human authorization";
  if (row.riskFlags && row.riskFlags.includes("repeat_contact")) return "Customer repeated request";
  if (row.reasonCode) return reasonMeta(row.reasonCode).label;
  return "Customer support request";
}

export function whyNeedsHuman(row: ConversationRow): string {
  if (row.reasonCode === "prompt_injection") return "Prompt injection detected";
  if (row.reasonCode === "safety") return "Security concern";
  if (row.reasonCode === "payment_billing") return "Sensitive billing inquiry";
  if (row.reasonCode === "account_access") return "Account access & authorization";
  if (row.reasonCode === "sensitive_action") return "Sensitive account action";
  if (row.reasonCode === "private_info") return "Requires private identifiers";
  if (row.reasonCode === "repeat_contact") return "Repeat contact threshold reached";
  if (row.reasonCode === "hardware") return "Hardware or repair request";
  if (row.reasonCode === "human_requested") return "Customer requested human agent";
  if (row.reasonCode === "llm_unavailable" || row.reasonCode === "model_timeout") return "Model unavailable";
  if (row.reasonCode === "dependency_failure") return "System dependency failed";
  if (row.reasonCode === "insufficient_evidence" || row.reasonCode === "no_evidence") return "Insufficient evidence";
  if (row.reasonCode === "conflicting_evidence") return "Conflicting resolution evidence";
  if (row.reasonCode === "grounding_failed" || row.reasonCode === "verification_failed") return "Draft verification failed";
  if (row.reasonCode === "legal_media") return "Legal or media threat";
  if (row.reasonCode === "abusive_threatening") return "Abusive content";
  return reasonMeta(row.reasonCode).label;
}

export function nextActionText(row: ConversationRow): string {
  if (row.stored?.result.handoff?.recommended_next_action) {
    return row.stored.result.handoff.recommended_next_action;
  }
  switch (row.reasonCode) {
    case "prompt_injection":
    case "safety":
      return "Review security concern";
    case "payment_billing":
      return "Verify customer billing information";
    case "account_access":
    case "private_info":
    case "sensitive_action":
      return "Verify customer identity & authorization";
    case "hardware":
      return "Inspect hardware diagnostics & repair options";
    case "repeat_contact":
      return "Review repeat contact history & escalate";
    case "human_requested":
      return "Continue with customer in real time";
    case "insufficient_evidence":
    case "conflicting_evidence":
    case "grounding_failed":
    case "verification_failed":
      return "Review case & provide verified resolution";
    case "llm_unavailable":
    case "model_timeout":
    case "dependency_failure":
      return "Review case manually";
    case "legal_media":
      return "Escalate to specialized compliance team";
    case "abusive_threatening":
      return "Review policy violation & determine action";
    default:
      return "Review case & assist customer";
  }
}

export type RowFilter = "all" | "needs_attention" | "auto" | "clarification" | "handoff" | "high_risk" | "insufficient_evidence";

export const PRIMARY_FILTERS: { key: RowFilter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "needs_attention", label: "Needs attention" },
  { key: "auto", label: "Auto-handled" },
  { key: "clarification", label: "Needs clarification" },
  { key: "handoff", label: "Human handoff" },
];

export const ROW_FILTERS: { key: RowFilter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "needs_attention", label: "Needs attention" },
  { key: "auto", label: "Auto-handled" },
  { key: "clarification", label: "Clarification" },
  { key: "handoff", label: "Human handoff" },
  { key: "high_risk", label: "High risk" },
  { key: "insufficient_evidence", label: "Insufficient evidence" },
];

export function isHighRisk(row: Pick<ConversationRow, "riskFlags" | "reasonCode">): boolean {
  return row.riskFlags.some((f) => HARD_BLOCK_FLAGS.has(f)) || reasonMeta(row.reasonCode).severity === "high";
}

export function matchesFilter(row: ConversationRow, filter: RowFilter): boolean {
  switch (filter) {
    case "needs_attention":
      return row.action === "HUMAN_HANDOFF" || row.action === "CLARIFICATION_REQUIRED" || isHighRisk(row);
    case "auto":
      return row.action === "AUTO_HANDLE";
    case "clarification":
      return row.action === "CLARIFICATION_REQUIRED";
    case "handoff":
      return row.action === "HUMAN_HANDOFF";
    case "high_risk":
      return isHighRisk(row);
    case "insufficient_evidence":
      return row.evidenceSufficient === false;
    default:
      return true;
  }
}

/** Reads a filter from the URL in any capitalization or separator ("Handoff", "HIGH-RISK"); unknown values mean all. */
export function parseRowFilter(value: string | null | undefined): RowFilter {
  const key = foldForMatch(value).replace(/[\s-]+/g, "_");
  return ROW_FILTERS.find((f) => f.key === key)?.key ?? "all";
}

export function matchesQuery(row: ConversationRow, query: string): boolean {
  const q = foldForMatch(query);
  if (!q) return true;
  return [row.traceId, row.requestId, row.preview, row.intent, row.intent ? intentLabel(row.intent) : null, row.reasonCode, row.reasonCode ? reasonMeta(row.reasonCode).label : null, row.action]
    .filter(Boolean)
    .some((v) => foldForMatch(v as string).includes(q));
}

export function queueCategory(row: Pick<ConversationRow, "reasonCode" | "rule">): QueueCategory {
  return handoffCategory(row.reasonCode, row.rule);
}

export interface LiveMetrics {
  n: number;
  auto: number;
  clarification: number;
  handoff: number;
  autoOnSufficientEvidence: number;
  evidenceSufficient: number;
  failed: number;
  medianLatencyMs: number | null;
  meanLatencyMs: number | null;
  p95LatencyMs: number | null;
  modelCalls: number;
  /** Sum of the per-trace list-price estimates; null when no trace recorded model usage. */
  estimatedCostUsd: number | null;
  oldest: string | null;
  newest: string | null;
}

/** Nearest-rank percentile of an ascending list. */
function percentile(sorted: number[], p: number): number | null {
  if (!sorted.length) return null;
  return sorted[Math.min(sorted.length - 1, Math.max(0, Math.ceil((p / 100) * sorted.length) - 1))];
}

/** Operational counts over the traces the API recorded in this environment (not a production workload). */
export function liveMetrics(summaries: TraceSummary[]): LiveMetrics {
  const count = (a: string) => summaries.filter((s) => s.final_decision === a).length;
  const lat = summaries
    .map((s) => s.latency_ms)
    .filter((v): v is number => typeof v === "number")
    .sort((a, b) => a - b);
  const median = lat.length ? (lat.length % 2 ? lat[(lat.length - 1) / 2] : (lat[lat.length / 2 - 1] + lat[lat.length / 2]) / 2) : null;
  const times = summaries.map((s) => s.started_at).sort();
  const costs = summaries.map((s) => s.estimated_cost_usd).filter((v): v is number => typeof v === "number");
  return {
    n: summaries.length,
    auto: count("AUTO_HANDLE"),
    clarification: count("CLARIFICATION_REQUIRED"),
    handoff: count("HUMAN_HANDOFF"),
    autoOnSufficientEvidence: summaries.filter((s) => s.final_decision === "AUTO_HANDLE" && s.evidence_sufficient === true).length,
    evidenceSufficient: summaries.filter((s) => s.evidence_sufficient === true).length,
    failed: summaries.filter((s) => s.error || !s.final_decision).length,
    medianLatencyMs: median,
    meanLatencyMs: lat.length ? lat.reduce((a, b) => a + b, 0) / lat.length : null,
    p95LatencyMs: percentile(lat, 95),
    modelCalls: summaries.reduce((sum, s) => sum + (s.llm_calls ?? 0), 0),
    estimatedCostUsd: costs.length ? costs.reduce((a, b) => a + b, 0) : null,
    oldest: times[0] ?? null,
    newest: times[times.length - 1] ?? null,
  };
}
