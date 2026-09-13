"use client";

import { ArrowUp, RotateCcw, UserRound } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { BrandMark } from "@/components/shell/sidebar";
import { api } from "@/lib/api/client";
import type { ResolveResponse } from "@/lib/api/types";
import { intentLabel } from "@/lib/labels";

interface Turn {
  role: "customer" | "brand";
  text: string;
  /** Present on agent turns: what the agent decided, for the behind-the-scenes panel. */
  result?: ResolveResponse;
}

const SUGGESTIONS = [
  "My iPhone is not turning on",
  "My battery drains very quickly since the update",
  "I can't log into my Apple ID",
  "Can I talk to a human?",
];

const DECISION_COPY: Record<string, { label: string; tone: string; note: string }> = {
  AUTO_HANDLE: { label: "Resolved automatically", tone: "bg-success-bg text-success", note: "Historical cases supported this answer." },
  CLARIFICATION_REQUIRED: { label: "Asked for detail", tone: "bg-warning-bg text-warning", note: "Not enough to answer safely yet." },
  HUMAN_HANDOFF: { label: "Handed to a person", tone: "bg-danger-bg text-danger", note: "A teammate takes over with full context." },
};

/**
 * The customer-facing surface: what someone contacting support would actually see. It calls the same `/api/v1/resolve`
 * endpoint the operator console uses, so every reply here is the agent's real output — never a script.
 */
export function CustomerChat() {
  const [turns, setTurns] = useState<Turn[]>([{ role: "brand", text: "Hi! What can we help you with today?" }]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns, busy]);

  const latest = [...turns].reverse().find((t) => t.result)?.result ?? null;

  async function send(text: string) {
    const message = text.trim();
    if (!message || busy) return;
    setError(null);
    setDraft("");
    const history: Turn[] = [...turns, { role: "customer", text: message }];
    setTurns(history);
    try {
      // The agent needs the thread, so short replies ("still happening") keep the issue they answer.
      const conversation = history.filter((t) => t.text).map((t) => ({ role: t.role, text: t.text }));
      const res = await api.resolve({ conversation });
      setTurns((prev) => [...prev, { role: "brand", text: res.data.response.text, result: res.data }]);
    } catch {
      setError("We couldn't reach support just now. Please try again.");
    } finally {
      setBusy(false);
      inputRef.current?.focus();
    }
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_300px] lg:items-start">
      <section aria-label="Chat with ResolveAI support" className="flex h-[560px] min-w-0 flex-col overflow-hidden rounded-xl border border-line bg-surface">
        <header className="flex shrink-0 items-center gap-2.5 border-b border-line px-4 py-3">
          <BrandMark className="size-7" />
          <div className="min-w-0 flex-1 leading-tight">
            <div className="text-[13px] font-semibold text-ink">ResolveAI Support</div>
            <div className="flex items-center gap-1.5 text-[11px] text-ink-3">
              <span className="size-1.5 rounded-full bg-brand-600" aria-hidden="true" /> Online
            </div>
          </div>
          <button
            type="button"
            onClick={() => {
              setTurns([{ role: "brand", text: "Hi! What can we help you with today?" }]);
              setError(null);
            }}
            className="rounded-md p-1.5 text-ink-3 hover:bg-subtle hover:text-ink-2"
            title="Start a new conversation"
          >
            <RotateCcw className="size-4" aria-hidden="true" />
            <span className="sr-only">Start a new conversation</span>
          </button>
        </header>

        <div className="min-h-0 flex-1 space-y-3 overflow-y-auto px-4 py-4" role="log" aria-live="polite" aria-label="Conversation">
          {turns.map((t, i) => (
            <div key={i} className={`flex gap-2.5 ${t.role === "customer" ? "flex-row-reverse" : ""}`}>
              <span
                className={`flex size-7 shrink-0 items-center justify-center rounded-full ${t.role === "customer" ? "bg-subtle" : "bg-brand-50"}`}
                aria-hidden="true"
              >
                {t.role === "customer" ? <UserRound className="size-3.5 text-ink-3" /> : <BrandMark className="size-5" />}
              </span>
              <div className={`min-w-0 max-w-[78%] ${t.role === "customer" ? "text-right" : ""}`}>
                <div className="mb-0.5 text-[11px] text-ink-3">{t.role === "customer" ? "You" : "ResolveAI"}</div>
                <div
                  className={`inline-block rounded-xl px-3 py-2 text-[13px] leading-relaxed ${
                    t.role === "customer" ? "bg-brand-700 text-white" : "bg-canvas text-ink"
                  }`}
                >
                  {t.text}
                </div>
                {t.result && t.result.action === "HUMAN_HANDOFF" ? (
                  <div className="mt-1 text-[11px] text-ink-3">This conversation is now with a support teammate.</div>
                ) : null}
              </div>
            </div>
          ))}
          {busy ? (
            <div className="flex gap-2.5">
              <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-brand-50" aria-hidden="true">
                <BrandMark className="size-5" />
              </span>
              <div className="rounded-xl bg-canvas px-3 py-2.5" aria-label="ResolveAI is replying">
                <span className="flex gap-1">
                  {[0, 150, 300].map((d) => (
                    <span key={d} className="size-1.5 animate-bounce rounded-full bg-ink-3" style={{ animationDelay: `${d}ms` }} />
                  ))}
                </span>
              </div>
            </div>
          ) : null}
          {error ? <p className="text-[12px] text-danger">{error}</p> : null}
          <div ref={endRef} />
        </div>

        {turns.length === 1 && !busy ? (
          <div className="shrink-0 border-t border-line px-4 pt-3">
            <div className="flex flex-wrap gap-1.5">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => send(s)}
                  className="rounded-full border border-line px-2.5 py-1 text-[12px] text-ink-2 hover:border-brand-500 hover:text-ink"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : null}

        <form
          className="flex shrink-0 items-center gap-2 border-t border-line px-4 py-3"
          onSubmit={(e) => {
            e.preventDefault();
            send(draft);
          }}
        >
          <label htmlFor="chat-input" className="sr-only">
            Type your message
          </label>
          <input
            ref={inputRef}
            id="chat-input"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Type your message…"
            autoComplete="off"
            className="h-10 min-w-0 flex-1 rounded-lg border border-line bg-canvas px-3 text-[13px] text-ink placeholder:text-ink-3 focus:border-brand-500 focus:bg-surface"
          />
          <button
            type="submit"
            disabled={busy || !draft.trim()}
            className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-brand-700 text-white disabled:opacity-40"
          >
            <ArrowUp className="size-4" aria-hidden="true" />
            <span className="sr-only">Send</span>
          </button>
        </form>
      </section>

      <aside aria-label="What ResolveAI did" className="min-w-0 rounded-xl border border-line bg-surface p-4">
        <h2 className="text-[13px] font-semibold text-ink">Behind this reply</h2>
        <p className="mt-1 text-[11px] leading-snug text-ink-3">The customer never sees this. Your support team does.</p>
        {latest ? (
          <dl className="mt-4 space-y-3.5">
            <div>
              <dt className="text-[11px] text-ink-3">Decision</dt>
              <dd className="mt-1">
                <span className={`rounded-md px-2 py-0.5 text-[12px] font-medium ${DECISION_COPY[latest.action].tone}`}>{DECISION_COPY[latest.action].label}</span>
                <p className="mt-1.5 text-[11px] leading-snug text-ink-3">{DECISION_COPY[latest.action].note}</p>
              </dd>
            </div>
            <div>
              <dt className="text-[11px] text-ink-3">Intent</dt>
              <dd className="mt-0.5 text-[13px] text-ink">{intentLabel(latest.intent.intent)}</dd>
            </div>
            <div>
              <dt className="text-[11px] text-ink-3">Evidence</dt>
              <dd className="mt-0.5 text-[13px] text-ink">
                {latest.evidence.n_retrieved
                  ? `${latest.response.evidence_refs.length} of ${latest.evidence.n_retrieved} cases used`
                  : "No historical cases needed"}
              </dd>
            </div>
            <div>
              <dt className="text-[11px] text-ink-3">Why</dt>
              <dd className="mt-0.5 text-[12px] leading-snug text-ink-2">{latest.outcome.why}</dd>
            </div>
            <a href={`/conversations/${latest.trace_id}`} className="block text-[12px] font-medium text-brand-700 hover:underline">
              Open in the workspace →
            </a>
          </dl>
        ) : (
          <p className="mt-4 text-[12px] leading-snug text-ink-3">Send a message and the intent, evidence and decision behind the reply appear here.</p>
        )}
      </aside>
    </div>
  );
}
