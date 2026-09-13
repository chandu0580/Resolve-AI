import type { Metadata } from "next";
import { InboxWorkspace } from "@/components/conversation/inbox/inbox-workspace";
import { api, load } from "@/lib/api/client";

export const metadata: Metadata = {
  title: "Conversations — Customer Support Workspace",
  description: "Enterprise customer-support workspace: review incoming requests, AI decisions, and manage human handoffs.",
};

export default async function ConversationsPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const sp = await searchParams;
  const traceIdParam = Array.isArray(sp.id) ? sp.id[0] : sp.id;
  const traces = await load(api.traces({ limit: 100 }));

  return (
    <div className="space-y-3">
      <InboxWorkspace
        initialTraceId={traceIdParam || undefined}
        traces={traces.data?.items ?? null}
      />
    </div>
  );
}
