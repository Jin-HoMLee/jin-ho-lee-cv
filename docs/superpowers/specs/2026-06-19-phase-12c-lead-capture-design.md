# Phase 12c — Digital-twin lead-capture: design

**Date:** 2026-06-19
**Issue:** [#85](https://github.com/Jin-HoMLee/jin-ho-lee-cv/issues/85)
**Depends on:** Phase 12b (merged, PR #86, `1791691`) — reuses its D1 store + Cloudflare-Access-gated dashboard.

## Goal

When a digital-twin chat winds down, let the visitor **opt in to leave their contact
details** so Jin-Ho can follow up. This turns an anonymous chat into a warm lead —
arguably the highest-value thing the twin can do for a job-seeker's CV site.

This is the deliberate **inverse of speculative data-hoarding** (which 12b explicitly
rejected): instead of quietly over-collecting, the visitor *chooses* to hand over their
details because they *want* to be contacted — explicit opt-in, clear purpose, consented
PII, retained because the purpose genuinely needs it.

## Decisions (from brainstorming)

| Decision | Choice |
|---|---|
| Notification | Chat webhook (free, instant, no DNS / domain-reputation overhead) |
| Webhook target | Swappable `LeadNotifier` interface; **default Telegram**; secret set at deploy |
| Affordance | Persistent "📇 Leave your details" button **+** one-time heuristic nudge after 3 assistant replies; **no LLM intent detection** (deterministic, testable) |
| Form fields | Email **required**; name + message optional; **consent checkbox required** |
| Retention | Leads **kept** — not auto-purged (the deliberate flip vs. 12b's 30-day questions) |
| Storage stance | Store in D1 **first**, notify best-effort via `ctx.waitUntil` — dashboard is the backstop |

## Architecture & data flow

```
Widget (web/src/components/DigitalTwin.astro)
  └─ "📇 Leave your details" button (always visible) + one-time nudge card after 3 assistant replies
       └─ inline form: email* , name, message, ☑ consent
            └─ POST /lead  { email, name, message, consent, turnstileToken }   (web/src/lib/twin.ts: submitLead)
                 ↓ Worker (worker/src/index.ts)
                 ├─ CORS allowlist + Turnstile verify + per-IP daily submit cap (reuse 12a guards + RATE_KV)
                 ├─ validateLead(): email shape, length bounds, consent === true  → 400 on fail
                 ├─ insertLead() into contact_submissions (D1)   ← stored first = source of truth
                 └─ ctx.waitUntil(notifyLead(...))                ← best-effort push, never blocks the response
            └─ 200 → widget shows "Thanks — Jin-Ho will be in touch"
Dashboard  /twin-insights (Access-gated, 12b)
  └─ new "Leads" section: email (mailto), name, message, country, time
```

**Key principle — store before notify.** The lead is written to D1 *before* the webhook
fires. Notification is best-effort (`ctx.waitUntil`): if Telegram is down or unconfigured,
the lead is still safe in D1 and visible on the dashboard. The visitor always receives a
clean `200` once the row is stored — we never claim success on an unstored lead.

## Components

### New
- **`worker/src/leads.ts`** — data layer mirroring `insights.ts`:
  - `validateLead(input)` — pure function: trims/checks email shape (simple, permissive
    regex), enforces length bounds (email ≤ 254, name ≤ 100, message ≤ 1000), requires
    `consent === true`. Returns a discriminated `{ ok: true, lead } | { ok: false }`.
  - `insertLead(db, lead)` — INSERT into `contact_submissions`.
  - `recentLeads(db, limit)` — SELECT newest-first for the dashboard.
- **`worker/src/notify.ts`** — `notifyLead(lead, env)` behind a tiny `LeadNotifier`
  interface. Telegram implementation (default): POSTs a formatted message to the Bot API.
  **Graceful default:** if `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` are unset, it logs and
  no-ops — the feature still stores leads (mirrors the widget's "endpoint unset → renders
  nothing" pattern). Swallows delivery errors (never throws into `waitUntil`).

### Changed
- **`worker/src/index.ts`** — add a `POST /lead` route: reuses `corsHeaders` /
  `isAllowedOrigin`, `verifyTurnstile`, and a modest per-IP **daily submit cap** (3/day) via
  the existing `RATE_KV` (separate key namespace, e.g. `lead:<ip>`). Country from
  `req.cf.country`. Stores then `ctx.waitUntil(notifyLead(...))`.
- **`worker/schema.sql`** — add `contact_submissions` (below). **Not** auto-purged: the 12b
  purge cron deletes only from `questions`, so this table is untouched.
- **`worker/src/dashboard.ts`** — add a "Leads" section to `renderDashboard()` (reuse
  `escapeHtml`; email rendered as a `mailto:` link). Accepts a new `leads` field.
- **`web/src/lib/twin.ts`** — add `submitLead(endpoint, payload, turnstileToken)` (POST,
  returns ok/err). Mirrors `streamTwin`'s fetch/error shape.
- **`web/src/components/DigitalTwin.astro`** — persistent button, one-time nudge card
  (shown after the 3rd assistant reply, dismissible, shows once per session), inline form
  with consent checkbox + clear purpose copy, submit handler using a fresh Turnstile token.

## Schema

```sql
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

## Privacy & consent

- The consent checkbox copy names the purpose explicitly ("so Jin-Ho can follow up about
  opportunities") and that the details are **stored and not auto-deleted**. `consent` is
  persisted; a row only exists if consent was given (validation rejects otherwise).
- No PII lands in git: leads live in Cloudflare D1; the dashboard rendering them is
  Access-gated and off the public surface (sitemap / llms.txt / CNAME). The repo PII guard
  (`check_pii.py`) is therefore unaffected.
- Deletion-on-request is handled informally (the visitor can email to be removed); a
  deletion UI is out of scope.

## Config / secrets

- `TELEGRAM_BOT_TOKEN` — secret via `wrangler secret put`.
- `TELEGRAM_CHAT_ID` — non-secret var (account/chat-scoped, like the KV/D1 ids) in
  `wrangler.toml [vars]`, overridable in `worker/.dev.vars` for local dev.
- Unset → `notifyLead` no-ops gracefully. No change to the Pages build; the widget form is
  present whenever the twin endpoint is configured.

## Error handling

| Condition | Response |
|---|---|
| Bad JSON / failed validation / `consent !== true` | `400` (with CORS) |
| Turnstile verification fails | `403` |
| Per-IP daily submit cap exceeded | `429` |
| D1 insert fails (lead NOT stored) | `502` — honest; widget shows the resting/error notice |
| Webhook delivery fails | swallowed in `ctx.waitUntil`; lead already stored, dashboard backstop |

## Testing (TDD, vitest against the fake D1)

- `validateLead`: valid/invalid email shapes, length bounds, `consent` gate, optional-field
  handling (empty name/message → null).
- `insertLead` / `recentLeads`: round-trip via `test/fakeD1.ts`; newest-first ordering.
- `notifyLead`: mock `fetch` — payload shape for Telegram, **no-op when unconfigured**,
  swallows a failing/throwing fetch without rejecting.
- `/lead` routing: CORS / Turnstile / validation / rate-cap / store-then-notify branches.
- `dashboard`: renders a leads row with escaped values and a `mailto:` email.

## Out of scope (future)

Per-visitor session memory; CRM integration; multilingual chat; email delivery (webhook
instead); deletion UI; LLM intent detection.

## Done when

A winding-down visitor can opt in to leave contact details; submissions are stored
(consented, kept) and Jin-Ho is notified via the webhook; leads are visible on the 12b
Access-gated dashboard; full gate (validate + test + lint) green; CLAUDE.md Phase 12c row
added.
