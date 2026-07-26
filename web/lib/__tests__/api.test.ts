import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { api } from "@/lib/api";

// Helpers to build fake fetch Responses without a real network.
function jsonResponse(body: unknown, init: { ok?: boolean; status?: number } = {}) {
  const ok = init.ok ?? true;
  return {
    ok,
    status: init.status ?? (ok ? 200 : 500),
    json: async () => body,
  } as unknown as Response;
}

describe("api client — request() behavior", () => {
  beforeEach(() => {
    sessionStorage.clear();
    // jsdom's default location is http://localhost/, so the demo-token
    // fallback in getToken() is active; clear any prior token first.
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it("attaches a Bearer token from sessionStorage", async () => {
    sessionStorage.setItem("kc_token", "tok-123");
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ submission_id: "s1" }));
    vi.stubGlobal("fetch", fetchMock);

    await api.getResults("s1");

    const [, opts] = fetchMock.mock.calls[0];
    expect((opts.headers as Record<string, string>).Authorization).toBe("Bearer tok-123");
  });

  it("uses the demo-local-token fallback on localhost when no token is set", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ submission_id: "s1" }));
    vi.stubGlobal("fetch", fetchMock);

    await api.getResults("s1");

    const [, opts] = fetchMock.mock.calls[0];
    expect((opts.headers as Record<string, string>).Authorization).toBe("Bearer demo-local-token");
  });

  it("surfaces the server's `detail` message on a non-ok response", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse({ detail: "Result not found" }, { ok: false, status: 404 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(api.getResults("missing")).rejects.toThrow("Result not found");
  });

  it("falls back to a status message when the error body has no detail", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse({}, { ok: false, status: 500 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(api.getResults("x")).rejects.toThrow("Request failed: 500");
  });

  it("maps a network failure to a friendly message", async () => {
    const fetchMock = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
    vi.stubGlobal("fetch", fetchMock);

    await expect(api.getResults("x")).rejects.toThrow("Network error: unable to reach API");
  });

  it("maps an aborted (timed-out) request to a timeout message", async () => {
    const abortErr = new DOMException("aborted", "AbortError");
    const fetchMock = vi.fn().mockRejectedValue(abortErr);
    vi.stubGlobal("fetch", fetchMock);

    await expect(api.getResults("x")).rejects.toThrow(/timed out/);
  });
});

describe("api client — normalizeDrugRequests via listDrugRequests()", () => {
  beforeEach(() => sessionStorage.clear());
  afterEach(() => vi.restoreAllMocks());

  const row = {
    drug_request_id: "d1",
    result_id: "r1",
    target_gene: "KRAS",
    cancer_type: "NSCLC",
    status: "open",
  };

  it("unwraps a { requests: [...] } payload", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ requests: [row] })));
    const out = await api.listDrugRequests();
    expect(out.requests).toEqual([row]);
  });

  it("passes through a bare array payload", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse([row])));
    const out = await api.listDrugRequests();
    expect(out.requests).toEqual([row]);
  });

  it("returns an empty array for an unexpected shape", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ nope: true })));
    const out = await api.listDrugRequests();
    expect(out.requests).toEqual([]);
  });
});
