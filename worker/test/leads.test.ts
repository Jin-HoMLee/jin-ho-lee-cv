import { describe, expect, it } from "vitest";
import { validateLead, insertLead, recentLeads } from "../src/leads";
import { fakeD1 } from "./fakeD1";

describe("validateLead", () => {
  it("accepts a valid email with consent; trims and nulls empty optionals", () => {
    const r = validateLead({ email: "  a@b.co ", consent: true });
    expect(r).toEqual({ ok: true, lead: { email: "a@b.co", name: null, message: null } });
  });

  it("keeps trimmed name and message when present", () => {
    const r = validateLead({ email: "a@b.co", name: " Ada ", message: " hi ", consent: true });
    expect(r).toEqual({ ok: true, lead: { email: "a@b.co", name: "Ada", message: "hi" } });
  });

  it("rejects when consent is not exactly true", () => {
    expect(validateLead({ email: "a@b.co", consent: false }).ok).toBe(false);
    expect(validateLead({ email: "a@b.co" }).ok).toBe(false);
    expect(validateLead({ email: "a@b.co", consent: "true" }).ok).toBe(false);
  });

  it("rejects a malformed or missing email", () => {
    expect(validateLead({ email: "nope", consent: true }).ok).toBe(false);
    expect(validateLead({ email: "a@b", consent: true }).ok).toBe(false);
    expect(validateLead({ consent: true }).ok).toBe(false);
    expect(validateLead({ email: 42, consent: true }).ok).toBe(false);
  });

  it("rejects an over-long email / name / message", () => {
    expect(validateLead({ email: "a@" + "b".repeat(253) + ".co", consent: true }).ok).toBe(false);
    expect(validateLead({ email: "a@b.co", name: "x".repeat(101), consent: true }).ok).toBe(false);
    expect(validateLead({ email: "a@b.co", message: "x".repeat(1001), consent: true }).ok).toBe(false);
  });

  it("trims whitespace-only name/message to null", () => {
    const r = validateLead({ email: "a@b.co", name: "   ", message: "\t\n", consent: true });
    expect(r).toEqual({ ok: true, lead: { email: "a@b.co", name: null, message: null } });
  });
});

describe("leads data layer", () => {
  it("insertLead writes ts/email/name/message/country/consent=1/msg_count", async () => {
    const { db, calls } = fakeD1();
    await insertLead(db, {
      ts: 100, email: "a@b.co", name: "Ada", message: "hi", country: "DE", msg_count: 4,
    });
    expect(calls).toHaveLength(1);
    expect(calls[0].sql).toContain("INSERT INTO contact_submissions");
    expect(calls[0].args).toEqual([100, "a@b.co", "Ada", "hi", "DE", 4]);
  });

  it("insertLead passes null optionals through", async () => {
    const { db, calls } = fakeD1();
    await insertLead(db, { ts: 1, email: "a@b.co", name: null, message: null, country: null, msg_count: null });
    expect(calls[0].args).toEqual([1, "a@b.co", null, null, null, null]);
  });

  it("recentLeads binds the limit and returns rows newest-first", async () => {
    const rows = [{ id: 2, ts: 9, email: "a@b.co", name: null, message: null, country: null, consent: 1, msg_count: 1 }];
    const { db, calls } = fakeD1(() => ({ results: rows }));
    expect(await recentLeads(db, 200)).toEqual(rows);
    expect(calls[0].sql).toContain("FROM contact_submissions");
    expect(calls[0].sql).toContain("ORDER BY ts DESC");
    expect(calls[0].args).toEqual([200]);
  });
});
