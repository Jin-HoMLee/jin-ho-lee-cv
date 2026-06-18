import { vi } from "vitest";

export interface RecordedStmt {
  sql: string;
  args: unknown[];
}

// Lightweight in-memory D1 fake: records every prepared statement + its bound
// args, and returns seeded results from an optional handler keyed on the SQL
// text. Mirrors how 12a tests the Gemini boundary by mocking fetch rather than
// calling the real service. Real D1 behaviour is exercised manually via
// `wrangler dev`'s local D1 (see README).
export function fakeD1(handler?: (sql: string, args: unknown[]) => { results?: any[]; first?: any }) {
  const calls: RecordedStmt[] = [];
  const db = {
    prepare(sql: string) {
      const rec: RecordedStmt = { sql, args: [] };
      const stmt = {
        bind(...args: unknown[]) {
          rec.args = args;
          return stmt;
        },
        async run() {
          calls.push(rec);
          return { success: true } as unknown as D1Result;
        },
        async all() {
          calls.push(rec);
          return { results: handler?.(rec.sql, rec.args)?.results ?? [] } as unknown as D1Result;
        },
        async first() {
          calls.push(rec);
          return (handler?.(rec.sql, rec.args)?.first ?? null) as unknown;
        },
      };
      return stmt as unknown as D1PreparedStatement;
    },
  } as unknown as D1Database;
  return { db, calls, _vi: vi };
}
