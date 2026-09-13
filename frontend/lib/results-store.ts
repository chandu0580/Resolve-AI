/**
 * Full results of simulations run from this browser, kept in localStorage.
 *
 * Why: the API's audit traces deliberately never store customer text or evidence text, so a trace alone cannot re-render the
 * conversation workspace. The complete (already PII-redacted) API response is kept here instead, on this device only, capped
 * at MAX_RESULTS and clearable from the UI. Nothing here is invented: every entry is a response the API returned.
 */
import { useSyncExternalStore } from "react";
import type { ResolveResponse } from "@/lib/api/types";

export const STORAGE_KEY = "resolveai.results.v1";
export const MAX_RESULTS = 50;
const CHANGE_EVENT = "resolveai:results-changed";

export interface StoredResult {
  traceId: string;
  savedAt: string;
  source: string;
  result: ResolveResponse;
}

const EMPTY: StoredResult[] = [];
let cacheRaw: string | null = null;
let cacheValue: StoredResult[] = EMPTY;

function read(): StoredResult[] {
  if (typeof window === "undefined") return EMPTY;
  let raw: string | null = null;
  try {
    raw = window.localStorage.getItem(STORAGE_KEY);
  } catch {
    return EMPTY;
  }
  if (raw === cacheRaw) return cacheValue;
  cacheRaw = raw;
  try {
    const parsed = raw ? (JSON.parse(raw) as StoredResult[]) : EMPTY;
    cacheValue = Array.isArray(parsed) ? parsed.filter((x) => x && typeof x.traceId === "string" && x.result) : EMPTY;
  } catch {
    cacheValue = EMPTY;
  }
  return cacheValue;
}

function write(items: StoredResult[]): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(items.slice(0, MAX_RESULTS)));
  } catch {
    /* storage full or blocked: the result is still shown for this page view */
  }
  window.dispatchEvent(new Event(CHANGE_EVENT));
}

export function loadResults(): StoredResult[] {
  return read();
}

export function getStoredResult(traceId: string): StoredResult | undefined {
  return read().find((r) => r.traceId === traceId);
}

export function saveResult(result: ResolveResponse, source: string): StoredResult {
  const entry: StoredResult = { traceId: result.trace_id, savedAt: new Date().toISOString(), source, result };
  write([entry, ...read().filter((r) => r.traceId !== result.trace_id)]);
  return entry;
}

export function clearResults(): void {
  write([]);
}

function subscribe(onChange: () => void): () => void {
  window.addEventListener(CHANGE_EVENT, onChange);
  window.addEventListener("storage", onChange);
  return () => {
    window.removeEventListener(CHANGE_EVENT, onChange);
    window.removeEventListener("storage", onChange);
  };
}

export function useStoredResults(): StoredResult[] {
  return useSyncExternalStore(subscribe, read, () => EMPTY);
}
