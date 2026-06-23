export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

// Free-tier model cascade, best-first. Each model carries its OWN free-tier daily
// request cap, so chaining several multiplies the combined budget and keeps the
// twin reachable long after the top model's quota is gone. We try the best model
// first and fall through to the next on a retryable failure (a daily-quota 429, or
// a transient 503/500). Caps run roughly best≈small, lite/older≈large (e.g.
// 3.5-flash ~20/day vs 2.5-flash-lite ~1000/day — verified against the live API),
// so the lower rungs carry the load once the premium quota is spent. Thinking
// config is model-family-specific: Gemini 3.x Flash takes `thinkingLevel` ("low"
// keeps the reasoning from eating the visible-answer token budget); the 2.5 models
// reject `thinkingLevel` (HTTP 400) and take `thinkingBudget: 0` to disable
// thinking; the 2.0 models have no thinking feature at all, so we omit
// thinkingConfig entirely — a stray budget there could 400 (non-retryable) and
// prematurely break the chain.
interface ModelConfig {
  name: string;
  thinkingConfig?: Record<string, unknown>;
}
const MODELS: ModelConfig[] = [
  { name: "gemini-3.5-flash", thinkingConfig: { thinkingLevel: "low" } },
  { name: "gemini-3.1-flash-lite", thinkingConfig: { thinkingLevel: "low" } },
  { name: "gemini-2.5-flash", thinkingConfig: { thinkingBudget: 0 } },
  { name: "gemini-2.5-flash-lite", thinkingConfig: { thinkingBudget: 0 } },
  { name: "gemini-2.0-flash" },
  { name: "gemini-2.0-flash-lite" },
];

// Upstream statuses worth retrying on the NEXT model in the cascade: 429 (daily or
// per-minute quota exhausted), 503 (model overloaded / "high demand"), 500
// (transient upstream error). A 400/401/403 is a config/auth bug — the next model
// would fail identically, so we stop and surface it rather than burn the cascade.
function isRetryable(status: number): boolean {
  return status === 429 || status === 500 || status === 503;
}

// Streams a Gemini Flash response (free tier), cascading down MODELS on a retryable
// upstream failure. The API key is a query param (server-side only — never exposed
// to the browser). Returns the first model's ok streaming Response; if a model
// fails retryably it tries the next, and if all are exhausted it returns the last
// failed Response (the caller turns any non-ok into a generic 502). The returned
// SSE body is transformed back into the client envelope by geminiToClientStream so
// the browser widget contract stays unchanged.
export async function streamGemini(
  apiKey: string,
  systemText: string,
  messages: ChatMessage[],
  maxTokens: number,
  fetchImpl: typeof fetch = fetch,
): Promise<Response> {
  const contents = messages.map((m) => ({
    role: m.role === "assistant" ? "model" : "user",
    parts: [{ text: m.content }],
  }));
  let res!: Response;
  for (const model of MODELS) {
    const url =
      `https://generativelanguage.googleapis.com/v1beta/models/${model.name}:streamGenerateContent` +
      `?alt=sse&key=${apiKey}`;
    res = await fetchImpl(url, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        systemInstruction: { parts: [{ text: systemText }] },
        contents,
        generationConfig: {
          maxOutputTokens: maxTokens,
          // Omitted for models without a thinking feature (the 2.0 family) — a
          // stray thinkingConfig there can 400 and break the cascade.
          ...(model.thinkingConfig ? { thinkingConfig: model.thinkingConfig } : {}),
        },
      }),
    });
    if (res.ok || !isRetryable(res.status)) return res;
    // Retryable failure → try the next model. Drain this error body (small JSON,
    // never an SSE stream) so the upstream connection isn't held open until GC.
    res.body?.cancel();
  }
  return res; // every model exhausted — surface the last failure
}

// PURE: map a parsed Gemini SSE chunk to zero or more client envelopes — exactly
// the shape the browser widget (web/src/lib/twin.ts) already parses. Tolerates
// missing fields (keep-alives, malformed chunks) by returning [].
export function geminiChunkToEnvelopes(chunk: any): object[] {
  const envelopes: object[] = [];
  const candidate = chunk?.candidates?.[0];
  const parts = candidate?.content?.parts;
  if (Array.isArray(parts)) {
    for (const part of parts) {
      if (typeof part?.text === "string") {
        envelopes.push({ type: "content_block_delta", delta: { text: part.text } });
      }
    }
  }
  if (candidate?.finishReason === "MAX_TOKENS") {
    envelopes.push({ type: "message_delta", delta: { stop_reason: "max_tokens" } });
  }
  return envelopes;
}

// One-shot (non-streaming) completion used by the Phase 12b digest cron. Uses the
// :generateContent endpoint (not :streamGenerateContent) and returns the joined
// candidate text. Cascades down the same free-tier MODELS as the chat path (no new
// credential or cost) so the daily digest still runs when the top model's quota is
// spent. Throws on a non-retryable error or after every model is exhausted, so the
// cron can skip writing a digest.
export async function generateText(
  apiKey: string,
  prompt: string,
  fetchImpl: typeof fetch = fetch,
): Promise<string> {
  let status = 0;
  for (const model of MODELS) {
    const url =
      `https://generativelanguage.googleapis.com/v1beta/models/${model.name}:generateContent` +
      `?key=${apiKey}`;
    const res = await fetchImpl(url, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        contents: [{ role: "user", parts: [{ text: prompt }] }],
        generationConfig: model.thinkingConfig ? { thinkingConfig: model.thinkingConfig } : {},
      }),
    });
    if (res.ok) {
      const data = (await res.json()) as any;
      const parts = data?.candidates?.[0]?.content?.parts;
      if (!Array.isArray(parts)) return "";
      return parts.map((p: any) => (typeof p?.text === "string" ? p.text : "")).join("");
    }
    status = res.status;
    if (!isRetryable(status)) break; // config/auth error — next model won't help
  }
  throw new Error(`gemini generateText upstream ${status}`);
}

// Read Gemini's native SSE and re-emit the client envelope SSE. Buffers across
// network chunks, splits on newlines, parses each `data: {json}` line, and
// enqueues `data: ${envelope}\n\n` for every envelope geminiChunkToEnvelopes
// yields. Non-JSON lines (keep-alives, comments) are skipped.
export function geminiToClientStream(
  upstream: ReadableStream<Uint8Array>,
): ReadableStream<Uint8Array> {
  const reader = upstream.getReader();
  const decoder = new TextDecoder();
  const encoder = new TextEncoder();
  let buffer = "";

  function emit(controller: ReadableStreamDefaultController<Uint8Array>, line: string): void {
    const trimmed = line.trimEnd();
    if (!trimmed.startsWith("data:")) return;
    const json = trimmed.slice(trimmed.indexOf(":") + 1).trim();
    if (!json) return;
    let parsed: unknown;
    try {
      parsed = JSON.parse(json);
    } catch {
      return; // keep-alive / non-JSON line
    }
    for (const env of geminiChunkToEnvelopes(parsed)) {
      controller.enqueue(encoder.encode(`data: ${JSON.stringify(env)}\n\n`));
    }
  }

  return new ReadableStream<Uint8Array>({
    async pull(controller) {
      const { done, value } = await reader.read();
      if (done) {
        if (buffer) emit(controller, buffer);
        controller.close();
        return;
      }
      buffer += decoder.decode(value, { stream: true });
      let idx: number;
      while ((idx = buffer.indexOf("\n")) !== -1) {
        const line = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 1);
        emit(controller, line);
      }
    },
    cancel(reason) {
      reader.cancel(reason);
    },
  });
}
