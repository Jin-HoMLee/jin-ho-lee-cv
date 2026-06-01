# Issue #47 (scoped) — llms.txt renderer + ATS text-layer CI guard

**Issue:** [#47](https://github.com/Jin-HoMLee/jin-ho-lee-cv/issues/47) (`enhancement`, size: M → two size-S items after split)

**Scope decision (2026-06-01):** Ship the two clean size-S sub-items here — (1) an `llms.txt` renderer and (3) an ATS text-layer CI guard. The size-M **Crossref citation enrichment** (sub-item 2) is split out to **#57**. The optional curated `llms-full.txt` recruiter Q&A is **skipped** (bespoke prose, no single-source-of-truth home).

**Goal:** Add a content-derived `/llms.txt` (LLM-friendly site map) and turn "ATS-clean PDF" from an assumption into a CI-verified property.

## Why

- **llms.txt** ([llmstxt.org](https://llmstxt.org/)): a concise Markdown map an LLM reads instead of scraping HTML — H1 + blockquote summary + sectioned link lists. Honoured by Anthropic/Perplexity; ignored by Google/OpenAI; **no measured citation lift** — a cheap differentiator, NOT a JSON-LD replacement.
- **ATS guard**: nothing currently verifies the built PDF has an extractable text layer with name/email/headings/umlauts intact. The existing `pdftotext` tests skip in CI's `validate` job (no Typst there), so ATS-cleanliness is unverified in CI today.

## Part A — `llms.txt` renderer

### `scripts/render_llms.py` (new)

Mirrors `scripts/render_text.py` (section helpers, `main(--output)`), EN-only, all derived from `content/` + bib (single source of truth). Produces Markdown per the llmstxt.org spec:

```
# Jin-Ho Lee — Bioinformatics · Data Science

> {profile.tagline}        ← one-line blockquote summary

{profile.paragraphs[0]}    ← short intro paragraph (optional, plain)

## Selected Projects
- [{title}]({PAGES_BASE_URL}/projects/{id}/): {summary}
…

## Publications
- [{title}](https://doi.org/{doi}): {venue}, {year}      ← DOI link when present; plain title + venue/year otherwise
…

## CV & machine-readable formats
- [CV (PDF, EN)]({PAGES_BASE_URL}/cv-en.pdf)
- [CV (PDF, DE)]({PAGES_BASE_URL}/cv-de.pdf)
- [JSON Resume]({PAGES_BASE_URL}/resume.json)
- [JSON-LD (schema.org)]({PAGES_BASE_URL}/person.jsonld)
- [Plain text]({PAGES_BASE_URL}/cv-en.txt)

## Links
- [GitHub](…)
- [LinkedIn](…)
- [ORCID](…)
- [Website](…)
```

- H1 = `"{given} {family} — {headline.en}"`; blockquote = `profile.tagline`; one intro paragraph from `profile.paragraphs[0]`.
- Projects from `content["selected_projects"]` (the curated subset), Publications from the bib (DOI-linked), Links from `personal.links`.
- Output via `main(argv)` with `--output` default `dist/llms.txt` (mirror `render_text.main`).

### Build wiring

- `justfile`: `build-llms` (→ `dist/llms.txt`); a `web-llms` recipe copying `dist/llms.txt` → `web/public/llms.txt`; add `web-llms` to the `web-build`/`web-dev` dependency lists (alongside `web-jsonld`) so the deployed site serves `/llms.txt`. Add `build-llms` to `build-formats`.
- Astro copies `web/public/*` to the site root verbatim → `https://…/llms.txt`. (Same mechanism as `person.jsonld`.)

### Tests

- `tests/test_render_llms.py` (TDD): H1 has name + headline; blockquote present; each selected project + each publication appears (DOI-linked when DOI present); CV-format + Links sections present and absolute-URL'd; derived from content (no hardcoded strings); no PII (private fields never loaded).
- **Golden snapshot** (#42): add `test_llms_txt` to `tests/test_snapshots.py` (byte-faithful, `.txt` extension via the existing `_TextSnap`).

## Part B — ATS text-layer CI guard

### `tests/test_ats_pdf.py` (new)

Skip-guarded on `typst` + `pdftotext` availability (mirror `test_pdf_publications`). Builds the **bridge EN + DE** PDFs via `subprocess` (`python -m pdf.build --lang … --target bridge`), extracts text with `pdftotext <pdf> -`, and asserts the text layer round-trips:

- **EN**: contains `"Jin-Ho Lee"`, the email `"jinho.michael.lee@gmail.com"`, and the section headings `"PROFILE"`, `"SKILLS"`, `"EDUCATION"`, `"PUBLICATIONS"` (these extract cleanly; **avoid** `"SELECTED PROJECTS"` — Typst letter-spacing makes pdftotext emit `"PROJ ECTS"`). Umlaut round-trip: `"Jülich"` present with the `ü` intact (FZ Jülich is in the experience).
- **DE**: contains `"Jin-Ho Lee"` and a DE-specific umlaut word that round-trips (e.g. `"Jülich"` / `"begutachtete"` for context; assert at least one `ü`/`ä`/`ö`/`ß`-bearing token survives, proving Unicode extraction).
- A guard that the extracted text is non-trivial (length > N) — i.e. there *is* a real text layer, not an image.

### CI wiring (`.github/workflows/ci.yml`)

The existing PDF tests never run in CI (the `validate` job lacks Typst). Add a dedicated job so the ATS guard actually executes:

```yaml
  ats-guard:
    needs: validate
    runs-on: ubuntu-latest
    steps:
      - checkout / install uv / python 3.12 / uv sync --all-groups
      - install Typst (pinned via .typstversion, as build-pdf does)
      - install IBM Plex Sans font (as build-pdf does)
      - run: sudo apt-get update && sudo apt-get install -y poppler-utils   # pdftotext
      - run: uv run pytest tests/test_ats_pdf.py -v
```

Runs once (not per matrix cell). Locally the test runs when Typst+poppler are installed, else skips.

## Out of scope

- Crossref citation counts → **#57**.
- `llms-full.txt` recruiter Q&A (skipped).
- Any change to existing renderers' output (llms.txt is additive; ATS guard is read-only).

## Testing / verification

- TDD for `render_llms` (tests first). `just validate && just test && just lint` green; new `build-llms`/`web-llms` recipes work; `just web-build` emits `web/dist/llms.txt`.
- ATS guard passes locally (Typst+poppler present) and is wired to run in CI's new `ats-guard` job.
- llms.txt golden snapshot committed.

## Commit plan (atomic)

1. `feat: #47 llms.txt renderer (scripts/render_llms.py) + build/web wiring` (+ tests)
2. `test: #47 add llms.txt golden snapshot`
3. `test: #47 ATS PDF text-layer guard (tests/test_ats_pdf.py)`
4. `ci: #47 run the ATS text-layer guard in a dedicated job`
5. `docs: #47 note llms.txt + ATS guard in CLAUDE.md commands/conventions`

(Spec committed first.)
