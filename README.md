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
