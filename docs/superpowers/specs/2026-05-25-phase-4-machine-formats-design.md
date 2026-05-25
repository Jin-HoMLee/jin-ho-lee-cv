# Design: Phase 4 — Machine Formats + Publications Chart

**Date:** 2026-05-25
**Owner:** Jin-Ho Lee
**Parent spec:** [`2026-05-21-codified-cv-design.md`](./2026-05-21-codified-cv-design.md)
**Predecessor phase:** Phase 3 — Astro website + GitHub Pages (merged 2026-05-25, commit `6018d60`)

## 1. Scope

Phase 4 ships four small, independent additions:

1. **JSON Resume** (`dist/resume.json`) — single-file JSON conforming to the [jsonresume.org](https://jsonresume.org/schema/) schema, for ATS / external tooling interop.
2. **JSON-LD** (`dist/person.jsonld` + embedded `<script>` in every page) — schema.org structured data for search engines and LLMs.
3. **Plain text** (`dist/cv-{en,de}.txt`) — section-headed ATS-friendly text dump in both languages.
4. **Publications authorship chart** — inline SVG pie inside the website's Publications section.

All four are independent in code but share the same loaders, the same CI workflows, and the same release-channel pattern. They are bundled into a single phase because each is small and the integration touch points (CI release job, justfile, CLAUDE.md) are shared.

## 2. Goal

After Phase 4:

- `https://github.com/Jin-HoMLee/jin-ho-lee-cv/releases/latest/download/resume.json` returns a valid JSON Resume document.
- `https://github.com/Jin-HoMLee/jin-ho-lee-cv/releases/latest/download/cv-en.txt` and `cv-de.txt` return section-headed plain text dumps.
- `https://jin-homlee.github.io/jin-ho-lee-cv/person.jsonld` returns standalone schema.org JSON-LD.
- Every page on the website embeds the same JSON-LD in `<head>` for SEO / LLM consumers.
- The website's Publications section displays an inline SVG pie chart breaking down authorship (first / shared / middle).
- Every push to `main` regenerates and republishes all four artifacts.
- Phase 5 (per-project pages, custom domain) can build on the JSON-LD `Person.url` field without changes to Phase 4 code.

## 3. Non-goals

- **Per-language JSON Resume.** JSON Resume is a single-locale schema by convention; the spec has no `lang` discriminator. EN only.
- **Per-language JSON-LD.** schema.org `Person` describes a person, not a localized profile. Crawlers and LLMs don't consume two parallel documents for the same person. EN only.
- **Header download links for JSON Resume / plain text.** The PDF buttons stay as the only visible header download. JSON / TXT consumers find the formats via GitHub Releases.
- **Interactive / animated chart.** No tooltips, hover effects, click-to-filter, or chart library. Static SVG only.
- **Multiple chart types.** Just authorship breakdown. No per-year publications timeline, no co-author network, no journal distribution.
- **DOI lookup / metadata enrichment for publications.** The BibTeX entries are the source of truth; no external fetches.
- **PR previews of any of the four artifacts.** CI builds them on every PR (catches breakage), but only `main` publishes.
- **Schema validation against the live jsonresume schema URL** in CI. Tests assert against a pinned fixture, not a live fetch.

## 4. Architecture

Three new Python renderers + one new Astro component. All four reuse the existing content loader; no changes to `content/`, `schema/`, or existing Python modules.

```
                  ┌─ pdf/build.py                       (UNCHANGED, Phase 1-2b)
content/*.yaml ──┐│
content/*.bib   ─┼├─ scripts/content_loader.py          (UNCHANGED)
                  │  scripts/bib_loader.py              (UNCHANGED)
                  │  scripts/langstring.py              (UNCHANGED)
                  ├─ scripts/render_web_data.py         (UNCHANGED, Phase 3)
                  │
                  ├─ scripts/render_jsonresume.py       (NEW)  → dist/resume.json
                  ├─ scripts/render_jsonld.py           (NEW)  → dist/person.jsonld
                  └─ scripts/render_text.py             (NEW)  → dist/cv-{en,de}.txt
                                                          │
                                                          ├──→ GitHub Releases (resume.json + cv-{en,de}.txt)
                                                          └──→ Pages public dir (person.jsonld)

                  pages.yml extra step:
                      render_jsonld.py → web/public/person.jsonld
                      copy → BaseLayout.astro injects same JSON inline

                  PublicationsChart.astro (NEW) reads existing publications
                  data + authorship_counts() → emits inline SVG pie
```

### 4.1 Why bundle vs. split

Phase 2 split (2a EN PDF / 2b DE PDF) was driven by a shippable midpoint: 2a was useful on its own. For Phase 4, none of the four artifacts produces user-facing value mid-phase — they're complementary. Splitting into four micro-phases would 4× the CI/docs/PR overhead for no shippable-midpoint benefit.

### 4.2 Why JSON-LD is special

Two of the three renderers (`render_jsonresume.py`, `render_text.py`) produce release artifacts only. `render_jsonld.py` produces both:

- **Standalone** `dist/person.jsonld` → published with releases AND copied to `web/public/person.jsonld` so it's reachable at `https://jin-homlee.github.io/jin-ho-lee-cv/person.jsonld` (stable URL crawlers can canonicalize against).
- **Embedded** `<script type="application/ld+json">` in `BaseLayout.astro` (`set:html={…}`) so every HTML page contains the same JSON-LD inline, which is how search engines discover it without a separate fetch.

This double-publish is intentional: search engines prefer inline; LLM crawlers and `og:type=profile` tooling sometimes prefer the standalone file.

## 5. Module-level design

### 5.1 `scripts/render_jsonresume.py`

```python
def main(output_path: Path = REPO_ROOT / "dist" / "resume.json") -> None:
    content = load_content(CONTENT_DIR, lang="en")
    pubs = load_publications(CONTENT_DIR / "publications.bib")
    content = resolve_langstrings(content, lang="en")
    doc = _to_jsonresume(content, pubs)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(doc, indent=2, ensure_ascii=False))
```

Shape of `_to_jsonresume(content, pubs)`:

```python
{
  "$schema": "https://jsonresume.org/schema/0.0.0/resume.json",
  "basics": {
    "name": "...",
    "label": "...",                  # from profile.tagline (EN)
    "email": "...",
    "url": "https://jin-homlee.github.io/jin-ho-lee-cv/",
    "summary": "\n\n".join(profile.paragraphs),
    "location": {"city": "...", "countryCode": "DE"},
    "profiles": [{"network": "GitHub", "url": "..."}, ...]
  },
  "work":         [...],   # from experience.yaml
  "education":    [...],
  "skills":       [...],   # categories[].name + groups[].label flattened
  "languages":    [...],
  "volunteer":    [...],   # flatten volunteer.categories[].entries[]
  "projects":     [...],   # all projects, ordered by experience.refs occurrence
  "publications": [...]    # from publications.bib
}
```

**Date handling:** JSON Resume uses ISO-8601 `YYYY-MM-DD`. Existing YAML uses `YYYY-MM`. Pad with `-01` for start, `-28` for end (safe in every month).

**Skill flattening:** `categories[].groups[].items[]` flattens to JSON Resume's flat `skills[]` array with `{name, level, keywords}`. Map: `category.name` → `name`, `group.label` → `level`, `items` → `keywords`. JSON Resume intends `level` for proficiency ("Master", "Beginner") rather than subcategory, but using it for our group label is the lowest-friction fit and most ATS tools display the field verbatim regardless of semantics.

**Tests** (`tests/test_render_jsonresume.py`):
- `test_output_validates_against_schema_fixture` — vendored copy of jsonresume schema at `tests/fixtures/jsonresume-schema.json`; assert no validation errors.
- `test_basics_round_trip` — name, email, summary, profiles match the EN content.
- `test_all_experience_entries_present` — count of `work` items == count of EN experience entries.
- `test_all_publications_present` — count of `publications` items == count of bib entries.
- `test_dates_iso_8601` — every `startDate` / `endDate` matches `^\d{4}-\d{2}-\d{2}$`.

### 5.2 `scripts/render_jsonld.py`

```python
def main(output_path: Path = REPO_ROOT / "dist" / "person.jsonld") -> None:
    content = load_content(CONTENT_DIR, lang="en")
    pubs = load_publications(CONTENT_DIR / "publications.bib")
    content = resolve_langstrings(content, lang="en")
    doc = _to_jsonld(content, pubs)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(doc, indent=2, ensure_ascii=False))
```

Shape of `_to_jsonld(content, pubs)`:

```python
{
  "@context": "https://schema.org",
  "@type": "Person",
  "name": "Jin-Ho Lee",
  "url": "https://jin-homlee.github.io/jin-ho-lee-cv/",
  "image": "https://jin-homlee.github.io/jin-ho-lee-cv/photo.jpg",
  "email": "mailto:...",
  "jobTitle": "...",                     # profile.tagline (truncated to first clause)
  "description": "...",                  # profile.paragraphs[0]
  "address": {"@type": "PostalAddress",
              "addressLocality": "...",
              "addressCountry": "DE"},
  "sameAs": [...github, linkedin, orcid urls...],
  "alumniOf": [
    {"@type": "EducationalOrganization", "name": "..."},
    ...
  ],
  "knowsAbout": [...all flattened skill items...],
  "worksFor": {"@type": "Organization", "name": "..."},   # current employer if any
  "@graph": [
    {"@type": "ScholarlyArticle", "name": "...", "datePublished": "YYYY",
     "author": [...], "isPartOf": {"@type": "Periodical", "name": venue}},
    ...
  ]
}
```

**Embedding into the site:** [BaseLayout.astro](web/src/layouts/BaseLayout.astro) adds, inside `<head>`:

```astro
---
import jsonld from "../../public/person.jsonld?raw";
---
<script type="application/ld+json" set:html={jsonld}></script>
```

The `?raw` query strips Vite's JSON-as-module behavior and gives us the file contents as a string, which `set:html` injects verbatim. Both EN and DE pages get the same JSON-LD (it describes the person, not the page).

**Tests** (`tests/test_render_jsonld.py`):
- `test_output_valid_json` + `test_has_schema_context` + `test_type_is_person`
- `test_publications_count_matches_bib` — `@graph` length == pub count
- `test_alumni_count_matches_education` — `alumniOf` length == education entries
- `test_no_pii_in_output` — assert phone/private address not present (smoke test for the public-only loader path)

### 5.3 `scripts/render_text.py`

```python
def main(lang: str, output_path: Path | None = None) -> None:
    content = load_content(CONTENT_DIR, lang=lang)
    pubs = load_publications(CONTENT_DIR / "publications.bib")
    content = resolve_langstrings(content, lang=lang)
    text = _to_text(content, pubs, lang=lang)
    output_path = output_path or REPO_ROOT / "dist" / f"cv-{lang}.txt"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")
```

**Format** (illustrative):

```
JIN-HO LEE
Data Science and Bioinformatics — Mannheim, Germany
jinho.michael.lee@gmail.com · https://github.com/Jin-HoMLee · https://jin-homlee.github.io/jin-ho-lee-cv/

================================================================================
PROFILE
================================================================================
I bridge wet-lab research and production AI, with a track record of 10+ ...
Happy to contribute my open, curious, and adaptive work ethos to ...

================================================================================
EXPERIENCE
================================================================================
Consultant — Cintellic GmbH                                         2024-05 to present
  · Genomics & Immunotherapy: ...
  · Biophysics & Imaging: ...

================================================================================
SKILLS
================================================================================
Bioinformatics
  Genomics: NGS, RNA-Seq, SNV Calling, Splice Analysis
  ...

(etc. — Education, Languages, Volunteer, Publications)
```

**Rules:**
- 80-column hard wrap on paragraphs only (section headers and bullets stay un-wrapped to avoid mangling URLs / titles).
- ASCII bullets (`·`) and dashes only — no Unicode beyond what's in the content.
- Section dividers: 80 `=` chars.
- DE version uses the DE `labels.yaml` for "PROFILE" → "PROFIL", "EXPERIENCE" → "ERFAHRUNG", etc. — same mechanism as the PDF (Phase 1).

**Tests** (`tests/test_render_text.py`):
- `test_produces_both_languages` — calling with `lang="en"` and `lang="de"` writes the right files.
- `test_section_headers_present` — every expected section heading appears.
- `test_no_markdown_chars` — no `**`, `__`, backticks, or `#` in body (apart from the literal section dividers).
- `test_email_phone_excluded_when_public` — phone absent (since `load_content` is hard-coded to `private_path=None`).

### 5.4 `web/src/components/PublicationsChart.astro`

```astro
---
import type { ContentData } from "../types/content";
const { publications } = Astro.props as { publications: ContentData["publications"] };

const counts = publications.reduce<Record<string, number>>((acc, p) => {
  acc[p.authorship] = (acc[p.authorship] ?? 0) + 1;
  return acc;
}, {});

// Order matters for color assignment + legend stability
const slices = ["first", "shared", "middle", "last", "corresponding"]
  .filter((k) => counts[k] > 0)
  .map((k) => ({ label: k, count: counts[k] }));

const total = slices.reduce((s, x) => s + x.count, 0);
// Sketch — implementation walks slices cumulatively, converts
// fraction → angle → (x, y) on the unit circle, and emits one
// `<path d="M 0 0 L x1 y1 A 1 1 0 large 1 x2 y2 Z">` per slice.
const arcs = computeArcs(slices, total);
---
<figure class="my-6 flex items-center gap-6">
  <svg viewBox="-1 -1 2 2" class="w-32 h-32" aria-label="Publication authorship breakdown">
    {arcs.map((arc) => <path d={arc.d} fill={arc.color} />)}
  </svg>
  <ul class="text-sm">
    {slices.map((s) => <li>
      <span class="inline-block w-3 h-3" style={`background:${s.color}`}/>
      {s.label} ({s.count})
    </li>)}
  </ul>
</figure>
```

**Colors:** accent blue from `pdf/styles.typ` for `first` (strongest signal), graduated tints for `shared` and `middle`. 3-5 colors total; pick from existing palette only.

**Used in** [PublicationsList.astro](web/src/components/PublicationsList.astro): rendered once above the grouped-by-type list.

**Accessibility:** SVG has `aria-label`; legend list provides the same information textually.

**Tests:** No new Python tests needed (`render_web_data.py` already emits `publications[i].authorship`, which `bib_loader_test` covers). The TS component is exercised by the existing `pnpm build` in CI — a TS error or a missing prop would fail the build.

### 5.5 `web/src/layouts/BaseLayout.astro` (modify)

Add the JSON-LD injection. ~5 lines.

### 5.6 `web/src/components/PublicationsList.astro` (modify)

Pass `publications` to the new chart component. ~3 lines.

### 5.7 `web/public/person.jsonld` (new, generated)

Output of `render_jsonld.py` copied here before `pnpm build`. Gitignored.

### 5.8 `web/.gitignore` (modify)

Add `public/person.jsonld`.

### 5.9 `justfile` (modify)

Add:

```just
# Render JSON Resume → dist/resume.json
build-resume:
    uv run python -m scripts.render_jsonresume

# Render JSON-LD → dist/person.jsonld
build-jsonld:
    uv run python -m scripts.render_jsonld

# Render plain text in both languages → dist/cv-{en,de}.txt
build-text:
    uv run python -m scripts.render_text --lang en
    uv run python -m scripts.render_text --lang de

# Render every machine format (Phase 4 artifacts)
build-all-formats: build build-de build-resume build-jsonld build-text
```

`just clean` already wipes `dist/`, so no change needed there.

### 5.10 `.github/workflows/ci.yml` (modify)

Add a single sibling job `build-formats` that runs all three Python renderers (one job, four output files — no matrix; the renderers are too cheap to parallelize) and uploads them as one artifact:

```yaml
build-formats:
  needs: validate
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v6
    - name: Install uv
      uses: astral-sh/setup-uv@v8.1.0
    - name: Set up Python
      run: uv python install 3.12
    - name: Install dependencies
      run: uv sync --all-groups
    - name: Build machine formats
      run: |
        uv run python -m scripts.render_jsonresume
        uv run python -m scripts.render_jsonld
        uv run python -m scripts.render_text --lang en
        uv run python -m scripts.render_text --lang de
    - name: Upload artifact
      uses: actions/upload-artifact@v7
      with:
        name: cv-formats
        path: |
          dist/resume.json
          dist/person.jsonld
          dist/cv-en.txt
          dist/cv-de.txt
        retention-days: ${{ github.event_name == 'pull_request' && 30 || 1 }}
        if-no-files-found: error
```

The existing `release` job needs two changes:

1. `needs: [build-pdf, build-formats]` (was `needs: build-pdf`)
2. Append four filenames to the `files:` block — the current release uses an explicit list (`dist/cv-en.pdf`, `dist/cv-de.pdf`), not a glob, so each new artifact must be named:

```yaml
files: |
  dist/cv-en.pdf
  dist/cv-de.pdf
  dist/resume.json
  dist/person.jsonld
  dist/cv-en.txt
  dist/cv-de.txt
```

The existing `download-artifact` step already uses `merge-multiple: true` and downloads everything matching the `path: dist` target, so `cv-formats` will land in `dist/` alongside the PDFs with no glob/pattern change there.

### 5.11 `.github/workflows/pages.yml` (modify)

One extra step before `pnpm build`:

```yaml
- name: Render JSON-LD into web/public/
  run: |
    uv run python -m scripts.render_jsonld
    cp dist/person.jsonld web/public/person.jsonld
```

So the Astro build picks it up via the `import jsonld from "../../public/person.jsonld?raw"` in BaseLayout, AND it ships as a static asset reachable at `/jin-ho-lee-cv/person.jsonld`.

### 5.12 README.md + CLAUDE.md updates

README gets a "Machine formats" line linking to the JSON Resume + plain text + JSON-LD URLs.

CLAUDE.md `scripts/` line updates to include the three new renderers.

## 6. Failure modes

| Failure | Detection | Recovery |
|---|---|---|
| JSON Resume schema drift (jsonresume.org changes shape) | Pinned fixture test passes regardless; only manual schema-update PRs fail | Bump the vendored schema and fix renderer in same PR |
| Crawler can't parse inline JSON-LD because of HTML escaping | Manual check via Google's Rich Results Test; not in CI | Astro's `set:html` doesn't escape; verified by reading the output HTML |
| `person.jsonld` missing during Astro build | `import … from "../../public/person.jsonld?raw"` throws at build time → pnpm build fails → pages.yml fails | The new pages.yml step runs `render_jsonld.py` before `pnpm build`; failure is loud |
| Pie chart slices don't sum to 360° (rounding) | Pytest doesn't catch (TS-side); visual smoke during Task 16-style local check | Round the last slice to fill remainder; arc math handles this |
| BibTeX has authorship values not in the 5-value enum | `bib_loader._parse_entry` already raises on unknown authorship — fails CI | Fix the .bib entry |
| Plain text wraps a URL across two lines and breaks links | Test asserts no line in body contains `http` past column 79 if it started before; alternatively just don't wrap lines containing `http` | Skip wrap on URL-containing lines |
| PDF release picks up unwanted dist/ files | The release job globs explicit filenames, not `dist/*` | See §5.10 |

## 7. Testing

| Layer | Tool | What |
|---|---|---|
| Unit | pytest | Each renderer has 4-6 assertions covering shape, round-trip, PII isolation |
| Schema | pytest + jsonschema | `tests/fixtures/jsonresume-schema.json` vendored; renderer output must validate |
| Integration | pytest + Astro build | The injected JSON-LD survives Astro build; checked by grepping the built HTML for `application/ld+json` (in the pre-existing Task 16-style local smoke pattern, not added as a unit test) |
| E2E | Manual | Post-merge: open the live site, view source, confirm `<script type="application/ld+json">` present; download each format from Releases and inspect |

## 8. Migration / rollback

Fully additive. To roll back Phase 4 cleanly: delete the three `render_*.py` scripts, the PublicationsChart component, the JSON-LD injection in BaseLayout, the new CI job, and the new justfile recipes. No existing module changes; rollback does not touch `content/`, the PDF pipeline, or the existing web components.

## 9. Sequencing for Phase 5

- **JSON-LD `Person.url`** is the canonical URL for everything in Phase 5. Per-project pages get `url` fields appended to `@graph` as `CreativeWork` items.
- **Custom domain (Phase 5)** changes `Person.url` and `image` in JSON-LD. Render logic stays the same; only the constant changes.
- **OG images (Phase 5)** can lift the JSON Resume `basics.summary` as the OG `description`.

## 10. Open decisions deferred to implementation

- **Exact accent color tints for chart slices.** Will be lifted from existing palette during Task 8 (the chart task).
- **Plain text URL handling.** Will inspect actual output; if URLs wrap badly, skip wrap on lines containing `http`. Decision made during implementation.
- **JSON Resume `meta.canonical`.** Set to the GitHub Pages URL; can switch to custom domain in Phase 5.
- **Whether `render_jsonld.py` should produce the same JSON keys in a stable order.** Recommend yes (stable diffs) — implementation uses `json.dumps(…, sort_keys=False)` with manual key order in the dict literal.
