import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  FirstResponseTimeoutError,
  GEMINI_FIRST_RESPONSE_DEADLINE_MS,
  WORKERS_AI_FIRST_RESPONSE_DEADLINE_MS,
  raceDeadline,
} from "../src/deadline";

beforeEach(() => {
  vi.useFakeTimers();
});
afterEach(() => {
  vi.useRealTimers();
});

describe("raceDeadline", () => {
  it("resolves with the promise value when it settles before the deadline", async () => {
    await expect(raceDeadline(Promise.resolve("ok"), 1000, "gemini")).resolves.toBe("ok");
  });

  it("rejects with FirstResponseTimeoutError when the promise hangs past the deadline", async () => {
    const hang = new Promise<never>(() => {});
    const raced = raceDeadline(hang, 1000, "gemini");
    const assertion = expect(raced).rejects.toBeInstanceOf(FirstResponseTimeoutError);
    await vi.advanceTimersByTimeAsync(1000);
    await assertion;
  });

  it("names the vendor in the timeout error message (wrangler tail observability)", async () => {
    const raced = raceDeadline(new Promise<never>(() => {}), 500, "workers-ai");
    const assertion = expect(raced).rejects.toThrow(/workers-ai/);
    await vi.advanceTimersByTimeAsync(500);
    await assertion;
  });

  it("propagates the promise's own rejection unchanged", async () => {
    await expect(raceDeadline(Promise.reject(new Error("boom")), 1000, "gemini")).rejects.toThrow(
      "boom",
    );
  });

  it("clears its timer once the promise wins (no stray timer left behind)", async () => {
    await raceDeadline(Promise.resolve(1), 60_000, "gemini");
    expect(vi.getTimerCount()).toBe(0);
  });

  it("keeps the combined default budgets under the widget's 30s stall guard", () => {
    // web/src/lib/twin.ts STALL_MS is 30_000; the worst-case phase-1 wait
    // (full Gemini budget + the Workers AI slice) must stay below it so the
    // visitor always receives a server-generated response first.
    expect(
      GEMINI_FIRST_RESPONSE_DEADLINE_MS + WORKERS_AI_FIRST_RESPONSE_DEADLINE_MS,
    ).toBeLessThan(30_000);
  });
});
