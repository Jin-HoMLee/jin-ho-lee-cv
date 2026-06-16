import { describe, expect, it } from "vitest";
import { corsHeaders, isAllowedOrigin } from "../src/index";

describe("CORS", () => {
  it("accepts the configured origin and rejects others", () => {
    const allowed = "https://jinholee.is-a.dev";
    expect(isAllowedOrigin(allowed, allowed)).toBe(true);
    expect(isAllowedOrigin("https://evil.example", allowed)).toBe(false);
  });

  it("emits ACAO only for the allowed origin", () => {
    const allowed = "https://jinholee.is-a.dev";
    expect(corsHeaders(allowed, allowed)["Access-Control-Allow-Origin"]).toBe(allowed);
    expect(corsHeaders("https://evil.example", allowed)["Access-Control-Allow-Origin"]).toBe("");
  });

  it("accepts any origin in a comma-separated allowlist (prod + localhost dev)", () => {
    const allowed = "https://jinholee.is-a.dev, http://localhost:4321";
    expect(isAllowedOrigin("https://jinholee.is-a.dev", allowed)).toBe(true);
    expect(isAllowedOrigin("http://localhost:4321", allowed)).toBe(true);
    expect(isAllowedOrigin("https://evil.example", allowed)).toBe(false);
    expect(isAllowedOrigin(null, allowed)).toBe(false);
  });

  it("echoes the matched request origin (not the whole list) as ACAO", () => {
    const allowed = "https://jinholee.is-a.dev,http://localhost:4321";
    expect(corsHeaders("http://localhost:4321", allowed)["Access-Control-Allow-Origin"]).toBe(
      "http://localhost:4321",
    );
    expect(corsHeaders("https://jinholee.is-a.dev", allowed)["Access-Control-Allow-Origin"]).toBe(
      "https://jinholee.is-a.dev",
    );
  });
});
