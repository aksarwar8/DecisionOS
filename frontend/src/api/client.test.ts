// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { request } from "./client";

describe("API client", () => {
  afterEach(() => vi.restoreAllMocks());
  it("encodes repeated parameters", async () => {
    const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 }));
    await request("/catalog/products", { params: { search: "FOODS 1", product_ids: [1, 2] } });
    expect(fetch.mock.calls[0][0]).toBe("/api/catalog/products?search=FOODS+1&product_ids=1&product_ids=2");
  });
  it("preserves backend error and request ID", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ detail: "Bad request" }), {
      status: 400, headers: { "X-Request-ID": "abc" },
    }));
    await expect(request("/test")).rejects.toMatchObject({ message: "Bad request", status: 400, requestId: "abc", name: "Error" });
  });
});
