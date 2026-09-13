import { ConfidenceMeter } from "@/components/ui/meter";
import { BandBadge } from "@/components/ui/status";
import type { IntentResult } from "@/lib/api/types";
import { pct } from "@/lib/format";
import { intentLabel } from "@/lib/labels";

export function IntentSummary({ intent }: { intent: IntentResult }) {
  const alternatives = ((intent.top3 ?? []) as unknown as [string, number][]).filter(([code]) => code !== intent.intent).slice(0, 2);
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-medium text-ink">{intentLabel(intent.intent)}</span>
        <BandBadge band={intent.confidence_band} />
      </div>
      <p className="font-mono text-[11px] text-ink-3">{intent.intent}</p>
      <ConfidenceMeter value={intent.confidence} label="Calibrated intent confidence" />
      {alternatives.length ? (
        <p className="text-xs text-ink-3">
          Alternatives: {alternatives.map(([code, p]) => `${intentLabel(code)} ${pct(p)}`).join(" · ")}
        </p>
      ) : null}
      <p className="text-xs text-ink-3">
        {intent.second_opinion_applied ? "A model second opinion changed the classifier's answer." : intent.second_opinion ? "A model second opinion was consulted and not applied." : "Classifier answer used directly."}
        {intent.multi_intent ? " Several issues detected." : ""}
        {intent.taxonomy_gap ? " Possibly outside the supported topics." : ""}
      </p>
    </div>
  );
}
