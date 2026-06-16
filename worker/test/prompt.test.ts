import { describe, expect, it } from "vitest";
import { buildSystemText, wrapContext } from "../src/prompt";

describe("wrapContext", () => {
  it("wraps the CV blob in delimiters so user text can't pose as instructions", () => {
    const out = wrapContext("PROFILE: builds pipelines");
    expect(out).toContain("<cv_context>");
    expect(out).toContain("</cv_context>");
    expect(out).toContain("PROFILE: builds pipelines");
  });
});

describe("buildSystemText", () => {
  it("returns one system string with the persona then the delimited CV", () => {
    const text = buildSystemText("PERSONA TEXT", "CV BLOB");
    expect(text).toContain("PERSONA TEXT");
    expect(text).toContain("<cv_context>");
    expect(text).toContain("</cv_context>");
    expect(text).toContain("CV BLOB");
    // persona comes before the wrapped context
    expect(text.indexOf("PERSONA TEXT")).toBeLessThan(text.indexOf("<cv_context>"));
  });
});
