// Single source of truth for long-form write-ups (Phase 15).
// The route, the CV cross-link, the OG-image route, and the article JSON-LD all
// read from here, so a second write-up later is a data addition, not a refactor.
// This is the one piece of deliberate forward-design; everything else stays minimal.

export interface Writeup {
  /** URL slug under /writeups/. */
  slug: string;
  /** Visible article title (also the <h1> and JSON-LD headline). */
  title: string;
  /** One-sentence summary (meta description, OG, card blurb). */
  summary: string;
  /** ISO date the write-up was published/last revised. */
  date: string;
  /** Honest lifecycle marker; v1 ships "in-progress". */
  status: "draft" | "in-progress" | "published";
  /** Article language. v1 is English-only. */
  lang: "en";
  /** The CV project id this write-up amplifies (drives the card cross-link). */
  projectId: string;
  /** Code repository the article is based on (JSON-LD isBasedOn / linkout). */
  repoUrl: string;
  /** OG-image key registered in web/src/pages/og/[...path].ts. */
  ogSlug: string;
}

export const writeups: Writeup[] = [
  {
    slug: "splice-neoepitopes",
    title: "From Splice Junctions to Neoepitopes",
    summary:
      "How a modernized, reproducible RNA-Seq pipeline turns tumor-exclusive splice junctions into candidate immunotherapy targets.",
    date: "2026-07-20",
    status: "in-progress",
    lang: "en",
    projectId: "L5",
    repoUrl: "https://github.com/Jin-HoMLee/splice-neoepitope-pipeline",
    ogSlug: "writeups-splice-neoepitopes-en",
  },
];

export function writeupByProjectId(id: string): Writeup | undefined {
  return writeups.find((w) => w.projectId === id);
}
