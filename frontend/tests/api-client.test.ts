import { describe, expect, it, vi } from "vitest";
import { ApiError, api, apiRequest, load } from "@/lib/api/client";
import { fx, jsonResponse } from "./fixtures";

describe("typed API client", () => {
  it("returns data with the correlation headers", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(jsonResponse(fx.traces, 200, { "x-request-id": "req-1", "x-trace-id": "t-1" }));
    const res = await api.traces({ limit: 5, action: "HUMAN_HANDOFF" }, { fetchImpl });
    expect(fetchImpl).toHaveBeenCalledWith("/api/v1/traces?limit=5&action=HUMAN_HANDOFF", expect.objectContaining({ method: "GET", cache: "no-store" }));
    expect(res.data.items.length).toBe(fx.traces.items.length);
    expect(res.requestId).toBe("req-1");
    expect(res.traceId).toBe("t-1");
  });

  it("posts the conversation to /resolve as JSON with an optional request id", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(jsonResponse(fx.autoHandle));
    const request = { conversation: [{ role: "customer" as const, text: "hello" }] };
    const res = await api.resolve(request, { fetchImpl, requestId: "console-test" });
    const [url, init] = fetchImpl.mock.calls[0];
    expect(url).toBe("/api/v1/resolve");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual(request);
    expect(init.headers["X-Request-ID"]).toBe("console-test");
    expect(res.data.action).toBe("AUTO_HANDLE");
  });

  it("turns the API error body into an ApiError with code, message, request id and trace id", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(jsonResponse(fx.errorTraceNotFound, 404));
    const err = await api.trace("0".repeat(32), { fetchImpl }).catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(404);
    expect(err.errorCode).toBe("trace_not_found");
    expect(err.requestId).toBe(fx.errorTraceNotFound.request_id);
    expect(err.traceId).toBe("0".repeat(32));
  });

  it("keeps validation details from a 413", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(jsonResponse(fx.errorInputTooLarge, 413));
    const err = await api.resolve({ conversation: [{ role: "customer", text: "x" }] }, { fetchImpl }).catch((e) => e);
    expect(err.errorCode).toBe("input_too_large");
    expect(err.details).toEqual(fx.errorInputTooLarge.details);
  });

  it("reports an unreachable API as api_unavailable", async () => {
    const fetchImpl = vi.fn().mockRejectedValue(new TypeError("fetch failed"));
    const err = await api.health({ fetchImpl }).catch((e) => e);
    expect(err.errorCode).toBe("api_unavailable");
    expect(err.status).toBe(502);
  });

  it("reports a request that exceeds its timeout as timeout", async () => {
    const fetchImpl = vi.fn((_url: string, init: RequestInit) => new Promise<Response>((_, reject) => init.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")))));
    const err = await apiRequest("/api/v1/health", { timeoutMs: 20, fetchImpl: fetchImpl as unknown as typeof fetch }).catch((e) => e);
    expect(err.errorCode).toBe("timeout");
  });

  it("reports a caller cancellation as cancelled", async () => {
    const controller = new AbortController();
    const fetchImpl = vi.fn((_url: string, init: RequestInit) => new Promise<Response>((_, reject) => init.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")))));
    const pending = apiRequest("/api/v1/resolve", { method: "POST", body: {}, signal: controller.signal, fetchImpl: fetchImpl as unknown as typeof fetch });
    controller.abort();
    await expect(pending).rejects.toMatchObject({ errorCode: "cancelled" });
  });

  it("reports a non-JSON body (for example an HTML proxy page) as invalid_response", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(new Response("<html>Bad gateway</html>", { status: 200 }));
    await expect(api.config({ fetchImpl })).rejects.toMatchObject({ errorCode: "invalid_response" });
  });

  it("treats readiness 503 as a payload, not an error", async () => {
    const body = { ready: false, components: { agent: { state: "loading" } } };
    const fetchImpl = vi.fn().mockResolvedValue(jsonResponse(body, 503));
    const res = await api.ready({ fetchImpl });
    expect(res.status).toBe(503);
    expect(res.data.ready).toBe(false);
  });

  it("load() returns the error instead of throwing, for server components", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(jsonResponse({ error_code: "evaluation_not_available", message: "missing", request_id: "r", trace_id: null, details: null }, 404));
    const res = await load(api.evaluationSummary({ fetchImpl }));
    expect(res.data).toBeNull();
    expect(res.error?.errorCode).toBe("evaluation_not_available");
  });
});
