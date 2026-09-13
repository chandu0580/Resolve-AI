import { CircleCheck, CircleSlash } from "lucide-react";
import { GATE_CHECK_LABELS } from "@/lib/labels";

/** Every output-gate check the API reports. An automatic reply is only possible when all of them pass. */
export function OutputGateChecklist({ gate, blocking = [] }: { gate: Record<string, boolean>; blocking?: string[] }) {
  const keys = [...Object.keys(GATE_CHECK_LABELS).filter((k) => k in gate), ...Object.keys(gate).filter((k) => !(k in GATE_CHECK_LABELS))];
  if (!keys.length) return <p className="text-[13px] text-ink-3">No output-gate checks recorded.</p>;
  return (
    <ul className="grid gap-x-6 gap-y-1.5 sm:grid-cols-2">
      {keys.map((k) => {
        const ok = gate[k];
        return (
          <li key={k} className="flex items-start gap-2 text-[13px]">
            {ok ? <CircleCheck className="mt-0.5 size-4 shrink-0 text-success" aria-hidden="true" /> : <CircleSlash className="mt-0.5 size-4 shrink-0 text-ink-3" aria-hidden="true" />}
            <span className={ok ? "text-ink" : "text-ink-2"}>
              {GATE_CHECK_LABELS[k] ?? k}
              <span className="sr-only">{ok ? ": met" : ": not met"}</span>
              {!ok && blocking.includes(k) ? <span className="ml-1.5 text-xs text-ink-3">(not met)</span> : null}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
