import { BookOpen, ListChecks, Scale, Sparkles, UserRound } from "lucide-react";

/** The operating principle, shown in the shell and on the Overview. Each step names where it is enforced. */
export const PRINCIPLE = [
  { key: "model", verb: "Model proposes", icon: Sparkles, detail: "Intent second opinion, risk flags, drafts and verification verdicts. It never decides escalation." },
  { key: "evidence", verb: "Evidence grounds", icon: BookOpen, detail: "Only SUFFICIENT or STRONG historical evidence can support an automatic reply." },
  { key: "policy", verb: "Policy decides", icon: Scale, detail: "Deterministic, ordered rules choose auto-handle, clarification or human handoff." },
  { key: "verifier", verb: "Verifier checks", icon: ListChecks, detail: "Every automatic reply is checked against the evidence it cites, then the output gate." },
  { key: "humans", verb: "Humans control exceptions", icon: UserRound, detail: "Anything unsafe, sensitive or unsupported goes to a person with a handoff packet." },
] as const;

export function PrincipleLine() {
  return (
    <p className="text-[11px] leading-snug text-ink-3">
      {PRINCIPLE.map((p, i) => (
        <span key={p.key}>
          {i ? " · " : ""}
          {p.verb}
        </span>
      ))}
    </p>
  );
}

export function PrincipleStrip() {
  return (
    <section aria-labelledby="principle-heading" className="rounded-lg border border-line bg-surface px-4 py-3">
      <h2 id="principle-heading" className="sr-only">
        Operating principle
      </h2>
      <ol className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        {PRINCIPLE.map((p, i) => {
          const Icon = p.icon;
          return (
            <li key={p.key} className="flex min-w-0 gap-2.5">
              <span className="flex size-7 shrink-0 items-center justify-center rounded-md bg-brand-50 text-brand-700">
                <Icon className="size-3.5" aria-hidden="true" />
              </span>
              <div className="min-w-0">
                <div className="text-[12px] font-semibold tracking-wide text-ink uppercase">
                  <span className="sr-only">Step {i + 1}: </span>
                  {p.verb}
                </div>
                <p className="text-xs text-ink-3">{p.detail}</p>
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
