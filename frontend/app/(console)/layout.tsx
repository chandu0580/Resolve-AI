import { connection } from "next/server";
import type { ReactNode } from "react";
import { AppShell } from "@/components/shell/app-shell";
import type { RuntimeInfo } from "@/components/shell/runtime";
import { api, load } from "@/lib/api/client";

export default async function ConsoleLayout({ children }: { children: ReactNode }) {
  await connection();
  const [config, health, traces] = await Promise.all([load(api.config()), load(api.health()), load(api.traces({ limit: 200 }))]);
  // Sidebar counts and the notification dot are real: conversations recorded by this deployment, and how many went to a person.
  const items = traces.data?.items ?? [];
  const handoffs = items.filter((t) => t.final_decision === "HUMAN_HANDOFF").length;
  const counts: Record<string, number> = {};
  if (items.length) counts["/conversations"] = items.length;
  if (handoffs) counts["/handoffs"] = handoffs;
  const runtime: RuntimeInfo = {
    env: config.data?.service.env ?? health.data?.env ?? null,
    model: config.data?.llm.model ?? null,
    provider: config.data?.llm.provider ?? null,
    llmEnabled: config.data ? config.data.llm.enabled : null,
    apiVersion: health.data?.version ?? null,
    apiReachable: health.error === null,
  };
  return (
    <AppShell runtime={runtime} counts={counts} attention={handoffs}>
      {children}
    </AppShell>
  );
}
