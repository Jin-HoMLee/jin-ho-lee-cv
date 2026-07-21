import { WORKERS_AI_FIRST_RESPONSE_DEADLINE_MS, raceDeadline } from "./deadline";
import type { ChatMessage } from "./gemini";

// Cross-vendor fallback rung (#97): Cloudflare Workers AI, reached via the env.AI
// platform binding - no external API key, no new secret. The account is on the
// Workers FREE plan: past the free 10k Neurons/day allowance ai.run just throws
// (no billing surface), which the callers treat as this rung failing too.
//
// The model must be LIVE-VERIFIED before being swapped (the Gemma lesson: a
// catalog listing is not proof a model behaves at our token budget). fp8-fast is
// the latency-optimized Llama 3.3 70B variant, verified to stream a clean grounded
// persona answer within MAX_TOKENS.
export const WORKERS_AI_MODEL = "@cf/meta/llama-3.3-70b-instruct-fp8-fast";

// Minimal structural surface of the env.AI binding - deliberately NOT the `Ai`
// type from @cloudflare/workers-types, whose model-name union lags the live
// catalog and would reject newer model ids at compile time.
export interface AiBinding {
  run(model: string, options: Record<string, unknown>): Promise<unknown>;
}

// PURE: map a parsed Workers AI SSE chunk to zero or more client envelopes.
// Workers AI streams `data: {"response":"<token>", ...}` lines and terminates with
// the non-JSON sentinel `data: [DONE]` (skipped upstream by sseToClientStream's
// JSON.parse guard). Usage/final chunks carry an empty response - yield nothing.
export function workersAiChunkToEnvelopes(chunk: any): object[] {
  if (typeof chunk?.response === "string" && chunk.response.length > 0) {
    return [{ type: "content_block_delta", delta: { text: chunk.response } }];
  }
  return [];
}

// Streaming chat completion. The system text rides as a leading system-role message
// (Workers AI has no separate systemInstruction field); history roles pass through
// unchanged (same "user"/"assistant" names). Errors (neuron exhaustion, model
// errors) propagate as thrown exceptions - the caller decides the terminal message.
//
// First-response deadline (#119): the `await ai.run(...)` gets the same phase-1
// treatment as streamGemini's fetches - a bounded wait (default 5s, a RESERVED
// slice on top of Gemini's 20s budget so this rung always gets a real chance)
// whose expiry rejects with FirstResponseTimeoutError, which the caller's
// existing catch turns into the friendly terminal message.
export async function streamWorkersAI(
  ai: AiBinding,
  systemText: string,
  messages: ChatMessage[],
  maxTokens: number,
  deadlineMs: number = WORKERS_AI_FIRST_RESPONSE_DEADLINE_MS,
): Promise<ReadableStream<Uint8Array>> {
  const result = await raceDeadline(
    ai.run(WORKERS_AI_MODEL, {
      messages: [
        { role: "system", content: systemText },
        ...messages.map((m) => ({ role: m.role, content: m.content })),
      ],
      stream: true,
      max_tokens: maxTokens,
    }),
    deadlineMs,
    "workers-ai",
  );
  return result as ReadableStream<Uint8Array>;
}

// One-shot (non-streaming) completion - the digest-cron fallback. Without
// `stream: true` the binding resolves to an object carrying a `response` string.
export async function generateTextWorkersAI(ai: AiBinding, prompt: string): Promise<string> {
  const result = (await ai.run(WORKERS_AI_MODEL, {
    messages: [{ role: "user", content: prompt }],
  })) as { response?: unknown };
  return typeof result?.response === "string" ? result.response : "";
}
