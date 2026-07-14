import { describe, expect, it } from "vitest";
import { checkLimits, type Counters, type Limits } from "../src/ratelimit";

const LIMITS: Limits = { perMinute: 10, perDay: 50, monthlyCeiling: 5000 };

describe("checkLimits", () => {
  it("allows when all counters are under their limits", () => {
    const counters: Counters = { minute: 3, day: 12, month: 100 };
    expect(checkLimits(counters, LIMITS)).toEqual({ allowed: true });
  });

  it("blocks with 429 when the per-minute limit is hit", () => {
    const counters: Counters = { minute: 10, day: 12, month: 100 };
    expect(checkLimits(counters, LIMITS)).toEqual({ allowed: false, status: 429, reason: "rate" });
  });

  it("blocks with 429 when the per-day limit is hit", () => {
    const counters: Counters = { minute: 1, day: 50, month: 100 };
    expect(checkLimits(counters, LIMITS)).toEqual({ allowed: false, status: 429, reason: "rate" });
  });

  it("blocks with 503 when the global monthly ceiling is hit", () => {
    const counters: Counters = { minute: 1, day: 1, month: 5000 };
    expect(checkLimits(counters, LIMITS)).toEqual({ allowed: false, status: 503, reason: "ceiling" });
  });

  it("prioritises the monthly ceiling over per-IP rate", () => {
    const counters: Counters = { minute: 10, day: 50, month: 5000 };
    // Full-object assertion: narrows the LimitResult union under tsc (#123) and
    // pins status alongside the reason.
    expect(checkLimits(counters, LIMITS)).toEqual({ allowed: false, status: 503, reason: "ceiling" });
  });
});
