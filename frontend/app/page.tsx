import type { Metadata } from "next";
import { ArrowRight, Database, FileText, MessageSquare, Search, ShieldCheck, Users } from "lucide-react";
import Link from "next/link";
import type { ElementType } from "react";
import { BrandMark } from "@/components/shell/sidebar";

export const metadata: Metadata = {
  title: "ResolveAI — AI Customer Support That Knows When to Answer and When to Hand Off",
  description:
    "ResolveAI learns from historical support conversations to classify intents, draft grounded replies, and decide when to handle automatically or escalate to a human.",
};

const SITE_NAV = [
  { href: "#how", label: "How it works" },
  { href: "#capabilities", label: "Capabilities" },
  { href: "/evaluation", label: "Evaluation" },
];

const CAPABILITIES: { icon: ElementType; title: string; body: string }[] = [
  { icon: MessageSquare, title: "Understand", body: "Classify messy customer messages into clear support intents." },
  { icon: Search, title: "Find evidence", body: "Find similar issues and proven resolutions from support history." },
  { icon: FileText, title: "Draft a reply", body: "Generate a grounded response using relevant evidence." },
  { icon: Users, title: "Make a decision", body: "Resolve automatically when safe. Escalate when a human is needed." },
  { icon: ShieldCheck, title: "Built for trust", body: "Verify the response before it reaches the customer." },
];

/** Precise metrics describing the research and evaluation foundations of ResolveAI. */
const FACTS = [
  { value: "3M+", label: "conversations in the\nCustomer Support on Twitter dataset" },
  { value: "AppleSupport", label: "Selected support dataset\nReal support history." },
  { value: "197", label: "examples in the\nfrozen evaluation set" },
];

const STEPS = [
  {
    n: "01",
    title: "Understand",
    sub: "Recognize what the customer needs.",
    body: "Classify unstructured messages into verified support intents.",
  },
  {
    n: "02",
    title: "Ground",
    sub: "Find relevant answers from trusted support history.",
    body: "Search how the brand resolved similar issues and test evidence strength.",
  },
  {
    n: "03",
    title: "Resolve",
    sub: "Draft a response based on proven resolutions.",
    body: "Every automatic reply must be supported by sufficient historical evidence.",
  },
  {
    n: "04",
    title: "Escalate",
    sub: "Bring in a human when the issue needs one.",
    body: "A structured context packet is delivered to the right place.",
  },
];

function SiteHeader() {
  return (
    <header className="sticky top-0 z-40 border-b border-line/70 bg-canvas/90 backdrop-blur">
      <div className="mx-auto flex h-16 w-full max-w-[1180px] items-center gap-6 px-5">
        <Link href="/" className="flex shrink-0 items-center gap-2">
          <BrandMark className="size-7" />
          <span className="text-[17px] font-semibold tracking-tight text-ink">ResolveAI</span>
        </Link>
        <nav aria-label="Site" className="hidden items-center gap-6 md:flex">
          {SITE_NAV.map((l) => (
            <Link key={l.href} href={l.href} className="text-[13px] text-ink-2 hover:text-ink">
              {l.label}
            </Link>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-3">
          <Link
            href="/overview"
            className="inline-flex items-center gap-1.5 rounded-lg border border-line bg-surface px-3.5 py-2 text-[13px] font-medium text-ink hover:bg-subtle"
          >
            Open workspace
          </Link>
          <Link
            href="/chat"
            className="inline-flex items-center gap-1.5 rounded-lg bg-brand-700 px-4 py-2 text-[13px] font-medium text-white hover:bg-brand-900"
          >
            Try ResolveAI <ArrowRight className="size-3.5" aria-hidden="true" />
          </Link>
        </div>
      </div>
    </header>
  );
}

/** The hero visual: the customer conversation front and center with the decision context card. */
function HeroCustomerChatPreview() {
  return (
    <div className="flex flex-col gap-3">
      {/* Customer Chat Window */}
      <div className="overflow-hidden rounded-2xl border border-line bg-surface shadow-[0_20px_50px_-20px_rgba(26,28,25,0.22)]">
        {/* Chat header */}
        <div className="flex items-center justify-between border-b border-line bg-canvas px-4 py-3">
          <div className="flex items-center gap-2.5">
            <BrandMark className="size-6" />
            <div>
              <div className="text-[13px] font-semibold text-ink">ResolveAI Support</div>
              <div className="flex items-center gap-1.5 text-[11px] text-ink-3">
                <span className="size-2 rounded-full bg-brand-600 animate-pulse" aria-hidden="true" />
                <span>Online · AI Support Agent</span>
              </div>
            </div>
          </div>
          <span className="rounded-full border border-line bg-surface px-2.5 py-0.5 text-[11px] font-medium text-ink-2">
            Apple Support
          </span>
        </div>

        {/* Chat message thread */}
        <div className="space-y-3.5 p-4 sm:p-5">
          {/* AI Greeting */}
          <div className="flex gap-2.5">
            <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-brand-50" aria-hidden="true">
              <BrandMark className="size-4" />
            </span>
            <div className="min-w-0 max-w-[85%]">
              <div className="mb-0.5 text-[10px] font-medium text-ink-3">ResolveAI</div>
              <div className="rounded-2xl rounded-tl-sm bg-subtle px-3.5 py-2.5 text-[13px] leading-relaxed text-ink">
                Hi! How can I help you with your Apple device today?
              </div>
            </div>
          </div>

          {/* Customer Message */}
          <div className="flex flex-row-reverse gap-2.5">
            <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-brand-700 text-[11px] font-medium text-white" aria-hidden="true">
              JD
            </span>
            <div className="min-w-0 max-w-[85%] text-right">
              <div className="mb-0.5 text-[10px] font-medium text-ink-3">Customer</div>
              <div className="inline-block rounded-2xl rounded-tr-sm bg-brand-700 px-3.5 py-2.5 text-[13px] leading-relaxed text-white text-left">
                My iPhone isn&apos;t turning on. I tried charging it for an hour but the screen stays black.
              </div>
            </div>
          </div>

          {/* Grounded AI Reply */}
          <div className="flex gap-2.5">
            <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-brand-50" aria-hidden="true">
              <BrandMark className="size-4" />
            </span>
            <div className="min-w-0 max-w-[88%]">
              <div className="mb-0.5 flex items-center gap-2 text-[10px] font-medium text-ink-3">
                <span>ResolveAI</span>
                <span className="rounded bg-success-bg px-1.5 py-0.5 text-[9px] font-medium text-success">Grounded reply</span>
              </div>
              <div className="rounded-2xl rounded-tl-sm border border-line bg-canvas px-3.5 py-2.5 text-[13px] leading-relaxed text-ink">
                I can help with that. Let&apos;s try a force restart first: quickly press and release Volume Up, then Volume Down, then press and hold the Side button until the Apple logo appears.
                <div className="mt-2 flex items-center gap-1.5 text-[11px] text-ink-3">
                  <span className="size-1.5 rounded-full bg-brand-600" />
                  <span>Cited from 3 verified historical resolutions</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Input mockup */}
        <div className="flex items-center gap-2 border-t border-line bg-canvas/60 px-4 py-2.5">
          <div className="flex-1 rounded-lg border border-line bg-surface px-3 py-2 text-[12px] text-ink-3">
            Type your message…
          </div>
          <Link
            href="/chat"
            className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-brand-700 text-white hover:bg-brand-900 transition-colors"
            title="Try live in chat"
          >
            <ArrowRight className="size-4" aria-hidden="true" />
          </Link>
        </div>
      </div>

      {/* Contextual Card: Behind the decision */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 rounded-xl border border-line bg-surface p-3.5 shadow-sm">
        <div className="grid grid-cols-3 gap-4 text-left w-full sm:w-auto">
          <div>
            <div className="text-[10px] font-medium uppercase tracking-wider text-ink-3">Intent</div>
            <div className="text-[12px] font-semibold text-ink">Hardware / Power</div>
          </div>
          <div>
            <div className="text-[10px] font-medium uppercase tracking-wider text-ink-3">Evidence</div>
            <div className="text-[12px] font-semibold text-ink">3 similar cases</div>
          </div>
          <div>
            <div className="text-[10px] font-medium uppercase tracking-wider text-ink-3">Decision</div>
            <div className="inline-flex items-center gap-1 text-[12px] font-semibold text-success">
              <span className="size-1.5 rounded-full bg-success" />
              Auto-handle
            </div>
          </div>
        </div>
        <Link
          href="/chat"
          className="inline-flex items-center gap-1 text-[12px] font-medium text-brand-700 hover:text-brand-900 hover:underline shrink-0"
        >
          <span>Test customer chat</span>
          <ArrowRight className="size-3.5" aria-hidden="true" />
        </Link>
      </div>
    </div>
  );
}

/** The internal operator console preview: 20-30% larger for clarity, showing supervisor triage, handoffs, and decision traces. */
function ConsolePreview() {
  const rows = [
    { who: "JD", title: "My iPhone is not turning on", sub: "I tried charging it but nothing happens.", tag: "Auto-handled", tone: "success", t: "2m" },
    { who: "SR", title: "Charged but no refund", sub: "I was charged but didn't receive my refund.", tag: "Needs review", tone: "warning", t: "12m" },
    { who: "MK", title: "Can I talk to a human?", sub: "This is really frustrating.", tag: "Handoff", tone: "danger", t: "28m" },
    { who: "AP", title: "Account locked", sub: "I can't log into my Apple ID.", tag: "Auto-handled", tone: "success", t: "1h" },
    { who: "TS", title: "Battery draining fast", sub: "My battery drains very quickly.", tag: "Needs review", tone: "warning", t: "2h" },
  ];
  const tone: Record<string, string> = {
    success: "bg-success-bg text-success",
    warning: "bg-warning-bg text-warning",
    danger: "bg-danger-bg text-danger",
  };
  return (
    <div aria-hidden="true" className="overflow-hidden rounded-2xl border border-line bg-surface shadow-[0_20px_48px_-24px_rgba(26,28,25,0.28)]">
      <div className="grid grid-cols-[140px_minmax(0,1fr)] sm:grid-cols-[190px_minmax(0,1fr)]">
        <div className="border-r border-line bg-canvas px-3.5 py-4">
          <div className="mb-4 flex items-center gap-2 px-1">
            <BrandMark className="size-5" />
            <span className="text-[13px] font-semibold text-ink">ResolveAI</span>
          </div>
          {[
            ["Workspace", ["Overview", "Conversations", "Handoffs"]],
            ["AI", ["Agent", "Knowledge", "Test Agent"]],
            ["Insights", ["Evaluation", "Analytics"]],
          ].map(([g, items]) => (
            <div key={g as string} className="mb-3.5">
              <div className="px-1 pb-1 text-[9px] font-medium tracking-wider text-ink-3 uppercase">{g as string}</div>
              {(items as string[]).map((i) => (
                <div key={i} className={`rounded px-2 py-1.5 text-[11px] ${i === "Conversations" ? "bg-brand-50 font-medium text-brand-700" : "text-ink-2"}`}>
                  {i}
                </div>
              ))}
            </div>
          ))}
        </div>
        <div className="min-w-0 p-4 sm:p-5">
          <div className="mb-3 flex items-center justify-between">
            <div>
              <div className="text-[14px] sm:text-[15px] font-semibold text-ink">Conversations</div>
              <div className="text-[11px] text-ink-3">Live conversation supervision</div>
            </div>
            <span className="rounded-full bg-brand-50 px-2.5 py-0.5 text-[10px] font-medium text-brand-700">Operator Console</span>
          </div>
          <div className="mb-3 flex gap-1.5">
            {["All", "Open", "Auto-handled", "Handoffs"].map((f, i) => (
              <span key={f} className={`rounded px-2.5 py-1 text-[10px] font-medium ${i === 0 ? "bg-brand-700 text-white" : "bg-subtle text-ink-2"}`}>
                {f}
              </span>
            ))}
          </div>
          <div className="divide-y divide-line rounded-xl border border-line">
            {rows.map((r) => (
              <div key={r.who} className="flex items-center gap-3 px-3 py-2.5">
                <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-subtle text-[9px] font-semibold text-ink-2">{r.who}</span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[12px] sm:text-[13px] font-medium text-ink">{r.title}</span>
                  <span className="block truncate text-[10px] sm:text-[11px] text-ink-3">{r.sub}</span>
                </span>
                <span className={`shrink-0 rounded px-2 py-0.5 text-[9px] sm:text-[10px] font-medium ${tone[r.tone]}`}>{r.tag}</span>
                <span className="w-8 shrink-0 text-right text-[10px] text-ink-3">{r.t}</span>
              </div>
            ))}
          </div>
          <div className="mt-3.5 rounded-xl border border-line bg-canvas px-3.5 py-3">
            <div className="text-[11px] font-semibold text-ink-2">Why this decision? (Selected conversation: JD)</div>
            <div className="mt-2 grid grid-cols-2 gap-3 sm:grid-cols-4 text-[10px] sm:text-[11px]">
              {[
                ["Customer message", "My iPhone is not turning on"],
                ["Intent", "Hardware / power (98%)"],
                ["Evidence", "3 verified historical cases"],
                ["Decision", "Safe to resolve (Auto-handle)"],
              ].map(([k, v]) => (
                <div key={k}>
                  <div className="font-semibold text-ink">{k}</div>
                  <div className="mt-0.5 text-ink-3">{v}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-canvas">
      <a href="#main" className="sr-only z-50 rounded-md bg-surface px-3 py-2 text-sm focus:not-sr-only focus:fixed focus:top-2 focus:left-2">
        Skip to content
      </a>
      <SiteHeader />

      <main id="main">
        {/* hero: customer experience first */}
        <section className="mx-auto w-full max-w-[1180px] px-5 pt-12 pb-14 lg:pt-16">
          <div className="grid items-center gap-10 lg:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)]">
            <div className="min-w-0">
              <p className="text-[11px] font-medium tracking-[0.12em] text-ink-3 uppercase">AI Customer Support</p>
              <h1 className="mt-4 text-[34px] leading-[1.12] font-semibold tracking-tight text-ink sm:text-[46px]">
                Support that actually <span className="text-brand-600">resolves.</span>
              </h1>
              <p className="mt-4 text-[17px] font-medium text-ink">
                Understand customers. Ground every answer. Know when to hand off.
              </p>
              <p className="mt-3 max-w-xl text-[14px] leading-relaxed text-ink-2">
                ResolveAI learns from historical support conversations to classify intents, draft grounded replies,
                and know when to resolve automatically or bring in a teammate.
              </p>
              <div className="mt-7 flex flex-wrap items-center gap-3">
                <Link
                  href="/chat"
                  className="inline-flex items-center gap-2 rounded-lg bg-brand-700 px-5 py-3 text-[14px] font-medium text-white hover:bg-brand-900 shadow-sm"
                >
                  Try ResolveAI <ArrowRight className="size-4" aria-hidden="true" />
                </Link>
                <Link
                  href="/overview"
                  className="inline-flex items-center gap-2 rounded-lg border border-line bg-surface px-5 py-3 text-[14px] font-medium text-ink hover:bg-subtle"
                >
                  Open workspace
                </Link>
              </div>
              <p className="mt-2 text-[12px] text-ink-3">Talk to the customer-facing agent</p>

              <ul className="mt-8 flex flex-wrap gap-x-7 gap-y-2.5 text-[13px] text-ink-2">
                <li className="flex items-center gap-2">
                  <Database className="size-4 text-ink-3" aria-hidden="true" /> Grounded in real data
                </li>
                <li className="flex items-center gap-2">
                  <Users className="size-4 text-ink-3" aria-hidden="true" /> Human-in-the-loop
                </li>
                <li className="flex items-center gap-2">
                  <ShieldCheck className="size-4 text-ink-3" aria-hidden="true" /> Built for trust
                </li>
              </ul>
            </div>
            <div className="min-w-0">
              <HeroCustomerChatPreview />
            </div>
          </div>
        </section>

        {/* capabilities */}
        <section id="capabilities" aria-labelledby="cap-h" className="mx-auto w-full max-w-[1180px] px-5 pb-16">
          <h2 id="cap-h" className="sr-only">
            What ResolveAI does
          </h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            {CAPABILITIES.map(({ icon: Icon, title, body }) => (
              <div key={title} className="rounded-xl border border-line bg-surface p-4">
                <span className="mb-3 flex size-9 items-center justify-center rounded-lg bg-brand-50">
                  <Icon className="size-4 text-brand-700" aria-hidden="true" />
                </span>
                <h3 className="text-[14px] font-semibold text-ink">{title}</h3>
                <p className="mt-1.5 text-[13px] leading-snug text-ink-3">{body}</p>
              </div>
            ))}
          </div>
        </section>

        {/* how it works */}
        <section id="how" aria-labelledby="how-h" className="mx-auto w-full max-w-[1180px] px-5 py-14">
          <p className="text-[11px] font-medium tracking-[0.12em] text-ink-3 uppercase">How it works</p>
          <h2 id="how-h" className="mt-3 max-w-2xl text-[26px] leading-snug font-semibold text-ink sm:text-[30px]">
            ResolveAI knows when to answer — and when to ask for help.
          </h2>
          <ol className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {STEPS.map((s) => (
              <li key={s.n} className="rounded-xl border border-line bg-surface p-5">
                <span className="text-[12px] font-semibold text-brand-600 tabular">{s.n}</span>
                <h3 className="mt-2 text-[14px] font-semibold text-ink">{s.title}</h3>
                <p className="mt-1 text-[13px] font-medium text-ink-2">{s.sub}</p>
                <p className="mt-1 text-[12px] leading-snug text-ink-3">{s.body}</p>
              </li>
            ))}
          </ol>

          <div className="mt-4 rounded-xl border border-line bg-surface p-4 text-[12px] text-ink-3 sm:flex sm:items-center sm:justify-between">
            <div>
              <span className="font-semibold text-ink">How decisions stay grounded: </span>
              <span>Evidence supports the response → safeguards check it → humans handle exceptions.</span>
            </div>
            <Link href="/trust" className="mt-1.5 block shrink-0 font-medium text-brand-700 hover:underline sm:mt-0">
              Review trust &amp; safety controls →
            </Link>
          </div>
        </section>

        {/* team supervision: the dashboard comes second */}
        <section id="supervision" aria-labelledby="supervision-h" className="mx-auto w-full max-w-[1180px] px-5 py-14">
          <div className="mb-8 max-w-2xl">
            <p className="text-[11px] font-medium tracking-[0.12em] text-ink-3 uppercase">Internal Supervision</p>
            <h2 id="supervision-h" className="mt-3 text-[26px] leading-snug font-semibold text-ink sm:text-[32px]">
              Your team stays in control.
            </h2>
            <p className="mt-2 text-[14px] leading-relaxed text-ink-2">
              Customers talk to ResolveAI. Your team can review conversations, take over when needed, and inspect why each decision was made.
            </p>
          </div>
          <ConsolePreview />
          <div className="mt-4 flex flex-wrap items-center justify-between gap-3 text-[12px] text-ink-3">
            <span>Conversations, handoffs, and agent stages are inspectable in real time.</span>
            <Link href="/overview" className="font-medium text-brand-700 hover:underline">
              Open the operator workspace →
            </Link>
          </div>
        </section>

        {/* facts: measured results */}
        <section aria-labelledby="facts-h" className="bg-brand-900">
          <div className="mx-auto grid w-full max-w-[1180px] gap-8 px-5 py-12 lg:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)] lg:items-center">
            <div>
              <p className="text-[11px] font-medium tracking-[0.12em] text-white/60 uppercase">Real support data. Measured results.</p>
              <h2 id="facts-h" className="mt-3 text-[26px] leading-snug font-semibold text-white sm:text-[30px]">
                Support operations,
                <br />
                without the guesswork.
              </h2>
            </div>
            <dl className="grid gap-6 sm:grid-cols-3">
              {FACTS.map((f) => (
                <div key={f.value} className="border-white/15 sm:border-l sm:pl-6 sm:first:border-l-0 sm:first:pl-0">
                  <dt className="text-[28px] font-semibold text-white tabular">{f.value}</dt>
                  <dd className="mt-1.5 text-[13px] leading-snug whitespace-pre-line text-white/70">{f.label}</dd>
                </div>
              ))}
            </dl>
          </div>
        </section>

        {/* closing */}
        <section className="mx-auto w-full max-w-[1180px] px-5 py-16">
          <div className="flex flex-col items-start gap-5 rounded-xl border border-line bg-surface px-6 py-8 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0">
              <h2 className="text-[20px] font-semibold text-ink">See the agent in action.</h2>
              <p className="mt-1.5 max-w-xl text-[13px] text-ink-3">
                Experience how ResolveAI interacts with customers, or step into the operator workspace to review
                conversations, handoffs, and evaluation results.
              </p>
            </div>
            <div className="flex shrink-0 flex-wrap items-center gap-3">
              <Link
                href="/chat"
                className="inline-flex items-center gap-2 rounded-lg bg-brand-700 px-5 py-3 text-[14px] font-medium text-white hover:bg-brand-900"
              >
                Try ResolveAI <ArrowRight className="size-4" aria-hidden="true" />
              </Link>
              <Link
                href="/overview"
                className="inline-flex items-center gap-2 rounded-lg border border-line bg-surface px-5 py-3 text-[14px] font-medium text-ink hover:bg-subtle"
              >
                Open workspace
              </Link>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-line">
        <div className="mx-auto flex w-full max-w-[1180px] flex-wrap items-center justify-between gap-x-6 gap-y-3 px-5 py-6 text-[12px] text-ink-3">
          <div className="flex items-center gap-2.5">
            <BrandMark className="size-5" />
            <span className="font-semibold text-ink">ResolveAI</span>
            <span>· AI customer support that knows when to answer and when to hand off.</span>
          </div>
          <div className="flex items-center gap-5">
            <Link href="/chat" className="hover:text-ink-2">
              Customer Chat
            </Link>
            <Link href="/overview" className="hover:text-ink-2">
              Workspace
            </Link>
            <Link href="/evaluation" className="hover:text-ink-2">
              Evaluation
            </Link>
            <Link href="/trust" className="hover:text-ink-2">
              Trust &amp; Safety
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
