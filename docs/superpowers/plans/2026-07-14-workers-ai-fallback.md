# Workers AI Cross-Vendor Fallback (#97) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Cloudflare Workers AI as a final cross-vendor fallback rung so the digital twin survives a full Google/Gemini outage, for both the chat stream and the daily digest cron.

**Architecture:** Extract the vendor-neutral SSE-to-client-envelope transformer out of `gemini.ts` into a new `sse.ts`; add a pure-Workers-AI vendor module `workersai.ts`; the fall-through lives at the callers (`index.ts` chat handler, `digest.ts` cron). Spec: `docs/superpowers/specs/2026-07-14-workers-ai-fallback-design.md`.

**Tech Stack:** TypeScript Cloudflare Worker, vitest 2 (fake-driven, no network), wrangler.

## Global Constraints

- Branch: `97-workers-ai-fallback` (already created and checked out; spec committed as `0d17ab3`).
- Model: `@cf/meta/llama-3.3-70b-instruct-fp8-fast` (single constant `WORKERS_AI_MODEL`; must be live-verified in Task 5 before merge).
- The fallback fires on ANY non-ok Gemini terminal Response (deliberately wider than the issue's "retryable" wording; rationale in the spec).
- Absent `AI` binding ⇒ behavior byte-identical to today (all pre-existing handler tests must keep passing unchanged).
- The digest's unconditional `purgeOld` must never move or become conditional (privacy guarantee).
- Worker tests run with `npm --prefix worker test` from the repo root (never `cd`). Expected: all files pass, zero failures.
- Commit messages: plain, prefix `worker(#97):` (or `docs(#97):`), no attribution trailers.
- No em dashes in any authored text (use "-").
- Type note (deliberate spec refinement): instead of the `Ai` type from `@cloudflare/workers-types` (whose model-name union lags the live catalog and would reject our model id), `workersai.ts` defines a minimal structural `AiBinding` interface. Same runtime object, no version coupling.

---

### Task 1: Extract the vendor-neutral SSE layer into `sse.ts`

Pure refactor, behavior-preserving. The proof is the existing test suite passing with the transformer tests relocated and their assertions unchanged.

**Files:**
- Create: `worker/src/sse.ts`
- Create: `worker/test/sse.test.ts`
- Modify: `worker/src/gemini.ts` (remove moved code, wrap)
- Modify: `worker/src/index.ts:1-8` (imports only)
- Modify: `worker/test/gemini.test.ts` (remove moved tests + now-unused helpers)

**Interfaces:**
- Consumes: current `gemini.ts` internals (`clientMessageStream`, `RESTING_MESSAGE`, `TROUBLE_MESSAGE`, `IDLE_MS`, `geminiToClientStream` body).
- Produces (later tasks rely on these exact exports from `./sse`):
  - `sseToClientStream(upstream: ReadableStream<Uint8Array>, chunkToEnvelopes: ChunkToEnvelopes, opts?: { idleMs?: number }): ReadableStream<Uint8Array>`
  - `type ChunkToEnvelopes = (chunk: any) => object[]`
  - `clientMessageStream(message: string): ReadableStream<Uint8Array>`
  - `RESTING_MESSAGE: string`, `TROUBLE_MESSAGE: string`
  - `gemini.ts` keeps exporting: `streamGemini`, `generateText`, `geminiChunkToEnvelopes`, `geminiToClientStream`, `type ChatMessage`.

- [ ] **Step 1: Create `worker/src/sse.ts`**

The bodies of `clientMessageStream` and the transformer are MOVED VERBATIM from `worker/src/gemini.ts` (currently lines 6-38 and 202-300), with exactly two changes: the transformer is renamed `sseToClientStream` and takes `chunkToEnvelopes` as its second parameter (replacing the hard-coded `geminiChunkToEnvelopes` call).

```typescript
// Vendor-neutral client-envelope streaming layer. Every upstream LLM vendor speaks
// its own SSE dialect; this module owns the single transform pipeline that turns
// any of them into the browser widget's client envelope (web/src/lib/twin.ts),
// plus the friendly terminal messages. Vendor modules (gemini.ts, workersai.ts)
// supply only a pure chunk-to-envelopes mapper.

// Friendly terminal messages surfaced IN the client envelope (as assistant text) so
// the widget shows a clear sentence instead of spinning or throwing a raw error.
// RESTING_MESSAGE is for a known full-cascade quota exhaustion (all rungs 429);
// TROUBLE_MESSAGE is for an ambiguous transient failure (non-quota error, a stalled
// 200 stream, or a 200 stream that closes with no content).
export const RESTING_MESSAGE =
  "The twin is resting — it has reached today's free-tier limit. Please try again later.";
export const TROUBLE_MESSAGE =
  "The twin had trouble responding just now. Please try again in a moment.";

// Worker-side idle guard for the upstream SSE read. Gemini's streaming endpoint can
// answer HTTP 200 and then stall (send nothing, never close), which would otherwise
// keep the Worker open until the runtime kills the request as "hung" (~44s, #103).
// 15s is comfortably under both that cancel and the widget's 30s client-side stall
// guard, and the timer resets on every chunk so a slow-but-progressing answer is
// never cut — only genuine silence trips it.
const IDLE_MS = 15_000;

// A pure mapper from one parsed vendor SSE chunk to zero or more client envelopes.
export type ChunkToEnvelopes = (chunk: any) => object[];

// Build a one-shot client-envelope SSE stream that emits a single assistant message
// then closes — the graceful terminal response for a failed/exhausted upstream.
export function clientMessageStream(message: string): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(
        encoder.encode(
          `data: ${JSON.stringify({ type: "content_block_delta", delta: { text: message } })}\n\n`,
        ),
      );
      controller.close();
    },
  });
}

// Read a vendor's native SSE and re-emit the client envelope SSE. Buffers across
// network chunks, splits on newlines, parses each `data: {json}` line, and
// enqueues `data: ${envelope}\n\n` for every envelope chunkToEnvelopes yields.
// Non-JSON lines (keep-alives, comments, Workers AI's `[DONE]` sentinel) are skipped.
export function sseToClientStream(
  upstream: ReadableStream<Uint8Array>,
  chunkToEnvelopes: ChunkToEnvelopes,
  opts: { idleMs?: number } = {},
): ReadableStream<Uint8Array> {
  const idleMs = opts.idleMs ?? IDLE_MS;
  const reader = upstream.getReader();
  const decoder = new TextDecoder();
  const encoder = new TextEncoder();
  let buffer = "";
  // Whether any real model envelope reached the client. If the upstream stalls or
  // closes without ever producing content (a 200-then-error SSE, or a quota stall),
  // we emit a single TROUBLE_MESSAGE so the widget shows a sentence, not silence.
  let emittedContent = false;

  // Parse one SSE line and enqueue any client envelopes it yields; returns the count
  // enqueued so the pull loop knows whether it produced data this turn.
  function emit(controller: ReadableStreamDefaultController<Uint8Array>, line: string): number {
    const trimmed = line.trimEnd();
    if (!trimmed.startsWith("data:")) return 0;
    const json = trimmed.slice(trimmed.indexOf(":") + 1).trim();
    if (!json) return 0;
    let parsed: unknown;
    try {
      parsed = JSON.parse(json);
    } catch {
      return 0; // keep-alive / non-JSON line
    }
    let count = 0;
    for (const env of chunkToEnvelopes(parsed)) {
      controller.enqueue(encoder.encode(`data: ${JSON.stringify(env)}\n\n`));
      emittedContent = true;
      count++;
    }
    return count;
  }

  // Close the stream, first surfacing TROUBLE_MESSAGE iff nothing was ever emitted.
  function finish(controller: ReadableStreamDefaultController<Uint8Array>): void {
    if (!emittedContent) {
      controller.enqueue(
        encoder.encode(
          `data: ${JSON.stringify({ type: "content_block_delta", delta: { text: TROUBLE_MESSAGE } })}\n\n`,
        ),
      );
    }
    controller.close();
  }

  return new ReadableStream<Uint8Array>({
    async pull(controller) {
      // Loop until this pull either enqueues at least one envelope, closes the stream,
      // or trips the idle guard. A pull that returns without enqueuing is NOT
      // re-invoked by the stream, so a read that yields no client envelope (a
      // keep-alive, an error chunk, or a partial line) must drive another read here
      // rather than leave the consumer hanging.
      for (;;) {
        // Race the upstream read against an idle timeout so a stalled (open-but-silent)
        // connection can never hold the Worker open until the runtime cancels it.
        let timer!: ReturnType<typeof setTimeout>; // set synchronously by the executor below
        const idle = new Promise<"idle">((resolve) => {
          timer = setTimeout(() => resolve("idle"), idleMs);
        });
        let result: ReadableStreamReadResult<Uint8Array> | "idle";
        try {
          result = await Promise.race([reader.read(), idle]);
        } finally {
          clearTimeout(timer);
        }
        if (result === "idle") {
          finish(controller);
          await reader.cancel("idle timeout").catch(() => {});
          return;
        }
        const { done, value } = result;
        if (done) {
          if (buffer) emit(controller, buffer);
          finish(controller);
          return;
        }
        buffer += decoder.decode(value, { stream: true });
        let enqueued = 0;
        let idx: number;
        while ((idx = buffer.indexOf("\n")) !== -1) {
          const line = buffer.slice(0, idx);
          buffer = buffer.slice(idx + 1);
          enqueued += emit(controller, line);
        }
        if (enqueued > 0) return; // produced data — wait for the next pull
      }
    },
    cancel(reason) {
      reader.cancel(reason);
    },
  });
}
```

(The two `—` inside the moved string literals and comments are pre-existing content moved verbatim; do not rewrite them.)

- [ ] **Step 2: Shrink `worker/src/gemini.ts`**

Delete from `gemini.ts`:
- The `RESTING_MESSAGE` / `TROUBLE_MESSAGE` constants and their comment block (lines 6-14).
- The `IDLE_MS` constant and its comment block (lines 16-22).
- `clientMessageStream` and its comment (lines 24-38).
- The entire `geminiToClientStream` implementation and its comment (lines 202-300).

Add at the top of the file:

```typescript
import { sseToClientStream } from "./sse";
```

Add where `geminiToClientStream` used to be:

```typescript
// Read Gemini's native SSE and re-emit the client envelope SSE — a thin wrapper
// binding the shared vendor-neutral transformer to the Gemini chunk dialect.
export function geminiToClientStream(
  upstream: ReadableStream<Uint8Array>,
  opts: { idleMs?: number } = {},
): ReadableStream<Uint8Array> {
  return sseToClientStream(upstream, geminiChunkToEnvelopes, opts);
}
```

Everything else in `gemini.ts` (`ChatMessage`, `MODELS`, `isRetryable`, `streamGemini`, `geminiChunkToEnvelopes`, `generateText`) stays untouched.

- [ ] **Step 3: Update the import block in `worker/src/index.ts`**

Replace lines 1-8:

```typescript
import { streamGemini, geminiToClientStream, type ChatMessage } from "./gemini";
import { clientMessageStream, RESTING_MESSAGE, TROUBLE_MESSAGE } from "./sse";
```

No other `index.ts` change in this task.

- [ ] **Step 4: Move the transformer tests to `worker/test/sse.test.ts`**

Create `worker/test/sse.test.ts`. The three tests are the current `describe("geminiToClientStream graceful degradation")` block from `worker/test/gemini.test.ts` (lines 215-244) with unchanged assertions; only the call site becomes `sseToClientStream(upstream, geminiChunkToEnvelopes, opts)`. The `readAll` and `upstreamOf` helpers move here (they are only used by these tests).

```typescript
import { describe, expect, it } from "vitest";
import { sseToClientStream, TROUBLE_MESSAGE } from "../src/sse";
import { geminiChunkToEnvelopes } from "../src/gemini";

// Drain a client-envelope stream to a single decoded string.
async function readAll(stream: ReadableStream<Uint8Array>): Promise<string> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let out = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    out += decoder.decode(value, { stream: true });
  }
  out += decoder.decode(); // flush any multi-byte char split across the final chunk
  return out;
}

// An upstream SSE body that emits the given chunks (each enqueued verbatim) then closes.
function upstreamOf(...chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream<Uint8Array>({
    start(c) {
      for (const chunk of chunks) c.enqueue(encoder.encode(chunk));
      c.close();
    },
  });
}

// Exercised through the Gemini chunk dialect — the transformer itself is
// vendor-neutral (workersai.test.ts covers the Workers AI dialect).
describe("sseToClientStream graceful degradation", () => {
  const contentChunk = `data: {"candidates":[{"content":{"parts":[{"text":"hello"}]}}]}\n\n`;

  it("passes model content through and appends NO fallback message when the model answered", async () => {
    const out = await readAll(sseToClientStream(upstreamOf(contentChunk), geminiChunkToEnvelopes));
    expect(out).toContain('"text":"hello"');
    expect(out).not.toContain(TROUBLE_MESSAGE);
  });

  it("emits a friendly fallback when the upstream closes with no content (200-then-error SSE)", async () => {
    // Gemini's streaming endpoint can return HTTP 200 then deliver a quota/error
    // chunk that yields zero content envelopes — without a guard the widget gets an
    // empty assistant bubble. Assert the fallback message is surfaced instead.
    const errorChunk = `data: {"error":{"code":429,"status":"RESOURCE_EXHAUSTED"}}\n\n`;
    const out = await readAll(sseToClientStream(upstreamOf(errorChunk), geminiChunkToEnvelopes));
    expect(out).toContain(TROUBLE_MESSAGE);
  });

  it("emits a friendly fallback and closes fast when the upstream stalls (never hangs to the runtime cancel)", async () => {
    // The ~44s hang in #103: a 200 streaming response whose read never resolves.
    // A short idle guard must close the stream cleanly with a fallback message.
    const stalling = new ReadableStream<Uint8Array>({
      pull() {
        return new Promise<void>(() => {}); // never resolves, never enqueues
      },
    });
    const out = await readAll(sseToClientStream(stalling, geminiChunkToEnvelopes, { idleMs: 30 }));
    expect(out).toContain(TROUBLE_MESSAGE);
  });
});
```

- [ ] **Step 5: Trim `worker/test/gemini.test.ts`**

Remove from `gemini.test.ts`:
- The `describe("geminiToClientStream graceful degradation")` block (lines 215-244).
- The `readAll` helper (lines 11-23) and `upstreamOf` helper (lines 25-34) — now unused there.
- `geminiToClientStream`, `RESTING_MESSAGE`, and `TROUBLE_MESSAGE` from the `../src/gemini` import (all three become unused; `RESTING_MESSAGE`/`TROUBLE_MESSAGE` no longer live there anyway).

The import block becomes:

```typescript
import { describe, expect, it, vi } from "vitest";
import { geminiChunkToEnvelopes, generateText, streamGemini } from "../src/gemini";
```

Everything else (`scriptedFetch`, `modelOf`, the cascade and `generateText` describes) stays untouched.

- [ ] **Step 6: Run the worker suite**

Run: `npm --prefix worker test`
Expected: all test files pass (including the new `sse.test.ts` with 3 tests); zero failures. This green run IS the extraction proof.

- [ ] **Step 7: Commit**

```bash
git add worker/src/sse.ts worker/src/gemini.ts worker/src/index.ts worker/test/sse.test.ts worker/test/gemini.test.ts
git commit -m "worker(#97): extract the vendor-neutral SSE client-envelope layer into sse.ts"
```

---

### Task 2: The Workers AI vendor module (`workersai.ts`)

TDD: tests first, watch them fail, then implement.

**Files:**
- Create: `worker/test/workersai.test.ts`
- Create: `worker/src/workersai.ts`

**Interfaces:**
- Consumes: `sseToClientStream`, `type ChunkToEnvelopes` from `./sse` (Task 1); `type ChatMessage` from `./gemini` (pre-existing: `{ role: "user" | "assistant"; content: string }`).
- Produces (Tasks 3 and 4 rely on these exact exports from `./workersai`):
  - `WORKERS_AI_MODEL: string` (value `"@cf/meta/llama-3.3-70b-instruct-fp8-fast"`)
  - `interface AiBinding { run(model: string, options: Record<string, unknown>): Promise<unknown> }`
  - `workersAiChunkToEnvelopes(chunk: any): object[]`
  - `streamWorkersAI(ai: AiBinding, systemText: string, messages: ChatMessage[], maxTokens: number): Promise<ReadableStream<Uint8Array>>`
  - `generateTextWorkersAI(ai: AiBinding, prompt: string): Promise<string>`

- [ ] **Step 1: Write the failing tests**

Create `worker/test/workersai.test.ts`:

```typescript
import { describe, expect, it, vi } from "vitest";
import { sseToClientStream } from "../src/sse";
import {
  WORKERS_AI_MODEL,
  workersAiChunkToEnvelopes,
  streamWorkersAI,
  generateTextWorkersAI,
  type AiBinding,
} from "../src/workersai";

// Drain a client-envelope stream to a single decoded string.
async function readAll(stream: ReadableStream<Uint8Array>): Promise<string> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let out = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    out += decoder.decode(value, { stream: true });
  }
  out += decoder.decode();
  return out;
}

// An upstream SSE body that emits the given chunks then closes.
function upstreamOf(...chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream<Uint8Array>({
    start(c) {
      for (const chunk of chunks) c.enqueue(encoder.encode(chunk));
      c.close();
    },
  });
}

describe("workersAiChunkToEnvelopes", () => {
  it("maps a token chunk to a content_block_delta envelope", () => {
    expect(workersAiChunkToEnvelopes({ response: "hi" })).toEqual([
      { type: "content_block_delta", delta: { text: "hi" } },
    ]);
  });

  it("yields nothing for an empty response (usage/final chunks)", () => {
    expect(workersAiChunkToEnvelopes({ response: "", usage: { total_tokens: 9 } })).toEqual([]);
  });

  it("tolerates a garbage/empty chunk", () => {
    expect(workersAiChunkToEnvelopes({})).toEqual([]);
    expect(workersAiChunkToEnvelopes(null)).toEqual([]);
  });
});

describe("streamWorkersAI", () => {
  it("calls ai.run with the model, system-prefixed messages, stream and max_tokens, returning the raw stream", async () => {
    const stream = upstreamOf("");
    const run = vi.fn(async () => stream);
    const ai: AiBinding = { run };
    const out = await streamWorkersAI(ai, "persona", [{ role: "user", content: "hi" }], 700);
    expect(out).toBe(stream);
    expect(run).toHaveBeenCalledWith(WORKERS_AI_MODEL, {
      messages: [
        { role: "system", content: "persona" },
        { role: "user", content: "hi" },
      ],
      stream: true,
      max_tokens: 700,
    });
  });

  it("propagates ai.run errors (neuron exhaustion, outage) to the caller", async () => {
    const ai: AiBinding = {
      run: vi.fn(async () => {
        throw new Error("neurons exhausted");
      }),
    };
    await expect(streamWorkersAI(ai, "s", [], 700)).rejects.toThrow("neurons exhausted");
  });
});

describe("Workers AI SSE through the shared transformer (end to end)", () => {
  it("streams token chunks as client envelopes and skips the [DONE] sentinel", async () => {
    const upstream = upstreamOf(
      `data: {"response":"Hel"}\n\n`,
      `data: {"response":"lo"}\n\n`,
      `data: [DONE]\n\n`,
    );
    const out = await readAll(sseToClientStream(upstream, workersAiChunkToEnvelopes));
    expect(out).toContain('"text":"Hel"');
    expect(out).toContain('"text":"lo"');
    expect(out).not.toContain("DONE");
    expect(out).not.toContain("trouble responding");
  });
});

describe("generateTextWorkersAI", () => {
  it("returns the response string from a non-streaming run", async () => {
    const run = vi.fn(async () => ({ response: "## Themes" }));
    const out = await generateTextWorkersAI({ run }, "prompt");
    expect(out).toBe("## Themes");
    const [model, options] = run.mock.calls[0] as [string, any];
    expect(model).toBe(WORKERS_AI_MODEL);
    expect(options.messages).toEqual([{ role: "user", content: "prompt" }]);
    expect(options.stream).toBeUndefined();
  });

  it("returns an empty string when the response field is absent", async () => {
    const run = vi.fn(async () => ({}));
    expect(await generateTextWorkersAI({ run }, "p")).toBe("");
  });

  it("propagates ai.run errors", async () => {
    const run = vi.fn(async () => {
      throw new Error("boom");
    });
    await expect(generateTextWorkersAI({ run }, "p")).rejects.toThrow("boom");
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm --prefix worker test`
Expected: FAIL — `workersai.test.ts` cannot resolve `../src/workersai`. All other files stay green.

- [ ] **Step 3: Implement `worker/src/workersai.ts`**

```typescript
import type { ChatMessage } from "./gemini";

// Cross-vendor fallback rung (#97): Cloudflare Workers AI, reached via the env.AI
// platform binding — no external API key, no new secret. The account is on the
// Workers FREE plan: past the free 10k Neurons/day allowance ai.run just throws
// (no billing surface), which the callers treat as this rung failing too.
//
// The model must be LIVE-VERIFIED before being swapped (the Gemma lesson: a
// catalog listing is not proof a model behaves at our token budget). fp8-fast is
// the latency-optimized Llama 3.3 70B variant, verified to stream a clean grounded
// persona answer within MAX_TOKENS.
export const WORKERS_AI_MODEL = "@cf/meta/llama-3.3-70b-instruct-fp8-fast";

// Minimal structural surface of the env.AI binding — deliberately NOT the `Ai`
// type from @cloudflare/workers-types, whose model-name union lags the live
// catalog and would reject newer model ids at compile time.
export interface AiBinding {
  run(model: string, options: Record<string, unknown>): Promise<unknown>;
}

// PURE: map a parsed Workers AI SSE chunk to zero or more client envelopes.
// Workers AI streams `data: {"response":"<token>", ...}` lines and terminates with
// the non-JSON sentinel `data: [DONE]` (skipped upstream by sseToClientStream's
// JSON.parse guard). Usage/final chunks carry an empty response — yield nothing.
export function workersAiChunkToEnvelopes(chunk: any): object[] {
  if (typeof chunk?.response === "string" && chunk.response.length > 0) {
    return [{ type: "content_block_delta", delta: { text: chunk.response } }];
  }
  return [];
}

// Streaming chat completion. The system text rides as a leading system-role message
// (Workers AI has no separate systemInstruction field); history roles pass through
// unchanged (same "user"/"assistant" names). Errors (neuron exhaustion, model
// errors) propagate as thrown exceptions — the caller decides the terminal message.
export async function streamWorkersAI(
  ai: AiBinding,
  systemText: string,
  messages: ChatMessage[],
  maxTokens: number,
): Promise<ReadableStream<Uint8Array>> {
  const result = await ai.run(WORKERS_AI_MODEL, {
    messages: [
      { role: "system", content: systemText },
      ...messages.map((m) => ({ role: m.role, content: m.content })),
    ],
    stream: true,
    max_tokens: maxTokens,
  });
  return result as ReadableStream<Uint8Array>;
}

// One-shot (non-streaming) completion — the digest-cron fallback. Without
// `stream: true` the binding resolves to an object carrying a `response` string.
export async function generateTextWorkersAI(ai: AiBinding, prompt: string): Promise<string> {
  const result = (await ai.run(WORKERS_AI_MODEL, {
    messages: [{ role: "user", content: prompt }],
  })) as { response?: unknown };
  return typeof result?.response === "string" ? result.response : "";
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm --prefix worker test`
Expected: PASS, all files.

- [ ] **Step 5: Commit**

```bash
git add worker/src/workersai.ts worker/test/workersai.test.ts
git commit -m "worker(#97): add the Workers AI vendor module (llama-3.3-70b fp8-fast)"
```

---

### Task 3: Chat fall-through in `index.ts` + the `AI` binding

TDD via `handler.test.ts`. The three new tests fail first; the pre-existing "Gemini 429s on every rung" and "Gemini fails non-quota (500)" tests must KEEP passing untouched — they use an env without `AI`, which is exactly the graceful-absence guarantee.

**Files:**
- Modify: `worker/test/handler.test.ts` (helper + 3 new tests)
- Modify: `worker/src/index.ts` (Env, imports, fall-through)
- Modify: `worker/wrangler.toml` (the `[ai]` binding)

**Interfaces:**
- Consumes: `streamWorkersAI`, `workersAiChunkToEnvelopes`, `type AiBinding` from `./workersai` (Task 2); `sseToClientStream` from `./sse` (Task 1).
- Produces: `Env` gains `AI?: AiBinding` (Task 4's scheduled pass-through relies on it).

- [ ] **Step 1: Write the failing tests**

In `worker/test/handler.test.ts`:

Add to the imports (top of file):

```typescript
import type { AiBinding } from "../src/workersai";
```

Extend `makeEnv` with an optional third parameter (existing call sites need no change):

```typescript
function makeEnv(kv: KVNamespace = fakeKv(), db: D1Database = fakeD1().db, ai?: AiBinding): Env {
  return {
    RATE_KV: kv,
    INSIGHTS_DB: db,
    GEMINI_API_KEY: "k",
    TURNSTILE_SECRET_KEY: "s",
    ALLOWED_ORIGIN: ALLOWED,
    MONTHLY_CEILING: "5000",
    MAX_TOKENS: "700",
    ...(ai ? { AI: ai } : {}),
  };
}
```

Add these three tests inside `describe("fetch handler")`, directly after the existing "POST when Gemini fails non-quota (500) on every rung" test:

```typescript
  it("POST when Gemini exhausts but the AI binding is present → 200 SSE with the Workers AI answer (#97)", async () => {
    stubFetch({ geminiOk: false, geminiStatus: 429 });
    const run = vi.fn(async () => streamOf(`data: {"response":"llama says hi"}\n\ndata: [DONE]\n\n`));
    const res = await worker.fetch(
      post(ALLOWED, validBody),
      makeEnv(fakeKv(), fakeD1().db, { run }),
      makeCtx().ctx,
    );
    expect(res.status).toBe(200);
    expect(res.headers.get("content-type")).toBe("text/event-stream");
    const text = await res.text();
    expect(text).toContain('"text":"llama says hi"');
    expect(text).not.toContain("free-tier limit");
    // The persona/CV grounding and the token cap must reach the fallback vendor.
    const [model, options] = run.mock.calls[0] as [string, any];
    expect(model).toContain("llama");
    expect(options.messages[0].role).toBe("system");
    expect(options.max_tokens).toBe(700);
  });

  it("POST when Gemini 429s and Workers AI also fails → 200 SSE 'resting' message (#97)", async () => {
    stubFetch({ geminiOk: false, geminiStatus: 429 });
    const run = vi.fn(async () => {
      throw new Error("neurons exhausted");
    });
    const res = await worker.fetch(
      post(ALLOWED, validBody),
      makeEnv(fakeKv(), fakeD1().db, { run }),
      makeCtx().ctx,
    );
    expect(res.status).toBe(200);
    const text = await res.text();
    expect(text).toContain("free-tier limit");
  });

  it("POST when Gemini fails NON-retryably (400) → Workers AI still rescues (fires on any non-ok terminal, #97)", async () => {
    // A Gemini-side 400/401 is vendor-specific (request shape, API key); Workers AI
    // shares neither, so the cross-vendor rung fires on ANY non-ok terminal.
    stubFetch({ geminiOk: false, geminiStatus: 400 });
    const run = vi.fn(async () => streamOf(`data: {"response":"rescued"}\n\ndata: [DONE]\n\n`));
    const res = await worker.fetch(
      post(ALLOWED, validBody),
      makeEnv(fakeKv(), fakeD1().db, { run }),
      makeCtx().ctx,
    );
    expect(res.status).toBe(200);
    expect(await res.text()).toContain('"text":"rescued"');
  });
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm --prefix worker test`
Expected: FAIL — the three new tests: TypeScript rejects `AI` on `Env` and/or the responses carry the resting/trouble message instead of the llama answer. Everything else green.

- [ ] **Step 3: Implement the fall-through in `worker/src/index.ts`**

Update the import block (from Task 1's state) to:

```typescript
import { streamGemini, geminiToClientStream, type ChatMessage } from "./gemini";
import { clientMessageStream, RESTING_MESSAGE, TROUBLE_MESSAGE, sseToClientStream } from "./sse";
import { streamWorkersAI, workersAiChunkToEnvelopes, type AiBinding } from "./workersai";
```

Add to the `Env` interface, after `MAX_TOKENS: string;`:

```typescript
  // Workers AI platform binding (#97) — the cross-vendor fallback rung. Optional:
  // absent (tests, a deploy without [ai] in wrangler.toml) means the fall-through
  // is skipped and behavior is identical to the Gemini-only worker.
  AI?: AiBinding;
```

Replace the existing `if (!upstream.ok) { ... }` block (the one returning `clientMessageStream(message)`) with:

```typescript
    // On a non-200 from Gemini (429 quota exhausted, 400, 401, 500) the upstream body
    // is a JSON error object, NOT an SSE stream — we never forward it (it can leak
    // internal detail). First try the cross-vendor Workers AI rung (#97): it shares
    // neither Google's infrastructure nor the API key, so it fires on ANY non-ok
    // terminal, not just retryables. If it is absent or also fails, synthesize a
    // clean client-envelope stream carrying a friendly terminal message so the
    // widget shows a sentence and closes, rather than hanging or surfacing a raw
    // error (#103). streamGemini returns the LAST rung's failed Response, so
    // status === 429 means the cascade ended on a quota 429 → the free-tier budget
    // is spent (RESTING_MESSAGE). Any other terminal status (incl. a cascade that
    // started with 429s but ended on a transient 500) is treated conservatively as
    // a transient hiccup (TROUBLE_MESSAGE). A Workers AI failure never changes that
    // classification; it only fails to rescue it.
    if (!upstream.ok) {
      if (env.AI) {
        try {
          const aiStream = await streamWorkersAI(
            env.AI,
            systemText,
            body.messages,
            finite(env.MAX_TOKENS, 700),
          );
          return new Response(sseToClientStream(aiStream, workersAiChunkToEnvelopes), {
            status: 200,
            headers: { ...cors, "content-type": "text/event-stream" },
          });
        } catch {
          // Workers AI rung failed too (neurons spent, outage) — fall through to
          // the terminal message below.
        }
      }
      const message = upstream.status === 429 ? RESTING_MESSAGE : TROUBLE_MESSAGE;
      return new Response(clientMessageStream(message), {
        status: 200,
        headers: { ...cors, "content-type": "text/event-stream" },
      });
    }
```

- [ ] **Step 4: Add the binding to `worker/wrangler.toml`**

Insert after the `[[d1_databases]]` block:

```toml
# Workers AI — the cross-vendor fallback rung (#97). A platform binding: no id, no
# secret. The account is on the Workers free plan, so past the free daily Neuron
# allowance calls just fail (no billing surface) and the rung degrades gracefully.
[ai]
binding = "AI"
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `npm --prefix worker test`
Expected: PASS — the 3 new tests AND every pre-existing handler test (the no-`AI` envs prove graceful absence).

- [ ] **Step 6: Commit**

```bash
git add worker/src/index.ts worker/test/handler.test.ts worker/wrangler.toml
git commit -m "worker(#97): fall through to Workers AI when the Gemini cascade exhausts"
```

---

### Task 4: Digest-cron fallback

TDD via `digest.test.ts`. The pre-existing "still purges ... when Gemini returns a non-200" test keeps passing untouched (no `ai` argument = today's behavior).

**Files:**
- Modify: `worker/test/digest.test.ts` (3 new tests)
- Modify: `worker/src/digest.ts` (optional `ai` param + inner fallback)
- Modify: `worker/src/index.ts` (scheduled passes `env.AI`)

**Interfaces:**
- Consumes: `generateTextWorkersAI`, `type AiBinding` from `./workersai` (Task 2); `Env.AI` (Task 3).
- Produces: `runDigest(db: D1Database, apiKey: string, now: number, fetchImpl?: typeof fetch, ai?: AiBinding): Promise<{ digested: number }>` — the two new trailing params are optional, so every existing caller stays valid.

- [ ] **Step 1: Write the failing tests**

In `worker/test/digest.test.ts`, add the import:

```typescript
import type { AiBinding } from "../src/workersai";
```

Add inside `describe("runDigest")`:

```typescript
  it("falls back to Workers AI when Gemini fails, and still writes the digest (#97)", async () => {
    const rows = [{ id: 1, ts: 5, text: "q1", country: "DE", msg_count: 1 }];
    const { db, calls } = fakeD1(handlerWith(rows));
    const fetchImpl = vi.fn(async () => ({
      ok: false,
      status: 429,
      json: async () => ({}),
    })) as unknown as typeof fetch;
    const run = vi.fn(async () => ({ response: "## Fallback theme" }));
    const ai: AiBinding = { run };

    const result = await runDigest(db, "KEY", NOW, fetchImpl, ai);

    expect(result.digested).toBe(1);
    const insert = calls.find((c) => c.sql.includes("INSERT INTO digests"));
    expect(insert).toBeTruthy();
    expect(insert!.args).toEqual([NOW, "## Fallback theme", 1]);
    // The fallback receives the SAME digest prompt Gemini would have.
    const [, options] = run.mock.calls[0] as [string, any];
    expect(options.messages[0].content).toContain("q1");
  });

  it("skips the digest but STILL purges when both vendors fail (#97)", async () => {
    const rows = [{ id: 1, ts: 5, text: "q1", country: "DE", msg_count: 1 }];
    const { db, calls } = fakeD1(handlerWith(rows));
    const fetchImpl = vi.fn(async () => ({
      ok: false,
      status: 429,
      json: async () => ({}),
    })) as unknown as typeof fetch;
    const ai: AiBinding = {
      run: vi.fn(async () => {
        throw new Error("neurons exhausted");
      }),
    };

    const result = await runDigest(db, "KEY", NOW, fetchImpl, ai);

    expect(result.digested).toBe(0);
    expect(calls.find((c) => c.sql.includes("INSERT INTO digests"))).toBeUndefined();
    // Purge is a privacy guarantee independent of EVERY vendor.
    const purge = calls.find((c) => c.sql.includes("DELETE FROM questions"));
    expect(purge!.args).toEqual([NOW - RETENTION_SECONDS]);
  });

  it("does not touch Workers AI when Gemini succeeds", async () => {
    const rows = [{ id: 1, ts: 5, text: "q1", country: "DE", msg_count: 1 }];
    const { db } = fakeD1(handlerWith(rows));
    const fetchImpl = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => ({ candidates: [{ content: { parts: [{ text: "## Theme" }] } }] }),
    })) as unknown as typeof fetch;
    const run = vi.fn(async () => ({ response: "unused" }));

    const result = await runDigest(db, "KEY", NOW, fetchImpl, { run });

    expect(result.digested).toBe(1);
    expect(run).not.toHaveBeenCalled();
  });
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm --prefix worker test`
Expected: FAIL — `runDigest` does not accept a 5th argument / the fallback test gets `digested: 0`.

- [ ] **Step 3: Implement the fallback in `worker/src/digest.ts`**

Add the import:

```typescript
import { generateTextWorkersAI, type AiBinding } from "./workersai";
```

Replace the `runDigest` signature and the `if (rows.length > 0)` block:

```typescript
export async function runDigest(
  db: D1Database,
  apiKey: string,
  now: number,
  fetchImpl: typeof fetch = fetch,
  ai?: AiBinding,
): Promise<{ digested: number }> {
  const since = await lastDigestTs(db);
  const rows = await questionsSince(db, since);
  let digested = 0;
  if (rows.length > 0) {
    try {
      const prompt = buildDigestPrompt(rows);
      let markdown: string;
      try {
        markdown = await generateText(apiKey, prompt, fetchImpl);
      } catch (err) {
        // Gemini cascade exhausted — try the cross-vendor Workers AI rung (#97)
        // before giving up on this round's digest.
        if (!ai) throw err;
        markdown = await generateTextWorkersAI(ai, prompt);
      }
      await insertDigest(db, { ts: now, markdown, n_questions: rows.length });
      digested = rows.length;
    } catch {
      // Both vendors down: skip this round's digest but STILL purge below.
      // The purge is a privacy guarantee and must not depend on an external service.
    }
  }
  await purgeOld(db, now - RETENTION_SECONDS);
  return { digested };
}
```

- [ ] **Step 4: Pass `env.AI` through in `worker/src/index.ts` `scheduled()`**

```typescript
  async scheduled(_event: ScheduledController, env: Env, ctx: ExecutionContext): Promise<void> {
    ctx.waitUntil(
      runDigest(env.INSIGHTS_DB, env.GEMINI_API_KEY, Math.floor(Date.now() / 1000), fetch, env.AI).then(
        () => {},
      ),
    );
  },
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `npm --prefix worker test`
Expected: PASS, all files (including the untouched `scheduled.test.ts` — its env has no `AI`, exercising graceful absence on the cron path).

- [ ] **Step 6: Commit**

```bash
git add worker/src/digest.ts worker/src/index.ts worker/test/digest.test.ts
git commit -m "worker(#97): give the digest cron the Workers AI fallback"
```

---

### Task 5: Live verification (the Gemma lesson)

No code changes expected; this task gates the model choice with real-world evidence. Needs the machine's existing wrangler login (the one used for `just worker-deploy`). `wrangler dev` proxies the `AI` binding to the real Workers AI service.

**Files:**
- Possibly modify: `worker/src/workersai.ts` (only if the model misbehaves and `WORKERS_AI_MODEL` must be swapped)
- Temporarily modify (NEVER commit): `worker/.dev.vars`

- [ ] **Step 1: Back up `.dev.vars` and force the Gemini cascade to fail**

```bash
cp worker/.dev.vars worker/.dev.vars.bak
```

Edit `worker/.dev.vars`: set `GEMINI_API_KEY=invalid-key-forcing-fallback` (keep every other line). Every Gemini rung will now fail with 400/403, forcing the Workers AI fall-through (which fires on any non-ok terminal).

- [ ] **Step 2: Start the dev worker**

Run (background): `just worker-dev`
Expected: wrangler dev listening on `http://localhost:8787` (the AI binding line appears in the startup output).

- [ ] **Step 3: Exercise the fall-through with a real chat request**

```bash
curl -N -s http://localhost:8787/ \
  -H "content-type: application/json" \
  -H "Origin: http://localhost:4321" \
  -d '{"messages":[{"role":"user","content":"What does Jin-Ho Lee do professionally?"}],"turnstileToken":"dev-test-token"}'
```

(The dev `.dev.vars` uses the always-pass Turnstile test secret, so any token verifies; `http://localhost:4321` is in the dev `ALLOWED_ORIGIN`.)

Expected: a stream of `data: {"type":"content_block_delta","delta":{"text":"..."}}` lines forming a clean, grounded, English persona answer that respects the CV context and finishes within MAX_TOKENS. It must NOT contain the resting/trouble message, raw reasoning, or malformed fragments.

- [ ] **Step 4: Verify the normal path is untouched**

```bash
mv worker/.dev.vars.bak worker/.dev.vars
```

Restart `just worker-dev`, repeat the same curl.
Expected: a normal Gemini-served answer (confirms the fall-through is truly last-resort and the restore worked).

- [ ] **Step 5: Verdict**

If the llama answer was clean: record the result in the task notes; nothing to commit.
If it misbehaved (truncation, malformed output, reasoning leaks): swap `WORKERS_AI_MODEL` in `worker/src/workersai.ts` to the next candidate (`@cf/meta/llama-4-scout-17b-16e-instruct`), run `npm --prefix worker test` (the constant is imported by the tests, so they stay green), repeat Steps 1-4, and commit the swap as `worker(#97): swap the Workers AI rung model after live verification`.

---

### Task 6: Docs + full green gate

**Files:**
- Modify: `worker/README.md` (cascade/cost section)
- Modify: `CLAUDE.md` (the Worker cascade convention paragraph)

- [ ] **Step 1: Update `worker/README.md`**

In the cost/cascade paragraph (the one ending "...keeps the twin reachable far longer than any single model."), append:

```markdown
Since #97 the chain ends with a **cross-vendor rung**: when every Gemini/Gemma rung
fails, the Worker falls through to **Cloudflare Workers AI**
(`@cf/meta/llama-3.3-70b-instruct-fp8-fast` via the `env.AI` platform binding - no
extra secret). The account is on the Workers free plan (10k Neurons/day), so an
exhausted allowance just fails the rung - there is no billing surface. The digest
cron gets the same fallback. An absent binding degrades to Gemini-only behavior.
```

- [ ] **Step 2: Update the CLAUDE.md convention paragraph**

In the "**Deploys outside GitHub Pages.**" convention bullet, directly after the sentence ending "...a live-verification catch.)", add:

```markdown
  Since #97 the cascade ends with a **cross-vendor rung**: when every Gemini/Gemma
  rung fails, the Worker falls through to **Cloudflare Workers AI**
  (`@cf/meta/llama-3.3-70b-instruct-fp8-fast` via the `env.AI` platform binding in
  `src/workersai.ts` - no new secret; free plan, so neuron exhaustion just throws
  and there is no billing surface). It fires on any non-ok Gemini terminal, also
  backs the digest cron, and an absent binding degrades gracefully to Gemini-only.
  The vendor-neutral SSE-to-client-envelope transformer lives in `src/sse.ts`;
  vendor modules supply only a pure chunk-to-envelopes mapper.
```

- [ ] **Step 3: Run the full repo gate**

```bash
just validate
just test
just lint
uv run ruff format --check .
npm --prefix worker test
```

Expected: all green (the Python surface is untouched; this is the belt-and-braces gate before the PR).

- [ ] **Step 4: Commit**

```bash
git add worker/README.md CLAUDE.md
git commit -m "docs(#97): document the cross-vendor Workers AI fallback rung"
```

---

## After the plan

Finish via `superpowers:finishing-a-development-branch`: push, open the PR (closes #97, spec + plan ship in it), tick the test-plan boxes, offer the @claude review. The `just worker-deploy` to actually ship the rung to Cloudflare is Jin-Ho's manual step, called out in the PR body.
