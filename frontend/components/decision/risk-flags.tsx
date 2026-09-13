import { CircleCheck, ShieldAlert, TriangleAlert } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { HARD_BLOCK_FLAGS, RISK_FLAG_LABELS } from "@/lib/labels";

export function RiskFlagList({ flags, source }: { flags: string[]; source?: string | null }) {
  return (
    <div>
      {flags.length ? (
        <ul className="flex flex-wrap gap-1.5" aria-label="Risk flags raised">
          {flags.map((f) => (
            <li key={f}>
              <Badge tone={HARD_BLOCK_FLAGS.has(f) ? "danger" : "warning"} icon={HARD_BLOCK_FLAGS.has(f) ? ShieldAlert : TriangleAlert}>
                {RISK_FLAG_LABELS[f] ?? f}
              </Badge>
            </li>
          ))}
        </ul>
      ) : (
        <p className="inline-flex items-center gap-1.5 text-[13px] text-ink-2">
          <CircleCheck className="size-4 text-success" aria-hidden="true" />
          No risk flags raised
        </p>
      )}
      {source ? (
        <p className="mt-2 text-xs text-ink-3">
          Detected by {source === "rules" ? "deterministic rules only (no model call needed)" : source === "llm+rules" ? "rules plus a compact model check" : source}
          {flags.some((f) => HARD_BLOCK_FLAGS.has(f)) ? ". Red flags force a human handoff." : "."}
        </p>
      ) : null}
    </div>
  );
}
