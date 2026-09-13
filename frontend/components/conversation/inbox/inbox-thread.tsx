"use client";

import {
  AlertTriangle,
  Bot,
  CheckCircle,
  CornerDownLeft,
  Send,
  ShieldAlert,
  Sparkles,
  UserCheck,
  UserRound,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { SupportConversation } from "./inbox-seed-data";
import { StatusPill } from "./inbox-list";
import { dateTime, relativeTime } from "@/lib/format";

interface InboxThreadProps {
  conversation: SupportConversation;
  isAnalyzing: boolean;
  onSendMessage: (text: string, asCustomer: boolean) => void;
  onTakeOver: () => void;
  onReturnToAi: () => void;
  onToggleResolved: () => void;
}

export function InboxThread({
  conversation,
  isAnalyzing,
  onSendMessage,
  onTakeOver,
  onReturnToAi,
  onToggleResolved,
}: InboxThreadProps) {
  const [inputText, setInputText] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const isHumanActive =
    conversation.isHumanHandled || conversation.status === "HUMAN_HANDLING";

  // Auto-scroll to bottom on new message or thinking state
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [conversation.turns, isAnalyzing]);

  const handleSend = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!inputText.trim() || isAnalyzing) return;

    // If human agent took over, message is sent as human agent ("Support team")
    // If AI is handling, message is sent as customer to test/drive the conversation
    onSendMessage(inputText.trim(), !isHumanActive);
    setInputText("");
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex h-full flex-col bg-surface">
      {/* Thread Header */}
      <div className="flex shrink-0 items-center justify-between border-b border-line px-5 py-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h1 className="truncate text-[15px] font-semibold text-ink">
              {conversation.customerName}
            </h1>
            <span className="text-ink-3">·</span>
            <span className="truncate text-[13px] font-medium text-ink-2">
              {conversation.subject}
            </span>
          </div>
          <div className="mt-0.5 flex items-center gap-2 text-[11px] text-ink-3">
            <span className="font-medium">Apple Support · {conversation.channel.toUpperCase()}</span>
            <span>·</span>
            <span>Started {dateTime(conversation.startedAt)}</span>
          </div>
        </div>

        {/* Header Action Controls */}
        <div className="flex shrink-0 items-center gap-2">
          <StatusPill status={conversation.status} />

          {isHumanActive ? (
            <button
              type="button"
              onClick={onReturnToAi}
              className="inline-flex items-center gap-1.5 rounded-md border border-line bg-canvas px-2.5 py-1 text-[12px] font-medium text-ink hover:bg-subtle transition-colors"
            >
              <Bot className="size-3.5 text-brand-600" />
              Return to AI
            </button>
          ) : (
            <button
              type="button"
              onClick={onTakeOver}
              className="inline-flex items-center gap-1.5 rounded-md border border-line bg-canvas px-2.5 py-1 text-[12px] font-medium text-ink hover:bg-subtle transition-colors"
            >
              <UserCheck className="size-3.5 text-info" />
              Take over
            </button>
          )}

          <button
            type="button"
            onClick={onToggleResolved}
            className={`inline-flex items-center gap-1 rounded-md px-2.5 py-1 text-[12px] font-medium transition-colors ${
              conversation.status === "RESOLVED"
                ? "border border-line bg-subtle text-ink-2 hover:bg-canvas"
                : "border border-line bg-canvas text-ink-2 hover:bg-subtle"
            }`}
          >
            <CheckCircle className="size-3.5 text-brand-600" />
            {conversation.status === "RESOLVED" ? "Reopen" : "Resolve"}
          </button>
        </div>
      </div>

      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto p-5 space-y-4">
        {conversation.turns.map((turn, index) => {
          if (turn.role === "customer") {
            return (
              <div key={turn.id || index} className="flex gap-3 max-w-[82%]">
                <div className="flex size-7 shrink-0 items-center justify-center rounded-full bg-subtle border border-line text-[11px] font-semibold text-ink-2">
                  C
                </div>
                <div>
                  <div className="mb-1 flex items-center gap-2 text-[11px] text-ink-3">
                    <span className="font-semibold text-ink-2">
                      {conversation.customerName}
                    </span>
                    <span>{relativeTime(turn.timestamp)}</span>
                  </div>
                  <div className="rounded-xl rounded-tl-sm border border-line/90 bg-canvas px-4 py-2.5 text-[13px] leading-relaxed text-ink shadow-2xs">
                    {turn.text}
                  </div>
                </div>
              </div>
            );
          }

          if (turn.role === "brand") {
            return (
              <div
                key={turn.id || index}
                className="flex flex-row-reverse gap-3 max-w-[85%] ml-auto"
              >
                <div className="flex size-7 shrink-0 items-center justify-center rounded-full bg-brand-50 border border-brand-100 text-brand-700">
                  <Bot className="size-4" />
                </div>
                <div className="flex flex-col items-end">
                  <div className="mb-1 flex items-center gap-2 text-[11px] text-ink-3">
                    <span className="inline-flex items-center gap-1 font-semibold text-brand-700">
                      <Sparkles className="size-3" />
                      ResolveAI
                    </span>
                    <span>{relativeTime(turn.timestamp)}</span>
                  </div>
                  <div className="rounded-xl rounded-tr-sm border border-brand-100 bg-brand-50/30 px-4 py-2.5 text-[13px] leading-relaxed text-ink shadow-2xs">
                    {turn.text}
                  </div>
                </div>
              </div>
            );
          }

          // Human agent turn
          return (
            <div
              key={turn.id || index}
              className="flex flex-row-reverse gap-3 max-w-[85%] ml-auto"
            >
              <div className="flex size-7 shrink-0 items-center justify-center rounded-full bg-info-bg border border-info-line text-info">
                <UserRound className="size-4" />
              </div>
              <div className="flex flex-col items-end">
                <div className="mb-1 flex items-center gap-2 text-[11px] text-ink-3">
                  <span className="font-semibold text-info">Support team (You)</span>
                  <span>{relativeTime(turn.timestamp)}</span>
                </div>
                <div className="rounded-xl rounded-tr-sm border border-info-line/70 bg-info-bg/30 px-4 py-2.5 text-[13px] leading-relaxed text-ink shadow-2xs">
                  {turn.text}
                </div>
              </div>
            </div>
          );
        })}

        {/* In-Thread Handoff Notice */}
        {conversation.status === "NEEDS_HUMAN" && !isHumanActive && (
          <div className="my-3 rounded-lg border border-danger-line bg-danger-bg/60 p-4 text-ink shadow-2xs">
            <div className="flex items-start gap-3">
              <ShieldAlert className="mt-0.5 size-5 shrink-0 text-danger" />
              <div className="flex-1">
                <h4 className="text-[13px] font-semibold text-danger">
                  ResolveAI handed this conversation to a human support specialist.
                </h4>
                <p className="mt-1 text-[12px] leading-relaxed text-ink-2">
                  {conversation.handoffReason ||
                    "This request involves account security, hardware damage, or exceeds safe automated boundaries."}
                </p>
                {conversation.handoffNextStep && (
                  <p className="mt-1 text-[11px] font-medium text-ink-3">
                    Recommended action: {conversation.handoffNextStep}
                  </p>
                )}
                <div className="mt-3">
                  <button
                    type="button"
                    onClick={onTakeOver}
                    className="inline-flex items-center gap-1.5 rounded-md bg-danger px-3 py-1.5 text-[12px] font-semibold text-surface hover:opacity-90 transition-opacity"
                  >
                    <UserCheck className="size-3.5" />
                    Take over conversation
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* In-Thread Takeover Indicator */}
        {isHumanActive && (
          <div className="my-2 flex items-center justify-center gap-2 text-[11px] font-medium text-info">
            <span className="h-px w-12 bg-info-line" />
            <span className="inline-flex items-center gap-1">
              <UserCheck className="size-3.5" />
              Support team took over this conversation
            </span>
            <span className="h-px w-12 bg-info-line" />
          </div>
        )}

        {/* Subtle Thinking State */}
        {isAnalyzing && (
          <div className="flex flex-row-reverse gap-3 max-w-[85%] ml-auto">
            <div className="flex size-7 shrink-0 items-center justify-center rounded-full bg-brand-50 border border-brand-100 text-brand-700">
              <Bot className="size-4" />
            </div>
            <div className="flex flex-col items-end">
              <div className="mb-1 text-[11px] font-medium text-brand-700">
                ResolveAI
              </div>
              <div className="flex items-center gap-2 rounded-xl rounded-tr-sm border border-brand-100 bg-brand-50/40 px-4 py-2.5 text-[13px] text-ink-2 shadow-2xs">
                <span>ResolveAI is thinking</span>
                <span className="inline-flex gap-1">
                  <span className="size-1.5 animate-bounce rounded-full bg-brand-600 [animation-delay:-0.3s]" />
                  <span className="size-1.5 animate-bounce rounded-full bg-brand-600 [animation-delay:-0.15s]" />
                  <span className="size-1.5 animate-bounce rounded-full bg-brand-600" />
                </span>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Enterprise Message Composer */}
      <div className="border-t border-line bg-canvas/60 p-4">
        <form onSubmit={handleSend} className="space-y-2">
          {/* Mode Indicator */}
          <div className="flex items-center justify-between text-[11px] text-ink-3">
            {isHumanActive ? (
              <span className="inline-flex items-center gap-1.5 font-medium text-info">
                <UserRound className="size-3.5" />
                Support team mode active · Replying as Human Agent
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 font-medium text-brand-700">
                <Bot className="size-3.5" />
                AI handling active · Type message to continue conversation
              </span>
            )}

            {!isHumanActive && (
              <button
                type="button"
                onClick={onTakeOver}
                className="text-info hover:underline font-medium"
              >
                Take over as human
              </button>
            )}
          </div>

          {/* Textarea */}
          <div className="relative rounded-lg border border-line bg-surface shadow-2xs focus-within:border-brand-600">
            <textarea
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isAnalyzing}
              placeholder={
                isHumanActive
                  ? "Write a reply to customer... (Press Enter to send, Shift+Enter for new line)"
                  : "Write a message... (Press Enter to send, Shift+Enter for new line)"
              }
              rows={3}
              className="w-full resize-none bg-transparent p-3 text-[13px] text-ink placeholder:text-ink-3/60 focus:outline-none disabled:opacity-50"
            />

            <div className="flex items-center justify-between border-t border-line/60 px-3 py-2 bg-canvas/30">
              <span className="text-[11px] text-ink-3">
                Press <kbd className="rounded border border-line bg-surface px-1 py-0.5 text-[10px] font-mono">Enter ↵</kbd> to send
              </span>

              <button
                type="submit"
                disabled={!inputText.trim() || isAnalyzing}
                className="inline-flex items-center gap-1.5 rounded-md bg-brand-700 px-4 py-1.5 text-[12px] font-medium text-surface hover:bg-brand-900 transition-colors disabled:opacity-40"
              >
                <Send className="size-3.5" />
                Send
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}
