import type { Period, Labels } from "../types/content";

/**
 * Render a period like "2024-05" → "May 2024", using locale-resolved month
 * abbreviations and the language-specific "present" label for ongoing entries.
 */
export function formatPeriod(period: Period, labels: Labels): string {
  const fmt = (ym: string | null) => {
    if (!ym) return labels.misc.present;
    const [y, m] = ym.split("-");
    const monthIdx = parseInt(m, 10) - 1;
    const monthName = labels.months_abbr[monthIdx] ?? m;
    return `${monthName} ${y}`;
  };
  return `${fmt(period.start)} – ${fmt(period.end)}`;
}
