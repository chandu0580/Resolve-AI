import type { Metadata } from "next";
import { HandoffDetail } from "@/components/handoff/handoff-detail";
import { api, load } from "@/lib/api/client";
import { toErrorInfo } from "@/lib/errors";

export const metadata: Metadata = { title: "Handoff" };

export default async function HandoffPage({ params }: { params: Promise<{ traceId: string }> }) {
  const { traceId } = await params;
  const trace = await load(api.trace(traceId));
  return <HandoffDetail traceId={traceId} trace={trace.data} traceError={trace.error ? toErrorInfo(trace.error) : null} />;
}
