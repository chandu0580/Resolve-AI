import { Ban, CircleCheck, MessageCircleQuestionMark, ShieldCheck, UserRound } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, Notice } from "@/components/ui/card";
import type { ResolveResponse } from "@/lib/api/types";
import { fixed } from "@/lib/format";

/** What a customer would see. Always labelled as simulated: the reference environment is not connected to any channel. */
export function ResponsePanel({ result }: { result: ResolveResponse }) {
  const { response, verification, handoff, evidence } = result;
  const blockedDraft = result.action === "HUMAN_HANDOFF" && handoff?.draft_if_any && verification && !verification.verified ? handoff.draft_if_any : null;

  if (response.kind === "auto_reply" || response.kind === "template_reply") {
    // "Grounded" only when every citation is a retrieved case and the gate judged the evidence sufficient; the badge never infers it.
    const known = new Set(evidence.items.map((i) => i.evidence_id));
    const grounded = response.kind === "auto_reply" && response.evidence_refs.length > 0 && response.evidence_refs.every((ref) => known.has(ref.evidence_id)) && evidence.sufficient;
    return (
      <Card
        title={response.kind === "auto_reply" ? "Generated response" : "Template response"}
        description="Simulated response. Nothing was sent to a customer."
        actions={
          <>
            {grounded ? (
              <Badge tone="success" icon={CircleCheck}>
                Grounded in {response.evidence_refs.length} cases
              </Badge>
            ) : response.kind === "auto_reply" ? (
              <Badge tone="danger" icon={Ban}>
                Grounding not confirmed
              </Badge>
            ) : null}
            {verification?.verified ? (
              <Badge tone="success" icon={ShieldCheck}>
                Verified
              </Badge>
            ) : null}
          </>
        }
      >
        <blockquote className="rounded-md border border-line bg-canvas px-3.5 py-3 text-sm leading-relaxed text-ink">{response.text}</blockquote>
        {response.kind === "auto_reply" ? (
          <div className="mt-3 space-y-2 text-xs text-ink-2">
            {verification ? (
              <p>
                Verification {verification.verified ? "passed" : "failed"} · method <span className="font-mono">{verification.method}</span> · evidence word coverage {fixed(verification.coverage)} · draft attempts{" "}
                {verification.attempts}
              </p>
            ) : null}
            {response.evidence_refs.length ? (
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="text-ink-3">Cited cases:</span>
                {response.evidence_refs.map((ref) => (
                  <a key={ref.evidence_id} href={`#evidence-${ref.evidence_id}`} className="rounded border border-line bg-surface px-1.5 py-0.5 font-mono text-[11px] text-brand-700 hover:border-brand-500">
                    {ref.evidence_id} · {fixed(ref.similarity)}
                  </a>
                ))}
              </div>
            ) : null}
            <p className="text-ink-3">
              The API marks this reply as eligible for automatic sending. The console only simulates it; it is not connected to a support channel.
            </p>
          </div>
        ) : null}
      </Card>
    );
  }

  if (response.kind === "clarifying_question") {
    return (
      <Card title="Clarification" description="Suggested question for the customer. Simulated; nothing was sent." actions={<Badge tone="warning" icon={MessageCircleQuestionMark}>Question, not an answer</Badge>}>
        <blockquote className="rounded-md border border-warning-line bg-warning-bg px-3.5 py-3 text-sm leading-relaxed text-ink">{response.text}</blockquote>
      </Card>
    );
  }

  return (
    <Card title="No customer response: human handoff" description="ResolveAI did not answer. A human agent takes over with the handoff packet below." actions={<Badge tone="info" icon={UserRound}>Human-in-the-loop</Badge>}>
      <div className="space-y-3">
        {blockedDraft ? (
          <div className="rounded-md border border-danger-line bg-danger-bg px-3.5 py-3">
            <p className="flex items-center gap-1.5 text-[13px] font-semibold text-danger">
              <Ban className="size-4" aria-hidden="true" /> Draft blocked by verification
            </p>
            <p className="mt-1 text-xs text-ink-2">A reply was drafted, but the verifier could not confirm it against the evidence after a corrective retry, so it was never released.</p>
            <blockquote className="mt-2 rounded border border-line bg-surface px-3 py-2 text-[13px] text-ink-3">{blockedDraft}</blockquote>
            {verification?.issues.length ? (
              <ul className="mt-2 list-disc space-y-0.5 pl-5 text-xs text-ink-2">
                {verification.issues.map((i, n) => (
                  <li key={n}>
                    <span className="font-mono">{i.check}</span> ({i.severity}): {i.detail}
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        ) : null}
        <div>
          <div className="mb-1 text-xs text-ink-3">Holding notice a customer would see while a human takes over (simulated)</div>
          <blockquote className="rounded-md border border-line bg-canvas px-3.5 py-2.5 text-[13px] text-ink-2">{response.text}</blockquote>
        </div>
        <Notice tone="info">The holding notice contains no troubleshooting advice. Answering is left to the human agent.</Notice>
      </div>
    </Card>
  );
}
