import { CircleAlert, CircleCheck, CircleSlash, Info, MessageCircleQuestionMark, ShieldAlert, TriangleAlert, UserRound } from "lucide-react";
import type { ElementType } from "react";
import { Badge } from "@/components/ui/badge";
import type { Action } from "@/lib/api/types";
import { ACTION_META, EVIDENCE_LEVEL_META, SEVERITY_TONE, evidenceLevel, type Severity, type Tone } from "@/lib/labels";

export const ACTION_ICON: Record<Action, ElementType> = {
  AUTO_HANDLE: CircleCheck,
  CLARIFICATION_REQUIRED: MessageCircleQuestionMark,
  HUMAN_HANDOFF: UserRound,
};

export function ActionBadge({ action, size }: { action: Action | string | null | undefined; size?: "sm" | "md" }) {
  const meta = ACTION_META[action as Action];
  if (!meta) return <Badge size={size}>{action ?? "Unknown"}</Badge>;
  return (
    <Badge tone={meta.tone} icon={ACTION_ICON[action as Action]} size={size}>
      {meta.label}
    </Badge>
  );
}

const LEVEL_ICON: Record<string, ElementType> = { STRONG: CircleCheck, SUFFICIENT: CircleCheck, WEAK: CircleAlert, INSUFFICIENT: CircleSlash };

export function EvidenceLevelBadge({ level, size }: { level: string | null | undefined; size?: "sm" | "md" }) {
  if (!level) return <span className="text-ink-3">n/a</span>;
  const l = evidenceLevel(level);
  return (
    <Badge tone={EVIDENCE_LEVEL_META[l].tone} icon={LEVEL_ICON[l]} size={size} title={EVIDENCE_LEVEL_META[l].explanation}>
      {EVIDENCE_LEVEL_META[l].label}
    </Badge>
  );
}

const SEVERITY_ICON: Record<Severity, ElementType> = { high: ShieldAlert, medium: TriangleAlert, low: Info };

export function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <Badge tone={SEVERITY_TONE[severity]} icon={SEVERITY_ICON[severity]}>
      {severity.charAt(0).toUpperCase() + severity.slice(1)}
    </Badge>
  );
}

const BAND_TONE: Record<string, Tone> = { HIGH: "success", MEDIUM: "warning", LOW: "danger" };

export function BandBadge({ band }: { band: string | null | undefined }) {
  if (!band) return <span className="text-ink-3">n/a</span>;
  return <Badge tone={BAND_TONE[band] ?? "neutral"}>{band.charAt(0) + band.slice(1).toLowerCase()} band</Badge>;
}

export function PassFail({ ok, passLabel = "Passed", failLabel = "Blocked" }: { ok: boolean; passLabel?: string; failLabel?: string }) {
  return ok ? (
    <span className="inline-flex items-center gap-1 text-success">
      <CircleCheck className="size-4 shrink-0" aria-hidden="true" />
      <span>{passLabel}</span>
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 text-danger">
      <CircleSlash className="size-4 shrink-0" aria-hidden="true" />
      <span>{failLabel}</span>
    </span>
  );
}
