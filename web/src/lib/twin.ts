// Discriminated stream chunks: text deltas, plus a one-off "truncated" signal when
// the model stopped because it hit max_tokens (so the UI can show a graceful affordance).
export type TwinChunk = { type: "text"; text: string } | { type: "truncated" };

// Posts the conversation to the Worker and yields streamed chunks (SSE).
export async function* streamTwin(
  endpoint: string,
  messages: { role: "user" | "assistant"; content: string }[],
  turnstileToken: string,
): AsyncGenerator<TwinChunk> {
  // Stall guard: abort if the connection goes idle for STALL_MS (e.g. the Worker
  // connects but the Gemini upstream hangs without sending or closing). Without
  // this a stalled-but-open stream never throws, so the widget's `busy` guard
  // stays stuck and the typing dots spin forever. The timer resets on every chunk
  // so a slow-but-progressing answer isn't killed — only genuine silence is.
  const STALL_MS = 30_000;
  const ctrl = new AbortController();
  let timer = setTimeout(() => ctrl.abort(), STALL_MS);
  const keepalive = () => {
    clearTimeout(timer);
    timer = setTimeout(() => ctrl.abort(), STALL_MS);
  };
  try {
    const res = await fetch(endpoint, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ messages, turnstileToken }),
      signal: ctrl.signal,
    });
    if (!res.ok || !res.body) throw new Error(String(res.status));
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      keepalive(); // progress — reset the stall timer
      buf += decoder.decode(value, { stream: true });
      const lines = buf.split("\n");
      buf = lines.pop() ?? "";
      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        try {
          const evt = JSON.parse(line.slice(6));
          if (evt.type === "content_block_delta" && evt.delta?.text) {
            yield { type: "text", text: evt.delta.text };
          } else if (evt.type === "message_delta" && evt.delta?.stop_reason === "max_tokens") {
            // The reply was cut at the per-answer cap — signal the UI, don't silently truncate.
            yield { type: "truncated" };
          }
        } catch {
          /* keep-alive / non-JSON line — ignore */
        }
      }
    }
  } finally {
    clearTimeout(timer);
  }
}
