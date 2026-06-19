import { streamGemini, geminiToClientStream, type ChatMessage } from "./gemini";
import { runDigest } from "./digest";
import { latestDigest, recentQuestions, logQuestion } from "./insights";
import { renderDashboard } from "./dashboard";
import { PERSONA } from "./persona";
import { buildSystemText } from "./prompt";
import { checkLimits, type Counters, type Limits } from "./ratelimit";
import { verifyTurnstile } from "./turnstile";
import { validateLead, insertLead, recentLeads } from "./leads";
import { notifyLead } from "./notify";

// chat-context.md is copied into worker/ at deploy time and imported as text.
// @ts-expect-error — bundler text import of the generated context blob.
import CV_CONTEXT from "../chat-context.md";

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

// ALLOWED_ORIGIN may be a single origin or a comma-separated allowlist (e.g. the
// prod site plus http://localhost:4321 for local dev). An exact match against one
// of the listed origins is required.
export function isAllowedOrigin(origin: string | null, allowed: string): boolean {
  if (!origin) return false;
  return allowed
    .split(",")
    .map((o) => o.trim())
    .filter(Boolean)
    .includes(origin);
}

// Parse a config var to a finite, non-negative number, falling back to a safe
// default. A typo'd/unset MONTHLY_CEILING must NOT silently disengage the wallet
// guard (Number("") === NaN, and `month >= NaN` is always false).
export function finite(v: string, fallback: number): number {
  const n = Number(v);
  return Number.isFinite(n) && n >= 0 ? n : fallback;
}

export function corsHeaders(origin: string | null, allowed: string): Record<string, string> {
  // ACAO must echo the single matched request origin, never the whole allowlist.
  return {
    "Access-Control-Allow-Origin": isAllowedOrigin(origin, allowed) ? origin! : "",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "content-type",
  };
}

// MVP tradeoff: these KV counters are read-then-write (non-atomic), so under a
// concurrent burst the ceiling can slightly overshoot. The "monthly" window is a
// rolling ~31-day TTL from first write, not a calendar month. Both are accepted
// for the MVP; a Durable Object would be the hard-guarantee fix.
async function readCounters(kv: KVNamespace, ip: string): Promise<Counters> {
  const [minute, day, month] = await Promise.all([
    kv.get(`m:${ip}`),
    kv.get(`d:${ip}`),
    kv.get("month"),
  ]);
  return { minute: Number(minute ?? 0), day: Number(day ?? 0), month: Number(month ?? 0) };
}

async function bumpCounters(kv: KVNamespace, ip: string, c: Counters): Promise<void> {
  await Promise.all([
    kv.put(`m:${ip}`, String(c.minute + 1), { expirationTtl: 60 }),
    kv.put(`d:${ip}`, String(c.day + 1), { expirationTtl: 86400 }),
    kv.put("month", String(c.month + 1), { expirationTtl: 2678400 }),
  ]);
}

export default {
  async fetch(req: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const origin = req.headers.get("Origin");
    const cors = corsHeaders(origin, env.ALLOWED_ORIGIN);

    if (req.method === "OPTIONS") return new Response(null, { headers: cors });

    // Phase 12b private dashboard. Same-origin top-level navigation (no Origin
    // allowlist applies here, unlike POST /). Cloudflare Access authenticates at
    // the edge; this header check is cheap defense-in-depth so the route stays
    // closed even if the Access policy is misconfigured or removed.
    const url = new URL(req.url);
    if (req.method === "GET" && url.pathname === "/twin-insights") {
      if (!req.headers.get("Cf-Access-Authenticated-User-Email"))
        return new Response("forbidden", { status: 403 });
      const monthCount = Number((await env.RATE_KV.get("month")) ?? 0);
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
      return new Response(html, {
        status: 200,
        headers: { "content-type": "text/html; charset=utf-8" },
      });
    }

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

    if (req.method !== "POST" || !isAllowedOrigin(origin, env.ALLOWED_ORIGIN))
      return new Response("forbidden", { status: 403, headers: cors });

    const ip = req.headers.get("CF-Connecting-IP") ?? "0.0.0.0";

    // Parse the body defensively: non-JSON input must yield a clean 400 (with CORS),
    // not an opaque header-less 500. Validate shape BEFORE spending a Turnstile token
    // or bumping counters on a structurally invalid request.
    let body: { messages: ChatMessage[]; turnstileToken: string };
    try {
      body = (await req.json()) as { messages: ChatMessage[]; turnstileToken: string };
    } catch {
      return new Response("bad request", { status: 400, headers: cors });
    }
    // Bound the conversation to stop token-amplification abuse: a caller past Turnstile
    // could otherwise send a long history of large messages, inflating Gemini input tokens
    // (and burning the free-tier quota) well beyond what MAX_TOKENS — an OUTPUT cap — guards.
    if (
      !Array.isArray(body.messages) ||
      typeof body.turnstileToken !== "string" ||
      body.messages.length === 0 ||
      body.messages.length > 20 ||
      body.messages.some(
        (m) =>
          (m.role !== "user" && m.role !== "assistant") ||
          typeof m.content !== "string" ||
          m.content.length > 4000,
      )
    )
      return new Response("bad request", { status: 400, headers: cors });

    const ok = await verifyTurnstile(body.turnstileToken, env.TURNSTILE_SECRET_KEY, ip);
    if (!ok) return new Response("challenge failed", { status: 403, headers: cors });

    const limits: Limits = {
      perMinute: 10,
      perDay: 50,
      monthlyCeiling: finite(env.MONTHLY_CEILING, 5000),
    };
    const counters = await readCounters(env.RATE_KV, ip);
    const verdict = checkLimits(counters, limits);
    if (!verdict.allowed) {
      const msg = verdict.reason === "ceiling" ? "twin is resting" : "slow down a moment";
      return new Response(msg, { status: verdict.status, headers: cors });
    }
    await bumpCounters(env.RATE_KV, ip, counters);

    // Phase 12b: fire-and-forget log of the latest user question, AFTER every guard
    // (Turnstile + bounds + rate/ceiling) has passed — only real, human, allowed
    // questions are captured. Only a user-role final turn is logged; an assistant-role
    // last message is a valid shape but is not a visitor question. ctx.waitUntil keeps
    // it off the response path so a D1 error can never block or break the chat stream.
    // Privacy: text/ts/country/msg_count only — never the IP, never the answer.
    const latest = body.messages[body.messages.length - 1];
    if (latest.role === "user") {
      ctx.waitUntil(
        logQuestion(env.INSIGHTS_DB, {
          text: latest.content,
          ts: Math.floor(Date.now() / 1000),
          country: (req as { cf?: { country?: string } }).cf?.country ?? null,
          msg_count: body.messages.length,
        }).catch(() => {}),
      );
    }

    const systemText = buildSystemText(PERSONA, CV_CONTEXT as unknown as string);
    const upstream = await streamGemini(
      env.GEMINI_API_KEY,
      systemText,
      body.messages,
      finite(env.MAX_TOKENS, 700),
    );
    // On a non-200 from Gemini (429 quota exhausted, 400, 401, 500) the body is a
    // JSON error object, NOT an SSE stream — mislabeling it as text/event-stream
    // leaves a browser EventSource with a broken connection. Don't pass the raw
    // upstream error through (it can leak internal detail); return a generic 502.
    if (!upstream.ok)
      return new Response(JSON.stringify({ error: "twin upstream error" }), {
        status: 502,
        headers: { ...cors, "content-type": "application/json" },
      });
    // Transform Gemini's native SSE back into the client envelope the browser
    // widget already parses (web/src/lib/twin.ts) — the frontend contract is
    // unchanged across the provider swap.
    return new Response(geminiToClientStream(upstream.body!), {
      status: upstream.status,
      headers: { ...cors, "content-type": "text/event-stream" },
    });
  },

  // Phase 12b daily digest cron (wired via [triggers] crons in wrangler.toml).
  // Reuses the existing free-tier GEMINI_API_KEY; skip-on-empty + 30d purge live
  // in runDigest. waitUntil keeps the worker alive until the digest completes.
  async scheduled(_event: ScheduledController, env: Env, ctx: ExecutionContext): Promise<void> {
    ctx.waitUntil(runDigest(env.INSIGHTS_DB, env.GEMINI_API_KEY, Math.floor(Date.now() / 1000)).then(() => {}));
  },
};
