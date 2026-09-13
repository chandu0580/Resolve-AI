import { CircleAlert, LoaderCircle } from "lucide-react";
import type { ElementType, ReactNode } from "react";
import { explainError, type ErrorInfo } from "@/lib/errors";

export function EmptyState({ icon: Icon, title, children, action }: { icon?: ElementType; title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center px-6 py-10 text-center">
      {Icon ? (
        <div className="mb-3 flex size-10 items-center justify-center rounded-full bg-subtle text-ink-3">
          <Icon className="size-5" aria-hidden="true" />
        </div>
      ) : null}
      <p className="text-sm font-medium text-ink">{title}</p>
      {children ? <div className="mt-1 max-w-md text-[13px] text-ink-3">{children}</div> : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}

export function ErrorState({ error, retry, compact = false }: { error: ErrorInfo; retry?: ReactNode; compact?: boolean }) {
  const exp = explainError(error);
  const details = Array.isArray(error.details) ? (error.details as unknown[]) : null;
  return (
    <div role="alert" className={`rounded-lg border border-danger-line bg-danger-bg ${compact ? "px-3 py-2.5" : "px-4 py-4"}`}>
      <div className="flex gap-3">
        <CircleAlert className="mt-0.5 size-5 shrink-0 text-danger" aria-hidden="true" />
        <div className="min-w-0 text-[13px] text-ink-2">
          <p className="text-sm font-semibold text-ink">{exp.title}</p>
          <p className="mt-0.5">{exp.description}</p>
          {error.message && error.message !== exp.description ? <p className="mt-1 text-ink-3">API message: {error.message}</p> : null}
          {details && details.length ? (
            <ul className="mt-1 list-disc pl-5 text-ink-3">
              {details.slice(0, 5).map((d, i) => (
                <li key={i}>{typeof d === "string" ? d : JSON.stringify(d)}</li>
              ))}
            </ul>
          ) : null}
          <p className="mt-2 text-ink">{exp.action}</p>
          <p className="mt-2 font-mono text-[11px] text-ink-3">
            {error.errorCode} · HTTP {error.status}
            {error.requestId ? ` · request ${error.requestId}` : ""}
            {error.traceId ? ` · trace ${error.traceId}` : ""}
          </p>
          {retry ? <div className="mt-3">{retry}</div> : null}
        </div>
      </div>
    </div>
  );
}

export function Spinner({ label }: { label: string }) {
  return (
    <span className="inline-flex items-center gap-2 text-[13px] text-ink-3" role="status">
      <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />
      {label}
    </span>
  );
}

export function SkeletonRows({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-2 p-4" aria-hidden="true">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="h-8 animate-pulse rounded bg-subtle" />
      ))}
    </div>
  );
}
