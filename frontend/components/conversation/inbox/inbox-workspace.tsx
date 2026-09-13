"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  InboxFilter,
  InboxList,
} from "./inbox-list";
import { InboxThread } from "./inbox-thread";
import { InboxAiPanel } from "./inbox-ai-panel";
import {
  ConversationStatus,
  SEED_CONVERSATIONS,
  SupportConversation,
  buildConversationsFromTraces,
} from "./inbox-seed-data";
import { api } from "@/lib/api/client";
import type { TraceSummary } from "@/lib/api/types";
import { saveResult } from "@/lib/results-store";
import { useHydrated } from "@/lib/use-hydrated";
import { SkeletonRows } from "@/components/ui/states";

interface InboxWorkspaceProps {
  initialTraceId?: string;
  traces: TraceSummary[] | null;
}

export function InboxWorkspace({ initialTraceId, traces }: InboxWorkspaceProps) {
  const hydrated = useHydrated();

  // Master conversations state
  const [conversations, setConversations] = useState<SupportConversation[]>(() => {
    return buildConversationsFromTraces(traces, SEED_CONVERSATIONS);
  });

  const [activeId, setActiveId] = useState<string>(() => {
    if (initialTraceId) {
      const match = conversations.find(
        (c) => c.traceId === initialTraceId || c.id === initialTraceId || c.id === `trace-${initialTraceId}`
      );
      if (match) return match.id;
    }
    return conversations[0]?.id || "case-001";
  });

  const [filter, setFilter] = useState<InboxFilter>("all");
  const [query, setQuery] = useState("");
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const analyzedRef = useRef<Set<string>>(new Set());

  // Active conversation
  const activeConversation = useMemo(() => {
    return conversations.find((c) => c.id === activeId) || conversations[0] || null;
  }, [conversations, activeId]);

  // Execute ResolveAI analysis on a conversation with full multi-turn context
  const analyzeConversation = useCallback(
    async (convId: string, currentTurns?: SupportConversation["turns"]) => {
      const target = conversations.find((c) => c.id === convId);
      if (!target) return;

      const turnsToAnalyze = currentTurns || target.turns;
      const lastTurn = turnsToAnalyze[turnsToAnalyze.length - 1];
      if (!lastTurn || lastTurn.role !== "customer") return;

      // Map turns for the backend: customer or brand
      const apiTurns = turnsToAnalyze.map((t) => ({
        role: (t.role === "human_agent" ? "brand" : t.role) as "customer" | "brand",
        text: t.text,
      }));

      setIsAnalyzing(true);
      try {
        const res = await api.resolve({
          conversation: apiTurns,
          metadata: { channel: target.channel },
        });

        // Save trace in browser results store
        saveResult(res.data, "support-inbox");

        // Prepare resulting AI turn
        const aiResponseText = res.data.response.text;
        const aiTurn = {
          id: `m-ai-${Date.now()}`,
          role: "brand" as const,
          text: aiResponseText,
          timestamp: new Date().toISOString(),
        };

        setConversations((prev) =>
          prev.map((c) => {
            if (c.id !== convId) return c;

            let newStatus: ConversationStatus = c.status;
            if (!c.isHumanHandled) {
              if (res.data.action === "HUMAN_HANDOFF") newStatus = "NEEDS_HUMAN";
              else if (res.data.action === "CLARIFICATION_REQUIRED") newStatus = "NEEDS_CLARIFICATION";
              else if (res.data.action === "AUTO_HANDLE") newStatus = "AI_HANDLING";
            }

            // Append AI response turn if it isn't already the last turn
            const existingTurns = currentTurns || c.turns;
            const updatedTurns = [...existingTurns, aiTurn];

            return {
              ...c,
              traceId: res.data.trace_id,
              status: newStatus,
              turns: updatedTurns,
              lastMessageTime: aiTurn.timestamp,
              resolveResponse: res.data,
              handoffReason: res.data.handoff?.reason?.reason || res.data.outcome.why,
              handoffNextStep: res.data.handoff?.recommended_next_action || res.data.outcome.next_step,
            };
          })
        );
      } catch (err) {
        console.error("ResolveAI analysis failed:", err);
      } finally {
        setIsAnalyzing(false);
      }
    },
    [conversations]
  );

  // Proactively analyze active conversation if it only has an initial customer turn and no AI response yet
  useEffect(() => {
    if (!activeConversation) return;
    if (activeConversation.resolveResponse) return;
    if (activeConversation.isHumanHandled) return;

    // Check if the conversation ends with a customer turn needing an AI response
    const lastTurn = activeConversation.turns[activeConversation.turns.length - 1];
    if (lastTurn && lastTurn.role === "customer" && !analyzedRef.current.has(activeConversation.id)) {
      analyzedRef.current.add(activeConversation.id);
      analyzeConversation(activeConversation.id);
    }
  }, [activeConversation, analyzeConversation]);

  // Handle sending a new message (either customer follow-up or human agent reply)
  const handleSendMessage = async (text: string, asCustomer: boolean) => {
    if (!activeConversation) return;

    const newTurn = {
      id: `m-${Date.now()}`,
      role: asCustomer ? ("customer" as const) : ("human_agent" as const),
      text,
      timestamp: new Date().toISOString(),
    };

    const updatedTurns = [...activeConversation.turns, newTurn];

    // Optimistically update thread
    setConversations((prev) =>
      prev.map((c) => {
        if (c.id !== activeConversation.id) return c;
        return {
          ...c,
          turns: updatedTurns,
          lastMessageTime: newTurn.timestamp,
        };
      })
    );

    // If customer sent a message, call the real ResolveAI API with full multi-turn context
    if (asCustomer && !activeConversation.isHumanHandled) {
      await analyzeConversation(activeConversation.id, updatedTurns);
    }
  };

  // Human takeover
  const handleTakeOver = () => {
    if (!activeConversation) return;

    setConversations((prev) =>
      prev.map((c) => {
        if (c.id !== activeConversation.id) return c;
        return {
          ...c,
          status: "HUMAN_HANDLING",
          isHumanHandled: true,
        };
      })
    );
  };

  // Return to AI supervision
  const handleReturnToAi = () => {
    if (!activeConversation) return;

    setConversations((prev) =>
      prev.map((c) => {
        if (c.id !== activeConversation.id) return c;
        let returnStatus: ConversationStatus = "AI_HANDLING";
        if (c.resolveResponse?.action === "HUMAN_HANDOFF") returnStatus = "NEEDS_HUMAN";
        else if (c.resolveResponse?.action === "CLARIFICATION_REQUIRED") returnStatus = "NEEDS_CLARIFICATION";

        return {
          ...c,
          status: returnStatus,
          isHumanHandled: false,
        };
      })
    );
  };

  // Mark resolved / Reopen
  const handleToggleResolved = () => {
    if (!activeConversation) return;

    setConversations((prev) =>
      prev.map((c) => {
        if (c.id !== activeConversation.id) return c;
        const newStatus = c.status === "RESOLVED" ? "AI_HANDLING" : "RESOLVED";
        return {
          ...c,
          status: newStatus,
        };
      })
    );
  };

  // Create new incoming conversation simulation
  const handleNewConversation = () => {
    const nextNum = String(conversations.length + 1).padStart(3, "0");
    const newConv: SupportConversation = {
      id: `case-${nextNum}`,
      traceId: null,
      customerName: `Customer ${nextNum}`,
      subject: "New incoming customer inquiry",
      channel: "web",
      status: "AI_HANDLING",
      startedAt: new Date().toISOString(),
      lastMessageTime: new Date().toISOString(),
      turns: [
        {
          id: `m-init-${Date.now()}`,
          role: "customer",
          text: "Hi, I have a question about updating my iOS device.",
          timestamp: new Date().toISOString(),
        },
      ],
      resolveResponse: null,
      isHumanHandled: false,
    };

    setConversations((prev) => [newConv, ...prev]);
    setActiveId(newConv.id);
  };

  if (!hydrated) {
    return <SkeletonRows rows={8} />;
  }

  return (
    <div className="h-[calc(100vh-7.5rem)] rounded-xl border border-line bg-surface shadow-2xs overflow-hidden flex flex-col lg:flex-row">
      {/* COLUMN 1: LEFT - INBOX LIST */}
      <div className="w-full lg:w-[310px] xl:w-[330px] shrink-0 h-1/3 lg:h-full">
        <InboxList
          conversations={conversations}
          activeId={activeId}
          filter={filter}
          query={query}
          onSelect={setActiveId}
          onFilterChange={setFilter}
          onQueryChange={setQuery}
          onNewConversation={handleNewConversation}
        />
      </div>

      {/* COLUMN 2: CENTER - MODERN CHAT THREAD */}
      {activeConversation ? (
        <div className="flex-1 min-w-0 h-1/2 lg:h-full border-t lg:border-t-0 border-line">
          <InboxThread
            conversation={activeConversation}
            isAnalyzing={isAnalyzing}
            onSendMessage={handleSendMessage}
            onTakeOver={handleTakeOver}
            onReturnToAi={handleReturnToAi}
            onToggleResolved={handleToggleResolved}
          />
        </div>
      ) : (
        <div className="flex-1 flex items-center justify-center p-8 text-[13px] text-ink-3">
          Select a customer conversation to view message history and ResolveAI intelligence.
        </div>
      )}

      {/* COLUMN 3: RIGHT - RESOLVEAI INTELLIGENCE SIDEBAR */}
      {activeConversation && (
        <div className="w-full lg:w-[350px] xl:w-[380px] shrink-0 h-auto lg:h-full border-t lg:border-t-0 border-line">
          <InboxAiPanel
            conversation={activeConversation}
            isAnalyzing={isAnalyzing}
            onTakeOver={handleTakeOver}
          />
        </div>
      )}
    </div>
  );
}
