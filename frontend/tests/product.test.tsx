/** Product Completion 1: explanation, evidence-first view, handoff queues, PII scrub, trust statuses, navigation and the release scorecard. */
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DecisionExplanation } from "@/components/decision/decision-explanation";
import { ReleaseSections } from "@/components/evaluation/release";
import { EvidencePanel, INSUFFICIENT_EVIDENCE_TEXT } from "@/components/evidence/evidence-panel";
import { HandoffQueue } from "@/components/handoff/handoff-queue";
import { NAV, titleFor } from "@/components/shell/nav";
import { traceSummaryAnswers } from "@/components/trace/trace-summary";
import { trustControls } from "@/components/trust/trust-controls";
import type { RuntimeConfig } from "@/lib/api/types";
import { EXPLANATION_HEADINGS, POLICY_RULE_ORDER, explainResult, explainTrace } from "@/lib/explain";
import { handoffSummaryText, scrubPii } from "@/lib/handoff-summary";
import { QUEUE_CATEGORIES, REASON_META, handoffCategory } from "@/lib/labels";
import { liveMetrics, matchesQuery, mergeRows, parseRowFilter } from "@/lib/rows";
import { foldForMatch } from "@/lib/text";
import { fx } from "./fixtures";

describe("decision explanation (structured data only)", () => {
  it("uses the action-specific heading", () => {
    expect(explainResult(fx.autoHandle).heading).toBe("Why this response was allowed");
    expect(explainResult(fx.clarificationVague).heading).toBe("Why the agent asked for more information");
    expect(explainResult(fx.securityHandoff).heading).toBe("Why a human was required");
  });

  it("states decision, reason, evidence, policy, risk, verification and next action from the result", () => {
    const e = explainResult(fx.autoHandle);
    expect(e.policy).toContain(fx.autoHandle.outcome.rule);
    expect(e.policy).toContain(fx.autoHandle.outcome.policy_version);
    expect(e.evidence).toContain(`${fx.autoHandle.response.evidence_refs.length} used in the response`);
    expect(e.verification).toMatch(/verified against the evidence/);
    expect(e.nextAction).toBe(fx.autoHandle.outcome.next_step);
    const h = explainResult(fx.securityHandoff);
    expect(h.reason).toMatch(/^Safety or security concern\./);
    expect(h.risk).toContain("Security concern");
    expect(explainResult(fx.verificationFailed).verification).toMatch(/failed verification/);
    const blocking = fx.securityHandoff.outcome.blocking_checks.length;
    expect(explainResult(fx.securityHandoff).verification).toContain(`no automatic reply; ${blocking} of ${Object.keys(fx.securityHandoff.outcome.output_gate).length} checks not met`);
    expect(explainResult(fx.autoHandle).verification).toMatch(/all \d+ checks passed/);
    expect(explainResult(fx.clarificationInsufficientEvidence).evidence).toMatch(/Not sufficient to answer safely/);
  });

  it("reconstructs an explanation from a trace and says evidence text is not stored", () => {
    const e = explainTrace(fx.traceClarification)!;
    expect(e.source).toBe("trace");
    expect(e.heading).toBe(EXPLANATION_HEADINGS.CLARIFICATION_REQUIRED);
    expect(e.evidence).toContain("Evidence text is not stored in traces");
  });

  it("says what would have changed the decision, from the same rule order the API serves", () => {
    expect([...POLICY_RULE_ORDER]).toEqual(fx.agentProfile.policy.rules.map((r) => r.rule));
    const n = POLICY_RULE_ORDER.length;
    expect(explainResult(fx.autoHandle).whatWouldChange).toMatch(new RegExp(`reached the last policy rule: none of the ${n - 1} earlier rules matched`));
    expect(explainResult(fx.securityHandoff).whatWouldChange).toMatch(new RegExp(`^Rule security is number 3 of ${n}`));
    expect(explainResult(fx.clarificationVague).whatWouldChange).toMatch(/SUFFICIENT or STRONG evidence/);
  });

  it("renders all eight fields", () => {
    render(<DecisionExplanation explanation={explainResult(fx.securityHandoff)} />);
    for (const label of ["Decision", "Reason", "Evidence", "Policy", "Risk", "Verification", "What would change it", "Next action"]) expect(screen.getByText(label, { selector: "dt" })).toBeInTheDocument();
    expect(screen.getByText(/No model was asked to explain itself/)).toBeInTheDocument();
  });
});

describe("evidence-first view", () => {
  it("separates evidence used in the response from retrieved evidence", () => {
    const cited = fx.autoHandle.response.evidence_refs.map((r) => r.evidence_id);
    render(<EvidencePanel evidence={fx.autoHandle.evidence} citedIds={cited} />);
    const used = screen.getByRole("region", { name: "Evidence used in response" });
    expect(within(used).getAllByText("Cited in reply")).toHaveLength(cited.length);
    const retrieved = screen.getByRole("region", { name: "Retrieved evidence" });
    expect(within(retrieved).queryByText("Cited in reply")).toBeNull();
    expect(screen.queryByText(INSUFFICIENT_EVIDENCE_TEXT)).toBeNull();
  });

  it("says plainly when evidence is insufficient and that retrieved is not trustworthy", () => {
    render(<EvidencePanel evidence={fx.clarificationInsufficientEvidence.evidence} />);
    expect(screen.getByText(INSUFFICIENT_EVIDENCE_TEXT)).toBeInTheDocument();
    expect(screen.getByText(/No evidence was used in a customer response/)).toBeInTheDocument();
  });
});

describe("handoff queues and summary", () => {
  it("maps reason codes (and the security rule) to fixed queues", () => {
    expect(handoffCategory("safety", "security")).toBe("Security");
    expect(handoffCategory("safety", "safety")).toBe("Safety");
    expect(handoffCategory("prompt_injection", "prompt_injection")).toBe("Security");
    expect(handoffCategory("payment_billing")).toBe("Billing");
    expect(handoffCategory("private_info")).toBe("Account");
    expect(handoffCategory("hardware")).toBe("Technical");
    expect(handoffCategory("insufficient_evidence")).toBe("Insufficient evidence");
    expect(handoffCategory("llm_unavailable")).toBe("Model failure");
    expect(handoffCategory("something_new")).toBe("Other");
    expect(Object.values(REASON_META).every((m) => QUEUE_CATEGORIES.includes(m.category))).toBe(true);
  });

  it("offers every queue as a filter", () => {
    render(<HandoffQueue summaries={fx.traces.items} />);
    const group = screen.getByRole("group", { name: "Filter handoffs by queue" });
    for (const name of ["All", ...QUEUE_CATEGORIES]) expect(within(group).getByRole("button", { name: new RegExp(`^${name}`) })).toBeInTheDocument();
  });

  it("scrubs personal data from the copied summary", () => {
    expect(scrubPii("mail jane.doe@example.com or call 555-123-4567.")).toBe("mail <EMAIL> or call <PHONE>.");
    const h = fx.securityHandoff.handoff!;
    const leaky = { ...fx.securityHandoff, handoff: { ...h, customer_issue: "reach me at jane.doe@example.com", unresolved_questions: ["call 555-123-4567?"] } };
    const text = handoffSummaryText(leaky);
    expect(text).not.toContain("jane.doe@example.com");
    expect(text).not.toContain("555-123-4567");
    expect(text).toContain("Queue: Security");
  });
});

describe("trust and governance", () => {
  const config = (over: { auth?: boolean; traces?: boolean; llm?: boolean }) =>
    ({
      service: { env: "test", write_traces: over.traces ?? true, trace_store: { kind: "jsonl", dir: "traces" }, rate_limit_per_minute: 6, max_queue: 4, docs_enabled: false, auth: { required: over.auth ?? true, scheme: "bearer" }, limits: { max_body_bytes: 1, max_message_chars: 2000, max_turn_chars: 1, max_turns: 20, max_total_chars: 1 } },
      llm: { configured: true, enabled: over.llm ?? true, model: "m", provider: "p", temperature: 0, timeout_s: 30, max_retries: 1 },
      embedding_model: "e",
      brand: "b",
      agent_state: "loaded",
    }) as unknown as RuntimeConfig;

  it("lists the ten controls with status, enforcement point, threat, code and tests", () => {
    const controls = trustControls(config({}));
    expect(controls.map((c) => c.key)).toEqual(["pii", "injection", "evidence", "policy", "verification", "handoff", "audit", "auth", "limits", "model-failure"]);
    expect(controls.every((c) => c.enforcedAt && c.protectsAgainst && c.code.length && c.tests.length && c.status.label === "Enforced")).toBe(true);
  });

  it("reports the configured status honestly", () => {
    const byKey = (cfg: RuntimeConfig | null) => Object.fromEntries(trustControls(cfg).map((c) => [c.key, c.status.label]));
    const off = byKey(config({ auth: false, traces: false, llm: false }));
    expect(off.auth).toBe("Not required in this profile");
    expect(off.audit).toBe("Disabled in this profile");
    expect(off.verification).toMatch(/^Model off/);
    expect(Object.values(byKey(null)).every((s) => s.startsWith("Status unknown"))).toBe(true);
  });
});

describe("search and filters ignore capitalization", () => {
  it("folds case, width and invisible characters but never changes the displayed text", () => {
    expect(foldForMatch("  MY​ IPHONE ")).toBe("my iphone");
    expect(foldForMatch("ＩＰＨＯＮＥ")).toBe("iphone");
    const stored = { traceId: "t-case", savedAt: "2026-01-01T00:00:00Z", source: "test", result: fx.autoHandle };
    const row = mergeRows([], [stored])[0];
    const results = ["my iphone", "MY IPHONE", "My iPhone", "mY iPhOnE", "ＭＹ ＩＰＨＯＮＥ"].map((q) => matchesQuery(row, q));
    expect(new Set(results)).toEqual(new Set([matchesQuery(row, "my iphone")]));
    expect(row.preview).toBe(fx.autoHandle.conversation.message.text);
  });

  it("reads URL filters in any capitalization or separator", () => {
    expect(parseRowFilter("HANDOFF")).toBe("handoff");
    expect(parseRowFilter("High-Risk")).toBe("high_risk");
    expect(parseRowFilter("Insufficient Evidence")).toBe("insufficient_evidence");
    expect(parseRowFilter("nonsense")).toBe("all");
    expect(parseRowFilter(undefined)).toBe("all");
  });
});

describe("navigation, trace summary and live metrics", () => {
  it("has the product information architecture", () => {
    expect(NAV.map((g) => g.group)).toEqual(["Workspace", "AI", "Insights", "Governance"]);
    expect(NAV.flatMap((g) => g.items.map((i) => i.href))).toEqual(["/overview", "/conversations", "/handoffs", "/agents", "/knowledge", "/simulate", "/evaluation", "/analytics", "/trust", "/traces", "/settings"]);
    expect(titleFor("/handoffs")).toBe("Handoff queue");
    expect(titleFor("/evaluation")).toBe("Evaluation");
    expect(titleFor(`/traces/${"a".repeat(32)}`)).toBe("Audit Log");
    expect(titleFor("/trust")).toBe("Trust & Safety");
  });

  it("answers what happened, how long and what failed from a trace", () => {
    const a = traceSummaryAnswers(fx.traceAuto);
    expect(a.whatFailed).toMatch(/^Nothing failed/);
    expect(a.howLong).toContain("in total");
    expect(a.why).toContain("default_auto");
  });

  it("sums model calls and keeps cost unknown when no trace recorded it", () => {
    const m = liveMetrics(fx.traces.items);
    expect(m.modelCalls).toBe(fx.traces.items.reduce((s, t) => s + (t.llm_calls ?? 0), 0));
    expect(liveMetrics([]).estimatedCostUsd).toBeNull();
  });
});

describe("release scorecard", () => {
  it("shows release metrics with confidence intervals and dataset labels, served as stored", () => {
    render(<ReleaseSections release={fx.release} />);
    const scorecard = document.querySelector<HTMLElement>('[aria-label="Release scorecard"]')!;
    expect(scorecard).toBeTruthy();
    const cell = Object.values(fx.release.golden.table!)[0].escalation_precision;
    const pct = (v: number) => `${(v * 100).toFixed(1)}%`;
    expect(within(scorecard).getByText(pct(cell.resolveai!))).toBeInTheDocument();
    expect(within(scorecard).getByText(`95% CI ${pct(cell.resolveai_ci!.ci_low)} to ${pct(cell.resolveai_ci!.ci_high)}`)).toBeInTheDocument();
    expect(screen.getAllByText(/FROZEN GOLDEN SET/).length).toBeGreaterThan(0);
    expect(screen.getByText(/DEV EXPERIMENTS/)).toBeInTheDocument();
    expect(screen.getByText("Human judge validation pending")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: `${fx.release.golden.failure_modes!.unnecessary_handoffs.total} unnecessary handoffs` })).toBeInTheDocument();
  });
});
