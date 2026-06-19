-- Phase 12b digital-twin insights. Applied with:
--   wrangler d1 execute twin-insights --file=schema.sql
CREATE TABLE IF NOT EXISTS questions (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  ts        INTEGER NOT NULL,           -- unix seconds
  text      TEXT    NOT NULL,           -- verbatim latest user message
  country   TEXT,                       -- coarse, from req.cf.country (nullable)
  msg_count INTEGER NOT NULL            -- conversation length at log time
);
CREATE INDEX IF NOT EXISTS idx_questions_ts ON questions(ts);

CREATE TABLE IF NOT EXISTS digests (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  ts          INTEGER NOT NULL,         -- unix seconds of the run
  markdown    TEXT    NOT NULL,         -- LLM-generated themed summary
  n_questions INTEGER NOT NULL          -- how many questions this digest covered
);
CREATE INDEX IF NOT EXISTS idx_digests_ts ON digests(ts);

-- Phase 12c lead-capture. Consented contact details a visitor opts in to leave.
-- KEPT (not auto-purged): unlike the 30-day `questions` log, the purpose (follow-up)
-- genuinely needs retention. The 12b purge cron deletes only from `questions`.
CREATE TABLE IF NOT EXISTS contact_submissions (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  ts        INTEGER NOT NULL,         -- unix seconds
  email     TEXT    NOT NULL,         -- required, validated shape
  name      TEXT,                     -- optional
  message   TEXT,                     -- optional, bounded
  country   TEXT,                     -- coarse, from req.cf.country (nullable)
  consent   INTEGER NOT NULL,         -- 1 = explicit opt-in (always 1 if a row exists)
  msg_count INTEGER                   -- conversation length at submit (context)
);
CREATE INDEX IF NOT EXISTS idx_leads_ts ON contact_submissions(ts);
