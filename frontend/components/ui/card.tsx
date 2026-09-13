import Link from "next/link";
import type { ReactNode } from "react";

export function Card({
  title,
  description,
  actions,
  children,
  className = "",
  bodyClassName = "p-4",
  id,
  headingLevel = 2,
}: {
  title?: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  children?: ReactNode;
  className?: string;
  bodyClassName?: string;
  id?: string;
  headingLevel?: 2 | 3;
}) {
  const Heading = headingLevel === 2 ? "h2" : "h3";
  const headingId = id ? `${id}-title` : undefined;
  return (
    <section id={id} aria-labelledby={title ? headingId : undefined} className={`min-w-0 rounded-lg border border-line bg-surface shadow-[0_1px_2px_rgba(15,23,42,0.04)] ${className}`}>
      {title || actions ? (
        <header className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2 border-b border-line px-4 py-3">
          <div className="min-w-0">
            {title ? (
              <Heading id={headingId} className="text-sm font-semibold text-ink">
                {title}
              </Heading>
            ) : null}
            {description ? <p className="mt-0.5 text-[13px] text-ink-3">{description}</p> : null}
          </div>
          {actions ? <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div> : null}
        </header>
      ) : null}
      <div className={bodyClassName}>{children}</div>
    </section>
  );
}

/**
 * Collapsed-by-default disclosure for engineering detail (versions, gate names, model usage, configuration hashes).
 * The operator experience stays human-readable; the same facts remain one click away and in the Trace Explorer.
 */
export function Advanced({ label = "Technical details", children }: { label?: string; children: ReactNode }) {
  return (
    <details className="group mt-3 border-t border-line pt-3">
      <summary className="cursor-pointer list-none text-xs font-medium text-ink-3 hover:text-ink-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-500">
        <span className="inline-block transition-transform group-open:rotate-90" aria-hidden="true">&rsaquo;</span> {label}
      </summary>
      <div className="mt-3">{children}</div>
    </details>
  );
}

export function PageHeader({
  title,
  description,
  actions,
  eyebrow,
  breadcrumbs,
}: {
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
  eyebrow?: ReactNode;
  breadcrumbs?: { label: string; href?: string }[];
}) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
      <div className="min-w-0 max-w-3xl">
        {breadcrumbs?.length ? (
          <nav aria-label="Breadcrumb" className="mb-1">
            <ol className="flex flex-wrap items-center gap-1 text-xs text-ink-3">
              {breadcrumbs.map((b, i) => (
                <li key={`${b.label}-${i}`} className="flex items-center gap-1">
                  {i ? <span aria-hidden="true">/</span> : null}
                  {b.href ? (
                    <Link href={b.href} className="font-medium text-brand-700 hover:underline">
                      {b.label}
                    </Link>
                  ) : (
                    <span aria-current="page">{b.label}</span>
                  )}
                </li>
              ))}
            </ol>
          </nav>
        ) : eyebrow ? (
          <div className="mb-1 text-xs font-medium tracking-wide text-brand-700 uppercase">{eyebrow}</div>
        ) : null}
        <h1 className="text-xl font-semibold tracking-tight text-ink">{title}</h1>
        {description ? <p className="mt-1 text-sm text-ink-3">{description}</p> : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </div>
  );
}

export function KeyValues({ items, columns = 1 }: { items: { label: ReactNode; value: ReactNode; hint?: ReactNode }[]; columns?: 1 | 2 }) {
  return (
    <div className="@container">
      <dl className={`grid gap-x-6 gap-y-2.5 ${columns === 2 ? "@2xl:grid-cols-2" : ""}`}>
        {items.map((item, i) => (
          <div key={i} className="grid min-w-0 grid-cols-1 gap-0.5 @[20rem]:grid-cols-[minmax(7rem,38%)_minmax(0,1fr)] @[20rem]:items-baseline @[20rem]:gap-3">
            <dt className="text-[13px] text-ink-3">{item.label}</dt>
            <dd className="min-w-0 text-[13px] break-words text-ink">
              {item.value}
              {item.hint ? <div className="mt-0.5 text-xs text-ink-3">{item.hint}</div> : null}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

export function Mono({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <code className={`rounded bg-subtle px-1 py-px font-mono text-[12px] break-all text-ink-2 ${className}`}>{children}</code>;
}

export function Notice({ tone = "neutral", title, children, icon: Icon }: { tone?: "neutral" | "info" | "warning" | "danger"; title?: ReactNode; children?: ReactNode; icon?: React.ElementType }) {
  const cls = {
    neutral: "border-neutral-line bg-neutral-bg text-ink-2",
    info: "border-info-line bg-info-bg text-ink-2",
    warning: "border-warning-line bg-warning-bg text-ink-2",
    danger: "border-danger-line bg-danger-bg text-ink-2",
  }[tone];
  const iconCls = { neutral: "text-neutral", info: "text-info", warning: "text-warning", danger: "text-danger" }[tone];
  return (
    <div className={`flex gap-2.5 rounded-md border px-3 py-2.5 text-[13px] ${cls}`}>
      {Icon ? <Icon className={`mt-0.5 size-4 shrink-0 ${iconCls}`} aria-hidden="true" /> : null}
      <div className="min-w-0">
        {title ? <div className="font-medium text-ink">{title}</div> : null}
        {children ? <div className={title ? "mt-0.5" : ""}>{children}</div> : null}
      </div>
    </div>
  );
}
