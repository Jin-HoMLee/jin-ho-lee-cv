import { describe, expect, it } from "vitest";
import { geminiChunkToEnvelopes } from "../src/gemini";

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
