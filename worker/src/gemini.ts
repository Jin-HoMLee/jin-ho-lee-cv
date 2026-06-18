export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

// Free-tier Flash model. Bump here when Google ships a newer default.
const MODEL = "gemini-3.5-flash";

// Streams a Gemini 3.5 Flash response (free tier). The API key is a query param
// (server-side only — never exposed to the browser). Returns the raw upstream SSE
// Response; the body is transformed back into the client envelope by
// geminiToClientStream so the browser widget contract stays unchanged.
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
  const url =
    `https://generativelanguage.googleapis.com/v1beta/models/${MODEL}:streamGenerateContent` +
    `?alt=sse&key=${apiKey}`;
  return fetchImpl(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      systemInstruction: { parts: [{ text: systemText }] },
      contents,
      // thinkingLevel "low": Gemini 3.x Flash thinks by default and that reasoning
      // competes with the visible answer for the token budget — short, grounded CV
      // replies don't need it, and minimizing it stops answers truncating mid-sentence.
      generationConfig: {
        maxOutputTokens: maxTokens,
        thinkingConfig: { thinkingLevel: "low" },
      },
    }),
  });
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
