import type { Metadata } from "next";
import { PageHeader } from "@/components/ui/card";
import { ErrorState } from "@/components/ui/states";
import { TrustDashboard } from "@/components/trust/trust-dashboard";
import { api, load } from "@/lib/api/client";
import { toErrorInfo } from "@/lib/errors";

export const metadata: Metadata = { title: "Trust & Safety" };
export const dynamic = "force-dynamic";

export default async function TrustPage() {
  const [config, release] = await Promise.all([
    load(api.config()),
    load(api.evaluationRelease()),
  ]);

  return (
    <>
      <PageHeader
        eyebrow="Admin"
        title="Trust & Safety"
        description="Control when ResolveAI can act on its own and when a human must take over."
      />

      {config.error ? (
        <div className="mb-4">
          <ErrorState error={toErrorInfo(config.error)} compact />
        </div>
      ) : null}

      <TrustDashboard
        config={config.data}
        release={release.data}
      />
    </>
  );
}
