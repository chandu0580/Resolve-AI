"use client";

import { BookOpen, Search } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { ButtonLink } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState, SkeletonRows } from "@/components/ui/states";
import { EvidenceCard } from "@/components/evidence/evidence-card";
import type { Action, EvidenceItem } from "@/lib/api/types";
import { shortId } from "@/lib/format";
import { ACTION_META } from "@/lib/labels";
import { useStoredResults } from "@/lib/results-store";
import { foldForMatch } from "@/lib/text";
import { useHydrated } from "@/lib/use-hydrated";

interface Entry {
  item: EvidenceItem;
  uses: { traceId: string; action: Action }[];
  cited: number;
}

export function KnowledgeExplorer() {
  const hydrated = useHydrated();
  const stored = useStoredResults();
  const [query, setQuery] = useState("");
  const [resolutionOnly, setResolutionOnly] = useState(false);

  const entries = useMemo(() => {
    const map = new Map<string, Entry>();
    for (const st of stored) {
      const cited = new Set(st.result.response.evidence_refs.map((r) => r.evidence_id));
      for (const item of st.result.evidence.items) {
        const e = map.get(item.evidence_id) ?? { item, uses: [], cited: 0 };
        if (!e.uses.some((u) => u.traceId === st.traceId)) e.uses.push({ traceId: st.traceId, action: st.result.action });
        if (cited.has(item.evidence_id)) e.cited += 1;
        map.set(item.evidence_id, e);
      }
    }
    return [...map.values()].sort((a, b) => b.uses.length - a.uses.length || b.cited - a.cited);
  }, [stored]);

  const q = foldForMatch(query);
  const visible = entries.filter(
    (e) =>
      (!resolutionOnly || e.item.quality?.resolution_relevance) &&
      (!q || foldForMatch(e.item.customer_message).includes(q) || foldForMatch(e.item.brand_reply).includes(q) || foldForMatch(e.item.evidence_id).includes(q)),
  );

  if (!hydrated) return <SkeletonRows rows={4} />;

  return (
    <Card
      title="Evidence retrieved in this browser's simulations"
      description="Historical cases ResolveAI retrieved from the corpus during your simulations, showing relevance scores and verified resolution signals."
      bodyClassName="p-0"
    >
      {!entries.length ? (
        <EmptyState icon={BookOpen} title="No evidence browsed yet" action={<ButtonLink href="/simulate" variant="primary">Run a simulation</ButtonLink>}>
          Run a conversation in the simulator. Every historical case retrieved for it, cited or not, appears here with its relevance, resolution signal and source.
        </EmptyState>
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-3 border-b border-line px-4 py-3">
            <div className="relative w-full sm:w-80">
              <label htmlFor="evidence-search" className="sr-only">
                Search evidence text
              </label>
              <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-ink-3" aria-hidden="true" />
              <input
                id="evidence-search"
                type="search"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search customer message, reply or case id"
                className="h-8 w-full rounded-md border border-line bg-surface pr-2 pl-8 text-[13px] placeholder:text-ink-3 focus:border-brand-500"
              />
            </div>
            <label className="inline-flex items-center gap-2 text-[13px] text-ink-2">
              <input type="checkbox" checked={resolutionOnly} onChange={(e) => setResolutionOnly(e.target.checked)} className="size-4 accent-brand-600" />
              Only replies that state a resolution
            </label>
            <span className="ml-auto text-xs text-ink-3 tabular">
              {visible.length} of {entries.length} cases
            </span>
          </div>
          {visible.length ? (
            <ul className="grid gap-3 p-4 md:grid-cols-2 2xl:grid-cols-3">
              {visible.map((e) => (
                <li key={e.item.evidence_id} className="flex min-w-0 flex-col gap-1.5">
                  <EvidenceCard item={e.item} cited={e.cited > 0} />
                  <p className="px-1 text-xs text-ink-3">
                    Retrieved for {e.uses.length} conversation{e.uses.length === 1 ? "" : "s"}
                    {e.cited ? `, cited in ${e.cited} generated repl${e.cited === 1 ? "y" : "ies"}` : ""}:{" "}
                    {e.uses.slice(0, 3).map((u, i) => (
                      <span key={u.traceId}>
                        {i ? ", " : ""}
                        <Link href={`/conversations/${u.traceId}`} className="font-mono text-brand-700 hover:underline">
                          {shortId(u.traceId)}
                        </Link>{" "}
                        ({ACTION_META[u.action].label.toLowerCase()})
                      </span>
                    ))}
                  </p>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState icon={Search} title="No cases match" />
          )}
          <p className="border-t border-line px-4 py-2.5 text-xs text-ink-3">Rank and scores shown are from the first conversation that retrieved each case.</p>
        </>
      )}
    </Card>
  );
}
