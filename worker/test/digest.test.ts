import { describe, expect, it, vi } from "vitest";
import { buildDigestPrompt, runDigest, RETENTION_SECONDS } from "../src/digest";
import { fakeD1 } from "./fakeD1";
import type { AiBinding } from "../src/workersai";

const NOW = 1_000_000;

// A handler that returns N questions for the questionsSince SELECT and ts=0 for
// the lastDigestTs MAX query.
function handlerWith(questionRows: any[]) {
  return (sql: string) => {
    if (sql.includes("MAX(ts)")) return { first: { ts: 0 } };
    if (sql.includes("WHERE ts > ?")) return { results: questionRows };
    return {};
  };
}

describe("buildDigestPrompt", () => {
  it("lists every question and asks for themed Markdown", () => {
    const rows = [
      { id: 1, ts: 1, text: "what is your salary", country: "DE", msg_count: 2 },
      { id: 2, ts: 2, text: "do you know rust", country: "US", msg_count: 1 },
    ];
    const p = buildDigestPrompt(rows as any);
    expect(p).toContain("what is your salary");
    expect(p).toContain("do you know rust");
    expect(p.toLowerCase()).toContain("theme");
  });
});

describe("runDigest", () => {
  it("writes one digest row when there are new questions, then purges", async () => {
    const rows = [{ id: 1, ts: 5, text: "q1", country: "DE", msg_count: 1 }];
    const { db, calls } = fakeD1(handlerWith(rows));
    const fetchImpl = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => ({ candidates: [{ content: { parts: [{ text: "## Theme" }] } }] }),
    })) as unknown as typeof fetch;

    const result = await runDigest(db, "KEY", NOW, fetchImpl);

    expect(result.digested).toBe(1);
    expect(fetchImpl).toHaveBeenCalledTimes(1); // Gemini called once
    const insert = calls.find((c) => c.sql.includes("INSERT INTO digests"));
    expect(insert).toBeTruthy();
    expect(insert!.args).toEqual([NOW, "## Theme", 1]);
    const purge = calls.find((c) => c.sql.includes("DELETE FROM questions"));
    expect(purge!.args).toEqual([NOW - RETENTION_SECONDS]);
  });

  it("skips the LLM call and writes no digest when there are no new questions, but still purges", async () => {
    const { db, calls } = fakeD1(handlerWith([]));
    const fetchImpl = vi.fn() as unknown as typeof fetch;

    const result = await runDigest(db, "KEY", NOW, fetchImpl);

    expect(result.digested).toBe(0);
    expect(fetchImpl).not.toHaveBeenCalled(); // skip-on-empty
    expect(calls.find((c) => c.sql.includes("INSERT INTO digests"))).toBeUndefined();
    expect(calls.find((c) => c.sql.includes("DELETE FROM questions"))).toBeTruthy();
  });

  it("still purges and returns digested=0 when Gemini returns a non-200 (LLM outage)", async () => {
    // Simulate one new question but a Gemini 429 response.
    const rows = [{ id: 1, ts: 5, text: "q1", country: "DE", msg_count: 1 }];
    const { db, calls } = fakeD1(handlerWith(rows));
    const fetchImpl = vi.fn(async () => ({
      ok: false,
      status: 429,
      json: async () => ({}),
    })) as unknown as typeof fetch;

    // The throw from generateText must NOT escape runDigest — no unhandled rejection.
    const result = await runDigest(db, "KEY", NOW, fetchImpl);

    // Digest was NOT written (LLM failed).
    expect(result.digested).toBe(0);
    expect(calls.find((c) => c.sql.includes("INSERT INTO digests"))).toBeUndefined();

    // Purge MUST still run — it is a privacy guarantee independent of the LLM.
    const purge = calls.find((c) => c.sql.includes("DELETE FROM questions"));
    expect(purge).toBeTruthy();
    expect(purge!.args).toEqual([NOW - RETENTION_SECONDS]);
  });

  it("falls back to Workers AI when Gemini fails, and still writes the digest (#97)", async () => {
    const rows = [{ id: 1, ts: 5, text: "q1", country: "DE", msg_count: 1 }];
    const { db, calls } = fakeD1(handlerWith(rows));
    const fetchImpl = vi.fn(async () => ({
      ok: false,
      status: 429,
      json: async () => ({}),
    })) as unknown as typeof fetch;
    const run = vi.fn(async () => ({ response: "## Fallback theme" }));
    const ai: AiBinding = { run };

    const result = await runDigest(db, "KEY", NOW, fetchImpl, ai);

    expect(result.digested).toBe(1);
    const insert = calls.find((c) => c.sql.includes("INSERT INTO digests"));
    expect(insert).toBeTruthy();
    expect(insert!.args).toEqual([NOW, "## Fallback theme", 1]);
    // The fallback receives the SAME digest prompt Gemini would have.
    const [, options] = run.mock.calls[0] as [string, any];
    expect(options.messages[0].content).toContain("q1");
  });

  it("skips the digest but STILL purges when both vendors fail (#97)", async () => {
    const rows = [{ id: 1, ts: 5, text: "q1", country: "DE", msg_count: 1 }];
    const { db, calls } = fakeD1(handlerWith(rows));
    const fetchImpl = vi.fn(async () => ({
      ok: false,
      status: 429,
      json: async () => ({}),
    })) as unknown as typeof fetch;
    const run = vi.fn(async () => {
      throw new Error("neurons exhausted");
    });
    const ai: AiBinding = { run };

    const result = await runDigest(db, "KEY", NOW, fetchImpl, ai);

    expect(result.digested).toBe(0);
    expect(calls.find((c) => c.sql.includes("INSERT INTO digests"))).toBeUndefined();
    // Purge is a privacy guarantee independent of EVERY vendor.
    const purge = calls.find((c) => c.sql.includes("DELETE FROM questions"));
    expect(purge!.args).toEqual([NOW - RETENTION_SECONDS]);
    // The fallback must have been ATTEMPTED - otherwise this test passes even if
    // the ai param is silently ignored.
    expect(run).toHaveBeenCalled();
  });

  it("does not touch Workers AI when Gemini succeeds", async () => {
    const rows = [{ id: 1, ts: 5, text: "q1", country: "DE", msg_count: 1 }];
    const { db } = fakeD1(handlerWith(rows));
    const fetchImpl = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => ({ candidates: [{ content: { parts: [{ text: "## Theme" }] } }] }),
    })) as unknown as typeof fetch;
    const run = vi.fn(async () => ({ response: "unused" }));

    const result = await runDigest(db, "KEY", NOW, fetchImpl, { run });

    expect(result.digested).toBe(1);
    expect(run).not.toHaveBeenCalled();
  });
});
