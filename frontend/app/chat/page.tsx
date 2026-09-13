import type { Metadata } from "next";
import { ArrowLeft, ArrowRight, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { CustomerChat } from "@/components/chat/customer-chat";
import { BrandMark } from "@/components/shell/sidebar";

export const metadata: Metadata = {
  title: "Customer Chat — ResolveAI",
  description: "Talk directly to ResolveAI. Send a real support message to experience grounded replies, clarification, and human handoff live.",
};

export default function ChatPage() {
  return (
    <div className="min-h-screen bg-canvas">
      {/* Top navigation */}
      <header className="sticky top-0 z-40 border-b border-line/70 bg-canvas/90 backdrop-blur">
        <div className="mx-auto flex h-16 w-full max-w-[1180px] items-center justify-between gap-4 px-5">
          <div className="flex items-center gap-3">
            <Link href="/" className="flex items-center gap-2 text-ink hover:opacity-80">
              <BrandMark className="size-7" />
              <span className="text-[17px] font-semibold tracking-tight text-ink">ResolveAI</span>
            </Link>
            <span className="rounded-full bg-brand-50 px-2.5 py-0.5 text-[11px] font-medium text-brand-700">
              Customer Chat
            </span>
          </div>
          <div className="flex items-center gap-3">
            <Link
              href="/"
              className="inline-flex items-center gap-1.5 rounded-lg border border-line bg-surface px-3 py-1.5 text-[13px] font-medium text-ink hover:bg-subtle"
            >
              <ArrowLeft className="size-3.5" aria-hidden="true" />
              <span>Back to Home</span>
            </Link>
            <Link
              href="/overview"
              className="inline-flex items-center gap-1.5 rounded-lg bg-brand-700 px-3.5 py-1.5 text-[13px] font-medium text-white hover:bg-brand-900"
            >
              <span>Open workspace</span>
              <ArrowRight className="size-3.5" aria-hidden="true" />
            </Link>
          </div>
        </div>
      </header>

      {/* Main chat surface */}
      <main className="mx-auto w-full max-w-[1180px] px-5 py-8 sm:py-10">
        <div className="mb-6 max-w-2xl">
          <div className="flex items-center gap-2 text-[11px] font-medium tracking-[0.12em] text-ink-3 uppercase">
            <ShieldCheck className="size-3.5 text-brand-600" aria-hidden="true" />
            <span>Customer-facing AI Agent</span>
          </div>
          <h1 className="mt-2 text-[26px] font-semibold tracking-tight text-ink sm:text-[32px]">
            Customer Chat
          </h1>
          <p className="mt-2 text-[14px] leading-relaxed text-ink-2">
            Talk directly to ResolveAI. Send a real support message to experience grounded replies, clarification,
            and human handoff live. Every reply is backed by historical support cases or safely escalated.
          </p>
        </div>

        <CustomerChat />

        <div className="mt-8 rounded-xl border border-line bg-surface p-4 text-[12px] text-ink-3 sm:flex sm:items-center sm:justify-between">
          <p>
            Every conversation here triggers live pipeline stages: redaction, intent classification, evidence search,
            policy evaluation, and output verification.
          </p>
          <Link href="/overview" className="mt-2 block shrink-0 font-medium text-brand-700 hover:underline sm:mt-0">
            View conversations in the workspace →
          </Link>
        </div>
      </main>
    </div>
  );
}
