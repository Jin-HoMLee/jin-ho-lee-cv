# Phase 12c — Digital-twin lead-capture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a digital-twin visitor opt in to leave contact details; store them (consented, kept) in D1, push a best-effort notification to Jin-Ho via a chat webhook, and surface leads on the existing Access-gated dashboard.

**Architecture:** Extend the existing Cloudflare Worker (`worker/`) with a `POST /lead` route that reuses the 12a CORS/Turnstile/rate-limit guards and the 12b D1 + dashboard. Store-before-notify: the lead is written to D1 first (source of truth), then `ctx.waitUntil(notifyLead(...))` fires a best-effort Telegram message. The Astro widget gains a persistent affordance + a deterministic one-time nudge (after 3 assistant replies — no LLM intent detection).

**Tech Stack:** TypeScript Cloudflare Worker (vitest), Cloudflare D1, Cloudflare Turnstile, Telegram Bot API, Astro (vanilla TS widget).

**Spec:** `docs/superpowers/specs/2026-06-19-phase-12c-lead-capture-design.md`

## Global Constraints

- **Free-tier only.** D1, Cron, Turnstile, Telegram Bot API — zero out-of-pocket cost.
- **Store before notify.** D1 insert is the source of truth; notification is best-effort via `ctx.waitUntil` and must never block or fail the response. A `200` is returned only after the row is stored.
- **No PII in git.** Leads live in Cloudflare D1; the dashboard rendering them is Access-gated and stays off the public surface (sitemap / llms.txt / CNAME). Tests use synthetic emails only.
- **Consent is mandatory.** A row is stored only when `consent === true`; validation rejects otherwise.
- **Leads are kept** — never auto-purged. The 12b purge cron must continue to touch only the `questions` table.
- **Graceful default.** If the Telegram secret/var are unset, `notifyLead` logs and no-ops — the feature still stores leads (mirrors the widget's "endpoint unset → renders nothing").
- **Reuse existing patterns.** Mirror `insights.ts` (data layer), `handler.test.ts` (route tests), `dashboard.ts` (server-rendered HTML, `escapeHtml`), `turnstile.ts` (injectable `fetchImpl`).
- Worker test command: `cd worker && npm test` (vitest). Run a single file with `npx vitest run test/<file>`.

---

### Task 1: Schema + leads data layer

**Files:**
- Modify: `worker/schema.sql` (append `contact_submissions` table)
- Create: `worker/src/leads.ts`
- Test: `worker/test/leads.test.ts`

**Interfaces:**
- Consumes: `D1Database`; `worker/test/fakeD1.ts` (`fakeD1`).
- Produces:
  - `interface LeadInput { email?: unknown; name?: unknown; message?: unknown; consent?: unknown; msg_count?: unknown }`
  - `interface Lead { email: string; name: string | null; message: string | null }`
  - `type ValidateResult = { ok: true; lead: Lead } | { ok: false }`
  - `function validateLead(input: LeadInput): ValidateResult`
  - `interface LeadRow { id: number; ts: number; email: string; name: string | null; message: string | null; country: string | null; consent: number; msg_count: number | null }`
  - `function insertLead(db: D1Database, l: { ts: number; email: string; name: string | null; message: string | null; country: string | null; msg_count: number | null }): Promise<void>`
  - `function recentLeads(db: D1Database, limit: number): Promise<LeadRow[]>`

- [ ] **Step 1: Append the table to `worker/schema.sql`**

```sql

-- Phase 12c lead-capture. Consented contact details a visitor opts in to leave.
-- KEPT (not auto-purged): unlike the 30-day `questions` log, the purpose (follow-up)
-- genuinely needs retention. The 12b purge cron deletes only from `questions`.
CREATE TABLE IF NOT EXISTS contact_submissions (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  ts        INTEGER NOT NULL,         -- unix seconds
  email     TEXT    NOT NULL,         -- required, validated shape
  name      TEXT,                     -- optional
  message   TEXT,                     -- optional, bounded
  country   TEXT,                     -- coarse, from req.cf.country (nullable)
  consent   INTEGER NOT NULL,         -- 1 = explicit opt-in (always 1 if a row exists)
  msg_count INTEGER                   -- conversation length at submit (context)
);
CREATE INDEX IF NOT EXISTS idx_leads_ts ON contact_submissions(ts);
```

- [ ] **Step 2: Write the failing test** — `worker/test/leads.test.ts`

```ts
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
```

- [ ] **Step 3: Run the test, verify it fails**

Run: `cd worker && npx vitest run test/leads.test.ts`
Expected: FAIL — `Cannot find module '../src/leads'`.

- [ ] **Step 4: Write `worker/src/leads.ts`**

```ts
// Phase 12c lead-capture data layer. Mirrors insights.ts: every function takes a
// D1Database so it's unit-testable against test/fakeD1.ts. validateLead is pure.
// Privacy note: this table intentionally stores CONSENTED PII (email, name, message)
// — the deliberate inverse of the ephemeral 12b question log. Rows are KEPT.

export interface LeadInput {
  email?: unknown;
  name?: unknown;
  message?: unknown;
  consent?: unknown;
  msg_count?: unknown;
}

export interface Lead {
  email: string;
  name: string | null;
  message: string | null;
}

export type ValidateResult = { ok: true; lead: Lead } | { ok: false };

// Permissive single-line email shape: one @, a dot in the domain, no whitespace.
// Deliberately not RFC-5322-exhaustive — we only need to reject obvious junk; a
// real typo'd-but-valid address is the visitor's problem, not a security boundary.
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function validateLead(input: LeadInput): ValidateResult {
  if (input.consent !== true) return { ok: false };
  if (typeof input.email !== "string") return { ok: false };
  const email = input.email.trim();
  if (!email || email.length > 254 || !EMAIL_RE.test(email)) return { ok: false };

  let name: string | null = null;
  if (input.name !== undefined && input.name !== null && input.name !== "") {
    if (typeof input.name !== "string" || input.name.length > 100) return { ok: false };
    name = input.name.trim() || null;
  }

  let message: string | null = null;
  if (input.message !== undefined && input.message !== null && input.message !== "") {
    if (typeof input.message !== "string" || input.message.length > 1000) return { ok: false };
    message = input.message.trim() || null;
  }

  return { ok: true, lead: { email, name, message } };
}

export interface LeadRow {
  id: number;
  ts: number;
  email: string;
  name: string | null;
  message: string | null;
  country: string | null;
  consent: number;
  msg_count: number | null;
}

export async function insertLead(
  db: D1Database,
  l: {
    ts: number;
    email: string;
    name: string | null;
    message: string | null;
    country: string | null;
    msg_count: number | null;
  },
): Promise<void> {
  // consent is hardcoded 1: a row only exists because validateLead enforced consent===true.
  await db
    .prepare(
      "INSERT INTO contact_submissions (ts, email, name, message, country, consent, msg_count) VALUES (?, ?, ?, ?, ?, 1, ?)",
    )
    .bind(l.ts, l.email, l.name, l.message, l.country, l.msg_count)
    .run();
}

export async function recentLeads(db: D1Database, limit: number): Promise<LeadRow[]> {
  const { results } = await db
    .prepare(
      "SELECT id, ts, email, name, message, country, consent, msg_count FROM contact_submissions ORDER BY ts DESC LIMIT ?",
    )
    .bind(limit)
    .all<LeadRow>();
  return results ?? [];
}
```

- [ ] **Step 5: Run the test, verify it passes**

Run: `cd worker && npx vitest run test/leads.test.ts`
Expected: PASS (all cases green).

- [ ] **Step 6: Commit**

```bash
git add worker/schema.sql worker/src/leads.ts worker/test/leads.test.ts
git commit -m "feat(12c): contact_submissions schema + leads data layer (validate/insert/recent)"
```

---

### Task 2: Telegram notifier (best-effort, graceful no-op)

**Files:**
- Create: `worker/src/notify.ts`
- Test: `worker/test/notify.test.ts`

**Interfaces:**
- Consumes: nothing from earlier tasks (standalone). Uses an injectable `fetchImpl` like `turnstile.ts`.
- Produces:
  - `interface NotifyLead { email: string; name: string | null; message: string | null; country: string | null; msg_count: number | null; ts: number }`
  - `interface NotifyEnv { TELEGRAM_BOT_TOKEN?: string; TELEGRAM_CHAT_ID?: string }`
  - `type LeadNotifier = (lead: NotifyLead, env: NotifyEnv, fetchImpl?: typeof fetch) => Promise<void>`
  - `function formatLead(lead: NotifyLead): string`
  - `const notifyLead: LeadNotifier` (Telegram-backed default)

- [ ] **Step 1: Write the failing test** — `worker/test/notify.test.ts`

```ts
import { describe, expect, it, vi } from "vitest";
import { notifyLead, formatLead, type NotifyLead } from "../src/notify";

const lead: NotifyLead = {
  email: "a@b.co", name: "Ada", message: "let's talk", country: "DE", msg_count: 5, ts: 100,
};

describe("formatLead", () => {
  it("includes the email and omits absent optional fields", () => {
    const text = formatLead({ ...lead, name: null, message: null });
    expect(text).toContain("a@b.co");
    expect(text).not.toContain("Name:");
    expect(text).not.toContain("Message:");
  });
});

describe("notifyLead", () => {
  it("no-ops (no fetch) when Telegram is not configured", async () => {
    const fetchMock = vi.fn();
    await notifyLead(lead, {}, fetchMock as unknown as typeof fetch);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("POSTs to the Telegram sendMessage API when configured", async () => {
    const fetchMock = vi.fn(async () => ({ ok: true }) as unknown as Response);
    await notifyLead(lead, { TELEGRAM_BOT_TOKEN: "T", TELEGRAM_CHAT_ID: "42" }, fetchMock as unknown as typeof fetch);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("https://api.telegram.org/botT/sendMessage");
    const body = JSON.parse(String(init.body));
    expect(body.chat_id).toBe("42");
    expect(body.text).toContain("a@b.co");
  });

  it("swallows a thrown fetch (best-effort — never rejects)", async () => {
    const fetchMock = vi.fn(async () => {
      throw new Error("network down");
    });
    await expect(
      notifyLead(lead, { TELEGRAM_BOT_TOKEN: "T", TELEGRAM_CHAT_ID: "42" }, fetchMock as unknown as typeof fetch),
    ).resolves.toBeUndefined();
  });
});
```

- [ ] **Step 2: Run the test, verify it fails**

Run: `cd worker && npx vitest run test/notify.test.ts`
Expected: FAIL — `Cannot find module '../src/notify'`.

- [ ] **Step 3: Write `worker/src/notify.ts`**

```ts
// Phase 12c lead notification. Best-effort, behind a tiny swappable interface
// (LeadNotifier). Default backend = Telegram Bot API (free, no DNS / domain
// reputation). Graceful default: if the bot token / chat id are unset, this
// logs and no-ops — the lead is still stored (the dashboard is the backstop).
// fetchImpl is injectable for unit tests (same pattern as turnstile.ts).

export interface NotifyLead {
  email: string;
  name: string | null;
  message: string | null;
  country: string | null;
  msg_count: number | null;
  ts: number;
}

export interface NotifyEnv {
  TELEGRAM_BOT_TOKEN?: string;
  TELEGRAM_CHAT_ID?: string;
}

export type LeadNotifier = (lead: NotifyLead, env: NotifyEnv, fetchImpl?: typeof fetch) => Promise<void>;

export function formatLead(lead: NotifyLead): string {
  return [
    "📇 New lead from your digital twin",
    `Email: ${lead.email}`,
    lead.name ? `Name: ${lead.name}` : null,
    lead.message ? `Message: ${lead.message}` : null,
    lead.country ? `Country: ${lead.country}` : null,
  ]
    .filter(Boolean)
    .join("\n");
}

export const notifyLead: LeadNotifier = async (lead, env, fetchImpl = fetch) => {
  const token = env.TELEGRAM_BOT_TOKEN;
  const chatId = env.TELEGRAM_CHAT_ID;
  if (!token || !chatId) {
    console.log("notifyLead: Telegram not configured — lead stored, notification skipped");
    return;
  }
  try {
    await fetchImpl(`https://api.telegram.org/bot${token}/sendMessage`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ chat_id: chatId, text: formatLead(lead), disable_web_page_preview: true }),
    });
  } catch {
    // Best-effort: the lead is already in D1 and visible on the dashboard.
    console.log("notifyLead: Telegram delivery failed — lead is stored, view it on the dashboard");
  }
};
```

- [ ] **Step 4: Run the test, verify it passes**

Run: `cd worker && npx vitest run test/notify.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add worker/src/notify.ts worker/test/notify.test.ts
git commit -m "feat(12c): best-effort Telegram lead notifier (graceful no-op when unconfigured)"
```

---

### Task 3: `POST /lead` route in the Worker

**Files:**
- Modify: `worker/src/index.ts` (add optional Telegram fields to `Env`; add the `POST /lead` route block)
- Test: `worker/test/lead-handler.test.ts`

**Interfaces:**
- Consumes: `validateLead`, `insertLead` (Task 1); `notifyLead` (Task 2); existing `isAllowedOrigin`, `corsHeaders`, `verifyTurnstile`, `RATE_KV`.
- Produces: the `POST /lead` behaviour (403/400/429/502/200) other code does not call directly.

- [ ] **Step 1: Write the failing test** — `worker/test/lead-handler.test.ts`

```ts
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import worker, { type Env } from "../src/index";
import { fakeD1 } from "./fakeD1";
import { fakeKv } from "./fakeKv";

const ALLOWED = "https://jinholee.is-a.dev";

function makeCtx() {
  const promises: Promise<unknown>[] = [];
  const ctx = {
    waitUntil: (p: Promise<unknown>) => {
      promises.push(p);
    },
    passThroughOnException: () => {},
  } as unknown as ExecutionContext;
  return { ctx, promises };
}

function makeEnv(kv: KVNamespace = fakeKv(), db: D1Database = fakeD1().db): Env {
  return {
    RATE_KV: kv,
    INSIGHTS_DB: db,
    GEMINI_API_KEY: "k",
    TURNSTILE_SECRET_KEY: "s",
    ALLOWED_ORIGIN: ALLOWED,
    MONTHLY_CEILING: "5000",
    MAX_TOKENS: "700",
  };
}

// Turnstile is the only outbound fetch on the /lead path (Telegram is unconfigured
// in tests, so notifyLead no-ops). Branch on URL for safety.
function stubFetch(turnstileSuccess = true) {
  const mock = vi.fn(async (url: string) => {
    if (String(url).includes("challenges.cloudflare.com/turnstile")) {
      return { json: async () => ({ success: turnstileSuccess }) } as unknown as Response;
    }
    throw new Error(`unexpected fetch URL: ${url}`);
  });
  vi.stubGlobal("fetch", mock);
  return mock;
}

function postLead(origin: string | null, body: string): Request {
  const headers: Record<string, string> = { "content-type": "application/json" };
  if (origin) headers.Origin = origin;
  return new Request("https://twin.example/lead", { method: "POST", headers, body });
}

const validLead = JSON.stringify({ email: "a@b.co", name: "Ada", message: "hi", consent: true, msg_count: 4, turnstileToken: "tok" });

beforeEach(() => vi.restoreAllMocks());
afterEach(() => vi.unstubAllGlobals());

describe("POST /lead", () => {
  it("disallowed origin → 403", async () => {
    stubFetch();
    const res = await worker.fetch(postLead("https://evil.example", validLead), makeEnv(), makeCtx().ctx);
    expect(res.status).toBe(403);
  });

  it("non-JSON body → 400, Turnstile not called", async () => {
    const fetchMock = stubFetch();
    const res = await worker.fetch(postLead(ALLOWED, "not json {"), makeEnv(), makeCtx().ctx);
    expect(res.status).toBe(400);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("missing consent → 400 before Turnstile", async () => {
    const fetchMock = stubFetch();
    const body = JSON.stringify({ email: "a@b.co", turnstileToken: "tok" });
    const res = await worker.fetch(postLead(ALLOWED, body), makeEnv(), makeCtx().ctx);
    expect(res.status).toBe(400);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("malformed email → 400 before Turnstile", async () => {
    const fetchMock = stubFetch();
    const body = JSON.stringify({ email: "nope", consent: true, turnstileToken: "tok" });
    const res = await worker.fetch(postLead(ALLOWED, body), makeEnv(), makeCtx().ctx);
    expect(res.status).toBe(400);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("Turnstile failure → 403, nothing stored", async () => {
    stubFetch(false);
    const { db, calls } = fakeD1();
    const res = await worker.fetch(postLead(ALLOWED, validLead), makeEnv(fakeKv(), db), makeCtx().ctx);
    expect(res.status).toBe(403);
    expect(calls.find((c) => c.sql.includes("INSERT INTO contact_submissions"))).toBeUndefined();
  });

  it("per-IP daily cap (3) exceeded → 429, nothing stored", async () => {
    stubFetch();
    const { db, calls } = fakeD1();
    const env = makeEnv(fakeKv({ "lead:0.0.0.0": "3" }), db);
    const res = await worker.fetch(postLead(ALLOWED, validLead), env, makeCtx().ctx);
    expect(res.status).toBe(429);
    expect(calls.find((c) => c.sql.includes("INSERT INTO contact_submissions"))).toBeUndefined();
  });

  it("happy path → 200, stores one lead row (consent=1) and schedules notify", async () => {
    stubFetch();
    const { db, calls } = fakeD1();
    const { ctx, promises } = makeCtx();
    const res = await worker.fetch(postLead(ALLOWED, validLead), makeEnv(fakeKv(), db), ctx);
    expect(res.status).toBe(200);
    await Promise.all(promises); // flush the fire-and-forget notify
    const insert = calls.find((c) => c.sql.includes("INSERT INTO contact_submissions"));
    expect(insert).toBeTruthy();
    // args: [ts, email, name, message, country, msg_count]
    expect(insert!.args[1]).toBe("a@b.co");
    expect(insert!.args[2]).toBe("Ada");
    expect(insert!.args[5]).toBe(4);
  });

  it("D1 insert failure → 502 application/json", async () => {
    stubFetch();
    // A db whose prepare().run() throws simulates a storage failure.
    const db = {
      prepare() {
        return { bind: () => ({ run: async () => { throw new Error("d1 down"); } }) };
      },
    } as unknown as D1Database;
    const res = await worker.fetch(postLead(ALLOWED, validLead), makeEnv(fakeKv(), db), makeCtx().ctx);
    expect(res.status).toBe(502);
    expect(res.headers.get("content-type")).toBe("application/json");
  });
});
```

- [ ] **Step 2: Run the test, verify it fails**

Run: `cd worker && npx vitest run test/lead-handler.test.ts`
Expected: FAIL — `/lead` is not routed, so requests fall through to the chat handler and return 400/403 for the wrong reasons (e.g. the happy-path test fails because no `INSERT INTO contact_submissions` is recorded).

- [ ] **Step 3: Add the optional Telegram fields to `Env`** in `worker/src/index.ts`

Find the `Env` interface (lines ~14-22) and add the two optional fields:

```ts
export interface Env {
  RATE_KV: KVNamespace;
  INSIGHTS_DB: D1Database;
  GEMINI_API_KEY: string;
  TURNSTILE_SECRET_KEY: string;
  ALLOWED_ORIGIN: string;
  MONTHLY_CEILING: string;
  MAX_TOKENS: string;
  TELEGRAM_BOT_TOKEN?: string;
  TELEGRAM_CHAT_ID?: string;
}
```

- [ ] **Step 4: Add the imports** at the top of `worker/src/index.ts`

```ts
import { validateLead, insertLead } from "./leads";
import { notifyLead } from "./notify";
```

- [ ] **Step 5: Add the `POST /lead` route block** in `worker/src/index.ts`

Insert immediately AFTER the `GET /twin-insights` block (after its closing `}`, before the `if (req.method !== "POST" || ...)` chat guard). The route validates shape BEFORE spending a Turnstile token (mirrors the chat handler), then stores-before-notify:

```ts
    // Phase 12c lead-capture. Reuses the same CORS allowlist + Turnstile as chat,
    // plus a modest per-IP daily submit cap (a public form is a spam target).
    // Store-before-notify: the lead is written to D1 first (source of truth); the
    // Telegram push is best-effort via ctx.waitUntil and never blocks the 200.
    if (req.method === "POST" && url.pathname === "/lead") {
      if (!isAllowedOrigin(origin, env.ALLOWED_ORIGIN))
        return new Response("forbidden", { status: 403, headers: cors });

      const leadIp = req.headers.get("CF-Connecting-IP") ?? "0.0.0.0";

      let leadBody: { turnstileToken?: unknown; msg_count?: unknown } & Record<string, unknown>;
      try {
        leadBody = (await req.json()) as typeof leadBody;
      } catch {
        return new Response("bad request", { status: 400, headers: cors });
      }
      if (typeof leadBody.turnstileToken !== "string")
        return new Response("bad request", { status: 400, headers: cors });

      // Validate shape (incl. consent) before spending the single-use Turnstile token.
      const parsed = validateLead(leadBody);
      if (!parsed.ok) return new Response("bad request", { status: 400, headers: cors });

      const okLead = await verifyTurnstile(leadBody.turnstileToken, env.TURNSTILE_SECRET_KEY, leadIp);
      if (!okLead) return new Response("challenge failed", { status: 403, headers: cors });

      // Per-IP daily submit cap (3/day). Separate key namespace from the chat counters.
      const capKey = `lead:${leadIp}`;
      const submitted = Number((await env.RATE_KV.get(capKey)) ?? 0);
      if (submitted >= 3)
        return new Response("slow down a moment", { status: 429, headers: cors });
      await env.RATE_KV.put(capKey, String(submitted + 1), { expirationTtl: 86400 });

      const leadCountry = (req as { cf?: { country?: string } }).cf?.country ?? null;
      const leadMsgCount = typeof leadBody.msg_count === "number" ? leadBody.msg_count : null;
      const leadTs = Math.floor(Date.now() / 1000);

      // Store FIRST — the row is the source of truth. On failure, be honest (502);
      // never claim success on an unstored lead.
      try {
        await insertLead(env.INSIGHTS_DB, {
          ts: leadTs,
          email: parsed.lead.email,
          name: parsed.lead.name,
          message: parsed.lead.message,
          country: leadCountry,
          msg_count: leadMsgCount,
        });
      } catch {
        return new Response(JSON.stringify({ error: "could not store lead" }), {
          status: 502,
          headers: { ...cors, "content-type": "application/json" },
        });
      }

      // Best-effort notification — off the response path so a webhook failure can
      // never break the visitor's 200.
      ctx.waitUntil(
        notifyLead(
          {
            email: parsed.lead.email,
            name: parsed.lead.name,
            message: parsed.lead.message,
            country: leadCountry,
            msg_count: leadMsgCount,
            ts: leadTs,
          },
          env,
        ).catch(() => {}),
      );

      return new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { ...cors, "content-type": "application/json" },
      });
    }
```

- [ ] **Step 6: Run the new test AND the existing handler test, verify both pass**

Run: `cd worker && npx vitest run test/lead-handler.test.ts test/handler.test.ts`
Expected: PASS (the chat path is unaffected — `/lead` is matched before the chat guard).

- [ ] **Step 7: Commit**

```bash
git add worker/src/index.ts worker/test/lead-handler.test.ts
git commit -m "feat(12c): POST /lead route (CORS+Turnstile+cap, store-before-notify)"
```

---

### Task 4: Surface leads on the Access-gated dashboard

**Files:**
- Modify: `worker/src/dashboard.ts` (add `leads` to `renderDashboard`)
- Modify: `worker/src/index.ts` (fetch `recentLeads` in the `GET /twin-insights` handler and pass them in)
- Test: `worker/test/dashboard.test.ts` (add cases)

**Interfaces:**
- Consumes: `LeadRow`, `recentLeads` (Task 1).
- Produces: `renderDashboard` now requires a `leads: LeadRow[]` field in its argument object.

- [ ] **Step 1: Add the failing dashboard test cases** to `worker/test/dashboard.test.ts`

Add to the existing `base` object a `leads` field, then add the new cases. Update the top import:

```ts
import { escapeHtml, renderDashboard } from "../src/dashboard";
```

Extend `base`:

```ts
  const base = {
    digest: { id: 1, ts: 1_700_000_000, markdown: "## Theme A\n3 questions", n_questions: 3 },
    monthCount: 142,
    ceiling: 5000,
    questions: [
      { id: 2, ts: 1_700_000_500, text: "what is your salary?", country: "DE", msg_count: 2 },
    ],
    leads: [
      { id: 1, ts: 1_700_000_900, email: "ada@example.com", name: "Ada", message: "let's chat", country: "GB", consent: 1, msg_count: 5 },
    ],
  };
```

Add these `it` blocks inside `describe("renderDashboard", ...)`:

```ts
  it("renders a Leads section with the email as a mailto link", () => {
    const html = renderDashboard(base);
    expect(html.toLowerCase()).toContain("leads");
    expect(html).toContain('href="mailto:ada@example.com"');
    expect(html).toContain("Ada");
    expect(html).toContain("let&#39;s chat"); // escaped apostrophe
  });

  it("escapes an untrusted lead email/name (no raw script survives)", () => {
    const html = renderDashboard({
      ...base,
      leads: [{ id: 9, ts: 1, email: "x@y.co", name: "<script>alert(1)</script>", message: null, country: null, consent: 1, msg_count: null }],
    });
    expect(html).not.toContain("<script>alert(1)</script>");
    expect(html).toContain("&lt;script&gt;");
  });

  it("handles no leads yet without throwing", () => {
    const html = renderDashboard({ ...base, leads: [] });
    expect(html.toLowerCase()).toContain("no leads");
  });
```

- [ ] **Step 2: Run the dashboard test, verify it fails**

Run: `cd worker && npx vitest run test/dashboard.test.ts`
Expected: FAIL — `renderDashboard` ignores `leads`; the new assertions (mailto link, "no leads") fail.

- [ ] **Step 3: Update `renderDashboard` in `worker/src/dashboard.ts`**

Add the import at the top:

```ts
import type { DigestRow, QuestionRow, LeadRow } from "./insights";
```

Wait — `LeadRow` lives in `leads.ts`, not `insights.ts`. Use two imports:

```ts
import type { DigestRow, QuestionRow } from "./insights";
import type { LeadRow } from "./leads";
```

Extend the `data` parameter type and destructure:

```ts
export function renderDashboard(data: {
  digest: DigestRow | null;
  monthCount: number;
  ceiling: number;
  questions: QuestionRow[];
  leads: LeadRow[];
}): string {
  const { digest, monthCount, ceiling, questions, leads } = data;
```

Build the leads section. Add this block just before the existing `const rows = questions...`:

```ts
  const leadRows = leads
    .map(
      (l) =>
        `<tr><td style="padding:6px 10px;border-bottom:1px solid #272d39"><a style="color:#7aa2f7" href="mailto:${escapeHtml(
          l.email,
        )}">${escapeHtml(l.email)}</a></td><td style="padding:6px 10px;border-bottom:1px solid #272d39">${escapeHtml(
          l.name ?? "—",
        )}</td><td style="padding:6px 10px;border-bottom:1px solid #272d39;color:#99a0ac">${escapeHtml(
          l.message ?? "—",
        )}</td><td style="padding:6px 10px;border-bottom:1px solid #272d39;color:#99a0ac">${escapeHtml(
          l.country ?? "—",
        )}</td><td style="padding:6px 10px;border-bottom:1px solid #272d39;color:#99a0ac">${fmtTime(
          l.ts,
        )}</td></tr>`,
    )
    .join("");

  const leadsBlock = leads.length
    ? `<table><thead><tr><th>Email</th><th>Name</th><th>Message</th><th>Country</th><th>Time</th></tr></thead><tbody>${leadRows}</tbody></table>`
    : `<p style="color:#99a0ac">No leads yet — opted-in contact details will appear here.</p>`;
```

Insert the section into the returned HTML, right after the digest block and before "Recent questions":

```ts
<h2>📇 Leads (${leads.length})</h2>
${leadsBlock}
<h2>Recent questions (${questions.length})</h2>
```

- [ ] **Step 4: Wire `recentLeads` into the `GET /twin-insights` handler** in `worker/src/index.ts`

Add `recentLeads` to the leads import (Task 3 added `import { validateLead, insertLead } from "./leads";`):

```ts
import { validateLead, insertLead, recentLeads } from "./leads";
```

In the `GET /twin-insights` block, extend the `Promise.all` and pass `leads`:

```ts
      const [digest, questions, leads] = await Promise.all([
        latestDigest(env.INSIGHTS_DB),
        recentQuestions(env.INSIGHTS_DB, 200),
        recentLeads(env.INSIGHTS_DB, 200),
      ]);
      const html = renderDashboard({
        digest,
        monthCount,
        ceiling: finite(env.MONTHLY_CEILING, 5000),
        questions,
        leads,
      });
```

- [ ] **Step 5: Run the dashboard test AND the handler test, verify both pass**

Run: `cd worker && npx vitest run test/dashboard.test.ts test/handler.test.ts`
Expected: PASS. (The existing `GET /twin-insights` handler test seeds D1 via a SQL-branching fake; a `FROM contact_submissions` select returns `[]` by default, so the dashboard renders "No leads yet".)

- [ ] **Step 6: Run the FULL worker suite**

Run: `cd worker && npm test`
Expected: PASS — all files green.

- [ ] **Step 7: Commit**

```bash
git add worker/src/dashboard.ts worker/src/index.ts worker/test/dashboard.test.ts
git commit -m "feat(12c): show opted-in leads on the Access-gated dashboard"
```

---

### Task 5: Widget affordance + nudge + lead form (frontend)

**Files:**
- Modify: `web/src/lib/twin.ts` (add `submitLead`)
- Modify: `web/src/components/DigitalTwin.astro` (button, nudge, form, submit handler, styles)

**Interfaces:**
- Consumes: the Worker `POST /lead` contract (Task 3): JSON `{ email, name, message, consent, msg_count, turnstileToken }` → `200 { ok: true }` on success.
- Produces: `submitLead(endpoint: string, payload: { email: string; name: string; message: string; consent: boolean; msg_count: number }, turnstileToken: string): Promise<boolean>`.

> **Note:** No web unit-test harness exists (Astro project, no vitest). This task is verified manually against a local Worker (`just worker-dev`) + dev site (`just web-dev`), plus a Playwright screenshot per the `reference_web_visual_verify` memory.

- [ ] **Step 1: Add `submitLead` to `web/src/lib/twin.ts`**

Append to the end of the file:

```ts
// Phase 12c: post an opted-in lead to the Worker's /lead route. The endpoint is the
// twin root URL; /lead is a sibling route. Returns true on a 2xx (the Worker stores
// the lead before responding), false otherwise — the widget surfaces a retry notice.
export async function submitLead(
  endpoint: string,
  payload: { email: string; name: string; message: string; consent: boolean; msg_count: number },
  turnstileToken: string,
): Promise<boolean> {
  const url = endpoint.replace(/\/+$/, "") + "/lead";
  try {
    const res = await fetch(url, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ ...payload, turnstileToken }),
    });
    return res.ok;
  } catch {
    return false;
  }
}
```

- [ ] **Step 2: Add the affordance + nudge + form markup** in `web/src/components/DigitalTwin.astro`

Inside `#twin-panel`, immediately after the `<form id="twin-form">…</form>` and before the `<div class="cf-turnstile">`, add:

```astro
      <button type="button" id="twin-lead-toggle" class="twin-lead-toggle">📇 Leave your details for Jin-Ho</button>
      <div id="twin-nudge" class="twin-nudge" hidden>
        <p>Enjoying the chat? You can leave your details and Jin-Ho will follow up personally.</p>
        <div class="twin-nudge-actions">
          <button type="button" id="twin-nudge-open">Leave details</button>
          <button type="button" id="twin-nudge-dismiss" aria-label="Dismiss">Not now</button>
        </div>
      </div>
      <form id="twin-lead-form" class="twin-lead-form" hidden>
        <input id="twin-lead-email" type="email" required autocomplete="email" maxlength="254" placeholder="Your email (required)" />
        <input id="twin-lead-name" type="text" autocomplete="name" maxlength="100" placeholder="Your name (optional)" />
        <textarea id="twin-lead-message" maxlength="1000" rows="2" placeholder="A short message (optional)"></textarea>
        <label class="twin-consent">
          <input id="twin-lead-consent" type="checkbox" />
          <span>I agree to share these details so Jin-Ho can follow up about opportunities. They're stored securely and kept until I ask for removal.</span>
        </label>
        <button type="submit">Send my details</button>
        <p id="twin-lead-status" class="twin-lead-status" aria-live="polite"></p>
      </form>
```

- [ ] **Step 3: Add the widget logic** in the `<script>` block of `DigitalTwin.astro`

Add the `submitLead` import to the existing import line:

```ts
    import { streamTwin, submitLead } from "../lib/twin";
```

After the existing element lookups (near `const avatarTpl = …`), add the lead-form element handles, the assistant-reply counter, and the handlers. Place this block after the `form.addEventListener("submit", …)` chat handler:

```ts
    // ---- Phase 12c: lead capture ----
    const leadToggle = document.getElementById("twin-lead-toggle")!;
    const nudge = document.getElementById("twin-nudge")!;
    const leadForm = document.getElementById("twin-lead-form") as HTMLFormElement;
    const leadEmail = document.getElementById("twin-lead-email") as HTMLInputElement;
    const leadName = document.getElementById("twin-lead-name") as HTMLInputElement;
    const leadMessage = document.getElementById("twin-lead-message") as HTMLTextAreaElement;
    const leadConsent = document.getElementById("twin-lead-consent") as HTMLInputElement;
    const leadStatus = document.getElementById("twin-lead-status")!;

    let assistantReplies = 0; // bumped on each completed assistant turn (see chat handler)
    let nudgeShown = false; // one-time: never re-show after dismiss/open
    const NUDGE_AFTER = 3;

    function showLeadForm(): void {
      leadForm.hidden = false;
      nudge.hidden = true;
      nudgeShown = true;
      leadEmail.focus();
    }
    function maybeNudge(): void {
      if (nudgeShown || leadForm.hidden === false) return;
      if (assistantReplies >= NUDGE_AFTER) {
        nudge.hidden = false;
        nudgeShown = true;
      }
    }

    leadToggle.addEventListener("click", () => {
      leadForm.hidden = !leadForm.hidden;
      if (!leadForm.hidden) leadEmail.focus();
    });
    document.getElementById("twin-nudge-open")!.addEventListener("click", showLeadForm);
    document.getElementById("twin-nudge-dismiss")!.addEventListener("click", () => {
      nudge.hidden = true;
      nudgeShown = true;
    });

    leadForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const email = leadEmail.value.trim();
      if (!email) {
        leadStatus.textContent = "An email is required.";
        return;
      }
      if (!leadConsent.checked) {
        leadStatus.textContent = "Please tick the consent box so I can pass your details on.";
        return;
      }
      // @ts-expect-error — Turnstile global from the injected script.
      const token = window.turnstile?.getResponse?.() ?? "";
      if (!token) {
        leadStatus.textContent = "One sec — finishing a quick anti-spam check, try again.";
        return;
      }
      leadStatus.textContent = "Sending…";
      const ok = await submitLead(
        endpoint,
        {
          email,
          name: leadName.value.trim(),
          message: leadMessage.value.trim(),
          consent: true,
          msg_count: history.length,
        },
        token,
      );
      // @ts-expect-error — Turnstile global from the injected script.
      window.turnstile?.reset?.();
      if (ok) {
        leadForm.hidden = true;
        notice("Thanks — I've passed your details to Jin-Ho; he'll be in touch. 👋");
      } else {
        leadStatus.textContent = "Hmm, that didn't go through — please try again in a moment.";
      }
    });
```

In the chat `form.addEventListener("submit", …)` handler, bump the counter and trigger the nudge after a completed assistant turn. Locate `history.push({ role: "assistant", content: acc });` (right after the `if (!acc) throw …` line) and add immediately after it:

```ts
        assistantReplies += 1;
        maybeNudge();
```

- [ ] **Step 4: Add styles** at the end of the `<style>` block in `DigitalTwin.astro` (before the closing `</style>`)

```css
    .twin-lead-toggle {
      align-self: flex-start;
      padding: 0.3125rem 0.625rem;
      border-radius: 9999px;
      border: 1px solid var(--surface-border);
      background: var(--surface-2);
      color: var(--muted);
      font-size: 0.75rem;
      cursor: pointer;
      transition: color 0.15s, border-color 0.15s;
    }
    .twin-lead-toggle:hover { color: var(--accent); border-color: var(--accent); }

    .twin-nudge {
      padding: 0.625rem;
      border-radius: 0.625rem;
      border: 1px solid var(--accent);
      background: var(--surface-2);
      font-size: 0.8125rem;
    }
    .twin-nudge[hidden] { display: none; }
    .twin-nudge p { margin: 0 0 0.5rem; }
    .twin-nudge-actions { display: flex; gap: 0.5rem; }
    .twin-nudge-actions button {
      padding: 0.3125rem 0.625rem;
      border-radius: 0.5rem;
      border: 1px solid var(--surface-border);
      background: var(--bg);
      color: var(--text);
      font: inherit;
      font-size: 0.75rem;
      cursor: pointer;
    }
    #twin-nudge-open { background: var(--accent); color: var(--accent-contrast); border: none; }

    .twin-lead-form {
      display: flex;
      flex-direction: column;
      gap: 0.5rem;
    }
    .twin-lead-form[hidden] { display: none; }
    .twin-lead-form input,
    .twin-lead-form textarea {
      padding: 0.5rem 0.625rem;
      border-radius: 0.5rem;
      border: 1px solid var(--surface-border);
      background: var(--bg);
      color: var(--text);
      font: inherit;
      resize: vertical;
    }
    .twin-lead-form input::placeholder,
    .twin-lead-form textarea::placeholder { color: var(--faint); }
    .twin-consent {
      display: flex;
      gap: 0.5rem;
      align-items: flex-start;
      font-size: 0.75rem;
      color: var(--muted);
      line-height: 1.4;
    }
    .twin-consent input { margin-top: 0.2rem; flex: none; }
    .twin-lead-form button[type="submit"] {
      align-self: flex-start;
      padding: 0.5rem 0.875rem;
      border-radius: 0.5rem;
      border: none;
      background: var(--accent);
      color: var(--accent-contrast);
      font-weight: 600;
      cursor: pointer;
    }
    .twin-lead-status { margin: 0; font-size: 0.75rem; color: var(--muted); min-height: 1em; }
```

- [ ] **Step 5: Type-check the web project**

Run: `cd web && npm run check`
Expected: 0 errors (Astro `astro check` passes).

- [ ] **Step 6: Manual verification against a local Worker**

1. Set up local secrets: `cp worker/.dev.vars.example worker/.dev.vars` and ensure `ALLOWED_ORIGIN` includes `http://localhost:4321`. (Telegram can stay unset — the lead still stores and `notifyLead` no-ops.)
2. Apply the new table to local D1: `cd worker && npx wrangler d1 execute twin-insights --local --file=schema.sql`
3. Terminal A: `just worker-dev`  Terminal B: `just web-dev`
4. In the browser (http://localhost:4321): open the twin, send 3+ messages, confirm the nudge appears once after the 3rd reply; dismiss it and confirm it does not return. Click "📇 Leave your details", submit with an invalid email (blocked), without consent (blocked), then a valid synthetic email + consent → "Thanks…" confirmation.
5. Confirm storage: `cd worker && npx wrangler d1 execute twin-insights --local --command "SELECT email, name, consent FROM contact_submissions"` shows the row with `consent = 1`.
6. Screenshot the open form (light + dark) via Playwright per the `reference_web_visual_verify` memory; eyeball spacing/contrast.

- [ ] **Step 7: Commit**

```bash
git add web/src/lib/twin.ts web/src/components/DigitalTwin.astro
git commit -m "feat(12c): twin widget lead affordance, one-time nudge, consent form"
```

---

### Task 6: Config, deploy docs, and CLAUDE.md

**Files:**
- Modify: `worker/wrangler.toml` (add `TELEGRAM_CHAT_ID` var placeholder + comment)
- Modify: `worker/.dev.vars.example` (document the Telegram local-dev vars)
- Modify: `worker/README.md` (deploy steps: schema apply + secret put) — if absent, add a short "Phase 12c lead-capture" note where 12b deploy steps live
- Modify: `CLAUDE.md` (Phasing table row + convention note)

**Interfaces:** none (docs/config only).

- [ ] **Step 1: Add the Telegram chat-id var to `worker/wrangler.toml`**

In the `[vars]` block, add (the chat id is account/chat-scoped, not a secret — same reasoning as the KV/D1 ids):

```toml
# Phase 12c lead-capture: Telegram chat id for lead notifications (not a secret —
# chat-scoped). The bot token IS a secret: `wrangler secret put TELEGRAM_BOT_TOKEN`.
# Both unset → notifyLead no-ops gracefully (leads still store + show on the dashboard).
TELEGRAM_CHAT_ID = ""
```

- [ ] **Step 2: Document the local-dev Telegram vars in `worker/.dev.vars.example`**

Append:

```
# Phase 12c lead-capture notifications (optional locally — unset → notifyLead no-ops):
# TELEGRAM_BOT_TOKEN = "..."
# TELEGRAM_CHAT_ID = "..."
```

- [ ] **Step 3: Add the deploy note** (in `worker/README.md`, near the 12b D1/Access deploy steps; if no README, create a short one)

```markdown
### Phase 12c lead-capture deploy

The `contact_submissions` table ships in `schema.sql` — re-apply it remotely after deploy:

    npx wrangler d1 execute twin-insights --remote --file=schema.sql

Set the Telegram notifier (optional — leads still store + show on the dashboard if unset):

    npx wrangler secret put TELEGRAM_BOT_TOKEN     # from @BotFather
    # set TELEGRAM_CHAT_ID in wrangler.toml [vars] (your chat id from @userinfobot)

Then `just worker-deploy`. Leads appear in the 📇 Leads section of `/twin-insights`.
```

- [ ] **Step 4: Update the Phasing table in `CLAUDE.md`**

Add this row after the 12b row:

```markdown
| 12c | Digital-twin lead-capture (consented opt-in contact form: persistent affordance + one-time nudge → `contact_submissions` D1 + best-effort Telegram notify + leads on the 12b dashboard) | ✅ Done (merged <DATE>, `--no-ff`, PR #<N>, commit `<sha>`); leads KEPT (no TTL — purpose-driven retention, the deliberate flip vs 12b's 30-day questions); Telegram notifier graceful no-op when unconfigured; reuses 12a Turnstile/CORS + a per-IP 3/day submit cap. Worker deploy (remote schema re-apply + `TELEGRAM_BOT_TOKEN` secret) is a separate manual step |
```

(Leave `<DATE>`/`<N>`/`<sha>` to fill at merge — the merge commit is the finishing step. Until then, mark the row `🚧 In progress (branch `phase-12c-lead-capture`)`.)

- [ ] **Step 5: Add a convention note** under the Worker bullet in CLAUDE.md "Conventions" (after the D1+Cron note)

```markdown
- **Worker also captures consented leads (Phase 12c).** A `POST /lead` route stores
  visitor-opted-in contact details in the `contact_submissions` D1 table (KEPT — not
  auto-purged, unlike the 30-day `questions` log; purpose-driven retention). It reuses
  the 12a Turnstile + CORS guards plus a per-IP 3/day submit cap, and fires a
  best-effort Telegram notification via `ctx.waitUntil` (graceful no-op when
  `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` are unset). Leads surface in the 📇 Leads
  section of the Access-gated `/twin-insights` dashboard. No PII reaches git (leads
  live in D1; the route is off the public surface).
```

- [ ] **Step 6: Run the full gate one more time**

Run: `cd worker && npm test && npx tsc --noEmit` then from repo root `just validate && just test && just lint`
Expected: all green. (Root `just test`/`lint` cover the Python side, unaffected; the worker suite covers the new TS.)

- [ ] **Step 7: Commit**

```bash
git add worker/wrangler.toml worker/.dev.vars.example worker/README.md CLAUDE.md
git commit -m "docs(12c): config, deploy steps, and CLAUDE.md phase row"
```

---

## Self-Review

**1. Spec coverage:**
- Affordance + one-time nudge → Task 5 ✅
- Consent-clear copy → Task 5 (consent label) ✅
- `contact_submissions` table (kept, not purged) → Task 1 ✅ (purge untouched — note in schema comment)
- Turnstile-protected submit + per-IP cap → Task 3 ✅
- Notification (Telegram, swappable, graceful) → Task 2 + Task 3 wiring ✅
- Leads on the dashboard → Task 4 ✅
- Store-before-notify / error table (400/403/429/502/200) → Task 3 ✅
- Config/secrets + deploy + CLAUDE.md row → Task 6 ✅

**2. Placeholder scan:** Every code step shows full code; commands have expected output. The only intentional `<DATE>/<N>/<sha>` placeholders are in the CLAUDE.md row, filled at merge time (finishing step) — flagged explicitly.

**3. Type consistency:**
- `validateLead` returns `{ ok: true; lead: Lead } | { ok: false }` — consumed in Task 3 as `parsed.ok` / `parsed.lead` ✅
- `insertLead` signature (object with `ts/email/name/message/country/msg_count`) matches Task 3 call ✅
- `LeadRow` defined in `leads.ts`, imported by `dashboard.ts` (Task 4) and used by `recentLeads` ✅
- `notifyLead(lead: NotifyLead, env: NotifyEnv, fetchImpl?)` — Task 3 calls `notifyLead(leadObj, env)` (fetchImpl defaults) ✅
- `submitLead` payload shape matches the `POST /lead` body the route parses (`email/name/message/consent/msg_count/turnstileToken`) ✅
