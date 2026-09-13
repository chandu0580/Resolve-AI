import type { Metadata } from "next";
import { PageHeader } from "@/components/ui/card";
import { ErrorState } from "@/components/ui/states";
import { HandoffQueue } from "@/components/handoff/handoff-queue";
import { api, load } from "@/lib/api/client";
import { toErrorInfo } from "@/lib/errors";

export const metadata: Metadata = { title: "Handoffs" };

export default async function HandoffsPage() {
  const traces = await load(api.traces({ limit: 200, action: "HUMAN_HANDOFF" }));
  return (
    <>
      <PageHeader
        eyebrow="WORKSPACE"
        title="Handoffs"
        description="Cases that need a human to take over. ResolveAI has already summarized the issue, evidence, reason for escalation, and recommended next action."
      />
      {traces.error ? (
        <div className="mb-4">
          <ErrorState error={toErrorInfo(traces.error)} compact />
        </div>
      ) : null}
      <HandoffQueue summaries={traces.data?.items ?? null} />
    </>
  );
}
