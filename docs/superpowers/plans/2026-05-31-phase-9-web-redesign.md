# Phase 9 — Web Design Overhaul (2026 dark-technical) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure the Astro website into a refined-dark, "CV-as-code" experience (dark default + light toggle) without touching `content/` — a renderer-only change.

**Architecture:** A semantic CSS-token theme layer drives every component; a no-flash inline script + vanilla-JS `ThemeToggle` switch `data-theme` on `<html>`. New components `CodeHero` (renders real `profile.yaml` data as a syntax-highlighted editor) and `StatBand` (four build-derived metric tiles) sit above the existing, restyled two-column content. Subtle motion (typing, count-up, section reveal) is gated behind `prefers-reduced-motion`. OG share cards get a dark restyle. All existing features (i18n, target switcher, SEO, sitemap, analytics, PDFs, machine formats) are preserved.

**Tech Stack:** Astro 5, Tailwind CSS 4 (CSS custom properties via arbitrary `var(--token)` utilities — *not* `@theme`, which compiles statically and can't switch at runtime), IBM Plex Sans + IBM Plex Mono (`@fontsource`), vanilla-JS Astro islands.

**Spec:** [`docs/superpowers/specs/2026-05-31-phase-9-web-redesign-design.md`](../specs/2026-05-31-phase-9-web-redesign-design.md)

**Branch:** `phase-9-web-redesign` (already created; spec committed at `e97a92e`).

---

## Conventions for every task

- **Build/verify command:** `just web-build` (runs `render_web_data` + `render_jsonld` + `astro build` → `web/dist`). Type-check: `pnpm --dir web exec astro check`.
- This is a **CSS/visual** redesign — there is little pure logic to unit-test. Verification leans on: `astro check` (types compile), `just web-build` (SSG succeeds), `grep` assertions on `web/dist/*.html` (elements reached the output), and a documented manual dark/light/reduced-motion pass (Task 10). The Python suite (`just validate && just test && just lint`) stays green **by construction** — `content/`, schema, and Python are untouched.
- **Commit** after each task with a plain message (no Claude attribution, per CLAUDE.md).
- **Do not** touch `content/`, the Python renderers, or the data JSON shape. Do not add a client framework.

### Design note — CodeHero is canonical (does NOT target-switch)

The `CodeHero` renders the **bridge/canonical** `headline` + `tagline`. It is *not* wired to the Phase 8c target switcher: thematically the hero shows the *source file* (one canonical identity), while the switcher re-positions the human-readable sections below it. Concretely this also avoids the switcher's `document.querySelector('[data-cv-field=…]')` first-match-only behavior breaking if `headline`/`tagline` hooks were duplicated. **The CodeHero's YAML must NOT carry `data-cv-field` attributes.** (If syncing the hero to the switcher is wanted later, that's a scoped follow-up that converts the switcher to `querySelectorAll`.)

---

## Task 1: Fonts + theme token foundation

**Files:**
- Modify: `web/package.json` (add `@fontsource/ibm-plex-mono`)
- Modify (full rewrite): `web/src/styles/global.css`

- [ ] **Step 1: Add the mono font dependency**

In `web/package.json`, add to `dependencies` (alphabetical, next to the existing ibm-plex-sans line):

```json
"@fontsource/ibm-plex-mono": "^5.0.0",
```

Then install:

Run: `pnpm --dir web install`
Expected: lockfile updates, `@fontsource/ibm-plex-mono` resolved.

- [ ] **Step 2: Rewrite `global.css` as a token layer**

Replace the **entire** contents of `web/src/styles/global.css` with:

```css
@import "tailwindcss";

@import "@fontsource/ibm-plex-sans/400.css";
@import "@fontsource/ibm-plex-sans/500.css";
@import "@fontsource/ibm-plex-sans/600.css";
@import "@fontsource/ibm-plex-sans/700.css";
@import "@fontsource/ibm-plex-mono/400.css";
@import "@fontsource/ibm-plex-mono/500.css";

/* ── Semantic theme tokens ─────────────────────────────────────────────
   Dark is the default (:root). Light overrides under [data-theme="light"].
   Components reference these via arbitrary utilities, e.g. bg-[var(--bg)].
   Back-compat aliases (--color-accent / --color-sidebar-bg) keep any
   un-migrated reference working during the sweep. */
:root {
  --bg: #0a0c12;
  --surface: #0e1520;
  --surface-2: #11161f;
  --surface-border: #1c2636;
  --text: #e8edf4;
  --muted: #9fb0c3;
  --faint: #5b6b80;
  --accent: #2dd4bf;
  --accent-hover: #5eead4;
  --accent-contrast: #042b25;

  /* editor / code syntax (GitHub-dark family) */
  --code-bg: #0d1117;
  --code-chrome: #161b22;
  --code-gutter: #3a414c;
  --code-key: #7ee787;
  --code-string: #a5d6ff;
  --code-number: #79c0ff;
  --code-comment: #8b949e;
  --code-punct: #ff7b72;

  /* publications chart ramp (accent → muted) */
  --chart-1: #2dd4bf;
  --chart-2: #3fb9a8;
  --chart-3: #4f9d9b;
  --chart-4: #5b7aac;
  --chart-5: #8aa0bd;

  /* aliases (legacy names) */
  --color-accent: var(--accent);
  --color-sidebar-bg: var(--surface);

  color-scheme: dark;
}

:root[data-theme="light"] {
  --bg: #ffffff;
  --surface: #f4f7fb;
  --surface-2: #eef2f7;
  --surface-border: #e2e8f0;
  --text: #0f172a;
  --muted: #475569;
  --faint: #94a3b8;
  --accent: #0f766e;
  --accent-hover: #115e59;
  --accent-contrast: #ffffff;

  --code-bg: #f6f8fa;
  --code-chrome: #eaeef2;
  --code-gutter: #afb8c1;
  --code-key: #116329;
  --code-string: #0a3069;
  --code-number: #0550ae;
  --code-comment: #6e7781;
  --code-punct: #cf222e;

  --chart-1: #0f766e;
  --chart-2: #2f6f6a;
  --chart-3: #3f6a8a;
  --chart-4: #5b7aac;
  --chart-5: #94a3b8;

  color-scheme: light;
}

html {
  font-family: "IBM Plex Sans", system-ui, -apple-system, sans-serif;
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
  scroll-behavior: smooth;
}

body {
  background: var(--bg);
  color: var(--text);
}

/* Sticky-header offset for anchor jumps */
[id] { scroll-margin-top: 80px; }

/* Mono utility (editor, micro-labels, dates, chips) */
.font-mono-plex {
  font-family: "IBM Plex Mono", ui-monospace, "SF Mono", Menlo, monospace;
}

/* Reusable section eyebrow heading */
.eyebrow {
  font-size: 0.6875rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  font-weight: 600;
  color: var(--accent);
}

/* Scroll-reveal (Task 6). Hidden until .revealed is added by the island. */
[data-reveal] {
  opacity: 0;
  transform: translateY(12px);
  transition: opacity 0.5s ease, transform 0.5s ease;
}
[data-reveal].revealed {
  opacity: 1;
  transform: none;
}

@media (prefers-reduced-motion: reduce) {
  html { scroll-behavior: auto; }
  [data-reveal] { opacity: 1; transform: none; transition: none; }
}
```

- [ ] **Step 3: Verify build + types**

Run: `just web-build && pnpm --dir web exec astro check`
Expected: build succeeds, `astro check` reports 0 errors. (The page is still light-styled because components haven't migrated yet — that's fine; this task only lays the token layer. Visuals will look mixed until Task 3.)

- [ ] **Step 4: Commit**

```bash
git add web/package.json web/pnpm-lock.yaml web/src/styles/global.css
git commit -m "feat(web): semantic theme tokens + IBM Plex Mono foundation"
```

---

## Task 2: No-flash theme script + ThemeToggle + header wiring

**Files:**
- Create: `web/src/components/ThemeToggle.astro`
- Modify: `web/src/layouts/BaseLayout.astro` (inline head script + body tokens)
- Modify: `web/src/components/Header.astro` (mount toggle + tokens)

- [ ] **Step 1: Add the no-flash inline script to `BaseLayout.astro`**

In `web/src/layouts/BaseLayout.astro`, add this as the **first** child of `<head>` (immediately after `<head>`, before `<meta charset>`). `is:inline` keeps Astro from bundling/deferring it so it runs before first paint:

```astro
    <script is:inline>
      (function () {
        try {
          var saved = localStorage.getItem("cvTheme");
          var theme = saved
            || (window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark");
          document.documentElement.dataset.theme = theme;
        } catch (e) {
          document.documentElement.dataset.theme = "dark";
        }
      })();
    </script>
```

- [ ] **Step 2: Migrate the `BaseLayout` body + footer to tokens**

In the same file, change the `<body>` tag:

```astro
  <body class="min-h-screen bg-[var(--bg)] text-[var(--text)]">
```

And the footer block — replace its classes:

```astro
    <footer class="mx-auto max-w-6xl px-4 py-8 text-xs text-[var(--faint)] md:px-8">
      <p>
        © {new Date().getUTCFullYear()} {data.personal.name.given} {data.personal.name.family} ·
        <a class="underline hover:text-[var(--text)]" href="https://github.com/Jin-HoMLee/jin-ho-lee-cv">Source on GitHub</a>
      </p>
    </footer>
```

- [ ] **Step 3: Create `ThemeToggle.astro`**

Create `web/src/components/ThemeToggle.astro`:

```astro
---
interface Props { class?: string }
const { class: className = "" } = Astro.props;
---
<button
  type="button"
  data-theme-toggle
  class:list={["inline-flex items-center justify-center rounded-md p-1.5 text-[var(--muted)] transition-colors hover:bg-[var(--surface)] hover:text-[var(--text)]", className]}
  aria-label="Toggle light / dark theme"
  aria-pressed="false"
>
  <!-- moon (shown in dark mode → click for light) -->
  <svg data-icon-dark xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
  </svg>
  <!-- sun (shown in light mode → click for dark) -->
  <svg data-icon-light hidden xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <circle cx="12" cy="12" r="4"></circle>
    <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"></path>
  </svg>
</button>

<script>
  const root = document.documentElement;
  const toggles = document.querySelectorAll<HTMLButtonElement>("[data-theme-toggle]");

  function sync(theme: string) {
    root.dataset.theme = theme;
    const isLight = theme === "light";
    for (const btn of toggles) {
      btn.setAttribute("aria-pressed", String(isLight));
      btn.querySelector("[data-icon-dark]")?.toggleAttribute("hidden", isLight);
      btn.querySelector("[data-icon-light]")?.toggleAttribute("hidden", !isLight);
    }
  }

  // Reflect whatever the no-flash script already set.
  sync(root.dataset.theme === "light" ? "light" : "dark");

  for (const btn of toggles) {
    btn.addEventListener("click", () => {
      const next = root.dataset.theme === "light" ? "dark" : "light";
      try { localStorage.setItem("cvTheme", next); } catch { /* private mode */ }
      sync(next);
    });
  }
</script>
```

- [ ] **Step 4: Mount the toggle + migrate `Header.astro` to tokens**

In `web/src/components/Header.astro`:

1. Add the import after the existing `LanguageSwitcher` import:

```astro
import ThemeToggle from "./ThemeToggle.astro";
```

2. Replace the `<header>` open tag classes (translucent, token-based):

```astro
<header class="sticky top-0 z-10 border-b border-[var(--surface-border)] backdrop-blur" style="background-color: color-mix(in srgb, var(--bg) 85%, transparent)">
```

3. The name `<p>` keeps `style="color: var(--color-accent)"` (alias resolves to `--accent`) — leave as-is or change to `var(--accent)`. The headline `<p>` keeps its `data-cv-field="headline"` hook; change its color class:

```astro
      <p class="font-mono-plex text-xs text-[var(--accent)]" data-cv-field="headline">{personal.headline}</p>
```

4. Change the controls row: the "Download PDF" label and PDF buttons:

```astro
    <div class="flex items-center gap-2 text-sm">
      <span class="text-[var(--faint)]">{downloadLabel}:</span>
      <a
        class="rounded-md px-3 py-1.5 text-[var(--accent-contrast)] hover:opacity-90"
        style="background-color: var(--accent)"
        href={`${pdfUrlBase}/cv-en.pdf`}
      >EN</a>
      <a
        class="rounded-md px-3 py-1.5 text-[var(--accent-contrast)] hover:opacity-90"
        style="background-color: var(--accent)"
        href={`${pdfUrlBase}/cv-de.pdf`}
      >DE</a>
      <LanguageSwitcher currentLang={lang} />
      <ThemeToggle />
    </div>
```

- [ ] **Step 5: Verify**

Run: `just web-build && pnpm --dir web exec astro check`
Then: `grep -q 'data-theme-toggle' web/dist/index.html && grep -q 'data-theme-toggle' web/dist/de/index.html && echo OK`
Expected: build + check clean; `OK` printed. Manual: open `web/dist/index.html` (or `just web-dev`), confirm the toggle flips dark↔light and the choice survives a reload with no flash.

- [ ] **Step 6: Commit**

```bash
git add web/src/components/ThemeToggle.astro web/src/components/Header.astro web/src/layouts/BaseLayout.astro
git commit -m "feat(web): dark/light theme toggle with no-flash head script"
```

---

## Task 3: Token migration sweep (all remaining components)

**Goal:** Convert every remaining component from hardcoded `neutral-*`/`white`/`black` colors to tokens. No structural/behavioral change. The publications chart is handled separately in Task 7.

**Files (modify):**
`web/src/components/ProfileSection.astro`, `ExperienceSection.astro`, `ProjectsSection.astro`, `ProjectPage.astro`, `PublicationsList.astro`, `PublicationsCumulative.astro`, `AwardsSection.astro`, `SkillsSidebar.astro`, `EducationSection.astro`, `LanguagesList.astro`, `VolunteerSection.astro`, `LanguageSwitcher.astro`, `TargetSwitcher.astro`.

- [ ] **Step 1: Apply this exact class mapping across all files above**

Replace every occurrence (left → right):

| Old utility | New utility |
|---|---|
| `bg-white` | `bg-[var(--bg)]` |
| `text-neutral-900` | `text-[var(--text)]` |
| `text-neutral-800` | `text-[var(--text)]` |
| `text-neutral-700` | `text-[var(--muted)]` |
| `text-neutral-600` | `text-[var(--muted)]` |
| `text-neutral-400` | `text-[var(--faint)]` |
| `border-neutral-200` | `border-[var(--surface-border)]` |
| `border-neutral-300` | `border-[var(--surface-border)]` |
| `bg-neutral-100` | `bg-[var(--surface)]` |
| `hover:bg-neutral-100` | `hover:bg-[var(--surface-2)]` |
| `hover:bg-neutral-200` | `hover:bg-[var(--surface-border)]` |
| `text-white` | `text-[var(--accent-contrast)]` |
| `hover:text-neutral-900` | `hover:text-[var(--text)]` |
| `bg-[var(--color-sidebar-bg)]` | `bg-[var(--surface)]` |
| `border-l-color`/inline `--color-accent` | `var(--accent)` |

**Two context-specific rules** (apply by meaning, not blind replace):

1. **Section eyebrow headings.** Every section heading currently reads
   `class="mb-N text-xs font-semibold uppercase tracking-wider text-neutral-500"`.
   Replace with `class="eyebrow mb-N"` (keep the existing `mb-N` value; drop the now-redundant `text-xs font-semibold uppercase tracking-wider text-neutral-500`).
2. **`text-neutral-500` elsewhere** (dates, captions, "·" separators, small meta) → `text-[var(--faint)]`.

- [ ] **Step 2: `ExperienceSection.astro` — teal timeline + mono dates (full result)**

This component needs the accent timeline edge and mono dates, so apply explicitly. The `<article>` border and the date `<p>`:

```astro
      <article id={`exp-${exp.id}`} class="border-l-2 border-[var(--accent)] pl-4">
        <header class="mb-2 flex flex-wrap items-baseline justify-between gap-2">
          <h3 class="text-base font-semibold text-[var(--text)]">
            {exp.role}
            <span class="font-normal text-[var(--muted)]"> · {exp.org.name}</span>
          </h3>
          <p class="font-mono-plex text-xs text-[var(--faint)]">{formatPeriod(exp.period, labels)}</p>
        </header>
        <ul class="space-y-1.5 text-sm text-[var(--muted)]">
          {exp.bullets.map((b) => (
            <li class="flex gap-2">
              <span aria-hidden="true" class="text-[var(--accent)]">▸</span>
              <span>
                {b[lang]}
                {b.refs && b.refs.length > 0 && (
                  <span class="ml-1 inline-flex gap-1">
                    {b.refs.map((r) => (
                      <a
                        href={`#${r}`}
                        class="font-mono-plex rounded bg-[var(--surface)] px-1.5 py-0.5 text-xs font-medium text-[var(--accent)] no-underline hover:bg-[var(--surface-2)]"
                      >{r}</a>
                    ))}
                  </span>
                )}
              </span>
            </li>
          ))}
        </ul>
      </article>
```

Note the section heading at the top of this file also becomes `class="eyebrow mb-4"` (Step 1, rule 1). The previous global rule `section#experience article { border-left-color }` is no longer needed — the border color is now set inline above.

- [ ] **Step 3: `SkillsSidebar.astro` — mono chips on surface (skill items)**

Change the skill `<li>` chip class:

```astro
                {g.items.map((item) => (
                  <li class="font-mono-plex rounded bg-[var(--surface)] px-1.5 py-0.5 text-xs text-[var(--muted)]">{item}</li>
                ))}
```

Category name `<h3>` → `text-[var(--text)]`; group label `<p>` → `text-[var(--muted)]`; section heading → `eyebrow` (Step 1).

- [ ] **Step 4: `ProfileSection.astro` — eyebrow + tagline emphasis**

Section heading → `class="eyebrow mb-3"`. Tagline keeps `data-cv-field="tagline"`; make it stand out:

```astro
      <p class="text-lg font-medium text-[var(--text)]" data-cv-field="tagline">{profile.tagline}</p>
      {profile.paragraphs.map((p, i) => (
        <p class="mt-3 leading-relaxed text-[var(--muted)]" data-cv-field={i === 0 ? "lead" : i === 1 ? "second" : undefined}>{p}</p>
      ))}
```

- [ ] **Step 5: `TargetSwitcher.astro` — migrate the control's literal colors**

Apply to its markup (the `<script>` block is untouched):

```astro
  <span class="font-semibold uppercase tracking-wider text-[var(--faint)]">{t.intro}:</span>
```

and each button:

```astro
        class="rounded-md border border-[var(--surface-border)] px-3 py-1.5 font-medium text-[var(--muted)] transition-colors hover:bg-[var(--surface-2)] aria-[pressed=true]:border-transparent aria-[pressed=true]:bg-[var(--accent)] aria-[pressed=true]:text-[var(--accent-contrast)] aria-[pressed=true]:hover:bg-[var(--accent)]"
```

- [ ] **Step 6: Verify the sweep — no hardcoded colors remain**

Run:
```bash
grep -rnE "neutral-[0-9]|bg-white|text-white|bg-black|text-black" web/src/components web/src/layouts web/src/pages || echo "CLEAN"
```
Expected: `CLEAN` (no matches). The only acceptable remaining literals are inside `PublicationsChart.astro`/`PublicationsCumulative.astro` (Task 7) — if those show up, that's expected and handled next.

Run: `just web-build && pnpm --dir web exec astro check`
Expected: build + check clean. Manual: page is now coherently dark; toggle to light looks intentional.

- [ ] **Step 7: Commit**

```bash
git add web/src/components web/src/layouts
git commit -m "refactor(web): migrate components from hardcoded colors to theme tokens"
```

---

## Task 4: CodeHero component + typing island + page wiring

**Files:**
- Create: `web/src/components/CodeHero.astro`
- Modify: `web/src/pages/index.astro`, `web/src/pages/de/index.astro`

- [ ] **Step 1: Create `CodeHero.astro`**

Create `web/src/components/CodeHero.astro`. `roots` is the curated trio (renderer-authored, per spec §6.1); `stack` is derived from real skill items. The YAML is real text server-side (crawlable/selectable); the tagline span carries `data-type` for the typing island. **No `data-cv-field` attributes** (see Design note).

```astro
---
import type { Personal, Profile, Publication, Skills, Lang } from "../types/content";

interface Props {
  personal: Personal;
  profile: Profile;
  publications: Publication[];
  skills: Skills;
  lang: Lang;
}

const { personal, profile, publications, skills, lang } = Astro.props;

// roots — curated positioning trio (renderer-authored, like OG kickers; NOT in content/)
const ROOTS = ["cancer-genomics", "HLA-typing", "neoantigens"];

// stack — derived: lead real tokens flattened across skill categories
const stack = skills.categories
  .flatMap((c) => c.groups.flatMap((g) => g.items))
  .slice(0, 4);

const name = `${personal.name.given} ${personal.name.family}`;
const pubCount = publications.length;
const tabs = ["profile.yaml", "experience.yaml", "publications.bib"];
const eyebrow = lang === "en"
  ? "// one source of truth — pdf · web · json · jsonld · text"
  : "// eine Quelle — pdf · web · json · jsonld · text";
const authorComment = lang === "en" ? "# first / shared-first author" : "# Erst-/geteilte Erstautorenschaft";
const ctaLabel = lang === "en" ? "View work →" : "Projekte ansehen →";
const pdfBase = "https://github.com/Jin-HoMLee/jin-ho-lee-cv/releases/latest/download";
const pdfLabel = lang === "en" ? "download" : "Download";
const lineCount = 8;
---
<section class="py-8" data-code-hero data-reveal>
  <p class="font-mono-plex mb-4 text-xs" style="color: var(--accent-hover)">{eyebrow}</p>

  <div class="overflow-hidden rounded-xl border border-[var(--surface-border)] shadow-2xl" style="background: var(--code-bg)">
    <!-- tab chrome (decorative) -->
    <div class="flex items-center text-[11px]" style="background: var(--code-chrome)" aria-hidden="true">
      {tabs.map((tab, i) => (
        <span class="font-mono-plex px-3 py-2" style={i === 0
          ? "color: var(--text); border-top: 2px solid var(--accent); background: var(--code-bg)"
          : "color: var(--code-comment)"}>{tab}</span>
      ))}
    </div>

    <!-- code body -->
    <div class="flex font-mono-plex text-[13px] leading-[1.9]">
      <div class="select-none py-3 pl-3 pr-2 text-right" style="color: var(--code-gutter)" aria-hidden="true">
        {Array.from({ length: lineCount }, (_, i) => <div>{i + 1}</div>)}
      </div>
      <div class="overflow-x-auto py-3 pr-4">
        <div><span class="ck">name</span>: <span class="cs">{name}</span></div>
        <div><span class="ck">headline</span>: <span class="cs">{personal.headline}</span></div>
        <div><span class="ck">roots</span>: [{ROOTS.map((r, i) => <><span class="cs">{r}</span>{i < ROOTS.length - 1 ? ", " : ""}</>)}]</div>
        <div><span class="ck">stack</span>: [{stack.map((s, i) => <><span class="cs">{s}</span>{i < stack.length - 1 ? ", " : ""}</>)}]</div>
        <div><span class="ck">publications</span>: <span class="cn">{pubCount}</span>&nbsp;&nbsp;<span class="cc">{authorComment}</span></div>
        <div><span class="ck">tagline</span>: <span class="cp">&gt;-</span></div>
        <div>&nbsp;&nbsp;<span class="cs" data-type={profile.tagline}>{profile.tagline}</span><span class="cursor" aria-hidden="true">▋</span></div>
        <div>&nbsp;</div>
      </div>
    </div>
  </div>

  <div class="mt-5 flex flex-wrap items-center gap-4">
    <a href="#experience" class="rounded-lg px-4 py-2 text-sm font-semibold text-[var(--accent-contrast)] hover:opacity-90" style="background: var(--accent)">{ctaLabel}</a>
    <span class="font-mono-plex text-xs text-[var(--faint)]">{pdfLabel} · <a class="underline hover:text-[var(--text)]" href={`${pdfBase}/cv-en.pdf`}>cv-en.pdf</a> / <a class="underline hover:text-[var(--text)]" href={`${pdfBase}/cv-de.pdf`}>cv-de.pdf</a></span>
  </div>
</section>

<style>
  .ck { color: var(--code-key); }
  .cs { color: var(--code-string); }
  .cn { color: var(--code-number); }
  .cc { color: var(--code-comment); }
  .cp { color: var(--code-punct); }
  .cursor { color: var(--accent); animation: blink 1.1s steps(1) infinite; }
  @keyframes blink { 50% { opacity: 0; } }
  @media (prefers-reduced-motion: reduce) { .cursor { animation: none; } }
</style>

<script>
  const el = document.querySelector<HTMLElement>("[data-code-hero] [data-type]");
  if (el) {
    const full = el.dataset.type ?? el.textContent ?? "";
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (!reduce) {
      el.textContent = "";
      let i = 0;
      const tick = () => {
        el.textContent = full.slice(0, ++i);
        if (i < full.length) setTimeout(tick, 16);
      };
      tick();
    }
    // reduced-motion: leave the already-rendered full text in place.
  }
</script>
```

- [ ] **Step 2: Wire `CodeHero` into the EN homepage**

In `web/src/pages/index.astro`, add the import (after the `Header` import):

```astro
import CodeHero from "../components/CodeHero.astro";
```

Then place it directly below the header slot, **above** `TargetSwitcher`:

```astro
  <Header slot="header" personal={data.personal} lang="en" />
  <CodeHero personal={data.personal} profile={data.profile} publications={data.publications} skills={data.skills} lang="en" />
  <TargetSwitcher variants={variantsEn} lang="en" />
```

- [ ] **Step 3: Wire `CodeHero` into the DE homepage**

In `web/src/pages/de/index.astro`, mirror Step 2 with `lang="de"` and the DE data/variants the page already imports (match the existing prop names in that file).

- [ ] **Step 4: Verify**

Run: `just web-build && pnpm --dir web exec astro check`
Then:
```bash
grep -q 'data-code-hero' web/dist/index.html && grep -q 'profile.yaml' web/dist/index.html && grep -q 'data-code-hero' web/dist/de/index.html && echo OK
```
Expected: build + check clean; `OK`. Manual: hero renders as an editor; tagline types once; under DevTools "reduce motion" it shows instantly; with JS disabled the full tagline + YAML are still legible.

- [ ] **Step 5: Commit**

```bash
git add web/src/components/CodeHero.astro web/src/pages/index.astro web/src/pages/de/index.astro
git commit -m "feat(web): CV-as-code hero panel with reduced-motion-safe typing"
```

---

## Task 5: StatBand component + counter island + page wiring

**Files:**
- Create: `web/src/components/StatBand.astro`
- Modify: `web/src/pages/index.astro`, `web/src/pages/de/index.astro`

- [ ] **Step 1: Create `StatBand.astro`**

Four build-derived tiles. The final number renders server-side (JS-off shows it); the counter island resets to 0 and animates up on scroll-into-view unless reduced-motion. `new Date()` here runs at **build time** (Node) — allowed in Astro frontmatter (the footer already uses it).

```astro
---
import type { ContentData, Lang } from "../types/content";

interface Props { data: ContentData; lang: Lang }
const { data, lang } = Astro.props;

const pubs = data.publications.length;
const firstShared = data.publications.filter(
  (p) => p.authorship === "first" || p.authorship === "shared",
).length;
const startYears = data.experience
  .map((e) => parseInt(e.period.start.slice(0, 4), 10))
  .filter((n) => !Number.isNaN(n));
const yearsActive = startYears.length ? new Date().getUTCFullYear() - Math.min(...startYears) : 0;
const FORMATS = 5; // pdf · web · json resume · json-ld · text

type Tile = { value: number; suffix: string; label: string; varName: string };
const tiles: Tile[] = lang === "en"
  ? [
      { value: pubs, suffix: "", label: "peer-reviewed publications", varName: "--chart-1" },
      { value: firstShared, suffix: "", label: "as first / shared-first author", varName: "--chart-4" },
      { value: yearsActive, suffix: "+", label: "years, wet-lab → ML", varName: "--code-punct" },
      { value: FORMATS, suffix: "", label: "output formats, one source", varName: "--code-key" },
    ]
  : [
      { value: pubs, suffix: "", label: "begutachtete Publikationen", varName: "--chart-1" },
      { value: firstShared, suffix: "", label: "als Erst-/geteilte Erstautorenschaft", varName: "--chart-4" },
      { value: yearsActive, suffix: "+", label: "Jahre, Labor → ML", varName: "--code-punct" },
      { value: FORMATS, suffix: "", label: "Ausgabeformate, eine Quelle", varName: "--code-key" },
    ];
---
<section class="py-6" data-stat-band data-reveal>
  <div class="grid grid-cols-2 gap-3 md:grid-cols-4">
    {tiles.map((t) => (
      <div class="rounded-xl border border-[var(--surface-border)] p-4" style="background: var(--surface)">
        <div
          class="font-mono-plex text-3xl font-extrabold tracking-tight"
          style={`color: var(${t.varName})`}
          data-count-to={t.value}
          data-suffix={t.suffix}
        >{t.value}{t.suffix}</div>
        <div class="mt-1 text-xs text-[var(--muted)]">{t.label}</div>
      </div>
    ))}
  </div>
</section>

<script>
  const nums = document.querySelectorAll<HTMLElement>("[data-stat-band] [data-count-to]");
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (nums.length && !reduce && "IntersectionObserver" in window) {
    const animate = (el: HTMLElement) => {
      const target = Number(el.dataset.countTo ?? "0");
      const suffix = el.dataset.suffix ?? "";
      const dur = 900;
      const start = performance.now();
      const step = (now: number) => {
        const p = Math.min(1, (now - start) / dur);
        const eased = 1 - Math.pow(1 - p, 3);
        el.textContent = Math.round(target * eased) + suffix;
        if (p < 1) requestAnimationFrame(step);
      };
      requestAnimationFrame(step);
    };
    const io = new IntersectionObserver((entries) => {
      for (const e of entries) {
        if (e.isIntersecting) { animate(e.target as HTMLElement); io.unobserve(e.target); }
      }
    }, { rootMargin: "0px 0px -10% 0px" });
    for (const n of nums) { n.textContent = "0" + (n.dataset.suffix ?? ""); io.observe(n); }
  }
  // reduced-motion / no-IO: leave the server-rendered final numbers as-is.
</script>
```

- [ ] **Step 2: Wire into both homepages**

In `web/src/pages/index.astro`, add import:

```astro
import StatBand from "../components/StatBand.astro";
```

Place it directly **below** `CodeHero`, above `TargetSwitcher`:

```astro
  <CodeHero personal={data.personal} profile={data.profile} publications={data.publications} skills={data.skills} lang="en" />
  <StatBand data={data} lang="en" />
  <TargetSwitcher variants={variantsEn} lang="en" />
```

Mirror in `web/src/pages/de/index.astro` with `lang="de"` and that page's data variable.

- [ ] **Step 3: Verify**

Run: `just web-build && pnpm --dir web exec astro check`
Then: `grep -q 'data-stat-band' web/dist/index.html && grep -q 'data-stat-band' web/dist/de/index.html && echo OK`
Expected: build + check clean; `OK`. Manual: four tiles; numbers count up when scrolled into view; reduced-motion shows final numbers immediately; JS-off shows final numbers.

- [ ] **Step 4: Commit**

```bash
git add web/src/components/StatBand.astro web/src/pages/index.astro web/src/pages/de/index.astro
git commit -m "feat(web): bento stat band with build-derived metrics"
```

---

## Task 6: Section reveal motion (reduced-motion safe)

**Files:**
- Modify: `web/src/layouts/BaseLayout.astro` (reveal island)
- Modify: `web/src/pages/index.astro`, `web/src/pages/de/index.astro` (add `data-reveal` to section wrappers)

The reveal CSS is already in `global.css` (Task 1). `CodeHero` and `StatBand` already carry `data-reveal`. This task adds the observer and tags the remaining major sections.

- [ ] **Step 1: Add the reveal island to `BaseLayout.astro`**

Add a bundled `<script>` just before `</body>`:

```astro
    <script>
      const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      const els = document.querySelectorAll("[data-reveal]");
      if (reduce || !("IntersectionObserver" in window)) {
        els.forEach((e) => e.classList.add("revealed"));
      } else {
        const io = new IntersectionObserver((entries) => {
          for (const e of entries) {
            if (e.isIntersecting) { e.target.classList.add("revealed"); io.unobserve(e.target); }
          }
        }, { rootMargin: "0px 0px -8% 0px" });
        els.forEach((e) => io.observe(e));
      }
    </script>
```

- [ ] **Step 2: Tag the main content sections**

In `web/src/pages/index.astro`, add `data-reveal` to the two grid columns' wrapping so each major block reveals. Simplest: add it to the `<div>` and `<aside>` inside the grid:

```astro
  <div class="grid grid-cols-1 gap-8 md:grid-cols-[2fr_1fr]">
    <div data-reveal>
      <ExperienceSection ... />
      ...
    </div>
    <aside data-reveal>
      <SkillsSidebar ... />
      ...
    </aside>
  </div>
```

Mirror in `web/src/pages/de/index.astro`.

- [ ] **Step 3: Verify**

Run: `just web-build && pnpm --dir web exec astro check`
Expected: clean. Manual: sections fade/translate in on first scroll; with reduce-motion everything is visible immediately (no hidden content). Confirm no content is stuck invisible if JS fails (the `reduce || !IO` branch reveals all; also test by blocking the script — content should still appear because… note: if JS is fully disabled the inline `[data-reveal]{opacity:0}` would hide content).

- [ ] **Step 4: Add a no-JS safety fallback**

Because `[data-reveal]` starts at `opacity:0`, a JS-disabled visitor would see blank sections. Add a `<noscript>` override in `BaseLayout.astro` `<head>`:

```astro
    <noscript><style>[data-reveal]{opacity:1 !important;transform:none !important;}</style></noscript>
```

Re-run: `just web-build`. Manual: disable JS in DevTools → all sections visible.

- [ ] **Step 5: Commit**

```bash
git add web/src/layouts/BaseLayout.astro web/src/pages/index.astro web/src/pages/de/index.astro
git commit -m "feat(web): subtle scroll reveal motion, reduced-motion and no-JS safe"
```

---

## Task 7: Publications chart dark/light re-theme

**Files:**
- Modify: `web/src/components/PublicationsChart.astro`
- Modify: `web/src/components/PublicationsCumulative.astro` (apply the same token rules)

The chart hardcodes a navy ramp and `neutral-*` text. Move colors to the `--chart-*` tokens (theme-aware) and migrate text/tooltip.

- [ ] **Step 1: `PublicationsChart.astro` — token ramp via CSS variables**

The `colors` map currently holds hex per authorship. SVG `fill` can't take `var()` as an attribute, so apply it via inline `style`. Change the frontmatter `colors` to map authorship → token var **name**, and have `computeArcs` carry a `varName`:

```astro
const colorVars: Record<AuthorshipType, string> = {
  first:         "--chart-1",
  shared:        "--chart-2",
  corresponding: "--chart-3",
  last:          "--chart-4",
  middle:        "--chart-5",
};
```

In `computeArcs`, replace `color: colors[s.key]` with `varName: colorVars[s.key]` (and update the returned object's type accordingly).

In the SVG, set fill via style and the legend swatch likewise:

```astro
    {arcs.map((arc) => (
      <path
        d={arc.d}
        style={`fill: var(${arc.varName})`}
        data-label={arc.label}
        data-count={arc.count}
        data-pct={((arc.count / total) * 100).toFixed(1)}
        class="cursor-pointer"
      />
    ))}
```

```astro
        <span class="inline-block h-3 w-3 shrink-0" style={`background: var(${arc.varName})`} />
```

- [ ] **Step 2: `PublicationsChart.astro` — migrate text + tooltip to tokens**

- Legend `<ul>`: `text-neutral-700` → `text-[var(--muted)]`.
- Σ total line: `text-neutral-500` → `text-[var(--faint)]`.
- Tooltip div: `bg-neutral-900 ... text-white` → `style="background: var(--text); color: var(--bg)"` (so it inverts correctly in both themes); keep the rest of the classes.

- [ ] **Step 3: Apply the same rules to `PublicationsCumulative.astro`**

Migrate any `neutral-*`/hardcoded line/area colors to `--chart-*` (lines/areas) and `--muted`/`--faint` (axes/labels) following the same pattern. Use `var(--accent)` for the primary cumulative line.

- [ ] **Step 4: Verify — no hardcoded colors remain anywhere**

Run:
```bash
grep -rnE "neutral-[0-9]|#1f3a68|#3d5a8a|#5b7aac|#7a99cd|#b8c7df|bg-white|text-white" web/src || echo "CLEAN"
```
Expected: `CLEAN`. Then: `just web-build && pnpm --dir web exec astro check` → clean. Manual: chart legible and on-palette in both themes; tooltip readable in both.

- [ ] **Step 5: Commit**

```bash
git add web/src/components/PublicationsChart.astro web/src/components/PublicationsCumulative.astro
git commit -m "style(web): re-theme publications charts for dark/light tokens"
```

---

## Task 8: OG image dark refresh

**Files:**
- Modify: `web/src/pages/og/[...path].ts` (the `getImageOptions` return)

- [ ] **Step 1: Restyle the OG card to the dark identity**

In `getImageOptions`, replace the visual fields (keep `title`/`description` content and structure):

```ts
    bgGradient: [[10, 12, 18], [12, 24, 38]],
    border: { color: [45, 212, 191], width: 8, side: "inline-start" },
    padding: 60,
    font: {
      title: {
        size: 56,
        color: [232, 237, 244],
        weight: "Bold",
        families: ["IBM Plex Sans", "Inter", "Helvetica", "Arial"],
        lineHeight: 1.15,
      },
      description: {
        size: 22,
        color: [159, 176, 195],
        families: ["IBM Plex Sans", "Inter", "Helvetica", "Arial"],
        lineHeight: 1.4,
      },
    },
```

- [ ] **Step 2: Verify**

Run: `just web-build`
Then confirm the cards regenerated and are non-blank:
```bash
test -f web/dist/og/index-en.png && size=$(stat -f%z web/dist/og/index-en.png 2>/dev/null || stat -c%s web/dist/og/index-en.png); [ "$size" -gt 5120 ] && echo "OG OK ($size bytes)"
```
Expected: `OG OK (...)`. Manual: open `web/dist/og/index-en.png` — dark card, teal edge, light title.

- [ ] **Step 3: Commit**

```bash
git add "web/src/pages/og/[...path].ts"
git commit -m "feat(web-og): dark identity for social share cards"
```

---

## Task 9: CI smoke-checks for the redesign

**Files:**
- Modify: `.github/workflows/pages.yml` (extend the "Smoke-check build outputs" step)

- [ ] **Step 1: Add redesign assertions**

In `.github/workflows/pages.yml`, inside the `Smoke-check build outputs` `run: |` block, **after** the existing Phase 8c target-switcher block (the lines ending at the variant-leak `python3` checks, around line 116) and **before** the step ends, append:

```bash
          # Phase 9: redesign elements reached the built HTML, both langs
          for page in web/dist/index.html web/dist/de/index.html; do
            grep -q 'data-theme-toggle' "$page" || (echo "Theme toggle missing in $page" && exit 1)
            grep -q 'data-code-hero' "$page" || (echo "CodeHero missing in $page" && exit 1)
            grep -q 'data-stat-band' "$page" || (echo "StatBand missing in $page" && exit 1)
            grep -q 'profile.yaml' "$page" || (echo "CodeHero YAML tab missing in $page" && exit 1)
          done
```

The existing Phase 8c assertions (`data-cv-switcher`, the four `data-cv-field` hooks, the variant-text-inlined and head-leak checks) **stay unchanged** — they confirm the redesign didn't regress the switcher.

- [ ] **Step 2: Verify locally (simulate the smoke-check)**

Run:
```bash
just web-build
for page in web/dist/index.html web/dist/de/index.html; do
  for hook in data-theme-toggle data-code-hero data-stat-band data-cv-switcher; do
    grep -q "$hook" "$page" || echo "MISSING $hook in $page"
  done
done
echo "done"
```
Expected: only `done` (no `MISSING` lines).

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/pages.yml
git commit -m "ci(pages): assert redesign elements present in built HTML"
```

---

## Task 10: Final verification + CLAUDE.md phasing update

**Files:**
- Modify: `CLAUDE.md` (Phasing table)

- [ ] **Step 1: Full green-bar verification**

Run each, confirm all pass:
```bash
just validate    # JSON Schema + cross-ref + bib  → green (content untouched)
just test        # pytest                          → green
just lint        # ruff                            → green
just web-build   # render + astro build            → succeeds
pnpm --dir web exec astro check   # types          → 0 errors
grep -rnE "neutral-[0-9]|bg-white|text-white|#1f3a68" web/src || echo "NO HARDCODED COLORS"
```
Expected: all green; `NO HARDCODED COLORS`.

- [ ] **Step 2: Manual acceptance pass (document results in the PR test plan)**

Run `just web-dev` and confirm:
- [ ] Dark by default; toggle → polished light theme; reload keeps choice; **no flash**.
- [ ] Hero renders as an editor with real data; tagline types once; YAML legible/selectable.
- [ ] Stat band: four tiles; numbers count up on scroll.
- [ ] `prefers-reduced-motion` (DevTools → Rendering → Emulate): no typing, no count-up, no reveal animation; all content shown.
- [ ] JS disabled: full page renders (hero YAML, stats final numbers, all sections visible).
- [ ] EN (`/`) and DE (`/de/`) both render; language switch works.
- [ ] Target switcher still swaps headline/tagline/lead/second; preference persists.
- [ ] Keyboard: toggle, switchers, links reachable with visible focus rings.
- [ ] Mobile width: single-column reflow is clean.

- [ ] **Step 3: Update the CLAUDE.md Phasing table**

In `CLAUDE.md`, add a row to the Phasing table after the `8c` row:

```markdown
| 9 | Web design overhaul (2026 dark-technical) | ✅ Done (merged 2026-05-31, PR #XX, commit `XXXXXXX`) |
```

(Fill PR # and merge commit when the branch merges; until then mark the status `🚧 In progress`.)

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: mark Phase 9 row in CLAUDE.md phasing table"
```

- [ ] **Step 5: Finish the branch**

Use `superpowers:finishing-a-development-branch` to open a PR (or `--no-ff` merge to `main`, per repo convention). Verify each PR **Test plan** checkbox against Step 2 results before considering the PR done.

---

## Self-review notes

- **Spec coverage:** §3 identity → Tasks 1,4,5; §4 theme system → Tasks 1,2; §5 architecture → Tasks 4,5,6 + page wiring; §6.1 CodeHero (curated roots / derived stack) → Task 4; §6.2 StatBand → Task 5; §6.3 ThemeToggle → Task 2; §7 component restyle → Task 3; §8 fonts+motion → Tasks 1,4,5,6; §9 OG → Task 8; §10 a11y → Tasks 2,4,5,6 (reduced-motion, no-JS, focus) + Task 10 manual; §11 invariants → preserved (Task 3 keeps `data-cv-*`; Task 9 asserts) ; §12 CI → Task 9; §13 tests → Task 10; §15 success criteria → Task 10 acceptance pass.
- **Placeholder scan:** none — every code step has concrete content; the only "fill in" is the PR#/commit in the CLAUDE.md row (genuinely unknown until merge).
- **Type/attribute consistency:** hook names are consistent across tasks and CI — `data-theme-toggle` (Task 2/9), `data-code-hero` + `data-type` (Task 4/9), `data-stat-band` + `data-count-to`/`data-suffix` (Task 5/9), `data-reveal` (Tasks 1,4,5,6). Preserved 8c contracts: `data-cv-switcher`, `data-cv-target`, `data-cv-field` (Task 3 keeps them; CodeHero deliberately omits `data-cv-field`).
```
