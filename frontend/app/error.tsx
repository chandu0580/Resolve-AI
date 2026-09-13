"use client";

import { CircleAlert, RotateCcw } from "lucide-react";
import { Button, ButtonLink } from "@/components/ui/button";

export default function ErrorPage({ error, retry }: { error: Error & { digest?: string }; retry: () => void }) {
  return (
    <div className="mx-auto max-w-xl py-10">
      <div role="alert" className="rounded-lg border border-danger-line bg-danger-bg px-5 py-5">
        <div className="flex gap-3">
          <CircleAlert className="mt-0.5 size-5 shrink-0 text-danger" aria-hidden="true" />
          <div className="min-w-0">
            <h1 className="text-sm font-semibold text-ink">This page could not be displayed</h1>
            <p className="mt-1 text-[13px] text-ink-2">The console hit an unexpected error while rendering. The API and the agent are not affected.</p>
            {error.digest ? <p className="mt-2 font-mono text-[11px] text-ink-3">digest {error.digest}</p> : null}
            <div className="mt-4 flex gap-2">
              <Button variant="primary" icon={RotateCcw} onClick={() => retry()}>
                Try again
              </Button>
              <ButtonLink href="/">Overview</ButtonLink>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
