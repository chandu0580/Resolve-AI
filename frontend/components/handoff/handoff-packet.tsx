import { Badge } from "@/components/ui/badge";
import { Card, KeyValues } from "@/components/ui/card";
import { CopyButton } from "@/components/ui/copy-button";
import { EvidenceLevelBadge, SeverityBadge } from "@/components/ui/status";
import { RiskFlagList } from "@/components/decision/risk-flags";
import type { ResolveResponse } from "@/lib/api/types";
import { fixed, pct } from "@/lib/format";
import { activeRiskFlags, handoffSummaryText } from "@/lib/handoff-summary";
import { EVIDENCE_LEVEL_META, SUFFICIENCY_REASON_LABELS, evidenceLevel, handoffCategory, intentLabel, reasonMeta } from "@/lib/labels";

export function HandoffPacketView({ result }: { result: ResolveResponse }) {
  const h = result.handoff;
  if (!h) return null;
  const reason = reasonMeta(h.reason.reason_code);
  return (
    <Card
      title="Handoff packet"
      description="Everything a human agent needs to take the case. No automatic answer was given."
      actions={<CopyButton text={handoffSummaryText(result)} label="Copy handoff summary" variant="primary" />}
    >
      <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <SeverityBadge severity={reason.severity} />
          <Badge>Queue: {handoffCategory(h.reason.reason_code, h.reason.rule)}</Badge>
          <span className="text-[13px] font-medium text-ink">{reason.label}</span>
        </div>
        <div className="rounded-md border border-info-line bg-info-bg px-3.5 py-2.5">
          <div className="text-[11px] font-medium tracking-wide text-info uppercase">Recommended next action</div>
          <p className="mt-0.5 text-sm text-ink">{h.recommended_next_action}</p>
        </div>
        <KeyValues
          items={[
            { label: "Customer issue", value: h.customer_issue, hint: "PII redacted" },
            ...(h.summary && h.summary !== h.customer_issue ? [{ label: "Conversation summary", value: h.summary }] : []),
            {
              label: "Context",
              value: result.conversation.context.turns.length
                ? `${result.conversation.context.turns.length} earlier turn${result.conversation.context.turns.length === 1 ? "" : "s"} before this message${result.conversation.context.truncated ? " (truncated to the context window)" : ""}`
                : "First message in the conversation",
              hint: "The full redacted thread is in the conversation workspace.",
            },
            { label: "Why handed off", value: h.reason.reason },
            {
              label: "Intent",
              value: `${intentLabel(h.intent)} · ${pct(h.confidence)} · ${h.confidence_band.toLowerCase()} band`,
              hint: h.alternatives.length ? `Alternatives: ${h.alternatives.map(intentLabel).join(", ")}` : undefined,
            },
            { label: "Risk flags", value: <RiskFlagList flags={activeRiskFlags(h.risk as unknown as Record<string, unknown>)} /> },
            {
              label: "Evidence found",
              value: (
                <span className="inline-flex flex-wrap items-center gap-1.5">
                  <EvidenceLevelBadge level={h.evidence_level} />
                  <span>{h.historical_examples.length ? `${h.historical_examples.length} related historical case${h.historical_examples.length === 1 ? "" : "s"}` : "No related historical case"}</span>
                </span>
              ),
              hint: h.evidence_summary,
            },
            {
              label: "What ResolveAI tried",
              value: `${result.evidence.n_retrieved ? `Searched ${result.evidence.n_retrieved} historical cases (evidence ${EVIDENCE_LEVEL_META[evidenceLevel(result.evidence.sufficiency_level)].label.toLowerCase()})` : "Did not search historical cases"}; ${
                result.response.draft_attempts ? `drafted a reply ${result.response.draft_attempts === 1 ? "once" : `${result.response.draft_attempts} times`} and verification did not accept it` : "no reply was drafted"
              }.`,
            },
            {
              label: "Evidence missing",
              value: EVIDENCE_LEVEL_META[evidenceLevel(h.evidence_level)].allowsAnswer ? "Nothing: evidence was sufficient, another check required a human" : (SUFFICIENCY_REASON_LABELS[h.evidence_reason] ?? h.evidence_reason),
            },
            { label: "Escalated because", value: h.reason.reason, hint: `Rule ${h.reason.rule} in ${h.policy_version}` },
          ]}
        />
        {h.unresolved_questions.length ? (
          <div>
            <h3 className="mb-1 text-xs font-medium text-ink">Unresolved questions</h3>
            <ul className="list-disc space-y-0.5 pl-5 text-[13px] text-ink-2">
              {h.unresolved_questions.map((q) => (
                <li key={q}>{q}</li>
              ))}
            </ul>
          </div>
        ) : null}
        {h.suggested_opening ? (
          <div>
            <h3 className="mb-1 text-xs font-medium text-ink">Suggested opening</h3>
            <blockquote className="rounded-md border border-line bg-canvas px-3 py-2 text-[13px] text-ink-2">{h.suggested_opening}</blockquote>
          </div>
        ) : null}
        {h.draft_if_any ? (
          <div>
            <h3 className="mb-1 text-xs font-medium text-danger">Rejected draft (blocked by verification): review before any use</h3>
            <blockquote className="rounded-md border border-danger-line bg-danger-bg px-3 py-2 text-[13px] text-ink-2">{h.draft_if_any}</blockquote>
          </div>
        ) : null}
        {h.historical_examples.length ? (
          <div>
            <h3 className="mb-1 text-xs font-medium text-ink">Historical examples</h3>
            <p className="mb-2 text-xs text-ink-3">For reference only. These were not verified as a solution for this customer.</p>
            <ul className="space-y-2">
              {h.historical_examples.slice(0, 3).map((e) => (
                <li key={e.evidence_id} className="rounded-md border border-line px-3 py-2 text-xs">
                  <div className="flex flex-wrap justify-between gap-2 text-ink-3">
                    <span className="font-mono">case {e.evidence_id}</span>
                    <span className="tabular">
                      {e.action_class} · similarity {fixed(e.similarity)}
                    </span>
                  </div>
                  <p className="mt-1 line-clamp-2 text-ink-2">{e.customer_message}</p>
                  <p className="mt-1 line-clamp-2 text-ink">{e.brand_reply}</p>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        <p className="text-[11px] text-ink-3">
          The severity and queue labels only group the policy reason code for triage in this console. The agent does not produce them.
        </p>
      </div>
    </Card>
  );
}
