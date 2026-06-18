// Phase 12b insights data layer. Every function takes a D1Database so it can be
// unit-tested against the in-memory fake (test/fakeD1.ts); real D1 binding
// behaviour is exercised via `wrangler dev` local D1. Privacy invariant: the
// questions table stores ONLY ts/text/country/msg_count — never a raw IP, the
// twin's answer, or any fingerprint.

export interface QuestionRow {
  id: number;
  ts: number;
  text: string;
  country: string | null;
  msg_count: number;
}

export interface DigestRow {
  id: number;
  ts: number;
  markdown: string;
  n_questions: number;
}

export async function logQuestion(
  db: D1Database,
  q: { text: string; ts: number; country: string | null; msg_count: number },
): Promise<void> {
  await db
    .prepare("INSERT INTO questions (ts, text, country, msg_count) VALUES (?, ?, ?, ?)")
    .bind(q.ts, q.text, q.country, q.msg_count)
    .run();
}

export async function lastDigestTs(db: D1Database): Promise<number> {
  const row = await db.prepare("SELECT MAX(ts) AS ts FROM digests").first<{ ts: number | null }>();
  return row?.ts ?? 0;
}

export async function questionsSince(db: D1Database, ts: number): Promise<QuestionRow[]> {
  const { results } = await db
    .prepare("SELECT id, ts, text, country, msg_count FROM questions WHERE ts > ? ORDER BY ts ASC")
    .bind(ts)
    .all<QuestionRow>();
  return results ?? [];
}

export async function insertDigest(
  db: D1Database,
  d: { ts: number; markdown: string; n_questions: number },
): Promise<void> {
  await db
    .prepare("INSERT INTO digests (ts, markdown, n_questions) VALUES (?, ?, ?)")
    .bind(d.ts, d.markdown, d.n_questions)
    .run();
}

export async function purgeOld(db: D1Database, cutoffTs: number): Promise<void> {
  await db.prepare("DELETE FROM questions WHERE ts < ?").bind(cutoffTs).run();
}

export async function latestDigest(db: D1Database): Promise<DigestRow | null> {
  return await db
    .prepare("SELECT id, ts, markdown, n_questions FROM digests ORDER BY ts DESC LIMIT 1")
    .first<DigestRow>();
}

export async function recentQuestions(db: D1Database, limit: number): Promise<QuestionRow[]> {
  const { results } = await db
    .prepare("SELECT id, ts, text, country, msg_count FROM questions ORDER BY ts DESC LIMIT ?")
    .bind(limit)
    .all<QuestionRow>();
  return results ?? [];
}
