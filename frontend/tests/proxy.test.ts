// @vitest-environment node
/** The same-origin forwarder is the only path from the browser to the API: it must forward only API endpoints, attach the server token, and never pass browser credentials or cookies. */
import { NextRequest } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { GET, POST } from "@/app/api/v1/[...path]/route";

const SERVER_TOKEN = "server-token-0123456789-abcdefghijklmnopqrstu";
const ctx = (path: string[]) => ({ params: Promise.resolve({ path }) });

describe("API forwarder", () => {
  beforeEach(() => {
    process.env.RESOLVEAI_API_URL = "http://api.internal:8000";
    process.env.RESOLVEAI_API_TOKEN = SERVER_TOKEN;
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify({ items: [], limit: 5 }), { status: 200, headers: { "content-type": "application/json", "x-request-id": "req-1", "set-cookie": "session=abc" } })),
    );
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    delete process.env.RESOLVEAI_API_TOKEN;
    delete process.env.RESOLVEAI_API_URL;
  });

  it.each([["docs"], ["openapi.json"], ["traces/../config"], ["traces/abc/def"], ["admin"], ["resolve/extra"], ["evaluation"]])("refuses %s without contacting the API", async (sub) => {
    const res = await GET(new NextRequest(`http://console.local/api/v1/${sub}`), ctx(sub.split("/")));
    expect(res.status).toBe(404);
    expect((await res.json()).error_code).toBe("not_found");
    expect(fetch).not.toHaveBeenCalled();
  });

  it("attaches the server token, drops browser credentials and cookies, and passes status and correlation ids", async () => {
    const req = new NextRequest("http://console.local/api/v1/traces?limit=5", { headers: { authorization: "Bearer browser-supplied-token", cookie: "x=1", "x-request-id": "req-1" } });
    const res = await GET(req, ctx(["traces"]));
    const [url, init] = vi.mocked(fetch).mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://api.internal:8000/api/v1/traces?limit=5");
    const headers = init.headers as Record<string, string>;
    expect(headers.Authorization).toBe(`Bearer ${SERVER_TOKEN}`);
    expect(JSON.stringify(headers)).not.toContain("browser-supplied-token");
    expect(JSON.stringify(headers).toLowerCase()).not.toContain("cookie");
    expect(res.status).toBe(200);
    expect(res.headers.get("x-request-id")).toBe("req-1");
    expect(res.headers.get("set-cookie")).toBeNull();
    expect(res.headers.get("cache-control")).toBe("no-store");
  });

  it("forwards the POST body unchanged for /resolve", async () => {
    const body = JSON.stringify({ conversation: [{ role: "customer", text: "battery drains" }] });
    await POST(new NextRequest("http://console.local/api/v1/resolve", { method: "POST", body, headers: { "content-type": "application/json" } }), ctx(["resolve"]));
    const [, init] = vi.mocked(fetch).mock.calls[0] as [string, RequestInit];
    expect(init.method).toBe("POST");
    expect(init.body).toBe(body);
  });

  it("answers an unreachable API with the API's error shape and no internal detail", async () => {
    vi.mocked(fetch).mockRejectedValueOnce(new Error("connect ECONNREFUSED 10.0.0.5:8000"));
    const res = await GET(new NextRequest("http://console.local/api/v1/health"), ctx(["health"]));
    const b = await res.json();
    expect(res.status).toBe(502);
    expect(b.error_code).toBe("api_unavailable");
    expect(JSON.stringify(b)).not.toContain("10.0.0.5");
  });
});
