// Named [...path].ts, not [...path].png.ts: astro-og-canvas appends .png itself;
// using [...path].png.ts would produce double-extension outputs (key.png.png).
import { OGImageRoute } from "astro-og-canvas";
import contentEn from "../../data/content.en.json";
import contentDe from "../../data/content.de.json";
import type { ContentData, Project, Lang } from "../../types/content";

const en = contentEn as ContentData;
const de = contentDe as ContentData;

interface OgPage {
  title: string;
  kicker: string;
  subtitle?: string;
  meta: { label: string; value: string }[];
}

function homepagePage(data: ContentData, lang: Lang): OgPage {
  const name = `${data.personal.name.given} ${data.personal.name.family}`;
  return {
    kicker: lang === "en" ? `${name} — CV` : `${name} — Lebenslauf`,
    title: data.profile.tagline,
    subtitle: data.personal.headline,
    meta: [
      { label: lang === "en" ? "Based in" : "Standort", value: data.personal.location.city },
      { label: lang === "en" ? "Languages" : "Sprachen", value: data.languages.map((l) => l.name).join(" · ") },
    ],
  };
}

function projectPage(project: Project, lang: Lang, dataName: string): OgPage {
  const techPreview = project.technologies.slice(0, 3).join(" · ");
  return {
    kicker: lang === "en" ? `${dataName} — Project Brief` : `${dataName} — Projektkurzbeschreibung`,
    title: project.title,
    subtitle: project.role,
    meta: [
      {
        label: lang === "en" ? "Period" : "Zeitraum",
        value: `${project.period.start}${project.period.end ? ` – ${project.period.end}` : ""}`,
      },
      { label: lang === "en" ? "Stack" : "Technologien", value: techPreview },
      { label: lang === "en" ? "Project" : "Projekt", value: project.id },
    ],
  };
}

const enName = `${en.personal.name.given} ${en.personal.name.family}`;
const deName = `${de.personal.name.given} ${de.personal.name.family}`;

const pages: Record<string, OgPage> = {
  "index-en": homepagePage(en, "en"),
  "index-de": homepagePage(de, "de"),
};
for (const [id, project] of Object.entries(en.projects)) {
  pages[`projects-${id}-en`] = projectPage(project, "en", enName);
}
for (const [id, project] of Object.entries(de.projects)) {
  pages[`projects-${id}-de`] = projectPage(project, "de", deName);
}

export const { getStaticPaths, GET } = await OGImageRoute({
  param: "path",
  pages,
  getImageOptions: (_path, page: OgPage) => ({
    title: page.title,
    description: [
      page.kicker,
      page.subtitle ?? "",
      ...page.meta.map((m) => `${m.label}: ${m.value}`),
    ]
      .filter(Boolean)
      .join("\n"),
    bgGradient: [[244, 247, 251]],
    border: { color: [31, 58, 104], width: 8, side: "inline-start" },
    padding: 60,
    font: {
      title: {
        size: 56,
        color: [31, 58, 104],
        weight: "Bold",
        families: ["IBM Plex Sans", "Inter", "Helvetica", "Arial"],
        lineHeight: 1.15,
      },
      description: {
        size: 22,
        color: [68, 68, 68],
        families: ["IBM Plex Sans", "Inter", "Helvetica", "Arial"],
        lineHeight: 1.4,
      },
    },
  }),
});
