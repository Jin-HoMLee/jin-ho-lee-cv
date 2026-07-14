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
