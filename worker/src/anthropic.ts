import type { SystemBlock } from "./prompt";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

// Streams a Claude Haiku 4.5 response. Returns the raw SSE Response body to pipe to the client.
export async function streamClaude(
  apiKey: string,
  system: SystemBlock[],
  messages: ChatMessage[],
  maxTokens: number,
  fetchImpl: typeof fetch = fetch,
): Promise<Response> {
  return fetchImpl("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-api-key": apiKey,
      "anthropic-version": "2023-06-01",
    },
    body: JSON.stringify({
      model: "claude-haiku-4-5-20251001",
      max_tokens: maxTokens,
      system,
      messages,
      stream: true,
    }),
  });
}
