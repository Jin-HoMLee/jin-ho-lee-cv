import type { Labels, Lang, PublicationMetrics } from "../types/content";

type PublicationView = "authorship" | "cumulative";

const prefixes: Record<Lang, Record<PublicationView, string>> = {
  en: {
    authorship: "All-record authorship",
    cumulative: "All-record cumulative view",
  },
  de: {
    authorship: "Autorschaft über alle Einträge",
    cumulative: "Kumulative Ansicht aller Einträge",
  },
};

const totalLabels: Record<Lang, { nominative: string; dative: string }> = {
  en: { nominative: "bibliography records", dative: "bibliography records" },
  de: { nominative: "Bibliografie-Datensätze", dative: "Bibliografie-Datensätzen" },
};

export function formatPublicationTotalLabel(
  lang: Lang,
  grammaticalCase: "nominative" | "dative" = "nominative",
): string {
  return totalLabels[lang][grammaticalCase];
}

export function formatPublicationScopeCaption(
  metrics: PublicationMetrics,
  labels: Labels,
  lang: Lang,
  view: PublicationView,
): string {
  const breakdown = [
    `${metrics.research_records} ${labels.publications.research_label}`,
    `${metrics.applied_records} ${labels.publications.applied_label}`,
  ].join(" + ");
  return `${prefixes[lang][view]} · ${metrics.total_records} ${formatPublicationTotalLabel(lang)} (${breakdown})`;
}
