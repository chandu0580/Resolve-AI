"use client";

import { ChevronDown, ChevronRight } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { AgentStatus } from "@/components/shell/agent-status";
import { NAV, isActive } from "@/components/shell/nav";
import type { RuntimeInfo } from "@/components/shell/runtime";

/** ResolveAI's mark: a leaf, drawn rather than imported so the shell has no image dependency. */
export function BrandMark({ className = "size-7" }: { className?: string }) {
  return (
    <svg viewBox="0 0 28 28" className={`${className} shrink-0`} aria-hidden="true">
      <rect width="28" height="28" rx="8" className="fill-brand-50" />
      <path d="M20.5 7.5c0 6.2-3.6 10.2-8.4 10.2-1.3 0-2.4-.3-3.3-.8 1-4.9 4.9-8.4 11.7-9.4Z" className="fill-brand-600" />
      <path d="M7.5 20.5c1.2-4.6 4.4-8.2 9.3-10.4" fill="none" stroke="currentColor" className="text-brand-50" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

/**
 * The brand this deployment serves. ResolveAI is built and evaluated for one brand (AppleSupport) by design, so this is a
 * label, not a switcher: there is no second corpus to switch to and pretending otherwise would be a fake control.
 */
function WorkspaceLabel() {
  return (
    <div className="mx-2.5 mt-3 flex items-center gap-2.5 rounded-lg border border-line bg-surface px-2.5 py-2">
      <span className="flex size-6 shrink-0 items-center justify-center rounded-md bg-ink text-[11px] font-semibold text-surface">A</span>
      <span className="min-w-0 flex-1 truncate text-[13px] font-medium text-ink">Apple Support</span>
      <ChevronDown className="size-3.5 shrink-0 text-ink-3" aria-hidden="true" />
      <span className="sr-only">The only brand this deployment is trained and evaluated for</span>
    </div>
  );
}

export function Sidebar({ counts, onNavigate }: { runtime?: RuntimeInfo; counts?: Record<string, number>; onNavigate?: () => void }) {
  const pathname = usePathname();

  // Identify which group contains the current active route
  const activeGroup = NAV.find((g) => g.items.some((item) => isActive(pathname, item.href)))?.group ?? "Workspace";

  // Track which pathname last auto-opened its activeGroup
  const [lastActivePath, setLastActivePath] = useState(pathname);
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>(() => ({
    [activeGroup]: true,
  }));

  // Auto-expand group of new route when user navigates, preserving previously opened groups
  if (lastActivePath !== pathname) {
    setLastActivePath(pathname);
    setOpenGroups((prev) => ({
      ...prev,
      [activeGroup]: true,
    }));
  }

  const toggleGroup = (groupName: string) => {
    setOpenGroups((prev) => ({
      ...prev,
      [groupName]: !prev[groupName],
    }));
  };

  return (
    <div className="flex h-full flex-col bg-canvas">
      <div className="flex h-14 shrink-0 items-center gap-2 px-4">
        <BrandMark />
        <span className="text-[15px] font-semibold tracking-tight text-ink">ResolveAI</span>
      </div>
      <WorkspaceLabel />
      <nav aria-label="Primary" className="flex-1 overflow-y-auto px-2.5 py-3">
        <div className="space-y-4">
          {NAV.map((group) => {
            const isGroupActive = group.items.some((item) => isActive(pathname, item.href));
            const isExpanded = Boolean(openGroups[group.group]);

            return (
              <div key={group.group}>
                <button
                  type="button"
                  onClick={() => toggleGroup(group.group)}
                  aria-expanded={isExpanded}
                  aria-controls={`group-${group.group}`}
                  className={`flex w-full items-center justify-between rounded-md px-1.5 py-1 text-[11px] font-bold tracking-widest uppercase transition-colors ${
                    isGroupActive
                      ? "text-brand-700 hover:bg-brand-50/50"
                      : "text-ink-3 hover:bg-subtle hover:text-ink"
                  }`}
                >
                  <span className="flex items-center gap-2">
                    {isExpanded ? (
                      <ChevronDown className={`size-3.5 shrink-0 ${isGroupActive ? "text-brand-600" : "text-ink-3"}`} aria-hidden="true" />
                    ) : (
                      <ChevronRight className={`size-3.5 shrink-0 ${isGroupActive ? "text-brand-600" : "text-ink-3"}`} aria-hidden="true" />
                    )}
                    <span>{group.group}</span>
                  </span>
                  {isGroupActive && !isExpanded ? (
                    <span className="size-1.5 rounded-full bg-brand-600" title="Contains active page" />
                  ) : null}
                </button>

                {isExpanded ? (
                  <ul id={`group-${group.group}`} className="mt-1.5 ml-3 space-y-0.5 border-l border-line/70 pl-2.5">
                    {group.items.map(({ href, label, icon: Icon }) => {
                      const active = isActive(pathname, href);
                      const badge = counts?.[href];
                      return (
                        <li key={href}>
                          <Link
                            href={href}
                            onClick={onNavigate}
                            aria-current={active ? "page" : undefined}
                            className={`flex items-center gap-2.5 rounded-md px-2 py-1.5 text-[13px] transition-colors ${
                              active ? "bg-brand-50 font-medium text-brand-700" : "text-ink-2 hover:bg-subtle hover:text-ink"
                            }`}
                          >
                            <Icon className={`size-[17px] shrink-0 ${active ? "text-brand-600" : "text-ink-3"}`} aria-hidden="true" />
                            <span className="min-w-0 flex-1 truncate">{label}</span>
                            {badge ? (
                              <span className="shrink-0 rounded-full bg-subtle px-1.5 py-0.5 text-[11px] font-medium text-ink-2 tabular">{badge}</span>
                            ) : null}
                          </Link>
                        </li>
                      );
                    })}
                  </ul>
                ) : null}
              </div>
            );
          })}
        </div>
      </nav>
      <div className="shrink-0 border-t border-line/60 px-4 py-3.5">
        <AgentStatus />
      </div>
    </div>
  );
}
