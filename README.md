# Jin-Ho Lee — Codified CV

Machine-readable, version-controlled CV. Single source of truth in YAML + BibTeX; renderers produce PDF, website, JSON Resume, JSON-LD, and plain text.

See `docs/superpowers/specs/` for the architectural spec and `docs/superpowers/plans/` for active implementation plans.

## Quickstart

```bash
uv sync
just validate    # check all content is well-formed
just test        # run unit tests
```

## Layout

- `content/` — public source of truth (YAML + BibTeX)
- `content.private/` — gitignored PII overlay (phone, address)
- `schema/cv.schema.json` — JSON Schema for content
- `scripts/` — loader, validator, future renderers
- `tests/` — pytest suite

## Local-only assets

Some files referenced from content YAML are not committed to the repo:

- `assets/photo.jpg` — your headshot, referenced from `content/personal.yaml`. Add it locally before running Phase 1 PDF builds.
- `content.private/private.yaml` — your phone, address, and other PII. See `content.private.example/private.example.yaml` for the template.

## Building the PDF

Phase 1 produces a one-page English PDF locally. Requirements:

- Python 3.12 + `uv` (already needed for Phase 0)
- Typst CLI: `brew install typst` (macOS) or `cargo install --locked typst-cli`
- IBM Plex Sans font (recommended): `brew install --cask font-ibm-plex` on macOS. If absent, Typst falls back to a default sans font.
- Optional: `assets/photo.jpg` for the sidebar photo. If missing, the sidebar reflows without it.

### Commands

```bash
just build          # → dist/cv-en.pdf (no PII)
just build-private  # → dist-private/cv-en.pdf (with phone + address)
just clean          # remove dist/, dist-private/, and pdf/.cache/
```

The private build requires `content.private/private.yaml` to exist. Copy `content.private.example/private.example.yaml` and fill in your details.

### How it works

`pdf/build.py` loads the YAML content tree (Phase 0 loader), merges the private overlay if present, resolves language maps to plain strings, writes the result to `pdf/.cache/data.json`, then invokes `typst compile` on `pdf/templates/cv.typ`. The Typst template reads the JSON and renders the layout. Design tokens live in `pdf/styles.typ`.
