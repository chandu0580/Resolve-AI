/**
 * Same-origin forwarder for browser calls: /api/v1/<endpoint> -> RESOLVEAI_API_URL/api/v1/<endpoint>.
 * Only the API's own endpoints are forwarded; the body, X-Request-ID and the API's status and headers pass through unchanged.
 * It adds no logic: failures to reach the API become the same error body shape the API uses.
 */
import { NextRequest } from "next/server";
import { serverApiUrl } from "@/lib/api/client";

export const dynamic = "force-dynamic";

const ALLOWED = /^(resolve|traces|traces\/[A-Za-z0-9_-]{1,64}|health|ready|config|evaluation\/summary|evaluation\/release|agent\/profile|knowledge\/summary|demo\/scenarios)$/;
const TIMEOUT_MS = Number(process.env.RESOLVEAI_PROXY_TIMEOUT_MS ?? 190_000);

function errorBody(status: number, code: string, message: string, requestId: string | null) {
  return Response.json({ error_code: code, message, request_id: requestId ?? "unknown", trace_id: null, details: null }, { status, headers: { "Cache-Control": "no-store" } });
}

async function forward(req: NextRequest, params: Promise<{ path: string[] }>): Promise<Response> {
  const { path } = await params;
  const sub = path.join("/");
  const requestId = req.headers.get("x-request-id");
  if (!ALLOWED.test(sub)) return errorBody(404, "not_found", "No such endpoint.", requestId);

  const headers: Record<string, string> = { Accept: "application/json" };
  const contentType = req.headers.get("content-type");
  if (contentType) headers["Content-Type"] = contentType;
  if (requestId) headers["X-Request-ID"] = requestId;
  // The API token is attached here, from the console server's environment. A browser-supplied Authorization header is never forwarded.
  const token = process.env.RESOLVEAI_API_TOKEN;
  if (token) headers.Authorization = `Bearer ${token}`;

  let upstream: Response;
  try {
    upstream = await fetch(`${serverApiUrl()}/api/v1/${sub}${req.nextUrl.search}`, {
      method: req.method,
      headers,
      body: req.method === "POST" ? await req.text() : undefined,
      cache: "no-store",
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
  } catch (err) {
    if (err instanceof Error && (err.name === "TimeoutError" || err.name === "AbortError")) {
      return errorBody(504, "timeout", `ResolveAI did not answer within ${Math.round(TIMEOUT_MS / 1000)} s.`, requestId);
    }
    return errorBody(502, "api_unavailable", "The ResolveAI API is not reachable from the console server.", requestId);
  }

  const out = new Headers({ "Content-Type": upstream.headers.get("content-type") ?? "application/json", "Cache-Control": "no-store" });
  for (const name of ["x-request-id", "x-trace-id", "retry-after"]) {
    const value = upstream.headers.get(name);
    if (value) out.set(name, value);
  }
  return new Response(await upstream.text(), { status: upstream.status, headers: out });
}

export async function GET(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  return forward(req, ctx.params);
}

export async function POST(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  return forward(req, ctx.params);
}
