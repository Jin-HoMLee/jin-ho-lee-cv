import { describe, expect, it, vi } from "vitest";
import { geminiChunkToEnvelopes, generateText, streamGemini } from "../src/gemini";

// A fake fetch that returns a scripted status per call (in order), recording the
// requested URL + parsed body so cascade assertions can inspect which model was
// hit and with what thinking config. A 200 carries a tiny SSE body so the ok path
// is realistic; non-200s carry no body (mirrors how Gemini errors arrive as JSON,
// not SSE — the worker discards them).
function scriptedFetch(statuses: number[]) {
  const calls: { url: string; body: any }[] = [];
  let i = 0;
  const fn = vi.fn(async (url: string, init: any) => {
    calls.push({ url: String(url), body: JSON.parse(init.body) });
    const status = statuses[Math.min(i, statuses.length - 1)];
    i++;
    return {
      ok: status >= 200 && status < 300,
      status,
      body:
        status === 200
          ? new ReadableStream({
              start(c) {
                c.close();
              },
            })
          : null,
    } as unknown as Response;
  }) as unknown as typeof fetch;
  return { fn, calls };
}

// Model name appearing in a Gemini URL (…/models/<name>:streamGenerateContent…).
function modelOf(url: string): string {
  return url.match(/\/models\/([^:]+):/)?.[1] ?? "";
}

describe("geminiChunkToEnvelopes", () => {
  it("maps a content part to a content_block_delta envelope", () => {
    const chunk = { candidates: [{ content: { parts: [{ text: "hi" }] } }] };
    expect(geminiChunkToEnvelopes(chunk)).toEqual([
      { type: "content_block_delta", delta: { text: "hi" } },
    ]);
  });

  it("emits a max_tokens message_delta when finishReason is MAX_TOKENS", () => {
    const chunk = {
      candidates: [{ content: { parts: [{ text: "tail" }] }, finishReason: "MAX_TOKENS" }],
    };
    const out = geminiChunkToEnvelopes(chunk);
    expect(out).toContainEqual({ type: "content_block_delta", delta: { text: "tail" } });
    expect(out).toContainEqual({ type: "message_delta", delta: { stop_reason: "max_tokens" } });
  });

  it("does not emit a truncation envelope for a normal STOP finish with no parts", () => {
    const chunk = { candidates: [{ content: { parts: [] }, finishReason: "STOP" }] };
    expect(geminiChunkToEnvelopes(chunk)).toEqual([]);
  });

  it("tolerates an empty/garbage chunk", () => {
    expect(geminiChunkToEnvelopes({})).toEqual([]);
  });
});

describe("streamGemini model cascade", () => {
  const args = ["KEY", "system", [{ role: "user" as const, content: "hi" }], 700] as const;

  it("returns the first model's response when it succeeds (no fallback)", async () => {
    const { fn, calls } = scriptedFetch([200]);
    const res = await streamGemini(...args, fn);
    expect(res.ok).toBe(true);
    expect(calls).toHaveLength(1);
    expect(modelOf(calls[0].url)).toBe("gemini-3.5-flash");
  });

  it("falls through to the next model on a 429 (daily quota) and returns its ok response", async () => {
    const { fn, calls } = scriptedFetch([429, 200]);
    const res = await streamGemini(...args, fn);
    expect(res.ok).toBe(true);
    expect(res.status).toBe(200);
    expect(calls.map((c) => modelOf(c.url))).toEqual(["gemini-3.5-flash", "gemini-2.5-flash"]);
  });

  it("falls through twice (429 then 503) down to the lite model", async () => {
    const { fn, calls } = scriptedFetch([429, 503, 200]);
    const res = await streamGemini(...args, fn);
    expect(res.ok).toBe(true);
    expect(calls.map((c) => modelOf(c.url))).toEqual([
      "gemini-3.5-flash",
      "gemini-2.5-flash",
      "gemini-2.5-flash-lite",
    ]);
  });

  it("returns the last failed response when every model is quota-exhausted", async () => {
    const { fn, calls } = scriptedFetch([429, 429, 429]);
    const res = await streamGemini(...args, fn);
    expect(res.ok).toBe(false);
    expect(res.status).toBe(429);
    expect(calls).toHaveLength(3); // tried all three models
  });

  it("stops at the first model on a non-retryable status (400) — does not waste lower-tier calls", async () => {
    const { fn, calls } = scriptedFetch([400, 200]);
    const res = await streamGemini(...args, fn);
    expect(res.status).toBe(400);
    expect(calls).toHaveLength(1);
  });

  it("falls through on a transient 500 (completes the retryable-status matrix)", async () => {
    const { fn, calls } = scriptedFetch([500, 200]);
    const res = await streamGemini(...args, fn);
    expect(res.ok).toBe(true);
    expect(calls.map((c) => modelOf(c.url))).toEqual(["gemini-3.5-flash", "gemini-2.5-flash"]);
  });

  it("sends model-appropriate thinking config (3.x thinkingLevel, 2.5 thinkingBudget)", async () => {
    const { fn, calls } = scriptedFetch([429, 429, 200]);
    await streamGemini(...args, fn);
    expect(calls[0].body.generationConfig.thinkingConfig).toEqual({ thinkingLevel: "low" });
    expect(calls[1].body.generationConfig.thinkingConfig).toEqual({ thinkingBudget: 0 });
    expect(calls[2].body.generationConfig.thinkingConfig).toEqual({ thinkingBudget: 0 });
  });
});

describe("generateText", () => {
  it("posts to :generateContent and returns the joined text", async () => {
    const fetchImpl = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => ({ candidates: [{ content: { parts: [{ text: "themes" }] } }] }),
    })) as unknown as typeof fetch;
    const out = await generateText("KEY", "prompt", fetchImpl);
    expect(out).toBe("themes");
    const [url] = (fetchImpl as any).mock.calls[0];
    expect(String(url)).toContain(":generateContent");
    expect(String(url)).not.toContain("streamGenerateContent");
  });

  it("throws on a non-200 upstream", async () => {
    const fetchImpl = vi.fn(async () => ({ ok: false, status: 429, json: async () => ({}) })) as unknown as typeof fetch;
    await expect(generateText("KEY", "p", fetchImpl)).rejects.toThrow();
  });

  it("throws after every model is quota-exhausted (tries all three, then gives up)", async () => {
    const { fn, calls } = scriptedFetch([429, 429, 429]);
    await expect(generateText("KEY", "p", fn)).rejects.toThrow("upstream 429");
    expect(calls).toHaveLength(3);
  });

  it("stops on a non-retryable status (400) without trying lower models", async () => {
    const { fn, calls } = scriptedFetch([400, 200]);
    await expect(generateText("KEY", "p", fn)).rejects.toThrow("upstream 400");
    expect(calls).toHaveLength(1);
  });

  it("returns empty string when no candidate text is present", async () => {
    const fetchImpl = vi.fn(async () => ({ ok: true, status: 200, json: async () => ({}) })) as unknown as typeof fetch;
    expect(await generateText("KEY", "p", fetchImpl)).toBe("");
  });

  it("cascades to the next model on a 429 (digest path stays alive when 3.5 is exhausted)", async () => {
    const urls: string[] = [];
    let call = 0;
    const fetchImpl = vi.fn(async (url: string) => {
      urls.push(String(url));
      const exhausted = call++ === 0; // first model 429s, second succeeds
      return {
        ok: !exhausted,
        status: exhausted ? 429 : 200,
        json: async () => ({ candidates: [{ content: { parts: [{ text: "digest" }] } }] }),
      } as unknown as Response;
    }) as unknown as typeof fetch;
    const out = await generateText("KEY", "p", fetchImpl);
    expect(out).toBe("digest");
    expect(urls[0]).toContain("gemini-3.5-flash");
    expect(urls[1]).toContain("gemini-2.5-flash");
  });
});
