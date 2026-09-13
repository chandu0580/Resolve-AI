// @vitest-environment node
import { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";
import { GET, POST } from "@/app/api/v1/[...path]/route";

const ctx = (...path: string[]) => ({ params: Promise.resolve({ path }) });

describe("same-origin API forwarder", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("forwards allowed endpoints with the query, request id, status and correlation headers", async () => {
    const upstream = vi.fn().mockResolvedValue(new Response('{"items":[],"limit":5}', { status: 200, headers: { "content-type": "application/json", "x-request-id": "r1", "x-trace-id": "t1" } }));
    vi.stubGlobal("fetch", upstream);
    const res = await GET(new NextRequest("http://localhost:3000/api/v1/traces?limit=5", { headers: { "x-request-id": "r1" } }), ctx("traces"));
    expect(upstream.mock.calls[0][0]).toBe("http://127.0.0.1:8000/api/v1/traces?limit=5");
    expect(upstream.mock.calls[0][1].headers["X-Request-ID"]).toBe("r1");
    expect(res.status).toBe(200);
    expect(res.headers.get("x-trace-id")).toBe("t1");
    expect(await res.json()).toEqual({ items: [], limit: 5 });
  });

  it("passes the POST body and API error statuses through unchanged", async () => {
    const upstream = vi.fn().mockResolvedValue(new Response('{"error_code":"validation_error"}', { status: 422, headers: { "content-type": "application/json" } }));
    vi.stubGlobal("fetch", upstream);
    const res = await POST(new NextRequest("http://localhost:3000/api/v1/resolve", { method: "POST", body: '{"conversation":[]}', headers: { "content-type": "application/json" } }), ctx("resolve"));
    expect(upstream.mock.calls[0][1].body).toBe('{"conversation":[]}');
    expect(res.status).toBe(422);
  });

  it("does not forward paths outside the API's endpoints", async () => {
    const upstream = vi.fn();
    vi.stubGlobal("fetch", upstream);
    const res = await GET(new NextRequest("http://localhost:3000/api/v1/docs"), ctx("..", "docs"));
    expect(res.status).toBe(404);
    expect(upstream).not.toHaveBeenCalled();
  });

  it("answers api_unavailable in the API's error shape when the backend is down", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("fetch failed")));
    const res = await GET(new NextRequest("http://localhost:3000/api/v1/health"), ctx("health"));
    expect(res.status).toBe(502);
    expect(await res.json()).toMatchObject({ error_code: "api_unavailable", trace_id: null });
  });
});
