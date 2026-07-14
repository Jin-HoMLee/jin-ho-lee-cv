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
