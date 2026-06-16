import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import worker, { type Env } from "../src/index";

const ALLOWED = "https://jinholee.is-a.dev";

// In-memory KV stub: enough of the KVNamespace surface for read/bump counters.
function fakeKv() {
  const store = new Map<string, string>();
  return {
    get: vi.fn(async (key: string) => store.get(key) ?? null),
    put: vi.fn(async (key: string, value: string) => {
      store.set(key, value);
    }),
  } as unknown as KVNamespace;
}

function makeEnv(): Env {
  return {
    RATE_KV: fakeKv(),
    GEMINI_API_KEY: "k",
    TURNSTILE_SECRET_KEY: "s",
    ALLOWED_ORIGIN: ALLOWED,
    MONTHLY_CEILING: "5000",
    MAX_TOKENS: "700",
  };
}

// A ReadableStream that emits one string then closes — stands in for the Gemini
// upstream SSE body.
function streamOf(text: string): ReadableStream<Uint8Array> {
  return new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(new TextEncoder().encode(text));
      controller.close();
    },
  });
}

// Branch the global fetch mock on URL: Turnstile siteverify vs Gemini streaming.
function stubFetch(opts: {
  turnstileSuccess?: boolean;
  geminiOk?: boolean;
  geminiStatus?: number;
}) {
  const { turnstileSuccess = true, geminiOk = true, geminiStatus = 200 } = opts;
  const mock = vi.fn(async (url: string) => {
    if (String(url).includes("challenges.cloudflare.com/turnstile")) {
      return { json: async () => ({ success: turnstileSuccess }) } as unknown as Response;
    }
    if (String(url).includes("generativelanguage.googleapis.com")) {
      return {
        ok: geminiOk,
        status: geminiStatus,
        body: geminiOk
          ? streamOf(`data: {"candidates":[{"content":{"parts":[{"text":"hello"}]}}]}\n\n`)
          : null,
      } as unknown as Response;
    }
    throw new Error(`unexpected fetch URL: ${url}`);
  });
  vi.stubGlobal("fetch", mock);
  return mock;
}

function post(origin: string | null, body: string): Request {
  const headers: Record<string, string> = { "content-type": "application/json" };
  if (origin) headers.Origin = origin;
  return new Request("https://twin.example/", { method: "POST", headers, body });
}

const validBody = JSON.stringify({ messages: [{ role: "user", content: "hi" }], turnstileToken: "tok" });

beforeEach(() => {
  vi.restoreAllMocks();
});
afterEach(() => {
  vi.unstubAllGlobals();
});

describe("fetch handler", () => {
  it("OPTIONS returns cors with ACAO for the allowed origin", async () => {
    stubFetch({});
    const req = new Request("https://twin.example/", {
      method: "OPTIONS",
      headers: { Origin: ALLOWED },
    });
    const res = await worker.fetch(req, makeEnv());
    expect(res.status).toBe(200);
    expect(res.headers.get("Access-Control-Allow-Origin")).toBe(ALLOWED);
  });

  it("POST from a disallowed origin → 403", async () => {
    stubFetch({});
    const res = await worker.fetch(post("https://evil.example", validBody), makeEnv());
    expect(res.status).toBe(403);
  });

  it("POST with a non-JSON body → 400 (C1)", async () => {
    stubFetch({});
    const res = await worker.fetch(post(ALLOWED, "not json {"), makeEnv());
    expect(res.status).toBe(400);
    expect(res.headers.get("Access-Control-Allow-Origin")).toBe(ALLOWED);
  });

  it("POST with messages not an array → 400, and Turnstile is not called (C1)", async () => {
    const fetchMock = stubFetch({});
    const badShape = JSON.stringify({ messages: "nope", turnstileToken: "tok" });
    const res = await worker.fetch(post(ALLOWED, badShape), makeEnv());
    expect(res.status).toBe(400);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("POST with Turnstile verify success:false → 403", async () => {
    stubFetch({ turnstileSuccess: false });
    const res = await worker.fetch(post(ALLOWED, validBody), makeEnv());
    expect(res.status).toBe(403);
  });

  it("POST when Gemini returns 429 → 502 application/json, not SSE (I1)", async () => {
    stubFetch({ geminiOk: false, geminiStatus: 429 });
    const res = await worker.fetch(post(ALLOWED, validBody), makeEnv());
    expect(res.status).toBe(502);
    expect(res.headers.get("content-type")).toBe("application/json");
    expect(res.headers.get("content-type")).not.toBe("text/event-stream");
  });

  it("POST happy path → 200 text/event-stream with transformed client envelope", async () => {
    stubFetch({ geminiOk: true, geminiStatus: 200 });
    const res = await worker.fetch(post(ALLOWED, validBody), makeEnv());
    expect(res.status).toBe(200);
    expect(res.headers.get("content-type")).toBe("text/event-stream");
    const text = await res.text();
    expect(text).toContain('"type":"content_block_delta"');
    expect(text).toContain('"text":"hello"');
  });
});
