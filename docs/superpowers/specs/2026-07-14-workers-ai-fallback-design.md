# Workers AI cross-vendor fallback: design

**Date:** 2026-07-14
**Issue:** [#97](https://github.com/Jin-HoMLee/jin-ho-lee-cv/issues/97)

## Why

The digital twin's resilience currently rests entirely on Google: the cascade in `worker/src/gemini.ts` is eight Gemini/Gemma free-tier rungs, but they share one vendor and one API key.
A Google-wide outage (or a project-level cap) takes the whole chain down at once.
A final fallback rung from a different provider removes that single point of failure.

Workers AI is the lowest-friction cross-vendor option because the twin already runs as a Cloudflare Worker:
it is an `env.AI` platform binding (no new secret), it has a free daily allowance, and it adds no extra outbound hop.

## Verified platform facts (checked live 2026-07-14)

- Free allowance: 10,000 Neurons/day, reset 00:00 UTC.
- The account is on the Workers **free** plan: exceeding the allowance makes further calls fail with an error.
  There is no billing surface at all; an exhausted allowance is just a failed fallback rung.
- Streaming: `env.AI.run(model, { messages, stream: true, max_tokens })` returns a `ReadableStream` of SSE.
  Each data line is `data: {"response": "<token>", ...}`; the stream ends with the non-JSON sentinel `data: [DONE]`.
- Non-streaming: the same call without `stream` resolves to an object with a `response` string.
- Model: `@cf/meta/llama-3.3-70b-instruct-fp8-fast` supports streaming, a `messages` array with a `system` role, and `max_tokens`.

## Locked decisions

- **Model:** `@cf/meta/llama-3.3-70b-instruct-fp8-fast`.
  Mature, latency-optimized, strong instruction-following for a grounded-QA persona task.
  Must be **live-verified during implementation** before being locked in (the Gemma lesson: a catalog listing is not proof the model behaves at our token budget).
- **Scope: both consumers.** The chat stream and the daily digest cron both get the Workers AI fallback.
  The seam (binding + module) is shared, so the digest coverage is nearly free and the outage story stays symmetric.
- **Fire on any non-ok Gemini terminal, not only retryables.**
  A Gemini-side 400/401 is vendor-specific (request shape, API key); Workers AI shares neither, so falling through maximizes uptime at zero cost.
  This deliberately widens the issue's "retryable failure" wording.
- **No vendor switch mid-stream.** A Gemini stream that goes 200-then-stalls keeps today's behavior (idle guard, trouble message): once bytes have reached the client, switching vendors is not possible.
- **Graceful absence.** `AI` is typed optional; an absent binding means the fall-through step is skipped and behavior is byte-identical to today (the Telegram-notifier pattern).
- **Out of scope:** Groq / OpenRouter (each adds a secret + transform), any provider-registry abstraction, and any neuron-usage guard (the free plan hard-fails; existing MAX_TOKENS / per-IP caps / monthly ceiling already bound usage).

## Design

### Module layout

**`worker/src/sse.ts` (new): the vendor-neutral streaming layer.**
Extracted from `gemini.ts` with behavior unchanged:

- `sseToClientStream(upstream, chunkToEnvelopes, opts)`: the existing buffering + idle-guard + trouble-on-empty SSE transformer, generalized to take the chunk-to-envelopes mapper as a parameter.
- `clientMessageStream`, `RESTING_MESSAGE`, `TROUBLE_MESSAGE`, `IDLE_MS` move here (they are client-envelope concerns, not Gemini concerns).

`gemini.ts` re-exports nothing; consumers import from the module that owns the symbol.
`geminiToClientStream` becomes a thin wrapper: `sseToClientStream(upstream, geminiChunkToEnvelopes, opts)`.
The extraction proof: every existing transformer test passes with unchanged assertions (they relocate to `sse.test.ts`, see Testing).

**`worker/src/workersai.ts` (new): pure Workers AI, mirroring what `gemini.ts` is to Gemini.**

- `WORKERS_AI_MODEL = "@cf/meta/llama-3.3-70b-instruct-fp8-fast"`.
- `workersAiChunkToEnvelopes(chunk)`: pure.
  `{response: "tok"}` maps to `{type: "content_block_delta", delta: {text: "tok"}}`.
  Missing/empty `response` fields (usage chunks, keep-alives) yield `[]`.
  The `[DONE]` sentinel is not JSON, so the shared transformer already skips it.
- `streamWorkersAI(ai, systemText, messages, maxTokens)`: builds `[{role: "system", content: systemText}, ...history]` (assistant role passes through as-is; Workers AI uses the same `user`/`assistant` names), calls `ai.run(WORKERS_AI_MODEL, {messages, stream: true, max_tokens: maxTokens})`, and returns the raw SSE `ReadableStream`.
  Errors (neuron exhaustion, model errors) propagate as thrown exceptions; the caller catches.
- `generateTextWorkersAI(ai, prompt)`: non-streaming variant for the digest.
  Calls `ai.run` without `stream`, returns `result.response` (empty string if absent).

### Chat data flow (`index.ts`)

Today: `streamGemini` returns non-ok, the handler synthesizes a terminal message.
New: one fall-through step in between.

```
streamGemini exhausts (non-ok terminal Response)
  └─ env.AI bound? ── no ──→ terminal message (exactly today's behavior)
       └─ yes: try streamWorkersAI
            ├─ ok    → 200 SSE via sseToClientStream(stream, workersAiChunkToEnvelopes)
            └─ throws → terminal message (RESTING if Gemini ended 429, else TROUBLE)
```

The terminal-message mapping stays keyed on the Gemini terminal status, as today:
a cascade that ended on a quota 429 means the free-tier budget is spent (resting), anything else is treated as transient trouble.
A Workers AI failure does not change that classification; it only fails to rescue it.

### Digest data flow (`digest.ts`)

`runDigest` gains an optional `ai?: Ai` parameter (same optional-dependency shape as the existing `fetchImpl`).
Inside the existing `try`: when `generateText` throws and `ai` is present, try `generateTextWorkersAI(ai, prompt)` before giving up on this round's digest.
The unconditional `purgeOld` stays exactly where it is: the privacy guarantee must never depend on any vendor, including the new one.
`index.ts`'s `scheduled()` passes `env.AI` through.

### Config and environment

- `wrangler.toml`: add `[ai]` / `binding = "AI"`. No id, no secret; it is a platform binding.
- `Env` gains `AI?: AiBinding`, a minimal structural interface (`run(model: string, options: Record<string, unknown>): Promise<unknown>`) defined in `workersai.ts`.
  Deliberately not the `Ai` type from `@cloudflare/workers-types`: that type's model-name union lags the live catalog and would reject newer model ids at compile time.
  Optional typing keeps every absent-binding path (tests, local dev without login, misconfigured deploy) on the graceful skip branch.
- No change to `web/`, no change to the client envelope, no change to any secret.

### Error handling summary

| Failure | Behavior |
|---|---|
| Gemini cascade exhausts, `AI` absent | Terminal message, byte-identical to today |
| Gemini cascade exhausts, Workers AI streams | Visitor gets a llama-served answer in the unchanged client envelope |
| Gemini cascade exhausts, Workers AI throws (neurons spent, outage) | Terminal message keyed on the Gemini terminal status |
| Workers AI stream stalls mid-answer | Shared idle guard closes it; trouble message iff nothing was emitted |
| Digest: Gemini throws, Workers AI answers | Digest written, purge runs |
| Digest: both throw | Digest skipped, purge still runs |

## Testing

TDD throughout, mirroring the existing suite's fake-driven style (no network in tests).

- **`workersai.test.ts` (new).**
  Pure transform: token chunk, empty/usage chunk, malformed chunk.
  `streamWorkersAI` against a fake `ai.run`: asserts model id, system+history message shaping, `max_tokens`, `stream: true`, and that the returned stream is passed through raw.
  Throw propagation from `ai.run`.
- **`sse.test.ts` (new).**
  The transformer tests move here from `gemini.test.ts` alongside the code they cover (buffering across chunks, idle guard, trouble-on-empty, cancel), parameterized with `geminiChunkToEnvelopes`.
- **`handler.test.ts` additions.**
  Full-Gemini-failure + fake `AI` binding: the llama answer reaches the client as envelope SSE with a 200.
  Full-Gemini-failure + no `AI`: response identical to today's (resting/trouble).
  Full-Gemini-429 + `AI` throwing: RESTING_MESSAGE.
- **`digest.test.ts` additions.**
  Gemini down + `ai` present: digest written via the fallback.
  Both down: digest skipped, purge still runs.
- **Existing `gemini.test.ts`:** the non-transformer tests stay green with only import-path edits; the moved transformer tests pass in `sse.test.ts` with unchanged assertions.
  Together that is the extraction proof.
- **Live verification before merge** (the Gemma lesson):
  `wrangler dev` with the real binding, one real conversation through the widget flow, confirming llama-3.3-70b-fp8-fast streams a clean grounded persona answer within MAX_TOKENS.
  If it misbehaves, swap `WORKERS_AI_MODEL` and re-verify.
  Forcing the fall-through locally: point the Gemini key at an invalid value in `worker/.dev.vars` so every Gemini rung fails.

## Rollout

1. Implementation lands via PR on branch `97-workers-ai-fallback` (spec ships in the same PR; validate + test + lint + format green).
2. Deploy is the usual separate manual step: `just worker-deploy`.
3. Post-deploy smoke: temporarily exhaust/invalidate nothing in prod; instead verify via `wrangler tail` that normal traffic still serves from Gemini, and trust the live-verified dev fall-through.
   (A prod Gemini outage is the only true end-to-end trigger; the dev forcing method above is the proxy.)
4. CLAUDE.md: update the Worker cascade convention paragraph to mention the cross-vendor rung (the plan's final task, per repo convention).
