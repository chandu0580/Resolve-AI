import { Activity, Bot, BookOpen, ChartColumn, Inbox, LayoutDashboard, MessagesSquare, Play, Settings, ShieldCheck, TrendingUp } from "lucide-react";
import type { ElementType } from "react";

export interface NavItem {
  href: string;
  label: string;
  /** Page title shown in the top bar when it differs from the navigation label. */
  title?: string;
  icon: ElementType;
}

export const NAV: { group: string; items: NavItem[] }[] = [
  {
    group: "Workspace",
    items: [
      { href: "/overview", label: "Overview", icon: LayoutDashboard },
      { href: "/conversations", label: "Conversations", icon: MessagesSquare },
      { href: "/handoffs", label: "Handoffs", title: "Handoff queue", icon: Inbox },
    ],
  },
  {
    group: "AI",
    items: [
      { href: "/agents", label: "Agent", title: "Agent", icon: Bot },
      { href: "/knowledge", label: "Knowledge", icon: BookOpen },
      { href: "/simulate", label: "Test the Agent", title: "Test the Customer Experience", icon: Play },
    ],
  },
  {
    group: "Insights",
    items: [
      { href: "/evaluation", label: "Evaluation", icon: ChartColumn },
      { href: "/analytics", label: "Analytics", icon: TrendingUp },
    ],
  },
  {
    group: "Governance",
    items: [
      { href: "/trust", label: "Trust & Safety", icon: ShieldCheck },
      { href: "/traces", label: "Audit Log", title: "Audit Log", icon: Activity },
      { href: "/settings", label: "Settings", icon: Settings },
    ],
  },
];

export function isActive(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}

const DETAIL_TITLES: Record<string, string> = {
  "/conversations": "Conversation workspace",
  "/handoffs": "Handoff detail",
  "/traces": "Audit Log",
};

export function titleFor(pathname: string): string {
  for (const [prefix, title] of Object.entries(DETAIL_TITLES)) {
    if (pathname.startsWith(`${prefix}/`)) return title;
  }
  for (const group of NAV) {
    const item = group.items.find((i) => i.href === pathname);
    if (item) return item.title ?? item.label;
  }
  return "ResolveAI";
}
