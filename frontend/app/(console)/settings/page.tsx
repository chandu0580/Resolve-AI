import type { Metadata } from "next";
import { PageHeader } from "@/components/ui/card";
import { ErrorState } from "@/components/ui/states";
import { SettingsDashboard } from "@/components/settings/settings-dashboard";
import { api, load } from "@/lib/api/client";
import { toErrorInfo } from "@/lib/errors";

export const metadata: Metadata = { title: "Settings" };
export const dynamic = "force-dynamic";

export default async function SettingsPage() {
  const [config, health, knowledge] = await Promise.all([
    load(api.config()),
    load(api.health()),
    load(api.knowledgeSummary()),
  ]);

  // Server-side presence check only: token value is never sent to the browser
  const tokenPresent = Boolean(process.env.RESOLVEAI_API_TOKEN);

  return (
    <>
      <PageHeader
        eyebrow="Admin"
        title="Settings"
        description="Configure how ResolveAI works for your support team."
      />

      {config.error ? (
        <div className="mb-4">
          <ErrorState error={toErrorInfo(config.error)} compact />
        </div>
      ) : null}

      <SettingsDashboard
        config={config.data}
        health={health.data}
        knowledge={knowledge.data}
        tokenPresent={tokenPresent}
      />
    </>
  );
}
