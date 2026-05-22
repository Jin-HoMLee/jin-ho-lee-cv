# Design: Phase 2b — DE Translations + Bilingual CI Release

**Date:** 2026-05-22
**Owner:** Jin-Ho Lee
**Parent spec:** [`2026-05-21-codified-cv-design.md`](./2026-05-21-codified-cv-design.md)
**Predecessor phase:** Phase 2a — CI release pipeline for EN PDF (merged 2026-05-22, commit `45c0b15`)

## 1. Scope

Phase 2a shipped an auto-released EN PDF. Phase 2b makes the CV bilingual: a DE PDF is built alongside the EN PDF, both attached to every GitHub Release.

**Target translation depth: full bilingual.** Every user-visible string in the rendered PDF has a German equivalent. Brand names, organization names, and technology names (e.g. "Python", "BigQuery", "Cintellic") stay verbatim in both languages.

## 2. Goal

After Phase 2b:

- Every push to `main` produces a GitHub Release tagged `cv-YYYY-MM-DD-<short-sha>` with **both** `cv-en.pdf` and `cv-de.pdf` attached.
- `https://github.com/Jin-HoMLee/jin-ho-lee-cv/releases/latest/download/cv-de.pdf` resolves to the newest DE PDF (alongside the existing `cv-en.pdf`).
- Every pull request uploads both PDFs as downloadable workflow artifacts so reviewers can visually verify both renders.
- `just build-de` and `just build-private-de` recipes exist for local DE builds.

## 3. Non-goals

- Korean (`*.kr.yaml`) — schema supports it; no Korean renderer or content in this phase.
- Per-language font choice — both EN and DE PDFs use IBM Plex Sans.
- Locale-specific date formatting — month abbreviations are translated (e.g. `Mar`→`Mär`), but full month names are not currently rendered.
- Astro website translation — Phase 3.
- Cleanup of `CLAUDE.md:77` stale "Required for Phase 1" line — out of scope; separate cleanup.

## 4. Architecture

Three pieces ship together; each is useless without the others.

```
                                  ┌─ content/labels.yaml      (NEW)
content/*.yaml          ──────┐   │
content/projects/*.en.yaml  ──┼──→├─ content_loader.py         (UNCHANGED)
content/projects/*.de.yaml  ──┘   │  resolve_langstrings already supports `de`
content/profile.{en,de}.yaml  ────┘                  │
                                                     ↓
                                  pdf/build.py --lang {en,de}
                                                     │
                                                     ↓
                                  pdf/templates/cv.typ  (reads `data.labels`)
                                                     │
                                                     ↓
                                  dist/cv-{en,de}.pdf
                                                     │
                       ┌─────────────────────────────┴──────────────────┐
                       ↓                                                 ↓
              .github/workflows/ci.yml                       just build / build-de / build-private*
                                                                   (UNCHANGED for EN; new DE recipes)
                       │
                       ↓
            ┌────────────────────────────────┐
            │  build-pdf (matrix: [en, de])  │
            │      ↓ uploads artifact         │
            └─────────────┬──────────────────┘
                          ↓
                  ┌──────────────────────────────┐
                  │  release (single, main only) │
                  │  downloads both artifacts    │
                  │  creates one release with    │
                  │  both PDFs attached          │
                  └──────────────────────────────┘
```

## 5. Detailed changes

### 5.1 New file: `content/labels.yaml`

Single source of truth for render-time labels that appear in the PDF (section headings, month abbreviations, proficiency labels). These are loaded by [`scripts/content_loader.py`](../../../scripts/content_loader.py), resolved by [`scripts/langstring.py`](../../../scripts/langstring.py), and reach Typst as `data.labels`. Future renderers (Phase 3 Astro site, Phase 4 plain-text) consume the same labels.

```yaml
sections:
  profile:    { en: "Profile",    de: "Profil" }
  experience: { en: "Experience", de: "Berufserfahrung" }
  education:  { en: "Education",  de: "Ausbildung" }
  skills:     { en: "Skills",     de: "Kenntnisse" }
  languages:  { en: "Languages",  de: "Sprachen" }
  volunteer:  { en: "Volunteer",  de: "Ehrenamtlich" }

months_abbr:
  - { en: "Jan", de: "Jan" }
  - { en: "Feb", de: "Feb" }
  - { en: "Mar", de: "Mär" }
  - { en: "Apr", de: "Apr" }
  - { en: "May", de: "Mai" }
  - { en: "Jun", de: "Jun" }
  - { en: "Jul", de: "Jul" }
  - { en: "Aug", de: "Aug" }
  - { en: "Sep", de: "Sep" }
  - { en: "Oct", de: "Okt" }
  - { en: "Nov", de: "Nov" }
  - { en: "Dec", de: "Dez" }

proficiency:
  native:  { en: "native",  de: "Muttersprache" }
  fluent:  { en: "fluent",  de: "fließend" }
  basic:   { en: "basic",   de: "Grundkenntnisse" }
  passive: { en: "passive", de: "passive Kenntnisse" }
```

The DE strings above are the authoritative initial values; Jin-Ho writes/polishes them during implementation.

### 5.2 YAML additions for DE strings

Every existing `{ en: "..." }` map throughout `content/` gets a `de:` key. Concretely:

| File | Strings needing DE |
|---|---|
| `content/personal.yaml` | `headline` (1) |
| `content/experience.yaml` | 3 entries × (1 `role` + ~3 `bullets`) ≈ 12 strings |
| `content/education.yaml` | 2 `degree` entries |
| `content/skills.yaml` | 3 category `name` + 9 group `label`. `items` (e.g. "Python", "BigQuery") stay verbatim. |
| `content/volunteer.yaml` | 4 category `name`. `entries` (org names) stay verbatim. |
| `content/languages.yaml` | 5 language `name`. `proficiency` becomes lookups into `labels.yaml`. |

### 5.3 New per-language content files

- `content/profile.de.yaml` — mirrors `content/profile.en.yaml`'s structure with translated multi-paragraph prose. Jin-Ho reviews; AI drafts permitted.
- `content/projects/{L1..L4,D1..D3,C1..C2}.de.yaml` — one new file per project, mirroring the EN counterpart's structure:
  - Translated: `title`, `summary`, `role`, every entry in `contributions`, `outcome`.
  - Verbatim: `id`, `category`, `period`, `technologies` (brand/tech names).

The langstring resolver already falls back to EN if a `de` key is missing on any individual field, so a partial DE rollout would still render — but the validator (§5.5) prevents that for in-tree fields. Per-language files are loaded by file path, so a missing `projects/L1.de.yaml` fails fast at load time.

### 5.4 Typst template updates

The following hardcoded English strings move out of the templates and into `data.labels` lookups:

| File:Line | Current | Becomes |
|---|---|---|
| `pdf/templates/profile.typ:4` | `section-heading("Profile")` | `section-heading(data.labels.sections.profile)` |
| `pdf/templates/experience.typ:40` | `section-heading("Experience")` | `section-heading(data.labels.sections.experience)` |
| `pdf/templates/education.typ:4` | `section-heading("Education")` | `section-heading(data.labels.sections.education)` |
| `pdf/templates/sidebar.typ:4` | `section-heading("Skills")` | `section-heading(data.labels.sections.skills)` |
| `pdf/templates/sidebar.typ:19` | `section-heading("Languages")` | `section-heading(data.labels.sections.languages)` |
| `pdf/templates/sidebar.typ:31` | `section-heading("Volunteer")` | `section-heading(data.labels.sections.volunteer)` |
| `pdf/styles.typ:3` | `#let _months = ("Jan", ..., "Dec")` | derive from `data.labels.months_abbr` (passed in from `cv.typ`) |
| `pdf/templates/sidebar.typ:24` | `text(...)[#l.proficiency]` | look up via `data.labels.proficiency[l.proficiency]` |

The `_months` change is the only nontrivial Typst edit: the `format-period` function in `styles.typ` currently reads the module-level constant. It needs to accept months as a parameter, or `styles.typ` needs to import the labels via some other mechanism. Simplest: change `format-period(period)` to `format-period(period, months)`, and call sites pass `data.labels.months_abbr`.

### 5.5 Schema / validator updates

- `schema/cv.schema.json` — verify the langmap pattern is already open enough to accept `de:` everywhere (it should be — the pattern recognizes any 2-letter lowercase key per [`scripts/langstring.py:10-16`](../../../scripts/langstring.py#L10-L16)). Add explicit allowance if the schema currently enforces `en`-only.
- `scripts/validate.py` — add a cross-reference check: every `projects/<ID>.en.yaml` must have a matching `projects/<ID>.de.yaml`. New failure mode if someone adds an EN project without DE counterpart.
- One new pytest test in `tests/test_de_completeness.py`:
  - Walks the resolved DE content tree and asserts no English-only strings leak through.
  - Implementation: load tree with `lang="de"`, then compare against tree loaded with `lang="en"`. Any field that's identical between them AND was a langstring in raw YAML is a missing-`de:` bug. (Pure-value fields like emails and URLs are expected to be identical and excluded.)

### 5.6 Workflow refactor — split `build-pdf` into matrix + `release` job

Per the Phase 2a final reviewer's flag: parallel matrix jobs racing to set `make_latest: true` on the same tag is fragile. New structure:

```yaml
jobs:
  validate:           # unchanged
  build-pdf:
    needs: validate
    runs-on: ubuntu-latest
    strategy:
      matrix:
        lang: [en, de]
    steps:
      - ... setup (checkout, uv, python, deps, IBM Plex font, typst) ...
      - name: Build ${{ matrix.lang }} PDF
        run: uv run python -m pdf.build --lang ${{ matrix.lang }}
      - name: Upload PDF artifact
        uses: actions/upload-artifact@v7
        with:
          name: cv-${{ matrix.lang }}-pdf
          path: dist/cv-${{ matrix.lang }}.pdf
          retention-days: 30
          if-no-files-found: error
  release:
    needs: build-pdf
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - name: Download all PDF artifacts
        uses: actions/download-artifact@v7
        with:
          path: dist
          merge-multiple: true
      - name: Compute release metadata
        id: meta
        run: |
          echo "date=$(date -u +%Y-%m-%d)" >> "$GITHUB_OUTPUT"
          echo "short_sha=${GITHUB_SHA::7}" >> "$GITHUB_OUTPUT"
      - name: Create GitHub Release
        uses: softprops/action-gh-release@v3
        with:
          tag_name: cv-${{ steps.meta.outputs.date }}-${{ steps.meta.outputs.short_sha }}
          name: CV ${{ steps.meta.outputs.date }}
          files: |
            dist/cv-en.pdf
            dist/cv-de.pdf
          make_latest: true
          body: |
            Auto-generated CV release from commit ${{ github.sha }}.

            Commit: ${{ github.event.head_commit.message }}

            View commit: ${{ github.server_url }}/${{ github.repository }}/commit/${{ github.sha }}
```

Notes:
- `build-pdf` job-level `permissions: contents: write` from Phase 2a is removed (only `release` needs it).
- The PR artifact upload condition `if: github.event_name == 'pull_request'` is also removed; artifacts upload on every run (push and PR), which is harmless on push runs since `release` consumes them anyway.
- `actions/download-artifact@v7` is the latest major matching the upload-artifact@v7 already in use.

### 5.7 Justfile additions

Two new recipes in `justfile`:

```just
# Build the public DE PDF → dist/cv-de.pdf
build-de:
    uv run python -m pdf.build --lang de

# Build the private DE PDF (with phone + address) → dist-private/cv-de.pdf
build-private-de:
    uv run python -m pdf.build --lang de --private
```

### 5.8 README updates

The existing "Latest CV" download link gets a DE companion:

```markdown
**Latest CV:** [EN](https://github.com/Jin-HoMLee/jin-ho-lee-cv/releases/latest/download/cv-en.pdf) · [DE](https://github.com/Jin-HoMLee/jin-ho-lee-cv/releases/latest/download/cv-de.pdf) — auto-published on every change to `main`.
```

### 5.9 Translation workflow (division of labor)

To minimize total turnaround:

- **Claude drafts** (PR-stage): `content/profile.de.yaml` and the prose-heavy fields in every `content/projects/*.de.yaml` (`summary`, `outcome`, each entry in `contributions`).
- **Jin-Ho writes** (PR-stage): `content/labels.yaml` (the DE side), all `experience.yaml` `role`/`bullets`, all `education.yaml` `degree`, all `skills.yaml` category/group labels, all `volunteer.yaml` category names, all `languages.yaml` language names, the `title` and `role` in each project file.

The split mirrors where idiom matters most (short, headline-style strings → Jin-Ho) vs. where volume matters most (multi-sentence prose → Claude drafts, Jin-Ho polishes during review).

## 6. Failure modes & how they're handled

| Failure mode | Mitigation |
|---|---|
| New EN project file added without DE counterpart | `scripts/validate.py` cross-reference check fails at validate-time. |
| Existing EN langmap not given a `de:` key | `tests/test_de_completeness.py` fails: detects strings that didn't change between en and de resolution. |
| DE PDF renders with English fallback for some field | `test_de_completeness` catches this before merge. |
| Matrix job for one language fails | `release` job's `needs: build-pdf` blocks the release — no partial release published. |
| Both matrix jobs succeed but artifacts have same name | Phase 2b uses distinct names: `cv-en-pdf` and `cv-de-pdf`. Phase 2a's single-name conflict is gone. |
| Race on `make_latest: true` | Eliminated: only the single `release` job ever calls `gh-release`. |

## 7. Testing strategy

Three layers:

1. **Schema + cross-reference (extended).** `validate.py` checks DE-EN file parity for projects. JSON Schema accepts `de:` on every langmap.
2. **DE completeness test (new).** `tests/test_de_completeness.py` asserts no English strings fall through to the DE-resolved tree where a `de:` should exist.
3. **Build smoke tests (extended).** Both PDFs render in CI; both attached to the release. PR previews include both as artifacts.

Visual regression on the PDFs remains explicitly out of scope (parent spec §8).

## 8. Migration / rollback

- **Migration:** additive. EN content is unchanged. New `de:` keys, new `*.de.yaml` files, new `labels.yaml`, Typst templates read from `data.labels` instead of literals.
- **Rollback:** the only mechanically-destructive change is the workflow refactor (matrix + release split). To roll back, restore Phase 2a's monolithic `build-pdf` job from git history. The DE YAML files become inert (no consumer); they can be left in place or pruned.

## 9. Sequencing for later phases

- **Phase 3 (Astro website):** consumes the same `content/labels.yaml` for section headings in both languages. The langstring infrastructure already in place handles per-page locale routing.
- **Phase 4 (JSON Resume / JSON-LD / plain text):** each renderer reads `data.labels` for section headings in the user's chosen language. No labels duplication.
- The Phase 2b workflow shape (`build-pdf` matrix → `release` join job) is the template for future format additions (e.g. Phase 4 could add a `build-text` matrix job that produces `cv-{en,de}.txt`, with `release` adding both to the same release).

## 10. Open decisions deferred to implementation

- **Schema enforcement of `de:` presence.** Should JSON Schema *require* `de:` on every langmap, or remain permissive and rely on `test_de_completeness` for the check? Plan favors permissive schema + strict test (cleaner errors, no schema-level forcing of all future langs to ship at once).
- **`pdf/styles.typ` months refactor.** Whether to pass months through as a function parameter or restructure styles.typ to import labels. Implementation chooses the simpler of the two when writing the code.
