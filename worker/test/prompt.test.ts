import { describe, expect, it } from "vitest";
import { buildSystemPrompt, wrapContext } from "../src/prompt";

describe("wrapContext", () => {
  it("wraps the CV blob in delimiters so user text can't pose as instructions", () => {
    const out = wrapContext("PROFILE: builds pipelines");
    expect(out).toContain("<cv_context>");
    expect(out).toContain("</cv_context>");
    expect(out).toContain("PROFILE: builds pipelines");
  });
});

describe("buildSystemPrompt", () => {
  it("returns a cacheable persona block + a cacheable context block", () => {
    const blocks = buildSystemPrompt("PERSONA TEXT", "CV BLOB");
    expect(blocks).toHaveLength(2);
    expect(blocks[0].text).toBe("PERSONA TEXT");
    expect(blocks[1].text).toContain("CV BLOB");
    expect(blocks[1].cache_control).toEqual({ type: "ephemeral" });
  });
});
