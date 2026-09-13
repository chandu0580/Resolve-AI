/**
 * Pure formatting helpers for the Audit Log.
 * This file has NO "use client" directive so it can be imported
 * by both server components (trace detail page) and client components
 * (audit-log-view table).
 */

import { intentLabel, reasonMeta } from "@/lib/labels";

export function conversationTitle(
  intent: string | null | undefined,
  reasonCode?: string | null,
): string {
  if (reasonCode === "prompt_injection") return "Security & instruction boundary check";
  if (reasonCode === "human_requested") return "Customer human escalation request";
  if (intent === "keyboard_text_bug") return "iPhone keyboard & autocorrect issue";
  if (intent === "battery_power") return "Battery performance & charging inquiry";
  if (intent === "account_store_repair") return "Account, store & repair request";
  if (intent === "performance_crash") return "Device performance & crash inquiry";
  if (intent === "connectivity") return "Network & Wi-Fi connectivity issue";
  if (intent === "data_loss_sync") return "iCloud sync & data backup inquiry";
  if (intent === "apps_services") return "App Store & service billing issue";
  if (intent === "hardware_damage") return "Hardware defect & screen repair";
  if (intent === "general_complaint") return "Customer feedback & escalation";
  if (intent) return `${intentLabel(intent)} inquiry`;
  if (reasonCode && reasonCode !== "none") return reasonMeta(reasonCode).label;
  return "Customer support conversation";
}

export function formatAuditReason(
  decision: string | null | undefined,
  reasonCode: string | null | undefined,
): string {
  if (decision === "AUTO_HANDLE") return "Verified support resolution";
  if (!reasonCode || reasonCode === "none") return "Standard resolution";
  switch (reasonCode) {
    case "insufficient_evidence":
      return "No verified answer";
    case "human_requested":
      return "Customer requested a human";
    case "safety":
    case "prompt_injection":
      return "Security or account concern";
    case "insufficient_context":
    case "low_confidence":
      return "Request needs more information";
    case "repeat_contact":
      return "Repeated unresolved request";
    case "hardware":
      return "Hardware or repair defect";
    case "payment_billing":
      return "Billing, order or refund";
    case "account_access":
      return "Account credential recovery";
    default:
      return reasonMeta(reasonCode).label;
  }
}

export function formatEvidenceLabel(
  level: string | null | undefined,
  decision?: string | null,
): { label: string; tone: "success" | "warning" | "neutral" } {
  if (!level || level === "n/a" || level === "none") {
    if (decision === "AUTO_HANDLE") return { label: "Strong", tone: "success" };
    return { label: "Not required", tone: "neutral" };
  }
  const u = level.toUpperCase();
  if (u === "STRONG") return { label: "Strong", tone: "success" };
  if (u === "SUFFICIENT") return { label: "Sufficient", tone: "success" };
  if (u === "WEAK") return { label: "Weak", tone: "warning" };
  if (u === "INSUFFICIENT") return { label: "Insufficient", tone: "neutral" };
  return { label: "Not required", tone: "neutral" };
}

export function humanInvolvement(
  decision: string | null | undefined,
): { label: string; tone: "success" | "info" | "warning" } {
  if (decision === "AUTO_HANDLE") return { label: "AI handled", tone: "success" };
  if (decision === "HUMAN_HANDOFF") return { label: "Human required", tone: "info" };
  return { label: "AI handled", tone: "warning" };
}

export function decisionDisplay(
  decision: string | null | undefined,
): { label: string; tone: "success" | "info" | "warning" | "danger" } {
  if (decision === "AUTO_HANDLE") return { label: "Auto-handled", tone: "success" };
  if (decision === "CLARIFICATION_REQUIRED") return { label: "Needs clarification", tone: "warning" };
  if (decision === "HUMAN_HANDOFF") return { label: "Human handoff", tone: "info" };
  return { label: "Failed execution", tone: "danger" };
}
