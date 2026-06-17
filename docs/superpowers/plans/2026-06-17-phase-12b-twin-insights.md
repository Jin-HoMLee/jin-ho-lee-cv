# Phase 12b — Digital Twin insights Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Log each allowed visitor question to a D1 database, generate a daily Gemini-themed digest (purging raw questions after 30 days), and serve a private Cloudflare-Access-gated HTML dashboard from the existing Phase 12a Worker.

**Architecture:** Pure extension of `worker/src/index.ts` — no new Cloudflare service beyond D1 + Cron Triggers. A new `insights.ts` data layer (functions taking a `D1Database`) handles all SQL; `digest.ts` orchestrates the cron; `dashboard.ts` renders self-contained HTML. The `fetch` handler gains a `ctx` arg and fire-and-forget logging via `ctx.waitUntil`, a `GET /twin-insights` route, and a sibling `scheduled()` export. D1 is tested against a lightweight in-memory fake (no `@cloudflare/vitest-pool-workers`); Gemini is mocked via `vi.stubGlobal("fetch")` exactly as in 12a.

**Tech Stack:** TypeScript, Cloudflare Workers (D1, KV, Cron Triggers), Google Gemini (`gemini-3.5-flash`) free tier, Vitest 2, Wrangler 3.

## Global Constraints

- **No new test dependency.** Reuse plain `vitest` + the `md-stub` plugin + `vi.stubGlobal("fetch")`. Do **not** add `@cloudflare/vitest-pool-workers` or miniflare.
- **No new runtime dependency.** The Worker must not gain a markdown-rendering or any other npm dependency; render the digest markdown inside a `<pre>` block.
- **Free-tier only.** D1, Cron Triggers, and the digest's Gemini call must stay on free tiers. Reuse the existing `GEMINI_API_KEY` secret — no new credential.
- **Privacy invariants (never violate):** the `questions` table stores only `text`, `ts`, `country`, `msg_count`. Never store a raw IP (`CF-Connecting-IP`), the twin's answer, or any fingerprint. `country` comes from `req.cf?.country` only.
- **Model id:** `gemini-3.5-flash` (the `MODEL` const already in `worker/src/gemini.ts`).
- **Worker dir:** all commands run from `worker/` unless noted; tests live in `worker/test/`.
- **Cron schedule:** `"0 6 * * *"` (daily ~06:00 UTC during the pilot).
- **Dashboard route is private:** `GET /twin-insights` must never be added to the sitemap, `llms.txt`, or `CNAME`.

---

### Task 1: Insights data layer (`insights.ts`) + schema + in-memory D1 fake

**Files:**
- Create: `worker/src/insights.ts`
- Create: `worker/schema.sql`
- Create: `worker/test/fakeD1.ts`
- Create: `worker/test/insights.test.ts`
- Modify: `worker/src/index.ts:11-18` (add `INSIGHTS_DB` to `Env`)
- Modify: `worker/wrangler.toml` (add `[[d1_databases]]`)

**Interfaces:**
- Produces: `QuestionRow { id: number; ts: number; text: string; country: string | null; msg_count: number }`, `DigestRow { id: number; ts: number; markdown: string; n_questions: number }`.
- Produces: `logQuestion(db, { text, ts, country, msg_count }): Promise<void>`, `lastDigestTs(db): Promise<number>`, `questionsSince(db, ts): Promise<QuestionRow[]>`, `insertDigest(db, { ts, markdown, n_questions }): Promise<void>`, `purgeOld(db, cutoffTs): Promise<void>`, `latestDigest(db): Promise<DigestRow | null>`, `recentQuestions(db, limit): Promise<QuestionRow[]>`.
- Produces (test util): `fakeD1(handler?)` → `{ db: D1Database, calls: { sql: string; args: unknown[] }[] }`, where `handler(sql, args)` may return `{ results?: any[]; first?: any }`.

- [ ] **Step 1: Write `worker/schema.sql`**

```sql
-- Phase 12b digital-twin insights. Applied with:
--   wrangler d1 execute twin-insights --file=schema.sql
CREATE TABLE IF NOT EXISTS questions (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  ts        INTEGER NOT NULL,           -- unix seconds
  text      TEXT    NOT NULL,           -- verbatim latest user message
  country   TEXT,                       -- coarse, from req.cf.country (nullable)
  msg_count INTEGER NOT NULL            -- conversation length at log time
);
CREATE INDEX IF NOT EXISTS idx_questions_ts ON questions(ts);

CREATE TABLE IF NOT EXISTS digests (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  ts          INTEGER NOT NULL,         -- unix seconds of the run
  markdown    TEXT    NOT NULL,         -- LLM-generated themed summary
  n_questions INTEGER NOT NULL          -- how many questions this digest covered
);
```

- [ ] **Step 2: Write the in-memory D1 fake** — `worker/test/fakeD1.ts`

```ts
import { vi } from "vitest";

export interface RecordedStmt {
  sql: string;
  args: unknown[];
}

// Lightweight in-memory D1 fake: records every prepared statement + its bound
// args, and returns seeded results from an optional handler keyed on the SQL
// text. Mirrors how 12a tests the Gemini boundary by mocking fetch rather than
// calling the real service. Real D1 behaviour is exercised manually via
// `wrangler dev`'s local D1 (see README).
export function fakeD1(handler?: (sql: string, args: unknown[]) => { results?: any[]; first?: any }) {
  const calls: RecordedStmt[] = [];
  const db = {
    prepare(sql: string) {
      const rec: RecordedStmt = { sql, args: [] };
      const stmt = {
        bind(...args: unknown[]) {
          rec.args = args;
          return stmt;
        },
        async run() {
          calls.push(rec);
          return { success: true } as unknown as D1Result;
        },
        async all() {
          calls.push(rec);
          return { results: handler?.(rec.sql, rec.args)?.results ?? [] } as unknown as D1Result;
        },
        async first() {
          calls.push(rec);
          return (handler?.(rec.sql, rec.args)?.first ?? null) as unknown;
        },
      };
      return stmt as unknown as D1PreparedStatement;
    },
  } as unknown as D1Database;
  return { db, calls, _vi: vi };
}
```

- [ ] **Step 3: Write the failing test** — `worker/test/insights.test.ts`

```ts
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
```

- [ ] **Step 4: Run the test to verify it fails**

Run: `cd worker && npx vitest run test/insights.test.ts`
Expected: FAIL — `Cannot find module '../src/insights'`.

- [ ] **Step 5: Implement `worker/src/insights.ts`**

```ts
// Phase 12b insights data layer. Every function takes a D1Database so it can be
// unit-tested against the in-memory fake (test/fakeD1.ts); real D1 binding
// behaviour is exercised via `wrangler dev` local D1. Privacy invariant: the
// questions table stores ONLY ts/text/country/msg_count — never a raw IP, the
// twin's answer, or any fingerprint.

export interface QuestionRow {
  id: number;
  ts: number;
  text: string;
  country: string | null;
  msg_count: number;
}

export interface DigestRow {
  id: number;
  ts: number;
  markdown: string;
  n_questions: number;
}

export async function logQuestion(
  db: D1Database,
  q: { text: string; ts: number; country: string | null; msg_count: number },
): Promise<void> {
  await db
    .prepare("INSERT INTO questions (ts, text, country, msg_count) VALUES (?, ?, ?, ?)")
    .bind(q.ts, q.text, q.country, q.msg_count)
    .run();
}

export async function lastDigestTs(db: D1Database): Promise<number> {
  const row = await db.prepare("SELECT MAX(ts) AS ts FROM digests").first<{ ts: number | null }>();
  return row?.ts ?? 0;
}

export async function questionsSince(db: D1Database, ts: number): Promise<QuestionRow[]> {
  const { results } = await db
    .prepare("SELECT id, ts, text, country, msg_count FROM questions WHERE ts > ? ORDER BY ts ASC")
    .bind(ts)
    .all<QuestionRow>();
  return results ?? [];
}

export async function insertDigest(
  db: D1Database,
  d: { ts: number; markdown: string; n_questions: number },
): Promise<void> {
  await db
    .prepare("INSERT INTO digests (ts, markdown, n_questions) VALUES (?, ?, ?)")
    .bind(d.ts, d.markdown, d.n_questions)
    .run();
}

export async function purgeOld(db: D1Database, cutoffTs: number): Promise<void> {
  await db.prepare("DELETE FROM questions WHERE ts < ?").bind(cutoffTs).run();
}

export async function latestDigest(db: D1Database): Promise<DigestRow | null> {
  return await db
    .prepare("SELECT id, ts, markdown, n_questions FROM digests ORDER BY ts DESC LIMIT 1")
    .first<DigestRow>();
}

export async function recentQuestions(db: D1Database, limit: number): Promise<QuestionRow[]> {
  const { results } = await db
    .prepare("SELECT id, ts, text, country, msg_count FROM questions ORDER BY ts DESC LIMIT ?")
    .bind(limit)
    .all<QuestionRow>();
  return results ?? [];
}
```

- [ ] **Step 6: Add `INSIGHTS_DB` to the `Env` interface** — `worker/src/index.ts` (the `Env` block at lines 11-18)

```ts
export interface Env {
  RATE_KV: KVNamespace;
  INSIGHTS_DB: D1Database;
  GEMINI_API_KEY: string;
  TURNSTILE_SECRET_KEY: string;
  ALLOWED_ORIGIN: string;
  MONTHLY_CEILING: string;
  MAX_TOKENS: string;
}
```

- [ ] **Step 7: Add the D1 binding to `worker/wrangler.toml`**

Insert after the `[[kv_namespaces]]` block (the real `database_id` is filled in at deploy time by Task 8's `wrangler d1 create` — leave the placeholder until then):

```toml
# Phase 12b digital-twin insights store. The database_id is account-scoped (not a
# secret — same reasoning as the KV id) and is filled in from `wrangler d1 create`.
[[d1_databases]]
binding = "INSIGHTS_DB"
database_name = "twin-insights"
database_id = "PLACEHOLDER_RUN_WRANGLER_D1_CREATE"
```

- [ ] **Step 8: Run the tests to verify they pass**

Run: `cd worker && npx vitest run test/insights.test.ts`
Expected: PASS (8 tests).

- [ ] **Step 9: Commit**

```bash
git add worker/src/insights.ts worker/schema.sql worker/test/fakeD1.ts worker/test/insights.test.ts worker/src/index.ts worker/wrangler.toml
git commit -m "feat(12b): D1 insights data layer + schema + in-memory D1 fake"
```

---

### Task 2: Non-streaming Gemini call for the digest (`generateText`)

**Files:**
- Modify: `worker/src/gemini.ts` (add `generateText`)
- Modify: `worker/test/gemini.test.ts` (add `generateText` tests)

**Interfaces:**
- Consumes: the `MODEL` const already in `gemini.ts`.
- Produces: `generateText(apiKey: string, prompt: string, fetchImpl?: typeof fetch): Promise<string>` — one-shot, non-streaming completion; throws on a non-200.

- [ ] **Step 1: Write the failing test** — append to `worker/test/gemini.test.ts`

```ts
import { generateText } from "../src/gemini";
import { vi } from "vitest";

describe("generateText", () => {
  it("posts to :generateContent and returns the joined text", async () => {
    const fetchImpl = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => ({ candidates: [{ content: { parts: [{ text: "themes" }] } }] }),
    })) as unknown as typeof fetch;
    const out = await generateText("KEY", "prompt", fetchImpl);
    expect(out).toBe("themes");
    const [url] = (fetchImpl as any).mock.calls[0];
    expect(String(url)).toContain(":generateContent");
    expect(String(url)).not.toContain("streamGenerateContent");
  });

  it("throws on a non-200 upstream", async () => {
    const fetchImpl = vi.fn(async () => ({ ok: false, status: 429, json: async () => ({}) })) as unknown as typeof fetch;
    await expect(generateText("KEY", "p", fetchImpl)).rejects.toThrow();
  });

  it("returns empty string when no candidate text is present", async () => {
    const fetchImpl = vi.fn(async () => ({ ok: true, status: 200, json: async () => ({}) })) as unknown as typeof fetch;
    expect(await generateText("KEY", "p", fetchImpl)).toBe("");
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd worker && npx vitest run test/gemini.test.ts`
Expected: FAIL — `generateText` is not exported.

- [ ] **Step 3: Implement `generateText`** — append to `worker/src/gemini.ts`

```ts
// One-shot (non-streaming) completion used by the Phase 12b digest cron. Uses the
// :generateContent endpoint (not :streamGenerateContent) and returns the joined
// candidate text. Reuses the same free-tier MODEL + key as the chat path — no new
// credential or cost. Throws on a non-200 so the cron can skip writing a digest.
export async function generateText(
  apiKey: string,
  prompt: string,
  fetchImpl: typeof fetch = fetch,
): Promise<string> {
  const url =
    `https://generativelanguage.googleapis.com/v1beta/models/${MODEL}:generateContent` +
    `?key=${apiKey}`;
  const res = await fetchImpl(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      contents: [{ role: "user", parts: [{ text: prompt }] }],
      generationConfig: { thinkingConfig: { thinkingLevel: "low" } },
    }),
  });
  if (!res.ok) throw new Error(`gemini generateText upstream ${res.status}`);
  const data = (await res.json()) as any;
  const parts = data?.candidates?.[0]?.content?.parts;
  if (!Array.isArray(parts)) return "";
  return parts.map((p: any) => (typeof p?.text === "string" ? p.text : "")).join("");
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd worker && npx vitest run test/gemini.test.ts`
Expected: PASS (existing 4 + new 3).

- [ ] **Step 5: Commit**

```bash
git add worker/src/gemini.ts worker/test/gemini.test.ts
git commit -m "feat(12b): non-streaming generateText for the digest cron"
```

---

### Task 3: Digest orchestration (`digest.ts`)

**Files:**
- Create: `worker/src/digest.ts`
- Create: `worker/test/digest.test.ts`

**Interfaces:**
- Consumes: `lastDigestTs`, `questionsSince`, `insertDigest`, `purgeOld`, `QuestionRow` (Task 1); `generateText` (Task 2).
- Produces: `buildDigestPrompt(rows: QuestionRow[]): string`; `runDigest(db: D1Database, apiKey: string, now: number, fetchImpl?: typeof fetch): Promise<{ digested: number }>`.
- Produces: `RETENTION_SECONDS = 30 * 86400` (exported, reused nowhere else but asserted in tests).

- [ ] **Step 1: Write the failing test** — `worker/test/digest.test.ts`

```ts
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd worker && npx vitest run test/digest.test.ts`
Expected: FAIL — `Cannot find module '../src/digest'`.

- [ ] **Step 3: Implement `worker/src/digest.ts`**

```ts
import {
  lastDigestTs,
  questionsSince,
  insertDigest,
  purgeOld,
  type QuestionRow,
} from "./insights";
import { generateText } from "./gemini";

// Raw question rows are ephemeral input to the digest; the digest is the durable
// artifact. 30-day TTL bounds any leak window and aligns retention with use.
export const RETENTION_SECONDS = 30 * 86400;

// PURE: assemble the "group these into themes" prompt over a set of question rows.
export function buildDigestPrompt(rows: QuestionRow[]): string {
  const list = rows.map((r) => `- ${r.text}`).join("\n");
  return (
    "You are summarising questions visitors asked a personal CV chatbot. " +
    "Group them into a few short themes. For each theme, give a one-line heading " +
    "and how many questions fell under it. Output concise Markdown, nothing else.\n\n" +
    "Questions:\n" +
    list
  );
}

// Daily cron body: digest new questions since the last run (skip the LLM entirely
// when there are none), then purge questions older than the retention window. The
// purge ALWAYS runs, even on an empty round.
export async function runDigest(
  db: D1Database,
  apiKey: string,
  now: number,
  fetchImpl: typeof fetch = fetch,
): Promise<{ digested: number }> {
  const since = await lastDigestTs(db);
  const rows = await questionsSince(db, since);
  if (rows.length > 0) {
    const markdown = await generateText(apiKey, buildDigestPrompt(rows), fetchImpl);
    await insertDigest(db, { ts: now, markdown, n_questions: rows.length });
  }
  await purgeOld(db, now - RETENTION_SECONDS);
  return { digested: rows.length };
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd worker && npx vitest run test/digest.test.ts`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add worker/src/digest.ts worker/test/digest.test.ts
git commit -m "feat(12b): digest orchestration (skip-on-empty + 30d purge)"
```

---

### Task 4: Dashboard HTML renderer (`dashboard.ts`)

**Files:**
- Create: `worker/src/dashboard.ts`
- Create: `worker/test/dashboard.test.ts`

**Interfaces:**
- Consumes: `DigestRow`, `QuestionRow` (Task 1).
- Produces: `escapeHtml(s: string): string`; `renderDashboard(data: { digest: DigestRow | null; monthCount: number; ceiling: number; questions: QuestionRow[] }): string`.

- [ ] **Step 1: Write the failing test** — `worker/test/dashboard.test.ts`

```ts
import { describe, expect, it } from "vitest";
import { escapeHtml, renderDashboard } from "../src/dashboard";

describe("escapeHtml", () => {
  it("escapes HTML-significant characters", () => {
    expect(escapeHtml(`<script>"&'`)).toBe("&lt;script&gt;&quot;&amp;&#39;");
  });
});

describe("renderDashboard", () => {
  const base = {
    digest: { id: 1, ts: 1_700_000_000, markdown: "## Theme A\n3 questions", n_questions: 3 },
    monthCount: 142,
    ceiling: 5000,
    questions: [
      { id: 2, ts: 1_700_000_500, text: "what is your salary?", country: "DE", msg_count: 2 },
    ],
  };

  it("shows the usage counter as N / ceiling and labels it a rolling window", () => {
    const html = renderDashboard(base);
    expect(html).toContain("142");
    expect(html).toContain("5000");
    expect(html.toLowerCase()).toContain("current window");
  });

  it("renders the latest digest markdown in a pre block", () => {
    const html = renderDashboard(base);
    expect(html).toContain("<pre");
    expect(html).toContain("Theme A");
  });

  it("escapes untrusted question text (no raw script tag survives)", () => {
    const html = renderDashboard({
      ...base,
      questions: [{ id: 3, ts: 1, text: "<script>alert(1)</script>", country: null, msg_count: 1 }],
    });
    expect(html).not.toContain("<script>alert(1)</script>");
    expect(html).toContain("&lt;script&gt;");
  });

  it("handles no digest yet without throwing", () => {
    const html = renderDashboard({ ...base, digest: null });
    expect(html.toLowerCase()).toContain("no digest");
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd worker && npx vitest run test/dashboard.test.ts`
Expected: FAIL — `Cannot find module '../src/dashboard'`.

- [ ] **Step 3: Implement `worker/src/dashboard.ts`**

```ts
import type { DigestRow, QuestionRow } from "./insights";

// Visitor question text is untrusted — escape before rendering into the page.
export function escapeHtml(s: string): string {
  return s.replace(
    /[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!,
  );
}

function fmtTime(ts: number): string {
  return new Date(ts * 1000).toISOString().replace("T", " ").slice(0, 16) + " UTC";
}

// Self-contained, server-rendered dashboard. No Astro, no markdown dependency:
// the digest markdown is shown verbatim in a <pre> (honest, zero new dep). This
// route is private (Cloudflare Access) and intentionally off the public site
// surface — never in the sitemap / llms.txt / CNAME.
export function renderDashboard(data: {
  digest: DigestRow | null;
  monthCount: number;
  ceiling: number;
  questions: QuestionRow[];
}): string {
  const { digest, monthCount, ceiling, questions } = data;

  const digestBlock = digest
    ? `<pre style="white-space:pre-wrap;background:#11151d;border:1px solid #272d39;border-radius:10px;padding:1rem;color:#e8eaed">${escapeHtml(
        digest.markdown,
      )}</pre><p style="color:#99a0ac;font-size:.85rem">covering ${digest.n_questions} question(s), generated ${fmtTime(
        digest.ts,
      )}</p>`
    : `<p style="color:#99a0ac">No digest yet — the cron will write the first one on its next run.</p>`;

  const rows = questions
    .map(
      (q) =>
        `<tr><td style="padding:6px 10px;border-bottom:1px solid #272d39">${escapeHtml(
          q.text,
        )}</td><td style="padding:6px 10px;border-bottom:1px solid #272d39;color:#99a0ac">${escapeHtml(
          q.country ?? "—",
        )}</td><td style="padding:6px 10px;border-bottom:1px solid #272d39;color:#99a0ac">${fmtTime(
          q.ts,
        )}</td></tr>`,
    )
    .join("");

  return `<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="robots" content="noindex,nofollow">
<title>Twin insights</title>
<style>body{margin:0;background:#0c0e13;color:#e8eaed;font:16px/1.6 -apple-system,Segoe UI,Roboto,sans-serif;padding:2rem;max-width:900px;margin:0 auto}h1{font-size:1.3rem}table{width:100%;border-collapse:collapse;font-size:.9rem}th{text-align:left;padding:6px 10px;color:#99a0ac;border-bottom:1px solid #272d39}</style>
</head><body>
<h1>🤖 Twin insights</h1>
<p>Usage this <strong>current window</strong> (rolling ~31-day): <strong>${monthCount}</strong> / ${ceiling}</p>
<h2>Latest digest</h2>
${digestBlock}
<h2>Recent questions (${questions.length})</h2>
<table><thead><tr><th>Question</th><th>Country</th><th>Time</th></tr></thead><tbody>${rows}</tbody></table>
</body></html>`;
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd worker && npx vitest run test/dashboard.test.ts`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add worker/src/dashboard.ts worker/test/dashboard.test.ts
git commit -m "feat(12b): self-contained dashboard HTML renderer"
```

---

### Task 5: Logging path in the `fetch` handler (`ctx.waitUntil`)

**Files:**
- Modify: `worker/src/index.ts` (add `ctx` arg; log after counters bump)
- Modify: `worker/test/handler.test.ts` (add `INSIGHTS_DB` to env, a `makeCtx` helper, update existing call sites, add logging assertions)

**Interfaces:**
- Consumes: `logQuestion` (Task 1); `Env.INSIGHTS_DB` (Task 1).
- Produces: new `fetch(req, env, ctx)` signature. Logging happens only after every guard passes, via `ctx.waitUntil(logQuestion(...).catch(() => {}))`.

- [ ] **Step 1: Update the test harness** — `worker/test/handler.test.ts`

Add the D1 fake import and a `makeCtx` helper near the top (after the existing `fakeKv`):

```ts
import { fakeD1 } from "./fakeD1";

// ExecutionContext fake: collect the promises passed to waitUntil so tests can
// await the fire-and-forget logging before asserting on it.
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
```

Update `makeEnv` to include the D1 binding (accept an optional fake so tests can inspect it):

```ts
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
```

- [ ] **Step 2: Update every existing `worker.fetch(...)` call site in `handler.test.ts`**

Each existing call `worker.fetch(req, env)` / `worker.fetch(req, makeEnv())` becomes `worker.fetch(req, env, makeCtx().ctx)`. For example:

```ts
const res = await worker.fetch(req, makeEnv(), makeCtx().ctx);
```

Apply to all 14 existing `worker.fetch` calls in the file.

- [ ] **Step 3: Write the failing logging tests** — append to the `describe("fetch handler", …)` block

```ts
it("logs exactly one question row on the happy path (text/country/msg_count, no IP)", async () => {
  stubFetch({ geminiOk: true, geminiStatus: 200 });
  const { db, calls } = fakeD1();
  const { ctx, promises } = makeCtx();
  const body = JSON.stringify({
    messages: [
      { role: "user", content: "first" },
      { role: "assistant", content: "reply" },
      { role: "user", content: "what is your salary?" },
    ],
    turnstileToken: "tok",
  });
  await worker.fetch(post(ALLOWED, body), makeEnv(fakeKv(), db), ctx);
  await Promise.all(promises); // flush fire-and-forget logging

  const insert = calls.find((c) => c.sql.includes("INSERT INTO questions"));
  expect(insert).toBeTruthy();
  expect(insert!.sql).not.toMatch(/ip/i);
  // args: [ts, text, country, msg_count] — latest user message + length
  expect(insert!.args[1]).toBe("what is your salary?");
  expect(insert!.args[3]).toBe(3);
});

it("does NOT log on a rejected request (bad shape → 400)", async () => {
  stubFetch({});
  const { db, calls } = fakeD1();
  const { ctx, promises } = makeCtx();
  const res = await worker.fetch(post(ALLOWED, "not json {"), makeEnv(fakeKv(), db), ctx);
  await Promise.all(promises);
  expect(res.status).toBe(400);
  expect(calls.find((c) => c.sql.includes("INSERT INTO questions"))).toBeUndefined();
});

it("does NOT log when the monthly ceiling is hit (503)", async () => {
  stubFetch({});
  const { db, calls } = fakeD1();
  const { ctx, promises } = makeCtx();
  const res = await worker.fetch(post(ALLOWED, validBody), makeEnv(fakeKv({ month: "5000" }), db), ctx);
  await Promise.all(promises);
  expect(res.status).toBe(503);
  expect(calls.find((c) => c.sql.includes("INSERT INTO questions"))).toBeUndefined();
});
```

- [ ] **Step 4: Run the tests to verify they fail**

Run: `cd worker && npx vitest run test/handler.test.ts`
Expected: FAIL — `fetch` ignores the third arg / `ctx.waitUntil` is undefined / no INSERT recorded.

- [ ] **Step 5: Add the import and `ctx` arg, and log after the counters bump** — `worker/src/index.ts`

Add to the imports at the top:

```ts
import { logQuestion } from "./insights";
```

Change the handler signature (line ~71):

```ts
  async fetch(req: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
```

Immediately **after** `await bumpCounters(env.RATE_KV, ip, counters);` (line ~121) and **before** `const systemText = …`, insert:

```ts
    // Phase 12b: fire-and-forget log of the latest user question, AFTER every guard
    // (Turnstile + bounds + rate/ceiling) has passed — only real, human, allowed
    // questions are captured. ctx.waitUntil keeps it off the response path so a D1
    // error can never block or break the chat stream. Privacy: text/ts/country/
    // msg_count only — never the IP, never the answer.
    const latest = body.messages[body.messages.length - 1];
    ctx.waitUntil(
      logQuestion(env.INSIGHTS_DB, {
        text: latest.content,
        ts: Math.floor(Date.now() / 1000),
        country: (req as { cf?: { country?: string } }).cf?.country ?? null,
        msg_count: body.messages.length,
      }).catch(() => {}),
    );
```

- [ ] **Step 6: Run the full worker test suite to verify it passes**

Run: `cd worker && npx vitest run`
Expected: PASS — all existing tests (now 3-arg) plus the 3 new logging tests.

- [ ] **Step 7: Commit**

```bash
git add worker/src/index.ts worker/test/handler.test.ts
git commit -m "feat(12b): fire-and-forget question logging after the guard gate"
```

---

### Task 6: `GET /twin-insights` route + Cloudflare Access guard

**Files:**
- Modify: `worker/src/index.ts` (add the GET route before the POST-only guard)
- Modify: `worker/test/handler.test.ts` (add dashboard-route tests)

**Interfaces:**
- Consumes: `latestDigest`, `recentQuestions` (Task 1); `renderDashboard` (Task 4); `finite` (already in `index.ts`).
- Produces: a `GET /twin-insights` branch returning `text/html`, 403 if the `Cf-Access-Authenticated-User-Email` header is absent.

- [ ] **Step 1: Write the failing tests** — append to `handler.test.ts`

```ts
function getInsights(headers: Record<string, string> = {}): Request {
  return new Request("https://twin.example/twin-insights", { method: "GET", headers });
}

describe("GET /twin-insights", () => {
  it("403 when the Cf-Access-Authenticated-User-Email header is absent", async () => {
    stubFetch({});
    const res = await worker.fetch(getInsights(), makeEnv(), makeCtx().ctx);
    expect(res.status).toBe(403);
  });

  it("200 text/html with the dashboard when the Access header is present", async () => {
    stubFetch({});
    const db = fakeD1((sql) => {
      if (sql.includes("FROM digests")) return { first: { id: 1, ts: 1, markdown: "## T", n_questions: 1 } };
      if (sql.includes("FROM questions")) return { results: [{ id: 2, ts: 2, text: "hi", country: "DE", msg_count: 1 }] };
      return {};
    }).db;
    const env = makeEnv(fakeKv({ month: "12" }), db);
    const res = await worker.fetch(
      getInsights({ "Cf-Access-Authenticated-User-Email": "jin@example.com" }),
      env,
      makeCtx().ctx,
    );
    expect(res.status).toBe(200);
    expect(res.headers.get("content-type")).toContain("text/html");
    const html = await res.text();
    expect(html).toContain("Twin insights");
    expect(html).toContain("12"); // usage counter
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd worker && npx vitest run test/handler.test.ts`
Expected: FAIL — the route falls through to the POST-only 403 for the GET case (and the 200 case never returns HTML).

- [ ] **Step 3: Add the imports and the route** — `worker/src/index.ts`

Add to the imports:

```ts
import { latestDigest, recentQuestions, logQuestion } from "./insights";
import { renderDashboard } from "./dashboard";
```

(Combine with the `logQuestion` import added in Task 5 — the line becomes the `latestDigest, recentQuestions, logQuestion` form above.)

Insert this branch **immediately after** the `if (req.method === "OPTIONS") …` line and **before** the `if (req.method !== "POST" || …)` guard:

```ts
    // Phase 12b private dashboard. Same-origin top-level navigation (no Origin
    // allowlist applies here, unlike POST /). Cloudflare Access authenticates at
    // the edge; this header check is cheap defense-in-depth so the route stays
    // closed even if the Access policy is misconfigured or removed.
    const url = new URL(req.url);
    if (req.method === "GET" && url.pathname === "/twin-insights") {
      if (!req.headers.get("Cf-Access-Authenticated-User-Email"))
        return new Response("forbidden", { status: 403 });
      const monthCount = Number((await env.RATE_KV.get("month")) ?? 0);
      const [digest, questions] = await Promise.all([
        latestDigest(env.INSIGHTS_DB),
        recentQuestions(env.INSIGHTS_DB, 200),
      ]);
      const html = renderDashboard({
        digest,
        monthCount,
        ceiling: finite(env.MONTHLY_CEILING, 5000),
        questions,
      });
      return new Response(html, {
        status: 200,
        headers: { "content-type": "text/html; charset=utf-8" },
      });
    }
```

- [ ] **Step 4: Run the full suite to verify it passes**

Run: `cd worker && npx vitest run`
Expected: PASS — including the 2 new dashboard-route tests.

- [ ] **Step 5: Commit**

```bash
git add worker/src/index.ts worker/test/handler.test.ts
git commit -m "feat(12b): GET /twin-insights dashboard route + Access guard"
```

---

### Task 7: `scheduled()` cron export + Cron Trigger config

**Files:**
- Modify: `worker/src/index.ts` (add `scheduled` to the default export)
- Modify: `worker/wrangler.toml` (add `[triggers] crons`)
- Create: `worker/test/scheduled.test.ts`

**Interfaces:**
- Consumes: `runDigest` (Task 3).
- Produces: `scheduled(event: ScheduledController, env: Env, ctx: ExecutionContext): Promise<void>` on the default export.

- [ ] **Step 1: Write the failing test** — `worker/test/scheduled.test.ts`

```ts
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import worker, { type Env } from "../src/index";
import { fakeD1 } from "./fakeD1";
import { fakeKv } from "./fakeKv"; // see Step 1a

function makeEnv(db: D1Database): Env {
  return {
    RATE_KV: fakeKv(),
    INSIGHTS_DB: db,
    GEMINI_API_KEY: "k",
    TURNSTILE_SECRET_KEY: "s",
    ALLOWED_ORIGIN: "https://jinholee.is-a.dev",
    MONTHLY_CEILING: "5000",
    MAX_TOKENS: "700",
  };
}

function makeCtx() {
  const promises: Promise<unknown>[] = [];
  return {
    ctx: { waitUntil: (p: Promise<unknown>) => promises.push(p), passThroughOnException: () => {} } as unknown as ExecutionContext,
    promises,
  };
}

beforeEach(() => vi.restoreAllMocks());
afterEach(() => vi.unstubAllGlobals());

describe("scheduled (digest cron)", () => {
  it("runs the digest: reads questions, calls Gemini once, writes a digest, purges", async () => {
    const db = fakeD1((sql) => {
      if (sql.includes("MAX(ts)")) return { first: { ts: 0 } };
      if (sql.includes("WHERE ts > ?")) return { results: [{ id: 1, ts: 5, text: "q", country: "DE", msg_count: 1 }] };
      return {};
    });
    const fetchMock = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => ({ candidates: [{ content: { parts: [{ text: "## Theme" }] } }] }),
    }));
    vi.stubGlobal("fetch", fetchMock);

    const { ctx, promises } = makeCtx();
    await worker.scheduled!({ cron: "0 6 * * *", scheduledTime: 0 } as any, makeEnv(db.db), ctx);
    await Promise.all(promises);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(db.calls.find((c) => c.sql.includes("INSERT INTO digests"))).toBeTruthy();
    expect(db.calls.find((c) => c.sql.includes("DELETE FROM questions"))).toBeTruthy();
  });
});
```

- [ ] **Step 1a: Extract the KV fake into a shared helper** — `worker/test/fakeKv.ts`

The KV fake currently lives inline in `handler.test.ts`. Move it to a shared module so both test files use one copy (DRY):

```ts
import { vi } from "vitest";

// In-memory KV stub: enough of the KVNamespace surface for read/bump counters.
export function fakeKv(initial: Record<string, string> = {}) {
  const store = new Map<string, string>(Object.entries(initial));
  return {
    get: vi.fn(async (key: string) => store.get(key) ?? null),
    put: vi.fn(async (key: string, value: string) => {
      store.set(key, value);
    }),
  } as unknown as KVNamespace;
}
```

Then in `handler.test.ts`, delete the inline `fakeKv` definition and add `import { fakeKv } from "./fakeKv";`.

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd worker && npx vitest run test/scheduled.test.ts`
Expected: FAIL — `worker.scheduled` is undefined.

- [ ] **Step 3: Add the `scheduled` export** — `worker/src/index.ts`

Add to the imports:

```ts
import { runDigest } from "./digest";
```

Add a `scheduled` method to the default export object, as a sibling of `fetch` (after the `fetch` method, inside the same `export default { … }`):

```ts
  // Phase 12b daily digest cron (wired via [triggers] crons in wrangler.toml).
  // Reuses the existing free-tier GEMINI_API_KEY; skip-on-empty + 30d purge live
  // in runDigest. waitUntil keeps the worker alive until the digest completes.
  async scheduled(_event: ScheduledController, env: Env, ctx: ExecutionContext): Promise<void> {
    ctx.waitUntil(runDigest(env.INSIGHTS_DB, env.GEMINI_API_KEY, Math.floor(Date.now() / 1000)).then(() => {}));
  },
```

- [ ] **Step 4: Add the Cron Trigger to `worker/wrangler.toml`**

Append at the end of the file:

```toml
# Phase 12b digest cron — daily ~06:00 UTC during the pilot (change to weekly later).
[triggers]
crons = ["0 6 * * *"]
```

- [ ] **Step 5: Run the full suite to verify it passes**

Run: `cd worker && npx vitest run`
Expected: PASS — all suites including `scheduled.test.ts`.

- [ ] **Step 6: Commit**

```bash
git add worker/src/index.ts worker/wrangler.toml worker/test/scheduled.test.ts worker/test/fakeKv.ts worker/test/handler.test.ts
git commit -m "feat(12b): daily digest scheduled() cron + trigger config"
```

---

### Task 8: Deploy wiring + docs (README, CLAUDE.md, manual steps)

**Files:**
- Modify: `worker/README.md` (D1 create, schema apply, cron, Access, dashboard route)
- Modify: `worker/wrangler.toml` (fill the real `database_id`)
- Modify: `CLAUDE.md` (phasing table row + conventions)

This task has no automated test — it is deploy enablement + docs. Verification is `wrangler` running locally and the full suite still green.

- [ ] **Step 1: Create the D1 database and apply the schema**

Run (from `worker/`):

```bash
npx wrangler d1 create twin-insights
```

Copy the printed `database_id` into `worker/wrangler.toml`'s `[[d1_databases]]` block (replacing `PLACEHOLDER_RUN_WRANGLER_D1_CREATE`). Then apply the schema to both local and remote D1:

```bash
npx wrangler d1 execute twin-insights --local --file=schema.sql
npx wrangler d1 execute twin-insights --remote --file=schema.sql
```

- [ ] **Step 2: Smoke-test locally with `wrangler dev`**

```bash
cd .. && just worker-dev
```

In another shell, confirm the dashboard route requires the Access header (Access runs at the edge, not locally, so the defense-in-depth guard is what you exercise here):

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8787/twin-insights
# expected: 403
curl -s -H "Cf-Access-Authenticated-User-Email: jin@example.com" http://localhost:8787/twin-insights | head -5
# expected: HTML starting with <!doctype html> … "Twin insights"
```

Invoke the cron handler against local D1:

```bash
curl -s "http://localhost:8787/__scheduled?cron=0+6+*+*+*"
# expected: 200 (no body); local D1 questions table is purged, a digest row written if any questions existed
```

- [ ] **Step 3: Update `worker/README.md`**

Add a **One-time setup** step (after the existing Turnstile step) for D1:

```markdown
6. Create the insights D1 database and apply the schema (the `database_id` is
   account-scoped, not a secret — safe to commit in `wrangler.toml`):
   ```bash
   npx wrangler d1 create twin-insights      # paste the id into wrangler.toml
   npx wrangler d1 execute twin-insights --remote --file=schema.sql
   ```
7. In the Cloudflare dashboard, put **Cloudflare Access** (Zero Trust → Access →
   Applications) in front of the deployed Worker's `/twin-insights` path, with a
   policy allowing only your Google login. No token or secret goes in git.
```

Replace the **"No operator usage visibility"** bullet under *Known limitations* with:

```markdown
- **Operator dashboard.** `GET /twin-insights` (Phase 12b) shows the latest digest,
  a rolling-window usage counter, and recent questions. It is gated by Cloudflare
  Access plus a `Cf-Access-Authenticated-User-Email` header check, and is never part
  of the public site (absent from sitemap / llms.txt / CNAME). A daily Cron Trigger
  (`scheduled()`) writes the digest and purges questions older than 30 days.
```

- [ ] **Step 4: Update the `CLAUDE.md` phasing table**

Add this row to the phasing table, immediately after the Phase 12a row:

```markdown
| 12b | Digital-twin insights (D1 question log + daily Gemini digest + Cloudflare-Access dashboard) | ✅ Done (merged <FILL AT MERGE>); free-tier D1 + Cron Triggers; verbatim questions, 30-day purge, no IP |
```

Add to the **Conventions** list (under the existing Worker/deploy bullet) a note:

```markdown
- **Worker now uses D1 + a Cron Trigger.** Phase 12b adds the `INSIGHTS_DB` D1 binding
  (question log + digests; schema in `worker/schema.sql`, applied via `wrangler d1
  execute`), a daily `scheduled()` digest cron (`[triggers] crons`), and a private
  `GET /twin-insights` HTML route gated by Cloudflare Access + a
  `Cf-Access-Authenticated-User-Email` guard. That route is intentionally excluded
  from the public site surface (sitemap / llms.txt / CNAME). D1 + Cron are free-tier;
  the digest reuses the existing `GEMINI_API_KEY`. D1 logging is fire-and-forget via
  `ctx.waitUntil` — it never blocks the chat stream.
```

- [ ] **Step 5: Run the full worker suite + lint one last time**

```bash
cd worker && npx vitest run
```

Expected: PASS (all suites). Then from repo root run the repo checks that apply:

```bash
cd .. && just validate
```

Expected: green (no content changes, but confirms nothing regressed).

- [ ] **Step 6: Commit**

```bash
git add worker/README.md worker/wrangler.toml CLAUDE.md
git commit -m "docs(12b): D1/cron/Access setup + dashboard; CLAUDE.md phasing row"
```

---

## Self-Review

**1. Spec coverage** — every spec section maps to a task:
- Privacy stance (no IP, verbatim, 30-day TTL, Access-gated) → Task 1 (schema + `logQuestion` columns), Task 3 (`RETENTION_SECONDS` purge), Task 5 (logging fields + PII test), Task 6 (Access guard).
- D1 logging in request path → Task 5 (`ctx.waitUntil` after guards; rejects not logged).
- Digest cron + retention purge → Task 3 (`runDigest`, skip-on-empty) + Task 7 (`scheduled` + trigger).
- Digest LLM = Gemini free tier → Task 2 (`generateText`, reuses `MODEL` + key).
- Dashboard (digest + rolling counter + questions) + router + Access → Task 4 (renderer, "current window" label) + Task 6 (route + 403 guard).
- New binding `INSIGHTS_DB`, committed db id → Task 1 (Env + wrangler) + Task 8 (`wrangler d1 create`).
- Testing approach (plain vitest + in-memory D1 fake, no pool-workers) → Task 1 (`fakeD1`), reused in Tasks 3/5/6/7.
- Ops (schema.sql, d1 execute, Access policy, `/__scheduled`, Pages unchanged) → Task 8.
- CLAUDE.md row → Task 8.

**2. Placeholder scan** — the only intentional placeholder is `database_id = "PLACEHOLDER_RUN_WRANGLER_D1_CREATE"` (Task 1), filled in Task 8 Step 1; and `<FILL AT MERGE>` for the CLAUDE.md merge commit. Both are explicitly resolved. No "TODO"/"add error handling"/"similar to Task N" left.

**3. Type consistency** — `QuestionRow`/`DigestRow` defined once in Task 1 and imported everywhere; `logQuestion`, `lastDigestTs`, `questionsSince`, `insertDigest`, `purgeOld`, `latestDigest`, `recentQuestions`, `generateText`, `buildDigestPrompt`, `runDigest`, `renderDashboard`, `escapeHtml`, `fakeD1`, `fakeKv` names used identically across tasks. `fetch(req, env, ctx)` and `scheduled(event, env, ctx)` signatures consistent. `RETENTION_SECONDS` defined in Task 3, asserted in its test.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-06-17-phase-12b-twin-insights.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

**Which approach?**
