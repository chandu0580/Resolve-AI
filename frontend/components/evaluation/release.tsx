import type { ReactNode } from "react";
import { Badge } from "@/components/ui/badge";
import { Card, KeyValues, Mono, Notice } from "@/components/ui/card";
import { Kpi, KpiGrid } from "@/components/ui/kpi";
import { DataTable, TD, TH } from "@/components/ui/table";
import type { MetricCell, ReleaseEvaluation } from "@/lib/api/types";
import { duration, fixed, humanize, pct, usd } from "@/lib/format";
import { intentLabel, reasonMeta } from "@/lib/labels";

type Kind = "rate" | "f1" | "count" | "usd" | "ms" | "score" | "calls";

export const RELEASE_METRICS: { key: string; label: string; kind: Kind; note?: string }[] = [
  { key: "escalation_precision", label: "Escalation precision", kind: "rate", note: "Share of handoffs that were necessary. Low because the policy is conservative." },
  { key: "escalation_recall", label: "Escalation recall", kind: "rate", note: "Share of cases that needed a human and got one." },
  { key: "escalation_f1", label: "Escalation F1", kind: "f1" },
  { key: "intent_macro_f1", label: "Intent macro-F1", kind: "f1", note: "11 classes weighted equally; small classes move it." },
  { key: "intent_accuracy", label: "Intent accuracy", kind: "rate" },
  { key: "autonomous_rate", label: "Automatic reply rate", kind: "rate" },
  { key: "safe_autonomous_rate", label: "Safe automatic reply rate", kind: "rate" },
  { key: "unsafe_autonomous_count", label: "Unsafe automatic replies", kind: "count", note: "Automatic replies on rows annotated for escalation." },
  { key: "unnecessary_handoffs", label: "Unnecessary handoffs", kind: "count", note: "Handoffs on rows not annotated for escalation." },
  { key: "judge_groundedness", label: "Judge groundedness (1 to 5)", kind: "score", note: "LLM judge; not validated against human ratings." },
  { key: "judge_hallucination", label: "Judge hallucination rate", kind: "rate", note: "LLM judge; see judge attribution." },
  { key: "judge_policy_violation", label: "Judge policy-violation rate", kind: "rate" },
  { key: "llm_calls_per_message", label: "Model calls per message", kind: "calls" },
  { key: "cost_usd_per_message", label: "Estimated cost per message", kind: "usd", note: "List price." },
  { key: "latency_p50_ms_as_run", label: "p50 latency as run", kind: "ms", note: "Cache-served evaluation run; see the performance profile for live latency." },
];

const COMPARISON_LABELS: Record<string, string> = { B2_direct_llm: "B2 direct LLM", B1_simple_ml: "B1 simple ML", phase9_final: "Pre-release run" };
const PROFILE_LABELS: Record<string, string> = {
  no_model: "No model (deterministic path only)",
  cached_model: "Model responses served from cache",
  live_random: "Live model, random dev requests",
  live_draft: "Live model, requests with sufficient evidence",
};

function fmt(kind: Kind, v: number | null | undefined): string {
  if (v === null || v === undefined) return "n/a";
  switch (kind) {
    case "rate":
      return pct(v);
    case "f1":
      return fixed(v, 3);
    case "score":
    case "calls":
      return fixed(v, 2);
    case "count":
      return String(Math.round(v));
    case "usd":
      return usd(v);
    case "ms":
      return duration(v);
  }
}

function diffFmt(kind: Kind, v: number): string {
  const sign = v > 0 ? "+" : v < 0 ? "−" : "";
  const a = Math.abs(v);
  if (kind === "rate") return `${sign}${(a * 100).toFixed(1)} pp`;
  return `${sign}${fmt(kind, a)}`;
}

function ciText(kind: Kind, cell: MetricCell | undefined): string | null {
  const c = cell?.resolveai_ci;
  return c ? `${fmt(kind, c.ci_low)} to ${fmt(kind, c.ci_high)}` : null;
}

export function DatasetBadge({ children, tone = "info" }: { children: ReactNode; tone?: "info" | "warning" | "brand" | "neutral" }) {
  return <Badge tone={tone}>{children}</Badge>;
}

function Section({ id, title, badge, description, children }: { id: string; title: string; badge: ReactNode; description?: ReactNode; children: ReactNode }) {
  return (
    <section id={id} aria-labelledby={`${id}-heading`} className="scroll-mt-20">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <h2 id={`${id}-heading`} className="text-base font-semibold text-ink">
          {title}
        </h2>
        {badge}
      </div>
      {description ? <p className="mt-0.5 mb-3 max-w-4xl text-[13px] text-ink-3">{description}</p> : <div className="mb-3" />}
      {children}
    </section>
  );
}

export const RELEASE_NAV: [string, string][] = [
  ["release-scorecard", "Release scorecard"],
  ["release-failure-modes", "Failure modes"],
  ["release-by-intent", "By intent"],
  ["release-judge", "Judge attribution"],
  ["release-human", "Human validation"],
  ["dev-experiments", "Dev experiments"],
  ["release-performance", "Latency & cost profile"],
];

export function ReleaseSections({ release }: { release: ReleaseEvaluation }) {
  const g = release.golden;
  const table = g.table ?? {};
  const comparisons = Object.keys(table);
  const firstTable = table[comparisons[0]] ?? {};
  const cell = (key: string) => firstTable[key];
  const fm = g.failure_modes;
  const missed = fm?.missed_escalations ?? [];
  const human = g.human_evaluation;
  const ja = g.judge_attribution;
  const risk = release.dev_experiments.risk_corroboration;
  const perf = release.performance;
  const n = g.release.n;

  return (
    <div className="space-y-9">
      <Section
        id="release-scorecard"
        title="Release scorecard"
        badge={<DatasetBadge>FROZEN GOLDEN SET · release {g.release.version}</DatasetBadge>}
        description={
          <>
            One run of release {g.release.version} ({g.release.pipeline_version ?? "pipeline n/a"}) on {n} annotated golden conversations. 95% bootstrap intervals ({g.release.n_boot} resamples, seed {g.release.seed}). The golden set
            was never used for tuning. Golden sha256 <Mono>{g.release.golden_sha256.slice(0, 16)}…</Mono>
          </>
        }
      >
        <KpiGrid label="Release scorecard">
          {["escalation_precision", "escalation_recall", "escalation_f1", "intent_macro_f1", "unnecessary_handoffs", "unsafe_autonomous_count"].map((key) => {
            const m = RELEASE_METRICS.find((x) => x.key === key)!;
            const c = cell(key);
            return (
              <Kpi
                key={key}
                label={m.label}
                value={fmt(m.kind, c?.resolveai)}
                ci={m.kind === "count" ? null : ciText(m.kind, c)}
                sub={`${c?.resolveai_ci?.n ?? n} golden conversations${key === "escalation_recall" ? ` · ${missed.length} missed` : ""}. ${m.note ?? ""}`}
              />
            );
          })}
        </KpiGrid>
        <Card className="mt-4" bodyClassName="p-0">
          <DataTable label="Release metrics with baselines" minWidth={980}>
            <thead>
              <tr>
                <th scope="col" className={TH}>Metric</th>
                <th scope="col" className={TH}>ResolveAI {g.release.version} (95% CI)</th>
                {comparisons.map((k) => (
                  <th key={k} scope="col" className={TH}>
                    {COMPARISON_LABELS[k] ?? humanize(k)} · difference (95% CI)
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="tabular">
              {RELEASE_METRICS.filter((m) => cell(m.key)).map((m) => (
                <tr key={m.key}>
                  <th scope="row" className={`${TD} text-left font-normal`}>
                    {m.label}
                    {m.note ? <div className="max-w-64 text-[11px] text-ink-3">{m.note}</div> : null}
                  </th>
                  <td className={TD}>
                    {fmt(m.kind, cell(m.key)?.resolveai)}
                    {ciText(m.kind, cell(m.key)) ? <div className="text-[11px] text-ink-3">[{ciText(m.kind, cell(m.key))}]</div> : null}
                  </td>
                  {comparisons.map((k) => {
                    const c = table[k]?.[m.key];
                    const d = c?.difference;
                    return (
                      <td key={k} className={TD}>
                        {fmt(m.kind, c?.baseline)}
                        {d ? (
                          <div className="text-[11px] text-ink-3">
                            {diffFmt(m.kind, d.difference)} [{diffFmt(m.kind, d.ci_low)}, {diffFmt(m.kind, d.ci_high)}] · {d.interval_excludes_zero ? "excludes 0" : "includes 0"}
                          </div>
                        ) : null}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </DataTable>
          <p className="px-4 py-2.5 text-xs text-ink-3">
            Difference is ResolveAI minus the comparison system on the same rows. B2 sends the message straight to the model; it is more precise but produced unsafe automatic replies. B1 is a simple
            classifier with nearest-neighbour replies. The pre-release run is the same pipeline before the release&apos;s one pre-registered change. Served as stored from {release.provenance.source}.
          </p>
        </Card>
      </Section>

      {fm ? (
        <Section id="release-failure-modes" title="Failure modes" badge={<DatasetBadge>FROZEN GOLDEN SET</DatasetBadge>} description="Where the release is wrong, counted on the golden rows. Example messages are PII-redacted.">
          <div className="grid gap-4 lg:grid-cols-2">
            <Card title={`${fm.unnecessary_handoffs.total} unnecessary handoffs`} headingLevel={3} description="By the policy reason that sent them to a human." bodyClassName="p-0">
              <DataTable label="Unnecessary handoffs by reason" minWidth={360}>
                <thead>
                  <tr>
                    <th scope="col" className={TH}>Reason</th>
                    <th scope="col" className={TH}>Handoffs</th>
                  </tr>
                </thead>
                <tbody className="tabular">
                  {Object.entries(fm.unnecessary_handoffs.by_reason_code).map(([code, count]) => (
                    <tr key={code}>
                      <th scope="row" className={`${TD} text-left font-normal`}>
                        {reasonMeta(code).label} <span className="font-mono text-[11px] text-ink-3">{code}</span>
                      </th>
                      <td className={TD}>{count}</td>
                    </tr>
                  ))}
                </tbody>
              </DataTable>
            </Card>
            <div className="space-y-4">
              <Card title={`${missed.length} missed escalation${missed.length === 1 ? "" : "s"}`} headingLevel={3}>
                {missed.length ? (
                  <ul className="space-y-2">
                    {missed.map((m) => (
                      <li key={m.gid} className="rounded-md border border-line px-3 py-2 text-xs">
                        <div className="flex flex-wrap justify-between gap-2 text-ink-3">
                          <span className="font-mono">{m.gid}</span>
                          <span>
                            annotated {humanize(m.gold_reason).toLowerCase()} · agent chose {humanize(m.action).toLowerCase()} ({m.reason_code})
                          </span>
                        </div>
                        <p className="mt-1 text-ink-2">{m.message}</p>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-[13px] text-ink-2">None on the golden set.</p>
                )}
              </Card>
              <Card title="Other failure signals" headingLevel={3}>
                <KeyValues
                  items={[
                    { label: "Intent errors", value: `${fm.intent_errors} of ${fm.n}`, hint: fm.top_intent_confusions.slice(0, 3).map((c) => `${intentLabel(c.gold)} → ${intentLabel(c.predicted)} (${c.count})`).join("; ") },
                    { label: "Non-English rows handed off", value: fm.non_english_rows_handed_off.length },
                    { label: "Rows with STRONG evidence", value: fm.strong_evidence_rows.length },
                    { label: "Templates the judge flagged", value: fm.judge_flagged_templates.length, hint: "Fixed holding and clarification texts flagged as hallucinations by the LLM judge." },
                  ]}
                />
              </Card>
            </div>
          </div>
        </Section>
      ) : null}

      {g.by_intent ? (
        <Section
          id="release-by-intent"
          title="Outcomes by intent"
          badge={<DatasetBadge>FROZEN GOLDEN SET</DatasetBadge>}
          description={`Per annotated intent. Knowledge-gap candidate rule: at least ${g.by_intent.gap_rule.min_rows} rows, SUFFICIENT or STRONG evidence on at most ${pct(g.by_intent.gap_rule.max_sufficient_share, 0)}, and a handoff share of at least ${pct(g.by_intent.gap_rule.min_handoff_share, 0)}. ${g.by_intent.note}`}
        >
          <Card bodyClassName="p-0">
            <DataTable label="Release outcomes by intent" minWidth={900}>
              <thead>
                <tr>
                  <th scope="col" className={TH}>Intent</th>
                  <th scope="col" className={TH}>Rows</th>
                  <th scope="col" className={TH}>Sufficient evidence</th>
                  <th scope="col" className={TH}>Auto / clarify / handoff</th>
                  <th scope="col" className={TH}>Unnecessary handoffs</th>
                  <th scope="col" className={TH}>Missed escalations</th>
                  <th scope="col" className={TH}>Gap candidate</th>
                </tr>
              </thead>
              <tbody className="tabular">
                {g.by_intent.by_intent.map((r) => (
                  <tr key={r.intent}>
                    <th scope="row" className={`${TD} text-left font-normal`}>{intentLabel(r.intent)}</th>
                    <td className={TD}>{r.rows}</td>
                    <td className={TD}>{pct(r.sufficient_share, 0)}</td>
                    <td className={TD}>
                      {r.auto_handled} / {r.clarifications} / {r.handoffs}
                    </td>
                    <td className={TD}>{r.unnecessary_handoffs}</td>
                    <td className={TD}>{r.missed_escalations}</td>
                    <td className={TD}>{r.knowledge_gap_candidate ? <Badge tone="warning">Yes</Badge> : "No"}</td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
          </Card>
        </Section>
      ) : null}

      {ja ? (
        <Section
          id="release-judge"
          title="Judge attribution"
          badge={<DatasetBadge>FROZEN GOLDEN SET</DatasetBadge>}
          description="Where the judge's hallucination flags come from. Responses identical to the previous run received identical scores, so score changes come from changed responses."
        >
          <div className="grid gap-4 lg:grid-cols-2">
            <Card title="Identical versus changed responses" headingLevel={3} bodyClassName="p-0">
              <DataTable label="Judge scores for identical and changed responses" minWidth={460}>
                <thead>
                  <tr>
                    <th scope="col" className={TH}>Responses</th>
                    <th scope="col" className={TH}>n</th>
                    <th scope="col" className={TH}>Hallucination flags (before → release)</th>
                    <th scope="col" className={TH}>Groundedness mean</th>
                  </tr>
                </thead>
                <tbody className="tabular">
                  {(
                    [
                      ["Identical", ja.identical_responses],
                      ["Changed", ja.changed_responses],
                      ...Object.entries(ja.changed_by_kind_transition).map(([k, b]) => [`Changed: ${k}`, b] as const),
                    ] as const
                  ).map(([label, b]) => (
                    <tr key={label}>
                      <th scope="row" className={`${TD} text-left font-normal`}>{label}</th>
                      <td className={TD}>{b.n}</td>
                      <td className={TD}>
                        {b.hallucination_flags_phase9} → {b.hallucination_flags_release}
                      </td>
                      <td className={TD}>
                        {fixed(b.groundedness_mean_phase9)} → {fixed(b.groundedness_mean_release)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </DataTable>
            </Card>
            <Card title="Release flags by response kind" headingLevel={3}>
              <KeyValues
                items={Object.entries(ja.release_hallucination_flags_by_response_kind).map(([kind, v]) => ({
                  label: humanize(kind),
                  value: `${v.flags} of ${v.parsed} judged responses flagged`,
                }))}
              />
              <p className="mt-3 text-xs text-ink-3">
                Most flags fall on handoff notices and clarifying questions, which make no troubleshooting claim. Treat the judge hallucination rate as a judge limitation to investigate, not as a count of false instructions.
              </p>
            </Card>
          </div>
        </Section>
      ) : null}

      <Section id="release-human" title="Human validation" badge={<DatasetBadge tone="warning">PENDING</DatasetBadge>}>
        <Notice tone="warning" title={human && human.fully_rated_rows === 0 ? "Human judge validation pending" : "Human judge validation"}>
          {human ? `${human.fully_rated_rows} of ${human.packet_rows} packet rows have been rated by people (status: ${humanize(human.status.toLowerCase())}).` : "No human evaluation record."} The second annotator for the
          risk labels was an AI annotator, not a person. Until people rate the packet, every judge score on this page is unvalidated.
        </Notice>
      </Section>

      <Section
        id="dev-experiments"
        title="Dev experiments"
        badge={<DatasetBadge tone="neutral">DEV EXPERIMENTS · never combined with golden results</DatasetBadge>}
        description="Pre-registered experiments run on the development split to choose release settings. The golden set was not touched."
      >
        {risk ? (
          <Card title={risk.decision.candidate} headingLevel={3} actions={<Badge tone={risk.decision.accepted ? "success" : "neutral"}>{risk.decision.accepted ? "Accepted" : "Rejected"}</Badge>}>
            <KeyValues
              items={[
                { label: "Decision", value: risk.decision.decision },
                { label: "Labels", value: risk.decision.labels, hint: risk.report ? `${risk.report.n_labelled_rows} labelled of ${risk.report.n_dev_rows} dev rows` : undefined },
                { label: "Golden set touched", value: risk.decision.golden_touched ? "Yes" : "No" },
                ...(risk.report
                  ? Object.entries(risk.report.scores_on_labelled_rows).map(([variant, sc]) => ({
                      label: `${variant} on labelled dev rows`,
                      value: `precision ${pct(sc.precision)} · recall ${pct(sc.recall)} · F1 ${fixed(sc.f1, 3)}`,
                      hint: `${sc.fp} unnecessary handoffs, ${sc.fn} missed; ${sc.auto_candidates_on_should_escalate_rows} automatic candidates on rows that needed a human`,
                    }))
                  : []),
              ]}
            />
          </Card>
        ) : (
          <p className="text-[13px] text-ink-3">No dev experiment record in this checkout.</p>
        )}
      </Section>

      {perf ? (
        <Section id="release-performance" title="Latency and cost profile" badge={<DatasetBadge tone="neutral">PERFORMANCE PROFILE · dev requests, not golden</DatasetBadge>} description={perf.machine_note}>
          <Card bodyClassName="p-0">
            <DataTable label="Latency and cost by profile" minWidth={900}>
              <thead>
                <tr>
                  <th scope="col" className={TH}>Profile</th>
                  <th scope="col" className={TH}>n</th>
                  <th scope="col" className={TH}>p50 latency</th>
                  <th scope="col" className={TH}>p95 latency</th>
                  <th scope="col" className={TH}>Model calls / request</th>
                  <th scope="col" className={TH}>Cost p50 / p95</th>
                  <th scope="col" className={TH}>Timeouts</th>
                  <th scope="col" className={TH}>Drafted and verified</th>
                </tr>
              </thead>
              <tbody className="tabular">
                {Object.entries(perf.profiles).map(([k, p]) => (
                  <tr key={k}>
                    <th scope="row" className={`${TD} text-left font-normal`}>{PROFILE_LABELS[k] ?? humanize(k)}</th>
                    <td className={TD}>{p.n}</td>
                    <td className={TD}>{duration(p.total_ms.p50)}</td>
                    <td className={TD}>{duration(p.total_ms.p95)}</td>
                    <td className={TD}>{fixed(p.mean_llm_calls, 2)}</td>
                    <td className={TD}>
                      {usd(p.cost_usd_per_request.p50)} / {usd(p.cost_usd_per_request.p95)}
                    </td>
                    <td className={TD}>{p.timeouts}</td>
                    <td className={TD}>{p.model_drafted_and_verified}</td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
            <p className="px-4 py-2.5 text-xs text-ink-3">
              {perf.price_per_million_tokens_usd.note} (input ${perf.price_per_million_tokens_usd.input}, output ${perf.price_per_million_tokens_usd.output} per million tokens). Small samples: p95 values rest on a handful of requests.
            </p>
          </Card>
        </Section>
      ) : null}

      <Card title="Release limitations">
        <ul className="list-disc space-y-1 pl-5 text-[13px] text-ink-2">
          {release.limitations.map((l) => (
            <li key={l}>{l}</li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
