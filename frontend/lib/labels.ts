/**
 * Display vocabulary for the agent's codes. This file only NAMES what the backend decided; it never decides anything.
 * Queue categories and severities are a display grouping of the policy reason code for triage, not an agent output.
 */
import type { Action } from "@/lib/api/types";

export type Tone = "success" | "warning" | "info" | "danger" | "neutral" | "brand";

export const ACTION_META: Record<Action, { label: string; banner: string; tone: Tone; summary: string }> = {
  AUTO_HANDLE: {
    label: "Auto-handled",
    banner: "Auto-handled",
    tone: "success",
    summary: "Evidence, policy, verification and the output gate all allowed an automatic reply.",
  },
  CLARIFICATION_REQUIRED: {
    label: "Clarification",
    banner: "Clarification",
    tone: "warning",
    summary: "The agent asks one question instead of answering from thin evidence or an unclear message.",
  },
  HUMAN_HANDOFF: {
    label: "Human handoff",
    banner: "Human handoff",
    tone: "info",
    summary: "A human agent takes the case with a handoff packet; no automatic answer is given.",
  },
};

export type EvidenceLevel = "INSUFFICIENT" | "WEAK" | "SUFFICIENT" | "STRONG";

export const EVIDENCE_LEVELS: EvidenceLevel[] = ["INSUFFICIENT", "WEAK", "SUFFICIENT", "STRONG"];

export const EVIDENCE_LEVEL_META: Record<EvidenceLevel, { label: string; tone: Tone; explanation: string; allowsAnswer: boolean }> = {
  STRONG: {
    label: "Strong",
    tone: "success",
    allowsAnswer: true,
    explanation: "Several independent historical cases for closely matching issues prescribe the same resolution.",
  },
  SUFFICIENT: {
    label: "Sufficient",
    tone: "success",
    allowsAnswer: true,
    explanation: "Historical responses contain a consistent resolution pattern relevant to this issue.",
  },
  WEAK: {
    label: "Weak",
    tone: "warning",
    allowsAnswer: false,
    explanation: "Related cases exist, but they do not establish one consistent, instruction-bearing resolution.",
  },
  INSUFFICIENT: {
    label: "Insufficient",
    tone: "neutral",
    allowsAnswer: false,
    explanation: "No historical case is similar enough, or the message does not state a concrete symptom to match.",
  },
};

export function evidenceLevel(value: string | null | undefined): EvidenceLevel {
  return (EVIDENCE_LEVELS as string[]).includes(value ?? "") ? (value as EvidenceLevel) : "INSUFFICIENT";
}

export const SUFFICIENCY_REASON_LABELS: Record<string, string> = {
  strong_consistent_evidence: "Consistent resolution across independent cases",
  weak_similarity: "Closest historical cases are not similar enough",
  insufficient_resolution_evidence: "Similar cases do not state a resolution",
  conflicting_evidence: "Historical cases disagree",
  ambiguous_intent: "Retrieved cases span different issues",
  no_relevant_evidence: "Nothing relevant retrieved",
  customer_history_risk: "Only this customer's own earlier thread matched",
  insufficient_query: "Message has no concrete symptom to match",
  mixed_resolution: "Cases prescribe different resolutions",
  weak_resolution_evidence: "Too few cases share one resolution",
  not_applicable: "No evidence needed: greeting only",
};

export type QueueCategory = "Safety" | "Security" | "Billing" | "Account" | "Technical" | "Insufficient evidence" | "Model failure" | "Other";
export type Severity = "high" | "medium" | "low";

export const QUEUE_CATEGORIES: QueueCategory[] = ["Safety", "Security", "Billing", "Account", "Technical", "Insufficient evidence", "Model failure", "Other"];

export const REASON_META: Record<string, { label: string; category: QueueCategory; severity: Severity }> = {
  safety: { label: "Safety or security concern", category: "Safety", severity: "high" },
  prompt_injection: { label: "Prompt-injection attempt", category: "Security", severity: "high" },
  legal_media: { label: "Legal or media threat", category: "Other", severity: "high" },
  abusive_threatening: { label: "Abusive message", category: "Safety", severity: "medium" },
  account_access: { label: "Account access", category: "Account", severity: "medium" },
  payment_billing: { label: "Billing, order or refund", category: "Billing", severity: "medium" },
  sensitive_action: { label: "Sensitive account action", category: "Account", severity: "medium" },
  private_info: { label: "Needs private identifiers", category: "Account", severity: "medium" },
  hardware: { label: "Hardware or repair", category: "Technical", severity: "medium" },
  repeat_contact: { label: "Repeat contact", category: "Technical", severity: "medium" },
  human_requested: { label: "Customer asked for a person", category: "Other", severity: "medium" },
  vague_hostile: { label: "Frustrated, no concrete issue", category: "Other", severity: "low" },
  taxonomy_gap_risk: { label: "Outside supported topics", category: "Other", severity: "low" },
  conflicting_evidence: { label: "Conflicting evidence", category: "Insufficient evidence", severity: "low" },
  low_confidence: { label: "Unclear intent", category: "Other", severity: "low" },
  insufficient_context: { label: "Issue not stated", category: "Other", severity: "low" },
  insufficient_evidence: { label: "No proven resolution", category: "Insufficient evidence", severity: "low" },
  grounding_failed: { label: "Draft not grounded", category: "Insufficient evidence", severity: "low" },
  verification_failed: { label: "Draft failed verification", category: "Insufficient evidence", severity: "low" },
  output_gate: { label: "Output gate blocked", category: "Other", severity: "low" },
  llm_unavailable: { label: "Model unavailable", category: "Model failure", severity: "low" },
  model_timeout: { label: "Model timed out", category: "Model failure", severity: "low" },
  dependency_failure: { label: "System dependency failed", category: "Other", severity: "medium" },
  audit_unavailable: { label: "Audit trail unavailable", category: "Other", severity: "medium" },
  none: { label: "No escalation", category: "Other", severity: "low" },
};

export function reasonMeta(code: string | null | undefined) {
  return REASON_META[code ?? ""] ?? { label: code ? code.replace(/_/g, " ") : "Unknown", category: "Other" as QueueCategory, severity: "low" as Severity };
}

/**
 * Handoff queue for triage: a fixed display grouping of the policy reason code (and, for the shared `safety` reason code, the rule
 * that fired: rule `security` is a security concern). No model is involved.
 */
export function handoffCategory(reasonCode: string | null | undefined, rule?: string | null): QueueCategory {
  if (reasonCode === "safety" && rule === "security") return "Security";
  return reasonMeta(reasonCode).category;
}

/** The reason codes behind each queue, so the grouping can be shown next to the filters. */
export function categoryReasonCodes(category: QueueCategory): string[] {
  const codes = Object.entries(REASON_META)
    .filter(([code, m]) => m.category === category && code !== "none")
    .map(([code]) => code);
  if (category === "Security") codes.push("safety (rule security)");
  return codes;
}

export const SEVERITY_TONE: Record<Severity, Tone> = { high: "danger", medium: "warning", low: "neutral" };

export const INTENT_LABELS: Record<string, string> = {
  battery_power: "Battery & power",
  performance_crash: "Performance & crashes",
  keyboard_text_bug: "Keyboard & autocorrect",
  connectivity: "Connectivity",
  data_loss_sync: "Data loss & sync",
  apps_services: "Apps & services",
  account_store_repair: "Account, store & repair",
  hardware_damage: "Hardware damage",
  general_complaint: "General complaint",
  non_english: "Non-English",
  other: "Other / not a support request",
};

export function intentLabel(code: string | null | undefined): string {
  return INTENT_LABELS[code ?? ""] ?? (code ? code.replace(/_/g, " ") : "Unknown");
}

export const RISK_FLAG_LABELS: Record<string, string> = {
  safety_concern: "Safety concern",
  security_concern: "Security concern",
  privacy_concern: "Privacy concern",
  account_access_risk: "Account access",
  payment_billing_risk: "Billing or payment",
  legal_or_media_threat: "Legal or media threat",
  abusive_threatening: "Abusive or threatening",
  high_impact: "High impact",
  needs_private_info: "Needs private identifiers",
  physical_damage: "Physical damage",
  repeat_contact: "Repeat contact",
  sensitive_action_required: "Sensitive action requested",
  high_frustration: "High frustration",
  prompt_injection: "Prompt-injection attempt",
  insufficient_context: "Insufficient context",
  conflicting_evidence: "Conflicting evidence",
};

/** Mirrors RiskFlags.any_hard_block() in resolveai/schemas/core.py, for display emphasis only. */
export const HARD_BLOCK_FLAGS = new Set(["safety_concern", "security_concern", "legal_or_media_threat", "abusive_threatening", "prompt_injection"]);

export const GATE_CHECK_LABELS: Record<string, string> = {
  policy_allows_automation: "Policy allows automation",
  no_blocking_risk_flag: "No hard risk flag",
  intent_confidence_acceptable: "Intent confidence acceptable",
  evidence_sufficient: "Evidence sufficient",
  response_generated: "Response generated",
  response_verified: "Response verified",
  evidence_refs_exist: "Evidence references present",
  pii_guard: "PII guard passed",
  schema_valid: "Result complete",
  audit_trace_written: "Audit trace written",
};

export const RESPONSE_KIND_META: Record<string, { title: string; tone: Tone; note: string }> = {
  auto_reply: { title: "Generated response", tone: "success", note: "Simulated in the reference environment. Nothing was sent to a customer." },
  template_reply: { title: "Template response", tone: "success", note: "A fixed template (language redirect or closure). Simulated; nothing was sent." },
  clarifying_question: { title: "Clarification", tone: "warning", note: "Suggested question for the customer. Simulated; nothing was sent." },
  handoff_notice: { title: "No customer response: human handoff", tone: "info", note: "Only a holding notice would be shown while a human takes over. Simulated; nothing was sent." },
};

export const STAGE_ORDER: { key: string; label: string; events: string[]; latencyKeys: string[] }[] = [
  { key: "request", label: "Request", events: ["request_received"], latencyKeys: [] },
  { key: "pii", label: "PII check", events: ["pii_redacted", "injection_checked"], latencyKeys: ["pii_redaction"] },
  { key: "context", label: "Context", events: ["context_built"], latencyKeys: ["context"] },
  { key: "intent", label: "Intent", events: ["intent_predicted", "intent_classified", "second_opinion_used"], latencyKeys: ["intent", "second_opinion"] },
  { key: "retrieval", label: "Retrieval", events: ["retrieval_started", "retrieval_completed", "retrieval_skipped", "evidence_quarantined"], latencyKeys: ["retrieval"] },
  { key: "evidence_gate", label: "Evidence gate", events: ["evidence_evaluated", "evidence_gate"], latencyKeys: ["evidence_gate"] },
  { key: "risk", label: "Risk", events: ["risk_flags_extracted", "risk_extracted"], latencyKeys: ["risk"] },
  { key: "policy", label: "Policy", events: ["escalation_decided", "policy_checked"], latencyKeys: ["policy"] },
  { key: "draft", label: "Draft", events: ["draft_generated", "fallback"], latencyKeys: ["draft"] },
  { key: "verification", label: "Verification", events: ["response_verified", "grounding_checked"], latencyKeys: ["verification"] },
  { key: "decision", label: "Final action", events: ["output_allowed", "decision_made", "clarification_created", "handoff_created", "handoff"], latencyKeys: ["output_gate", "handoff"] },
  { key: "complete", label: "Trace complete", events: ["response_returned", "execution_failed", "error"], latencyKeys: [] },
];

export const EVENT_LABELS: Record<string, string> = {
  request_received: "Request received",
  pii_redacted: "PII redacted",
  injection_checked: "Prompt-injection check",
  context_built: "Conversation context built",
  intent_predicted: "Intent predicted",
  intent_classified: "Intent classified",
  second_opinion_used: "Intent second opinion",
  retrieval_started: "Retrieval started",
  retrieval_completed: "Retrieval completed",
  retrieval_skipped: "Retrieval skipped: nothing to look up",
  evidence_evaluated: "Evidence gate evaluated",
  evidence_gate: "Evidence gate",
  risk_flags_extracted: "Risk flags extracted",
  risk_extracted: "Risk extracted",
  escalation_decided: "Policy decided",
  policy_checked: "Policy checked",
  draft_generated: "Draft generated",
  fallback: "Fallback applied",
  response_verified: "Response verified",
  grounding_checked: "Grounding checked",
  output_allowed: "Output gate: automatic reply allowed",
  decision_made: "Output gate: decision made",
  clarification_created: "Clarification created",
  handoff_created: "Handoff packet created",
  handoff: "Handoff",
  response_returned: "Result returned",
  evidence_quarantined: "Evidence quarantined (instruction-like text)",
  model_call_failed: "Model call failed (fallback applied)",
  dependency_failed: "Dependency failed (handed off)",
  execution_failed: "Execution failed",
  error: "Error",
};
