// Single source of truth for long-form write-ups (Phase 15).
// The route, the CV cross-link, the OG-image route, and the article JSON-LD all
// read from here, so a second write-up later is a data addition, not a refactor.
// This is the one piece of deliberate forward-design; everything else stays minimal.

export interface Writeup {
  /** URL slug under /writeups/. */
  slug: string;
  /** "research" amplifies a CV project; "build" is a meta post about this repo itself. */
  kind: "research" | "build";
  /** Visible article title (also the <h1> and JSON-LD headline). */
  title: string;
  /** One-sentence summary (meta description, OG, card blurb). */
  summary: string;
  /** ISO date the write-up was published/last revised. */
  date: string;
  /** Honest lifecycle marker. */
  status: "draft" | "in-progress" | "published";
  /** Article language. Both current write-ups are English-only. */
  lang: "en";
  /** CV project id a research write-up amplifies (drives the project-card cross-link). Absent for build posts. */
  projectId?: string;
  /** Code repository the article is based on (JSON-LD isBasedOn / linkout). */
  repoUrl: string;
  /** OG-image key registered in web/src/pages/og/[...path].ts. */
  ogSlug: string;
}

export const writeups: Writeup[] = [
  {
    slug: "splice-neoepitopes",
    kind: "research",
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
  {
    slug: "ask-my-cv",
    kind: "build",
    title: "Ask my CV",
    summary:
      "How I turned my CV into one YAML source of truth, five renderers, and a digital twin you can talk to - and had an AI agent build most of it.",
    date: "2026-07-22",
    status: "published",
    lang: "en",
    repoUrl: "https://github.com/Jin-HoMLee/jin-ho-lee-cv",
    ogSlug: "writeups-ask-my-cv-en",
  },
];

export function writeupByProjectId(id: string): Writeup | undefined {
  return writeups.find((w) => w.projectId === id);
}
