import type { Metadata } from "next";
import { PageHeader } from "@/components/ui/card";
import { ErrorState } from "@/components/ui/states";
import { AuditLogView } from "@/components/trace/audit-log-view";
import { api, load } from "@/lib/api/client";
import { toErrorInfo } from "@/lib/errors";

export const metadata: Metadata = { title: "Audit Log" };
export const dynamic = "force-dynamic";

export default async function TracesPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const sp = await searchParams;
  const raw = Array.isArray(sp.action) ? sp.action[0] : sp.action;
  const wanted = (raw ?? "").trim().toUpperCase();
  const validActions = ["AUTO_HANDLE", "CLARIFICATION_REQUIRED", "HUMAN_HANDOFF"];
  const action = validActions.includes(wanted) ? wanted : "";

  // Always fetch traces to allow fluid client-side switching and accurate summary counts
  const traces = await load(api.traces({ limit: 200 }));
  const items = traces.data?.items ?? [];

  return (
    <>
      <PageHeader
        eyebrow="Admin"
        title="Audit Log"
        description="See how ResolveAI handled customer conversations and why each decision was made."
      />

      {traces.error ? (
        <div className="mb-4">
          <ErrorState error={toErrorInfo(traces.error)} />
        </div>
      ) : null}

      <AuditLogView initialItems={items} currentAction={action} />
    </>
  );
}
