import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import worker, { type Env } from "../src/index";
import { fakeD1 } from "./fakeD1";
import { fakeKv } from "./fakeKv"; // see Step 1a

function makeEnv(db: D1Database): Env {
  return {
    RATE_KV: fakeKv(),
    INSIGHTS_DB: db,
    GEMINI_API_KEY: "k",
    TURNSTILE_SECRET_KEY: "s",
    ALLOWED_ORIGIN: "https://jinholee.is-a.dev",
    MONTHLY_CEILING: "5000",
    MAX_TOKENS: "700",
  };
}

function makeCtx() {
  const promises: Promise<unknown>[] = [];
  return {
    ctx: { waitUntil: (p: Promise<unknown>) => promises.push(p), passThroughOnException: () => {} } as unknown as ExecutionContext,
    promises,
  };
}

beforeEach(() => vi.restoreAllMocks());
afterEach(() => vi.unstubAllGlobals());

describe("scheduled (digest cron)", () => {
  it("runs the digest: reads questions, calls Gemini once, writes a digest, purges", async () => {
    const db = fakeD1((sql) => {
      if (sql.includes("MAX(ts)")) return { first: { ts: 0 } };
      if (sql.includes("WHERE ts > ?")) return { results: [{ id: 1, ts: 5, text: "q", country: "DE", msg_count: 1 }] };
      return {};
    });
    const fetchMock = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => ({ candidates: [{ content: { parts: [{ text: "## Theme" }] } }] }),
    }));
    vi.stubGlobal("fetch", fetchMock);

    const { ctx, promises } = makeCtx();
    await worker.scheduled!({ cron: "0 6 * * *", scheduledTime: 0 } as any, makeEnv(db.db), ctx);
    await Promise.all(promises);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(db.calls.find((c) => c.sql.includes("INSERT INTO digests"))).toBeTruthy();
    expect(db.calls.find((c) => c.sql.includes("DELETE FROM questions"))).toBeTruthy();
  });
});
