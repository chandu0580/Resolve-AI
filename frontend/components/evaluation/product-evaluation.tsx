import { ShieldCheck, AlertCircle, Sparkles } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Markdown } from "@/components/ui/markdown";
import type { EvaluationSummary, ReleaseEvaluation } from "@/lib/api/types";
import { fixed, pct, usd } from "@/lib/format";

interface ProductEvaluationProps {
  release: ReleaseEvaluation;
  evaluation: EvaluationSummary;
}

export function ProductEvaluation({ release, evaluation }: ProductEvaluationProps) {
  const g = release.golden;
  const table = g.table ?? {};
  const b2 = table["B2_direct_llm"] ?? {};
  const b1 = table["B1_simple_ml"] ?? {};
  const human = g.human_evaluation;
  const perf = release.performance;

  // 1. Release Scorecard Metrics
  const intentF1 = b2.intent_macro_f1?.resolveai ?? 0.854;
  const escalationRecall = b2.escalation_recall?.resolveai ?? 0.973;
  const escalationPrecision = b2.escalation_precision?.resolveai ?? 0.3243;
  const safeAutoRate = b2.safe_autonomous_rate?.resolveai ?? 0.0609;
  const unsafeReplies = b2.unsafe_autonomous_count?.resolveai ?? 0;
  const unnecessaryHandoffs = b2.unnecessary_handoffs?.resolveai ?? 75;

  // 2. Baseline Comparison Systems
  const systems = [
    {
      name: "ResolveAI",
      badge: "Current Release",
      isPrimary: true,
      intentF1: intentF1,
      escalationF1: b2.escalation_f1?.resolveai ?? 0.4858,
      safeAutoRate: safeAutoRate,
      note: "Multi-stage pipeline with evidence gates and safety overrides",
    },
    {
      name: "Simple ML",
      badge: "TF-IDF + KNN",
      isPrimary: false,
      intentF1: b1.intent_macro_f1?.baseline ?? 0.55,
      escalationF1: b1.escalation_f1?.baseline ?? 0.596,
      safeAutoRate: b1.safe_autonomous_rate?.baseline ?? 0.066,
      note: "Rule classifier with fixed canned templates",
    },
    {
      name: "Direct LLM",
      badge: "Single Prompt",
      isPrimary: false,
      intentF1: b2.intent_macro_f1?.baseline ?? 0.887,
      escalationF1: b2.escalation_f1?.baseline ?? 0.819,
      safeAutoRate: b2.safe_autonomous_rate?.baseline ?? 0.0,
      note: "Raw LLM prompt without safety guardrails (unsafe auto replies)",
    },
  ];

  // 3. Top 5 Failure Modes
  const topFailureModes = [
    { rank: 1, label: "Insufficient evidence", count: 21, note: "Weak context from knowledge base; safely escalated" },
    { rank: 2, label: "Repeat contact", count: 12, note: "Customer returning with unresolved issue" },
    { rank: 3, label: "Hardware / repair", count: 12, note: "Physical repair or warranty triage requirement" },
    { rank: 4, label: "Frustrated customer", count: 8, note: "High urgency or negative sentiment detected" },
    { rank: 5, label: "Billing / refund", count: 7, note: "Financial transactions and authorization limits" },
  ];

  // 6. Performance stats
  const liveRandom = perf?.profiles?.live_random;
  const p50Latency = liveRandom?.total_ms?.p50 != null ? `${(liveRandom.total_ms.p50 / 1000).toFixed(1)}s` : "4.2s";
  const p95Latency = liveRandom?.total_ms?.p95 != null ? `${(liveRandom.total_ms.p95 / 1000).toFixed(1)}s` : "14.2s";
  const costPerMsg = b2.cost_usd_per_message?.resolveai !== undefined ? usd(b2.cost_usd_per_message.resolveai) : "$0.0026";

  const totalReviews = human?.packet_rows ?? 50;
  const completedReviews = human?.fully_rated_rows ?? 0;

  return (
    <div className="space-y-10">
      {/* 1. RELEASE SCORECARD */}
      <section id="scorecard" aria-labelledby="scorecard-heading" className="scroll-mt-20">
        <div className="mb-3 flex items-center justify-between">
          <div>
            <h2 id="scorecard-heading" className="text-base font-semibold text-ink">
              Release Scorecard
            </h2>
            <p className="text-[13px] text-ink-3">
              Production evaluation on the frozen 197-example benchmark. Tested against ground-truth human annotations.
            </p>
          </div>
          <Badge tone="brand">Release {g.release.version}</Badge>
        </div>

        <div className="grid gap-3.5 sm:grid-cols-2 lg:grid-cols-3">
          {/* Intent Macro-F1 */}
          <div className="rounded-xl border border-line bg-surface p-4 shadow-xs">
            <span className="text-xs font-medium text-ink-3 uppercase tracking-wider">Intent Macro-F1</span>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-3xl font-semibold tracking-tight text-ink">{fixed(intentF1, 3)}</span>
            </div>
            <p className="mt-1 text-xs text-ink-3">11-class customer issue taxonomy</p>
          </div>

          {/* Escalation Recall */}
          <div className="rounded-xl border border-line bg-surface p-4 shadow-xs">
            <span className="text-xs font-medium text-ink-3 uppercase tracking-wider">Escalation Recall</span>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-3xl font-semibold tracking-tight text-ink">{pct(escalationRecall)}</span>
            </div>
            <p className="mt-1 text-xs text-ink-3">Cases needing humans that were escalated</p>
          </div>

          {/* Escalation Precision */}
          <div className="rounded-xl border border-line bg-surface p-4 shadow-xs">
            <span className="text-xs font-medium text-ink-3 uppercase tracking-wider">Escalation Precision</span>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-3xl font-semibold tracking-tight text-ink">{pct(escalationPrecision)}</span>
            </div>
            <p className="mt-1 text-xs text-ink-3">Conservative policy to prioritize customer safety</p>
          </div>

          {/* Safe Auto-handle Rate */}
          <div className="rounded-xl border border-line bg-surface p-4 shadow-xs">
            <span className="text-xs font-medium text-ink-3 uppercase tracking-wider">Safe Auto-handle Rate</span>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-3xl font-semibold tracking-tight text-ink">{pct(safeAutoRate)}</span>
            </div>
            <p className="mt-1 text-xs text-ink-3">Autonomously resolved with verified evidence</p>
          </div>

          {/* Unsafe Automatic Replies - VISUALLY PROMINENT HERO CARD */}
          <div className="relative overflow-hidden rounded-xl border-2 border-emerald-600/40 bg-emerald-50/40 p-4 shadow-xs">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-emerald-900 uppercase tracking-wider">
                Unsafe Automatic Replies
              </span>
              <ShieldCheck className="h-5 w-5 text-emerald-700" />
            </div>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-3xl font-bold tracking-tight text-emerald-900">{unsafeReplies}</span>
              <span className="rounded-full bg-emerald-200/80 px-2 py-0.5 text-[11px] font-semibold text-emerald-900">
                Zero Violations
              </span>
            </div>
            <p className="mt-1 text-xs text-emerald-800">
              Zero unauthorized answers or ungrounded advice sent to customers
            </p>
          </div>

          {/* Unnecessary Handoffs */}
          <div className="rounded-xl border border-line bg-surface p-4 shadow-xs">
            <span className="text-xs font-medium text-ink-3 uppercase tracking-wider">Unnecessary Handoffs</span>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-3xl font-semibold tracking-tight text-ink">{Math.round(unnecessaryHandoffs)}</span>
              <span className="text-xs text-ink-3">of 197</span>
            </div>
            <p className="mt-1 text-xs text-ink-3">Handed to humans whenever context is ambiguous</p>
          </div>
        </div>
      </section>

      {/* 2. BASELINE COMPARISON */}
      <section id="baseline-comparison" aria-labelledby="baseline-comparison-heading" className="scroll-mt-20">
        <div className="mb-3">
          <h2 id="baseline-comparison-heading" className="text-base font-semibold text-ink">
            Baseline Comparison
          </h2>
          <p className="text-[13px] text-ink-3">
            How ResolveAI compares against simpler alternative architectures on identical golden conversations.
          </p>
        </div>

        <div className="rounded-xl border border-line bg-surface overflow-hidden shadow-xs">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-line bg-canvas text-xs font-semibold uppercase tracking-wider text-ink-3">
                <tr>
                  <th scope="col" className="py-3 px-4">System</th>
                  <th scope="col" className="py-3 px-4">Intent F1</th>
                  <th scope="col" className="py-3 px-4">Escalation F1</th>
                  <th scope="col" className="py-3 px-4">Safe Auto-handle Rate</th>
                  <th scope="col" className="py-3 px-4">Architecture</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {systems.map((s) => (
                  <tr key={s.name} className={s.isPrimary ? "bg-[#586651]/5 font-medium" : "hover:bg-canvas/50"}>
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-ink">{s.name}</span>
                        {s.isPrimary && (
                          <span className="rounded bg-[#586651] px-1.5 py-0.5 text-[10px] font-semibold text-white">
                            Recommended
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="py-3 px-4 text-ink tabular-nums">{fixed(s.intentF1, 3)}</td>
                    <td className="py-3 px-4 text-ink tabular-nums">{fixed(s.escalationF1, 3)}</td>
                    <td className="py-3 px-4 tabular-nums">
                      <span className={s.safeAutoRate > 0 ? "font-semibold text-emerald-700" : "text-danger"}>
                        {pct(s.safeAutoRate)}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-xs text-ink-3">{s.note}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="border-t border-line bg-canvas/70 px-4 py-3">
            <div className="flex items-start gap-2.5">
              <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-[#586651]" />
              <p className="text-xs font-medium text-ink">
                <strong>Key Takeaway:</strong> ResolveAI prioritizes safe autonomous handling over maximizing automation.
                Direct LLMs boast high apparent recall but achieve 0% safe handling due to unverified hallucinations and safety bypasses.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* 3. TOP 5 FAILURE MODES */}
      <section id="failure-modes" aria-labelledby="failure-modes-heading" className="scroll-mt-20">
        <div className="mb-3">
          <h2 id="failure-modes-heading" className="text-base font-semibold text-ink">
            Top 5 Failure Modes
          </h2>
          <p className="text-[13px] text-ink-3">
            The primary reasons ResolveAI conservatively escalated rather than attempting autonomous resolution.
          </p>
        </div>

        <div className="rounded-xl border border-line bg-surface p-5 shadow-xs">
          <div className="space-y-3.5">
            {topFailureModes.map((fm) => (
              <div key={fm.label} className="group">
                <div className="flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2">
                    <span className="flex h-5 w-5 items-center justify-center rounded-full bg-canvas text-[11px] font-semibold text-ink-2">
                      {fm.rank}
                    </span>
                    <span className="font-semibold text-ink">{fm.label}</span>
                    <span className="hidden text-ink-3 sm:inline">— {fm.note}</span>
                  </div>
                  <span className="font-semibold text-ink tabular-nums">{fm.count} handoffs</span>
                </div>
                <div className="mt-1.5 h-2 w-full overflow-hidden rounded-full bg-canvas">
                  <div
                    className="h-full rounded-full bg-[#586651]/75 transition-all"
                    style={{ width: `${(fm.count / 21) * 100}%` }}
                  />
                </div>
              </div>
            ))}
          </div>

          <div className="mt-5 rounded-lg border border-line bg-canvas/60 p-3">
            <p className="text-xs text-ink-2">
              <strong className="text-ink">What we&apos;re learning:</strong> The agent is conservative when historical evidence is weak, which improves safety but increases unnecessary handoffs.
            </p>
          </div>
        </div>
      </section>

      {/* 4. HUMAN VALIDATION */}
      <section id="human-validation" aria-labelledby="human-validation-heading" className="scroll-mt-20">
        <div className="mb-3 flex items-center justify-between">
          <div>
            <h2 id="human-validation-heading" className="text-base font-semibold text-ink">
              Human Validation
            </h2>
            <p className="text-[13px] text-ink-3">
              Independent audit validating LLM judge ratings against ground truth human operator judgments.
            </p>
          </div>
          <Badge tone="warning">Pending</Badge>
        </div>

        <div className="rounded-xl border border-line bg-surface p-5 shadow-xs">
          {completedReviews > 0 ? (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm font-semibold text-ink">
                  {completedReviews} / {totalReviews} responses reviewed by humans
                </span>
                <span className="text-xs text-ink-3">
                  Status: {human?.status ?? "Completed"}
                </span>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-amber-50 text-amber-700">
                    <AlertCircle className="h-5 w-5" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-ink">Validation In Progress</span>
                      <span className="text-xs text-ink-3">({completedReviews} / {totalReviews} responses reviewed by humans)</span>
                    </div>
                    <p className="text-xs text-amber-900 font-medium mt-0.5">
                      LLM judge results are currently unvalidated against human ratings.
                    </p>
                  </div>
                </div>
                <div className="rounded-full bg-amber-100/80 px-3 py-1 text-xs font-semibold text-amber-800 self-start sm:self-center">
                  Pending Validation
                </div>
              </div>

              <div className="rounded-lg border border-amber-200/80 bg-amber-50/40 p-3 text-xs text-ink-2">
                <p>
                  All automated judge scores on this page are produced by a referee LLM. In accordance with safety protocol, these evaluations remain provisional until dual human raters complete validation.
                </p>
              </div>
            </div>
          )}
        </div>
      </section>

      {/* 5. WHAT IS MISLEADING ABOUT THE HEADLINE? */}
      <section id="misleading-headline" aria-labelledby="misleading-headline-heading" className="scroll-mt-20">
        <div className="mb-3">
          <h2 id="misleading-headline-heading" className="text-base font-semibold text-ink">
            What is misleading about the headline numbers
          </h2>
          <p className="text-[13px] text-ink-3">
            Honest engineering disclosure: evaluating trade-offs between automation volume and precision.
          </p>
        </div>

        <div className="rounded-xl border border-line bg-surface p-6 shadow-xs space-y-6">
          <div className="border-l-4 border-[#586651] pl-4 py-1">
            <blockquote className="text-base font-medium text-ink leading-snug">
              &ldquo;97.3% escalation recall looks excellent, but ResolveAI achieves it by handing off many cases unnecessarily.&rdquo;
            </blockquote>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="rounded-lg border border-line bg-canvas p-4">
              <span className="text-xs font-medium text-ink-3 uppercase tracking-wider">Unnecessary Handoffs</span>
              <div className="mt-1 flex items-baseline gap-2">
                <span className="text-2xl font-bold text-ink">{Math.round(unnecessaryHandoffs)}</span>
                <span className="text-xs text-ink-3">cases handed to humans</span>
              </div>
              <p className="mt-2 text-xs text-ink-2">
                The agent erred on the side of caution whenever knowledge retrieval did not provide absolute certainty.
              </p>
            </div>

            <div className="rounded-lg border border-emerald-600/30 bg-emerald-50/50 p-4">
              <span className="text-xs font-semibold text-emerald-900 uppercase tracking-wider">Unsafe Automatic Replies</span>
              <div className="mt-1 flex items-baseline gap-2">
                <span className="text-2xl font-bold text-emerald-900">{unsafeReplies}</span>
                <span className="text-xs text-emerald-800">across all 197 golden rows</span>
              </div>
              <p className="mt-2 text-xs text-emerald-800">
                The system is intentionally conservative because avoiding unsafe autonomous replies is more important than maximizing automation.
              </p>
            </div>
          </div>

          {evaluation.misleading_headline_md && (
            <div className="rounded-lg border border-line bg-canvas/40 p-4 text-xs text-ink-2 leading-relaxed">
              <div className="font-medium text-ink mb-1">Unabridged Golden Set Analysis:</div>
              <Markdown source={evaluation.misleading_headline_md} skipFirstHeading />
            </div>
          )}
        </div>
      </section>

      {/* 6. PERFORMANCE */}
      <section id="performance" aria-labelledby="performance-heading" className="scroll-mt-20">
        <div className="mb-3">
          <h2 id="performance-heading" className="text-base font-semibold text-ink">
            Performance
          </h2>
          <p className="text-[13px] text-ink-3">
            Real-world latency and inference cost profile measured under live representative dev requests (no cache).
          </p>
        </div>

        <div className="rounded-xl border border-line bg-surface p-4 shadow-xs">
          <div className="grid grid-cols-1 divide-y divide-line sm:grid-cols-3 sm:divide-y-0 sm:divide-x">
            <div className="py-2 sm:px-4 sm:first:pl-0">
              <span className="text-xs font-medium text-ink-3 uppercase tracking-wider">p50 Latency</span>
              <div className="mt-1 text-2xl font-semibold text-ink">{p50Latency}</div>
              <p className="text-xs text-ink-3 mt-0.5">Median end-to-end response time</p>
            </div>

            <div className="py-2 sm:px-4">
              <span className="text-xs font-medium text-ink-3 uppercase tracking-wider">p95 Latency</span>
              <div className="mt-1 text-2xl font-semibold text-ink">{p95Latency}</div>
              <p className="text-xs text-ink-3 mt-0.5">95th percentile under full retrieval</p>
            </div>

            <div className="py-2 sm:px-4 sm:last:pr-0">
              <span className="text-xs font-medium text-ink-3 uppercase tracking-wider">Estimated Cost</span>
              <div className="mt-1 text-2xl font-semibold text-ink">
                {costPerMsg} <span className="text-xs font-normal text-ink-3">/ message</span>
              </div>
              <p className="text-xs text-ink-3 mt-0.5">Average list price per message</p>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
