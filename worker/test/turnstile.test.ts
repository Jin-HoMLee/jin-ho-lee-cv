import { describe, expect, it, vi } from "vitest";
import { verifyTurnstile } from "../src/turnstile";

describe("verifyTurnstile", () => {
  it("returns true when Cloudflare reports success", async () => {
    const fakeFetch = vi.fn().mockResolvedValue({ json: async () => ({ success: true }) });
    const ok = await verifyTurnstile("tok", "secret", "1.2.3.4", fakeFetch as unknown as typeof fetch);
    expect(ok).toBe(true);
  });

  it("returns false on failure and on a missing token", async () => {
    const fakeFetch = vi.fn().mockResolvedValue({ json: async () => ({ success: false }) });
    expect(await verifyTurnstile("tok", "secret", "1.2.3.4", fakeFetch as unknown as typeof fetch)).toBe(false);
    expect(await verifyTurnstile("", "secret", "1.2.3.4", fakeFetch as unknown as typeof fetch)).toBe(false);
  });
});
