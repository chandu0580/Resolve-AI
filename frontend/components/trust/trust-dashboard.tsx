"use client";

import Link from "next/link";
import {
  ChevronDown,
  EyeOff,
  FileCheck2,
  RotateCcw,
  Scale,
  Shield,
  ShieldAlert,
  ShieldCheck,
  UserCheck,
  UserRound,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, KeyValues } from "@/components/ui/card";
import { trustControls } from "@/components/trust/trust-controls";
import type { ReleaseEvaluation, RuntimeConfig } from "@/lib/api/types";

interface TrustDashboardProps {
  config: RuntimeConfig | null;
  release: ReleaseEvaluation | null;
}

const passBadge = (passed: number, total: number) => (
  <Badge tone={passed === total ? "success" : "danger"}>{`${passed} of ${total} passed`}</Badge>
);

export function TrustDashboard({ config, release }: TrustDashboardProps) {
  const checks = release?.checks;
  const controls = trustControls(config);

  return (
    <div className="space-y-6">
      {/* Trust Summary Banner */}
      <section aria-label="Trust summary" className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <div className="rounded-lg border border-line bg-surface p-3.5">
          <div className="flex items-center gap-2">
            <span className="flex size-6 shrink-0 items-center justify-center rounded-md bg-emerald-50 text-emerald-700">
              <ShieldCheck className="size-4" aria-hidden="true" />
            </span>
            <span className="text-xs font-semibold uppercase tracking-wider text-ink-3">AI safety</span>
          </div>
          <div className="mt-2 text-lg font-semibold text-ink">Protected</div>
          <div className="text-xs text-ink-3">6 safeguards active</div>
        </div>

        <div className="rounded-lg border border-line bg-surface p-3.5">
          <div className="flex items-center gap-2">
            <span className="flex size-6 shrink-0 items-center justify-center rounded-md bg-brand-50 text-brand-700">
              <Scale className="size-4" aria-hidden="true" />
            </span>
            <span className="text-xs font-semibold uppercase tracking-wider text-ink-3">Automatic replies</span>
          </div>
          <div className="mt-2 text-lg font-semibold text-ink">Evidence required</div>
          <div className="text-xs text-ink-3">Verified answers only</div>
        </div>

        <div className="rounded-lg border border-line bg-surface p-3.5">
          <div className="flex items-center gap-2">
            <span className="flex size-6 shrink-0 items-center justify-center rounded-md bg-amber-50 text-amber-800">
              <UserCheck className="size-4" aria-hidden="true" />
            </span>
            <span className="text-xs font-semibold uppercase tracking-wider text-ink-3">Human oversight</span>
          </div>
          <div className="mt-2 text-lg font-semibold text-ink">Always available</div>
          <div className="text-xs text-ink-3">Safe fallback on uncertainty</div>
        </div>
      </section>

      {/* Primary Trust Controls Grid (6 Clean Enterprise Safeguards) */}
      <section aria-labelledby="primary-safeguards">
        <h2 id="primary-safeguards" className="sr-only">
          Active Safeguards
        </h2>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {/* 1. Human handoff */}
          <div className="flex flex-col justify-between rounded-lg border border-line bg-surface p-4">
            <div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="flex size-7 items-center justify-center rounded-md bg-brand-50 text-brand-700">
                    <UserRound className="size-4" aria-hidden="true" />
                  </span>
                  <h3 className="text-sm font-semibold text-ink">Human handoff</h3>
                </div>
                <Badge tone="success">ENABLED</Badge>
              </div>
              <p className="mt-3 text-xs leading-relaxed text-ink-2">
                ResolveAI hands conversations to a human when the request is unsafe, unresolved, or requires human judgment.
              </p>
              <div className="mt-3.5 border-t border-line/60 pt-3">
                <div className="text-[11px] font-semibold tracking-wide text-ink-3 uppercase">Handoff triggers</div>
                <ul className="mt-1.5 space-y-1 text-xs text-ink-2">
                  <li className="flex items-center gap-1.5">
                    <span className="size-1 rounded-full bg-brand-600" />
                    Customer requests a human
                  </li>
                  <li className="flex items-center gap-1.5">
                    <span className="size-1 rounded-full bg-brand-600" />
                    Sensitive / high-risk request
                  </li>
                  <li className="flex items-center gap-1.5">
                    <span className="size-1 rounded-full bg-brand-600" />
                    No verified resolution
                  </li>
                  <li className="flex items-center gap-1.5">
                    <span className="size-1 rounded-full bg-brand-600" />
                    Repeated unresolved interaction
                  </li>
                </ul>
              </div>
            </div>
            <div className="mt-4 pt-2">
              <Link href="/handoffs" className="text-xs font-semibold text-brand-700 hover:underline">
                Handoff Center →
              </Link>
            </div>
          </div>

          {/* 2. Grounded responses */}
          <div className="flex flex-col justify-between rounded-lg border border-line bg-surface p-4">
            <div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="flex size-7 items-center justify-center rounded-md bg-brand-50 text-brand-700">
                    <Scale className="size-4" aria-hidden="true" />
                  </span>
                  <h3 className="text-sm font-semibold text-ink">Grounded responses</h3>
                </div>
                <Badge tone="success">ENFORCED</Badge>
              </div>
              <p className="mt-3 text-xs leading-relaxed text-ink-2">
                ResolveAI only sends an automatic answer when it has sufficient verified support evidence.
              </p>
              <div className="mt-3.5 rounded-md border border-line bg-canvas/60 p-2.5 text-xs text-ink-2">
                <span className="font-medium text-ink">Core policy rule:</span> Automatic replies require verified support evidence.
              </div>
            </div>
            <div className="mt-4 pt-2">
              <Link href="/knowledge" className="text-xs font-semibold text-brand-700 hover:underline">
                Knowledge Base →
              </Link>
            </div>
          </div>

          {/* 3. Privacy protection */}
          <div className="flex flex-col justify-between rounded-lg border border-line bg-surface p-4">
            <div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="flex size-7 items-center justify-center rounded-md bg-brand-50 text-brand-700">
                    <EyeOff className="size-4" aria-hidden="true" />
                  </span>
                  <h3 className="text-sm font-semibold text-ink">Privacy protection</h3>
                </div>
                <Badge tone="success">ENFORCED</Badge>
              </div>
              <p className="mt-3 text-xs leading-relaxed text-ink-2">
                Sensitive customer information is protected before it reaches AI processing and audit records.
              </p>
              <div className="mt-3.5 rounded-md border border-line bg-canvas/60 p-2.5 text-xs text-ink-2">
                <span className="font-medium text-ink">Sanitization:</span> Emails, phone numbers, and account identifiers are masked before processing.
              </div>
            </div>
            <div className="mt-4 pt-2 text-[11px] text-ink-3">
              Enforced at pipeline ingress and audit storage
            </div>
          </div>

          {/* 4. Prompt injection protection */}
          <div className="flex flex-col justify-between rounded-lg border border-line bg-surface p-4">
            <div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="flex size-7 items-center justify-center rounded-md bg-brand-50 text-brand-700">
                    <ShieldAlert className="size-4" aria-hidden="true" />
                  </span>
                  <h3 className="text-sm font-semibold text-ink">Prompt injection protection</h3>
                </div>
                <Badge tone="success">ENFORCED</Badge>
              </div>
              <p className="mt-3 text-xs leading-relaxed text-ink-2">
                Attempts to override the agent&apos;s instructions or safety boundaries are blocked and routed safely.
              </p>
              <div className="mt-3.5 rounded-md border border-line bg-canvas/60 p-2.5 text-xs text-ink-2">
                <span className="font-medium text-ink">Boundary defense:</span> Customer input is treated strictly as untrusted data; instruction overrides trigger safe escalation.
              </div>
            </div>
            <div className="mt-4 pt-2 text-[11px] text-ink-3">
              Tested against adversarial red-team benchmarks
            </div>
          </div>

          {/* 5. Response verification */}
          <div className="flex flex-col justify-between rounded-lg border border-line bg-surface p-4">
            <div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="flex size-7 items-center justify-center rounded-md bg-brand-50 text-brand-700">
                    <FileCheck2 className="size-4" aria-hidden="true" />
                  </span>
                  <h3 className="text-sm font-semibold text-ink">Response verification</h3>
                </div>
                <Badge tone="success">ENFORCED</Badge>
              </div>
              <p className="mt-3 text-xs leading-relaxed text-ink-2">
                AI-generated responses are checked before they are sent to customers.
              </p>
              <div className="mt-3.5 rounded-md border border-line bg-canvas/60 p-2.5 text-xs text-ink-2">
                <span className="font-medium text-ink">Guardrail:</span> If verification fails: Human handoff.
              </div>
            </div>
            <div className="mt-4 pt-2 text-[11px] text-ink-3">
              Checks evidence citations and hallucination prevention
            </div>
          </div>

          {/* 6. AI failure fallback */}
          <div className="flex flex-col justify-between rounded-lg border border-line bg-surface p-4">
            <div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="flex size-7 items-center justify-center rounded-md bg-brand-50 text-brand-700">
                    <RotateCcw className="size-4" aria-hidden="true" />
                  </span>
                  <h3 className="text-sm font-semibold text-ink">AI failure fallback</h3>
                </div>
                <Badge tone="success">ENFORCED</Badge>
              </div>
              <p className="mt-3 text-xs leading-relaxed text-ink-2">
                If the AI service becomes unavailable or cannot safely complete a request, ResolveAI falls back to a human handoff.
              </p>
              <div className="mt-3.5 rounded-md border border-line bg-canvas/60 p-2.5 text-xs text-ink-2">
                <span className="font-medium text-ink">Availability guarantee:</span> Timeouts and errors route to humans; customer requests are never dropped.
              </div>
            </div>
            <div className="mt-4 pt-2 text-[11px] text-ink-3">
              Deterministic fallback path active
            </div>
          </div>
        </div>
      </section>

      {/* Advanced Verification (Collapsed by default at the bottom) */}
      <section aria-labelledby="section-advanced-verification" className="pt-2">
        <details className="group rounded-lg border border-line bg-surface p-4 transition-all">
          <summary className="flex cursor-pointer items-center justify-between text-sm font-semibold text-ink select-none">
            <div className="flex items-center gap-2">
              <Shield className="size-4 text-brand-700" aria-hidden="true" />
              <span>Advanced verification</span>
              <span className="text-xs font-normal text-ink-3">
                Release checks, adversarial test suites, and technical implementation controls
              </span>
            </div>
            <ChevronDown className="size-4 text-ink-3 transition-transform group-open:rotate-180" aria-hidden="true" />
          </summary>

          <div className="mt-5 space-y-6 border-t border-line pt-5">
            {/* Release Verification Summary */}
            {checks ? (
              <div>
                <div className="mb-3 flex flex-wrap items-center gap-2">
                  <h3 className="text-sm font-semibold text-ink">Release 1.0.0 verification</h3>
                  <Badge tone="info">Frozen artifacts · stored test evidence</Badge>
                </div>
                <Card>
                  <KeyValues
                    items={[
                      {
                        label: "Adversarial suite",
                        value: checks.adversarial_suite ? passBadge(checks.adversarial_suite.passed, checks.adversarial_suite.n_cases) : "Not available",
                        hint: checks.adversarial_suite?.model,
                      },
                      {
                        label: "API smoke (production profile)",
                        value: checks.api_smoke ? passBadge(checks.api_smoke.passed, checks.api_smoke.n_checks) : "Not available",
                        hint: "Authentication, scopes, rate limits, error bodies and trace privacy against a running server.",
                      },
                      {
                        label: "Frozen artifact verification",
                        value: checks.verification ? <Badge tone={checks.verification.passed ? "success" : "danger"}>{checks.verification.passed ? "Passed" : "Failed"}</Badge> : "Not available",
                        hint: checks.verification ? `Golden set ${checks.verification.golden.verified ? "verified" : "NOT verified"} (${checks.verification.golden.rows} rows) · run ${checks.verification.started}` : undefined,
                      },
                      {
                        label: "Clean environment check",
                        value: checks.clean_environment ? <Badge tone={checks.clean_environment.passed ? "success" : "danger"}>{checks.clean_environment.passed ? "Passed" : "Failed"}</Badge> : "Not available",
                        hint: checks.clean_environment ? `${checks.clean_environment.mode} mode on ${checks.clean_environment.os}` : undefined,
                      },
                    ]}
                  />
                  <p className="mt-3 text-xs text-ink-3">
                    These results were recorded when release 1.0.0 was verified and are served as stored evidence that the controls were exercised on that release.
                  </p>
                </Card>
              </div>
            ) : null}

            {/* Technical Safeguard Implementation References */}
            <div>
              <h3 className="mb-3 text-sm font-semibold text-ink">Implementation controls & source references</h3>
              <div className="overflow-x-auto rounded-lg border border-line bg-canvas/40">
                <table className="w-full text-left text-xs">
                  <thead className="border-b border-line bg-canvas text-ink-3">
                    <tr>
                      <th className="px-3 py-2 font-medium">Control</th>
                      <th className="px-3 py-2 font-medium">Status</th>
                      <th className="px-3 py-2 font-medium">Enforcement point</th>
                      <th className="px-3 py-2 font-medium">Code references</th>
                      <th className="px-3 py-2 font-medium">Test suite</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line/60 bg-surface">
                    {controls.map((c) => (
                      <tr key={c.key} className="hover:bg-canvas/30">
                        <td className="px-3 py-2.5 font-medium text-ink">{c.title}</td>
                        <td className="px-3 py-2.5">
                          <Badge tone={c.status.tone}>{c.status.label}</Badge>
                        </td>
                        <td className="px-3 py-2.5 text-ink-2 max-w-[240px] truncate" title={c.enforcedAt}>
                          {c.enforcedAt}
                        </td>
                        <td className="px-3 py-2.5 font-mono text-[11px] text-ink-3">
                          {c.code.map((p) => p.replace("resolveai/", "")).join(", ")}
                        </td>
                        <td className="px-3 py-2.5 font-mono text-[11px] text-ink-3">
                          {c.tests.map((t) => t.replace("tests/", "")).join(", ")}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </details>
      </section>
    </div>
  );
}
