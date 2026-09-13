/** A labelled 0-1 meter. Always rendered with its numeric value, so the bar is never the only carrier of information. */
export function ConfidenceMeter({ value, label, tone = "brand" }: { value: number; label: string; tone?: "brand" | "neutral" }) {
  const pctValue = Math.max(0, Math.min(1, value)) * 100;
  return (
    <div className="flex items-center gap-2">
      <div
        role="meter"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={1}
        aria-valuenow={Number(value.toFixed(4))}
        aria-valuetext={`${pctValue.toFixed(1)}%`}
        className="h-1.5 w-full max-w-40 overflow-hidden rounded-full bg-subtle"
      >
        <div className={`h-full rounded-full ${tone === "brand" ? "bg-brand-500" : "bg-neutral"}`} style={{ width: `${pctValue}%` }} />
      </div>
      <span className="tabular text-xs text-ink-2">{pctValue.toFixed(1)}%</span>
    </div>
  );
}
