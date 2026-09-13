import type { Metadata } from "next";
import { InboxWorkspace } from "@/components/conversation/inbox/inbox-workspace";
import { api, load } from "@/lib/api/client";

export const metadata: Metadata = { title: "Conversation — Support Workspace" };

export default async function ConversationPage({ params }: { params: Promise<{ traceId: string }> }) {
  const { traceId } = await params;
  const traces = await load(api.traces({ limit: 100 }));

  return (
    <div className="space-y-3">
      <InboxWorkspace initialTraceId={traceId} traces={traces.data?.items ?? null} />
    </div>
  );
}
