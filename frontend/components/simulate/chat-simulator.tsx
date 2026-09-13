"use client";

import {
  ArrowUp,
  CheckCircle,
  ChevronDown,
  CircleCheck,
  CircleX,
  MessageSquare,
  Play,
  RotateCcw,
  X,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button, ButtonLink } from "@/components/ui/button";
import { Notice } from "@/components/ui/card";
import { ErrorState } from "@/components/ui/states";
import { ConversationWorkspace } from "@/components/conversation/workspace";
import { ApiError, api } from "@/lib/api/client";
import type { AgentTrace, DemoScenario, ResolveRequest, ResolveResponse } from "@/lib/api/types";
import { isResolveResponse } from "@/lib/api/validate";
import { toErrorInfo, type ErrorInfo } from "@/lib/errors";
import { duration } from "@/lib/format";
import { intentLabel, reasonMeta } from "@/lib/labels";
import { groupTraceEvents, type StageStatus } from "@/lib/trace";
import { clearResults, saveResult, useStoredResults, type StoredResult } from "@/lib/results-store";
import { LLM_REQUIREMENT, checkExpectation, expectationText } from "@/lib/scenarios";

// ─── Types ─────────────────────────────────────────────────────────────────

interface ChatMessage {
  id: number;
  role: "customer" | "agent";
  text: string;
  result?: ResolveResponse;
  trace?: AgentTrace | null;
  error?: ErrorInfo;
  thinking?: boolean;
  isGreeting?: boolean;
}

type RunState = "idle" | "running" | "done";

// ─── Greeting ──────────────────────────────────────────────────────────────

const GREETING_TEXT =
  "Hi there! 👋 I'm ResolveAI, your AI-powered support assistant.\n\nI can help you troubleshoot device issues, answer account questions, and more. If I'm not sure or if your request needs a real human, I'll let you know and connect you with the right person.\n\nWhat can I help you with today?";

function makeGreeting(id: number): ChatMessage {
  return { id, role: "agent", text: GREETING_TEXT, isGreeting: true };
}

// ─── Suggested prompts ─────────────────────────────────────────────────────

const SUGGESTED_PROMPTS = [
  "How do I reset my iPhone?",
  "My account isn't working.",
  "I need help with a billing issue.",
];

// ─── Quick example presets ─────────────────────────────────────────────────

const EXAMPLES = [
  { id: "A", label: "Grounded answer" },
  { id: "B", label: "Needs clarification" },
  { id: "C", label: "Human handoff" },
  { id: "E", label: "Prompt injection" },
] as const;

// ─── Curated demo path (kept for Advanced section) ─────────────────────────

const CURATED: {
  n: number;
  title: string;
  api?: string;
  message?: string;
  expected: string;
  lookFor: string;
}[] = [
  {
    n: 1,
    title: "Safe grounded troubleshooting",
    api: "A",
    expected: "Auto-handled with cited evidence",
    lookFor:
      "Sufficient evidence, the exact cases the reply cites, verification and every output-gate check passing.",
  },
  {
    n: 2,
    title: "Ambiguous request",
    api: "B",
    expected: "Clarification",
    lookFor:
      "No concrete issue is stated: one clarifying question and no troubleshooting.",
  },
  {
    n: 3,
    title: "Risky request: human handoff",
    api: "C",
    expected: "Human handoff with a packet",
    lookFor:
      "A security risk flag is a hard block: a handoff packet with a recommended next action.",
  },
  {
    n: 4,
    title: "Insufficient evidence",
    api: "D",
    expected: "Clarification",
    lookFor:
      "The evidence gate finds no consistent resolution, so ResolveAI asks instead of answering.",
  },
  {
    n: 5,
    title: "Sensitive or private information",
    message:
      "I need the status of my repair order and which card you charged for it. Can you look it up on my Apple ID?",
    expected: "Human handoff",
    lookFor:
      "Order, payment and account details cannot be handled in a public reply; a deterministic rule requires a human.",
  },
  {
    n: 6,
    title: "Prompt injection",
    api: "E",
    expected: "Human handoff",
    lookFor:
      "Instruction-like text is treated as data and the prompt_injection rule hands off.",
  },
  {
    n: 7,
    title: "Model failure",
    api: "F",
    expected: "Human handoff when the model is unavailable",
    lookFor:
      "The fallback hands off instead of failing. With a working model this message is answered normally; to see the outage live, start the API with an unreachable model endpoint (docs/DEMO.md).",
  },
];

// ─── Stage status helpers (for Advanced pipeline stepper) ──────────────────

const STAGE_STATUS_TEXT: Record<StageStatus, string> = {
  ok: "completed",
  skipped: "skipped",
  fallback: "fallback",
  error: "failed",
  flagged: "flagged",
  not_recorded: "not recorded",
};
const STAGE_STATUS_CLS: Record<StageStatus, string> = {
  ok: "border-line bg-surface",
  skipped: "border-line bg-subtle",
  fallback: "border-warning-line bg-warning-bg",
  error: "border-danger-line bg-danger-bg",
  flagged: "border-warning-line bg-warning-bg",
  not_recorded: "border-line bg-subtle",
};

// ─── Sub-components ────────────────────────────────────────────────────────

/** Render multi-paragraph agent text — splits on newlines */
function ResponseText({ text }: { text: string }) {
  const paras = text.split(/\n+/).filter(Boolean);
  if (paras.length <= 1) return <span>{text}</span>;
  return (
    <>
      {paras.map((p, i) => (
        <p key={i} className={i > 0 ? "mt-2" : ""}>
          {p}
        </p>
      ))}
    </>
  );
}

function ThinkingDots() {
  return (
    <div className="flex items-start gap-3 px-4 py-3">
      {/* Agent avatar */}
      <div className="flex size-7 shrink-0 items-center justify-center rounded-full border border-[#98A68E]/40 bg-[#586651]/10 text-[10px] font-bold text-[#586651]">
        R
      </div>
      <div className="flex flex-col gap-1.5">
        <div className="flex items-center gap-1 rounded-2xl rounded-tl-sm border border-line bg-surface px-4 py-3 shadow-[0_1px_2px_rgba(15,23,42,0.04)]">
          <span className="thinking-dot" />
          <span className="thinking-dot" style={{ animationDelay: "0.18s" }} />
          <span className="thinking-dot" style={{ animationDelay: "0.36s" }} />
        </div>
        <span className="pl-1 text-[10px] text-ink-3">ResolveAI is reviewing your message…</span>
      </div>
    </div>
  );
}

function AgentMessageBubble({ msg }: { msg: ChatMessage }) {
  const result = msg.result;
  const isAutoHandle = result?.action === "AUTO_HANDLE";
  const isClarification = result?.action === "CLARIFICATION_REQUIRED";
  const isHandoff = result?.action === "HUMAN_HANDOFF";

  return (
    <div className="flex items-start gap-3 px-4 py-2.5">
      {/* Avatar */}
      <div className="flex size-7 shrink-0 items-center justify-center rounded-full border border-[#98A68E]/40 bg-[#586651]/10 text-[10px] font-bold text-[#586651]">
        R
      </div>
      <div className="flex min-w-0 max-w-[82%] flex-col gap-1.5">
        {/* Agent name */}
        <span className="pl-1 text-[11px] font-medium text-ink-3">ResolveAI</span>

        {/* Bubble */}
        <div className="rounded-2xl rounded-tl-sm border border-line bg-surface px-4 py-3 text-sm leading-relaxed text-ink shadow-[0_1px_2px_rgba(15,23,42,0.04)]">
          {msg.error ? (
            <span className="text-danger text-xs">
              ⚠️ {msg.error.message} — please try again or refresh the page.
            </span>
          ) : (
            <ResponseText text={msg.text} />
          )}
        </div>

        {/* Status chip below bubble */}
        {result && (
          <div className="flex items-center gap-1.5 pl-1">
            {isAutoHandle && (
              <span className="inline-flex items-center gap-1 text-[11px] font-medium text-[#3d7a57]">
                <CheckCircle className="size-3" aria-hidden="true" />
                Resolved by ResolveAI
              </span>
            )}
            {isClarification && (
              <span className="inline-flex items-center gap-1 text-[11px] font-medium text-[#8a5a12]">
                <MessageSquare className="size-3" aria-hidden="true" />
                Waiting for your reply
              </span>
            )}
            {isHandoff && (
              <span className="inline-flex items-center gap-1 text-[11px] font-medium text-[#A97975]">
                <span className="inline-block size-1.5 rounded-full bg-[#A97975]" aria-hidden="true" />
                Connecting you with a teammate
              </span>
            )}
          </div>
        )}

        {/* Handoff card */}
        {isHandoff && result && (
          <div className="mt-0.5 rounded-xl border border-[#D9B4B0]/70 bg-[#FDF8F7] px-4 py-3">
            <div className="flex items-center gap-2">
              <div className="flex size-6 items-center justify-center rounded-full bg-[#D9B4B0]/40">
                <span className="text-[10px]">👤</span>
              </div>
              <p className="text-xs font-semibold text-[#A97975]">Support teammate on the way</p>
            </div>
            <p className="mt-2 text-xs leading-relaxed text-ink-2">
              {result.handoff?.recommended_next_action
                ? result.handoff.recommended_next_action
                : "One of our specialists will pick this up shortly and follow up with you directly."}
            </p>
            <div className="mt-3 flex gap-2">
              <ButtonLink href={`/handoffs/${result.trace_id}`} variant="secondary" size="sm">
                View handoff queue
              </ButtonLink>
              <ButtonLink href={`/conversations/${result.trace_id}`} variant="ghost" size="sm">
                Full conversation
              </ButtonLink>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function CustomerBubble({ text }: { text: string }) {
  return (
    <div className="flex flex-col items-end gap-1 px-4 py-2.5">
      <span className="pr-1 text-[11px] font-medium text-ink-3">You</span>
      <div className="max-w-[75%] rounded-2xl rounded-tr-sm bg-[#EAE7DC] px-4 py-3 text-sm leading-relaxed text-ink">
        {text}
      </div>
    </div>
  );
}

function ChatEmptyState({
  onPrompt,
}: {
  onPrompt: (text: string) => void;
}) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-5 px-6 py-10 text-center">
      <div className="flex size-12 items-center justify-center rounded-full border border-[#98A68E]/40 bg-[#586651]/10 text-xl font-bold text-[#586651]">
        R
      </div>
      <div>
        <h2 className="text-sm font-semibold text-ink">Try a quick example</h2>
        <p className="mt-1.5 max-w-[30ch] text-xs leading-relaxed text-ink-3">
          Click a suggestion below or type your own message to get started.
        </p>
      </div>
      <div className="flex flex-col items-center gap-2">
        {SUGGESTED_PROMPTS.map((p) => (
          <button
            key={p}
            type="button"
            onClick={() => onPrompt(p)}
            className="rounded-full border border-line bg-surface px-4 py-2 text-sm text-ink-2 transition-colors hover:border-brand-700/40 hover:bg-canvas hover:text-ink"
          >
            {p}
          </button>
        ))}
      </div>
    </div>
  );
}

function ResolutionPanel({ result }: { result: ResolveResponse | null }) {
  if (!result) {
    return (
      <div className="flex h-full flex-col gap-3 p-4">
        <h2 className="text-sm font-semibold text-ink">Resolution</h2>
        <div className="flex flex-1 flex-col items-center justify-center gap-2 text-center">
          <div className="size-8 rounded-full border border-line bg-canvas" />
          <p className="text-xs text-ink-3">
            Send a message to see how ResolveAI decides.
          </p>
        </div>
      </div>
    );
  }

  const isAutoHandle = result.action === "AUTO_HANDLE";
  const isClarification = result.action === "CLARIFICATION_REQUIRED";
  const isHandoff = result.action === "HUMAN_HANDOFF";

  const citedIds = new Set(result.response.evidence_refs.map((r) => r.evidence_id));
  const citedEvidence = (result.evidence.items ?? []).filter((item) => citedIds.has(item.evidence_id));
  const displayEvidence = citedEvidence.length ? citedEvidence : (result.evidence.items ?? []).slice(0, 3);

  const intentCode = result.intent?.intent;

  const evidenceLevel = result.evidence?.sufficiency_level;
  const evidenceLevelLabel =
    evidenceLevel === "STRONG" ? "Strong" :
    evidenceLevel === "SUFFICIENT" ? "Sufficient" :
    evidenceLevel === "WEAK" ? "Weak" :
    evidenceLevel === "INSUFFICIENT" ? "Insufficient" : null;

  const reason = isAutoHandle
    ? "ResolveAI found enough verified support history to answer this request."
    : isClarification
      ? "The request is missing information needed to provide a reliable answer."
      : "ResolveAI could not safely resolve this request automatically.";

  return (
    <div className="flex flex-col gap-4 overflow-y-auto p-4">
      {/* Decision */}
      <div>
        <h2 className="mb-2 text-sm font-semibold text-ink">Resolution</h2>
        <div
          className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold ${
            isAutoHandle
              ? "bg-[#586651]/10 text-[#3d7a57]"
              : isClarification
                ? "bg-amber-50 text-amber-800"
                : "bg-[#D9B4B0]/30 text-[#A97975]"
          }`}
        >
          <span
            className={`size-1.5 rounded-full ${
              isAutoHandle ? "bg-[#3d7a57]" : isClarification ? "bg-amber-600" : "bg-[#A97975]"
            }`}
          />
          {isAutoHandle ? "Resolved" : isClarification ? "Needs clarification" : "Human handoff"}
        </div>
      </div>

      <div className="space-y-3 border-t border-line pt-3">
        {/* Intent */}
        {intentCode && (
          <div>
            <div className="text-[10px] font-semibold uppercase tracking-wider text-ink-3">
              Intent
            </div>
            <div className="mt-1 text-sm font-medium text-ink">{intentLabel(intentCode)}</div>
          </div>
        )}

        {/* Evidence */}
        {evidenceLevelLabel && (
          <div>
            <div className="text-[10px] font-semibold uppercase tracking-wider text-ink-3">
              Evidence
            </div>
            <div className="mt-1 flex items-center gap-1.5">
              <Badge
                tone={
                  evidenceLevelLabel === "Strong" || evidenceLevelLabel === "Sufficient"
                    ? "success"
                    : evidenceLevelLabel === "Weak"
                      ? "warning"
                      : "neutral"
                }
              >
                {evidenceLevelLabel}
              </Badge>
              {displayEvidence.length > 0 && (
                <span className="text-xs text-ink-3">
                  {displayEvidence.length} relevant case{displayEvidence.length !== 1 ? "s" : ""}
                </span>
              )}
            </div>
          </div>
        )}

        {/* Reason */}
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-wider text-ink-3">
            Reason
          </div>
          <p className="mt-1 text-xs leading-relaxed text-ink-2">{reason}</p>
        </div>
      </div>

      {/* Evidence snippets */}
      {displayEvidence.length > 0 && isAutoHandle && (
        <div className="border-t border-line pt-3">
          <div className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-ink-3">
            Evidence used
          </div>
          <div className="space-y-2">
            {displayEvidence.slice(0, 3).map((item) => (
              <div
                key={item.evidence_id}
                className="rounded-md border border-line bg-canvas/60 px-2.5 py-2 text-[11px]"
              >
                <p className="line-clamp-1 text-ink-3">
                  <strong className="font-medium">Q:</strong> {item.customer_message}
                </p>
                <p className="mt-0.5 line-clamp-2 text-ink-2">
                  <strong className="font-medium text-brand-700">A:</strong> {item.brand_reply}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function PipelineStepper({
  result,
  trace,
}: {
  result: ResolveResponse;
  trace: AgentTrace | null;
}) {
  const groups = groupTraceEvents(
    trace?.events ?? [],
    (trace?.stage_status ?? result.stage_status) as Record<string, string>,
    (trace?.latency_ms ?? result.latency_ms) as Record<string, number>,
  ).filter((g) => g.key !== "other");
  return (
    <div className="rounded-lg border border-line bg-surface p-4">
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-ink-3">
        Agent stages
      </h3>
      <ol aria-label="Agent stages for this run" className="flex flex-wrap gap-1.5">
        {groups.map((g, i) => (
          <li
            key={g.key}
            className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-xs text-ink ${STAGE_STATUS_CLS[g.status]}`}
          >
            <span className="tabular text-ink-3">{i + 1}</span>
            <span>{g.label}</span>
            <span className="text-ink-3">
              · {STAGE_STATUS_TEXT[g.status]}
              {g.durationMs ? ` · ${duration(g.durationMs)}` : ""}
            </span>
          </li>
        ))}
      </ol>
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
  const conversation: ResolveRequest["conversation"] | null = scenario
    ? scenario.conversation
    : item.message
      ? [{ role: "customer", text: item.message }]
      : null;
  const customer = conversation ? [...conversation].reverse().find((t) => t.role === "customer") : null;
  return (
    <li className="flex flex-col rounded-lg border border-line bg-surface p-3">
      <h4 className="text-[13px] font-semibold text-ink">
        <span className="mr-1.5 tabular text-ink-3">{item.n}</span>
        {item.title}
      </h4>
      <p className="mt-1 text-xs text-ink-3">
        Expected: {item.expected}
        {item.api ? ` · API scenario ${item.api}` : " · curated message"}
      </p>
      {customer ? (
        <p className="mt-1.5 line-clamp-2 text-xs text-ink-2">&quot;{customer.text}&quot;</p>
      ) : null}
      <p className="mt-1 text-xs text-ink-2">{item.lookFor}</p>
      <div className="mt-auto flex justify-end pt-2">
        <Button
          size="sm"
          variant="secondary"
          icon={Play}
          disabled={busy || !conversation}
          onClick={() => conversation && onRun(conversation)}
          aria-label={`Run curated scenario ${item.n}: ${item.title}`}
        >
          Run
        </Button>
      </div>
      {!conversation ? (
        <p className="mt-1 text-xs text-warning">Scenario {item.api} is not available.</p>
      ) : null}
    </li>
  );
}

function ScenarioCard({
  scenario,
  busy,
  onRun,
}: {
  scenario: DemoScenario;
  busy: boolean;
  onRun: () => void;
}) {
  const customer = [...scenario.conversation].reverse().find((t) => t.role === "customer");
  return (
    <li className="rounded-lg border border-line bg-surface p-3">
      <div className="flex items-start gap-2.5">
        <span className="flex size-6 shrink-0 items-center justify-center rounded-md bg-subtle font-mono text-xs font-semibold text-ink-2">
          {scenario.id}
        </span>
        <div className="min-w-0 flex-1">
          <h4 className="text-[13px] font-semibold text-ink">{scenario.title}</h4>
          <div className="mt-1 flex flex-wrap gap-1">
            <Badge tone={scenario.llm === "unavailable" ? "warning" : "neutral"}>
              {LLM_REQUIREMENT[scenario.llm]}
            </Badge>
            {scenario.conversation.length > 1 ? (
              <Badge>{scenario.conversation.length} turns</Badge>
            ) : null}
          </div>
          {customer ? (
            <p className="mt-1.5 line-clamp-2 text-xs text-ink-2">&quot;{customer.text}&quot;</p>
          ) : null}
          <p className="mt-1 text-xs text-ink-3">Expected: {expectationText(scenario)}</p>
        </div>
      </div>
      <div className="mt-2.5 flex flex-wrap justify-end gap-1.5">
        <Button
          size="sm"
          variant="secondary"
          icon={Play}
          onClick={onRun}
          disabled={busy}
          aria-label={`Run scenario ${scenario.id}: ${scenario.title}`}
        >
          Run
        </Button>
      </div>
    </li>
  );
}

// ─── Main component ────────────────────────────────────────────────────────

export function ChatSimulator({
  scenarios,
  scenariosError,
  maxMessageChars,
  model,
}: {
  scenarios: DemoScenario[] | null;
  scenariosError: ErrorInfo | null;
  maxMessageChars: number;
  model: string | null;
}) {
  const [messages, setMessages] = useState<ChatMessage[]>(() => [makeGreeting(0)]);
  const [input, setInput] = useState("");
  const [runState, setRunState] = useState<RunState>("idle");
  const [latestResult, setLatestResult] = useState<ResolveResponse | null>(null);
  const [latestTrace, setLatestTrace] = useState<AgentTrace | null>(null);
  const [latestScenario, setLatestScenario] = useState<DemoScenario | null>(null);
  const [latestStored, setLatestStored] = useState<StoredResult | null>(null);

  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const nextId = useRef(1);
  const stored = useStoredResults();
  const busy = runState === "running";

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  // Auto-resize textarea
  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    const ta = e.target;
    ta.style.height = "auto";
    ta.style.height = `${Math.min(ta.scrollHeight, 160)}px`;
  };

  // Build conversation array from message history
  // NOTE: greeting and error bubbles are UI-only and must NOT be sent to the API.
  const buildConversation = (extraCustomerText?: string): ResolveRequest["conversation"] => {
    const conv: ResolveRequest["conversation"] = [];
    for (const m of messages) {
      if (m.thinking) continue;
      if (m.isGreeting) continue;   // UI greeting — not a real brand turn
      if (m.error) continue;        // error bubbles are not real replies
      if (m.role === "customer") {
        conv.push({ role: "customer", text: m.text });
      } else if (m.role === "agent") {
        conv.push({ role: "brand", text: m.text });
      }
    }
    if (extraCustomerText) {
      conv.push({ role: "customer", text: extraCustomerText });
    }
    return conv;
  };

  const runConversation = async (
    conversation: ResolveRequest["conversation"],
    source: string,
    scenario: DemoScenario | null,
  ) => {
    const controller = new AbortController();
    abortRef.current = controller;
    setRunState("running");

    // Add thinking bubble
    const thinkingId = nextId.current++;
    setMessages((prev) => [...prev, { id: thinkingId, role: "agent", text: "", thinking: true }]);

    try {
      const { data } = await api.resolve({ conversation, metadata: { channel: "web" } }, { signal: controller.signal });
      if (!isResolveResponse(data)) throw new ApiError(200, "invalid_response", "The API response is missing required fields.");

      const entry = saveResult(data, source);
      setLatestStored(entry);
      setLatestResult(data);
      setLatestScenario(scenario);

      // Determine display text for agent bubble — context-aware, friendly openers
      const rawText =
        data.action === "AUTO_HANDLE"
          ? data.response.text
          : data.action === "CLARIFICATION_REQUIRED"
            ? (data.clarification?.question ?? data.response.text)
            : null;

      // Handoff message varies by reason so it never feels generic
      const reasonCode = data.outcome?.reason_code ?? "";
      const handoffText = (() => {
        if (reasonCode === "human_requested")
          return "Of course! Let me get a real person on this for you right away. 👋";
        if (reasonCode === "safety" || reasonCode === "prompt_injection")
          return "I need to involve our support team for this request. They'll be in touch shortly.";
        if (reasonCode === "account_access" || reasonCode === "private_info" || reasonCode === "payment_billing" || reasonCode === "sensitive_action")
          return "For security, account and billing requests need to be handled by our team directly. I'm connecting you now.";
        if (reasonCode === "hardware" || reasonCode === "repeat_contact")
          return "This looks like something our specialist team should handle. I'm passing this over to them now.";
        if (reasonCode === "taxonomy_gap_risk" || reasonCode === "vague_hostile" || reasonCode === "low_confidence" || reasonCode === "insufficient_context")
          return "I'm not sure I can help with that one! For anything outside device and account support, feel free to contact our team directly.";
        // Default warm handoff
        return "Thanks for reaching out. I want to make sure you get the best help possible — let me connect you with one of our support specialists who can take a closer look.";
      })();

      const responseText =
        data.action === "AUTO_HANDLE"
          ? rawText ?? ""
          : data.action === "CLARIFICATION_REQUIRED"
            ? `Happy to help! To make sure I give you the right answer, I have a quick question:\n\n${rawText ?? ""}`
            : handoffText;

      // Fetch trace in background
      let trace: AgentTrace | null = null;
      try {
        trace = (await api.trace(data.trace_id)).data;
      } catch {
        trace = null;
      }
      setLatestTrace(trace);

      // Replace thinking bubble with real response
      setMessages((prev) =>
        prev.map((m) =>
          m.id === thinkingId
            ? { id: thinkingId, role: "agent", text: responseText, result: data, trace }
            : m,
        ),
      );
      setRunState("done");
    } catch (err) {
      if (err instanceof ApiError && err.errorCode === "cancelled") {
        setMessages((prev) => prev.filter((m) => m.id !== thinkingId));
        setRunState("idle");
        return;
      }
      const errorInfo =
        err instanceof ApiError
          ? toErrorInfo(err)
          : { status: 0, errorCode: "client_error", message: String(err) };
      setMessages((prev) =>
        prev.map((m) =>
          m.id === thinkingId
            ? { id: thinkingId, role: "agent", text: "Something went wrong. Please try again.", error: errorInfo }
            : m,
        ),
      );
      setRunState("done");
    } finally {
      abortRef.current = null;
    }
  };

  const sendMessage = (textOverride?: string) => {
    const text = (textOverride ?? input).trim();
    if (!text || busy) return;

    // Add customer message
    setMessages((prev) => [...prev, { id: nextId.current++, role: "customer", text }]);
    setInput("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }

    // Build conversation from history + this new message
    const conv = buildConversation(text);
    void runConversation(conv, "Chat", null);
  };

  const runScenario = async (
    conversation: ResolveRequest["conversation"],
    source: string,
    scenario: DemoScenario | null,
  ) => {
    // Reset and seed the chat with scenario messages
    const newMessages: ChatMessage[] = [];
    for (const turn of conversation.slice(0, -1)) {
      newMessages.push({
        id: nextId.current++,
        role: turn.role === "customer" ? "customer" : "agent",
        text: turn.text,
      });
    }
    const lastTurn = conversation[conversation.length - 1];
    if (lastTurn?.role === "customer") {
      newMessages.push({ id: nextId.current++, role: "customer", text: lastTurn.text });
    }
    setMessages(newMessages);
    setLatestResult(null);
    setLatestTrace(null);

    await runConversation(conversation, source, scenario);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const resetChat = () => {
    abortRef.current?.abort();
    nextId.current = 1;
    setMessages([makeGreeting(0)]);
    setInput("");
    setLatestResult(null);
    setLatestTrace(null);
    setLatestScenario(null);
    setLatestStored(null);
    setRunState("idle");
  };

  // Only count real (non-greeting) messages to decide if the chat has started
  const hasRealMessages = messages.some((m) => !m.isGreeting);

  return (
    <div className="flex flex-col gap-4">
      {/* ── Main two-column layout ── */}
      <div className="grid items-start gap-4 lg:grid-cols-[1fr_300px]">
        {/* ── LEFT: Chat panel ── */}
        <div className="flex flex-col rounded-lg border border-line bg-surface shadow-[0_1px_2px_rgba(15,23,42,0.04)] overflow-hidden" style={{ minHeight: 560 }}>
          {/* Chat header */}
          <div className="flex items-center justify-between border-b border-line px-4 py-3">
            <div className="flex items-center gap-3">
              <div className="flex size-8 items-center justify-center rounded-full border border-[#98A68E]/40 bg-[#586651]/10 text-sm font-bold text-[#586651]">
                R
              </div>
              <div>
                <div className="text-sm font-semibold text-ink">ResolveAI</div>
                <div className="flex items-center gap-1 text-[11px] text-ink-3">
                  <span className="inline-block size-1.5 rounded-full bg-[#3d7a57]" aria-hidden="true" />
                  Online · AI Support Agent
                </div>
              </div>
            </div>
            {hasRealMessages && (
              <Button
                size="sm"
                variant="ghost"
                icon={RotateCcw}
                onClick={resetChat}
                aria-label="New conversation"
              >
                New chat
              </Button>
            )}
          </div>

          {/* Message area */}
          <div
            ref={scrollRef}
            className="flex-1 overflow-y-auto py-2"
            style={{ minHeight: 360, maxHeight: "calc(100vh - 340px)" }}
            aria-label="Conversation"
            aria-live="polite"
          >
            {messages.map((msg) =>
                msg.thinking ? (
                  <ThinkingDots key={msg.id} />
                ) : msg.role === "customer" ? (
                  <CustomerBubble key={msg.id} text={msg.text} />
                ) : (
                  <AgentMessageBubble key={msg.id} msg={msg} />
                ),
              )}
          </div>

          {/* Example chips — always visible above composer */}
          {!hasRealMessages && scenarios && scenarios.length > 0 && (
            <div className="flex flex-wrap items-center gap-2 border-t border-line px-4 py-2">
              <span className="text-[11px] font-medium text-ink-3">Try an example:</span>
              {EXAMPLES.map((ex) => {
                const sc = scenarios.find((s) => s.id === ex.id);
                if (!sc) return null;
                return (
                  <button
                    key={ex.id}
                    type="button"
                    disabled={busy}
                    onClick={() => void runScenario(sc.conversation, `Example: ${ex.label}`, sc)}
                    className="rounded-full border border-line bg-canvas px-3 py-1 text-[11px] text-ink-2 transition-colors hover:border-brand-700/40 hover:bg-surface hover:text-ink disabled:opacity-40"
                  >
                    {ex.label}
                  </button>
                );
              })}
            </div>
          )}

          {/* Composer */}
          <div className="border-t border-line px-4 py-3">
            {busy && (
              <div className="mb-2 flex items-center justify-between text-[11px] text-ink-3">
                <span>ResolveAI is thinking…</span>
                <button
                  type="button"
                  onClick={() => abortRef.current?.abort()}
                  className="flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] text-ink-3 hover:bg-subtle hover:text-ink"
                >
                  <X className="size-3" aria-hidden="true" />
                  Cancel
                </button>
              </div>
            )}
            <div className="flex items-end gap-2 rounded-xl border border-line-strong bg-canvas/60 px-3 py-2 focus-within:border-brand-700/50 focus-within:bg-surface transition-colors">
              <textarea
                ref={textareaRef}
                id="chat-composer"
                value={input}
                onChange={handleInputChange}
                onKeyDown={handleKeyDown}
                disabled={busy}
                rows={1}
                placeholder="Message ResolveAI…"
                aria-label="Message ResolveAI"
                className="flex-1 resize-none bg-transparent text-sm text-ink placeholder:text-ink-3 focus:outline-none disabled:opacity-50"
                style={{ minHeight: "1.5rem", maxHeight: "10rem" }}
              />
              <button
                type="button"
                onClick={() => sendMessage()}
                disabled={busy || !input.trim()}
                aria-label="Send message"
                className="mb-0.5 flex size-7 shrink-0 items-center justify-center rounded-lg bg-[#586651] text-white transition-opacity disabled:opacity-30 hover:bg-[#4a5644]"
              >
                <ArrowUp className="size-4" aria-hidden="true" />
              </button>
            </div>
            <p className="mt-1.5 text-[10px] text-ink-3">
              Enter to send · Shift + Enter for new line
            </p>
          </div>
        </div>

        {/* ── RIGHT: Resolution panel ── */}
        <div className="rounded-lg border border-line bg-surface shadow-[0_1px_2px_rgba(15,23,42,0.04)] lg:sticky lg:top-4">
          <ResolutionPanel result={latestResult} />
        </div>
      </div>

      {/* ── Advanced testing (collapsed) ── */}
      <details className="group rounded-lg border border-line bg-surface shadow-[0_1px_2px_rgba(15,23,42,0.04)]">
        <summary className="flex cursor-pointer list-none items-center justify-between px-4 py-3 select-none">
          <span className="text-sm font-semibold text-ink">Advanced testing</span>
          <ChevronDown
            className="size-4 text-ink-3 transition-transform group-open:rotate-180"
            aria-hidden="true"
          />
        </summary>

        <div className="border-t border-line px-4 pb-4 pt-4 space-y-6">
          {/* Simulation notice */}
          <Notice tone="warning" title="Simulation">
            Messages are processed by your local ResolveAI API
            {model ? ` (model ${model})` : ""}. Nothing is sent to any
            customer or channel. Results are kept in this browser only (last 50)
            so you can reopen them; audit traces on the API never store message
            text.
          </Notice>

          {/* Expected vs actual (when run from scenario) */}
          {latestStored && latestScenario ? (
            <ul
              className="flex w-full flex-wrap gap-x-4 gap-y-1 rounded-md border border-line bg-canvas p-3 text-xs"
              aria-label="Expected versus actual"
            >
              <li className="font-semibold text-ink">Expected versus actual:</li>
              {checkExpectation(latestScenario, latestStored.result).map((c) => (
                <li
                  key={c.label}
                  className={`inline-flex items-center gap-1 ${c.ok ? "font-medium text-success" : "font-medium text-warning"}`}
                >
                  {c.ok ? (
                    <CircleCheck className="size-3.5" aria-hidden="true" />
                  ) : (
                    <CircleX className="size-3.5" aria-hidden="true" />
                  )}
                  {c.label}
                  <span className="sr-only">{c.ok ? " (matches)" : " (differs)"}</span>
                </li>
              ))}
            </ul>
          ) : null}

          {/* Pipeline stepper */}
          {latestStored && latestResult ? (
            <PipelineStepper result={latestResult} trace={latestTrace} />
          ) : null}

          {/* Full conversation workspace */}
          {latestStored ? (
            <ConversationWorkspace
              result={latestStored.result}
              trace={latestTrace}
              savedAt={latestStored.savedAt}
              source={latestStored.source}
            />
          ) : null}

          {/* Curated demo path */}
          <div>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-ink">
              Curated demo path
            </h3>
            <ol
              aria-label="Curated demo path"
              className="grid gap-2.5 md:grid-cols-2 2xl:grid-cols-4"
            >
              {CURATED.map((c) => {
                const scenario = c.api ? (scenarios?.find((s) => s.id === c.api) ?? null) : null;
                return (
                  <CuratedCard
                    key={c.n}
                    item={c}
                    scenario={scenario}
                    busy={busy}
                    onRun={(conv) =>
                      void runScenario(conv, `Curated ${c.n}: ${c.title}`, scenario)
                    }
                  />
                );
              })}
            </ol>
          </div>

          {/* All API demo scenarios */}
          <div>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-ink">
              All API demo scenarios
            </h3>
            {scenariosError ? (
              <ErrorState error={scenariosError} compact />
            ) : scenarios && scenarios.length ? (
              <ul className="grid gap-2.5 md:grid-cols-2">
                {scenarios.map((s) => (
                  <ScenarioCard
                    key={s.id}
                    scenario={s}
                    busy={busy}
                    onRun={() =>
                      void runScenario(s.conversation, `Scenario ${s.id}: ${s.title}`, s)
                    }
                  />
                ))}
              </ul>
            ) : (
              <p className="text-xs text-ink-3">No demo scenarios available.</p>
            )}
          </div>

          {/* Stored results */}
          {stored.length ? (
            <p className="flex flex-wrap items-center gap-2 border-t border-line pt-3 text-xs text-ink-3">
              {stored.length} result{stored.length === 1 ? "" : "s"} stored in this browser.
              <button
                type="button"
                onClick={clearResults}
                className="font-medium text-ink-2 underline hover:text-ink"
              >
                Clear stored results
              </button>
            </p>
          ) : null}
        </div>
      </details>

      {/* Thinking dot animation styles */}
      <style>{`
        .thinking-dot {
          display: inline-block;
          width: 6px;
          height: 6px;
          border-radius: 50%;
          background: #98A68E;
          animation: thinking-pulse 1.2s ease-in-out infinite;
        }
        @keyframes thinking-pulse {
          0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
          30% { transform: translateY(-4px); opacity: 1; }
        }
      `}</style>
    </div>
  );
}
