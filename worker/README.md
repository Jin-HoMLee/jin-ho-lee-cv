# Digital-twin chat Worker

The Phase 12a digital-twin chat Worker: a Cloudflare Worker that proxies
CV-grounded questions to Google Gemini (`gemini-3.5-flash`), holding the Gemini
API key as a Worker secret. It reads only the generated public
`dist/chat-context.md` (compiled from `content/` by
`scripts/render_chat_context.py`) — no PII, nothing from `content.private/`.

The Worker transforms Gemini's native SSE back into the client envelope the
browser widget already parses, so the frontend contract is unchanged.

## Cost (read this first)

Every Cloudflare service this Worker uses — Workers, KV, Turnstile — is on the
**free tier** at expected traffic. The inference provider is the **Google Gemini
free tier** (`gemini-3.5-flash`, ~250 requests/day for Flash) — **no out-of-pocket
cost** at expected personal-site traffic. When the free quota is exhausted, Gemini
returns an error and the Worker shows the graceful "twin's resting" fallback. Usage
stays bounded by `MAX_TOKENS` per answer and the global `MONTHLY_CEILING` request
cap.

## One-time setup

1. `cd worker && npm install`
2. Create a Workers KV namespace and paste the returned id into
   `wrangler.toml`'s `[[kv_namespaces]] id`:
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
5. Create a Cloudflare Turnstile widget. Put its **SITE** key in `web/.env` as
   `PUBLIC_TURNSTILE_SITE_KEY`, and feed its **SECRET** key into the Worker
   secret from step 4. Also set `PUBLIC_TWIN_ENDPOINT` in `web/.env` to the
   deployed Worker URL.

## Deploy

From the repo root:

```bash
just worker-deploy   # bundles a fresh dist/chat-context.md, then `wrangler deploy`
```

Local development:

```bash
just worker-dev      # bundles chat-context.md, then `wrangler dev`
```

`worker/chat-context.md` is gitignored and regenerated at deploy time — never
commit it.

## Config vars (`wrangler.toml` `[vars]`)

| Var | Purpose | Default |
|---|---|---|
| `ALLOWED_ORIGIN` | The site origin allowed by CORS | — |
| `MONTHLY_CEILING` | Global monthly request cap (wallet guard) | `5000` |
| `MAX_TOKENS` | Per-answer token cap | `700` |

Secrets (set via `wrangler secret put`, never in git): `GEMINI_API_KEY`,
`TURNSTILE_SECRET_KEY`.

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
- **No operator usage visibility.** Question logging / usage dashboards are
  deferred to Phase 12b.
