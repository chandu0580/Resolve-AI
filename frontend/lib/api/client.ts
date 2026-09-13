/**
 * The only place the UI talks to the ResolveAI API.
 *
 * - On the server (server components) requests go straight to RESOLVEAI_API_URL (default http://127.0.0.1:8000).
 * - In the browser they go to the same-origin route handler /api/v1/* (app/api/v1/[...path]/route.ts), which forwards to the
 *   API. That keeps the backend address server-side and avoids a browser-side CORS dependency.
 * - Every failure becomes an ApiError with the backend's error_code, message, request_id and trace_id when present.
 */
import type {
  AgentProfile,
  AgentTrace,
  DemoScenario,
  EvaluationSummary,
  HealthResponse,
  KnowledgeSummary,
  ReadinessResponse,
  ReleaseEvaluation,
  ResolveRequest,
  ResolveResponse,
  RuntimeConfig,
  TraceListResponse,
} from "./types";

export class ApiError extends Error {
  readonly status: number;
  readonly errorCode: string;
  readonly requestId?: string;
  readonly traceId?: string;
  readonly details?: unknown;

  constructor(status: number, errorCode: string, message: string, extra: { requestId?: string; traceId?: string; details?: unknown } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.errorCode = errorCode;
    this.requestId = extra.requestId;
    this.traceId = extra.traceId;
    this.details = extra.details;
  }
}

export interface ApiResult<T> {
  data: T;
  status: number;
  requestId?: string;
  traceId?: string;
}

interface RequestOptions {
  method?: "GET" | "POST";
  body?: unknown;
  requestId?: string;
  signal?: AbortSignal;
  timeoutMs?: number;
  /** Non-2xx statuses whose body is a normal payload (readiness answers 503 with its component report). */
  payloadStatuses?: number[];
  fetchImpl?: typeof fetch;
}

export const RESOLVE_TIMEOUT_MS = 180_000;
const DEFAULT_TIMEOUT_MS = 20_000;

export function serverApiUrl(): string {
  return (process.env.RESOLVEAI_API_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
}

function baseUrl(): string {
  return typeof window === "undefined" ? serverApiUrl() : "";
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<ApiResult<T>> {
  const { method = "GET", body, requestId, signal, timeoutMs = DEFAULT_TIMEOUT_MS, payloadStatuses = [], fetchImpl = fetch } = options;
  const timeout = AbortSignal.timeout(timeoutMs);
  const combined = signal ? AbortSignal.any([signal, timeout]) : timeout;
  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (requestId) headers["X-Request-ID"] = requestId;
  // Server-side only: the API token lives in the console server's environment and is never bundled for or sent to the browser.
  if (typeof window === "undefined" && process.env.RESOLVEAI_API_TOKEN) headers.Authorization = `Bearer ${process.env.RESOLVEAI_API_TOKEN}`;

  let res: Response;
  try {
    res = await fetchImpl(`${baseUrl()}${path}`, { method, headers, body: body === undefined ? undefined : JSON.stringify(body), cache: "no-store", signal: combined });
  } catch (err) {
    if (timeout.aborted) {
      throw new ApiError(504, "timeout", `ResolveAI did not answer within ${Math.round(timeoutMs / 1000)} s.`);
    }
    if (signal?.aborted) throw new ApiError(499, "cancelled", "The request was cancelled.");
    throw new ApiError(502, "api_unavailable", "The ResolveAI API is not reachable.", { details: err instanceof Error ? err.message : String(err) });
  }

  const reqId = res.headers.get("x-request-id") ?? undefined;
  const traceId = res.headers.get("x-trace-id") ?? undefined;
  const text = await res.text();
  let parsed: unknown;
  try {
    parsed = text ? JSON.parse(text) : undefined;
  } catch {
    throw new ApiError(res.status, "invalid_response", "The API returned a response that is not valid JSON.", { requestId: reqId, traceId });
  }

  if (!res.ok && !payloadStatuses.includes(res.status)) {
    const e = (parsed ?? {}) as { error_code?: string; message?: string; request_id?: string; trace_id?: string | null; details?: unknown };
    throw new ApiError(res.status, e.error_code ?? "http_error", e.message ?? `The API answered ${res.status}.`, {
      requestId: e.request_id ?? reqId,
      traceId: e.trace_id ?? traceId,
      details: e.details,
    });
  }
  if (parsed === undefined) {
    throw new ApiError(res.status, "invalid_response", "The API returned an empty response.", { requestId: reqId, traceId });
  }
  return { data: parsed as T, status: res.status, requestId: reqId, traceId };
}

export const api = {
  resolve: (request: ResolveRequest, opts: { requestId?: string; signal?: AbortSignal; fetchImpl?: typeof fetch } = {}) =>
    apiRequest<ResolveResponse>("/api/v1/resolve", { method: "POST", body: request, timeoutMs: RESOLVE_TIMEOUT_MS, ...opts }),
  trace: (traceId: string, opts: { fetchImpl?: typeof fetch } = {}) => apiRequest<AgentTrace>(`/api/v1/traces/${encodeURIComponent(traceId)}`, opts),
  traces: (params: { limit?: number; action?: string } = {}, opts: { fetchImpl?: typeof fetch } = {}) => {
    const q = new URLSearchParams();
    if (params.limit) q.set("limit", String(params.limit));
    if (params.action) q.set("action", params.action);
    return apiRequest<TraceListResponse>(`/api/v1/traces${q.size ? `?${q}` : ""}`, opts);
  },
  health: (opts: { fetchImpl?: typeof fetch } = {}) => apiRequest<HealthResponse>("/api/v1/health", { timeoutMs: 5_000, ...opts }),
  ready: (opts: { fetchImpl?: typeof fetch } = {}) => apiRequest<ReadinessResponse>("/api/v1/ready", { timeoutMs: 5_000, payloadStatuses: [503], ...opts }),
  config: (opts: { fetchImpl?: typeof fetch } = {}) => apiRequest<RuntimeConfig>("/api/v1/config", { timeoutMs: 5_000, ...opts }),
  evaluationSummary: (opts: { fetchImpl?: typeof fetch } = {}) => apiRequest<EvaluationSummary>("/api/v1/evaluation/summary", opts),
  evaluationRelease: (opts: { fetchImpl?: typeof fetch } = {}) => apiRequest<ReleaseEvaluation>("/api/v1/evaluation/release", opts),
  agentProfile: (opts: { fetchImpl?: typeof fetch } = {}) => apiRequest<AgentProfile>("/api/v1/agent/profile", { timeoutMs: 5_000, ...opts }),
  knowledgeSummary: (opts: { fetchImpl?: typeof fetch } = {}) => apiRequest<KnowledgeSummary>("/api/v1/knowledge/summary", opts),
  demoScenarios: (opts: { fetchImpl?: typeof fetch } = {}) => apiRequest<DemoScenario[]>("/api/v1/demo/scenarios", opts),
};

/** Server-component helper: returns the data or the ApiError, so pages can render an explicit error state instead of throwing. */
export async function load<T>(call: Promise<ApiResult<T>>): Promise<{ data: T; error: null } | { data: null; error: ApiError }> {
  try {
    return { data: (await call).data, error: null };
  } catch (err) {
    if (err instanceof ApiError) return { data: null, error: err };
    return { data: null, error: new ApiError(500, "client_error", err instanceof Error ? err.message : String(err)) };
  }
}
