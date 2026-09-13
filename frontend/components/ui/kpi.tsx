import type { ReactNode } from "react";

export function Kpi({ label, value, sub, ci }: { label: string; value: ReactNode; sub?: ReactNode; ci?: string | null }) {
  return (
    <div className="min-w-0 rounded-lg border border-line bg-surface px-4 py-3">
      <dt className="text-xs text-ink-3">{label}</dt>
      <dd className="mt-1">
        <span className="text-2xl font-semibold tracking-tight text-ink tabular">{value}</span>
        {ci ? <span className="ml-1.5 text-xs text-ink-3 tabular">95% CI {ci}</span> : null}
        {sub ? <div className="mt-0.5 text-xs text-ink-3">{sub}</div> : null}
      </dd>
    </div>
  );
}

export function KpiGrid({ children, label }: { children: ReactNode; label: string }) {
  return (
    <dl aria-label={label} className="grid grid-cols-1 gap-3 min-[480px]:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-6">
      {children}
    </dl>
  );
}

export function DistributionBar({ segments, label }: { segments: { label: string; value: number; className: string }[]; label: string }) {
  const total = segments.reduce((s, x) => s + x.value, 0) || 1;
  return (
    <div>
      <div className="flex h-2.5 overflow-hidden rounded-full bg-subtle" role="img" aria-label={`${label}: ${segments.map((s) => `${s.label} ${((s.value / total) * 100).toFixed(1)}%`).join(", ")}`}>
        {segments.map((s) => (s.value > 0 ? <div key={s.label} className={s.className} style={{ width: `${(s.value / total) * 100}%` }} /> : null))}
      </div>
      <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-2" aria-hidden="true">
        {segments.map((s) => (
          <li key={s.label} className="flex items-center gap-1.5">
            <span className={`size-2 rounded-sm ${s.className}`} />
            {s.label} <span className="tabular text-ink-3">{((s.value / total) * 100).toFixed(1)}%</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
