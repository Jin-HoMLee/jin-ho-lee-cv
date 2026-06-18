import {
  lastDigestTs,
  questionsSince,
  insertDigest,
  purgeOld,
  type QuestionRow,
} from "./insights";
import { generateText } from "./gemini";

// Raw question rows are ephemeral input to the digest; the digest is the durable
// artifact. 30-day TTL bounds any leak window and aligns retention with use.
export const RETENTION_SECONDS = 30 * 86400;

// PURE: assemble the "group these into themes" prompt over a set of question rows.
// Visitor text is injected verbatim (prompt-injection risk). This is an ACCEPTED
// tradeoff: the digest output is shown only on the private Cloudflare-Access-gated
// dashboard and is never returned to any visitor.
export function buildDigestPrompt(rows: QuestionRow[]): string {
  const list = rows.map((r) => `- ${r.text}`).join("\n");
  return (
    "You are summarising questions visitors asked a personal CV chatbot. " +
    "Group them into a few short themes. For each theme, give a one-line heading " +
    "and how many questions fell under it. Output concise Markdown, nothing else.\n\n" +
    "Questions:\n" +
    list
  );
}

// Daily cron body: digest new questions since the last run (skip the LLM entirely
// when there are none), then purge questions older than the retention window. The
// purge ALWAYS runs unconditionally — on an empty round AND when the digest LLM
// call fails. It is a privacy guarantee and must not depend on an external service.
export async function runDigest(
  db: D1Database,
  apiKey: string,
  now: number,
  fetchImpl: typeof fetch = fetch,
): Promise<{ digested: number }> {
  const since = await lastDigestTs(db);
  const rows = await questionsSince(db, since);
  let digested = 0;
  if (rows.length > 0) {
    try {
      const markdown = await generateText(apiKey, buildDigestPrompt(rows), fetchImpl);
      await insertDigest(db, { ts: now, markdown, n_questions: rows.length });
      digested = rows.length;
    } catch {
      // Gemini outage (non-200): skip this round's digest but STILL purge below.
      // The purge is a privacy guarantee and must not depend on an external service.
    }
  }
  await purgeOld(db, now - RETENTION_SECONDS);
  return { digested };
}
