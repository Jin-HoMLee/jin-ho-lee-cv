import { describe, expect, it, vi } from "vitest";
import { buildDigestPrompt, runDigest, RETENTION_SECONDS } from "../src/digest";
import { fakeD1 } from "./fakeD1";

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
});
