/** Display formatting. Timestamps are rendered in UTC so server and client output are identical and audit times are unambiguous. */

export function pct(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "n/a";
  return `${(value * 100).toFixed(digits)}%`;
}

export function fixed(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "n/a";
  return value.toFixed(digits);
}

export function duration(ms: number | null | undefined): string {
  if (ms === null || ms === undefined || Number.isNaN(ms)) return "n/a";
  if (ms < 1) return "<1 ms";
  if (ms < 1000) return `${Math.round(ms)} ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)} s`;
  return `${Math.floor(ms / 60_000)} min ${Math.round((ms % 60_000) / 1000)} s`;
}

const DATE_TIME = new Intl.DateTimeFormat("en-GB", {
  year: "numeric",
  month: "short",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hour12: false,
  timeZone: "UTC",
});

export function dateTime(iso: string | null | undefined): string {
  if (!iso) return "n/a";
  const d = new Date(iso.includes("T") ? iso : iso.replace(" ", "T"));
  if (Number.isNaN(d.getTime())) return iso;
  return `${DATE_TIME.format(d)} UTC`;
}

export function timeOfDay(iso: string | null | undefined): string {
  if (!iso) return "n/a";
  const m = /T(\d{2}:\d{2}:\d{2}(?:\.\d{1,3})?)/.exec(iso);
  return m ? `${m[1]} UTC` : iso;
}

export function dateOnly(iso: string | null | undefined): string {
  return dateTime(iso).split(",")[0];
}

/** "2m", "3h", "5d" — compact age for dense tables. Falls back to the date once a record is over a week old. */
export function relativeTime(iso: string | null | undefined): string {
  if (!iso) return "n/a";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "n/a";
  const s = Math.max(0, Math.round((Date.now() - then) / 1000));
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.round(s / 60)}m ago`;
  if (s < 86_400) return `${Math.round(s / 3600)}h ago`;
  if (s < 604_800) return `${Math.round(s / 86_400)}d ago`;
  return dateOnly(iso);
}

export function shortId(id: string | null | undefined, n = 8): string {
  return id ? id.slice(0, n) : "n/a";
}

export function humanize(code: string | null | undefined): string {
  if (!code) return "n/a";
  const s = code.replace(/_/g, " ").trim();
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export function usd(value: number | null | undefined): string {
  if (value === null || value === undefined) return "n/a";
  return value < 0.01 ? `$${value.toFixed(4)}` : `$${value.toFixed(2)}`;
}
