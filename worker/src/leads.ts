// Phase 12c lead-capture data layer. Mirrors insights.ts: every function takes a
// D1Database so it's unit-testable against test/fakeD1.ts. validateLead is pure.
// Privacy note: this table intentionally stores CONSENTED PII (email, name, message)
// — the deliberate inverse of the ephemeral 12b question log. Rows are KEPT.

export interface LeadInput {
  email?: unknown;
  name?: unknown;
  message?: unknown;
  consent?: unknown;
  msg_count?: unknown;
}

export interface Lead {
  email: string;
  name: string | null;
  message: string | null;
}

export type ValidateResult = { ok: true; lead: Lead } | { ok: false };

// Permissive single-line email shape: one @, a dot in the domain, no whitespace.
// Deliberately not RFC-5322-exhaustive — we only need to reject obvious junk; a
// real typo'd-but-valid address is the visitor's problem, not a security boundary.
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function validateLead(input: LeadInput): ValidateResult {
  if (input.consent !== true) return { ok: false };
  if (typeof input.email !== "string") return { ok: false };
  const email = input.email.trim();
  if (!email || email.length > 254 || !EMAIL_RE.test(email)) return { ok: false };

  let name: string | null = null;
  if (input.name !== undefined && input.name !== null && input.name !== "") {
    if (typeof input.name !== "string" || input.name.length > 100) return { ok: false };
    name = input.name.trim() || null;
  }

  let message: string | null = null;
  if (input.message !== undefined && input.message !== null && input.message !== "") {
    if (typeof input.message !== "string" || input.message.length > 1000) return { ok: false };
    message = input.message.trim() || null;
  }

  return { ok: true, lead: { email, name, message } };
}

export interface LeadRow {
  id: number;
  ts: number;
  email: string;
  name: string | null;
  message: string | null;
  country: string | null;
  consent: number;
  msg_count: number | null;
}

export async function insertLead(
  db: D1Database,
  l: {
    ts: number;
    email: string;
    name: string | null;
    message: string | null;
    country: string | null;
    msg_count: number | null;
  },
): Promise<void> {
  // consent is hardcoded 1: a row only exists because validateLead enforced consent===true.
  await db
    .prepare(
      "INSERT INTO contact_submissions (ts, email, name, message, country, consent, msg_count) VALUES (?, ?, ?, ?, ?, 1, ?)",
    )
    .bind(l.ts, l.email, l.name, l.message, l.country, l.msg_count)
    .run();
}

export async function recentLeads(db: D1Database, limit: number): Promise<LeadRow[]> {
  const { results } = await db
    .prepare(
      "SELECT id, ts, email, name, message, country, consent, msg_count FROM contact_submissions ORDER BY ts DESC LIMIT ?",
    )
    .bind(limit)
    .all<LeadRow>();
  return results ?? [];
}
