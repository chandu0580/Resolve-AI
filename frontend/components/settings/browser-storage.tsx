"use client";

import { Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, KeyValues, Mono } from "@/components/ui/card";
import { SkeletonRows } from "@/components/ui/states";
import { MAX_RESULTS, STORAGE_KEY, clearResults, useStoredResults } from "@/lib/results-store";
import { useHydrated } from "@/lib/use-hydrated";

/** What this console keeps in the browser, with a way to remove it. */
export function BrowserStorageCard() {
  const hydrated = useHydrated();
  const stored = useStoredResults();
  return (
    <Card title="Browser storage" description="The only data the console keeps in this browser.">
      {!hydrated ? (
        <SkeletonRows rows={3} />
      ) : (
        <>
          <KeyValues
            items={[
              { label: "Stored results", value: `${stored.length} of at most ${MAX_RESULTS}` },
              { label: "Storage key", value: <Mono>{STORAGE_KEY}</Mono>, hint: "localStorage of this browser only; never sent to the API or any other service." },
              {
                label: "Contents",
                value: "Full simulation results: the PII-redacted conversation, decision, evidence and handoff packet.",
                hint: "Kept because audit traces never store text, so this is the only way to reopen a conversation's text. No tokens, secrets or credentials are stored.",
              },
            ]}
          />
          <div className="mt-3">
            <Button size="sm" icon={Trash2} onClick={clearResults} disabled={!stored.length}>
              Clear stored results
            </Button>
          </div>
        </>
      )}
    </Card>
  );
}
