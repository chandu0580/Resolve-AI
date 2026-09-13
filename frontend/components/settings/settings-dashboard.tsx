"use client";

import { useState } from "react";
import Link from "next/link";
import {
  Bot,
  CheckCircle2,
  ExternalLink,
  Globe,
  Inbox,
  Lock,
  MessageSquare,
  ShieldCheck,
  UserCheck,
  ChevronDown,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, KeyValues, Mono, Notice } from "@/components/ui/card";
import { BrowserStorageCard } from "@/components/settings/browser-storage";
import { CONSOLE_VERSION } from "@/lib/version";
import type { HealthResponse, KnowledgeSummary, RuntimeConfig } from "@/lib/api/types";

interface SettingsDashboardProps {
  config: RuntimeConfig | null;
  health: HealthResponse | null;
  knowledge: KnowledgeSummary | null;
  tokenPresent: boolean;
}

const LIMITATIONS = [
  "No user sign-in, roles or per-operator audit: the console authenticates to the API with one server-side token.",
  "Rate limits and the request queue are process-local; several API instances would not share them.",
  "Traces are local JSONL files, not a managed, access-controlled store.",
  "This is a local reference environment. It has not been deployed or load-tested as a production service.",
];

export function SettingsDashboard({ config, health, knowledge, tokenPresent }: SettingsDashboardProps) {
  const [agentStatus, setAgentStatus] = useState<"online" | "paused">("online");
  const [defaultBehavior, setDefaultBehavior] = useState<"auto" | "review">("auto");

  const s = config?.service;
  const brand = config?.brand ?? "Apple Support";
  const datasetRows = knowledge?.rows ? `${knowledge.rows.toLocaleString()} verified support cases` : "Verified resolution corpus active";

  return (
    <div className="space-y-6">
      {/* 1. AI Agent Section */}
      <section aria-labelledby="section-agent">
        <div className="mb-3 flex items-center gap-2">
          <Bot className="size-4 text-brand-700" aria-hidden="true" />
          <h2 id="section-agent" className="text-sm font-semibold text-ink">
            AI Agent
          </h2>
        </div>
        <Card>
          <div className="space-y-5">
            {/* Agent Status */}
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between border-b border-line pb-4">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-ink">Agent status</span>
                  <span className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium ${
                    agentStatus === "online" ? "bg-emerald-50 text-emerald-800 border border-emerald-200" : "bg-neutral-100 text-neutral-600 border border-neutral-200"
                  }`}>
                    <span className={`size-1.5 rounded-full ${agentStatus === "online" ? "bg-emerald-600 animate-pulse" : "bg-neutral-400"}`} />
                    {agentStatus === "online" ? "Online" : "Paused"}
                  </span>
                </div>
                <p className="mt-0.5 text-xs text-ink-3">
                  Controls whether ResolveAI actively evaluates incoming customer inquiries.
                </p>
              </div>
              <div className="inline-flex rounded-md border border-line bg-canvas p-0.5 text-xs">
                <button
                  type="button"
                  onClick={() => setAgentStatus("online")}
                  className={`rounded px-2.5 py-1 font-medium transition-colors ${
                    agentStatus === "online"
                      ? "bg-surface text-ink shadow-xs"
                      : "text-ink-3 hover:text-ink"
                  }`}
                  aria-pressed={agentStatus === "online"}
                >
                  Online
                </button>
                <button
                  type="button"
                  onClick={() => setAgentStatus("paused")}
                  className={`rounded px-2.5 py-1 font-medium transition-colors ${
                    agentStatus === "paused"
                      ? "bg-surface text-ink shadow-xs"
                      : "text-ink-3 hover:text-ink"
                  }`}
                  aria-pressed={agentStatus === "paused"}
                >
                  Paused
                </button>
              </div>
            </div>

            {/* Default Behavior */}
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between border-b border-line pb-4">
              <div>
                <span className="text-sm font-medium text-ink">Default behavior</span>
                <p className="mt-0.5 text-xs text-ink-3">
                  Determines how verified recommendations are dispatched to customers.
                </p>
              </div>
              <div className="inline-flex rounded-md border border-line bg-canvas p-0.5 text-xs">
                <button
                  type="button"
                  onClick={() => setDefaultBehavior("auto")}
                  className={`rounded px-2.5 py-1 font-medium transition-colors ${
                    defaultBehavior === "auto"
                      ? "bg-surface text-ink shadow-xs"
                      : "text-ink-3 hover:text-ink"
                  }`}
                  aria-pressed={defaultBehavior === "auto"}
                >
                  Resolve automatically
                </button>
                <button
                  type="button"
                  onClick={() => setDefaultBehavior("review")}
                  className={`rounded px-2.5 py-1 font-medium transition-colors ${
                    defaultBehavior === "review"
                      ? "bg-surface text-ink shadow-xs"
                      : "text-ink-3 hover:text-ink"
                  }`}
                  aria-pressed={defaultBehavior === "review"}
                >
                  Ask before resolving
                </button>
              </div>
            </div>

            {/* Human Handoff Rules */}
            <div>
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-ink">Human handoff</span>
                <Badge tone="success">Enabled</Badge>
              </div>
              <p className="mt-1 text-xs text-ink-3">
                ResolveAI automatically transfers the conversation to human support when:
              </p>
              <ul className="mt-2.5 grid gap-2 sm:grid-cols-2 text-xs text-ink-2">
                <li className="flex items-center gap-2 rounded-md border border-line bg-canvas/60 px-2.5 py-1.5">
                  <CheckCircle2 className="size-3.5 text-brand-600 shrink-0" aria-hidden="true" />
                  <span>Customer asks for a human</span>
                </li>
                <li className="flex items-center gap-2 rounded-md border border-line bg-canvas/60 px-2.5 py-1.5">
                  <CheckCircle2 className="size-3.5 text-brand-600 shrink-0" aria-hidden="true" />
                  <span>Safety or security concern</span>
                </li>
                <li className="flex items-center gap-2 rounded-md border border-line bg-canvas/60 px-2.5 py-1.5">
                  <CheckCircle2 className="size-3.5 text-brand-600 shrink-0" aria-hidden="true" />
                  <span>No verified answer in knowledge</span>
                </li>
                <li className="flex items-center gap-2 rounded-md border border-line bg-canvas/60 px-2.5 py-1.5">
                  <CheckCircle2 className="size-3.5 text-brand-600 shrink-0" aria-hidden="true" />
                  <span>Repeated unresolved conversation</span>
                </li>
              </ul>
            </div>
          </div>
        </Card>
      </section>

      {/* 2. Support Channels & 3. Knowledge Base */}
      <div className="grid gap-6 md:grid-cols-2">
        {/* Support Channels */}
        <section aria-labelledby="section-channels">
          <div className="mb-3 flex items-center gap-2">
            <Globe className="size-4 text-brand-700" aria-hidden="true" />
            <h2 id="section-channels" className="text-sm font-semibold text-ink">
              Support Channels
            </h2>
          </div>
          <Card>
            <div className="space-y-4">
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <MessageSquare className="size-4 text-brand-600" aria-hidden="true" />
                    <span className="text-sm font-medium text-ink">Web chat</span>
                  </div>
                  <p className="mt-1 text-xs text-ink-3">
                    Customer chat interface running on your web portal.
                  </p>
                </div>
                <Badge tone="success">Connected</Badge>
              </div>

              <div className="rounded-md border border-line bg-canvas/60 p-2.5 text-xs text-ink-2">
                <span className="font-medium text-ink">Active channel:</span> Web customer widget
                <div className="mt-1">
                  <Link href="/chat" className="inline-flex items-center gap-1 font-medium text-brand-700 hover:underline">
                    Open customer chat <ExternalLink className="size-3" aria-hidden="true" />
                  </Link>
                </div>
              </div>

              <p className="text-[11px] text-ink-3">
                Live conversations route directly into your Conversations inbox.
              </p>
            </div>
          </Card>
        </section>

        {/* Knowledge Base */}
        <section aria-labelledby="section-knowledge">
          <div className="mb-3 flex items-center gap-2">
            <ShieldCheck className="size-4 text-brand-700" aria-hidden="true" />
            <h2 id="section-knowledge" className="text-sm font-semibold text-ink">
              Knowledge
            </h2>
          </div>
          <Card>
            <div className="space-y-4">
              <div>
                <div className="text-xs font-semibold text-ink-3 uppercase tracking-wider">
                  Knowledge sources
                </div>
                <div className="mt-1 text-sm font-medium text-ink">
                  {knowledge?.dataset ?? "Resolution corpus"}
                </div>
                <div className="mt-0.5 text-xs text-ink-2">{datasetRows}</div>
              </div>

              <div>
                <div className="text-xs font-semibold text-ink-3 uppercase tracking-wider">
                  Last updated
                </div>
                <div className="mt-1 text-xs text-ink-2">
                  {knowledge?.date_range?.max ? `Corpus active · verified through ${knowledge.date_range.max}` : "Current release verified"}
                </div>
              </div>

              <div className="pt-1">
                <Link
                  href="/knowledge"
                  className="inline-flex items-center gap-1.5 text-xs font-semibold text-brand-700 hover:underline"
                >
                  Manage knowledge →
                </Link>
              </div>
            </div>
          </Card>
        </section>
      </div>

      {/* 4. Human Handoff & 5. Workspace */}
      <div className="grid gap-6 md:grid-cols-2">
        {/* Human Handoff */}
        <section aria-labelledby="section-handoff">
          <div className="mb-3 flex items-center gap-2">
            <UserCheck className="size-4 text-brand-700" aria-hidden="true" />
            <h2 id="section-handoff" className="text-sm font-semibold text-ink">
              Human Handoff
            </h2>
          </div>
          <Card>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-ink">Human handoff</span>
                <Badge tone="success">Enabled</Badge>
              </div>
              <p className="text-xs text-ink-3">
                Escalated conversations are packaged with structured summaries and sent to human agents.
              </p>
              <div className="rounded-md border border-line bg-canvas/60 p-2.5 text-xs">
                <span className="font-medium text-ink">Handoff destination:</span> Primary Support Queue
                <div className="mt-1 text-ink-3">
                  Structured handoff packet includes reason, customer intent, evidence retrieved, and recommended next step.
                </div>
              </div>
              <div className="pt-1">
                <Link
                  href="/handoffs"
                  className="inline-flex items-center gap-1.5 text-xs font-semibold text-brand-700 hover:underline"
                >
                  View handoffs queue →
                </Link>
              </div>
            </div>
          </Card>
        </section>

        {/* Workspace */}
        <section aria-labelledby="section-workspace">
          <div className="mb-3 flex items-center gap-2">
            <Inbox className="size-4 text-brand-700" aria-hidden="true" />
            <h2 id="section-workspace" className="text-sm font-semibold text-ink">
              Workspace
            </h2>
          </div>
          <Card>
            <div className="space-y-3.5">
              <div>
                <div className="text-xs font-semibold text-ink-3 uppercase tracking-wider">
                  Support brand
                </div>
                <div className="mt-1 text-sm font-medium text-ink">{brand}</div>
              </div>

              <div>
                <div className="text-xs font-semibold text-ink-3 uppercase tracking-wider">
                  Current environment
                </div>
                <div className="mt-1 flex items-center gap-2">
                  <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-800 border border-amber-200">
                    <span className="size-1.5 rounded-full bg-amber-600" />
                    {s?.env ? `${s.env} profile` : "Development / Demonstration"}
                  </span>
                </div>
                <p className="mt-1 text-[11px] text-ink-3">
                  Local operational environment with deterministic evaluation fallbacks.
                </p>
              </div>
            </div>
          </Card>
        </section>
      </div>

      {/* 6. Advanced Technical Details (Collapsed by default) */}
      <section aria-labelledby="section-advanced" className="pt-2">
        <details className="group rounded-lg border border-line bg-surface p-4 transition-all">
          <summary className="flex cursor-pointer items-center justify-between text-sm font-semibold text-ink select-none">
            <div className="flex items-center gap-2">
              <span>Advanced</span>
              <span className="text-xs font-normal text-ink-3">Runtime diagnostics, limits and server configuration</span>
            </div>
            <ChevronDown className="size-4 text-ink-3 transition-transform group-open:rotate-180" aria-hidden="true" />
          </summary>

          <div className="mt-5 space-y-6 border-t border-line pt-5">
            <div className="mb-2">
              <Notice tone="info" icon={Lock} title="Server Configuration">
                Tokens, API keys and endpoint addresses remain safely stored on the server.
              </Notice>
            </div>

            <div className="grid items-start gap-4 xl:grid-cols-2">
              {/* Connection & Auth */}
              <Card title="Connection and authentication">
                <KeyValues
                  items={[
                    {
                      label: "API",
                      value: health ? `Reachable · v${health.version}` : "Unreachable",
                      hint: "Configured on the server via RESOLVEAI_API_URL.",
                    },
                    { label: "API environment", value: s?.env ?? "n/a" },
                    {
                      label: "API authentication",
                      value: s?.auth ? (
                        s.auth.required ? (
                          <Badge tone="success">Required ({s.auth.scheme})</Badge>
                        ) : (
                          <Badge tone="warning">Not required in this profile</Badge>
                        )
                      ) : "n/a",
                    },
                    {
                      label: "Console server token",
                      value: tokenPresent ? <Badge tone="success">Configured</Badge> : <Badge tone="neutral">Not set</Badge>,
                    },
                    { label: "Console version", value: <Mono>{CONSOLE_VERSION}</Mono> },
                    { label: "API docs endpoint", value: s ? (s.docs_enabled ? "Enabled" : "Disabled") : "n/a" },
                  ]}
                />
              </Card>

              {/* Limits and budgets */}
              <Card title="Limits and budgets">
                <KeyValues
                  items={
                    s
                      ? [
                          { label: "Customer message", value: `${s.limits.max_message_chars} characters` },
                          { label: "Conversation", value: `${s.limits.max_turns} turns · ${s.limits.max_total_chars} characters in total` },
                          { label: "Request body", value: `${s.limits.max_body_bytes} bytes` },
                          { label: "Agent runs", value: `${s.rate_limit_per_minute} per minute per ${s.rate_limit_scope ?? "client"}` },
                          { label: "Reads", value: s.read_rate_limit_per_minute ? `${s.read_rate_limit_per_minute} per minute` : "n/a" },
                          { label: "Queue", value: `${s.max_queue} waiting${s.queue_timeout_s ? ` · ${s.queue_timeout_s} s wait limit` : ""}` },
                          { label: "Request time budget", value: s.request_budget_s ? `${s.request_budget_s} s` : "none" },
                        ]
                      : [{ label: "Limits", value: "Unavailable: the API could not be reached" }]
                  }
                />
              </Card>

              {/* Model and traces */}
              <Card title="Model and traces">
                <KeyValues
                  items={
                    config
                      ? [
                          {
                            label: "Model",
                            value: <Mono>{config.llm.model}</Mono>,
                            hint: `${config.llm.provider} provider · credential ${config.llm.configured ? "configured" : "not configured"}`,
                          },
                          { label: "Model calls", value: config.llm.enabled ? "Enabled" : "Disabled (deterministic fallbacks only)" },
                          { label: "Timeout and retries", value: `${config.llm.timeout_s} s · ${config.llm.max_retries} retries · temperature ${config.llm.temperature}` },
                          { label: "Embedding model", value: <Mono>{config.embedding_model}</Mono> },
                          { label: "Audit traces", value: s?.write_traces ? `Written (${s.trace_store.kind} store)` : "Not written in this profile" },
                        ]
                      : [{ label: "Model", value: "Unavailable: the API could not be reached" }]
                  }
                />
              </Card>

              {/* Browser storage */}
              <BrowserStorageCard />

              {/* Known limitations */}
              <Card title="Known limitations" className="xl:col-span-2">
                <ul className="list-disc space-y-1 pl-5 text-[13px] text-ink-2">
                  {LIMITATIONS.map((l) => (
                    <li key={l}>{l}</li>
                  ))}
                </ul>
              </Card>
            </div>
          </div>
        </details>
      </section>
    </div>
  );
}
