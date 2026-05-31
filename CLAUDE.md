# CLAUDE.md

Context for Claude Code sessions opened in this repo.

## What this is

A machine-readable, codified CV / resume for Jin-Ho Lee. Single source of truth in YAML + BibTeX; multiple renderers (PDF, website, JSON Resume, JSON-LD, plain text) consume the same data.

## Core architectural principle

**Content is content. Renderers are interchangeable.** Files under `content/` know nothing about how they get rendered. PDF, web, JSON-LD, plain-text are independent scripts that read the same YAML + BibTeX. Replace any renderer without touching content.

## Phasing

Eight phases (0–8), sequential. Each produces a usable artifact and gets its own brainstorm + plan + execution.

| Phase | Scope | Status |
|---|---|---|
| 0 | Content migration & validation | ✅ Done (merged 2026-05-21, commit `d464f58`) |
| 1 | PDF rendering via Typst | ✅ Done (merged 2026-05-21, commit `996d07e`) |
| 2a | CI release automation (EN PDF) | ✅ Done (merged 2026-05-22, commit `45c0b15`) |
| 2b | German translations + DE PDF in CI | ✅ Done (merged 2026-05-22, commit `ee1290a`) |
| 3 | Astro website + GitHub Pages | ✅ Done (merged 2026-05-25, commit `6018d60`) |
| 4 | JSON Resume + JSON-LD + plain text + publication chart | ✅ Done (merged 2026-05-25, commit `5f3ce71`) |
| 5 | Polish: custom domain, project deep-dive pages, OG images, chart interactivity | ✅ Done (merged 2026-05-26, commit `a3c682b`) |
| 6 | SEO (sitemap + robots.txt + GSC verify) + privacy-friendly analytics (GoatCounter) | ✅ Done (merged 2026-05-28, commit `c05530e`); Bing dropped (is-a.dev PSL quota blocker) |
| 7 | Content audit (bring CV up to date) | ✅ Done (merged 2026-05-29, PR #33, commit `b731222`) |
| 8a | Sharpen positioning (Bioinformatics · Data Science) | ✅ Done (merged 2026-05-30, PR #36, commit `c3862f5`) |
| 8b | Targeted CV variants (comp-bio · ds-ml from one source) | ✅ Done (merged 2026-05-30, PR #38, commit `b9f6895`) |
| 8c | Web target switcher (client-side variant positioning) | ✅ Done (merged 2026-05-31, PR #39, commit `6ced593`) |
| 9 | Web design overhaul (2026 dark-technical: CV-as-code hero, bento stat band, dark/light theme) | 🚧 In progress (branch `phase-9-web-redesign`) |

## Layout

```
content/                  source of truth (YAML + BibTeX)
content.private/          gitignored PII overlay (phone, address)
content.private.example/  template showing required private keys
schema/cv.schema.json     JSON Schema for content
scripts/                  validate.py, bib_loader.py, content_loader.py, langstring.py, config.py, render_web_data.py, render_jsonresume.py, render_jsonld.py, render_text.py
tests/                    pytest suite
pdf/                      Typst PDF renderer (Phase 1)
web/                      Astro website (Phase 3)
docs/superpowers/         specs and implementation plans for each phase
.github/workflows/        ci.yml (validate + PDF + release), pages.yml (web deploy)
```

## Commands

```bash
just validate          # JSON Schema + cross-ref + bib parsing
just test              # pytest, all suites
just lint              # ruff check
just fmt               # ruff format
just build             # → dist/cv-en.pdf
just build-de          # → dist/cv-de.pdf
just build-resume      # → dist/resume.json (JSON Resume)
just build-jsonld      # → dist/person.jsonld (schema.org)
just build-text        # → dist/cv-{en,de}.txt
just build-formats     # all three Phase 4 machine formats
just web-dev           # Astro dev server (regenerates content JSON + JSON-LD)
just web-build         # Production build of web/dist
```

validate + test + lint must all be green before merging anything.

## Conventions

- **TDD for non-trivial Python.** Tests first, watch them fail, then implement.
- **Atomic commits.** One logical change per commit. Plain commit messages — no Claude attribution / co-authored-by trailers unless explicitly requested.
- **Per-phase branches.** Phase N work happens on `phase-N-<topic>` branch, merged to `main` with `--no-ff` at the end of the phase to preserve the boundary in history.
- **`content/*.yaml` is the source of truth.** Renderers consume; never edit content from inside a renderer.
- **LangString pattern.** Short user-facing strings use inline `{ en: "...", de: "..." }` maps; long prose lives in per-language files (`profile.en.yaml`). `en` is required; other languages optional until Phase 2.
- **Cross-references validated.** Every `refs: [L1]` in `experience.yaml` must resolve to a `content/projects/L1.en.yaml` file. Filename and `id:` field must match. Enforced by `scripts/validate.py` and `scripts/content_loader.py`.
- **Plans keep this file current.** Every implementation plan ends with a task to update CLAUDE.md — refresh the Phasing table row for the phase (and any changed convention) so phase status stays authoritative. A merged phase with no row here is a doc bug.

## Workflow for new phases

1. Brainstorm: `superpowers:brainstorming` to refine scope, get user approval on design.
2. Spec: written to `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`.
3. Plan: `superpowers:writing-plans` to produce step-by-step tasks at `docs/superpowers/plans/YYYY-MM-DD-<topic>.md`. The plan's final task always updates the Phasing table in this file.
4. Execute: `superpowers:subagent-driven-development` — fresh subagent per task with spec + code-quality review checkpoints.
5. Finish: `superpowers:finishing-a-development-branch` — `--no-ff` merge to `main`.

## Files to read before any phase

- `docs/superpowers/specs/2026-05-21-codified-cv-design.md` — full architectural spec for the whole codified-CV project
- `docs/superpowers/specs/2026-05-25-phase-4-machine-formats-design.md` — Phase 4 design spec (JSON Resume, JSON-LD, plain text, publication chart)
- `docs/superpowers/specs/2026-05-26-phase-5-polish-design.md` — Phase 5 design spec (custom domain, project pages, OG images, chart tooltips)
- `scripts/content_loader.py` + `scripts/bib_loader.py` + `scripts/langstring.py` — the data layer every renderer consumes
- `scripts/render_web_data.py` — the closest pattern for a "Python script that emits JSON for a downstream renderer to consume"; mirror this style

## Local-only files (not in git)

- `assets/photo.jpg` — headshot for the private PDF build, only included when `--photo` is passed. Optional; omit and the PDF renders without a photo. Kept gitignored by convention (PDFs are intentionally photo-less to avoid discrimination per German hiring norms).
- `content.private/private.yaml` — phone + address. Copy from `content.private.example/private.example.yaml` template.

## Don't

- Don't commit PII (`content.private/` is gitignored — keep it that way).
- Don't add `--no-verify` or skip pre-commit hooks.
- Don't add Claude attribution trailers to commits.
- Don't restructure existing files without scope being part of the current task.
- Don't introduce renderers that read content directly from the PDF — content/ is the only source of truth.
