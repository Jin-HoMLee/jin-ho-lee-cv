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
    const [model, options] = run.mock.calls[0] as unknown as [string, any];
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
