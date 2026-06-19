import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import worker, { type Env } from "../src/index";
import { fakeD1 } from "./fakeD1";
import { fakeKv } from "./fakeKv";

const ALLOWED = "https://jinholee.is-a.dev";

function makeCtx() {
  const promises: Promise<unknown>[] = [];
  const ctx = {
    waitUntil: (p: Promise<unknown>) => {
      promises.push(p);
    },
    passThroughOnException: () => {},
  } as unknown as ExecutionContext;
  return { ctx, promises };
}

function makeEnv(kv: KVNamespace = fakeKv(), db: D1Database = fakeD1().db): Env {
  return {
    RATE_KV: kv,
    INSIGHTS_DB: db,
    GEMINI_API_KEY: "k",
    TURNSTILE_SECRET_KEY: "s",
    ALLOWED_ORIGIN: ALLOWED,
    MONTHLY_CEILING: "5000",
    MAX_TOKENS: "700",
  };
}

// Turnstile is the only outbound fetch on the /lead path (Telegram is unconfigured
// in tests, so notifyLead no-ops). Branch on URL for safety.
function stubFetch(turnstileSuccess = true) {
  const mock = vi.fn(async (url: string) => {
    if (String(url).includes("challenges.cloudflare.com/turnstile")) {
      return { json: async () => ({ success: turnstileSuccess }) } as unknown as Response;
    }
    throw new Error(`unexpected fetch URL: ${url}`);
  });
  vi.stubGlobal("fetch", mock);
  return mock;
}

function postLead(origin: string | null, body: string): Request {
  const headers: Record<string, string> = { "content-type": "application/json" };
  if (origin) headers.Origin = origin;
  return new Request("https://twin.example/lead", { method: "POST", headers, body });
}

const validLead = JSON.stringify({ email: "a@b.co", name: "Ada", message: "hi", consent: true, msg_count: 4, turnstileToken: "tok" });

beforeEach(() => vi.restoreAllMocks());
afterEach(() => vi.unstubAllGlobals());

describe("POST /lead", () => {
  it("disallowed origin → 403", async () => {
    stubFetch();
    const res = await worker.fetch(postLead("https://evil.example", validLead), makeEnv(), makeCtx().ctx);
    expect(res.status).toBe(403);
  });

  it("non-JSON body → 400, Turnstile not called", async () => {
    const fetchMock = stubFetch();
    const res = await worker.fetch(postLead(ALLOWED, "not json {"), makeEnv(), makeCtx().ctx);
    expect(res.status).toBe(400);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("missing consent → 400 before Turnstile", async () => {
    const fetchMock = stubFetch();
    const body = JSON.stringify({ email: "a@b.co", turnstileToken: "tok" });
    const res = await worker.fetch(postLead(ALLOWED, body), makeEnv(), makeCtx().ctx);
    expect(res.status).toBe(400);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("malformed email → 400 before Turnstile", async () => {
    const fetchMock = stubFetch();
    const body = JSON.stringify({ email: "nope", consent: true, turnstileToken: "tok" });
    const res = await worker.fetch(postLead(ALLOWED, body), makeEnv(), makeCtx().ctx);
    expect(res.status).toBe(400);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("Turnstile failure → 403, nothing stored", async () => {
    stubFetch(false);
    const { db, calls } = fakeD1();
    const res = await worker.fetch(postLead(ALLOWED, validLead), makeEnv(fakeKv(), db), makeCtx().ctx);
    expect(res.status).toBe(403);
    expect(calls.find((c) => c.sql.includes("INSERT INTO contact_submissions"))).toBeUndefined();
  });

  it("per-IP daily cap (3) exceeded → 429, nothing stored", async () => {
    stubFetch();
    const { db, calls } = fakeD1();
    const env = makeEnv(fakeKv({ "lead:0.0.0.0": "3" }), db);
    const res = await worker.fetch(postLead(ALLOWED, validLead), env, makeCtx().ctx);
    expect(res.status).toBe(429);
    expect(calls.find((c) => c.sql.includes("INSERT INTO contact_submissions"))).toBeUndefined();
  });

  it("happy path → 200, stores one lead row (consent=1) and schedules notify", async () => {
    stubFetch();
    const { db, calls } = fakeD1();
    const { ctx, promises } = makeCtx();
    const res = await worker.fetch(postLead(ALLOWED, validLead), makeEnv(fakeKv(), db), ctx);
    expect(res.status).toBe(200);
    await Promise.all(promises); // flush the fire-and-forget notify
    const insert = calls.find((c) => c.sql.includes("INSERT INTO contact_submissions"));
    expect(insert).toBeTruthy();
    // args: [ts, email, name, message, country, msg_count]
    expect(insert!.args[1]).toBe("a@b.co");
    expect(insert!.args[2]).toBe("Ada");
    expect(insert!.args[5]).toBe(4);
  });

  it("D1 insert failure → 502 application/json", async () => {
    stubFetch();
    // A db whose prepare().run() throws simulates a storage failure.
    const db = {
      prepare() {
        return { bind: () => ({ run: async () => { throw new Error("d1 down"); } }) };
      },
    } as unknown as D1Database;
    const res = await worker.fetch(postLead(ALLOWED, validLead), makeEnv(fakeKv(), db), makeCtx().ctx);
    expect(res.status).toBe(502);
    expect(res.headers.get("content-type")).toBe("application/json");
  });

  it("coerces a non-number msg_count to null in the stored row", async () => {
    stubFetch();
    const { db, calls } = fakeD1();
    const { ctx, promises } = makeCtx();
    const body = JSON.stringify({ email: "a@b.co", consent: true, msg_count: "oops", turnstileToken: "tok" });
    const res = await worker.fetch(postLead(ALLOWED, body), makeEnv(fakeKv(), db), ctx);
    expect(res.status).toBe(200);
    await Promise.all(promises);
    const insert = calls.find((c) => c.sql.includes("INSERT INTO contact_submissions"));
    expect(insert).toBeTruthy();
    // args: [ts, email, name, message, country, msg_count] — non-number msg_count → null
    expect(insert!.args[5]).toBe(null);
  });
});
