/**
 * "Why did ResolveAI do this?" Built only from structured decision data: the API's outcome, evidence gate, policy rule, risk
 * flags, verification and output gate (or, for a trace, the events it recorded). No model is ever asked to explain itself, and
 * nothing here decides anything.
 */
import type { Action, AgentTrace, ResolveResponse } from "@/lib/api/types";
import { humanize } from "@/lib/format";
import { activeRiskFlags } from "@/lib/handoff-summary";
import { ACTION_META, EVIDENCE_LEVEL_META, GATE_CHECK_LABELS, HARD_BLOCK_FLAGS, RISK_FLAG_LABELS, SUFFICIENCY_REASON_LABELS, evidenceLevel, reasonMeta } from "@/lib/labels";
import { eventData } from "@/lib/trace";

export const EXPLANATION_HEADINGS: Record<Action, string> = {
  AUTO_HANDLE: "Why this response was allowed",
  CLARIFICATION_REQUIRED: "Why the agent asked for more information",
  HUMAN_HANDOFF: "Why a human was required",
};

export interface Explanation {
  action: Action;
  heading: string;
  decision: string;
  reason: string;
  evidence: string;
  policy: string;
  risk: string;
  verification: string;
  /** What would have changed the decision, stated from the ordered policy rules and the output gate (never predicted). */
  whatWouldChange: string;
  nextAction: string;
  source: "result" | "trace";
}

/**
 * The policy's rules in the order `decide()` checks them (resolveai/policy/escalation.py POLICY_RULES, served by /agent/profile).
 * A console test asserts this list equals the served one, so the explanation cannot drift from the code.
 */
export const POLICY_RULE_ORDER = [
  "safety",
  "prompt_injection",
  "security",
  "legal",
  "abusive",
  "canned:greeting",
  "account_access",
  "payment_billing",
  "private_info",
  "hardware",
  "repeat_contact",
  "human_requested",
  "vague_hostile",
  "canned:other",
  "canned:acknowledgement",
  "canned:non_latin_script",
  "insufficient_context",
  "other_non_closure",
  "general_complaint_clarify",
  "taxonomy_gap",
  "low_confidence",
  "canned:non_english",
  "conflicting_evidence",
  "evidence_gate",
  "grounding_gate",
  "llm_fallback",
  "default_auto",
] as const;

const HANDOFF_CONDITIONS =
  "a hard risk flag (safety, prompt injection, security, legal or media, abuse), an account, billing, private-information, hardware or repeat-contact case, conflicting evidence, a draft that failed verification, or an unavailable model";

export function whatWouldChange(action: Action, rule: string | null | undefined): string {
  const idx = rule ? POLICY_RULE_ORDER.indexOf(rule as (typeof POLICY_RULE_ORDER)[number]) : -1;
  const position = idx >= 0 ? `Rule ${rule} is number ${idx + 1} of ${POLICY_RULE_ORDER.length} in the policy order` : null;
  if (action === "AUTO_HANDLE") {
    if (rule === "default_auto") {
      return `This reply reached the last policy rule: none of the ${POLICY_RULE_ORDER.length - 1} earlier rules matched. It would have been a human handoff on ${HANDOFF_CONDITIONS}; a clarification on an unstated issue, low intent confidence or a clarifiable evidence gap; and any failed output-gate check would have withheld it.`;
    }
    return `${position ?? "A fixed template"}. Any risk rule earlier in the order would have handed the case to a human instead; a template carries no troubleshooting content, so it needs no evidence.`;
  }
  if (action === "CLARIFICATION_REQUIRED") {
    return `${position ? `${position}. ` : ""}An automatic reply would have needed a stated issue, acceptable intent confidence and SUFFICIENT or STRONG evidence, then a verified draft. The same gap with a high-impact risk, several intents or a reason that cannot be clarified would have gone to a human.`;
  }
  if (position) {
    return `${position}; the rules after it were not evaluated. An automatic reply would have needed no earlier rule to match, SUFFICIENT or STRONG evidence, a verified draft and every output-gate check passing.`;
  }
  return "This handoff came from a failure or a gate outside the ordered policy rules (for example a dependency failure or an audit trail that could not be written); an automatic reply is never released in that case.";
}

const sufficiencyText = (reason: string | null | undefined) => SUFFICIENCY_REASON_LABELS[reason ?? ""] ?? humanize(reason);

function riskText(flags: string[], source?: string | null): string {
  if (!flags.length) return `No risk flags raised${source ? ` (${source})` : ""}.`;
  const hard = flags.filter((f) => HARD_BLOCK_FLAGS.has(f));
  const labels = flags.map((f) => RISK_FLAG_LABELS[f] ?? humanize(f));
  return `Raised: ${labels.join(", ")}${hard.length ? `. Hard block: ${hard.map((f) => RISK_FLAG_LABELS[f] ?? f).join(", ")}` : ""}${source ? ` (${source})` : ""}.`;
}

function gateText(gates: Record<string, boolean> | undefined, blocking: string[] | undefined): string {
  const checks = Object.keys(gates ?? {});
  if (!checks.length) return "";
  const blocked = blocking?.length ? blocking : checks.filter((k) => !gates![k]);
  return blocked.length
    ? ` Output gate: no automatic reply; ${blocked.length} of ${checks.length} checks not met (${blocked.map((k) => (GATE_CHECK_LABELS[k] ?? humanize(k)).toLowerCase()).join("; ")}).`
    : ` Output gate: all ${checks.length} checks passed.`;
}

export function explainResult(r: ResolveResponse): Explanation {
  const o = r.outcome;
  const level = evidenceLevel(r.evidence.sufficiency_level);
  const used = r.response.evidence_refs.length;
  const v = r.verification;
  let verification: string;
  if (v) {
    verification = v.verified
      ? "The drafted reply was verified against the evidence it cites."
      : `The drafted reply failed verification${v.issues.length ? `: ${v.issues.join("; ")}` : ""}. It was not sent.`;
  } else if (r.response.kind === "template_reply") {
    verification = "Not needed: a fixed template with no troubleshooting content.";
  } else {
    verification = "Not run: no reply was drafted, so there was nothing to verify.";
  }
  verification += gateText(o.output_gate, o.blocking_checks);
  return {
    action: r.action,
    heading: EXPLANATION_HEADINGS[r.action],
    source: "result",
    decision: `${ACTION_META[r.action].label}. ${o.what_happened}`,
    reason: r.action === "AUTO_HANDLE" ? o.why : `${reasonMeta(o.reason_code).label}. ${o.why}`,
    evidence:
      `${EVIDENCE_LEVEL_META[level].label} (${sufficiencyText(r.evidence.sufficiency_reason)}). ${r.evidence.items.length} historical case${r.evidence.items.length === 1 ? "" : "s"} retrieved, ${used} used in the response.` +
      (r.evidence.sufficient ? "" : " Not sufficient to answer safely; retrieved cases were not treated as an answer."),
    policy: `Rule ${o.rule} (reason ${o.reason_code}) in ${o.policy_version} was the first rule that matched. Autonomous response ${o.autonomous_response_allowed ? "allowed" : "not allowed"}.`,
    risk: riskText(activeRiskFlags(r.risk as unknown as Record<string, unknown>)),
    verification,
    whatWouldChange: whatWouldChange(r.action, o.rule),
    nextAction: o.next_step,
  };
}

/* ---------------------------------------------------------------- traces (no customer or evidence text is stored) */

interface PolicyEvent {
  decision?: string;
  reason_code?: string;
  rule?: string;
  policy_version?: string;
  clarification_allowed?: boolean;
  strategy?: string;
}
interface GateEvent {
  action?: string;
  blocking?: string[];
  gates?: Record<string, boolean>;
}
interface IntentEvent {
  intent?: string;
  confidence?: number;
  band?: string;
}
interface SecondOpinionEvent {
  before?: string;
  after?: string;
  applied?: boolean;
}
interface EvidenceEvent {
  sufficient?: boolean;
  reason?: string;
  level?: string;
  resolution_confidence?: number;
  consistency?: string;
  gate_version?: string;
}
interface RiskEvent {
  flags?: string[];
  source?: string;
}
interface ClarificationEvent {
  reason_code?: string;
  missing?: string[];
  already_provided?: string[];
}
interface RetrievalEvent {
  n_retrieved?: number;
  evidence_ids?: string[];
  top_similarity?: number;
  retriever?: string;
}

/** The decision data an audit trace records (no customer text, no evidence text). */
export function summarizeTraceDecision(trace: AgentTrace) {
  const d = <T,>(name: string) => eventData<T>(trace.events, name);
  const policy = d<PolicyEvent>("escalation_decided");
  const handoff = d<{ reason_code?: string }>("handoff_created");
  const clarification = d<ClarificationEvent>("clarification_created");
  const gate = d<GateEvent>("output_allowed") ?? d<GateEvent>("decision_made");
  const intent = d<IntentEvent>("intent_predicted");
  const second = d<SecondOpinionEvent>("second_opinion_used");
  const evidence = d<EvidenceEvent>("evidence_evaluated");
  const risk = d<RiskEvent>("risk_flags_extracted");
  const retrieval = d<RetrievalEvent>("retrieval_completed");
  const action = ((trace.final_decision ?? gate?.action) as Action | undefined) ?? null;
  const reasonCode = handoff?.reason_code ?? clarification?.reason_code ?? policy?.reason_code ?? "none";
  return { action, reasonCode, policy, gate, intent, second, evidence, risk, retrieval, clarification, finalIntent: second?.applied ? second.after : intent?.intent };
}

const TRACE_NEXT_ACTION: Record<Action, string> = {
  AUTO_HANDLE: "The verified reply was returned to the caller. In this reference environment nothing is sent to a customer.",
  CLARIFICATION_REQUIRED: "The clarifying question was returned; the conversation continues when the customer answers.",
  HUMAN_HANDOFF: "A human agent takes the case with the handoff packet. Only a holding notice is returned.",
};

export function explainTrace(trace: AgentTrace): Explanation | null {
  const s = summarizeTraceDecision(trace);
  if (!s.action) return null;
  const laterStage = Boolean(s.policy?.reason_code && s.policy.reason_code !== s.reasonCode);
  const stage = (k: string) => (trace.stage_status as Record<string, string> | undefined)?.[k];
  const verifyStatus = stage("verification");
  const level = evidenceLevel(s.evidence?.level);
  return {
    action: s.action,
    heading: EXPLANATION_HEADINGS[s.action],
    source: "trace",
    decision: `${ACTION_META[s.action].label}.`,
    reason:
      s.action === "AUTO_HANDLE"
        ? ACTION_META.AUTO_HANDLE.summary
        : `${reasonMeta(s.reasonCode).label}.${laterStage ? ` The policy stage chose ${humanize(s.policy?.reason_code).toLowerCase()}; a later stage changed the outcome.` : ""}`,
    evidence: s.evidence
      ? `${EVIDENCE_LEVEL_META[level].label} (${sufficiencyText(s.evidence.reason)}).${s.retrieval ? ` ${s.retrieval.n_retrieved ?? 0} candidates retrieved.` : ""} Evidence text is not stored in traces.`
      : "The evidence gate did not run.",
    policy: s.policy ? `Rule ${s.policy.rule ?? "n/a"} (reason ${s.policy.reason_code ?? "n/a"}) in ${s.policy.policy_version ?? trace.versions?.policy ?? "n/a"}.` : "No policy decision recorded.",
    risk: riskText(s.risk?.flags ?? [], s.risk?.source),
    verification: `${verifyStatus ? `Verification stage: ${humanize(verifyStatus).toLowerCase()}.` : "Verification stage not recorded."}${gateText(s.gate?.gates, s.gate?.blocking)}`,
    whatWouldChange: whatWouldChange(s.action, s.policy?.rule),
    nextAction: TRACE_NEXT_ACTION[s.action],
  };
}
