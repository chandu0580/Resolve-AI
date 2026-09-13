import { EvidenceLevelBadge } from "@/components/ui/status";
import { fixed, humanize } from "@/lib/format";
import { EVIDENCE_LEVELS, EVIDENCE_LEVEL_META, SUFFICIENCY_REASON_LABELS, evidenceLevel } from "@/lib/labels";

const FILL: Record<string, string> = {
  INSUFFICIENT: "bg-neutral",
  WEAK: "bg-warning",
  SUFFICIENT: "bg-success",
  STRONG: "bg-success",
};

export interface SufficiencyInput {
  sufficiency_level?: string | null;
  sufficiency_reason?: string | null;
  sufficient?: boolean | null;
  resolution_confidence?: number | null;
  consistency?: string | null;
  n_relevant?: number | null;
  n_retrieved?: number | null;
  gate_version?: string | null;
}

/** The evidence gate's verdict on the historical cases. Deliberately styled as a four-step scale, not as a confidence bar. */
export function EvidenceSufficiency({ evidence }: { evidence: SufficiencyInput }) {
  const level = evidenceLevel(evidence.sufficiency_level);
  const idx = EVIDENCE_LEVELS.indexOf(level);
  const meta = EVIDENCE_LEVEL_META[level];
  const reason = evidence.sufficiency_reason ? SUFFICIENCY_REASON_LABELS[evidence.sufficiency_reason] ?? humanize(evidence.sufficiency_reason) : null;
  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <EvidenceLevelBadge level={level} size="md" />
        <span className="text-xs text-ink-3">{meta.allowsAnswer ? "Evidence can support an answer" : "Not enough to answer"}</span>
      </div>
      <ol className="mt-3 grid grid-cols-4 gap-1" aria-label="Evidence sufficiency scale">
        {EVIDENCE_LEVELS.map((l, i) => (
          <li key={l} aria-current={i === idx ? "step" : undefined} className="min-w-0">
            <div className={`h-1.5 rounded-sm ${i <= idx ? FILL[level] : "bg-subtle"}`} aria-hidden="true" />
            <div className={`mt-1 truncate text-[11px] ${i === idx ? "font-semibold text-ink" : "text-ink-3"}`}>{EVIDENCE_LEVEL_META[l].label}</div>
          </li>
        ))}
      </ol>
      <p className="mt-2 text-[13px] text-ink-2">{meta.explanation}</p>
      <dl className="mt-2 space-y-1 text-xs">
        {reason ? (
          <div className="flex flex-wrap gap-x-1.5">
            <dt className="text-ink-3">Gate finding:</dt>
            <dd className="text-ink">{reason}</dd>
          </div>
        ) : null}
        {evidence.resolution_confidence !== undefined && evidence.resolution_confidence !== null ? (
          <div className="flex flex-wrap gap-x-1.5">
            <dt className="text-ink-3">Resolution confidence:</dt>
            <dd className="tabular text-ink">
              {fixed(evidence.resolution_confidence)}
              {evidence.consistency ? ` · ${humanize(evidence.consistency).toLowerCase()}` : ""}
            </dd>
          </div>
        ) : null}
        {evidence.n_relevant !== undefined && evidence.n_relevant !== null ? (
          <div className="flex flex-wrap gap-x-1.5">
            <dt className="text-ink-3">Cases:</dt>
            <dd className="tabular text-ink">
              {evidence.n_relevant} relevant of {evidence.n_retrieved ?? "?"} retrieved candidates
            </dd>
          </div>
        ) : null}
      </dl>
      <p className="mt-2 text-[11px] text-ink-3">The evidence gate{evidence.gate_version ? ` (${evidence.gate_version})` : ""} judges the historical cases. This is not the model&apos;s confidence.</p>
    </div>
  );
}
