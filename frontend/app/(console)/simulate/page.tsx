import type { Metadata } from "next";
import { PageHeader } from "@/components/ui/card";
import { ChatSimulator } from "@/components/simulate/chat-simulator";
import { api, load } from "@/lib/api/client";
import { toErrorInfo } from "@/lib/errors";

export const metadata: Metadata = { title: "Chat with ResolveAI · ResolveAI" };

export default async function SimulatePage() {
  const [scenarios, config] = await Promise.all([load(api.demoScenarios()), load(api.config())]);
  return (
    <>
      <PageHeader
        eyebrow="AI AGENT"
        title="Chat with ResolveAI"
        description="Test how ResolveAI understands, resolves, and escalates customer requests."
        actions={
          <span className="inline-flex items-center gap-1.5 rounded-full border border-[#98A68E]/50 bg-[#586651]/10 px-3 py-1 text-xs font-medium text-[#3d7a57]">
            <span className="inline-block size-1.5 rounded-full bg-[#3d7a57]" aria-hidden="true" />
            Agent online
          </span>
        }
      />
      <ChatSimulator
        scenarios={scenarios.data}
        scenariosError={scenarios.error ? toErrorInfo(scenarios.error) : null}
        maxMessageChars={config.data?.service.limits.max_message_chars ?? 2000}
        model={config.data?.llm.enabled ? config.data.llm.model : null}
      />
    </>
  );
}
