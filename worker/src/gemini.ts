export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

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

// Free-tier model cascade, best-first. Each model carries its OWN free-tier daily
// request cap, so chaining several multiplies the combined budget and keeps the
// twin reachable long after the top model's quota is gone. We try the best model
// first and fall through to the next on a retryable failure (a daily-quota 429, or
// a transient 503/500). Caps run roughly best≈small, lite/older≈large (e.g.
// 3.5-flash ~20/day vs 2.5-flash-lite ~1000/day — verified against the live API),
// so the lower rungs carry the load once the premium quota is spent.
//
// The quota bucket is keyed by the RESOLVED concrete model (the 429's
// `quotaDimensions.model`), so adding `-latest`/`-001`/preview ALIASES that resolve
// to a rung already here buys nothing. `gemini-3-flash-preview` is a genuinely
// distinct model id (its own daily bucket), and Gemma models draw from a SEPARATE
// free-tier pool from the Gemini models — both are real added headroom, both
// verified live. Gemma sits last (lowest quality + thinks-by-default, see below).
//
// Thinking config is model-family-specific: Gemini 3.x Flash takes `thinkingLevel`
// ("low" keeps the reasoning from eating the visible-answer token budget); the 2.5
// models reject `thinkingLevel` (HTTP 400) and take `thinkingBudget: 0`; the 2.0
// models and Gemma have no settable thinking feature, so we omit thinkingConfig
// entirely — any thinkingConfig 400s on Gemma ("Thinking budget is not supported")
// and a stray budget on 2.0 could 400 too, either of which would break the chain.
// NOTE: Gemma still THINKS by default and streams its reasoning as `thought: true`
// parts (which cannot be disabled); geminiChunkToEnvelopes/generateText filter those
// out so raw chain-of-thought never reaches the visible answer.
interface ModelConfig {
  name: string;
  thinkingConfig?: Record<string, unknown>;
}
const MODELS: ModelConfig[] = [
  { name: "gemini-3.5-flash", thinkingConfig: { thinkingLevel: "low" } },
  { name: "gemini-3-flash-preview", thinkingConfig: { thinkingLevel: "low" } },
  { name: "gemini-3.1-flash-lite", thinkingConfig: { thinkingLevel: "low" } },
  { name: "gemini-2.5-flash", thinkingConfig: { thinkingBudget: 0 } },
  { name: "gemini-2.5-flash-lite", thinkingConfig: { thinkingBudget: 0 } },
  { name: "gemini-2.0-flash" },
  { name: "gemini-2.0-flash-lite" },
  // Gemma draws from a separate free-tier pool. The dense gemma-4-31b-it looked like
  // the quality pick but returns MALFORMED_RESPONSE / thoughts-only at our token
  // budget (verified live); the lighter MoE gemma-4-26b-a4b-it reliably produces a
  // clean grounded answer within MAX_TOKENS, so it's the last-resort rung.
  { name: "gemma-4-26b-a4b-it" },
];

// Upstream statuses worth retrying on the NEXT model in the cascade: 429 (daily or
// per-minute quota exhausted), 503 (model overloaded / "high demand"), 500
// (transient upstream error), and 404 (model not found — a deprecated/removed model,
// which a -preview rung can become; the next rung is a different model so it's worth
// trying). A 400/401/403 is a request/auth bug — the next model would fail
// identically, so we stop and surface it rather than burn the cascade.
function isRetryable(status: number): boolean {
  return status === 429 || status === 500 || status === 503 || status === 404;
}

// Streams a Gemini Flash response (free tier), cascading down MODELS on a retryable
// upstream failure. The API key is a query param (server-side only — never exposed
// to the browser). Returns the first model's ok streaming Response; if a model
// fails retryably it tries the next, and if all are exhausted it returns the last
// failed Response (the caller turns any non-ok into a 200 SSE carrying a friendly
// terminal message — see index.ts). The returned ok SSE body is transformed back
// into the client envelope by geminiToClientStream so the browser widget contract
// stays unchanged.
export async function streamGemini(
  apiKey: string,
  systemText: string,
  messages: ChatMessage[],
  maxTokens: number,
  fetchImpl: typeof fetch = fetch,
): Promise<Response> {
  const contents = messages.map((m) => ({
    role: m.role === "assistant" ? "model" : "user",
    parts: [{ text: m.content }],
  }));
  let res!: Response;
  for (const model of MODELS) {
    const url =
      `https://generativelanguage.googleapis.com/v1beta/models/${model.name}:streamGenerateContent` +
      `?alt=sse&key=${apiKey}`;
    res = await fetchImpl(url, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        systemInstruction: { parts: [{ text: systemText }] },
        contents,
        generationConfig: {
          maxOutputTokens: maxTokens,
          // Omitted for models without a thinking feature (the 2.0 family) — a
          // stray thinkingConfig there can 400 and break the cascade.
          ...(model.thinkingConfig ? { thinkingConfig: model.thinkingConfig } : {}),
        },
      }),
    });
    if (res.ok || !isRetryable(res.status)) return res;
    // Retryable failure → try the next model. Drain this error body (small JSON,
    // never an SSE stream) so the upstream connection isn't held open until GC.
    res.body?.cancel();
  }
  return res; // every model exhausted — surface the last failure
}

// PURE: map a parsed Gemini SSE chunk to zero or more client envelopes — exactly
// the shape the browser widget (web/src/lib/twin.ts) already parses. Tolerates
// missing fields (keep-alives, malformed chunks) by returning [].
export function geminiChunkToEnvelopes(chunk: any): object[] {
  const envelopes: object[] = [];
  const candidate = chunk?.candidates?.[0];
  const parts = candidate?.content?.parts;
  if (Array.isArray(parts)) {
    for (const part of parts) {
      // Skip reasoning parts (Gemma streams chain-of-thought as `thought: true`
      // parts) so internal reasoning never leaks into the visible answer.
      if (typeof part?.text === "string" && part?.thought !== true) {
        envelopes.push({ type: "content_block_delta", delta: { text: part.text } });
      }
    }
  }
  if (candidate?.finishReason === "MAX_TOKENS") {
    envelopes.push({ type: "message_delta", delta: { stop_reason: "max_tokens" } });
  }
  return envelopes;
}

// One-shot (non-streaming) completion used by the Phase 12b digest cron. Uses the
// :generateContent endpoint (not :streamGenerateContent) and returns the joined
// candidate text. Cascades down the same free-tier MODELS as the chat path (no new
// credential or cost) so the daily digest still runs when the top model's quota is
// spent. Throws on a non-retryable error or after every model is exhausted, so the
// cron can skip writing a digest.
export async function generateText(
  apiKey: string,
  prompt: string,
  fetchImpl: typeof fetch = fetch,
): Promise<string> {
  let status = 0;
  for (const model of MODELS) {
    const url =
      `https://generativelanguage.googleapis.com/v1beta/models/${model.name}:generateContent` +
      `?key=${apiKey}`;
    const res = await fetchImpl(url, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        contents: [{ role: "user", parts: [{ text: prompt }] }],
        generationConfig: model.thinkingConfig ? { thinkingConfig: model.thinkingConfig } : {},
      }),
    });
    if (res.ok) {
      const data = (await res.json()) as any;
      const parts = data?.candidates?.[0]?.content?.parts;
      if (!Array.isArray(parts)) return "";
      // Drop `thought: true` reasoning parts (Gemma emits them) so the digest is the
      // answer text only, never the chain-of-thought.
      return parts
        .filter((p: any) => p?.thought !== true)
        .map((p: any) => (typeof p?.text === "string" ? p.text : ""))
        .join("");
    }
    status = res.status;
    if (!isRetryable(status)) break; // config/auth error — next model won't help
  }
  throw new Error(`gemini generateText upstream ${status}`);
}

// Read Gemini's native SSE and re-emit the client envelope SSE. Buffers across
// network chunks, splits on newlines, parses each `data: {json}` line, and
// enqueues `data: ${envelope}\n\n` for every envelope geminiChunkToEnvelopes
// yields. Non-JSON lines (keep-alives, comments) are skipped.
export function geminiToClientStream(
  upstream: ReadableStream<Uint8Array>,
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
    for (const env of geminiChunkToEnvelopes(parsed)) {
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
