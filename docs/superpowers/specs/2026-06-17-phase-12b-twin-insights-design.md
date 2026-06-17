# Phase 12b — Digital Twin insights (design)

**Date:** 2026-06-17
**Issue:** [#82](https://github.com/Jin-HoMLee/jin-ho-lee-cv/issues/82)
**Depends on:** Phase 12a (chat MVP, merged `7b6dfaa`)
**Supersedes:** the "Twin insights" section of
`docs/superpowers/specs/2026-06-15-phase-12-digital-twin-design.md`, which predates two
decisions made since (the Gemini backend pivot and the Cloudflare Access auth choice).

## What this is

Phase 12b answers one question for Jin-Ho: **what are people actually asking the twin?**
It logs each visitor question, generates a periodic themed digest, and surfaces both —
plus a live usage counter — on a private, auth-gated dashboard. It is a pure extension of
the existing 12a Worker: no new Cloudflare service beyond D1 + Cron Triggers, both free-tier.

## Out of scope (deliberately)

- **Email/push delivery** of the digest — the dashboard is pull, not push.
- **Lead capture** (visitor opts in to leave contact details) — banked as a future
  **Phase 12c**, which will build on 12b's D1 + Access-gated dashboard foundation.
- Per-visitor session memory; multilingual chat.

## Privacy stance (the framing decision)

Jin-Ho is in Germany, so GDPR is the governing frame, and free text a visitor types is
personal data. Rather than treat compliance as a burden, the design **minimizes so the
question is moot**:

- **No raw IP, ever** (IP is personal data per CJEU *Breyer*; matches the GoatCounter stance).
- **Verbatim question text** is stored (faithful to "what did people ask" — no lossy regex
  redaction, which breeds false confidence by missing PII it wasn't written to catch).
- **30-day retention TTL.** The *digest* is the durable artifact; raw question rows are
  ephemeral input whose standalone value decays once folded into a digest. A short TTL is
  therefore aligned with how the data is actually used, not a compromise — and it bounds any
  leak window to ~a month. The daily cron runs the purge.
- **Access-gated** (see §4) — raw questions never leave a login-protected surface.
- Disclosure already shipped in the 12a preamble ("chats may be reviewed to improve the
  twin"), covering the transparency/legitimate-interest angle.
- **Speculative over-collection is rejected on principle.** The test is not "could this data
  ever be useful" but "what decision would it change." Coarse country + turn count + question
  text serve the purpose; anything more is unused liability. (Consented contact data is the
  *opposite* case — that is exactly what 12c is for, with its own opt-in.)

## Architecture

12b adds three capabilities to the **existing** Worker (`worker/src/index.ts`), not a new
service:

1. **D1 logging** in the request path.
2. A **`scheduled()` cron** for the digest + retention purge.
3. A **`GET /twin-insights`** HTML dashboard route behind Cloudflare Access.

### New binding

A D1 database `INSIGHTS_DB`, added to `Env` and `wrangler.toml` (`[[d1_databases]]`).

### Schema

```sql
CREATE TABLE questions (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  ts        INTEGER NOT NULL,           -- unix seconds
  text      TEXT    NOT NULL,           -- verbatim latest user message
  country   TEXT,                       -- coarse, from req.cf.country (nullable)
  msg_count INTEGER NOT NULL            -- conversation length at log time
);
CREATE INDEX idx_questions_ts ON questions(ts);

CREATE TABLE digests (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  ts          INTEGER NOT NULL,         -- unix seconds of the run
  markdown    TEXT    NOT NULL,         -- LLM-generated themed summary
  n_questions INTEGER NOT NULL          -- how many questions this digest covered
);
```

No IP, no answer text, no fingerprint. Only the verbatim question, coarse `country`, and the
turn count. Deliberately **not** logging the twin's answer keeps the store minimal — the
question theme is the signal; the answer is reconstructable in spirit and adds only volume.

## 1. Logging path

In the existing `fetch` handler, **after** a request clears every guard (Turnstile +
conversation bounds + rate/ceiling counters) and as the stream starts, log the latest user
message to D1 via **`ctx.waitUntil(...)`** — fire-and-forget, so a D1 error can never block
or break the chat stream. This requires adding the `ctx: ExecutionContext` argument to the
`fetch` signature (currently `fetch(req, env)`).

- **Logged:** latest user message text (verbatim), `ts`, `country` (`req.cf?.country`),
  `msg_count` (`messages.length`).
- **Not logged:** rejected requests (failed Turnstile, over-limit, bad shape) — only real,
  human, allowed questions are captured. The log call sits after the same guard gate that
  the chat answer does.

## 2. Digest cron + retention purge

A `scheduled()` handler, wired via a Cloudflare Cron Trigger (`[triggers] crons` in
`wrangler.toml`; **daily during the pilot**, trivially changed to weekly later). Each run:

1. Reads questions since the last digest: `SELECT … WHERE ts > <last digest ts>` (or all if
   none yet).
2. **If there are any**, calls **Gemini** (`gemini.ts`, same `GEMINI_API_KEY` secret — no new
   credential or cost; one tiny summarization call, well within the free quota) with a
   "group these questions into themes" prompt, and writes one `digests` row.
3. Runs the retention purge: `DELETE FROM questions WHERE ts < <now − 30 days>`.

If zero new questions, it **skips the LLM call** — no empty digests, no wasted quota. The
purge still runs.

**Digest LLM = Gemini free tier (`gemini-3.5-flash`).** The original Phase 12 spec named
Claude/Haiku, but the `ANTHROPIC_API_KEY` was deleted when 12a pivoted to Gemini; reusing the
Gemini path is the only no-new-cost, no-new-credential option.

## 3. Dashboard & auth

`GET /twin-insights` returns a **self-contained, server-rendered HTML string** from the
Worker (no Astro; **never** in the sitemap, `llms.txt`, or `CNAME` — it is not part of the
public site). The Worker grows a tiny **method + path router**:

- `POST /` → chat (unchanged).
- `GET /twin-insights` → dashboard.
- else → 404.

The page shows:

- **Latest digest** (rendered markdown) up top.
- **Live monthly usage counter** — "N / `MONTHLY_CEILING`" — read from the existing KV `month`
  key ÷ `MONTHLY_CEILING`. This is the operator cap-visibility the 12a spec deferred here; its
  natural home is this already-protected, storage-backed page. (Honest labelling: the KV `month`
  counter is a *rolling ~31-day* window from first write, not a calendar month — a documented 12a
  tradeoff — so the dashboard says "current window," not "this calendar month.")
- **Browsable recent questions** — a table of `text` + `country` + time.

### Auth = Cloudflare Access (Zero Trust)

Configured in the Cloudflare dashboard in front of the route, gated by Jin-Ho's Google login —
**zero token in code**. This deliberately replaces the original spec's `?token=…` query string,
which leaks via server logs, `Referer` headers, and browser history.

As cheap **defense-in-depth**, the Worker also asserts the `Cf-Access-Authenticated-User-Email`
header is present on `GET /twin-insights` and returns 403 if not — so the route is never exposed
even if an Access policy is misconfigured or removed. (This is a guard, not the primary control;
Access does the real authentication at the edge.)

The dashboard is a same-origin top-level navigation, so it needs no CORS handling; the existing
`POST /` origin-locking is unchanged.

## 4. Testing

Vitest in `worker/`, reusing the **existing 12a setup** — plain `vitest` with the `md-stub`
plugin and mocked `fetch`. 12a does **not** use `@cloudflare/vitest-pool-workers`/miniflare, and
12b will **not** add it: that would be a heavy new dependency against 12a's "pure functions +
mocked boundaries" philosophy. Instead, D1 interactions are written as small functions that take
a `D1Database` and are tested against a **lightweight in-memory D1 fake** (implementing only the
`prepare`/`bind`/`run`/`all`/`first` surface actually used) — exactly how 12a tests Gemini by
mocking `fetch` rather than calling the live API. Real D1-binding behavior is exercised manually
via `wrangler dev`'s local D1 at deploy time. No live API calls — Gemini is mocked, as in 12a.

- **Logging:** logs exactly one row on an allowed request; logs **nothing** on each rejection
  path (bad shape, failed Turnstile, over-limit).
- **PII guard:** assert no column ever holds an IP — the logged row contains only
  text/ts/country/msg_count, and `country` is the coarse `cf` value, never `CF-Connecting-IP`.
- **Digest:** prompt assembly over a set of rows; **skip-on-empty** (no LLM call, no row when
  there are no new questions); a digest row is written with the right `n_questions`.
- **Retention purge:** boundary test — a row at `now − 30d + 1s` survives, `now − 30d − 1s` is
  deleted.
- **Dashboard:** HTML renders the latest digest + question table; monthly-counter math
  (`month` / `MONTHLY_CEILING`); the `Cf-Access-Authenticated-User-Email` 403 guard.

## Ops / deployment

- **D1 + Cron Triggers are free-tier** at this traffic; no new out-of-pocket cost. The digest's
  Gemini call reuses the existing free-tier key.
- D1 database created via `wrangler d1 create`; the returned database id goes into the committed
  `wrangler.toml` (account-scoped, not a secret — same reasoning as the KV id). Schema applied
  via a committed `worker/schema.sql` + `wrangler d1 execute`.
- Cloudflare Access policy (Google login, Jin-Ho's email) configured once in the CF dashboard —
  no code, no secret in git.
- Local dev: `wrangler dev` provides a local (miniflare) D1 and can invoke the scheduled
  handler via its `/__scheduled` endpoint for manual cron testing — this is where the real D1
  binding is exercised, since the vitest suite uses an in-memory fake (see §4).
- No change to the Pages build — the Worker still deploys separately via `just worker-deploy`.

## CLAUDE.md impact

Add a **Phase 12b** row to the phasing table on completion. Note the new conventions: the
Worker now uses D1 (insights) + a Cron Trigger, and serves a private Access-gated HTML route
that is intentionally excluded from the public site surface (sitemap/llms.txt).
