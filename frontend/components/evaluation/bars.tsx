/** Horizontal comparison bars with optional 95% interval whiskers. Every value is printed, so bars are never the only signal. */
export interface BarRow {
  key: string;
  label: string;
  value: number | null;
  ci?: [number, number] | null;
  highlight?: boolean;
}

export function BarList({ rows, max = 1, format, label }: { rows: BarRow[]; max?: number; format: (v: number) => string; label: string }) {
  return (
    <ul className="space-y-2" aria-label={label}>
      {rows.map((r) => {
        const w = r.value === null ? 0 : Math.max(0, Math.min(1, r.value / max)) * 100;
        return (
          <li key={r.key} className="grid grid-cols-[minmax(0,11rem)_minmax(0,1fr)_auto] items-center gap-3 text-[13px]">
            <span className={`truncate ${r.highlight ? "font-semibold text-ink" : "text-ink-2"}`} title={r.label}>
              {r.label}
            </span>
            <span className="relative h-2.5 rounded-full bg-subtle" aria-hidden="true">
              <span className={`absolute inset-y-0 left-0 rounded-full ${r.highlight ? "bg-brand-600" : "bg-line-strong"}`} style={{ width: `${w}%` }} />
              {r.ci ? (
                <span
                  className="absolute top-1/2 h-3.5 -translate-y-1/2 border-x-2 border-ink/60"
                  style={{ left: `${(Math.max(0, r.ci[0]) / max) * 100}%`, width: `${Math.max(0.5, ((Math.min(max, r.ci[1]) - Math.max(0, r.ci[0])) / max) * 100)}%` }}
                />
              ) : null}
            </span>
            <span className={`text-right tabular ${r.highlight ? "font-semibold text-ink" : "text-ink-2"}`}>
              {r.value === null ? "n/a" : format(r.value)}
              {r.ci ? <span className="ml-1 text-[11px] font-normal text-ink-3">[{format(r.ci[0])}, {format(r.ci[1])}]</span> : null}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
