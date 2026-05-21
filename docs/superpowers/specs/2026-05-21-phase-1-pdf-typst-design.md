# Design: Phase 1 — PDF Rendering via Typst

**Date:** 2026-05-21
**Owner:** Jin-Ho Lee
**Parent spec:** [`2026-05-21-codified-cv-design.md`](./2026-05-21-codified-cv-design.md)
**Branch:** `phase-1-pdf`

## 1. Goal

Produce a one-page, English-only PDF rendered from the content tree validated in Phase 0. The PDF is "close but cleaner" than the current hand-edited CV: same brand spirit (blue accent, photo, two-column layout, structured skill groupings) with modernized typography and a clean separation between data and rendering.

Phase 1 is **local-only** — no CI, no website, no German, no publications. Those are deferred to later phases per the parent spec.

## 2. Scope

### In scope
- One-page PDF, EN only, produced by `pdf/build.py --lang en`
- Public build (`just build`) → `dist/cv-en.pdf`, omits PII (phone, full address)
- Private build (`just build-private`) → `dist-private/cv-en.pdf`, includes phone + address from `content.private/private.yaml`
- Typst as renderer, Python as orchestrator (loads YAML, merges private overlay, resolves language, serializes to JSON, shells out to `typst compile`)
- Tests added to the existing pytest suite covering public build, private overlay behavior, and langstring resolution

### Out of scope (deferred)
- German translations and DE PDF → Phase 2
- CI release automation → Phase 2
- Astro website + GitHub Pages → Phase 3
- JSON Resume / JSON-LD / plain text → Phase 4
- Publications section in PDF → Phase 4 (along with the authorship chart)
- Separate "Selected Projects" section in PDF — projects appear only as inline `[L1]` reference chips next to experience bullets; full project deep-dives live on the website starting Phase 3
- Visual regression testing on the PDF — manual review catches anything that matters

## 3. PDF content

**Sections, in order:**
1. **Header (full width)** — name, headline, contact (email, LinkedIn, GitHub, city/country). Spans both columns above the body.
2. **Main column (left, ≈66%)**
   - **Profile** — multi-paragraph summary loaded from `content/profile.en.yaml`
   - **Experience** — entries from `content/experience.yaml`. Each entry shows org, role, period, bullets. Each bullet that has `refs: [L1, L2]` renders small uppercase chips (e.g. `L1` `L2`) inline at the end of the bullet text, in the accent color.
   - **Education** — entries from `content/education.yaml`
3. **Sidebar (right column, ≈34%)** — circular photo at the top, then Skills (categorized per `content/skills.yaml`), Languages, Volunteer. Light-blue background with a 3px navy left border.

**One-page constraint:** the template targets A4 single page. If content overflows during local builds, the build prints a clear warning but still produces a (multi-page) PDF — the user trims content rather than the template silently truncating. Trimming is editorial, not technical.

## 4. Visual decisions

Locked during brainstorming; all live in `pdf/styles.typ`:

| Token | Value |
|---|---|
| Layout | Two-column: main left (≈66%), sidebar right (≈34%). Header spans both. |
| Sidebar background | `#f4f7fb` (light blue tint) |
| Sidebar accent | 3px solid left border, `#1f3a68` |
| Primary accent | `#1f3a68` (deep navy) — name, section headings, ref chips |
| Body font | IBM Plex Sans, sizes ~10pt body, ~11pt subhead, ~16pt name |
| Section heading style | Small-caps, letterspaced, accent color |
| Ref chip | Small uppercase pill, accent color, e.g. `L1` next to bullet text |
| Photo | Top of sidebar, circular crop |
| Page margins | A4, ~14mm all sides (tune during implementation) |

## 5. Build flow

```
just build                                          just build-private
        │                                                    │
        ▼                                                    ▼
python pdf/build.py --lang en [--private]
    1. load_content(content_dir, private_path?, lang="en")    ← Phase 0 loader, reused
    2. resolve_langstrings(content, lang="en")                ← {en: "x"} → "x"
    3. dist[-private]/.tmp/data.json                          ← serialized resolved content
    4. typst compile pdf/templates/cv.typ                     ← reads data.json via json()
       → dist/cv-en.pdf or dist-private/cv-en.pdf
```

**Why this split:** Python handles data shaping (where existing Phase 0 code already lives — `scripts/content_loader.py`, `scripts/bib_loader.py`). Typst handles rendering only. The renderer never reads YAML directly; it reads one flat JSON dict. This keeps the Typst templates pure presentation — when Typst gets replaced in five years, only `pdf/templates/` and `pdf/styles.typ` are rewritten.

### 5.1 Langstring resolution

`scripts/content_loader.py` returns the raw tree with langmaps intact (e.g. `role: {en: "Consultant"}`). Phase 1 adds a `resolve_langstrings(content, lang)` function (in a new module, e.g. `scripts/langstring.py`) that walks the tree recursively and replaces every `{en: ..., de: ...}` dict with the selected language's value.

- A dict is treated as a langmap if **all** its keys are 2-letter language codes (ISO 639-1).
- If `lang` is missing from the map and `en` is present, fall back to `en` with a warning.
- If neither `lang` nor `en` is present, raise `ValueError` with the path into the tree.
- Non-langmap dicts pass through unchanged.

### 5.2 Private overlay

`content_loader.load_content` already accepts an optional `private_path`. Phase 1's `build.py`:
- `--private` flag: pass `content.private/private.yaml`; PDF lands in `dist-private/`.
- Without `--private`: skip the overlay; PDF lands in `dist/`.
- If `--private` is given but the file doesn't exist, exit non-zero with a clear error (don't silently produce a public build).

## 6. File structure

```
pdf/
├── build.py              # orchestrator: load → resolve → serialize → compile
├── styles.typ            # tokens: colors, fonts, spacing, sizes
└── templates/
    ├── cv.typ            # entry point: page setup, imports + composes sections
    ├── header.typ        # name, headline, contact, photo
    ├── profile.typ
    ├── experience.typ    # entries with inline [refs] chips
    ├── education.typ
    └── sidebar.typ       # skills, languages, volunteer

scripts/
└── langstring.py         # resolve_langstrings(content, lang)

dist/                     # gitignored — public PDFs
dist-private/             # gitignored — PII PDFs
```

Each section template stays small (~30-80 lines). When one section needs adjustment, it's easy to hold in context. `cv.typ` is the only file that knows the overall page composition.

## 7. CLI (justfile additions)

```
just build              # python pdf/build.py --lang en
just build-private      # python pdf/build.py --lang en --private
just clean              # rm -rf dist/ dist-private/
```

`just validate`, `just test`, `just lint`, `just fmt` already exist from Phase 0 and are unchanged.

## 8. Testing strategy

Three new tests, added to the existing pytest suite under `tests/`:

1. **`test_build_public.py`** — invoke `build.py --lang en` (no private). Assert exit code 0, `dist/cv-en.pdf` exists, file size > 1 KB, starts with `%PDF-` magic bytes.
2. **`test_build_private.py`** — with a fixture private.yaml (`tests/fixtures/private.yaml`), invoke `build.py --lang en --private`. Assert exit code 0, `dist-private/cv-en.pdf` exists, and is byte-different from the public build (overlay was actually applied — phone number got rendered). Public build runs once at session scope to provide the comparison baseline.
3. **`test_langstring.py`** — unit tests for `resolve_langstrings`:
   - basic resolution: `{en: "x", de: "y"}` with `lang="en"` → `"x"`
   - nested resolution inside lists and dicts
   - fallback to `en` when target lang missing
   - raises `ValueError` with tree path when neither lang nor `en` present
   - non-langmap dicts (e.g. `{name: "Cintellic", url: null}`) pass through unchanged

Tests require Typst to be installed locally. The PDF-producing tests use `pytest.importorskip` equivalent — they `subprocess.run(["typst", "--version"])` and `pytest.skip` if it fails, so contributors without Typst can still run the rest of the suite. CI will install Typst in Phase 2.

## 9. Typst install + version pinning

Phase 1 is local-only, so install is documented in `README.md`:

```bash
brew install typst        # macOS
# or: cargo install --locked typst-cli
```

A `.typstversion` file at the repo root records the version used for the canonical build. `build.py` reads `.typstversion` and compares to `typst --version` output; on mismatch it prints a warning but does **not** fail. Hard pinning is overkill at this stage.

## 10. Assets

- `assets/photo.jpg` — already referenced from `content/personal.yaml`. User provides locally; not committed (per parent spec §"Local-only files").
- IBM Plex Sans — bundled via Typst's font discovery (`brew install --cask font-ibm-plex` on macOS) or via a `--font-path` flag in `build.py` pointing to a vendored font directory. Implementation picks whichever is simpler; documented in README.
- If `assets/photo.jpg` is missing, the sidebar reflows without the photo (no reserved blank space, no placeholder image). The build logs a warning but does not fail — keeps Phase 1 buildable for contributors who don't have the photo file.

## 11. Open questions deferred to implementation

- Exact margins, line heights, and chip styling — tune in `styles.typ` while looking at the rendered PDF.
- Whether to bundle IBM Plex via `--font-path` or rely on system install — pick whichever produces a hermetic-enough local build.
- How to display `volunteer.yaml` entries in the sidebar — likely just titles + period, but the visual treatment can be decided when looking at real content.

## 12. Done criteria

Phase 1 is done when:
- [ ] `just build` produces `dist/cv-en.pdf` — one page, all sections present, no PII
- [ ] `just build-private` produces `dist-private/cv-en.pdf` — same layout, phone + address rendered
- [ ] `just test` is green (new tests + Phase 0 tests still pass)
- [ ] `just lint` and `just validate` still pass
- [ ] `README.md` has a "Building the PDF" section with install + commands
- [ ] `phase-1-pdf` branch merged to `main` via `--no-ff`
