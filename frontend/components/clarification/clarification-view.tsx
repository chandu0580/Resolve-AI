import { Badge } from "@/components/ui/badge";
import { Card, KeyValues } from "@/components/ui/card";
import { BandBadge, EvidenceLevelBadge } from "@/components/ui/status";
import type { ResolveResponse } from "@/lib/api/types";
import { pct } from "@/lib/format";
import { SUFFICIENCY_REASON_LABELS, intentLabel, reasonMeta } from "@/lib/labels";

export function ClarificationView({ result }: { result: ResolveResponse }) {
  const c = result.clarification;
  if (!c) return null;
  return (
    <Card title="Clarification packet" description="ResolveAI asks one question instead of guessing.">
      <div className="space-y-4">
        <div>
          <h3 className="mb-1 text-xs font-medium text-ink">Why it is unsafe to resolve now</h3>
          <p className="text-[13px] text-ink-2">{c.why}</p>
        </div>
        <KeyValues
          items={[
            { label: "Reason", value: reasonMeta(c.reason_code).label },
            {
              label: "Evidence",
              value: (
                <span className="inline-flex flex-wrap items-center gap-1.5">
                  <EvidenceLevelBadge level={c.evidence_level} />
                  <span>{SUFFICIENCY_REASON_LABELS[c.evidence_reason] ?? c.evidence_reason}</span>
                </span>
              ),
              hint: c.evidence_summary,
            },
            {
              label: "Intent hypothesis",
              value: (
                <span className="inline-flex flex-wrap items-center gap-1.5">
                  {intentLabel(c.intent_hypothesis)} · {pct(c.intent_confidence)} <BandBadge band={c.confidence_band} />
                </span>
              ),
              hint: c.alternatives.length ? `Alternatives: ${c.alternatives.map(intentLabel).join(", ")}` : undefined,
            },
          ]}
        />
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <h3 className="mb-1 text-xs font-medium text-ink">Missing information</h3>
            {c.missing_information.length ? (
              <ul className="list-disc space-y-0.5 pl-5 text-[13px] text-ink-2">
                {c.missing_information.map((m) => (
                  <li key={m}>{m}</li>
                ))}
              </ul>
            ) : (
              <p className="text-[13px] text-ink-3">None listed</p>
            )}
          </div>
          <div>
            <h3 className="mb-1 text-xs font-medium text-ink">Already provided</h3>
            {c.already_provided.length ? (
              <ul className="flex flex-wrap gap-1.5">
                {c.already_provided.map((m) => (
                  <li key={m}>
                    <Badge tone="success">{m}</Badge>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-[13px] text-ink-3">Nothing yet</p>
            )}
            <p className="mt-1 text-xs text-ink-3">The question does not ask for details that were already given.</p>
          </div>
        </div>
        <div>
          <h3 className="mb-1 text-xs font-medium text-ink">Suggested question</h3>
          <blockquote className="rounded-md border border-warning-line bg-warning-bg px-3 py-2 text-[13px] text-ink">{c.question}</blockquote>
        </div>
      </div>
    </Card>
  );
}
