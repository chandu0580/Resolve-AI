"use client";

import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  Clock,
  HelpCircle,
  Plus,
  Search,
  UserCheck,
  UserRound,
} from "lucide-react";
import type { ConversationStatus, SupportConversation } from "./inbox-seed-data";
import { relativeTime } from "@/lib/format";

export type InboxFilter =
  | "all"
  | "ai_handling"
  | "needs_human"
  | "waiting_for_customer"
  | "resolved";

interface InboxListProps {
  conversations: SupportConversation[];
  activeId: string | null;
  filter: InboxFilter;
  query: string;
  onSelect: (id: string) => void;
  onFilterChange: (f: InboxFilter) => void;
  onQueryChange: (q: string) => void;
  onNewConversation?: () => void;
}

export function StatusPill({ status }: { status: ConversationStatus }) {
  switch (status) {
    case "AI_HANDLING":
      return (
        <span className="inline-flex items-center gap-1 rounded-md border border-brand-100 bg-brand-50 px-2 py-0.5 text-[11px] font-medium text-brand-700">
          <Bot className="size-3 text-brand-600" aria-hidden="true" />
          AI handling
        </span>
      );
    case "NEEDS_CLARIFICATION":
      return (
        <span className="inline-flex items-center gap-1 rounded-md border border-warning-line/80 bg-warning-bg px-2 py-0.5 text-[11px] font-medium text-warning">
          <HelpCircle className="size-3 text-warning" aria-hidden="true" />
          Needs clarification
        </span>
      );
    case "NEEDS_HUMAN":
      return (
        <span className="inline-flex items-center gap-1 rounded-md border border-danger-line/70 bg-danger-bg px-2 py-0.5 text-[11px] font-medium text-danger">
          <AlertTriangle className="size-3 text-danger" aria-hidden="true" />
          Needs human
        </span>
      );
    case "WAITING_FOR_CUSTOMER":
      return (
        <span className="inline-flex items-center gap-1 rounded-md border border-line bg-subtle px-2 py-0.5 text-[11px] font-medium text-ink-2">
          <Clock className="size-3 text-ink-3" aria-hidden="true" />
          Waiting for customer
        </span>
      );
    case "HUMAN_HANDLING":
      return (
        <span className="inline-flex items-center gap-1 rounded-md border border-info-line/70 bg-info-bg px-2 py-0.5 text-[11px] font-medium text-info">
          <UserCheck className="size-3 text-info" aria-hidden="true" />
          Human handling
        </span>
      );
    case "RESOLVED":
      return (
        <span className="inline-flex items-center gap-1 rounded-md border border-line bg-subtle px-2 py-0.5 text-[11px] font-medium text-ink-3">
          <CheckCircle2 className="size-3 text-ink-3" aria-hidden="true" />
          Resolved
        </span>
      );
  }
}

export function InboxList({
  conversations,
  activeId,
  filter,
  query,
  onSelect,
  onFilterChange,
  onQueryChange,
  onNewConversation,
}: InboxListProps) {
  // Compute counts strictly from available data
  const counts: Record<InboxFilter, number> = {
    all: conversations.length,
    ai_handling: conversations.filter(
      (c) => c.status === "AI_HANDLING" || c.status === "NEEDS_CLARIFICATION"
    ).length,
    needs_human: conversations.filter(
      (c) => c.status === "NEEDS_HUMAN" || c.status === "HUMAN_HANDLING"
    ).length,
    waiting_for_customer: conversations.filter(
      (c) => c.status === "WAITING_FOR_CUSTOMER"
    ).length,
    resolved: conversations.filter((c) => c.status === "RESOLVED").length,
  };

  const filtered = conversations.filter((c) => {
    if (
      filter === "ai_handling" &&
      c.status !== "AI_HANDLING" &&
      c.status !== "NEEDS_CLARIFICATION"
    )
      return false;
    if (
      filter === "needs_human" &&
      c.status !== "NEEDS_HUMAN" &&
      c.status !== "HUMAN_HANDLING"
    )
      return false;
    if (filter === "waiting_for_customer" && c.status !== "WAITING_FOR_CUSTOMER")
      return false;
    if (filter === "resolved" && c.status !== "RESOLVED") return false;

    if (query.trim()) {
      const q = query.toLowerCase();
      const matchName = c.customerName.toLowerCase().includes(q);
      const matchSubject = c.subject.toLowerCase().includes(q);
      const matchTurns = c.turns.some((t) => t.text.toLowerCase().includes(q));
      if (!matchName && !matchSubject && !matchTurns) return false;
    }
    return true;
  });

  const FILTERS: { key: InboxFilter; label: string }[] = [
    { key: "all", label: "All" },
    { key: "ai_handling", label: "AI handling" },
    { key: "needs_human", label: "Needs human" },
    { key: "waiting_for_customer", label: "Waiting" },
    { key: "resolved", label: "Resolved" },
  ];

  return (
    <div className="flex h-full flex-col border-r border-line bg-surface">
      {/* Inbox Header */}
      <div className="border-b border-line px-3.5 py-3">
        <div className="flex items-center justify-between">
          <h2 className="text-[12px] font-bold tracking-wider text-ink-3 uppercase">
            Conversations
          </h2>
          {onNewConversation && (
            <button
              type="button"
              onClick={onNewConversation}
              className="inline-flex items-center gap-1 rounded bg-brand-50 border border-brand-100 px-2 py-0.5 text-[11px] font-medium text-brand-700 hover:bg-brand-100/70"
              title="Simulate incoming conversation"
            >
              <Plus className="size-3" />
              New
            </button>
          )}
        </div>

        {/* Search */}
        <div className="relative mt-2.5">
          <Search className="pointer-events-none absolute top-2.5 left-2.5 size-3.5 text-ink-3" />
          <input
            type="text"
            value={query}
            onChange={(e) => onQueryChange(e.target.value)}
            placeholder="Search conversations, intents..."
            className="w-full rounded-md border border-line bg-canvas py-1.5 pr-2.5 pl-8 text-[12px] text-ink placeholder:text-ink-3/60 focus:border-brand-600 focus:bg-surface focus:outline-none"
          />
        </div>

        {/* Filter Pills */}
        <div className="mt-2.5 flex flex-wrap gap-1">
          {FILTERS.map((f) => {
            const active = filter === f.key;
            const count = counts[f.key];
            return (
              <button
                key={f.key}
                type="button"
                onClick={() => onFilterChange(f.key)}
                className={`flex items-center gap-1 rounded-md px-2 py-1 text-[11px] font-medium transition-colors ${
                  active
                    ? "bg-brand-700 text-surface shadow-xs"
                    : "bg-canvas text-ink-2 hover:bg-subtle"
                }`}
              >
                <span>{f.label}</span>
                <span
                  className={`tabular text-[10px] ${
                    active ? "text-surface/80" : "text-ink-3"
                  }`}
                >
                  {count}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Conversation Rows List */}
      <div className="flex-1 overflow-y-auto divide-y divide-line/70">
        {filtered.length === 0 ? (
          <div className="p-6 text-center text-[12px] text-ink-3">
            No conversations in this view.
          </div>
        ) : (
          filtered.map((c) => {
            const isSelected = c.id === activeId;
            const lastTurn = c.turns[c.turns.length - 1];
            const isHumanOwned = c.isHumanHandled || c.status === "HUMAN_HANDLING";

            return (
              <button
                key={c.id}
                type="button"
                onClick={() => onSelect(c.id)}
                className={`group block w-full text-left transition-colors ${
                  isSelected
                    ? "bg-brand-50/50 shadow-[inset_3px_0_0_var(--color-brand-600)]"
                    : "hover:bg-canvas"
                }`}
              >
                <div className="px-3.5 py-3">
                  <div className="flex items-center justify-between gap-1.5">
                    <div className="flex items-center gap-1.5 truncate">
                      <div className="flex size-5 shrink-0 items-center justify-center rounded-full bg-subtle text-[10px] font-semibold text-ink-2">
                        {c.customerName.replace("Customer ", "C")}
                      </div>
                      <span className="truncate text-[13px] font-semibold text-ink">
                        {c.customerName}
                      </span>
                    </div>
                    <span className="tabular shrink-0 text-[11px] text-ink-3">
                      {relativeTime(c.lastMessageTime)}
                    </span>
                  </div>

                  <p className="mt-1 line-clamp-1 text-[12px] font-medium text-ink-2">
                    {c.subject}
                  </p>

                  <p className="mt-0.5 line-clamp-2 text-[11px] leading-relaxed text-ink-3">
                    {lastTurn ? lastTurn.text : "No messages yet."}
                  </p>

                  <div className="mt-2 flex items-center justify-between gap-2">
                    <StatusPill status={c.status} />
                    <span className="inline-flex items-center gap-1 text-[10px] font-medium text-ink-3">
                      {isHumanOwned ? (
                        <span className="flex items-center gap-0.5 text-info">
                          <UserRound className="size-3" />
                          Support team
                        </span>
                      ) : (
                        <span className="flex items-center gap-0.5 text-brand-700">
                          <Bot className="size-3" />
                          ResolveAI
                        </span>
                      )}
                    </span>
                  </div>
                </div>
              </button>
            );
          })
        )}
      </div>
    </div>
  );
}
