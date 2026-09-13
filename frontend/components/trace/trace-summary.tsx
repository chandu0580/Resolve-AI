import { Card } from "@/components/ui/card";
import type { AgentTrace } from "@/lib/api/types";
import { explainTrace, summarizeTraceDecision } from "@/lib/explain";
import { duration } from "@/lib/format";
import { groupTraceEvents } from "@/lib/trace";

/** Answers what happened, why, how long it took, what failed and what evidence was involved, from the recorded trace only. */
export function traceSummaryAnswers(trace: AgentTrace) {
  const explanation = explainTrace(trace);
  const s = summarizeTraceDecision(trace);
  const latency = (trace.latency_ms ?? {}) as Record<string, number>;
  const stages = groupTraceEvents(trace.events, trace.stage_status, latency);
  const timed = stages.filter((g) => typeof g.durationMs === "number" && g.durationMs > 0).sort((a, b) => (b.durationMs ?? 0) - (a.durationMs ?? 0));
  const failedStages = stages.filter((g) => g.status === "error" || g.status === "fallback").map((g) => `${g.label} (${g.status})`);
  const failures = ((trace as unknown as { failures?: { category: string; stage: string; kind: string }[] }).failures ?? []).map(
    (f) => `${f.category.replace(/_/g, " ")} at ${f.stage.replace(/_/g, " ")} (${f.kind})`,
  );
  const failed = [...failedStages, ...failures, ...(trace.error ? [`Recorded error: ${trace.error}`] : [])];
  const ids = s.retrieval?.evidence_ids ?? [];
  return {
    what: explanation ? `${explanation.decision} ${explanation.reason}` : "The execution did not reach a decision.",
    why: explanation ? explanation.policy : "No policy decision recorded.",
    howLong: `${duration(latency.total)} in total${timed[0] ? `; slowest stage ${timed[0].label} (${duration(timed[0].durationMs)})` : ""}.`,
    whatFailed: failed.length ? failed.join("; ") : "Nothing failed: every recorded stage completed or was skipped by design.",
    evidence: `${explanation?.evidence ?? "No evidence recorded."}${ids.length ? ` Case ids retrieved: ${ids.join(", ")}.` : ""}`,
  };
}

export function TraceSummaryCard({ trace }: { trace: AgentTrace }) {
  const a = traceSummaryAnswers(trace);
  const rows: [string, string][] = [
    ["What happened", a.what],
    ["Why", a.why],
    ["How long", a.howLong],
    ["What failed", a.whatFailed],
    ["What evidence", a.evidence],
  ];
  return (
    <Card title="Trace summary" description="Read from the recorded events. Traces never store customer text, evidence text, secrets or model reasoning.">
      <dl className="grid gap-y-2.5">
        {rows.map(([label, value]) => (
          <div key={label} className="grid gap-0.5 sm:grid-cols-[8rem_minmax(0,1fr)] sm:gap-3">
            <dt className="text-[11px] font-semibold tracking-wide text-ink-3 uppercase sm:pt-0.5">{label}</dt>
            <dd className="min-w-0 text-[13px] break-words text-ink">{value}</dd>
          </div>
        ))}
      </dl>
    </Card>
  );
}
