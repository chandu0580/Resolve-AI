import { Spinner } from "@/components/ui/states";

export default function Loading() {
  return (
    <div className="space-y-4">
      <Spinner label="Loading from the ResolveAI API…" />
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3" aria-hidden="true">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="h-24 animate-pulse rounded-lg border border-line bg-surface" />
        ))}
      </div>
      <div className="h-72 animate-pulse rounded-lg border border-line bg-surface" aria-hidden="true" />
    </div>
  );
}
