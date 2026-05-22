# CLAUDE.md

Context for Claude Code sessions opened in this repo.

## What this is

A machine-readable, codified CV / resume for Jin-Ho Lee. Single source of truth in YAML + BibTeX; multiple renderers (PDF, website, JSON Resume, JSON-LD, plain text) consume the same data.

## Core architectural principle

**Content is content. Renderers are interchangeable.** Files under `content/` know nothing about how they get rendered. PDF, web, JSON-LD, plain-text are independent scripts that read the same YAML + BibTeX. Replace any renderer without touching content.

## Phasing

Six phases, sequential. Each produces a usable artifact and gets its own brainstorm + plan + execution.

| Phase | Scope | Status |
|---|---|---|
| 0 | Content migration & validation | ✅ Done (merged 2026-05-21, commit `d464f58`) |
| 1 | PDF rendering via Typst | ✅ Done (merged 2026-05-21, commit `996d07e`) |
| 2a | CI release automation (EN PDF) | ✅ Done (merged 2026-05-22, commit `45c0b15`) |
| 2b | German translations + DE PDF in CI | Not started |
| 3 | Astro website + GitHub Pages | Not started |
| 4 | JSON Resume + JSON-LD + plain text + publication chart | Not started |
| 5 | Polish: custom domain, project deep-dive pages, OG images | Not started |

## Layout

```
content/                  source of truth (YAML + BibTeX)
content.private/          gitignored PII overlay (phone, address)
content.private.example/  template showing required private keys
schema/cv.schema.json     JSON Schema for content
scripts/                  validate.py, bib_loader.py, content_loader.py (renderers added in later phases)
tests/                    pytest suite (18 tests as of Phase 0)
docs/superpowers/         specs and implementation plans for each phase
.github/workflows/        CI (validate + test + lint on every push)
```

## Commands

```bash
just validate    # JSON Schema + cross-ref + bib parsing
just test        # pytest, all suites
just lint        # ruff check
just fmt         # ruff format
```

All three checks must be green before merging anything.

## Conventions

- **TDD for non-trivial Python.** Tests first, watch them fail, then implement.
- **Atomic commits.** One logical change per commit. Plain commit messages — no Claude attribution / co-authored-by trailers unless explicitly requested.
- **Per-phase branches.** Phase N work happens on `phase-N-<topic>` branch, merged to `main` with `--no-ff` at the end of the phase to preserve the boundary in history.
- **`content/*.yaml` is the source of truth.** Renderers consume; never edit content from inside a renderer.
- **LangString pattern.** Short user-facing strings use inline `{ en: "...", de: "..." }` maps; long prose lives in per-language files (`profile.en.yaml`). `en` is required; other languages optional until Phase 2.
- **Cross-references validated.** Every `refs: [L1]` in `experience.yaml` must resolve to a `content/projects/L1.en.yaml` file. Filename and `id:` field must match. Enforced by `scripts/validate.py` and `scripts/content_loader.py`.

## Workflow for new phases

1. Brainstorm: `superpowers:brainstorming` to refine scope, get user approval on design.
2. Spec: written to `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`.
3. Plan: `superpowers:writing-plans` to produce step-by-step tasks at `docs/superpowers/plans/YYYY-MM-DD-<topic>.md`.
4. Execute: `superpowers:subagent-driven-development` — fresh subagent per task with spec + code-quality review checkpoints.
5. Finish: `superpowers:finishing-a-development-branch` — `--no-ff` merge to `main`.

## Files to read before starting Phase 1

- `docs/superpowers/specs/2026-05-21-codified-cv-design.md` — full architectural spec
- `docs/superpowers/plans/2026-05-21-phase-0-content-migration.md` — what was done
- `scripts/content_loader.py` — the loader Phase 1's Typst builder will consume
- `scripts/bib_loader.py` — the publication structure

## Local-only files (not in git)

- `assets/photo.jpg` — headshot, referenced from `content/personal.yaml`. Required for Phase 1 PDF builds.
- `content.private/private.yaml` — phone + address. Copy from `content.private.example/private.example.yaml` template.

## Don't

- Don't commit PII (`content.private/` is gitignored — keep it that way).
- Don't add `--no-verify` or skip pre-commit hooks.
- Don't add Claude attribution trailers to commits.
- Don't restructure existing files without scope being part of the current task.
- Don't introduce renderers that read content directly from the PDF — content/ is the only source of truth.
