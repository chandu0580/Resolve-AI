import type { Metadata } from "next";
import { Lock, Sparkles } from "lucide-react";
import type { ReactNode } from "react";
import { Badge } from "@/components/ui/badge";
import { ButtonLink } from "@/components/ui/button";
import { Advanced, Card, KeyValues, Mono, PageHeader } from "@/components/ui/card";
import { ErrorState } from "@/components/ui/states";
import { DataTable, TD, TH } from "@/components/ui/table";
import { api, load } from "@/lib/api/client";
import type { PolicyRule } from "@/lib/api/types";
import { toErrorInfo } from "@/lib/errors";
import { STAGE_ORDER, reasonMeta } from "@/lib/labels";

export const metadata: Metadata = { title: "Agent Profile · ResolveAI" };

const OUTCOME_META: Record<PolicyRule["outcome"], { label: string; tone: "info" | "warning" | "success" }> = {
  handoff: { label: "Human handoff", tone: "info" },
  clarify: { label: "Clarification", tone: "warning" },
  clarify_or_handoff: { label: "Clarification or handoff", tone: "warning" },
  template_reply: { label: "Template reply", tone: "success" },
  auto_reply: { label: "Auto-handled (after verification)", tone: "success" },
};

const STAGE_OWNER: Record<string, string> = {
  request: "API",
  pii: "Deterministic",
  context: "Deterministic",
  intent: "Classifier; model second opinion",
  retrieval: "Embedding index",
  evidence_gate: "Deterministic",
  risk: "Rules; model may add flags",
  policy: "Deterministic",
  draft: "Model proposes",
  verification: "Deterministic checks and model check",
  decision: "Deterministic output gate",
  complete: "Trace store",
};

function value(v: unknown): ReactNode {
  if (v === null || v === undefined) return <span className="text-ink-3">none</span>;
  if (typeof v === "boolean") return v ? "Yes" : "No";
  if (Array.isArray(v)) return v.length ? <Mono>{v.join(", ")}</Mono> : <span className="text-ink-3">none</span>;
  if (typeof v === "object") return <Mono>{JSON.stringify(v)}</Mono>;
  return <Mono>{String(v)}</Mono>;
}

const entries = (o: Record<string, unknown> | null | undefined) =>
  Object.entries(o ?? {}).map(([k, v]) => ({
    label: <span className="font-mono text-[12px]">{k}</span>,
    value: value(v),
  }));

export default async function AgentsPage() {
  const [profile, config] = await Promise.all([load(api.agentProfile()), load(api.config())]);

  if (profile.error) {
    return (
      <>
        <PageHeader eyebrow="AI" title="ResolveAI" description="AI customer support agent for Apple Support." />
        <ErrorState error={toErrorInfo(profile.error)} />
      </>
    );
  }

  const p = profile.data;
  const versions = p.agent.versions as unknown as Record<string, unknown>;

  const header = (
    <PageHeader
      eyebrow={
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold uppercase tracking-wider text-brand-700">AI</span>
          <Badge tone={p.agent.state === "loaded" ? "success" : "warning"}>
            {p.agent.state === "loaded" ? "Active" : p.agent.state}
          </Badge>
        </div>
      }
      title={p.agent.name}
      description={`AI customer support agent for ${p.agent.brand === "AppleSupport" ? "Apple Support" : p.agent.brand}.`}
      actions={
        <>
          <ButtonLink href="/simulate" icon={Sparkles} variant="primary">
            Test the Agent
          </ButtonLink>
          <ButtonLink href="/evaluation" variant="secondary">
            View evaluation
          </ButtonLink>
        </>
      }
    />
  );

  return (
    <>
      {header}

      {/* Read-only banner */}
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3 rounded-md border border-line bg-surface px-3.5 py-2 text-xs text-ink-3">
        <div className="flex items-center gap-2">
          <Lock className="size-3.5 text-ink-3 shrink-0" aria-hidden="true" />
          <span className="font-semibold text-ink">Read-only configuration</span>
          <span>•</span>
          <span>Configuration lives in code and frozen config files and changes through review. Nothing on this page can change the agent.</span>
        </div>
      </div>

      <div className="space-y-6">
        {/* SECTION 1: Agent Overview */}
        <div className="grid items-start gap-4 lg:grid-cols-[300px_minmax(0,1fr)]">
          {/* Left: Agent profile */}
          <Card title="Agent profile" headingLevel={2}>
            <div className="divide-y divide-line/60 text-[13px]">
              <div className="flex items-center justify-between py-2">
                <span className="text-ink-3">Name</span>
                <span className="font-medium text-ink">{p.agent.name}</span>
              </div>
              <div className="flex items-center justify-between py-2">
                <span className="text-ink-3">Brand</span>
                <span className="font-medium text-ink">
                  {p.agent.brand === "AppleSupport" ? "Apple Support" : p.agent.brand}
                </span>
              </div>
              <div className="flex items-center justify-between py-2">
                <span className="text-ink-3">Status</span>
                <Badge tone={p.agent.state === "loaded" ? "success" : "warning"}>
                  {p.agent.state === "loaded" ? "Active" : p.agent.state}
                </Badge>
              </div>
              <div className="flex items-center justify-between py-2">
                <span className="text-ink-3">Environment</span>
                <span className="font-medium text-ink capitalize">
                  {config.data?.service.env ?? "Development"}
                </span>
              </div>
            </div>
          </Card>

          {/* Right: What this agent does */}
          <Card title="What this agent does" headingLevel={2}>
            <p className="text-[14px] leading-relaxed text-ink">
              ResolveAI classifies customer requests, finds relevant historical support evidence, drafts grounded responses, and decides whether to resolve, clarify, or hand off to a human.
            </p>
            <div className="mt-4 grid gap-3 sm:grid-cols-3">
              <div className="rounded-md border border-line bg-canvas/50 p-3">
                <div className="text-xs font-semibold text-brand-700 uppercase tracking-wider">Classify</div>
                <p className="mt-1 text-[13px] text-ink-2">Understand the customer&apos;s intent.</p>
              </div>
              <div className="rounded-md border border-line bg-canvas/50 p-3">
                <div className="text-xs font-semibold text-brand-700 uppercase tracking-wider">Ground</div>
                <p className="mt-1 text-[13px] text-ink-2">Use relevant historical support evidence.</p>
              </div>
              <div className="rounded-md border border-line bg-canvas/50 p-3">
                <div className="text-xs font-semibold text-brand-700 uppercase tracking-wider">Decide</div>
                <p className="mt-1 text-[13px] text-ink-2">Resolve automatically or route to a human when needed.</p>
              </div>
            </div>
          </Card>
        </div>

        {/* SECTION 2: How the Agent Handles Requests */}
        <Card
          title="How the agent handles requests"
          description="Every request is assessed for intent, evidence, and risk before ResolveAI decides how to respond."
          headingLevel={2}
        >
          <div className="grid gap-4 md:grid-cols-3">
            {/* Outcome 1: Auto-handle */}
            <div className="rounded-lg border border-line bg-surface p-4 flex flex-col justify-between shadow-[0_1px_2px_rgba(15,23,42,0.03)]">
              <div>
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-semibold text-ink">Auto-handle</span>
                  <span className="inline-flex size-2.5 rounded-full bg-[#3d7a57]" aria-hidden="true" />
                </div>
                <p className="mt-2 text-[13px] text-ink-2">
                  Resolve when confidence and evidence are strong.
                </p>
                <div className="mt-3 rounded border border-line/60 bg-canvas/60 p-2.5">
                  <div className="text-[10px] font-semibold uppercase tracking-wider text-ink-3">When applied</div>
                  <p className="mt-0.5 text-xs text-ink font-medium">
                    Clear request + sufficient evidence + no safety concern
                  </p>
                </div>
              </div>
              <p className="mt-3 text-[11.5px] text-ink-3 leading-snug">
                {p.allowed_actions.find((a) => a.action === "AUTO_HANDLE")?.requires}
              </p>
            </div>

            {/* Outcome 2: Ask for clarification */}
            <div className="rounded-lg border border-line bg-surface p-4 flex flex-col justify-between shadow-[0_1px_2px_rgba(15,23,42,0.03)]">
              <div>
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-semibold text-ink">Ask for clarification</span>
                  <span className="inline-flex size-2.5 rounded-full bg-[#8a5a12]" aria-hidden="true" />
                </div>
                <p className="mt-2 text-[13px] text-ink-2">
                  Get missing information when the issue is unclear.
                </p>
                <div className="mt-3 rounded border border-line/60 bg-canvas/60 p-2.5">
                  <div className="text-[10px] font-semibold uppercase tracking-wider text-ink-3">When applied</div>
                  <p className="mt-0.5 text-xs text-ink font-medium">
                    Request is ambiguous or missing information needed to proceed safely
                  </p>
                </div>
              </div>
              <p className="mt-3 text-[11.5px] text-ink-3 leading-snug">
                {p.allowed_actions.find((a) => a.action === "CLARIFICATION_REQUIRED")?.requires}
              </p>
            </div>

            {/* Outcome 3: Human handoff */}
            <div className="rounded-lg border border-line bg-surface p-4 flex flex-col justify-between shadow-[0_1px_2px_rgba(15,23,42,0.03)]">
              <div>
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-semibold text-ink">Human handoff</span>
                  <span className="inline-flex size-2.5 rounded-full bg-[#D9B4B0]" aria-hidden="true" />
                </div>
                <p className="mt-2 text-[13px] text-ink-2">
                  Escalate when the request is sensitive, risky, or cannot be safely resolved.
                </p>
                <div className="mt-3 rounded border border-line/60 bg-canvas/60 p-2.5">
                  <div className="text-[10px] font-semibold uppercase tracking-wider text-ink-3">When applied</div>
                  <p className="mt-0.5 text-xs text-ink font-medium">
                    Sensitive, risky, unsupported, or insufficiently grounded request
                  </p>
                </div>
              </div>
              <p className="mt-3 text-[11.5px] text-ink-3 leading-snug">
                {p.allowed_actions.find((a) => a.action === "HUMAN_HANDOFF")?.requires}
              </p>
            </div>
          </div>
        </Card>

        {/* SECTION 3: Human Handoff Rules */}
        <Card
          title="When ResolveAI hands off to a human"
          description="ResolveAI is deliberately conservative. If a request involves sensitive account details, risk signals, or lack of verified historical evidence, automated replies are withheld and the case is routed to human teammates."
          headingLevel={2}
        >
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {[
              { title: "Safety concerns", desc: "Customer safety, potential injury, or crisis situations." },
              { title: "Security concerns", desc: "Account takeover risk, suspected breach, or device compromise." },
              { title: "Account access", desc: "Identity verification, password resets, or authentication challenges." },
              { title: "Billing or payment", desc: "Transactions, refund requests, invoices, or payment modifications." },
              { title: "Sensitive / private information", desc: "Requests requiring private personal identifiers or credentials." },
              { title: "Hardware or physical damage", desc: "Physical device diagnostics, repairs, or battery replacements." },
              { title: "Repeated unsuccessful attempts", desc: "Customers who have already attempted troubleshooting without success." },
              { title: "Customer explicitly requests a human", desc: "Direct request to speak with a human support agent." },
              { title: "Prompt injection or suspicious instructions", desc: "Attempts to override system instructions or extract sensitive internal parameters." },
              { title: "Unsupported requests", desc: "Topics outside the supported product taxonomy or capability scope." },
              { title: "Insufficient / conflicting evidence", desc: "Requests where reliable historical support evidence is absent or inconsistent." },
            ].map((item) => (
              <div key={item.title} className="rounded-md border border-line bg-canvas/40 p-3">
                <div className="flex items-center gap-1.5 text-xs font-semibold text-ink">
                  <span className="size-1.5 shrink-0 rounded-full bg-[#D9B4B0]" aria-hidden="true" />
                  {item.title}
                </div>
                <p className="mt-1 text-[12px] text-ink-3 leading-relaxed">{item.desc}</p>
              </div>
            ))}
          </div>
        </Card>

        {/* SECTION 4: Knowledge & Response Behavior */}
        <Card title="Knowledge and response behavior" headingLevel={2}>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-md border border-line bg-canvas/50 p-3.5">
              <div className="text-[11px] font-semibold uppercase tracking-wider text-ink-3">Knowledge source</div>
              <p className="mt-1.5 text-[13.5px] font-medium text-ink">Historical Apple Support conversations</p>
              <p className="mt-1 text-[12px] text-ink-3">Verified resolution records from past customer support interactions.</p>
            </div>

            <div className="rounded-md border border-line bg-canvas/50 p-3.5">
              <div className="text-[11px] font-semibold uppercase tracking-wider text-ink-3">Response principle</div>
              <p className="mt-1.5 text-[13.5px] font-medium text-ink">Grounded in proven resolutions</p>
              <p className="mt-1 text-[12px] text-ink-3">Every automated response must cite relevant historical resolutions.</p>
            </div>

            <div className="rounded-md border border-line bg-canvas/50 p-3.5">
              <div className="text-[11px] font-semibold uppercase tracking-wider text-ink-3">Evidence behavior</div>
              <p className="mt-1.5 text-[13.5px] font-medium text-ink">Strict evidence requirements</p>
              <p className="mt-1 text-[12px] text-ink-3">ResolveAI withholds automatic replies when sufficient evidence is unavailable.</p>
            </div>

            <div className="rounded-md border border-line bg-canvas/50 p-3.5">
              <div className="text-[11px] font-semibold uppercase tracking-wider text-ink-3">Verification</div>
              <p className="mt-1.5 text-[13.5px] font-medium text-ink">Multi-step response checks</p>
              <p className="mt-1 text-[12px] text-ink-3">All drafted responses are verified against safety and accuracy gates before delivery.</p>
            </div>
          </div>
        </Card>

        {/* SECTION 5: Safety Boundaries */}
        <Card title="Safety boundaries" headingLevel={2}>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="rounded-lg border border-line bg-canvas/40 p-4">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-brand-700">
                Always hand off
              </h3>
              <p className="mt-1 text-xs text-ink-3">Triggers that immediately require a human operator:</p>
              <ul className="mt-3 space-y-2 text-[13px] text-ink-2">
                <li className="flex items-center gap-2">
                  <span className="size-1.5 rounded-full bg-[#D9B4B0]" aria-hidden="true" />
                  Safety or security concerns
                </li>
                <li className="flex items-center gap-2">
                  <span className="size-1.5 rounded-full bg-[#D9B4B0]" aria-hidden="true" />
                  Account access / identity-sensitive requests
                </li>
                <li className="flex items-center gap-2">
                  <span className="size-1.5 rounded-full bg-[#D9B4B0]" aria-hidden="true" />
                  Billing or payment actions
                </li>
                <li className="flex items-center gap-2">
                  <span className="size-1.5 rounded-full bg-[#D9B4B0]" aria-hidden="true" />
                  Sensitive private information
                </li>
                <li className="flex items-center gap-2">
                  <span className="size-1.5 rounded-full bg-[#D9B4B0]" aria-hidden="true" />
                  Hardware / physical damage
                </li>
                <li className="flex items-center gap-2">
                  <span className="size-1.5 rounded-full bg-[#D9B4B0]" aria-hidden="true" />
                  Explicit human requests
                </li>
                <li className="flex items-center gap-2">
                  <span className="size-1.5 rounded-full bg-[#D9B4B0]" aria-hidden="true" />
                  Suspicious / prompt-injection requests
                </li>
              </ul>
            </div>

            <div className="rounded-lg border border-line bg-canvas/40 p-4">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-ink-2">
                Never allowed
              </h3>
              <p className="mt-1 text-xs text-ink-3">Prohibited actions enforced at all times:</p>
              <ul className="mt-3 space-y-2 text-[13px] text-ink-2">
                <li className="flex items-center gap-2">
                  <span className="size-1.5 rounded-full bg-danger" aria-hidden="true" />
                  Perform sensitive account actions (refunds, order changes, account edits)
                </li>
                <li className="flex items-center gap-2">
                  <span className="size-1.5 rounded-full bg-danger" aria-hidden="true" />
                  Invent unsupported resolutions or ungrounded facts
                </li>
                <li className="flex items-center gap-2">
                  <span className="size-1.5 rounded-full bg-danger" aria-hidden="true" />
                  Send an unverified response or bypass verification gates
                </li>
                <li className="flex items-center gap-2">
                  <span className="size-1.5 rounded-full bg-danger" aria-hidden="true" />
                  Let the language model decide escalations (policy is deterministic)
                </li>
                <li className="flex items-center gap-2">
                  <span className="size-1.5 rounded-full bg-danger" aria-hidden="true" />
                  Expose private customer identifiers or secrets
                </li>
              </ul>
            </div>
          </div>
        </Card>

        {/* SECTION 6: Release Alignment */}
        <Card title="Release alignment" headingLevel={2}>
          <div className="rounded-md border border-line bg-surface p-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="text-[11px] font-semibold uppercase tracking-wider text-ink-3">Evaluation status</span>
                {p.evaluated.differences.length === 0 ? (
                  <Badge tone="success">Aligned</Badge>
                ) : (
                  <Badge tone="warning">Differences detected</Badge>
                )}
              </div>
              <p className="text-[14px] font-semibold text-ink">
                {p.evaluated.differences.length === 0
                  ? "Current runtime matches the evaluated release."
                  : "Current runtime differs from the evaluated release."}
              </p>
              <p className="text-[13px] text-ink-3">
                Evaluation results describe the frozen release used for benchmarking and should not be interpreted as exact measurements of the current runtime.
              </p>
            </div>

            <a
              href="#advanced-details"
              className="inline-flex items-center gap-1 text-xs font-medium text-brand-700 hover:underline shrink-0"
            >
              View technical differences &rarr;
            </a>
          </div>
        </Card>

        {/* SECTION 7 & 8: Advanced Technical Details & Policy Rules (Collapsed by default) */}
        <div id="advanced-details">
          <Card title="Advanced technical details" headingLevel={2}>
            <p className="text-[13px] text-ink-3">
              For engineering review, reproducibility, and audit.
            </p>
            <Advanced label="Show engineering specifications, pipeline stages, and policy rules">
              <div className="space-y-6 pt-3">
                {/* Subsection 1: Runtime & Model Configuration */}
                <div>
                  <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-ink">
                    Runtime & Model Configuration
                  </h3>
                  <KeyValues
                    columns={2}
                    items={[
                      {
                        label: "Model",
                        value: p.agent.model.name ? <Mono>{p.agent.model.name}</Mono> : "No model configured",
                        hint: `${p.agent.model.enabled ? "Model calls enabled" : "Model calls disabled"}. ${p.agent.model.role}.`,
                      },
                      { label: "API environment", value: config.data?.service.env ?? "n/a" },
                      { label: "Pipeline version", value: <Mono>{(versions.pipeline as string) || "n/a"}</Mono> },
                      { label: "Policy version", value: <Mono>{(versions.policy as string) || "n/a"}</Mono> },
                      { label: "Output gate version", value: <Mono>{(versions.output_gate as string) || "n/a"}</Mono> },
                      { label: "Evidence gate version", value: <Mono>{(versions.evidence_gate as string) || "n/a"}</Mono> },
                      { label: "Rerank version", value: <Mono>{(versions.rerank as string) || "n/a"}</Mono> },
                      { label: "Classifier version", value: <Mono>{(versions.classifier as string) || "n/a"}</Mono> },
                      { label: "Config hash", value: <Mono>{(versions.config_hash as string) || "n/a"}</Mono> },
                    ]}
                  />
                </div>

                {/* Subsection 2: Execution Pipeline */}
                <div>
                  <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-ink">
                    Execution Pipeline (12 Stages)
                  </h3>
                  <ol className="grid gap-1.5 sm:grid-cols-2">
                    {STAGE_ORDER.map((s, i) => (
                      <li
                        key={s.key}
                        className="flex items-baseline justify-between gap-2 rounded-md border border-line px-3 py-1.5 text-[12px]"
                      >
                        <span className="text-ink">
                          <span className="mr-2 text-ink-3 tabular">{i + 1}</span>
                          {s.label}
                        </span>
                        <span className="text-[11px] text-ink-3">{STAGE_OWNER[s.key]}</span>
                      </li>
                    ))}
                  </ol>
                </div>

                {/* Subsection 3: Active Configuration Parameters */}
                <div>
                  <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-ink">
                    Active Configuration Parameters
                  </h3>
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div className="rounded-md border border-line bg-canvas/30 p-3">
                      <h4 className="mb-1 text-xs font-medium text-ink">Agent parameters</h4>
                      <KeyValues items={entries(p.active.agent_config)} />
                    </div>
                    <div className="rounded-md border border-line bg-canvas/30 p-3">
                      <h4 className="mb-1 text-xs font-medium text-ink">Retrieval parameters</h4>
                      <KeyValues items={entries(p.active.retrieval)} />
                    </div>
                    <div className="rounded-md border border-line bg-canvas/30 p-3">
                      <h4 className="mb-1 text-xs font-medium text-ink">Evidence thresholds (gate)</h4>
                      <KeyValues items={entries(p.active.evidence_gate)} />
                    </div>
                    <div className="rounded-md border border-line bg-canvas/30 p-3">
                      <h4 className="mb-1 text-xs font-medium text-ink">Rerank weights</h4>
                      <KeyValues items={entries(p.active.rerank_weights)} />
                    </div>
                  </div>
                </div>

                {/* Subsection 4: Evaluation Configuration & Differences */}
                <div>
                  <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-ink">
                    Evaluation Benchmark Configuration & Differences
                  </h3>
                  {p.evaluated.agent_config ? (
                    <div className="space-y-3">
                      <KeyValues
                        columns={2}
                        items={[
                          { label: "Benchmark source", value: p.evaluated.source },
                          { label: "Evaluated pipeline", value: value(p.evaluated.pipeline_version) },
                          { label: "Evaluated config hash", value: value(p.evaluated.config_hash) },
                        ]}
                      />

                      <div className="mt-2">
                        <div className="mb-1 text-xs font-medium text-ink">Technical differences from active runtime</div>
                        {p.evaluated.differences.length ? (
                          <DataTable label="Configuration differences" minWidth={420}>
                            <thead>
                              <tr>
                                <th scope="col" className={TH}>Field</th>
                                <th scope="col" className={TH}>Active</th>
                                <th scope="col" className={TH}>Evaluated</th>
                              </tr>
                            </thead>
                            <tbody>
                              {p.evaluated.differences.map((d) => (
                                <tr key={d.field}>
                                  <th scope="row" className={`${TD} text-left font-mono text-[12px] font-normal`}>
                                    {d.field}
                                    {d.note ? <div className="font-sans text-[11px] text-ink-3">{d.note}</div> : null}
                                  </th>
                                  <td className={TD}>{value(d.active)}</td>
                                  <td className={TD}>{value(d.evaluated)}</td>
                                </tr>
                              ))}
                            </tbody>
                          </DataTable>
                        ) : (
                          <p className="text-[13px] text-ink-2">
                            None: the active agent runs with the exact evaluated configuration.
                          </p>
                        )}
                      </div>
                    </div>
                  ) : (
                    <p className="text-[13px] text-ink-3">Release evaluation metadata is not available.</p>
                  )}
                </div>

                {/* Subsection 5: Complete Policy Rules Table */}
                <div>
                  <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                    <h3 className="text-xs font-semibold uppercase tracking-wider text-ink">
                      Deterministic Policy Rules ({p.policy.rules.length} Rules in Order)
                    </h3>
                    <Badge tone="brand">
                      {p.policy.version} · {p.policy.order}
                    </Badge>
                  </div>
                  <div className="overflow-x-auto rounded-md border border-line">
                    <DataTable label="Policy rules in order" minWidth={850}>
                      <thead>
                        <tr>
                          <th scope="col" className={TH}>#</th>
                          <th scope="col" className={TH}>Rule</th>
                          <th scope="col" className={TH}>Outcome</th>
                          <th scope="col" className={TH}>Reason code</th>
                          <th scope="col" className={TH}>When it matches</th>
                        </tr>
                      </thead>
                      <tbody>
                        {p.policy.rules.map((r, i) => (
                          <tr key={r.rule}>
                            <td className={`${TD} tabular text-ink-3`}>{i + 1}</td>
                            <th scope="row" className={`${TD} text-left font-mono text-[12px] font-normal`}>
                              {r.rule}
                            </th>
                            <td className={TD}>
                              <Badge tone={OUTCOME_META[r.outcome].tone}>{OUTCOME_META[r.outcome].label}</Badge>
                            </td>
                            <td className={TD}>
                              <Mono>{r.reason_code}</Mono>
                              <div className="text-[11px] text-ink-3">{reasonMeta(r.reason_code).label}</div>
                            </td>
                            <td className={`${TD} text-ink-2`}>{r.when}</td>
                          </tr>
                        ))}
                      </tbody>
                    </DataTable>
                  </div>
                  <p className="mt-2 text-xs text-ink-3">
                    Deterministic rule order: the first matching rule is executed. Code verification asserts that the runtime evaluation strictly follows this order.
                  </p>
                </div>
              </div>
            </Advanced>
          </Card>
        </div>
      </div>
    </>
  );
}
