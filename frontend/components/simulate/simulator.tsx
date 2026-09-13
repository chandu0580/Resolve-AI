"use client";

import { ArrowRight, CircleCheck, CircleX, LoaderCircle, Play, Plus, RotateCcw, Sparkles, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button, ButtonLink } from "@/components/ui/button";
import { Advanced, Card, Notice } from "@/components/ui/card";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { ConversationWorkspace } from "@/components/conversation/workspace";
import { ApiError, api } from "@/lib/api/client";
import type { AgentTrace, DemoScenario, ResolveRequest, ResolveResponse } from "@/lib/api/types";
import { isResolveResponse } from "@/lib/api/validate";
import { toErrorInfo, type ErrorInfo } from "@/lib/errors";
import { duration, humanize } from "@/lib/format";
import { reasonMeta } from "@/lib/labels";
import { groupTraceEvents, type StageStatus } from "@/lib/trace";
import { clearResults, saveResult, useStoredResults, type StoredResult } from "@/lib/results-store";
import { LLM_REQUIREMENT, checkExpectation, expectationText } from "@/lib/scenarios";

interface Turn {
  id: number;
  role: "customer" | "brand";
  text: string;
}

type RunState =
  | { kind: "idle" }
  | { kind: "running"; label: string }
  | { kind: "done"; stored: StoredResult; trace: AgentTrace | null; scenario: DemoScenario | null }
  | { kind: "error"; error: ErrorInfo };

const CHANNELS = ["", "web", "chat", "email", "twitter", "api"] as const;

/** Presets for the primary operator playground */
const PRESETS = [
  { id: "A", label: "Grounded answer", hint: "Verified fix in corpus" },
  { id: "B", label: "Needs clarification", hint: "Ambiguous request" },
  { id: "C", label: "Human handoff", hint: "Security / account risk" },
  { id: "D", label: "Insufficient evidence", hint: "No verified resolution" },
  { id: "E", label: "Prompt injection", hint: "Adversarial override attempt" },
  { id: "F", label: "Model unavailable", hint: "Deterministic fallback" },
] as const;

/** Curated demo path preserved for engineering audit in Advanced testing */
const CURATED: { n: number; title: string; api?: string; message?: string; expected: string; lookFor: string }[] = [
  { n: 1, title: "Safe grounded troubleshooting", api: "A", expected: "Auto-handled with cited evidence", lookFor: "Sufficient evidence, the exact cases the reply cites, verification and every output-gate check passing." },
  { n: 2, title: "Ambiguous request", api: "B", expected: "Clarification", lookFor: "No concrete issue is stated: one clarifying question and no troubleshooting." },
  { n: 3, title: "Risky request: human handoff", api: "C", expected: "Human handoff with a packet", lookFor: "A security risk flag is a hard block: a handoff packet with a recommended next action." },
  { n: 4, title: "Insufficient evidence", api: "D", expected: "Clarification", lookFor: "The evidence gate finds no consistent resolution, so ResolveAI asks instead of answering." },
  {
    n: 5,
    title: "Sensitive or private information",
    message: "I need the status of my repair order and which card you charged for it. Can you look it up on my Apple ID?",
    expected: "Human handoff",
    lookFor: "Order, payment and account details cannot be handled in a public reply; a deterministic rule requires a human.",
  },
  { n: 6, title: "Prompt injection", api: "E", expected: "Human handoff", lookFor: "Instruction-like text is treated as data and the prompt_injection rule hands off." },
  {
    n: 7,
    title: "Model failure",
    api: "F",
    expected: "Human handoff when the model is unavailable",
    lookFor:
      "The fallback hands off instead of failing. With a working model this message is answered normally; to see the outage live, start the API with an unreachable model endpoint (docs/DEMO.md).",
  },
];

const STAGE_STATUS_TEXT: Record<StageStatus, string> = { ok: "completed", skipped: "skipped", fallback: "fallback", error: "failed", flagged: "flagged", not_recorded: "not recorded" };
const STAGE_STATUS_CLS: Record<StageStatus, string> = {
  ok: "border-line bg-surface",
  skipped: "border-line bg-subtle",
  fallback: "border-warning-line bg-warning-bg",
  error: "border-danger-line bg-danger-bg",
  flagged: "border-warning-line bg-warning-bg",
  not_recorded: "border-line bg-subtle",
};

/** Recorded outcome of each pipeline stage for one run */
function PipelineStepper({ result, trace }: { result: ResolveResponse; trace: AgentTrace | null }) {
  const groups = groupTraceEvents(
    trace?.events ?? [],
    (trace?.stage_status ?? result.stage_status) as Record<string, string>,
    (trace?.latency_ms ?? result.latency_ms) as Record<string, number>,
  ).filter((g) => g.key !== "other");
  return (
    <Card title="Agent stages" description="The recorded outcome of each stage for this run, in execution order. ResolveAI stores no chain-of-thought, so none is shown.">
      <ol aria-label="Agent stages for this run" className="flex flex-wrap gap-1.5">
        {groups.map((g, i) => (
          <li key={g.key} className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-xs text-ink ${STAGE_STATUS_CLS[g.status]}`}>
            <span className="text-ink-3 tabular">{i + 1}</span>
            <span>{g.label}</span>
            <span className="text-ink-3">
              · {STAGE_STATUS_TEXT[g.status]}
              {g.durationMs ? ` · ${duration(g.durationMs)}` : ""}
            </span>
          </li>
        ))}
      </ol>
    </Card>
  );
}

function Running({ onCancel }: { label: string; onCancel: () => void }) {
  const [startedAt] = useState(() => Date.now());
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = window.setInterval(() => setNow(Date.now()), 200);
    return () => window.clearInterval(t);
  }, []);
  return (
    <div className="flex min-h-[200px] flex-col items-center justify-center gap-4 rounded-lg border border-line bg-canvas/40 p-6">
      <LoaderCircle className="size-6 animate-spin text-brand-700" aria-hidden="true" />
      <div className="text-center">
        <p role="status" className="text-sm font-semibold text-ink">Analyzing request…</p>
        <p className="mt-1 text-xs text-ink-3">Reviewing intent, evidence, and safety boundaries</p>
      </div>
      <div className="flex items-center gap-1.5 text-[11px] text-ink-3">
        <span className="tabular font-medium" aria-hidden="true">{((now - startedAt) / 1000).toFixed(1)}s</span>
        <Button size="sm" variant="ghost" icon={X} onClick={onCancel}>Cancel</Button>
      </div>
    </div>
  );
}

function CuratedCard({
  item,
  scenario,
  busy,
  onRun,
}: {
  item: (typeof CURATED)[number];
  scenario: DemoScenario | null;
  busy: boolean;
  onRun: (conversation: ResolveRequest["conversation"]) => void;
}) {
  const conversation: ResolveRequest["conversation"] | null = scenario ? scenario.conversation : item.message ? [{ role: "customer", text: item.message }] : null;
  const customer = conversation ? [...conversation].reverse().find((t) => t.role === "customer") : null;
  return (
    <li className="flex flex-col rounded-lg border border-line bg-surface p-3">
      <h3 className="text-[13px] font-semibold text-ink">
        <span className="mr-1.5 text-ink-3 tabular">{item.n}</span>
        {item.title}
      </h3>
      <p className="mt-1 text-xs text-ink-3">
        Expected: {item.expected}
        {item.api ? ` · API scenario ${item.api}` : " · curated message, no frozen expectation"}
      </p>
      {customer ? <p className="mt-1.5 line-clamp-2 text-xs text-ink-2">“{customer.text}”</p> : null}
      <p className="mt-1 text-xs text-ink-2">{item.lookFor}</p>
      <div className="mt-auto flex justify-end pt-2">
        <Button size="sm" variant="secondary" icon={Play} disabled={busy || !conversation} onClick={() => conversation && onRun(conversation)} aria-label={`Run curated scenario ${item.n}: ${item.title}`}>
          Run
        </Button>
      </div>
      {!conversation ? <p className="mt-1 text-xs text-warning">Scenario {item.api} is not available from the API.</p> : null}
    </li>
  );
}

function ScenarioCard({ scenario, busy, onLoad, onRun }: { scenario: DemoScenario; busy: boolean; onLoad: () => void; onRun: () => void }) {
  const customer = [...scenario.conversation].reverse().find((t) => t.role === "customer");
  return (
    <li className="rounded-lg border border-line bg-surface p-3">
      <div className="flex items-start gap-2.5">
        <span className="flex size-6 shrink-0 items-center justify-center rounded-md bg-subtle font-mono text-xs font-semibold text-ink-2" aria-hidden="true">
          {scenario.id}
        </span>
        <div className="min-w-0 flex-1">
          <h3 className="text-[13px] font-semibold text-ink">{scenario.title}</h3>
          <div className="mt-1 flex flex-wrap gap-1">
            <Badge tone={scenario.llm === "unavailable" ? "warning" : "neutral"}>{LLM_REQUIREMENT[scenario.llm]}</Badge>
            {scenario.conversation.length > 1 ? <Badge>{scenario.conversation.length} turns</Badge> : null}
          </div>
          {customer ? <p className="mt-1.5 line-clamp-2 text-xs text-ink-2">“{customer.text}”</p> : null}
          <p className="mt-1 text-xs text-ink-3">Expected: {expectationText(scenario)}</p>
          {scenario.llm === "unavailable" ? (
            <p className="mt-1 text-xs text-warning">Through the live API the configured model answers, so this run will not show the outage path. The CLI demo simulates the outage.</p>
          ) : null}
        </div>
      </div>
      <div className="mt-2.5 flex flex-wrap justify-end gap-1.5">
        <Button size="sm" variant="ghost" onClick={onLoad} disabled={busy}>
          Load into form
        </Button>
        <Button size="sm" variant="secondary" icon={Play} onClick={onRun} disabled={busy} aria-label={`Run scenario ${scenario.id}: ${scenario.title}`}>
          Run
        </Button>
      </div>
    </li>
  );
}

export function Simulator({ scenarios, scenariosError, maxMessageChars, model }: { scenarios: DemoScenario[] | null; scenariosError: ErrorInfo | null; maxMessageChars: number; model: string | null }) {
  const [message, setMessage] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [channel, setChannel] = useState<(typeof CHANNELS)[number]>("web");
  const [state, setState] = useState<RunState>({ kind: "idle" });
  const [formError, setFormError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const resultRef = useRef<HTMLDivElement>(null);
  const nextId = useRef(1);
  const stored = useStoredResults();
  const busy = state.kind === "running";

  const loadScenario = (s: DemoScenario) => {
    const earlier = s.conversation.slice(0, -1);
    setTurns(earlier.map((t) => ({ id: nextId.current++, role: t.role, text: t.text })));
    setMessage(s.conversation[s.conversation.length - 1]?.text ?? "");
    setFormError(null);
  };

  const loadPreset = (presetId: string) => {
    const s = scenarios?.find((sc) => sc.id === presetId);
    if (s) {
      loadScenario(s);
    }
  };

  const run = async (conversation: ResolveRequest["conversation"], label: string, scenario: DemoScenario | null) => {
    const controller = new AbortController();
    abortRef.current = controller;
    setState({ kind: "running", label });
    window.requestAnimationFrame(() => resultRef.current?.scrollIntoView?.({ behavior: "smooth", block: "start" }));
    try {
      const { data } = await api.resolve({ conversation, metadata: channel ? { channel } : undefined }, { signal: controller.signal });
      if (!isResolveResponse(data)) throw new ApiError(200, "invalid_response", "The API response is missing required fields.");
      const entry = saveResult(data, label);
      let trace: AgentTrace | null = null;
      try {
        trace = (await api.trace(data.trace_id)).data;
      } catch {
        trace = null;
      }
      setState({ kind: "done", stored: entry, trace, scenario });
      window.requestAnimationFrame(() => resultRef.current?.focus());
    } catch (err) {
      if (err instanceof ApiError && err.errorCode === "cancelled") {
        setState({ kind: "idle" });
        return;
      }
      setState({ kind: "error", error: err instanceof ApiError ? toErrorInfo(err) : { status: 0, errorCode: "client_error", message: String(err) } });
    } finally {
      abortRef.current = null;
    }
  };

  const submit = () => {
    const text = message.trim();
    if (!text) return setFormError("Enter the customer message to analyze.");
    if (text.length > maxMessageChars) return setFormError(`The message has ${text.length} characters; the API accepts at most ${maxMessageChars}.`);
    if (turns.some((t) => !t.text.trim())) return setFormError("Fill in or remove the empty earlier turn.");
    setFormError(null);
    void run([...turns.map((t) => ({ role: t.role, text: t.text.trim() })), { role: "customer" as const, text }], "Custom message", null);
  };

  // Resolve result helpers
  const result = state.kind === "done" ? state.stored.result : null;
  const isAutoHandle = result?.action === "AUTO_HANDLE";
  const isClarification = result?.action === "CLARIFICATION_REQUIRED";

  const citedIds = new Set(result?.response.evidence_refs.map((r) => r.evidence_id) ?? []);
  const citedEvidence = result ? result.evidence.items.filter((item) => citedIds.has(item.evidence_id)) : [];
  const displayEvidence = citedEvidence.length ? citedEvidence : (result?.evidence.items.slice(0, 3) ?? []);

  return (
    <div className="space-y-4">
      {/* PRIMARY PLAYGROUND: Two-column layout */}
      <div className="grid items-start gap-4 lg:grid-cols-2">
        {/* LEFT COLUMN: Customer request */}
        <Card title="Customer request" headingLevel={2}>
          {/* Preset Selector */}
          <div className="mb-4">
            <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-ink-3">
              Try a scenario
            </div>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {PRESETS.map((p) => {
                const sc = scenarios?.find((s) => s.id === p.id);
                const isSelected = sc && message === sc.conversation[sc.conversation.length - 1]?.text;
                return (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => loadPreset(p.id)}
                    className={`flex flex-col items-start rounded-md border p-2 text-left transition-colors ${
                      isSelected
                        ? "border-brand-700 bg-brand-50/80 text-ink"
                        : "border-line bg-surface hover:bg-canvas text-ink-2 hover:text-ink"
                    }`}
                  >
                    <span className="text-xs font-semibold">{p.label}</span>
                    <span className="text-[11px] text-ink-3 leading-snug">{p.hint}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Form */}
          <form
            className="space-y-4"
            onSubmit={(e) => {
              e.preventDefault();
              submit();
            }}
          >
            {turns.length ? (
              <fieldset className="space-y-2">
                <legend className="mb-1 text-xs font-medium text-ink">Earlier conversation</legend>
                {turns.map((t, i) => (
                  <div key={t.id} className="flex flex-wrap items-start gap-2 rounded-md border border-line bg-canvas p-2">
                    <label className="sr-only" htmlFor={`turn-role-${t.id}`}>
                      Author of earlier turn {i + 1}
                    </label>
                    <select
                      id={`turn-role-${t.id}`}
                      value={t.role}
                      onChange={(e) => setTurns((ts) => ts.map((x) => (x.id === t.id ? { ...x, role: e.target.value as Turn["role"] } : x)))}
                      className="h-8 rounded-md border border-line bg-surface px-2 text-xs"
                    >
                      <option value="customer">Customer</option>
                      <option value="brand">Support</option>
                    </select>
                    <label className="sr-only" htmlFor={`turn-text-${t.id}`}>
                      Text of earlier turn {i + 1}
                    </label>
                    <textarea
                      id={`turn-text-${t.id}`}
                      value={t.text}
                      rows={2}
                      onChange={(e) => setTurns((ts) => ts.map((x) => (x.id === t.id ? { ...x, text: e.target.value } : x)))}
                      className="min-w-0 flex-1 resize-y rounded-md border border-line bg-surface px-2 py-1.5 text-[13px]"
                    />
                    <button type="button" onClick={() => setTurns((ts) => ts.filter((x) => x.id !== t.id))} className="rounded p-1.5 text-ink-3 hover:bg-subtle hover:text-ink" aria-label={`Remove earlier turn ${i + 1}`}>
                      <X className="size-4" aria-hidden="true" />
                    </button>
                  </div>
                ))}
              </fieldset>
            ) : null}

            <div>
              <div className="flex items-baseline justify-between gap-2">
                <label htmlFor="customer-message" className="text-xs font-medium text-ink">
                  Customer message
                </label>
                <span className={`text-xs tabular ${message.length > maxMessageChars ? "text-danger" : "text-ink-3"}`} aria-live="polite">
                  {message.length} / {maxMessageChars}
                </span>
              </div>
              <textarea
                id="customer-message"
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                rows={5}
                placeholder="e.g. My iPhone keeps changing “it” to “I.T” whenever I type. How do I fix this?"
                aria-invalid={formError ? true : undefined}
                aria-describedby={formError ? "form-error" : undefined}
                className="mt-1 w-full resize-y rounded-md border border-line-strong bg-surface px-3 py-2.5 text-sm placeholder:text-ink-3 focus:border-brand-500 focus:outline-none"
              />
            </div>

            <div className="flex flex-wrap items-end gap-3 pt-1">
              <div>
                <label htmlFor="channel" className="block text-xs font-medium text-ink">
                  Channel (optional)
                </label>
                <select id="channel" value={channel} onChange={(e) => setChannel(e.target.value as (typeof CHANNELS)[number])} className="mt-1 h-9 rounded-md border border-line-strong bg-surface px-2 text-xs">
                  {CHANNELS.map((c) => (
                    <option key={c || "none"} value={c}>
                      {c ? c.toUpperCase() : "Not specified"}
                    </option>
                  ))}
                </select>
              </div>

              <Button type="button" variant="ghost" size="sm" icon={Plus} onClick={() => setTurns((ts) => [...ts, { id: nextId.current++, role: "customer", text: "" }])} disabled={busy}>
                Add turn
              </Button>

              <div className="ml-auto flex gap-2">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  icon={RotateCcw}
                  disabled={busy}
                  onClick={() => {
                    setMessage("");
                    setTurns([]);
                    setFormError(null);
                  }}
                >
                  Reset
                </Button>
                <Button type="submit" variant="primary" icon={ArrowRight} disabled={busy} aria-label="Analyze">
                  Analyze request
                </Button>
              </div>
            </div>

            {formError ? (
              <p id="form-error" role="alert" className="text-[13px] text-danger">
                {formError}
              </p>
            ) : null}
          </form>
        </Card>

        {/* RIGHT COLUMN: ResolveAI */}
        <Card title="ResolveAI" headingLevel={2}>
          <div ref={resultRef} tabIndex={-1} className="outline-none">
            {state.kind === "idle" ? (
              <div className="flex min-h-[320px] flex-col items-center justify-center p-6 text-center">
                <div className="flex size-9 items-center justify-center rounded-full border border-line bg-surface text-brand-700 shadow-[0_1px_2px_rgba(15,23,42,0.04)]">
                  <Sparkles className="size-4" aria-hidden="true" />
                </div>
                <h3 className="mt-3 text-sm font-semibold text-ink">Ready to analyze</h3>
                <p className="mt-1.5 max-w-[26ch] text-xs leading-relaxed text-ink-3">
                  Send a customer request and ResolveAI will classify it, find relevant support history, and decide whether to answer, clarify, or hand off.
                </p>
                {/* Three-step flow */}
                <div className="mt-5 flex items-center gap-2" aria-label="How ResolveAI processes a request">
                  <div className="flex flex-col items-center gap-1">
                    <div className="flex size-7 items-center justify-center rounded-md border border-line bg-surface text-xs font-semibold text-brand-700">1</div>
                    <span className="text-[10px] font-medium uppercase tracking-wider text-ink-3">Understand</span>
                  </div>
                  <div className="h-px w-5 shrink-0 bg-line" aria-hidden="true" />
                  <div className="flex flex-col items-center gap-1">
                    <div className="flex size-7 items-center justify-center rounded-md border border-line bg-surface text-xs font-semibold text-brand-700">2</div>
                    <span className="text-[10px] font-medium uppercase tracking-wider text-ink-3">Find evidence</span>
                  </div>
                  <div className="h-px w-5 shrink-0 bg-line" aria-hidden="true" />
                  <div className="flex flex-col items-center gap-1">
                    <div className="flex size-7 items-center justify-center rounded-md border border-line bg-surface text-xs font-semibold text-brand-700">3</div>
                    <span className="text-[10px] font-medium uppercase tracking-wider text-ink-3">Decide</span>
                  </div>
                </div>
              </div>
            ) : null}

            {state.kind === "running" ? (
              <Running label={state.label} onCancel={() => abortRef.current?.abort()} />
            ) : null}

            {state.kind === "error" ? (
              <ErrorState error={state.error} retry={<Button size="sm" onClick={() => setState({ kind: "idle" })}>Dismiss</Button>} />
            ) : null}

            {state.kind === "done" && result ? (
              <div className="space-y-3">
                {/* Decision banner */}
                <div
                  className={`rounded-lg border px-4 py-3 ${
                    isAutoHandle
                      ? "border-[#98A68E]/60 bg-[#586651]/[0.06]"
                      : isClarification
                        ? "border-[#d4a359]/60 bg-[#8a5a12]/[0.06]"
                        : "border-[#D9B4B0] bg-[#A97975]/[0.08]"
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span
                        className={`inline-flex size-2 rounded-full ${
                          isAutoHandle ? "bg-[#3d7a57]" : isClarification ? "bg-[#8a5a12]" : "bg-[#A97975]"
                        }`}
                        aria-hidden="true"
                      />
                      <span
                        className={`text-[11px] font-semibold uppercase tracking-wider ${
                          isAutoHandle ? "text-[#3d7a57]" : isClarification ? "text-[#8a5a12]" : "text-[#A97975]"
                        }`}
                      >
                        {isAutoHandle ? "Auto-handle" : isClarification ? "Needs clarification" : "Human handoff"}
                      </span>
                    </div>
                    <span className="text-[11px] text-ink-3 tabular">{duration(result.latency_ms.total)}</span>
                  </div>
                  <p className="mt-1 text-[13px] font-medium text-ink">
                    {isAutoHandle
                      ? "Resolved automatically with strong historical support evidence"
                      : isClarification
                        ? "Missing details needed before this can be safely resolved"
                        : `${reasonMeta(result.outcome.reason_code).label} — human review required`}
                  </p>
                </div>

                {/* Content: Auto-handle / Clarification / Handoff */}
                {isAutoHandle ? (
                  <div className="space-y-3">
                    {/* Suggested Response */}
                    <div className="space-y-1.5">
                      <div className="flex items-center justify-between">
                        <h4 className="text-[11px] font-semibold uppercase tracking-wider text-ink-3">Suggested response</h4>
                        <span className="text-[11px] text-brand-700">Grounded &amp; verified</span>
                      </div>
                      <div className="rounded-md border border-line bg-surface px-3.5 py-3 text-[13px] leading-relaxed text-ink">
                        {result.response.text}
                      </div>
                    </div>

                    {/* Why this decision? */}
                    <div className="rounded-md border border-line bg-canvas/60 px-3 py-2.5 text-xs">
                      <div className="font-semibold uppercase tracking-wider text-ink-3">Why this decision?</div>
                      <p className="mt-1 leading-relaxed text-ink-2">
                        Historical evidence was found in verified support cases and no safety or account rules were triggered. All output checks passed.
                      </p>
                    </div>

                    {/* Supporting Evidence */}
                    {displayEvidence.length ? (
                      <div className="space-y-1.5">
                        <h4 className="text-[11px] font-semibold uppercase tracking-wider text-ink-3">Supporting evidence · {displayEvidence.length} case{displayEvidence.length === 1 ? "" : "s"}</h4>
                        <div className="space-y-1.5">
                          {displayEvidence.map((item) => (
                            <div key={item.evidence_id} className="rounded-md border border-line bg-canvas/40 px-3 py-2 text-xs">
                              <div className="flex items-center justify-between gap-2">
                                <span className="font-medium text-ink">Case {item.evidence_id}</span>
                                {item.quality?.resolution_relevance ? (
                                  <Badge tone="brand">{humanize(item.quality.action_class).toLowerCase()}</Badge>
                                ) : null}
                              </div>
                              <p className="mt-1 text-ink-2 line-clamp-1"><strong className="font-medium text-ink-3">Customer:</strong> {item.customer_message}</p>
                              <p className="mt-0.5 text-ink line-clamp-2"><strong className="font-medium text-brand-700">Support:</strong> {item.brand_reply}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : null}
                  </div>
                ) : isClarification ? (
                  <div className="space-y-3">
                    {/* Clarification question */}
                    <div className="space-y-1.5">
                      <h4 className="text-[11px] font-semibold uppercase tracking-wider text-ink-3">Clarification question</h4>
                      <div className="rounded-md border border-[#d4a359]/50 bg-surface px-3.5 py-3 text-[13px] leading-relaxed text-ink">
                        {result.clarification?.question ?? result.response.text}
                      </div>
                    </div>

                    {/* Why this decision? */}
                    <div className="rounded-md border border-line bg-canvas/60 px-3 py-2.5 text-xs">
                      <div className="font-semibold uppercase tracking-wider text-ink-3">Why this decision?</div>
                      <p className="mt-1 leading-relaxed text-ink-2">
                        The request is ambiguous or missing details needed to safely resolve it. ResolveAI asks for clarification rather than assuming.
                      </p>
                    </div>

                    {/* Evidence if present */}
                    {displayEvidence.length ? (
                      <div className="space-y-1.5">
                        <h4 className="text-[11px] font-semibold uppercase tracking-wider text-ink-3">Evidence evaluated · {displayEvidence.length} case{displayEvidence.length === 1 ? "" : "s"}</h4>
                        <div className="space-y-1.5">
                          {displayEvidence.map((item) => (
                            <div key={item.evidence_id} className="rounded-md border border-line bg-canvas/40 px-3 py-2 text-xs">
                              <p className="text-ink-2 line-clamp-1"><strong className="font-medium text-ink-3">Customer:</strong> {item.customer_message}</p>
                              <p className="mt-0.5 text-ink line-clamp-2"><strong className="font-medium text-brand-700">Support:</strong> {item.brand_reply}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : null}
                  </div>
                ) : (
                  <div className="space-y-3">
                    {/* Handoff reason */}
                    <div className="space-y-1.5">
                      <h4 className="text-[11px] font-semibold uppercase tracking-wider text-ink-3">Why a human is needed</h4>
                      <div className="rounded-md border border-[#D9B4B0] bg-surface px-3.5 py-3 text-[13px] leading-relaxed text-ink">
                        {result.handoff?.customer_issue ?? result.conversation.message.text}
                      </div>
                    </div>

                    {/* Risk and context */}
                    <div className="divide-y divide-line rounded-md border border-line bg-canvas/40 text-xs">
                      <div className="flex items-start justify-between gap-3 px-3 py-2">
                        <span className="text-ink-3">Reason</span>
                        <span className="text-right font-medium text-[#A97975]">{reasonMeta(result.outcome.reason_code).label}</span>
                      </div>
                      {result.handoff?.summary ? (
                        <div className="flex items-start justify-between gap-3 px-3 py-2">
                          <span className="text-ink-3 shrink-0">Context</span>
                          <span className="text-right text-ink">{result.handoff.summary}</span>
                        </div>
                      ) : null}
                      <div className="flex items-start justify-between gap-3 px-3 py-2">
                        <span className="text-ink-3 shrink-0">Evidence</span>
                        <span className="text-right text-ink">{result.evidence.items.length} historical case{result.evidence.items.length === 1 ? "" : "s"} reviewed</span>
                      </div>
                      <div className="flex items-start justify-between gap-3 px-3 py-2">
                        <span className="text-ink-3 shrink-0">Next action</span>
                        <span className="text-right font-medium text-ink">{result.handoff?.recommended_next_action ?? result.outcome.next_step}</span>
                      </div>
                    </div>

                    {/* Why this decision? */}
                    <div className="rounded-md border border-line bg-canvas/60 px-3 py-2.5 text-xs">
                      <div className="font-semibold uppercase tracking-wider text-ink-3">Why this decision?</div>
                      <p className="mt-1 leading-relaxed text-ink-2">
                        ResolveAI detected a safety, security, or account boundary that requires human review. Automated responses are withheld to protect customers.
                      </p>
                    </div>

                    {/* CTAs */}
                    <div className="flex flex-wrap items-center gap-2 pt-1">
                      <ButtonLink href={`/handoffs/${result.trace_id}`} variant="primary" size="sm">
                        Open handoff
                      </ButtonLink>
                      <ButtonLink href={`/conversations/${result.trace_id}`} variant="secondary" size="sm">
                        Open conversation
                      </ButtonLink>
                    </div>
                  </div>
                )}
              </div>
            ) : null}
          </div>
        </Card>
      </div>

      {/* PROGRESSIVE DISCLOSURE: Advanced testing */}
      <Card title="Advanced testing" headingLevel={2}>
        <p className="text-[13px] text-ink-3">
          Developer tools, API scenario execution, deterministic benchmark fixtures, and full pipeline execution timelines.
        </p>
        <Advanced label="Show API demo scenarios, pipeline stages, and audit traces">
          <div className="space-y-6 pt-3">
            {/* Simulation notice */}
            <Notice tone="warning" title="Simulation">
              Messages are processed by your local ResolveAI API{model ? ` (model ${model})` : ""}. Nothing is sent to any customer or channel. Results are kept in this browser only (last 50) so you can reopen them;
              audit traces on the API never store message text.
            </Notice>

            {/* Expected versus actual comparison (when run from scenario) */}
            {state.kind === "done" && state.scenario ? (
              <ul className="flex w-full flex-wrap gap-x-4 gap-y-1 rounded-md border border-line bg-canvas p-3 text-xs" aria-label="Expected versus actual">
                <li className="font-semibold text-ink">Expected versus actual:</li>
                {checkExpectation(state.scenario, state.stored.result).map((c) => (
                  <li key={c.label} className={`inline-flex items-center gap-1 ${c.ok ? "text-success font-medium" : "text-warning font-medium"}`}>
                    {c.ok ? <CircleCheck className="size-3.5" aria-hidden="true" /> : <CircleX className="size-3.5" aria-hidden="true" />}
                    {c.label}
                    <span className="sr-only">{c.ok ? " (matches)" : " (differs)"}</span>
                  </li>
                ))}
              </ul>
            ) : null}

            {/* Pipeline Stepper (when run) */}
            {state.kind === "done" ? (
              <PipelineStepper result={state.stored.result} trace={state.trace} />
            ) : null}

            {/* Full Conversation Workspace (when run) */}
            {state.kind === "done" ? (
              <ConversationWorkspace result={state.stored.result} trace={state.trace} savedAt={state.stored.savedAt} source={state.stored.source} />
            ) : null}

            {/* Curated demo path (7 items) */}
            <div>
              <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-ink">Curated demo path</h3>
              <ol aria-label="Curated demo path" className="grid gap-2.5 md:grid-cols-2 2xl:grid-cols-4">
                {CURATED.map((c) => {
                  const scenario = c.api ? (scenarios?.find((s) => s.id === c.api) ?? null) : null;
                  return <CuratedCard key={c.n} item={c} scenario={scenario} busy={busy} onRun={(conversation) => void run(conversation, `Curated ${c.n}: ${c.title}`, scenario)} />;
                })}
              </ol>
            </div>

            {/* All API demo scenarios */}
            <div>
              <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-ink">All API demo scenarios</h3>
              {scenariosError ? (
                <ErrorState error={scenariosError} compact />
              ) : scenarios && scenarios.length ? (
                <ul className="grid gap-2.5 md:grid-cols-2">
                  {scenarios.map((s) => (
                    <ScenarioCard key={s.id} scenario={s} busy={busy} onLoad={() => loadScenario(s)} onRun={() => void run(s.conversation, `Scenario ${s.id}: ${s.title}`, s)} />
                  ))}
                </ul>
              ) : (
                <EmptyState title="No demo scenarios available" />
              )}
            </div>

            {/* Stored results count */}
            {stored.length ? (
              <p className="flex flex-wrap items-center gap-2 border-t border-line pt-3 text-xs text-ink-3">
                {stored.length} result{stored.length === 1 ? "" : "s"} stored in this browser.
                <button type="button" onClick={clearResults} className="font-medium text-ink-2 underline hover:text-ink">
                  Clear stored results
                </button>
              </p>
            ) : null}
          </div>
        </Advanced>
      </Card>
    </div>
  );
}
