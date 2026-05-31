# Design: Phase 9 — Web design overhaul (2026 dark-technical)

**Date:** 2026-05-31
**Owner:** Jin-Ho Lee
**Parent spec:** [`2026-05-21-codified-cv-design.md`](./2026-05-21-codified-cv-design.md)
**Predecessor work:** Phase 8c — Web target switcher (merged 2026-05-31, PR #39, commit `6ced593`)

## 1. Context

Phases 0–8c built the codified-CV pipeline and a competent, conventional website: Astro 5 + Tailwind 4, IBM Plex Sans, a single navy accent (`#1f3a68`), a light two-column resume layout. It is correct and accessible but visually dated (≈2020). Phase 9 is a **full restructure** of the website's look and architecture into a refined-dark, "CV-as-code" experience for 2026.

This is a **renderer-only change**. It honors the core architectural principle: *content is content, renderers are interchangeable.* Nothing under `content/` changes; we restyle and restructure `web/` only. Every existing feature keeps working (see §11).

## 2. Goal & boundary

**Goal:** Restructure the Astro site so it reads as the portfolio of someone who builds polished, technical things — without sacrificing recruiter-scannability.

**The non-negotiable boundary — what must NOT change:**
- `content/` (YAML + BibTeX), `content.private/`, the schema, all Python loaders/renderers.
- The data the web consumes: `render_web_data.py` output (`content.{en,de}.json`, `content.{en,de}.variants.json`). *(One additive exception: §6.2 may add build-derived stat fields to the web JSON; this is a web-data concern, not a `content/` change.)*
- EN/DE i18n routing (`/` and `/de/`), the target switcher (comp-bio/ds-ml), PDF download links, project deep-dive pages, JSON-LD, sitemap, `robots.txt`, GoatCounter analytics, GSC verification.

We change `web/src/**` (styles, layouts, components, the OG route) and add CI assertions. PDFs and machine formats are untouched.

## 3. Visual identity — locked decisions

Settled during brainstorming (visual companion, 2026-05-31):

| Aspect | Decision |
|---|---|
| Aesthetic | **Refined Dark** — premium, restrained, generous space; mono only for micro-labels |
| Hero | **CV-as-Code editor panel** — renders real `profile.yaml` fields as syntax-highlighted YAML |
| Layout | **Editor hero → bento stat band → restyled two-column** |
| Theme mode | **Dark default + light toggle** (respects `prefers-color-scheme`; manual override persisted) |
| Motion | **Subtle** — hero tagline types once, stat counters tick up on scroll, gentle section reveals; all gated by `prefers-reduced-motion` |
| Accent | **Teal** — `#2dd4bf` on dark, `#0f766e` on light (contrast) |
| OG images | **Refresh to dark** to match shared-link previews |
| Phasing | **One Phase 9**, branch `phase-9-web-redesign`, `--no-ff` merge |

The single bold flourish (the editor hero) earns attention; the calm body earns trust.

## 4. Theme system

The current `global.css` hardcodes two variables (`--color-accent`, `--color-sidebar-bg`) and uses Tailwind utility classes with literal neutrals (`text-neutral-900`, `bg-white`) sprinkled across components. That cannot express two themes. Phase 9 replaces it with a **semantic token layer**.

### 4.1 Tokens

Define semantic CSS custom properties on `:root` (dark, the default) and override under `[data-theme="light"]`:

| Token | Dark | Light | Used for |
|---|---|---|---|
| `--bg` | `#0a0c12` | `#ffffff` | page background |
| `--surface` | `#0e1520` | `#f4f7fb` | cards, stat tiles, sidebar |
| `--surface-border` | `#1c2636` | `#e2e8f0` | tile/section borders |
| `--text` | `#e8edf4` | `#0f172a` | primary text |
| `--muted` | `#9fb0c3` | `#475569` | secondary text |
| `--faint` | `#5b6b80` | `#94a3b8` | dates, captions |
| `--accent` | `#2dd4bf` | `#0f766e` | eyebrows, buttons, timeline edge, stat numbers, links |
| `--accent-contrast` | `#042b25` | `#ffffff` | text on accent fills |
| `--code-bg` | `#0d1117` | `#f6f8fa` | editor panel |
| `--code-*` (key/string/number/comment/punct) | GitHub-dark ramp | GitHub-light ramp | YAML syntax colors |

Tailwind 4 reads these via the `@theme` block / arbitrary `var(--token)` utilities. Components reference **tokens only** — no literal `neutral-*`/`white`/`black` colors after the migration. This is the bulk of the mechanical work: a sweep replacing hardcoded color utilities with token-backed ones.

### 4.2 Mode selection & no-flash

- Default: dark. Honor `prefers-color-scheme: light` on first visit (no stored preference).
- A `ThemeToggle` writes `localStorage["cvTheme"] = "dark" | "light"` and sets `document.documentElement.dataset.theme`.
- A tiny **inline** `<head>` script (runs before paint) reads `localStorage`/`prefers-color-scheme` and sets `data-theme` synchronously, preventing a flash of the wrong theme. This is the one inline script; everything else is bundled.

## 5. Page architecture

New top-to-bottom structure (replaces today's header → TargetSwitcher → ProfileSection → 2-col grid):

```
┌ Header (sticky, translucent, themed) ───────────────────────┐
│  Name · headline(mono)   …   [target ▾] [EN|DE] [PDF] [◐]    │
├ CodeHero ───────────────────────────────────────────────────┤
│  // one source of truth — pdf · web · json · jsonld · text   │
│  ┌ profile.yaml │ experience.yaml │ publications.bib ──────┐ │
│  │ name / headline / roots / stack / publications / …      │ │
│  │ tagline: >- (types out once)                            │ │
│  └─────────────────────────────────────────────────────────┘ │
│  [ View work → ]   download · cv-en.pdf / cv-de.pdf          │
├ StatBand (bento, 4 tiles) ──────────────────────────────────┤
│  [15 pubs] [N first/shared] [10+ yrs] [5 formats]           │
├ Two-column ─────────────────────────────────────────────────┤
│  main:  Experience (teal timeline) · Projects · Publications │
│         (+ re-themed chart) · Awards                         │
│  aside: Skills (mono chips) · Education · Languages · Volunt.│
├ Footer (themed) ────────────────────────────────────────────┘
```

The two-column content grid is **retained** (it already serves scannability) but restyled to tokens. The novelty is the hero + stat band above it and the dark identity throughout.

**Header controls.** The header gains a `ThemeToggle`. The existing `LanguageSwitcher` and PDF links stay. The `TargetSwitcher` may live in the header or remain at the top of the profile — its `[data-cv-field]` hooks (from 8c) decouple it from placement, so this is a low-risk visual choice finalized in implementation. Its swap logic is unchanged.

## 6. New components

### 6.1 `CodeHero.astro`

Renders the hero editor panel. Reads **real** resolved fields from the page's content data (no new content):
- `name` ← `personal.name`, `headline` ← `personal.headline`
- `roots`, `stack` — **hybrid sourcing** (decision 2026-05-31: derive `stack`, curate `roots`):
  - `stack` ← **derived**: a short representative selection of real tokens flattened from `skills.categories[].groups[].items` (e.g. the lead items spanning the categories). Auto-updates with the skills data; stays truthful with no maintenance.
  - `roots` ← **curated** in the component: the tight positioning trio `cancer-genomics · HLA-typing · neoantigens`. Those terms live only in tagline prose (derivation can't cleanly extract them) and the broader skill-pillar names read less punchy, so this one line is a small constant list held in `CodeHero.astro` — **not** a `content/` edit, exactly like OG-card kickers are already renderer-authored. ~6 words maintained by hand.
  - Both are pure presentation computed in `CodeHero.astro`; **no `content/` edit**. Sourcing is one small function per line, so either line can flip derived↔curated later trivially.
- `publications` ← `publications.length`
- `tagline` ← `profile.tagline`

Markup: editor chrome (three inert tabs: `profile.yaml`, `experience.yaml`, `publications.bib`), gutter line numbers, syntax-colored YAML using `--code-*` tokens. The tagline value carries a `[data-type]` hook; a small bundled island types it once on load (reduced-motion → rendered instantly). The YAML is **real, readable text** server-side (crawlable, selectable); the typing effect only animates an already-present string.

The hero is **decorative-but-truthful**: it must degrade to legible static YAML with JS off and in reduced-motion.

### 6.2 `StatBand.astro`

Four bento tiles, values **derived at build** from content the web already imports. Cleanly-derivable set (no hardcoded magic numbers):

| Tile | Source |
|---|---|
| Publications | `publications.length` |
| First / shared-first author | count of `publications` where `authorship ∈ {first, shared}` |
| Years active | `currentYear − min(experience[].period.start year)` (→ "10+") |
| Output formats | constant `5` (PDF · web · JSON Resume · JSON-LD · text) — the codified-CV brag |

Derivation happens in the component (preferred — pure presentation, content untouched) **or** in `render_web_data.py` as additive numeric fields if cleaner. Either way it is build-time; no `content/` change. Each tile's number animates a count-up via `IntersectionObserver` (reduced-motion → final value shown immediately). Labels are localized via existing `labels`/inline strings.

### 6.3 `ThemeToggle.astro`

Sun/moon control, vanilla-JS island (same pattern as `TargetSwitcher`/`PublicationsChart`). Toggles `data-theme`, persists to `localStorage`, updates `aria-pressed`/`aria-label`. With JS off it is hidden (`no-js`/`js` class gate) and the page renders dark (or the `prefers-color-scheme` choice via the inline head script). No framework added.

## 7. Restyle existing components

Token migration + visual refresh for every component, no behavioral change:
`BaseLayout`, `Header`, `ProfileSection`, `ExperienceSection` (teal `--accent` timeline edge, mono dates), `ProjectsSection`, `ProjectPage`, `PublicationsList`, `AwardsSection`, `SkillsSidebar` (mono chips on `--surface`), `EducationSection`, `LanguagesList`, `VolunteerSection`, `LanguageSwitcher`, `TargetSwitcher`.

**`PublicationsChart.astro` / `PublicationsCumulative.astro`** currently hardcode a navy authorship ramp (`#1f3a68 … #b8c7df`) and Tailwind `neutral-*` text. Re-theme to a **teal-family ramp** driven by `--code-*`/accent tokens, make text/tooltip theme-aware (the tooltip's `bg-neutral-900` works on dark but needs a light variant). Chart geometry/logic is unchanged.

## 8. Typography & motion

- **Fonts:** keep IBM Plex Sans (body). Add **IBM Plex Mono** (`@fontsource/ibm-plex-mono`, weights 400/500) for the editor panel, eyebrow/micro-labels, dates, and skill chips. Display sizes scale up (hero name, section rhythm).
- **Motion** (all vanilla-JS islands, all behind `@media (prefers-reduced-motion: reduce)` → no animation):
  1. Hero tagline typing (once, on load).
  2. Stat count-up on scroll-into-view (`IntersectionObserver`).
  3. Gentle section fade/translate-in on first scroll-into-view.
  No layout shift; animations affect opacity/transform/text only.

## 9. OG image dark refresh

`web/src/pages/og/[...path].ts` currently emits light cards: `bgGradient: [[244,247,251]]`, navy border/title, gray description. Refresh `getImageOptions` to the dark identity:
- `bgGradient` → dark (`[[10,12,18]]`, optional subtle two-stop).
- `border` → teal `[45,212,191]`, `inline-start`.
- title color → light `[232,237,244]`; description → muted `[159,176,195]`.
- Keep IBM Plex Sans; optionally render the kicker in a mono family if available to the canvas renderer (fallback to sans).

Page selection, dimensions (1200×630), per-page content, and the `[...path].ts` naming caveat are unchanged. The 1200/630 `<meta>` in `BaseLayout` stays.

## 10. Accessibility

- WCAG **AA** contrast verified in **both** themes (text on `--bg`/`--surface`, accent buttons, chart colors, code syntax).
- All motion respects `prefers-reduced-motion`.
- Keyboard: theme toggle, target switcher, language switcher, links, and project anchors are focusable with visible `--accent` focus rings; logical tab order preserved.
- The editor hero is supplementary; its information (name, headline, tagline) is also present as real text, so screen-reader users lose nothing. Decorative chrome (tabs, gutter numbers) is `aria-hidden`.
- Semantic structure (`<header>`/`<main>`/`<section>`/`<h1..h3>`/`<footer>`) preserved; one `<h1>` per page.

## 11. Invariants — what keeps working (regression budget)

- **i18n:** `/` (EN) and `/de/` (DE) render; `LanguageSwitcher` links across; `<html lang>` correct.
- **Target switcher (8c):** comp-bio/ds-ml/bridge swaps still mutate `[data-cv-field]` text; `localStorage` persistence intact; bridge stays SEO-canonical.
- **SEO/meta:** `<title>`, `<meta description>`, canonical, OG/Twitter tags, JSON-LD `Person`, sitemap URL count, `robots.txt`, GSC verification — all unchanged in value (only OG *image styling* changes, not the tags' presence/targets).
- **PDF links, project pages, analytics** — unchanged.
- **Machine formats / PDFs** — entirely untouched (different renderers).

## 12. CI / Pages workflow

`.github/workflows/pages.yml` builds the site. Extend its smoke-check step (mirroring 8c's grep assertions) to confirm the redesign reached the built HTML:
- theme toggle present: `grep -q 'data-theme-toggle' web/dist/index.html` (and `/de/`).
- CodeHero rendered real data: assert a known token (e.g. `headline` value or `profile.yaml` tab) appears in `web/dist/index.html`.
- stat band present: `grep -q 'data-stat-band'`.
- **retain** the existing target-switcher (`data-cv-switcher`) assertion and the **22-URL** sitemap check.
Release artifacts (6 PDFs + machine formats) unchanged.

## 13. Validation & tests

- **Content layer:** `just validate && just test && just lint` stay green **by construction** — `content/`, schema, and Python are untouched. If §6.2 adds derived numeric fields to web JSON, a small `tests/` assertion covers their presence/correctness (mirroring `test_render_web_data_variants.py`).
- **Build:** `pnpm --dir web build` succeeds; `astro check` passes (TS types).
- **Manual pass (documented in PR test plan):** dark↔light toggle (incl. no-flash on reload), `prefers-reduced-motion` disables animation, EN/DE both render, target switcher still swaps, keyboard nav + focus rings, mobile (single-column) reflow, Lighthouse a11y/perf not regressed.

## 14. Non-goals

- No `content/` changes; no new content fields surfaced to humans.
- No change to PDFs, JSON Resume, JSON-LD, or plain-text renderers.
- No new client framework — vanilla-JS islands only (consistent with the repo).
- No new routes, no per-variant SEO, no sitemap growth.
- No CMS, no server runtime, no client-side data fetching.
- Not a content audit or repositioning (that was 7/8a) — purely presentation.

## 15. Success criteria

- ✅ Site renders dark by default; toggle switches to a polished light theme; choice persists across reloads with no flash.
- ✅ Hero shows a syntax-highlighted, real-data editor panel; tagline types once (instant under reduced-motion); YAML is legible/selectable with JS off.
- ✅ Stat band shows four build-derived tiles; numbers count up on scroll (instant under reduced-motion).
- ✅ All sections restyled to tokens; no hardcoded `neutral-*`/`white`/`black` colors remain; publications chart is theme-aware.
- ✅ OG cards render in the dark identity.
- ✅ Every §11 invariant holds: i18n, target switcher, PDF links, project pages, SEO tags, JSON-LD, sitemap (22 URLs), analytics.
- ✅ WCAG AA contrast in both themes; reduced-motion honored; keyboard-navigable.
- ✅ `just validate && just test && just lint` green; `pnpm --dir web build` + `astro check` succeed; CI smoke-checks pass.

## 16. Commits / branch

Branch `phase-9-web-redesign`, `--no-ff` merge to `main`. Indicative atomic commits (final order set by the plan):

1. `feat(web): semantic theme tokens + dark/light system with no-flash toggle` — `global.css` token layer, inline head script, `ThemeToggle.astro`, header wiring.
2. `refactor(web): migrate components from hardcoded colors to theme tokens` — the sweep across all existing components + `BaseLayout`.
3. `feat(web): CV-as-code hero panel` — `CodeHero.astro` + typing island, page wiring.
4. `feat(web): bento stat band with build-derived metrics` — `StatBand.astro` (+ derivation, tests if in `render_web_data.py`).
5. `feat(web): subtle scroll/section motion, reduced-motion safe` — section reveal island.
6. `style(web): re-theme publications chart for dark/light` — chart token migration.
7. `feat(web-og): dark identity for social share cards` — OG route restyle.
8. `ci(pages): assert redesign elements in built HTML` — `pages.yml` smoke-checks.
9. `docs: mark Phase 9 row in CLAUDE.md phasing table` — final task per repo convention.

A final verification pass (`just validate && just test && just lint`, `pnpm --dir web build`, manual dark/light + reduced-motion + i18n + switcher in `astro dev`) confirms end-to-end; it commits nothing.
