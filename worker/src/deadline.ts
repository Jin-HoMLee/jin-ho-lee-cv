// Server-side deadline for vendor FIRST-RESPONSE awaits (#119). The twin talks to
// an inference vendor in two phases: phase 1 waits for the vendor to respond at
// all (Gemini response headers, the Workers AI stream handle); phase 2 reads the
// open SSE stream. Phase 2 is guarded by sseToClientStream's 15s idle timer
// (#103); this module guards phase 1, where a half-dead upstream (connection
// accepted, response never sent) would otherwise block the await until the
// runtime's ~44s hung-request cancel - and a hang on Gemini rung 1 would bypass
// BOTH the remaining cascade rungs AND the #97 cross-vendor Workers AI rung.
//
// Budget shape: ONE cascade-wide deadline shared by all Gemini phase-1 awaits
// (20s across all 8 rungs - per-rung timers would stack to minutes), plus a
// separate small reserved budget for the single Workers AI attempt (5s). The
// reservation is the point: Gemini exhausting its budget must still leave the
// cross-vendor rung a real chance. Worst case is ~25s of phase-1 waiting,
// comfortably under the widget's 30s client-side stall guard
// (web/src/lib/twin.ts STALL_MS), so the visitor always receives a
// server-generated response - an answer or a friendly terminal message - first.
//
// A timeout is just another failure of the current vendor: streamGemini rejects,
// index.ts's existing catch moves on to Workers AI, and a Workers AI timeout
// falls through to the terminal message. No new control flow in the handler.
export const GEMINI_FIRST_RESPONSE_DEADLINE_MS = 20_000;
export const WORKERS_AI_FIRST_RESPONSE_DEADLINE_MS = 5_000;

// Distinguishable from vendor/network errors in wrangler tail (name + vendor in
// the message; never any upstream body).
export class FirstResponseTimeoutError extends Error {
  constructor(vendor: string) {
    super(`${vendor} first-response deadline exceeded`);
    this.name = "FirstResponseTimeoutError";
  }
}

// Race a phase-1 await against a deadline - the same timer-race pattern as
// sseToClientStream's idle guard (timer set synchronously, cleared in finally).
// Promise.race keeps its handlers attached to the losing promise, so an upstream
// that settles after the timeout can never surface as an unhandled rejection.
export async function raceDeadline<T>(promise: Promise<T>, ms: number, vendor: string): Promise<T> {
  let timer!: ReturnType<typeof setTimeout>; // set synchronously by the executor below
  const timeout = new Promise<never>((_, reject) => {
    timer = setTimeout(() => reject(new FirstResponseTimeoutError(vendor)), ms);
  });
  try {
    return await Promise.race([promise, timeout]);
  } finally {
    clearTimeout(timer);
  }
}
