import { Card } from "@/components/ui/card";
import type { Explanation } from "@/lib/explain";

const ROWS: [keyof Explanation, string][] = [
  ["decision", "Decision"],
  ["reason", "Reason"],
  ["evidence", "Evidence"],
  ["policy", "Policy"],
  ["risk", "Risk"],
  ["verification", "Verification"],
  ["whatWouldChange", "What would change it"],
  ["nextAction", "Next action"],
];

/** "Why did ResolveAI do this?" rendered from structured decision data (lib/explain.ts). */
export function DecisionExplanation({ explanation }: { explanation: Explanation }) {
  return (
    <Card
      title={<span className="tracking-wide uppercase">{explanation.heading}</span>}
      description={
        explanation.source === "trace"
          ? "Why did ResolveAI do this? Reconstructed from the audit trace's recorded decision data. No model was asked to explain itself."
          : "Why did ResolveAI do this? Built from the structured decision record: outcome, evidence gate, policy, risk flags and verification. No model was asked to explain itself."
      }
    >
      <dl className="grid gap-y-2.5">
        {ROWS.map(([key, label]) => (
          <div key={key} className="grid gap-0.5 sm:grid-cols-[7.5rem_minmax(0,1fr)] sm:gap-3">
            <dt className="text-[11px] font-semibold tracking-wide text-ink-3 uppercase sm:pt-0.5">{label}</dt>
            <dd className="min-w-0 text-[13px] break-words text-ink">{explanation[key]}</dd>
          </div>
        ))}
      </dl>
    </Card>
  );
}
