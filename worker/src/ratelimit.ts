export interface Limits {
  perMinute: number;
  perDay: number;
  monthlyCeiling: number;
}

export interface Counters {
  minute: number;
  day: number;
  month: number;
}

export type LimitResult =
  | { allowed: true }
  | { allowed: false; status: 429 | 503; reason: "rate" | "ceiling" };

// Ceiling (wallet protection) takes priority over per-IP fairness.
export function checkLimits(c: Counters, l: Limits): LimitResult {
  if (c.month >= l.monthlyCeiling) return { allowed: false, status: 503, reason: "ceiling" };
  if (c.minute >= l.perMinute || c.day >= l.perDay)
    return { allowed: false, status: 429, reason: "rate" };
  return { allowed: true };
}
