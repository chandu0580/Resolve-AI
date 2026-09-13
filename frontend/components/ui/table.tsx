import type { ReactNode } from "react";

export const TH = "border-b border-line bg-subtle/70 px-3 py-2 text-left text-xs font-medium whitespace-nowrap text-ink-3";
export const TD = "border-b border-line px-3 py-2.5 align-top text-[13px]";

export function DataTable({ label, children, minWidth = 860 }: { label: string; children: ReactNode; minWidth?: number }) {
  return (
    // Focusable so keyboard users can scroll a table that is wider than its card.
    <div className="overflow-x-auto" tabIndex={0} role="region" aria-label={`${label} table`}>
      <table aria-label={label} className="w-full border-separate border-spacing-0" style={{ minWidth }}>
        {children}
      </table>
    </div>
  );
}

export function FilterChips<K extends string>({
  label,
  options,
  value,
  onChange,
  counts,
}: {
  label: string;
  options: { key: K; label: string }[];
  value: K;
  onChange: (key: K) => void;
  counts?: Partial<Record<K, number>>;
}) {
  return (
    <div role="group" aria-label={label} className="flex flex-wrap gap-1.5">
      {options.map((o) => {
        const active = o.key === value;
        return (
          <button
            key={o.key}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(o.key)}
            className={`inline-flex h-7 items-center gap-1.5 rounded-full border px-2.5 text-xs font-medium transition-colors ${
              active ? "border-brand-600 bg-brand-600 text-white" : "border-line bg-surface text-ink-2 hover:border-line-strong hover:text-ink"
            }`}
          >
            {o.label}
            {counts && counts[o.key] !== undefined ? <span className={`tabular ${active ? "text-white" : "text-ink-3"}`}>{counts[o.key]}</span> : null}
          </button>
        );
      })}
    </div>
  );
}
