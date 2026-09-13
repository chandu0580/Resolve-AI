import { Activity, Cpu, EyeOff, Gauge, KeyRound, ListChecks, Scale, ShieldAlert, UserRound, Workflow } from "lucide-react";
import Link from "next/link";
import type { ElementType } from "react";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import type { RuntimeConfig } from "@/lib/api/types";
import type { Tone } from "@/lib/labels";

export interface TrustControl {
  key: string;
  title: string;
  icon: ElementType;
  status: { label: string; tone: Tone };
  enforcedAt: string;
  protectsAgainst: string;
  details: string[];
  code: string[];
  tests: string[];
  seeIt?: { label: string; href: string };
}

const ENFORCED = { label: "Enforced", tone: "success" as Tone };
const UNKNOWN = { label: "Status unknown: API unreachable", tone: "neutral" as Tone };

/** Implementation controls of this reference implementation. Status comes from the running API's safe configuration (/api/v1/config). */
export function trustControls(config: RuntimeConfig | null): TrustControl[] {
  const v = config?.versions;
  const llm = config?.llm;
  const s = config?.service;
  const limits = s?.limits;
  const known = (ok: boolean, off: string) => (!config ? UNKNOWN : ok ? ENFORCED : { label: off, tone: "warning" as Tone });
  return [
    {
      key: "pii",
      title: "PII protection",
      icon: EyeOff,
      status: config ? ENFORCED : UNKNOWN,
      enforcedAt: "Before any model call, trace or log: the first pipeline stage, and again inside the model client.",
      protectsAgainst: "Personal data reaching a model provider, the audit trail, logs or a generated reply.",
      details: [
        "Emails, phone numbers, card and order numbers and long identifiers become placeholders such as <EMAIL>.",
        "The model client refuses to send text that still contains unredacted personal data.",
        "Traces record only how many items were redacted; the copied handoff summary is scrubbed again in the browser.",
      ],
      code: ["resolveai/trust/pii.py", "resolveai/llm/provider.py"],
      tests: ["tests/test_phase9_pii.py", "tests/test_security.py"],
    },
    {
      key: "injection",
      title: "Prompt-injection defense",
      icon: ShieldAlert,
      status: config ? ENFORCED : UNKNOWN,
      enforcedAt: "Injection check on every turn before intent; the prompt_injection policy rule; the request schema.",
      protectsAgainst: "Customer text acting as instructions, supplying its own evidence or overriding policy.",
      details: [
        "A detected attempt hands off under the prompt_injection rule; the text is treated as data.",
        "The request schema rejects any evidence, policy or system field. Instruction-like evidence text is quarantined.",
      ],
      code: ["resolveai/trust/injection.py", "resolveai/api/schemas.py"],
      tests: ["tests/test_phase9_adversarial.py", "tests/test_final_adversarial_suite.py", "tests/test_trust_phase7.py"],
    },
    {
      key: "evidence",
      title: `Evidence requirement${v ? ` (${v.evidence_gate})` : ""}`,
      icon: Scale,
      status: config ? ENFORCED : UNKNOWN,
      enforcedAt: "Evidence gate after retrieval; the policy's evidence_gate rule; the output gate's evidence check.",
      protectsAgainst: "Automatic replies that no historical resolution supports.",
      details: [
        "Evidence is graded INSUFFICIENT, WEAK, SUFFICIENT or STRONG; only SUFFICIENT or STRONG can support an automatic reply.",
        "Only cases written before the customer's message count, and a customer's own earlier thread is never independent support.",
      ],
      code: ["resolveai/retrieval/resolution.py", "resolveai/policy/escalation.py"],
      tests: ["tests/test_resolution.py", "tests/test_agent_phase5.py"],
      seeIt: { label: "Knowledge Center", href: "/knowledge" },
    },
    {
      key: "policy",
      title: `Policy enforcement${v ? ` (${v.policy})` : ""}`,
      icon: Workflow,
      status: config ? ENFORCED : UNKNOWN,
      enforcedAt: "Deterministic, ordered rules after risk assessment; the API re-checks the autonomy invariant before responding.",
      protectsAgainst: "A model deciding escalation; safety, security, legal, billing or account cases answered automatically.",
      details: ["The first matching rule wins and is recorded in the trace.", "The model can only add risk flags, which can only move a decision towards a human."],
      code: ["resolveai/policy/escalation.py", "resolveai/api/presenter.py"],
      tests: ["tests/test_policy_and_trace.py", "tests/test_product_api.py"],
      seeIt: { label: "Ordered rules on the Agents page", href: "/agents" },
    },
    {
      key: "verification",
      title: `Output verification${v?.prompts?.verify ? ` (${v.prompts.verify})` : ""}`,
      icon: ListChecks,
      status: known(Boolean(llm?.enabled), "Model off: no drafts, so only fixed templates can auto-reply"),
      enforcedAt: `After drafting: deterministic checks, a model support check, then the output gate${v ? ` (${v.output_gate})` : ""}.`,
      protectsAgainst: "Replies with steps not in the cited evidence, invented promises, URLs, handles or personal data.",
      details: ["A failed check gets one corrective redraft; a second failure becomes a handoff that keeps the rejected draft for the human."],
      code: ["resolveai/agent/verifier.py", "resolveai/agent/gate.py"],
      tests: ["tests/test_agent.py", "tests/test_api.py"],
    },
    {
      key: "handoff",
      title: "Human handoff",
      icon: UserRound,
      status: config ? ENFORCED : UNKNOWN,
      enforcedAt: "Every path that is not a verified, evidence-backed reply or a clarifiable gap ends in a handoff packet.",
      protectsAgainst: "Customers receiving an unsafe or unsupported answer, and humans receiving a case without context.",
      details: ["The packet carries the reason, risk flags, evidence found and missing, unresolved questions and a recommended next action."],
      code: ["resolveai/agent/handoff.py"],
      tests: ["tests/test_agent.py"],
      seeIt: { label: "Handoff Center", href: "/handoffs" },
    },
    {
      key: "audit",
      title: "Audit traces",
      icon: Activity,
      status: known(Boolean(s?.write_traces), "Disabled in this profile"),
      enforcedAt: `Written for every execution${s ? ` to the ${s.trace_store.kind} trace store` : ""}; ids returned in X-Request-ID and X-Trace-ID.`,
      protectsAgainst: "Decisions that cannot be reviewed or reproduced later.",
      details: ["Traces record versions, config hash, stage statuses, latencies and decision data, never customer text, secrets or model reasoning.", "A corrupted trace line is skipped and counted, not served."],
      code: ["resolveai/observability/trace.py", "resolveai/api/service.py"],
      tests: ["tests/test_policy_and_trace.py", "tests/test_trace_store_corruption.py"],
      seeIt: { label: "Trace Explorer", href: "/traces" },
    },
    {
      key: "auth",
      title: "Authentication",
      icon: KeyRound,
      status: known(Boolean(s?.auth?.required), "Not required in this profile"),
      enforcedAt: "API middleware before any request body is read: bearer tokens with resolve and read scopes. The console attaches its token server-side.",
      protectsAgainst: "Unauthenticated use of the agent and the audit trail, and API tokens reaching the browser.",
      details: ["Missing and invalid credentials get the same 401. Failed attempts are rate limited per client address.", "There is no user sign-in or role model in this console."],
      code: ["resolveai/api/auth.py", "resolveai/api/access.py"],
      tests: ["tests/test_phase9_api_security.py"],
      seeIt: { label: "Settings", href: "/settings" },
    },
    {
      key: "limits",
      title: "Rate limiting and input limits",
      icon: Gauge,
      status: config ? ENFORCED : UNKNOWN,
      enforcedAt: "API middleware and route guards, before the agent runs.",
      protectsAgainst: "Abuse, runaway model cost and oversized inputs.",
      details: [
        s ? `${s.rate_limit_per_minute} agent runs and ${s.read_rate_limit_per_minute ?? "n/a"} reads per minute per ${s.rate_limit_scope ?? "client"}; at most ${s.max_queue} waiting.` : "Requests are rate limited per client.",
        limits ? `Customer message up to ${limits.max_message_chars} characters, ${limits.max_turns} turns, ${limits.max_total_chars} characters in total.` : "Message length, turn count and total size are limited.",
        "Limiters are process-local: they are not shared across several API instances.",
      ],
      code: ["resolveai/api/guards.py", "resolveai/api/access.py", "resolveai/api/routes.py"],
      tests: ["tests/test_phase9_api_security.py", "tests/test_api.py"],
    },
    {
      key: "model-failure",
      title: "Model-failure handling",
      icon: Cpu,
      status: config ? ENFORCED : UNKNOWN,
      enforcedAt: `Model client and orchestrator: timeouts${llm ? ` of ${llm.timeout_s} s with ${llm.max_retries} retr${llm.max_retries === 1 ? "y" : "ies"}` : ""}, a per-request time budget, deterministic fallbacks.`,
      protectsAgainst: "A model outage or timeout producing an error, a hang or an unverified reply.",
      details: ["An unavailable model becomes a safe handoff (llm_unavailable), not an HTTP error. Readiness checks never call the model."],
      code: ["resolveai/llm/provider.py", "resolveai/agent/orchestrator.py"],
      tests: ["tests/test_phase9_reliability.py"],
    },
  ];
}

export const CONTROLS_DISCLAIMER = "These are implementation controls in this reference implementation, with the tests that exercise them. They are not certifications or compliance attestations.";

function Paths({ paths }: { paths: string[] }) {
  return (
    <>
      {paths.map((p, i) => (
        <span key={p}>
          {i ? ", " : ""}
          <code className="font-mono text-[11px] break-all text-ink-2">{p}</code>
        </span>
      ))}
    </>
  );
}

export function TrustControlsGrid({ config }: { config: RuntimeConfig | null }) {
  return (
    <ul className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
      {trustControls(config).map((c) => {
        const Icon = c.icon;
        return (
          <li key={c.key} className="flex min-w-0 flex-col rounded-lg border border-line bg-surface p-4">
            <div className="flex flex-wrap items-center gap-2.5">
              <span className="flex size-8 shrink-0 items-center justify-center rounded-md bg-brand-50 text-brand-700">
                <Icon className="size-4" aria-hidden="true" />
              </span>
              <h2 className="text-sm font-semibold text-ink">{c.title}</h2>
            </div>
            <dl className="mt-3 grid gap-2 text-[13px]">
              <div>
                <dt className="text-[11px] font-semibold tracking-wide text-ink-3 uppercase">Status</dt>
                <dd className="mt-0.5">
                  <Badge tone={c.status.tone}>{c.status.label}</Badge>
                </dd>
              </div>
              <div>
                <dt className="text-[11px] font-semibold tracking-wide text-ink-3 uppercase">Enforced at</dt>
                <dd className="mt-0.5 text-ink">{c.enforcedAt}</dd>
              </div>
              <div>
                <dt className="text-[11px] font-semibold tracking-wide text-ink-3 uppercase">What it protects against</dt>
                <dd className="mt-0.5 text-ink">{c.protectsAgainst}</dd>
              </div>
            </dl>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-ink-2">
              {c.details.map((d) => (
                <li key={d}>{d}</li>
              ))}
            </ul>
            <div className="mt-auto space-y-0.5 pt-3 text-xs text-ink-3">
              <div>
                Code: <Paths paths={c.code} />
              </div>
              <div>
                Tests: <Paths paths={c.tests} />
              </div>
              {c.seeIt ? (
                <Link href={c.seeIt.href} className="font-medium text-brand-700 hover:underline">
                  {c.seeIt.label}
                </Link>
              ) : null}
            </div>
          </li>
        );
      })}
    </ul>
  );
}

export function TrustSummary({ config }: { config: RuntimeConfig | null }) {
  return (
    <Card
      title="Trust & Safety"
      description="Controls that keep automation safe, and their status in this environment."
      actions={
        <Link href="/trust" className="text-xs font-medium text-brand-700 hover:underline">
          All controls
        </Link>
      }
    >
      <ul className="space-y-2.5">
        {trustControls(config).map((c) => {
          const Icon = c.icon;
          return (
            <li key={c.key} className="flex gap-2.5">
              <Icon className="mt-0.5 size-4 shrink-0 text-brand-600" aria-hidden="true" />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center justify-between gap-x-2 gap-y-0.5">
                  <span className="text-[13px] font-medium text-ink">{c.title}</span>
                  <Badge tone={c.status.tone}>{c.status.label}</Badge>
                </div>
                <div className="text-xs text-ink-3">{c.protectsAgainst}</div>
              </div>
            </li>
          );
        })}
      </ul>
      <p className="mt-3 text-[11px] text-ink-3">{CONTROLS_DISCLAIMER}</p>
    </Card>
  );
}
