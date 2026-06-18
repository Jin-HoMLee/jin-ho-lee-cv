import { describe, expect, it, vi } from "vitest";
import { geminiChunkToEnvelopes, generateText } from "../src/gemini";

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

  it("returns empty string when no candidate text is present", async () => {
    const fetchImpl = vi.fn(async () => ({ ok: true, status: 200, json: async () => ({}) })) as unknown as typeof fetch;
    expect(await generateText("KEY", "p", fetchImpl)).toBe("");
  });
});
