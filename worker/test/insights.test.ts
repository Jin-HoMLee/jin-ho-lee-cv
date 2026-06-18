import { describe, expect, it } from "vitest";
import {
  logQuestion,
  lastDigestTs,
  questionsSince,
  insertDigest,
  purgeOld,
  latestDigest,
  recentQuestions,
} from "../src/insights";
import { fakeD1 } from "./fakeD1";

describe("insights data layer", () => {
  it("logQuestion inserts only ts/text/country/msg_count (never an IP column)", async () => {
    const { db, calls } = fakeD1();
    await logQuestion(db, { text: "hi", ts: 100, country: "DE", msg_count: 3 });
    expect(calls).toHaveLength(1);
    expect(calls[0].sql).toContain("INSERT INTO questions");
    expect(calls[0].sql).not.toMatch(/ip/i);
    expect(calls[0].args).toEqual([100, "hi", "DE", 3]);
  });

  it("logQuestion passes a null country through", async () => {
    const { db, calls } = fakeD1();
    await logQuestion(db, { text: "q", ts: 1, country: null, msg_count: 1 });
    expect(calls[0].args).toEqual([1, "q", null, 1]);
  });

  it("lastDigestTs returns 0 when there are no digests", async () => {
    const { db } = fakeD1(() => ({ first: { ts: null } }));
    expect(await lastDigestTs(db)).toBe(0);
  });

  it("lastDigestTs returns the MAX(ts)", async () => {
    const { db, calls } = fakeD1(() => ({ first: { ts: 555 } }));
    expect(await lastDigestTs(db)).toBe(555);
    expect(calls[0].sql).toContain("MAX(ts)");
    expect(calls[0].sql).toContain("FROM digests");
  });

  it("questionsSince binds the ts and returns rows", async () => {
    const rows = [{ id: 1, ts: 2, text: "a", country: "DE", msg_count: 1 }];
    const { db, calls } = fakeD1(() => ({ results: rows }));
    expect(await questionsSince(db, 10)).toEqual(rows);
    expect(calls[0].sql).toContain("WHERE ts > ?");
    expect(calls[0].args).toEqual([10]);
  });

  it("insertDigest binds ts/markdown/n_questions", async () => {
    const { db, calls } = fakeD1();
    await insertDigest(db, { ts: 9, markdown: "# themes", n_questions: 4 });
    expect(calls[0].sql).toContain("INSERT INTO digests");
    expect(calls[0].args).toEqual([9, "# themes", 4]);
  });

  it("purgeOld issues a DELETE bound to the cutoff", async () => {
    const { db, calls } = fakeD1();
    await purgeOld(db, 1234);
    expect(calls[0].sql).toContain("DELETE FROM questions WHERE ts < ?");
    expect(calls[0].args).toEqual([1234]);
  });

  it("latestDigest selects the newest digest", async () => {
    const d = { id: 1, ts: 5, markdown: "x", n_questions: 2 };
    const { db, calls } = fakeD1(() => ({ first: d }));
    expect(await latestDigest(db)).toEqual(d);
    expect(calls[0].sql).toContain("ORDER BY ts DESC");
    expect(calls[0].sql).toContain("LIMIT 1");
  });

  it("recentQuestions binds the limit and returns rows newest-first", async () => {
    const rows = [{ id: 2, ts: 9, text: "b", country: null, msg_count: 1 }];
    const { db, calls } = fakeD1(() => ({ results: rows }));
    expect(await recentQuestions(db, 200)).toEqual(rows);
    expect(calls[0].sql).toContain("ORDER BY ts DESC");
    expect(calls[0].args).toEqual([200]);
  });
});
