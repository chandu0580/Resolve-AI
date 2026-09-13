import type { Metadata } from "next";
import { Activity, BookOpen, FlaskConical } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Advanced, Card, KeyValues, Mono, Notice, PageHeader } from "@/components/ui/card";
import { Kpi, KpiGrid } from "@/components/ui/kpi";
import { ErrorState } from "@/components/ui/states";
import { DataTable, TD, TH } from "@/components/ui/table";
import { KnowledgeExplorer } from "@/components/knowledge/knowledge-explorer";
import { api, load } from "@/lib/api/client";
import type { TraceSummary } from "@/lib/api/types";
import { toErrorInfo } from "@/lib/errors";
import { dateOnly, humanize, pct } from "@/lib/format";
import { intentLabel, reasonMeta } from "@/lib/labels";

export const metadata: Metadata = { title: "Knowledge Center · ResolveAI" };

/** Live evidence coverage by the intent the agent recorded. Uses the same measurable rule as the frozen by-intent table. */
function liveByIntent(items: TraceSummary[]) {
  const groups = new Map<string, TraceSummary[]>();
  for (const t of items) {
    if (!t.intent) continue;
    groups.set(t.intent, [...(groups.get(t.intent) ?? []), t]);
  }
  return [...groups.entries()]
    .map(([intent, ts]) => ({
      intent,
      n: ts.length,
      sufficient: ts.filter((t) => t.evidence_sufficient === true).length,
      handoffs: ts.filter((t) => t.final_decision === "HUMAN_HANDOFF").length,
    }))
    .sort((a, b) => b.n - a.n);
}

function SectionTitle({ id, title, badge }: { id: string; title: string; badge: React.ReactNode }) {
  return (
    <div className="mb-3 flex flex-wrap items-center gap-x-3 gap-y-1">
      <h2 id={id} className="text-base font-semibold text-ink">
        {title}
      </h2>
      {badge}
    </div>
  );
}

export default async function KnowledgePage() {
  const [kb, release, traces] = await Promise.all([load(api.knowledgeSummary()), load(api.evaluationRelease()), load(api.traces({ limit: 200 }))]);
  const k = kb.data;
  const golden = release.data?.golden.by_intent ?? null;
  const rule = golden?.gap_rule;
  const live = traces.data ? liveByIntent(traces.data.items) : [];
  const liveCandidate = (r: { n: number; sufficient: number; handoffs: number }) =>
    Boolean(rule && r.n >= rule.min_rows && r.sufficient / r.n <= rule.max_sufficient_share && r.handoffs / r.n >= rule.min_handoff_share);

  return (
    <>
      <PageHeader
        eyebrow="AI"
        title="Knowledge Center"
        description="Historical Apple Support knowledge used by ResolveAI to ground responses and identify where evidence is insufficient."
      />

      <section aria-labelledby="kb-heading" className="mb-8">
        <SectionTitle
          id="kb-heading"
          title="Corpus"
          badge={<Badge tone="brand" icon={BookOpen}>HISTORICAL SUPPORT KNOWLEDGE</Badge>}
        />
        {kb.error ? (
          <ErrorState error={toErrorInfo(kb.error)} compact />
        ) : k ? (
          <>
            <KpiGrid label="Historical support knowledge statistics">
              <Kpi label="Indexed support cases" value={k.rows.toLocaleString("en-US")} sub={`${dateOnly(k.date_range.min)} to ${dateOnly(k.date_range.max)}`} />
              <Kpi label="Resolution-bearing replies" value={pct(k.resolution_bearing / k.rows)} sub={`${k.resolution_bearing.toLocaleString("en-US")} replies state an instruction or a released fix`} />
              <Kpi label="Substantive replies" value={k.substantive !== null ? pct(k.substantive / k.rows) : "n/a"} sub="Not a move-to-DM reply and long enough to ground on" />
              <Kpi label="Move-to-DM replies" value={k.dm_handoff !== null ? pct(k.dm_handoff / k.rows) : "n/a"} sub="The historical reply only moved the case to private messages" />
              <Kpi label="Usable for grounding" value={k.resolution_bearing_substantive !== null ? k.resolution_bearing_substantive.toLocaleString("en-US") : "n/a"} sub="Resolution-bearing and substantive" />
              <Kpi label="Dense indexes" value={k.indexes.dense.length} sub={`Search path: ${k.indexes.search_path.join(", ")}`} />
            </KpiGrid>

            {/* Evidence quality by issue category */}
            <div className="mt-4">
              <Card
                title="Evidence quality by issue category"
                headingLevel={3}
                description="Breakdown of historical support cases by customer issue area, showing how often proven resolutions were provided versus routing to private messages."
                bodyClassName="p-0"
              >
                <DataTable label="Historical support knowledge evidence quality by issue category" minWidth={520}>
                  <thead>
                    <tr>
                      <th scope="col" className={TH}>Issue category</th>
                      <th scope="col" className={TH}>Cases</th>
                      <th scope="col" className={TH}>Resolution-bearing</th>
                      <th scope="col" className={TH}>Move-to-DM</th>
                    </tr>
                  </thead>
                  <tbody className="tabular">
                    {k.by_weak_intent.map((r) => (
                      <tr key={r.intent}>
                        <th scope="row" className={`${TD} text-left font-normal`}>{intentLabel(r.intent)}</th>
                        <td className={TD}>{r.rows.toLocaleString("en-US")}</td>
                        <td className={TD}>{pct(r.resolution_bearing_share)}</td>
                        <td className={TD}>{pct(r.dm_handoff_share)}</td>
                      </tr>
                    ))}
                  </tbody>
                </DataTable>
              </Card>
            </div>

            {/* Advanced knowledge details (Collapsed by default) */}
            <div className="mt-4">
              <Card title="Advanced knowledge details" headingLevel={3}>
                <p className="text-[13px] text-ink-3">
                  Corpus hash, embedding model, leakage boundary, and definitions for audit and engineering review.
                </p>
                <Advanced label="Show engineering specifications, provenance, and definitions">
                  <div className="pt-2">
                    <KeyValues
                      columns={2}
                      items={[
                        { label: "Source", value: "Kaggle “Customer Support on Twitter” (AppleSupport), redacted in preprocessing" },
                        { label: "Embedding model", value: <Mono>{k.indexes.embedding_model}</Mono> },
                        { label: "Corpus hash", value: <Mono>{String(k.manifest.corpus_hash ?? "n/a")}</Mono> },
                        { label: "Preprocessing", value: <Mono>{String(k.manifest.preprocessing_version ?? "n/a")}</Mono> },
                        { label: "Leakage boundary", value: `Every case predates ${dateOnly(String(k.manifest.holdout_min_created_at ?? ""))}, the start of the evaluation holdout.` },
                        { label: "Dense indexes", value: <Mono>{k.indexes.dense.join(", ")}</Mono> },
                        { label: "Search path", value: <Mono>{k.indexes.search_path.join(", ")}</Mono> },
                        ...Object.entries(k.definitions).map(([key, d]) => ({ label: humanize(key), value: d })),
                      ]}
                    />
                  </div>
                </Advanced>
              </Card>
            </div>
          </>
        ) : null}
      </section>

      <section aria-labelledby="gaps-heading" className="mb-8">
        <SectionTitle id="gaps-heading" title="Coverage and knowledge gaps" badge={<Badge tone="info" icon={FlaskConical}>FROZEN GOLDEN SET</Badge>} />
        <Notice tone="info" title="Intent areas where reliable historical evidence is limited and human handling is common">
          {rule
            ? `Identifies intents in the benchmark with at least ${rule.min_rows} conversations where verified historical evidence was found for at most ${pct(rule.max_sufficient_share, 0)} of cases and at least ${pct(rule.min_handoff_share, 0)} escalated to a human operator. `
            : "Benchmark artifacts are unavailable. "}
          This measurable signal highlights high-priority opportunities to expand verified knowledge documentation. Inspect the counts and example conversations before acting.
        </Notice>
        {release.error ? (
          <div className="mt-3">
            <ErrorState error={toErrorInfo(release.error)} compact />
          </div>
        ) : golden ? (
          <Card className="mt-3" bodyClassName="p-0">
            <DataTable label="Evidence coverage by intent on the golden set" minWidth={940}>
              <thead>
                <tr>
                  <th scope="col" className={TH}>Intent</th>
                  <th scope="col" className={TH}>Conversations</th>
                  <th scope="col" className={TH}>Sufficient evidence</th>
                  <th scope="col" className={TH}>Handed off</th>
                  <th scope="col" className={TH}>Unnecessary handoffs</th>
                  <th scope="col" className={TH}>Gap candidate</th>
                  <th scope="col" className={TH}>Underlying examples</th>
                </tr>
              </thead>
              <tbody>
                {golden.by_intent.map((r) => (
                  <tr key={r.intent} className={r.knowledge_gap_candidate ? "bg-warning-bg/40" : ""}>
                    <th scope="row" className={`${TD} text-left font-normal`}>{intentLabel(r.intent)}</th>
                    <td className={`${TD} tabular`}>{r.rows}</td>
                    <td className={`${TD} tabular`}>{pct(r.sufficient_share, 0)}</td>
                    <td className={`${TD} tabular`}>{pct(r.handoff_share, 0)}</td>
                    <td className={`${TD} tabular`}>{r.unnecessary_handoffs}</td>
                    <td className={TD}>{r.knowledge_gap_candidate ? <Badge tone="warning">Candidate</Badge> : <span className="text-ink-3">No</span>}</td>
                    <td className={`${TD} max-w-96`}>
                      {r.examples.length ? (
                        <details>
                          <summary className="cursor-pointer text-xs font-medium text-brand-700">{r.examples.length} example{r.examples.length === 1 ? "" : "s"}</summary>
                          <ul className="mt-1.5 space-y-1.5">
                            {r.examples.map((e) => (
                              <li key={e.gid} className="text-xs text-ink-2">
                                <span className="font-mono text-ink-3">{e.gid}</span> · {reasonMeta(e.reason_code).label} · {humanize(e.evidence_level.toLowerCase())}
                                <div className="text-ink">{e.message}</div>
                              </li>
                            ))}
                          </ul>
                        </details>
                      ) : (
                        <span className="text-xs text-ink-3">none</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
            <p className="px-4 py-2.5 text-xs text-ink-3">{golden.note} Examples are PII-redacted.</p>
          </Card>
        ) : null}
      </section>

      <section aria-labelledby="live-coverage-heading" className="mb-8">
        <SectionTitle id="live-coverage-heading" title="Live evidence coverage" badge={<Badge tone="success" icon={Activity}>LIVE OPERATIONAL DATA · this environment</Badge>} />
        <p className="mb-3 text-[13px] text-ink-3">
          What the running agent can currently retrieve from the historical support corpus.
        </p>
        {traces.error ? (
          <ErrorState error={toErrorInfo(traces.error)} compact />
        ) : !live.length ? (
          <Card>
            <p className="text-[13px] text-ink-3">No conversations with a recorded intent in this environment yet. Nothing is shown until the API records traces.</p>
          </Card>
        ) : (
          <Card bodyClassName="p-0">
            <DataTable label="Live evidence coverage by intent" minWidth={640}>
              <thead>
                <tr>
                  <th scope="col" className={TH}>Intent</th>
                  <th scope="col" className={TH}>Conversations</th>
                  <th scope="col" className={TH}>Sufficient evidence</th>
                  <th scope="col" className={TH}>Handed off</th>
                  <th scope="col" className={TH}>Gap signal</th>
                </tr>
              </thead>
              <tbody className="tabular">
                {live.map((r) => (
                  <tr key={r.intent}>
                    <th scope="row" className={`${TD} text-left font-normal`}>{intentLabel(r.intent)}</th>
                    <td className={TD}>{r.n}</td>
                    <td className={TD}>
                      {r.sufficient} ({pct(r.sufficient / r.n, 0)})
                    </td>
                    <td className={TD}>
                      {r.handoffs} ({pct(r.handoffs / r.n, 0)})
                    </td>
                    <td className={TD}>{liveCandidate(r) ? <Badge tone="warning">Candidate</Badge> : rule && r.n < rule.min_rows ? <span className="text-ink-3">Too few ({r.n})</span> : <span className="text-ink-3">No</span>}</td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
            <p className="px-4 py-2.5 text-xs text-ink-3">From the latest {traces.data?.items.length ?? 0} traces the API recorded here (a local reference environment, not production traffic). Never combined with the golden set.</p>
          </Card>
        )}
      </section>

      <section aria-labelledby="recent-retrievals-heading">
        <h2 id="recent-retrievals-heading" className="sr-only">
          Recent retrievals
        </h2>
        <KnowledgeExplorer />
      </section>
    </>
  );
}
