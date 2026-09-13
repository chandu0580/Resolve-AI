import { TONE_TEXT } from "@/components/ui/badge";
import { ACTION_ICON } from "@/components/ui/status";
import type { Action } from "@/lib/api/types";
import { ACTION_META, reasonMeta } from "@/lib/labels";

const BANNER_BG: Record<string, string> = {
  success: "border-success-line bg-success-bg",
  warning: "border-warning-line bg-warning-bg",
  info: "border-info-line bg-info-bg",
};

export interface BannerOutcome {
  action: Action;
  reason_code: string;
  rule: string;
  policy_version: string;
  why: string;
}

export function DecisionBanner({ outcome }: { outcome: BannerOutcome }) {
  const meta = ACTION_META[outcome.action];
  const Icon = ACTION_ICON[outcome.action];
  const reason = reasonMeta(outcome.reason_code);
  return (
    <section aria-label={`Decision: ${meta.banner}`} className={`rounded-lg border px-4 py-3.5 ${BANNER_BG[meta.tone]}`}>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <Icon className={`size-5 shrink-0 ${TONE_TEXT[meta.tone]}`} aria-hidden="true" />
        <p className={`text-[13px] font-bold tracking-[0.08em] uppercase ${TONE_TEXT[meta.tone]}`}>{meta.banner}</p>
        <span className="text-[13px] font-medium text-ink">{outcome.action === "AUTO_HANDLE" ? "Every automation check passed" : reason.label}</span>
      </div>
      <p className="mt-1.5 text-sm text-ink">{outcome.why}</p>
      {/* The rule and version identify the decision for audit; they sit behind a disclosure so the banner stays readable. */}
      <details className="group mt-2">
        <summary className="cursor-pointer list-none text-xs text-ink-3 hover:text-ink-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-500">
          <span className="inline-block transition-transform group-open:rotate-90" aria-hidden="true">&rsaquo;</span> Decision reference
        </summary>
        <dl className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-xs">
          <div className="flex gap-1.5">
            <dt className="text-ink-3">Reason code</dt>
            <dd className="font-mono text-ink-2">{outcome.reason_code}</dd>
          </div>
          <div className="flex gap-1.5">
            <dt className="text-ink-3">Policy rule</dt>
            <dd className="font-mono text-ink-2">{outcome.rule}</dd>
          </div>
          <div className="flex gap-1.5">
            <dt className="text-ink-3">Policy version</dt>
            <dd className="font-mono text-ink-2">{outcome.policy_version}</dd>
          </div>
        </dl>
      </details>
    </section>
  );
}
