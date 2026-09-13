"use client";

import { ChevronDown, ChevronRight, Database, Quote } from "lucide-react";
import { useId, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { KeyValues, Mono } from "@/components/ui/card";
import type { EvidenceItem } from "@/lib/api/types";
import { dateOnly, fixed, humanize } from "@/lib/format";
import { intentLabel } from "@/lib/labels";

const OUTCOME_LABELS: Record<string, string> = {
  positive: "Customer followed up positively",
  negative: "Customer followed up negatively",
  mixed: "Mixed customer follow-up",
  none: "No customer follow-up signal",
};

const SOURCE_LABELS: Record<string, string> = {
  pair: "question-and-reply index",
  customer: "customer-message index",
  reply: "reply index",
};

/** Why this case was selected, stated only from signals the retrieval and gate already recorded. */
export function selectionReasons(item: EvidenceItem): string[] {
  const q = item.quality;
  const out = [`Ranked #${item.rank} in the ${SOURCE_LABELS[item.retrieval_source] ?? item.retrieval_source} (${item.retrieval_method}).`];
  if (q) {
    out.push(`Semantic similarity ${fixed(q.semantic_relevance)} to the redacted customer message.`);
    out.push(
      q.intent_match
        ? `About the same issue category (${intentLabel(q.candidate_intent)}).`
        : `About a different issue category (${intentLabel(q.candidate_intent)}), so it counts less.`,
    );
    out.push(q.resolution_relevance ? `The historical reply states a resolution (${humanize(q.action_class).toLowerCase()}).` : "The historical reply does not state a concrete resolution.");
    out.push(q.temporal_eligible ? "Written before the customer's message." : "Not eligible: written after the customer's message.");
    if (q.same_customer) out.push("From the same customer's earlier thread, so it is not independent support.");
  }
  return out;
}

export function EvidenceCard({ item, cited = false, defaultExpanded = false }: { item: EvidenceItem; cited?: boolean; defaultExpanded?: boolean }) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const [showSource, setShowSource] = useState(false);
  const uid = useId();
  const q = item.quality;
  const detailsId = `${uid}-details`;
  const sourceId = `${uid}-source`;
  return (
    <article id={`evidence-${item.evidence_id}`} aria-labelledby={`${uid}-title`} className="scroll-mt-20 rounded-lg border border-line bg-surface">
      <header className="flex flex-wrap items-start justify-between gap-2 px-3.5 pt-3">
        <div className="min-w-0">
          <h3 id={`${uid}-title`} className="text-[13px] font-semibold text-ink">
            <span className="mr-1.5 text-ink-3 tabular">#{item.rank}</span>Case {item.evidence_id}
          </h3>
          <p className="mt-0.5 text-xs text-ink-3">
            {dateOnly(item.created_at)} · thread {item.thread_id}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-1">
          {cited ? <Badge tone="success">Cited in reply</Badge> : null}
          {q ? (
            <Badge tone={q.resolution_relevance ? "brand" : "neutral"} title="Whether the historical reply states a resolution">
              {q.resolution_relevance ? `Resolution: ${humanize(q.action_class).toLowerCase()}` : "No stated resolution"}
            </Badge>
          ) : null}
        </div>
      </header>
      <div className="space-y-2 px-3.5 py-2.5">
        <div>
          <div className="mb-0.5 text-[11px] font-medium tracking-wide text-ink-3 uppercase">Customer (historical)</div>
          <p className={`text-[13px] text-ink-2 ${expanded ? "" : "line-clamp-2"}`}>{item.customer_message}</p>
        </div>
        <div className="rounded-md border-l-2 border-brand-500 bg-brand-50/60 px-2.5 py-1.5">
          <div className="mb-0.5 flex items-center gap-1 text-[11px] font-medium tracking-wide text-brand-700 uppercase">
            <Quote className="size-3" aria-hidden="true" /> Support reply (historical)
          </div>
          <p className={`text-[13px] text-ink ${expanded ? "" : "line-clamp-3"}`}>{item.brand_reply}</p>
        </div>
        <dl className="flex flex-wrap gap-x-4 gap-y-0.5 text-xs">
          <div className="flex gap-1">
            <dt className="text-ink-3">Relevance</dt>
            <dd className="tabular text-ink">{q ? fixed(q.semantic_relevance) : "n/a"}</dd>
          </div>
          <div className="flex gap-1">
            <dt className="text-ink-3">Resolution relevance</dt>
            <dd className="text-ink">{q ? (q.resolution_relevance ? "Yes" : "No") : "n/a"}</dd>
          </div>
          <div className="flex gap-1">
            <dt className="text-ink-3">Outcome</dt>
            <dd className="text-ink">{humanize(item.outcome)}</dd>
          </div>
        </dl>
      </div>
      <div className="flex flex-wrap gap-1 border-t border-line px-2 py-1.5">
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          aria-expanded={expanded}
          aria-controls={detailsId}
          className="inline-flex items-center gap-1 rounded px-1.5 py-1 text-xs font-medium text-ink-2 hover:bg-subtle"
        >
          {expanded ? <ChevronDown className="size-3.5" aria-hidden="true" /> : <ChevronRight className="size-3.5" aria-hidden="true" />}
          Why selected
        </button>
        <button
          type="button"
          onClick={() => setShowSource((v) => !v)}
          aria-expanded={showSource}
          aria-controls={sourceId}
          className="inline-flex items-center gap-1 rounded px-1.5 py-1 text-xs font-medium text-ink-2 hover:bg-subtle"
        >
          <Database className="size-3.5" aria-hidden="true" />
          View source
        </button>
      </div>
      {expanded ? (
        <div id={detailsId} className="space-y-3 border-t border-line px-3.5 py-3">
          <div>
            <div className="mb-1 text-xs font-medium text-ink">Why selected</div>
            <ul className="list-disc space-y-0.5 pl-5 text-xs text-ink-2">
              {selectionReasons(item).map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
          </div>
          <KeyValues
            items={[
              { label: "Retrieval method", value: <Mono>{item.retrieval_method}</Mono> },
              { label: "Semantic / lexical", value: q ? `${fixed(q.semantic_relevance)} / ${fixed(q.lexical_relevance)}` : "n/a" },
              { label: "Rerank score", value: fixed(item.scores?.rerank) },
              { label: "Issue category", value: q ? `${intentLabel(q.candidate_intent)}${q.intent_match ? " (matches)" : ""}` : "n/a" },
              { label: "Outcome signal", value: OUTCOME_LABELS[item.outcome] ?? humanize(item.outcome) },
              { label: "Moved to DM", value: item.dm_handoff ? "Yes, the reply moved the case to private messages" : "No" },
              { label: "Evidence quality", value: q ? humanize(q.quality) : "n/a" },
            ]}
          />
        </div>
      ) : null}
      {showSource ? (
        <div id={sourceId} className="border-t border-line px-3.5 py-3">
          <KeyValues
            items={[
              { label: "Dataset", value: <Mono>{item.source?.dataset ?? "n/a"}</Mono> },
              { label: "Brand", value: item.source?.brand ?? "n/a" },
              { label: "Source row", value: <Mono>{item.source_row_id}</Mono> },
              { label: "Thread", value: <Mono>{item.thread_id}</Mono> },
              { label: "Created", value: item.created_at },
              { label: "Preprocessing", value: item.source?.preprocessing_version ?? "n/a" },
              { label: "Knowledge base hash", value: <Mono>{item.source?.kb_hash ?? "n/a"}</Mono> },
            ]}
          />
          <p className="mt-2 text-[11px] text-ink-3">Public Kaggle “Customer Support on Twitter” corpus, as preprocessed and redacted by ResolveAI.</p>
        </div>
      ) : null}
    </article>
  );
}
