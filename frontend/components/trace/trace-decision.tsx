import { EyeOff } from "lucide-react";
import { Card, KeyValues, Mono, Notice } from "@/components/ui/card";
import { ConfidenceMeter } from "@/components/ui/meter";
import { BandBadge } from "@/components/ui/status";
import { DecisionBanner } from "@/components/decision/decision-banner";
import { EvidenceSufficiency } from "@/components/decision/evidence-sufficiency";
import { OutputGateChecklist } from "@/components/decision/output-gate";
import { RiskFlagList } from "@/components/decision/risk-flags";
import type { Action, AgentTrace } from "@/lib/api/types";
import { dateTime, duration, fixed, humanize, usd } from "@/lib/format";
import { summarizeTraceDecision } from "@/lib/explain";
import { ACTION_META, intentLabel, reasonMeta } from "@/lib/labels";

export { summarizeTraceDecision };

export function TraceDecisionView({ trace, showTextNotice = true }: { trace: AgentTrace; showTextNotice?: boolean }) {
  const s = summarizeTraceDecision(trace);
  if (!s.action) {
    return (
      <Notice tone="danger" title="This execution did not reach a decision">
        {trace.error ? `Recorded error: ${trace.error}` : "The trace has no final decision."}
      </Notice>
    );
  }
  const laterStage = s.policy?.reason_code && s.policy.reason_code !== s.reasonCode;
  const why =
    s.action === "AUTO_HANDLE"
      ? ACTION_META.AUTO_HANDLE.summary
      : `${reasonMeta(s.reasonCode).label}.${laterStage ? ` The policy stage allowed ${humanize(s.policy?.decision).toLowerCase()}; a later stage changed the outcome.` : ""}`;
  return (
    <div className="space-y-4">
      {showTextNotice ? (
        <Notice tone="info" icon={EyeOff} title="Reconstructed from the audit trace">
          Audit traces never store customer text or evidence text, so this view shows only the recorded decision data. The full conversation workspace is available for conversations run from this browser.
        </Notice>
      ) : null}
      <DecisionBanner
        outcome={{ action: s.action, reason_code: s.reasonCode, rule: s.policy?.rule ?? "n/a", policy_version: s.policy?.policy_version ?? trace.versions?.policy ?? "n/a", why }}
      />
      <div className="grid gap-4 md:grid-cols-2">
        <Card title="Intent" headingLevel={3}>
          {s.finalIntent ? (
            <div className="space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm font-medium text-ink">{intentLabel(s.finalIntent)}</span>
                <BandBadge band={s.intent?.band} />
              </div>
              {typeof s.intent?.confidence === "number" ? <ConfidenceMeter value={s.intent.confidence} label="Calibrated intent confidence" /> : null}
              <p className="text-xs text-ink-3">{s.second?.applied ? `A model second opinion changed ${intentLabel(s.second.before)} to ${intentLabel(s.second.after)}.` : "Classifier answer used directly."}</p>
            </div>
          ) : (
            <p className="text-[13px] text-ink-3">No intent recorded.</p>
          )}
        </Card>
        <Card title="Evidence sufficiency" headingLevel={3}>
          {s.evidence ? (
            <EvidenceSufficiency
              evidence={{
                sufficiency_level: s.evidence.level,
                sufficiency_reason: s.evidence.reason,
                sufficient: s.evidence.sufficient,
                resolution_confidence: s.evidence.resolution_confidence,
                consistency: s.evidence.consistency,
                gate_version: s.evidence.gate_version,
              }}
            />
          ) : (
            <p className="text-[13px] text-ink-3">The evidence gate did not run.</p>
          )}
        </Card>
        <Card title="Risk" headingLevel={3}>
          <RiskFlagList flags={s.risk?.flags ?? []} source={s.risk?.source} />
        </Card>
        <Card title="Retrieval" headingLevel={3}>
          {s.retrieval ? (
            <KeyValues
              items={[
                { label: "Retriever", value: <Mono>{s.retrieval.retriever ?? "n/a"}</Mono> },
                { label: "Candidates", value: s.retrieval.n_retrieved ?? "n/a" },
                { label: "Top similarity", value: fixed(s.retrieval.top_similarity) },
                { label: "Case ids", value: <Mono>{(s.retrieval.evidence_ids ?? []).join(", ") || "none"}</Mono>, hint: "Evidence text is not stored in traces." },
              ]}
            />
          ) : (
            <p className="text-[13px] text-ink-3">Retrieval was not recorded.</p>
          )}
        </Card>
      </div>
      {s.clarification ? (
        <Card title="Clarification" headingLevel={3}>
          <KeyValues
            items={[
              { label: "Missing information", value: (s.clarification.missing ?? []).join("; ") || "none" },
              { label: "Already provided", value: (s.clarification.already_provided ?? []).join(", ") || "nothing" },
            ]}
          />
        </Card>
      ) : null}
      {s.gate?.gates ? (
        <Card title="Output gate" description="An automatic reply requires every check.">
          <OutputGateChecklist gate={s.gate.gates} blocking={s.gate.blocking} />
        </Card>
      ) : null}
    </div>
  );
}

export function TraceFacts({ trace }: { trace: AgentTrace }) {
  const v = trace.versions;
  const usage = (trace.usage ?? []) as {
    model?: string;
    calls?: number;
    tokens_in?: number;
    tokens_out?: number;
    cache_hits?: number;
    estimated_cost_usd?: number;
    retries?: number;
    timeouts?: number;
    errors?: number;
    budget_exhausted?: number;
  }[];
  const failures = ((trace as unknown as { failures?: { category: string; stage: string; kind: string }[] }).failures ?? []).map(
    (f) => `${f.category.replace(/_/g, " ")} at ${f.stage.replace(/_/g, " ")} (${f.kind})`,
  );
  const reliability = usage
    .map((u) => `${u.retries ?? 0} retries, ${u.timeouts ?? 0} timeouts, ${u.errors ?? 0} failed attempts${u.budget_exhausted ? `, ${u.budget_exhausted} refused (budget spent)` : ""}`)
    .join("; ");
  const meta = (trace.request_meta ?? {}) as Record<string, unknown>;
  const prompts = (v?.prompts ?? trace.prompt_versions ?? {}) as unknown as Record<string, string>;
  return (
    <Card title="Trace record">
      <KeyValues
        items={[
          { label: "Trace id", value: <Mono>{trace.trace_id}</Mono> },
          { label: "Request id", value: <Mono>{trace.request_id || "n/a"}</Mono> },
          { label: "Started", value: dateTime(trace.started_at) },
          { label: "Finished", value: dateTime(trace.finished_at) },
          { label: "Total latency", value: duration((trace.latency_ms as Record<string, number> | undefined)?.total) },
          { label: "Final decision", value: trace.final_decision ? ACTION_META[trace.final_decision as Action]?.label ?? trace.final_decision : "none" },
          ...(trace.error ? [{ label: "Error", value: trace.error }] : []),
          { label: "Channel / locale", value: `${(meta.channel as string) ?? "n/a"} / ${(meta.locale as string) ?? "n/a"}` },
          { label: "Pipeline", value: <Mono>{trace.pipeline_version || v?.pipeline || "n/a"}</Mono> },
          { label: "Policy", value: <Mono>{v?.policy ?? "n/a"}</Mono> },
          { label: "Evidence gate", value: <Mono>{v ? `${v.evidence_gate} · ${v.rerank}` : "n/a"}</Mono> },
          { label: "Output gate", value: <Mono>{v?.output_gate ?? "n/a"}</Mono> },
          { label: "Retrieval", value: <Mono>{v?.retrieval ?? "n/a"}</Mono> },
          { label: "Classifier", value: <Mono>{v?.classifier ?? "n/a"}</Mono> },
          { label: "Model", value: <Mono>{v?.model ?? "none"}</Mono> },
          { label: "Prompts", value: <Mono>{Object.entries(prompts).map(([k, p]) => `${k}: ${p}`).join(", ") || "n/a"}</Mono> },
          { label: "Config hash", value: <Mono>{trace.config_hash || v?.config_hash || "n/a"}</Mono> },
          {
            label: "Model usage",
            value: usage.length
              ? usage.map((u) => `${u.model}: ${u.calls} calls (${u.cache_hits ?? 0} cached), ${u.tokens_in ?? 0}/${u.tokens_out ?? 0} tokens, ${usd(u.estimated_cost_usd)}`).join("; ")
              : "No model calls",
          },
          ...(usage.length ? [{ label: "Model reliability", value: reliability }] : []),
          { label: "Classified failures", value: failures.length ? failures.join("; ") : "None recorded", hint: failures.length ? "Codes only; the trace never stores error text from customer input." : undefined },
          ...(typeof (trace as unknown as { budget_s?: number | null }).budget_s === "number"
            ? [{ label: "Request time budget", value: `${(trace as unknown as { budget_s: number }).budget_s} s` }]
            : []),
        ]}
      />
      <p className="mt-3 text-[11px] text-ink-3">Traces store identifiers, versions, statuses, latencies and decision data. They never store customer text, secrets or model reasoning.</p>
    </Card>
  );
}
