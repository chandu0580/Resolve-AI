import type { Metadata } from "next";
import { TriangleAlert } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";
import { Badge } from "@/components/ui/badge";
import { Card, KeyValues, Mono, Notice, PageHeader } from "@/components/ui/card";
import { DistributionBar, Kpi, KpiGrid } from "@/components/ui/kpi";
import { Markdown } from "@/components/ui/markdown";
import { ErrorState } from "@/components/ui/states";
import { DataTable, TD, TH } from "@/components/ui/table";
import { BarList } from "@/components/evaluation/bars";
import { DatasetBadge, ReleaseSections } from "@/components/evaluation/release";
import { ProductEvaluation } from "@/components/evaluation/product-evaluation";
import { type ApiError, api, load } from "@/lib/api/client";
import type { Bootstrap, EvaluationSummary, ReleaseEvaluation } from "@/lib/api/types";
import { toErrorInfo } from "@/lib/errors";
import { duration, fixed, humanize, pct, usd } from "@/lib/format";

export const metadata: Metadata = { title: "Evaluations" };

const SYSTEM_LABELS: Record<string, string> = {
  resolveai_full: "ResolveAI (full)",
  B0_trivial: "B0 trivial",
  B0_trivial_always_handoff: "B0 always hand off",
  B1_simple_ml: "B1 simple ML",
  B2_direct_llm: "B2 direct LLM",
  minus_second_opinion: "Without second opinion",
  minus_resolution_rerank: "Without resolution rerank",
  minus_risk_llm: "Without risk model",
  minus_retrieval: "Without retrieval",
  offline_weak_drafts: "Offline weak drafts",
};

const label = (k: string) => SYSTEM_LABELS[k] ?? k;
const MAIN = ["resolveai_full", "B2_direct_llm", "B1_simple_ml", "B0_trivial", "B0_trivial_always_handoff"];
const ABLATIONS = ["minus_second_opinion", "minus_resolution_rerank", "minus_risk_llm", "minus_retrieval"];
const JUDGE_DIMENSIONS = ["groundedness", "relevance", "actionability", "completeness", "policy_compliance", "tone"];

const ciPair = (b?: Bootstrap | null): [number, number] | null => (b ? [b.ci_low, b.ci_high] : null);
const ciText = (b: Bootstrap, f: (v: number) => string) => `${f(b.ci_low)} to ${f(b.ci_high)}`;

function Section({ id, title, description, children }: { id: string; title: string; description?: ReactNode; children: ReactNode }) {
  return (
    <section id={id} aria-labelledby={`${id}-heading`} className="scroll-mt-20">
      <h2 id={`${id}-heading`} className="text-base font-semibold text-ink">
        {title}
      </h2>
      {description ? <p className="mt-0.5 mb-3 max-w-4xl text-[13px] text-ink-3">{description}</p> : <div className="mb-3" />}
      {children}
    </section>
  );
}

const PRIMARY_NAV: [string, string][] = [
  ["scorecard", "Release scorecard"],
  ["baseline-comparison", "Baseline comparison"],
  ["failure-modes", "Failure modes"],
  ["human-validation", "Human validation"],
  ["misleading-headline", "Misleading headline"],
  ["performance", "Performance"],
  ["advanced-details", "Advanced details"],
];

function EvaluationHeader() {
  return (
    <PageHeader
      eyebrow="Insights"
      title="ResolveAI Evaluation"
      description="Is ResolveAI actually good, safe, and better than simple alternatives? Frozen golden set results, safety guardrails, and baseline comparisons."
      actions={
        <Link href="#misleading-headline" className="text-[13px] font-medium text-[#586651] hover:underline">
          Read the misleading headline analysis
        </Link>
      }
    />
  );
}

function ReleaseBlock({ release }: { release: { data: ReleaseEvaluation; error: null } | { data: null; error: ApiError } }) {
  return release.error ? (
    <div className="mb-9">
      <ErrorState error={toErrorInfo(release.error)} compact />
    </div>
  ) : (
    <div className="mb-12">
      <ReleaseSections release={release.data} />
    </div>
  );
}

export default async function EvaluationPage() {
  const [res, release] = await Promise.all([load(api.evaluationSummary()), load(api.evaluationRelease())]);
  if (res.error) {
    return (
      <>
        <EvaluationHeader />
        <ReleaseBlock release={release} />
        <ErrorState error={toErrorInfo(res.error)} />
      </>
    );
  }
  const e: EvaluationSummary = res.data;
  const h = e.headline;
  const systems = e.systems;
  const present = (keys: string[]) => keys.filter((k) => systems[k]);
  const autoCount = Math.round(h.auto_handle_rate * h.n);
  const rq = e.reply_quality?.primary;
  const retrieval = e.retrieval;
  const human = e.agreement?.human;
  const crossFamily = e.agreement?.cross_family as { n?: number; note?: string; per_dimension?: { ordinal?: Record<string, { weighted_kappa?: number; weighted_kappa_ci?: [number, number] }> } } | undefined;
  const groundKappa = crossFamily?.per_dimension?.ordinal?.groundedness;

  return (
    <>
      <EvaluationHeader />
      <nav aria-label="Evaluation sections" className="mb-8 flex flex-wrap gap-2">
        {PRIMARY_NAV.map(([id, text]) => (
          <a
            key={id}
            href={`#${id}`}
            className="rounded-full border border-line bg-surface px-3 py-1 text-xs font-medium text-ink-2 hover:border-[#586651] hover:text-ink transition-colors shadow-2xs"
          >
            {text}
          </a>
        ))}
      </nav>

      {/* PRIMARY SECTIONS 1 TO 6 */}
      {release.data && <ProductEvaluation release={release.data} evaluation={e} />}

      {/* 7. ADVANCED EVALUATION DETAILS (COLLAPSED BY DEFAULT) */}
      <section id="advanced-details" aria-labelledby="advanced-details-heading" className="mt-14 scroll-mt-20">
        <details className="group rounded-xl border border-line bg-surface p-6 shadow-xs transition-all">
          <summary className="cursor-pointer list-none flex flex-wrap items-center justify-between gap-2 font-semibold text-ink hover:text-[#586651] select-none">
            <div className="flex items-center gap-3">
              <span id="advanced-details-heading" className="text-base font-semibold text-ink">
                Advanced evaluation details
              </span>
              <span className="rounded-full bg-canvas border border-line px-2.5 py-0.5 text-xs font-medium text-ink-3">
                Click to expand technical artifacts, ablations & dev experiments
              </span>
            </div>
            <span className="text-xs font-medium text-ink-3 group-open:rotate-180 transition-transform">
              ▼
            </span>
          </summary>

          <div className="mt-6 space-y-10 border-t border-line pt-6">
            <div className="mb-4">
              <Notice tone="warning" icon={TriangleAlert} title="Evaluation results are based on a frozen 197-example golden set.">
                Intervals are 95% bootstrap intervals (1,000 resamples, seed 42). Small counts move the numbers: the autonomy results rest on {autoCount} automatic replies, and {h.missed_escalations} missed
                escalations already cost several points of recall. These sections evaluate the configuration before the release 1.0.0 changes; the release scorecard above is the current release. {e.caveats}
                {e.provenance ? (
                  <span className="mt-1 block text-xs text-ink-3">
                    Golden set sha256 <Mono>{e.provenance.golden_sha256.slice(0, 16)}…</Mono> · {e.provenance.golden_rows} rows · {e.provenance.source}
                  </span>
                ) : null}
              </Notice>
            </div>

            {/* Detailed Release Evaluation Sections */}
            <div className="border-b border-line pb-10">
              <h3 className="text-sm font-semibold text-ink mb-4">Detailed Release Diagnostics & Breakdown</h3>
              <ReleaseBlock release={release} />
            </div>

            {/* Pre-release Development Evaluation Sections */}
            <div className="space-y-9">
              <div className="mb-3 flex flex-wrap items-center gap-x-3 gap-y-1">
                <h3 className="text-sm font-semibold text-ink">Development evaluation: baselines, ablations and judge study</h3>
                <DatasetBadge>FROZEN GOLDEN SET · pre-release configuration</DatasetBadge>
              </div>

              <Section id="headline" title="Headline" description={`System ${label(h.system)} on n = ${h.n}. ${humanize(h.caveat)}.`}>
                <KpiGrid label="Headline metrics">
                  <Kpi label="Intent macro-F1" value={fixed(h.intent_macro_f1.point, 3)} ci={ciText(h.intent_macro_f1, (v) => fixed(v, 3))} />
                  <Kpi label="Escalation recall" value={pct(h.escalation_recall.point)} ci={ciText(h.escalation_recall, (v) => pct(v))} sub={`${h.missed_escalations} missed escalations`} />
                  <Kpi label="Safe auto-handle rate" value={pct(h.safe_auto_handle_rate.point)} ci={ciText(h.safe_auto_handle_rate, (v) => pct(v))} sub={`${h.safe_auto_handle_count} safe automatic replies`} />
                  <Kpi label="Unsafe autonomous responses" value={h.unsafe_auto_handle_count} sub="Auto-handles on rows marked for escalation" />
                  <Kpi label="Judge groundedness" value={h.judge ? `${fixed(h.judge.groundedness, 2)} / 5` : "n/a"} sub="Model judge; human validation pending" />
                  <Kpi label="Judge hallucination rate" value={pct(h.judge_hallucination_rate)} sub="Share of judged responses with an unsupported claim" />
                </KpiGrid>
              </Section>

              <Section id="intent" title="Intent" description="Issue classification on the 11-class AppleSupport taxonomy. Macro-F1 weights rare classes equally.">
                <div className="grid gap-4 lg:grid-cols-2">
                  <Card title="Macro-F1 by system" headingLevel={3}>
                    <BarList
                      label="Intent macro-F1 by system"
                      format={(v) => fixed(v, 3)}
                      rows={[...present(MAIN), ...present(ABLATIONS)].map((k) => ({
                        key: k,
                        label: label(k),
                        value: systems[k].intent.macro_f1,
                        ci: k === "resolveai_full" ? ciPair(h.intent_macro_f1) : null,
                        highlight: k === "resolveai_full",
                      }))}
                    />
                  </Card>
                  <Card title="Accuracy by system" headingLevel={3}>
                    <BarList
                      label="Intent accuracy by system"
                      format={(v) => pct(v)}
                      rows={[...present(MAIN), ...present(ABLATIONS)].map((k) => ({
                        key: k,
                        label: label(k),
                        value: systems[k].intent.accuracy,
                        ci: k === "resolveai_full" ? ciPair(h.intent_accuracy) : null,
                        highlight: k === "resolveai_full",
                      }))}
                    />
                  </Card>
                </div>
              </Section>

              <Section
                id="escalation"
                title="Escalation"
                description="Should this case have gone to a human? Recall counts escalations caught; precision counts how many handoffs were necessary. A conservative policy buys recall with human time."
              >
                <div className="grid gap-4 lg:grid-cols-2">
                  <Card title="Recall by system" headingLevel={3}>
                    <BarList
                      label="Escalation recall by system"
                      format={(v) => pct(v)}
                      rows={[...present(MAIN), ...present(ABLATIONS)].map((k) => ({ key: k, label: label(k), value: systems[k].escalation.recall, ci: k === "resolveai_full" ? ciPair(h.escalation_recall) : null, highlight: k === "resolveai_full" }))}
                    />
                  </Card>
                  <Card title="Precision and F1" headingLevel={3}>
                    <DataTable label="Escalation precision and F1" minWidth={420}>
                      <thead>
                        <tr>
                          <th scope="col" className={TH}>System</th>
                          <th scope="col" className={TH}>Precision</th>
                          <th scope="col" className={TH}>F1</th>
                          <th scope="col" className={TH}>Missed</th>
                          <th scope="col" className={TH}>Unnecessary</th>
                        </tr>
                      </thead>
                      <tbody className="tabular">
                        {[...present(MAIN), ...present(ABLATIONS)].map((k) => (
                          <tr key={k} className={k === "resolveai_full" ? "bg-brand-50/50" : ""}>
                            <th scope="row" className={`${TD} text-left font-normal`}>{label(k)}</th>
                            <td className={TD}>{pct(systems[k].escalation.precision)}</td>
                            <td className={TD}>{fixed(systems[k].escalation.f1, 3)}</td>
                            <td className={TD}>{systems[k].escalation.fn}</td>
                            <td className={TD}>{systems[k].escalation.fp}</td>
                          </tr>
                        ))}
                      </tbody>
                    </DataTable>
                  </Card>
                </div>
              </Section>

              <Section
                id="autonomy"
                title="Autonomy"
                description="Safe means an automatic reply on a row the annotators did not mark for escalation that was either a verified reply citing evidence or the correct fixed template. Grounded means a verified troubleshooting reply with evidence references."
              >
                <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
                  <Card title="ResolveAI decision mix" headingLevel={3}>
                    <DistributionBar
                      label="ResolveAI decision mix on the golden set"
                      segments={[
                        { label: "Auto-handled", value: h.auto_handle_rate, className: "bg-success" },
                        { label: "Clarification", value: h.clarification_rate, className: "bg-warning" },
                        { label: "Human handoff", value: h.handoff_rate, className: "bg-info" },
                      ]}
                    />
                    <KeyValues
                      items={[
                        { label: "Automatic replies", value: `${autoCount} of ${h.n}` },
                        { label: "Safe", value: h.safe_auto_handle_count },
                        { label: "Unsafe", value: h.unsafe_auto_handle_count },
                        { label: "Grounded (verified, cited)", value: `${h.grounded_auto_handle_count} of ${autoCount}` },
                      ]}
                    />
                  </Card>
                  <Card title="Autonomy by system" headingLevel={3} bodyClassName="p-0">
                    <DataTable label="Autonomy by system" minWidth={620}>
                      <thead>
                        <tr>
                          <th scope="col" className={TH}>System</th>
                          <th scope="col" className={TH}>Auto</th>
                          <th scope="col" className={TH}>Clarify</th>
                          <th scope="col" className={TH}>Handoff</th>
                          <th scope="col" className={TH}>Safe</th>
                          <th scope="col" className={TH}>Unsafe</th>
                          <th scope="col" className={TH}>Grounded</th>
                        </tr>
                      </thead>
                      <tbody className="tabular">
                        {[...present(MAIN), ...present(ABLATIONS)].map((k) => {
                          const a = systems[k].autonomy;
                          return (
                            <tr key={k} className={k === "resolveai_full" ? "bg-brand-50/50" : ""}>
                              <th scope="row" className={`${TD} text-left font-normal`}>{label(k)}</th>
                              <td className={TD}>{pct(a.auto_handle_rate)}</td>
                              <td className={TD}>{pct(a.clarification_rate)}</td>
                              <td className={TD}>{pct(a.handoff_rate)}</td>
                              <td className={TD}>{a.safe_auto_handle_count}</td>
                              <td className={`${TD} ${a.unsafe_auto_handle_count ? "font-semibold text-danger" : ""}`}>{a.unsafe_auto_handle_count}</td>
                              <td className={TD}>{a.grounded_auto_handle_count}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </DataTable>
                  </Card>
                </div>
              </Section>

              {retrieval ? (
                <Section id="retrieval" title="Retrieval" description={retrieval.same_resolution_recall.protocol}>
                  <div className="grid gap-4 lg:grid-cols-2">
                    <Card title="Same-resolution recall" headingLevel={3} description={`Scorable on ${retrieval.same_resolution_recall.phase5_pair_rerank_gate_v3.n_ref} golden rows`} bodyClassName="p-0">
                      <DataTable label="Same-resolution recall" minWidth={420}>
                        <thead>
                          <tr>
                            <th scope="col" className={TH}>Retriever</th>
                            <th scope="col" className={TH}>@1</th>
                            <th scope="col" className={TH}>@3</th>
                            <th scope="col" className={TH}>@5</th>
                            <th scope="col" className={TH}>MRR</th>
                          </tr>
                        </thead>
                        <tbody className="tabular">
                          {(
                            [
                              ["Earlier customer-message index", retrieval.same_resolution_recall.phase2_customer_index_gate_v2],
                              ["Pair index + resolution rerank (current)", retrieval.same_resolution_recall.phase5_pair_rerank_gate_v3],
                            ] as const
                          ).map(([name, m]) => (
                            <tr key={name}>
                              <th scope="row" className={`${TD} text-left font-normal`}>{name}</th>
                              <td className={TD}>{fixed(m["recall@1"], 3)}</td>
                              <td className={TD}>{fixed(m["recall@3"], 3)}</td>
                              <td className={TD}>{fixed(m["recall@5"], 3)}</td>
                              <td className={TD}>{fixed(m.mrr, 3)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </DataTable>
                    </Card>
                    <Card title="Resolution-bearing results" headingLevel={3} description={retrieval.resolution_bearing_rank.definition} bodyClassName="p-0">
                      <DataTable label="Resolution-bearing rank" minWidth={420}>
                        <thead>
                          <tr>
                            <th scope="col" className={TH}>Retriever</th>
                            <th scope="col" className={TH}>@1</th>
                            <th scope="col" className={TH}>@3</th>
                            <th scope="col" className={TH}>@5</th>
                            <th scope="col" className={TH}>MRR</th>
                          </tr>
                        </thead>
                        <tbody className="tabular">
                          {(
                            [
                              ["Earlier customer-message index", retrieval.resolution_bearing_rank.phase2_customer_index],
                              ["Pair index + resolution rerank (current)", retrieval.resolution_bearing_rank.phase5_pair_rerank],
                            ] as const
                          ).map(([name, m]) => (
                            <tr key={name}>
                              <th scope="row" className={`${TD} text-left font-normal`}>{name}</th>
                              <td className={TD}>{fixed(m["resolution_bearing@1"], 3)}</td>
                              <td className={TD}>{fixed(m["resolution_bearing@3"], 3)}</td>
                              <td className={TD}>{fixed(m["resolution_bearing@5"], 3)}</td>
                              <td className={TD}>{fixed(m.resolution_mrr, 3)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </DataTable>
                    </Card>
                    <Card title="Evidence gate on the golden set" headingLevel={3}>
                      <DistributionBar
                        label="Evidence sufficiency levels on the golden set"
                        segments={Object.entries(retrieval.evidence_sufficiency_agent_run.levels).map(([lvl, n]) => ({
                          label: `${humanize(lvl.toLowerCase())} (${n})`,
                          value: n,
                          className: lvl === "INSUFFICIENT" ? "bg-neutral" : lvl === "WEAK" ? "bg-warning" : "bg-success",
                        }))}
                      />
                      <KeyValues
                        items={[
                          { label: "Sufficient or strong", value: pct(retrieval.evidence_sufficiency_agent_run.sufficient_rate) },
                          { label: "Same-intent retrieval", value: `${pct(retrieval.same_intent_retrieval.phase5)} (earlier index: ${pct(retrieval.same_intent_retrieval.phase2)})`, hint: retrieval.same_intent_retrieval.definition },
                          {
                            label: "Gate precision estimate",
                            value: (() => {
                              const row = retrieval.gate_precision_estimate.table[retrieval.gate_precision_estimate.chosen];
                              return row ? `${pct(row.precision_resolves_or_partial)} resolves or partially resolves (${row.n_sufficient} cases)` : "n/a";
                            })(),
                            hint: retrieval.gate_precision_estimate.source,
                          },
                        ]}
                      />
                    </Card>
                    <Card title="Retrieval limitations" headingLevel={3}>
                      <ul className="list-disc space-y-1 pl-5 text-[13px] text-ink-2">
                        {retrieval.limitations.map((l) => (
                          <li key={l}>{l}</li>
                        ))}
                      </ul>
                    </Card>
                  </div>
                </Section>
              ) : null}

              <Section
                id="groundedness"
                title="Groundedness and reply quality"
                description={`Scored by a frozen rubric with the ${rq?.judge_model ?? "model"} judge on a 1 to 5 scale. The judge is not yet validated against human ratings, and it scores replies written by its own model family.`}
              >
                <div className="grid gap-4 lg:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
                  {rq ? (
                    <Card title="Judge scores by system" headingLevel={3} bodyClassName="p-0">
                      <DataTable label="Judge scores by system" minWidth={700}>
                        <thead>
                          <tr>
                            <th scope="col" className={TH}>System</th>
                            {JUDGE_DIMENSIONS.map((d) => (
                              <th key={d} scope="col" className={TH}>
                                {humanize(d)}
                              </th>
                            ))}
                            <th scope="col" className={TH}>Hallucination</th>
                          </tr>
                        </thead>
                        <tbody className="tabular">
                          {Object.entries(rq.systems)
                            .filter(([k]) => MAIN.includes(k))
                            .map(([k, s]) => (
                              <tr key={k} className={k === "resolveai_full" ? "bg-brand-50/50" : ""}>
                                <th scope="row" className={`${TD} text-left font-normal`}>
                                  {label(k)}
                                  <div className="text-[11px] text-ink-3">
                                    {s.n_parsed} scored · {s.judge_failures} judge failures
                                  </div>
                                </th>
                                {JUDGE_DIMENSIONS.map((d) => (
                                  <td key={d} className={TD}>
                                    {fixed(s.means[d], 2)}
                                    {d === "groundedness" && s.bootstrap.groundedness ? (
                                      <div className="text-[11px] text-ink-3">
                                        [{fixed(s.bootstrap.groundedness.ci_low, 2)}, {fixed(s.bootstrap.groundedness.ci_high, 2)}]
                                      </div>
                                    ) : null}
                                  </td>
                                ))}
                                <td className={TD}>{pct(s.rates.hallucination)}</td>
                              </tr>
                            ))}
                        </tbody>
                      </DataTable>
                    </Card>
                  ) : null}
                  <div className="space-y-4">
                    <Card title="Judge validation" headingLevel={3}>
                      <KeyValues
                        items={[
                          {
                            label: "Human agreement",
                            value: <Badge tone="warning">{humanize((human?.status ?? e.human_study ?? "Pending human ratings").toLowerCase())}</Badge>,
                            hint: human ? `${human.n_fully_rated ?? 0} of ${human.n_examples ?? 0} packet examples rated by humans` : undefined,
                          },
                          {
                            label: "Second model family",
                            value: groundKappa?.weighted_kappa !== undefined ? `Groundedness weighted kappa ${fixed(groundKappa.weighted_kappa, 3)}` : "n/a",
                            hint: `${crossFamily?.n ?? 0} responses; judge versus judge, not human agreement.`,
                          },
                        ]}
                      />
                    </Card>
                    <Card title="Pairwise judge" headingLevel={3}>
                      <ul className="space-y-3">
                        {Object.entries(e.pairwise_judge).map(([k, p]) => {
                          const other = k.replace("resolveai_full_vs_", "");
                          const total = p.win + p.tie + p.loss || 1;
                          return (
                            <li key={k}>
                              <div className="flex flex-wrap justify-between gap-2 text-[13px]">
                                <span className="text-ink">ResolveAI vs {label(other)}</span>
                                <span className="tabular text-xs text-ink-3">
                                  {p.win} wins · {p.tie} ties · {p.loss} losses
                                </span>
                              </div>
                              <div className="mt-1 flex h-2 overflow-hidden rounded-full bg-subtle" role="img" aria-label={`ResolveAI versus ${label(other)}: win rate ${pct(p.win_rate)}, loss rate ${pct(p.loss_rate)}`}>
                                <span className="bg-success" style={{ width: `${(p.win / total) * 100}%` }} />
                                <span className="bg-line-strong" style={{ width: `${(p.tie / total) * 100}%` }} />
                                <span className="bg-danger/70" style={{ width: `${(p.loss / total) * 100}%` }} />
                              </div>
                            </li>
                          );
                        })}
                      </ul>
                      <p className="mt-3 text-xs text-ink-3">Question asked: {Object.values(e.pairwise_judge)[0]?.question}</p>
                    </Card>
                  </div>
                </div>
              </Section>

              <Section
                id="latency-cost"
                title="Latency and cost"
                description="Cost uses list prices and the tokens each call consumed when it ran live. ResolveAI's row comes from a cache-served run, so its latency understates live latency. The misleading headline analysis reports the live p50."
              >
                <Card bodyClassName="p-0">
                  <DataTable label="Latency and cost by system" minWidth={860}>
                    <thead>
                      <tr>
                        <th scope="col" className={TH}>System</th>
                        <th scope="col" className={TH}>p50 latency</th>
                        <th scope="col" className={TH}>p95 latency</th>
                        <th scope="col" className={TH}>Model calls / message</th>
                        <th scope="col" className={TH}>Live calls / message</th>
                        <th scope="col" className={TH}>Tokens in / out</th>
                        <th scope="col" className={TH}>Est. cost / message</th>
                        <th scope="col" className={TH}>Failed calls</th>
                      </tr>
                    </thead>
                    <tbody className="tabular">
                      {[...present(MAIN), ...present(ABLATIONS)].map((k) => {
                        const c = systems[k].cost_latency;
                        return (
                          <tr key={k} className={k === "resolveai_full" ? "bg-brand-50/50" : ""}>
                            <th scope="row" className={`${TD} text-left font-normal`}>{label(k)}</th>
                            <td className={TD}>{duration(c.p50_latency_ms)}</td>
                            <td className={TD}>{duration(c.p95_latency_ms)}</td>
                            <td className={TD}>{fixed(c.llm_calls_per_message, 2)}</td>
                            <td className={TD}>{fixed(c.live_calls_per_message, 2)}</td>
                            <td className={TD}>
                              {Math.round(c.tokens_in_per_message)} / {Math.round(c.tokens_out_per_message)}
                            </td>
                            <td className={TD}>{usd(c.estimated_cost_usd_per_message)}</td>
                            <td className={TD}>{c.failed_calls}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </DataTable>
                </Card>
              </Section>

              <Section id="baselines" title="Baselines and ablations" description="Baselines are deliberately simple; ablations remove one ResolveAI component at a time on the same golden rows.">
                <Card bodyClassName="p-0">
                  <DataTable label="Baselines and ablations" minWidth={960}>
                    <thead>
                      <tr>
                        <th scope="col" className={TH}>System</th>
                        <th scope="col" className={TH}>Kind</th>
                        <th scope="col" className={TH}>Intent macro-F1</th>
                        <th scope="col" className={TH}>Escalation recall</th>
                        <th scope="col" className={TH}>Escalation precision</th>
                        <th scope="col" className={TH}>Escalation F1</th>
                        <th scope="col" className={TH}>Auto-handle</th>
                        <th scope="col" className={TH}>Unsafe auto</th>
                        <th scope="col" className={TH}>Judge groundedness</th>
                      </tr>
                    </thead>
                    <tbody className="tabular">
                      {Object.entries(systems).map(([k, s]) => (
                        <tr key={k} className={k === "resolveai_full" ? "bg-brand-50/50" : ""}>
                          <th scope="row" className={`${TD} text-left font-normal`}>
                            {label(k)}
                            {s.description && s.description !== k ? <div className="max-w-64 text-[11px] text-ink-3">{s.description}</div> : null}
                          </th>
                          <td className={TD}>{k === "resolveai_full" ? "Full system" : ABLATIONS.includes(k) ? "Ablation" : "Baseline"}</td>
                          <td className={TD}>{fixed(s.intent.macro_f1, 3)}</td>
                          <td className={TD}>{pct(s.escalation.recall)}</td>
                          <td className={TD}>{pct(s.escalation.precision)}</td>
                          <td className={TD}>{fixed(s.escalation.f1, 3)}</td>
                          <td className={TD}>{pct(s.autonomy.auto_handle_rate)}</td>
                          <td className={TD}>{s.autonomy.unsafe_auto_handle_count}</td>
                          <td className={TD}>{s.judge ? fixed(s.judge.groundedness, 2) : "n/a"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </DataTable>
                </Card>
              </Section>

              {e.statistical_uncertainty_md ? (
                <Section id="uncertainty" title="Statistical uncertainty">
                  <Card>
                    <Markdown source={e.statistical_uncertainty_md} skipFirstHeading />
                  </Card>
                </Section>
              ) : null}
            </div>
          </div>
        </details>
      </section>
    </>
  );
}
