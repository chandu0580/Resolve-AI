import { FileSearch, TriangleAlert } from "lucide-react";
import { Card, Notice } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/states";
import { EvidenceCard } from "@/components/evidence/evidence-card";
import type { EvidenceSet } from "@/lib/api/types";
import { fixed, humanize, pct } from "@/lib/format";
import { EVIDENCE_LEVEL_META, SUFFICIENCY_REASON_LABELS, evidenceLevel } from "@/lib/labels";

export const INSUFFICIENT_EVIDENCE_TEXT = "ResolveAI did not find sufficient historical evidence to safely answer.";

export function ResolutionCandidates({ evidence }: { evidence: EvidenceSet }) {
  const clusters = evidence.resolution_candidates ?? [];
  if (!clusters.length) {
    return <p className="text-[13px] text-ink-3">No resolution pattern: the retrieved replies do not share an instruction-bearing resolution.</p>;
  }
  return (
    <ul className="space-y-2">
      {clusters.map((c) => (
        <li key={c.representative_id} className="rounded-md border border-line px-3 py-2">
          <div className="flex flex-wrap items-baseline justify-between gap-2 text-[13px]">
            <span className="font-medium text-ink">{humanize(c.action_class)}</span>
            <span className="tabular text-xs text-ink-3">
              {c.support_count} cases · {pct(c.share, 0)} of support · mean similarity {fixed(c.mean_similarity)}
            </span>
          </div>
          <p className="mt-1 line-clamp-2 text-xs text-ink-2">{c.representative_reply}</p>
        </li>
      ))}
    </ul>
  );
}

/**
 * Evidence-first view. EVIDENCE USED IN RESPONSE lists only the cases an automatic reply cites; RETRIEVED EVIDENCE lists the rest.
 * Retrieval is similarity, not trust: a retrieved case is never presented as a verified answer.
 */
export function EvidencePanel({ evidence, citedIds = [] }: { evidence: EvidenceSet; citedIds?: string[] }) {
  const cited = new Set(citedIds);
  const used = evidence.items.filter((i) => cited.has(i.evidence_id));
  const retrieved = evidence.items.filter((i) => !cited.has(i.evidence_id));
  const level = evidenceLevel(evidence.sufficiency_level);
  return (
    <Card title="Evidence" description={`${evidence.items.length} retrieved · ${used.length} used in response · retriever ${evidence.retriever}`} bodyClassName="p-3 space-y-4">
      {!evidence.sufficient ? (
        <Notice tone="warning" icon={TriangleAlert} title={INSUFFICIENT_EVIDENCE_TEXT}>
          Evidence level {EVIDENCE_LEVEL_META[level].label.toLowerCase()}: {SUFFICIENCY_REASON_LABELS[evidence.sufficiency_reason ?? ""] ?? humanize(evidence.sufficiency_reason)}. The cases below were retrieved by
          similarity for context only; being retrieved does not make a case correct or applicable to this customer.
        </Notice>
      ) : null}

      <section aria-label="Evidence used in response">
        <h3 className="mb-1.5 px-0.5 text-[11px] font-semibold tracking-wide text-ink uppercase">Evidence used in response</h3>
        {used.length ? (
          <div className="space-y-2.5">
            <p className="px-0.5 text-xs text-ink-3">The automatic reply cites exactly these cases; verification checked the reply against them.</p>
            {used.map((item) => (
              <EvidenceCard key={item.evidence_id} item={item} cited />
            ))}
          </div>
        ) : (
          <p className="px-0.5 text-[13px] text-ink-3">No evidence was used in a customer response: no automatic reply cites a historical case.</p>
        )}
      </section>

      <div>
        <h3 className="mb-1.5 px-0.5 text-xs font-medium text-ink">Resolution patterns</h3>
        <ResolutionCandidates evidence={evidence} />
      </div>

      <section aria-label="Retrieved evidence">
        <h3 className="mb-1.5 px-0.5 text-[11px] font-semibold tracking-wide text-ink uppercase">Retrieved evidence{used.length ? " (not cited)" : ""}</h3>
        {evidence.items.length ? (
          retrieved.length ? (
            <div className="space-y-2.5">
              <p className="px-0.5 text-xs text-ink-3">Ranked by similarity and the resolution reranker. Retrieved is not the same as trustworthy.</p>
              {retrieved.map((item) => (
                <EvidenceCard key={item.evidence_id} item={item} />
              ))}
            </div>
          ) : (
            <p className="px-0.5 text-[13px] text-ink-3">Every retrieved case is cited above.</p>
          )
        ) : (
          <EmptyState icon={FileSearch} title="No evidence retrieved">
            Retrieval returned no historical cases for this message, so no automatic answer was possible.
          </EmptyState>
        )}
      </section>
    </Card>
  );
}
