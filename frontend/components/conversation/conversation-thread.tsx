import { EyeOff } from "lucide-react";
import { Card, KeyValues } from "@/components/ui/card";
import type { ResolveResponse } from "@/lib/api/types";
import { intentLabel } from "@/lib/labels";

export function ConversationThread({ result }: { result: ResolveResponse }) {
  const { message, context } = result.conversation;
  const pii = Object.entries(message.pii_counts ?? {}).filter(([, n]) => n > 0);
  return (
    <Card title="Conversation" description="As the agent saw it, after PII redaction.">
      <ol className="space-y-2.5">
        {context.turns.map((t, i) => (
          <li key={i} className={`max-w-[92%] rounded-lg px-3 py-2 text-[13px] ${t.role === "customer" ? "bg-subtle text-ink-2" : "ml-auto border border-line bg-surface text-ink-2"}`}>
            <div className="mb-0.5 text-[11px] font-medium text-ink-3">{t.role === "customer" ? "Customer · earlier turn" : "Support · earlier turn"}</div>
            {t.text}
          </li>
        ))}
        <li className="max-w-[96%] rounded-lg border border-brand-100 bg-brand-50 px-3 py-2.5 text-sm text-ink">
          <div className="mb-0.5 text-[11px] font-semibold text-brand-700">Customer · message handled</div>
          {message.text}
        </li>
      </ol>
      {context.truncated ? <p className="mt-2 text-xs text-ink-3">Earlier turns were truncated to the configured context window.</p> : null}
      <p className="mt-3 flex items-start gap-1.5 text-xs text-ink-3">
        <EyeOff className="mt-px size-3.5 shrink-0" aria-hidden="true" />
        {pii.length ? `Redacted before any model call or trace: ${pii.map(([k, n]) => `${k.toLowerCase()} ×${n}`).join(", ")}.` : "No personal data detected. Redaction still ran before any model call."}
      </p>
    </Card>
  );
}

export function UnderstandingCard({ result }: { result: ResolveResponse }) {
  const { risk, intent, conversation } = result;
  return (
    <Card title="What ResolveAI understood">
      <KeyValues
        items={[
          { label: "Summary", value: risk.summary ? risk.summary : <span className="text-ink-3">No model summary. Risk was assessed by rules only.</span> },
          { label: "Issue category", value: intentLabel(intent.intent) },
          { label: "Actionable request", value: risk.is_actionable ? "Yes" : "No" },
          { label: "Concrete issue stated", value: intent.insufficient_context || risk.insufficient_context ? "No" : "Yes" },
          { label: "Context used", value: intent.context_used ? "Earlier turns" : "Current message only" },
          {
            label: "Injection check",
            value: risk.prompt_injection ? "Instruction-like text detected. Treated as data and handed off." : "No instruction-like text detected",
          },
          ...(conversation.message.language_hint ? [{ label: "Language hint", value: conversation.message.language_hint }] : []),
        ]}
      />
    </Card>
  );
}
