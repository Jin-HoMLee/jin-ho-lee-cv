# Design: Phase 3 — Astro Website + GitHub Pages

**Date:** 2026-05-25
**Owner:** Jin-Ho Lee
**Parent spec:** [`2026-05-21-codified-cv-design.md`](./2026-05-21-codified-cv-design.md)
**Predecessor phase:** Phase 2b — DE translations + bilingual CI release (merged 2026-05-22, commit `ee1290a`)

## 1. Scope

Phase 3 ships a bilingual static website at `https://jin-homlee.github.io/jin-ho-lee-cv/` (and `/de/`) that renders the same content the PDF renders, deployed automatically on every push to `main`. The website becomes Jin-Ho's primary professional landing page; the PDF stays available via prominent download links.

The site is a single-page CV view per language. Per-project deep-dive pages, the publications chart, custom domain, and JSON-LD/JSON Resume/plain text outputs are deferred to Phases 4–5.

## 2. Goal

After Phase 3:

- `https://jin-homlee.github.io/jin-ho-lee-cv/` renders the EN CV with a language switcher to the DE version at `/de/`.
- Every push to `main` redeploys the site within a few minutes.
- The site reuses 100% of the content in `content/` — no copy-paste, no duplicate source-of-truth.
- The site renders Jin-Ho's photo, links to the latest EN+DE PDFs, and shows all CV sections (profile, experience with inline project details, skills, education, languages, volunteer, publications grouped by type).
- Phase 4's JSON renderers can plug into the same content layer without changes to Phase 3 code.

## 3. Non-goals

- **Per-project deep-dive pages** (`/projects/L1/`) — Phase 5.
- **Publications authorship pie chart** — Phase 4.
- **JSON-LD `<script>` tag, JSON Resume, plain text** — Phase 4.
- **Custom domain** — Phase 5; the default `*.github.io` URL is fine for v1.
- **OG / social-share images** — Phase 5.
- **PR previews of the deployed site** — not in scope. PRs already get PDF previews via Phase 2a/2b. A site preview adds CI complexity for marginal value at this stage.
- **Dark mode** — additive later, no architectural cost from omitting it now.
- **Site-wide search, analytics, contact form** — not in scope.
- **Visual regression on the site** — out of scope per parent spec §8 (same rationale as for PDFs).
- **i18n beyond EN+DE** — schema already accommodates more locales; no Korean renderer work here.

## 4. Architecture

The site is a thin Astro presentation layer over the existing Python content loader. A new build step dumps the fully-resolved bilingual content to JSON; Astro imports the JSON at build time and emits static HTML.

```
                                       ┌─ pdf/build.py                  (UNCHANGED)
content/*.yaml         ──────┐         │
content/projects/*.{en,de}.yaml ──┐    │
content/labels.yaml          ────┼────→├─ scripts/content_loader.py    (UNCHANGED)
content/publications.bib     ────┘    │  resolve_langstrings, load_publications
                                       │
                                       ↓
                       scripts/render_web_data.py             (NEW)
                                       │
                                       ↓
                       web/src/data/content.{en,de}.json      (NEW; gitignored)
                                       │
                                       ↓
                       Astro pages import data, emit static HTML
                                       │
                                       ↓
                              web/dist/
                                       │
                       ┌───────────────┴────────────────┐
                       ↓                                 ↓
            .github/workflows/pages.yml          just web-dev / web-build / web-data
                  (NEW)                                (NEW recipes)
                       │
                       ↓
                GitHub Pages deploy
```

Why intermediate JSON instead of Astro Content Collections reading YAML directly: the alternative requires re-implementing in TypeScript what `scripts/content_loader.py` and `scripts/bib_loader.py` already do (multi-file project loading, bilingual fallback resolution, BibTeX parsing). That duplication risks schema drift and contradicts the parent spec's core principle ("renderers are interchangeable scripts that consume content"). Python stays the single parser; Astro is one of several consumers.

## 5. Detailed changes

### 5.1 New script: `scripts/render_web_data.py`

A thin orchestrator over `content_loader.load_content`. Produces two JSON files for Astro consumption.

**Signature:**

```bash
uv run python -m scripts.render_web_data
# writes web/src/data/content.en.json and web/src/data/content.de.json
```

**Behavior:**

1. For each `lang in ("en", "de")`:
   - Call `content_loader.load_content(content_dir=Path("content"), private_path=None, lang=lang)`.
     - `private_path=None` is **mandatory and hard-coded**, not a CLI flag. The web build must never see PII. Tests assert this.
   - Resolve all langstrings to the chosen language using `langstring.resolve_langstrings(tree, lang=lang)` so the JSON contains plain strings rather than `{en: ..., de: ...}` maps.
   - Convert `Publication` dataclass instances (from `bib_loader`) to plain dicts; drop the `raw` field (BibTeX-specific, not needed for rendering).
   - Convert `Path` objects (e.g. `personal.photo`) to forward-slash strings.
2. Write to `web/src/data/content.{lang}.json` with `indent=2, sort_keys=False, ensure_ascii=False`.
3. Exit non-zero with a clear error if any required content file is missing.

**Output JSON shape** (per language, after langstring resolution):

```json
{
  "personal": {
    "name": { "given": "Jin-Ho", "family": "Lee" },
    "headline": "Bioinformatics | Data Science | Consulting",
    "email": "...",
    "location": { "city": "Mannheim", "country": "GER" },
    "links": { "linkedin": "...", "github": "...", "researchgate": "...", "orcid": null },
    "photo": "assets/photo.jpg"
  },
  "profile": { "tagline": "...", "paragraphs": ["...", "..."] },
  "skills": { "categories": [...] },
  "education": [...],
  "experience": [
    { "id": "cintellic", "org": {...}, "role": "Consultant, ...", "period": {...},
      "bullets": [ { "text": "Architecting ...", "refs": ["C2"] }, ... ] }
  ],
  "projects": { "L1": {...}, "L2": {...}, ... },
  "languages": [...],
  "volunteer": [...],
  "publications": [
    { "key": "lee2021superres", "title": "...", "year": 2021, "type": "book-chapter",
      "authorship": "first", "authors": ["Lee, J.", "Hausmann, M."], "venue": "..." }
  ],
  "labels": {
    "sections": { "profile": "Profile", "experience": "Experience", ... },
    "months_abbr": ["Jan", "Feb", ...],
    "proficiency": { "native": "native", "fluent": "fluent", ... }
  }
}
```

`labels` is also resolved to the chosen language, so Astro components do not need to know how to pick locales — each JSON file is self-contained for one rendering pass.

### 5.2 New file: `web/` (Astro project)

A standard Astro 5 + Tailwind 4 project, scaffolded inside `web/`. Files committed:

```
web/
├── .gitignore                 # node_modules, dist, src/data/*.json
├── astro.config.mjs           # base, i18n, integrations
├── package.json
├── pnpm-lock.yaml
├── tsconfig.json
├── public/
│   ├── favicon.svg            # (optional; falls back to Astro default)
│   └── (photo.jpg goes here, gitignored — see §5.5)
└── src/
    ├── layouts/
    │   └── BaseLayout.astro
    ├── components/
    │   ├── Header.astro
    │   ├── LanguageSwitcher.astro
    │   ├── ProfileSection.astro
    │   ├── ExperienceSection.astro
    │   ├── ProjectDetails.astro
    │   ├── SkillsSidebar.astro
    │   ├── EducationSection.astro
    │   ├── LanguagesList.astro
    │   ├── VolunteerSection.astro
    │   └── PublicationsList.astro
    └── pages/
        ├── index.astro        # EN root
        └── de/
            └── index.astro    # DE root
```

**Component contract:** each section component takes its slice of the content JSON as a typed prop (e.g. `ExperienceSection({ experience, projects, labels })`). No component reads JSON files directly — pages do the import once and pass props down. Keeps components testable in isolation and reusable for the eventual per-project pages in Phase 5.

**Page shape:** `pages/index.astro` and `pages/de/index.astro` both look like:

```astro
---
import contentEn from "../data/content.en.json";
import BaseLayout from "../layouts/BaseLayout.astro";
import ProfileSection from "../components/ProfileSection.astro";
// ... (DE page imports content.de.json)
const data = contentEn;
---
<BaseLayout lang="en" data={data}>
  <ProfileSection profile={data.profile} labels={data.labels} />
  <ExperienceSection experience={data.experience} projects={data.projects} labels={data.labels} />
  <!-- ... -->
</BaseLayout>
```

The two pages are near-duplicates differing only in import + `lang` prop. Acceptable duplication; consolidation is a one-line refactor when more locales arrive.

### 5.3 `astro.config.mjs`

```js
import { defineConfig } from "astro/config";
import tailwind from "@astrojs/tailwind";

export default defineConfig({
  site: "https://jin-homlee.github.io",
  base: "/jin-ho-lee-cv/",
  trailingSlash: "always",
  i18n: {
    defaultLocale: "en",
    locales: ["en", "de"],
    routing: { prefixDefaultLocale: false },
  },
  integrations: [tailwind()],
});
```

- `base` matches the GitHub Pages project-site subpath. All internal links must use `import.meta.env.BASE_URL` or Astro's built-in `<a>` rewriting.
- `prefixDefaultLocale: false` puts EN at `/` and DE at `/de/`.

### 5.4 Design language

Mirror the PDF spirit, adapted to web:

- **Typography:** IBM Plex Sans, served via `@fontsource/ibm-plex-sans` package (installed locally; no Google Fonts third-party request).
- **Color:** blue accent (the PDF's primary blue, exact hex to be lifted from `pdf/styles.typ`). Neutral backgrounds. High contrast.
- **Layout (desktop ≥ 1024px):** two-column. Main column (left, ~65% width) holds profile, experience+projects, education, volunteer, publications. Sidebar (right, ~35%) holds skills, languages, contact links. Roughly mirrors the PDF's column split.
- **Layout (mobile):** single column, sidebar content stacks below main content.
- **Header:** sticky on scroll, contains name + headline (compact), language switcher, "Download PDF" button group (EN / DE links).
- **Project rendering:** each experience entry's bullets that reference projects (`refs: [L1, L2]`) expand inline as a small details/summary block or a card cluster below the bullet. Each project card is anchored as `#L1`, `#C2`, etc., so external links land at the right place.
- **Publications:** grouped by `type` (`article`, `book-chapter`, `conference`, `book`), each group sorted by year descending. Each entry shows title, authors (with Jin-Ho's name bolded), venue, year, and `authorship` badge. No chart in Phase 3.
- **Print stylesheet:** out of scope. Users wanting print get the PDF.

### 5.5 Photo handling

The local-only `assets/photo.jpg` (gitignored per parent spec) drives the *private* PDF build. The website needs its own photo asset, separate from that.

**Convention:**

- The site looks for `web/public/photo.jpg` at build time. Astro's `public/` folder ships its contents verbatim, so the photo lands at `/jin-ho-lee-cv/photo.jpg` after deploy.
- `web/public/photo.jpg` is **gitignored** (added to `web/.gitignore`). Jin-Ho drops a web-suitable photo there locally before pushing, or commits one if he chooses (rm from gitignore at that point).
- The `ProfileSection.astro` component renders the `<img>` only when `data.personal.photo` is truthy AND the photo file exists at build time. Implementation: a small inline check in `pages/index.astro` that sets `hasPhoto = await import("fs").then(fs => fs.existsSync("public/photo.jpg"))` or equivalent Astro-idiomatic file check at build time. If the file is absent, the component renders without a photo and reflows gracefully.
- The site does **not** depend on `assets/photo.jpg` from the repo root. PDF and web photo lifecycles are independent.

**Deployment implication:** the deployed site has no photo until Jin-Ho commits one (or the deploy workflow grows a step to fetch it from elsewhere). This is intentional — public-photo decisions are personal and should not be coupled to merging this phase.

### 5.6 Tooling pins

- **Node:** pin to the current LTS in `.nvmrc` (project root). At time of writing, Node 22 (LTS). The CI workflow reads `.nvmrc` for `setup-node`.
- **pnpm:** pin major in `package.json` `packageManager: "pnpm@10.x"`. CI uses `pnpm/action-setup@v4` matching.
- **Astro:** `^5.0.0` in `package.json`. Lockfile pins exact.
- **Tailwind:** `@astrojs/tailwind@^6.0.0` + `tailwindcss@^4.0.0`.
- **Renovate / Dependabot:** out of scope for Phase 3; add later if dependency churn becomes a problem.

### 5.7 New workflow: `.github/workflows/pages.yml`

Separate from `ci.yml` for the same reasons Phase 2a kept release in one file: deploy-web is a distinct artifact with distinct lifecycle and failure modes. Keeping `ci.yml` focused on validate + PDF + release prevents one giant workflow from being hard to reason about.

**Trigger:** `push: branches: [main]` only. PRs do not deploy.

**Concurrency:** group by `pages` with `cancel-in-progress: true` (only the newest commit's deploy matters).

**Permissions (top-level):**

```yaml
permissions:
  contents: read
  pages: write
  id-token: write
```

**Jobs:**

```yaml
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v8
        with: { version: "0.5.x" }
      - run: uv python install 3.12
      - run: uv sync --all-groups
      - uses: actions/setup-node@v4
        with:
          node-version-file: .nvmrc
      - uses: pnpm/action-setup@v4
        with: { version: 10 }
      - name: Render web JSON
        run: uv run python -m scripts.render_web_data
      - name: Install web deps
        run: pnpm --dir web install --frozen-lockfile
      - name: Build site
        run: pnpm --dir web build
      - uses: actions/upload-pages-artifact@v3
        with:
          path: web/dist

  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - id: deployment
        uses: actions/deploy-pages@v4
```

**Pages source configuration:** the repo's GitHub Pages settings must be set to "GitHub Actions" as the source (not "Deploy from a branch"). This is a one-time manual step in repo Settings → Pages, called out in the implementation plan.

### 5.8 Justfile additions

```just
# Render JSON for the Astro site → web/src/data/content.{en,de}.json
web-data:
    uv run python -m scripts.render_web_data

# Run the Astro dev server (regenerates data first)
web-dev: web-data
    pnpm --dir web dev

# Build the static site → web/dist/
web-build: web-data
    pnpm --dir web install --frozen-lockfile
    pnpm --dir web build

# Remove web build artifacts
web-clean:
    rm -rf web/dist web/node_modules web/src/data/*.json
```

The `clean` recipe in the existing justfile is extended to also call `web-clean`.

### 5.9 Gitignore additions

Root `.gitignore` additions:

```
web/node_modules/
web/dist/
web/src/data/*.json
web/public/photo.jpg
```

### 5.10 README updates

Add a "Website" section near the top, alongside the existing "Latest CV" links:

```markdown
**Website:** [jin-homlee.github.io/jin-ho-lee-cv](https://jin-homlee.github.io/jin-ho-lee-cv/) · auto-deployed on every change to `main`.
```

### 5.11 CLAUDE.md updates

- Update the Phase 3 row in the phase table from "Not started" to "In progress" (during the phase) then "Done" on merge.
- Add `web/` to the layout section.
- Add `just web-dev` / `just web-build` to the commands list.
- Add a "Local-only files" entry: `web/public/photo.jpg` — public-facing photo, gitignored by default.

## 6. Failure modes & how they're handled

| Failure mode | Mitigation |
|---|---|
| PII leaks into the deployed site | `scripts/render_web_data.py` hard-codes `private_path=None`. A pytest test asserts that running the script with `content.private/private.yaml` present still produces JSON that contains neither phone nor street address. |
| Astro schema drift from YAML changes | `pnpm build` runs in CI; any type/shape mismatch surfaces as a build error before deploy. Initial TS types live alongside the JSON imports; can be tightened later with generated types or Zod. |
| `content/labels.yaml` missing a key the site needs | Caught at build time — Astro throws on `undefined.toString()` etc. Add explicit assertions for required label keys in `render_web_data.py` to fail earlier with a clear message. |
| Subpath base misconfigured | Astro warns on `<a href>` with absolute paths. Verified on first deploy; thereafter stable. |
| Deploy succeeds but site doesn't update | GitHub Pages CDN cache. The `pages.yml` deploy step invalidates this automatically per `deploy-pages@v4` behavior. |
| New EN-only YAML field added without DE counterpart | Already caught by `tests/test_de_completeness.py` (Phase 2b). |
| `render_web_data.py` runs on a contributor's machine without `assets/photo.jpg` | Script does not read `assets/photo.jpg`. It only writes the path string into JSON. Astro's photo-file existence check at build time handles absence gracefully. |
| Race between PDF release workflow and pages workflow on same commit | Independent workflows; neither writes to the other's artifacts. Safe. |

## 7. Testing strategy

Four layers, all gating merge:

1. **Schema + cross-reference (existing).** `scripts/validate.py` continues to enforce content integrity.
2. **`render_web_data.py` unit tests (new).** In `tests/test_render_web_data.py`:
   - Round-trip test: load → resolve → dump → load JSON → assert key fields present and correctly typed.
   - PII isolation test: with a temporary `content.private/private.yaml` containing fake PII, assert the dumped JSON contains neither the phone nor street.
   - Bilingual parity test: EN dump and DE dump have the same structural shape (same keys, same array lengths, same project ids).
   - Publications shape test: `publications[].type ∈ {article, book-chapter, conference, book}`; `authorship` from the allowed set.
3. **Astro build smoke (CI).** `pnpm --dir web build` exits 0; `web/dist/index.html` and `web/dist/de/index.html` exist and are non-empty. Run inside `pages.yml`.
4. **Manual visual review (post-deploy).** First deploy gets eyeball-checked on desktop + mobile. Subsequent deploys reviewed only when the diff touches `web/` or styling.

**Explicitly skipped:** visual regression (per parent spec §8), accessibility audit (additive later if needed), Lighthouse scoring in CI.

## 8. Migration / rollback

- **Migration:** purely additive. No existing files modified except `.gitignore`, `justfile`, `README.md`, and `CLAUDE.md`. PDF build and Phase 2b's release workflow are untouched.
- **First-deploy gotcha:** GitHub Pages must be enabled with "GitHub Actions" as the source — manual one-time step in repo settings. Implementation plan lists this as an explicit task.
- **Rollback:** delete `.github/workflows/pages.yml` to stop deploys. Existing deployed site stays live until GitHub Pages is manually disabled. The `web/` directory and `scripts/render_web_data.py` can remain in place inertly, or be removed in a follow-up.

## 9. Sequencing for later phases

- **Phase 4 (JSON Resume / JSON-LD / plain text):**
  - `render_web_data.py` becomes the reference pattern for `render_jsonresume.py`, `render_jsonld.py`, `render_text.py` — each is a thin script over `content_loader.py` writing a different output shape.
  - The publications authorship pie chart (Phase 4) gets added to the Astro publications section as an inline SVG/component; the chart-generation script writes to `web/public/` and the site picks it up.
  - JSON-LD `<script type="application/ld+json">` blocks get added to `BaseLayout.astro`'s `<head>`, sourced from a Python-generated JSON-LD blob.
- **Phase 5 (polish):**
  - Per-project pages at `/projects/L1/`: add a dynamic route `pages/projects/[id].astro` that imports the same content JSON and renders one project per page. Components from Phase 3 (`ProjectDetails.astro`) get reused unchanged.
  - Custom domain: add a `web/public/CNAME` file and update DNS. `astro.config.mjs` `base` flips to `/`.
  - OG images: generated per-page via a small script writing to `web/public/og/`, referenced from `BaseLayout`.

## 10. Open decisions deferred to implementation

- **Exact blue hex** for the accent color — lift from `pdf/styles.typ` during implementation.
- **TS type definitions for the JSON imports.** Initial plan: hand-written `.d.ts` in `web/src/types/content.ts`. If types drift, generate from JSON Schema with `quicktype` or similar. Implementation chooses based on what hurts less first.
- **Whether to inline experience-bullet project refs as a `<details>` element or as cards below the bullet.** Try both in the dev server, pick the one that reads better. Either way, anchored by project id.
- **Sticky-header behavior on mobile** (full sticky vs. shrink-on-scroll vs. non-sticky). Defer to implementation; visual judgment call.
- **Whether the language switcher preserves scroll position** when switching EN ↔ DE. Nice-to-have; default to top-of-page if Astro's built-in routing doesn't preserve it.
