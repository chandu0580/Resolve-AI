"use client";

import { Bell, Menu, Search } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import type { RuntimeInfo } from "@/components/shell/runtime";

export const TRACE_ID_RE = /^[a-f0-9]{32}$/;

/** Live agent state, from /ready and /config — never a decorative "online" light. */
function AgentPill({ runtime }: { runtime: RuntimeInfo }) {
  const online = runtime.apiVersion !== null;
  return (
    <span
      className="hidden items-center gap-1.5 rounded-full border border-line bg-surface px-2.5 py-1 text-[12px] font-medium text-ink-2 sm:inline-flex"
      title={online ? "The agent API is reachable from this console" : "The agent API is not reachable"}
    >
      <span className={`size-1.5 rounded-full ${online ? "bg-brand-600" : "bg-danger"}`} aria-hidden="true" />
      {online ? "AI Agent Online" : "AI Agent Offline"}
    </span>
  );
}

export function Topbar({ runtime, onMenu, attention = 0 }: { runtime: RuntimeInfo; onMenu: () => void; attention?: number }) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const input = useRef<HTMLInputElement>(null);

  // Ctrl/Cmd-K focuses search, the shortcut the placeholder advertises.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        input.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <header className="sticky top-0 z-30 flex h-16 shrink-0 items-center gap-3 border-b border-line bg-canvas/95 px-4 backdrop-blur lg:px-6">
      <button type="button" onClick={onMenu} className="-ml-1 rounded-md p-1.5 text-ink-2 hover:bg-subtle lg:hidden" aria-label="Open navigation">
        <Menu className="size-5" aria-hidden="true" />
      </button>
      <form
        role="search"
        className="relative min-w-0 flex-1 sm:max-w-md"
        onSubmit={(e) => {
          e.preventDefault();
          const q = query.trim();
          if (!q) return;
          router.push(TRACE_ID_RE.test(q.toLowerCase()) ? `/traces/${q.toLowerCase()}` : `/conversations?q=${encodeURIComponent(q)}`);
        }}
      >
        <label htmlFor="global-search" className="sr-only">
          Search conversations and intents, or paste a trace id
        </label>
        <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-ink-3" aria-hidden="true" />
        <input
          ref={input}
          id="global-search"
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search conversations, intents, or customers…"
          className="h-10 w-full rounded-lg border border-line bg-surface pr-16 pl-9 text-[13px] text-ink placeholder:text-ink-3 focus:border-brand-500"
        />
        <kbd className="pointer-events-none absolute top-1/2 right-3 hidden -translate-y-1/2 rounded border border-line bg-canvas px-1.5 py-0.5 text-[11px] font-medium text-ink-3 sm:block">
          Ctrl K
        </kbd>
      </form>
      <div className="ml-auto flex shrink-0 items-center gap-2 sm:gap-3">
        <AgentPill runtime={runtime} />
        <Link
          href="/handoffs"
          className="relative rounded-lg border border-line bg-surface p-2 text-ink-2 hover:bg-subtle"
          title={attention ? `${attention} conversations waiting for a person` : "Nothing waiting for a person"}
        >
          <Bell className="size-4" aria-hidden="true" />
          {attention ? <span className="absolute top-1.5 right-1.5 size-1.5 rounded-full bg-danger" aria-hidden="true" /> : null}
          <span className="sr-only">{attention ? `${attention} conversations waiting for a person` : "Handoff queue"}</span>
        </Link>
        <div className="flex items-center gap-2">
          <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-brand-100 text-[12px] font-semibold text-brand-700" aria-hidden="true">
            OP
          </span>
          <div className="hidden leading-tight md:block">
            <div className="text-[13px] font-medium text-ink">Operator</div>
            <div className="text-[11px] text-ink-3">{runtime.env ? `${runtime.env} environment` : "Local"}</div>
          </div>
        </div>
      </div>
    </header>
  );
}
