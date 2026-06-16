import { describe, expect, it } from "vitest";
import { corsHeaders, isAllowedOrigin } from "../src/index";

describe("CORS", () => {
  it("accepts the configured origin and rejects others", () => {
    const allowed = "https://jin-ho-lee.is-a.dev";
    expect(isAllowedOrigin(allowed, allowed)).toBe(true);
    expect(isAllowedOrigin("https://evil.example", allowed)).toBe(false);
  });

  it("emits ACAO only for the allowed origin", () => {
    const allowed = "https://jin-ho-lee.is-a.dev";
    expect(corsHeaders(allowed, allowed)["Access-Control-Allow-Origin"]).toBe(allowed);
    expect(corsHeaders("https://evil.example", allowed)["Access-Control-Allow-Origin"]).toBe("");
  });
});
