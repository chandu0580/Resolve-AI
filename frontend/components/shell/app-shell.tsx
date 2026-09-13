"use client";

import { X } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import type { RuntimeInfo } from "@/components/shell/runtime";
import { Sidebar } from "@/components/shell/sidebar";
import { Topbar } from "@/components/shell/topbar";

export function AppShell({ runtime, counts, attention = 0, children }: { runtime: RuntimeInfo; counts?: Record<string, number>; attention?: number; children: ReactNode }) {
  const [drawerOpen, setDrawerOpen] = useState(false);

  useEffect(() => {
    if (!drawerOpen) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setDrawerOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [drawerOpen]);

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[248px_minmax(0,1fr)]">
      <a href="#main" className="sr-only z-50 rounded-md bg-surface px-3 py-2 text-sm focus:not-sr-only focus:fixed focus:top-2 focus:left-2">
        Skip to content
      </a>
      <div className="hidden border-r border-line lg:block">
        <aside className="sticky top-0 h-screen">
          <Sidebar runtime={runtime} counts={counts} />
        </aside>
      </div>
      {drawerOpen ? (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true" aria-label="Navigation">
          <div className="absolute inset-0 bg-ink/30" onClick={() => setDrawerOpen(false)} aria-hidden="true" />
          <div className="absolute inset-y-0 left-0 w-64 max-w-[85vw] bg-surface shadow-xl">
            <button type="button" onClick={() => setDrawerOpen(false)} className="absolute top-3 right-2 rounded-md p-1.5 text-ink-2 hover:bg-subtle" aria-label="Close navigation">
              <X className="size-5" aria-hidden="true" />
            </button>
            <Sidebar runtime={runtime} counts={counts} onNavigate={() => setDrawerOpen(false)} />
          </div>
        </div>
      ) : null}
      <div className="flex min-w-0 flex-col">
        <Topbar runtime={runtime} onMenu={() => setDrawerOpen(true)} attention={attention} />
        <main id="main" className="flex-1 px-4 py-5 sm:px-5 lg:px-6 lg:py-6">
          <div className="mx-auto w-full max-w-[1480px]">{children}</div>
        </main>
      </div>
    </div>
  );
}
