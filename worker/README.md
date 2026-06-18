# Digital-twin chat Worker

The Phase 12a digital-twin chat Worker: a Cloudflare Worker that proxies
CV-grounded questions to Google Gemini (a best-first free-tier model cascade —
see Cost below), holding the Gemini API key as a Worker secret. It reads only the
generated public
`dist/chat-context.md` (compiled from `content/` by
`scripts/render_chat_context.py`) — no PII, nothing from `content.private/`.

The Worker transforms Gemini's native SSE back into the client envelope the
browser widget already parses, so the frontend contract is unchanged.

## Cost (read this first)

Every Cloudflare service this Worker uses — Workers, KV, Turnstile — is on the
**free tier** at expected traffic. The inference provider is the **Google Gemini
free tier** — **no out-of-pocket cost** at expected personal-site traffic.

Each Gemini model has its own free-tier **daily** request cap, so `src/gemini.ts`
uses a best-first **model cascade**: it tries `gemini-3.5-flash` (newest, but only
**20 requests/day** free), and on a daily-quota `429` (or a transient `503`/`500`)
falls through to `gemini-2.5-flash` (**250/day**), then `gemini-2.5-flash-lite`
(**1,000/day**). Visitors get the best model that still has quota, and the twin
stays reachable on the ~**1,270 combined free requests/day** instead of dying at 20.
Only when *every* model is exhausted does Gemini's error surface as the graceful
"twin's resting" fallback. Usage also stays bounded by `MAX_TOKENS` per answer and
the global `MONTHLY_CEILING` request cap.

## One-time setup

1. `cd worker && npm install`
2. Create a Workers KV namespace and paste the returned id into
   `wrangler.toml`'s `[[kv_namespaces]] id` (this id is not a secret — it is
   account-scoped and safe to commit):
   ```bash
   npx wrangler kv namespace create RATE_KV
   ```
3. Set the Gemini API key as a Worker secret. Create a free key in
   [Google AI Studio](https://aistudio.google.com/apikey) (no credit card):
   ```bash
   npx wrangler secret put GEMINI_API_KEY
   ```
4. Set the Turnstile secret as a Worker secret:
   ```bash
   npx wrangler secret put TURNSTILE_SECRET_KEY
   ```
5. Create a Cloudflare Turnstile widget. Put its **SITE** key (public) in
   `web/.env.production` as `PUBLIC_TURNSTILE_SITE_KEY` and set
   `PUBLIC_TWIN_ENDPOINT` there to the deployed Worker URL; feed its **SECRET**
   key into the Worker secret from step 4. (Local dev uses the committed
   `web/.env.development`, which points at `just worker-dev` on localhost with
   Cloudflare's always-pass test site key — Astro loads the right file by mode,
   so there's nothing to switch. CI injects the same two prod values from GitHub
   repo *variables*.)
6. Create the insights D1 database and apply the schema (the `database_id` is
   account-scoped, not a secret — safe to commit in `wrangler.toml`):
   ```bash
   npx wrangler d1 create twin-insights      # paste the id into wrangler.toml
   npx wrangler d1 execute twin-insights --remote --file=schema.sql
   ```
7. In the Cloudflare dashboard, put **Cloudflare Access** (Zero Trust → Access →
   Applications) in front of the deployed Worker's `/twin-insights` path, with a
   policy allowing only your Google login. No token or secret goes in git.

## Deploy

From the repo root:

```bash
just worker-deploy   # bundles a fresh dist/chat-context.md, then `wrangler deploy`
```

Local development:

```bash
cp worker/.dev.vars.example worker/.dev.vars   # once — adds http://localhost:4321 to the CORS allowlist
just worker-dev                                # bundles chat-context.md, then `wrangler dev`
```

`worker/chat-context.md` is gitignored and regenerated at deploy time — never
commit it.

`wrangler.toml` holds the **production** config and is committed. Local-only
overrides go in `worker/.dev.vars` (gitignored); Wrangler reads it during
`wrangler dev` and overrides the matching `[vars]`. This is why the localhost
dev origin lives in `.dev.vars`, not in the committed `ALLOWED_ORIGIN` — so the
deployed config stays clean and there's no file to stash before merges. Copy the
committed `.dev.vars.example` template to get started.

## Config vars (`wrangler.toml` `[vars]`)

| Var | Purpose | Default |
|---|---|---|
| `ALLOWED_ORIGIN` | The site origin(s) allowed by CORS (comma-separated allowlist) | — |
| `MONTHLY_CEILING` | Global monthly request cap (wallet guard) | `5000` |
| `MAX_TOKENS` | Per-answer token cap | `700` |

Production values are committed in `wrangler.toml`. For local `wrangler dev`,
override any of them in `worker/.dev.vars` (gitignored; see `.dev.vars.example`).

Secrets (set via `wrangler secret put`, never in git): `GEMINI_API_KEY`,
`TURNSTILE_SECRET_KEY`. These can also be placed in `.dev.vars` for local dev.

## Known limitations

- **Non-atomic counters.** The KV per-IP rate-limit and monthly-ceiling counters
  are read-then-write, so under concurrent bursts the monthly ceiling can
  slightly overshoot. Accepted MVP tradeoff; a Durable Object would give a hard
  guarantee.
- **Rolling window.** The "monthly" window is a rolling ~31-day TTL from the
  first write, not a calendar month.
- **Bounded conversation.** To prevent token-amplification abuse (and to stay
  within the Gemini free-tier per-request limit), the Worker rejects requests with
  an empty history, more than 20 messages, a non-`user`/`assistant` role, or any
  message over 4,000 characters. The widget also caps its input at 2,000 chars.
- **Operator dashboard.** `GET /twin-insights` (Phase 12b) shows the latest digest,
  a rolling-window usage counter, and recent questions. It is gated by Cloudflare
  Access plus a `Cf-Access-Authenticated-User-Email` header check, and is never part
  of the public site (absent from sitemap / llms.txt / CNAME). A daily Cron Trigger
  (`scheduled()`) writes the digest and purges questions older than 30 days.
