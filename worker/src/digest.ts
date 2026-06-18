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
// purge ALWAYS runs, even on an empty round.
export async function runDigest(
  db: D1Database,
  apiKey: string,
  now: number,
  fetchImpl: typeof fetch = fetch,
): Promise<{ digested: number }> {
  const since = await lastDigestTs(db);
  const rows = await questionsSince(db, since);
  if (rows.length > 0) {
    const markdown = await generateText(apiKey, buildDigestPrompt(rows), fetchImpl);
    await insertDigest(db, { ts: now, markdown, n_questions: rows.length });
  }
  await purgeOld(db, now - RETENTION_SECONDS);
  return { digested: rows.length };
}
