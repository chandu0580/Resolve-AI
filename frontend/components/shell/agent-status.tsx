"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api/client";

type Status = "checking" | "ready" | "loading" | "failed" | "unavailable";

const META: Record<Status, { label: string; dot: string; detail: string }> = {
  checking: { label: "Checking agent", dot: "bg-neutral", detail: "Contacting the API" },
  ready: { label: "Agent ready", dot: "bg-success", detail: "Knowledge base, classifier and evidence gate loaded" },
  loading: { label: "Agent loading", dot: "bg-warning", detail: "Loading knowledge base and models" },
  failed: { label: "Agent failed", dot: "bg-danger", detail: "See /api/v1/ready" },
  unavailable: { label: "API unavailable", dot: "bg-danger", detail: "Start the FastAPI service" },
};

/** Reads /api/v1/ready (which never calls the model). Re-checks only while the agent is not ready. */
export function AgentStatus() {
  const [status, setStatus] = useState<Status>("checking");

  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;
    const check = async () => {
      let next: Status;
      try {
        const { data } = await api.ready();
        const state = (data.components?.agent as { state?: string } | undefined)?.state;
        next = data.ready ? "ready" : state === "failed" ? "failed" : "loading";
      } catch {
        next = "unavailable";
      }
      if (cancelled) return;
      setStatus(next);
      if (next !== "ready") timer = window.setTimeout(check, next === "loading" ? 4000 : 10000);
    };
    void check();
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, []);

  const meta = META[status];
  return (
    <div className="flex items-center gap-2" aria-live="polite">
      <span className={`size-2 shrink-0 rounded-full ${meta.dot}`} aria-hidden="true" />
      <span className="text-xs font-medium text-ink">{meta.label}</span>
      <span className="sr-only">. {meta.detail}</span>
    </div>
  );
}
