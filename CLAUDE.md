# CLAUDE.md

Context for Claude Code sessions opened in this repo.

## What this is

A machine-readable, codified CV / resume for Jin-Ho Lee. Single source of truth in YAML + BibTeX; multiple renderers (PDF, website, JSON Resume, JSON-LD, plain text) consume the same data.

## Core architectural principle

**Content is content. Renderers are interchangeable.** Files under `content/` know nothing about how they get rendered. PDF, web, JSON-LD, plain-text are independent scripts that read the same YAML + BibTeX. Replace any renderer without touching content.

## Phasing

Twelve phases (0–11), sequential. Each produces a usable artifact and gets its own brainstorm + plan + execution.

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
| 9 | Web design overhaul (2026 dark-technical: CV-as-code hero, bento stat band, dark/light theme) | ✅ Done (merged 2026-05-31, PR #40, commit `be80dc6`) |
| 10 | Agent interface (MCP server + skill over `content/` + validate) | ✅ Done (merged 2026-06-03, PR #63, commit `fbc18fe`) |
| 11 | Cover-letter generator (interview + JD → tailored letter, PDF + text) | ✅ Done (merged 2026-06-03, `--no-ff`, PR #66 @claude-approved); personal-voice craft upgrade (anti-slop brief, voice sample, self-critique, jd-gap report, cliché linter) added 2026-06-05 (#74) |

## Layout

```
content/                  source of truth (YAML + BibTeX)
content.private/          gitignored PII overlay (phone, address)
content.private.example/  template showing required private keys
applications/             per-application cover-letter material (gitignored overlay)
applications.example/     committed template showing the applications/ shape
data/citations.json      generated, committed Crossref citation cache (lockfile)
schema/cv.schema.json          JSON Schema for content
schema/application.schema.json schema for cover-letter application.yaml
schema/profile.schema.json     schema for the evergreen cover-letter profile.yaml
scripts/                  validate.py, bib_loader.py, publications.py, content_loader.py, langstring.py, config.py, render_web_data.py, render_jsonresume.py, render_jsonld.py, render_text.py, render_llms.py, fetch_citations.py, citations.py, agent_core.py, mcp_server.py, cover_letter_core.py, letter_text.py, render_letter.py, letter_lint.py, jd_gap.py
tests/                    pytest suite
pdf/                      Typst PDF renderer (Phase 1; incl. templates/cover-letter.typ for the DIN 5008 letter)
web/                      Astro website (Phase 3)
.claude/skills/cv/        committed Claude skill (agent interface) — SKILL.md + reference.md
.claude/skills/cover-letter/  committed Claude skill (cover-letter interview + render)
.mcp.json                 Claude Code project-scoped MCP server config
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
just build-formats     # all machine formats (resume.json + person.jsonld + plain text + llms.txt)
just refresh-citations # fetch Crossref citation counts → data/citations.json (manual, networked)
just snapshots-update  # regenerate committed renderer golden snapshots (after intentional output changes)
just web-dev           # Astro dev server (regenerates content JSON + JSON-LD)
just web-build         # Production build of web/dist
just mcp-server        # run the CV MCP server (stdio) — point an MCP client at this
just mcp-dev           # MCP Inspector against the server (needs the mcp dep group)
just letter <slug>     # render a cover letter → applications/<slug>/cover-letter-*.{pdf,txt}
just jd-gap <slug>     # advisory JD↔CV keyword report (checklist, not a verdict) for an application
```

validate + test + lint must all be green before merging anything.

## Conventions

- **TDD for non-trivial Python.** Tests first, watch them fail, then implement.
- **Golden snapshots.** Renderer outputs (`resume.json`, `person.jsonld`, `cv-{en,de}.txt`, `llms.txt`, web `content.*.json`) are byte-snapshotted with syrupy under `tests/__snapshots__/`; CI fails on unintended drift. Regenerate intentionally with `just snapshots-update` and eyeball the diff. `scripts/validate.py` also hard-fails reversed periods and advisory-warns implausible dates.
- **ATS guard.** The built PDF's text layer is CI-verified (`tests/test_ats_pdf.py` via the `ats-guard` job — name/email/headings/umlauts round-trip through `pdftotext`); the `release` job depends on it. Note: Typst letter-spacing makes `pdftotext` emit intra-word spaces in styled headings (e.g. `SELECTED PROJECTS` → `PROJ ECTS`), so the guard asserts only cleanly-extracting headings (`PROFILE`/`SKILLS`/`EDUCATION`/`PUBLICATIONS`) — don't re-add spaced ones. `/llms.txt` (llmstxt.org site map) is generated into `web/public/` for the deployed site (gitignored, like `person.jsonld`).
- **Atomic commits.** One logical change per commit. Plain commit messages — no Claude attribution / co-authored-by trailers unless explicitly requested.
- **Per-phase branches.** Phase N work happens on `phase-N-<topic>` branch, merged to `main` with `--no-ff` at the end of the phase to preserve the boundary in history.
- **`content/*.yaml` is the source of truth.** Renderers consume; never edit content from inside a renderer.
- **LangString pattern.** Short user-facing strings use inline `{ en: "...", de: "..." }` maps; long prose lives in per-language files (`profile.en.yaml`). `en` is required; other languages optional until Phase 2.
- **Cross-references validated.** Every `refs: [L1]` in `experience.yaml` must resolve to a `content/projects/L1.en.yaml` file. Filename and `id:` field must match. Enforced by `scripts/validate.py` and `scripts/content_loader.py`.
- **Citation cache is a lockfile.** `data/citations.json` is generated by `just refresh-citations` (the only networked recipe) and committed; renderers read it offline and degrade gracefully when a DOI (or the file) is absent. Regenerate intentionally and review the diff — never hand-edit. Adding/removing a publication DOI may require a refresh (a staleness test guards against orphaned cache keys).
- **Plans keep this file current.** Every implementation plan ends with a task to update CLAUDE.md — refresh the Phasing table row for the phase (and any changed convention) so phase status stays authoritative. A merged phase with no row here is a doc bug.
- **Agent interface.** `scripts/agent_core.py` is the pure-Python core (`read_cv`,
  `list_content_files`, `validate_cv`, `propose_edit`, `apply_edit`, `rerun_renderers`);
  `scripts/mcp_server.py` (FastMCP, `mcp` dep group) and `.claude/skills/cv/` are thin
  mirrors of it. PII can never leak — `read_cv` forces `private_path=None` and edit paths
  pass `_safe_content_path` (no `..`/symlink/`content.private`). Edits are gated by the
  full `validate_tree`; the skill docs are drift-guarded against the `justfile`/schema.
- **Cover letters are a read-only CV consumer.** `applications/` is gitignored (this
  repo is public); the generator reads `content/` via `cover_letter_core.cv_facts`
  (PII-safe `agent_core.read_cv`) and writes only under `applications/`. PDFs merge
  `content.private/` at render time and stay gitignored. Never commit `applications/`.
  Core: `scripts/cover_letter_core.py` (+ `letter_text.py`, `render_letter.py`,
  `letter_lint.py`, `jd_gap.py`); skill: `.claude/skills/cover-letter/`. The skill carries
  craft guidance ("How to write the body" + "AI tells & clichés to avoid" in reference.md);
  `just jd-gap <slug>` prints an advisory JD↔CV keyword checklist (not a verdict) and the
  cliché linter prints advisory `WARN:` lines from `render_letter` — both deterministic,
  neither ever blocks. Rendered text never contains the private address; only the gitignored
  PDF does.

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
- `docs/superpowers/specs/2026-05-28-phase-6-seo-analytics-design.md` — Phase 6 design spec (sitemap, robots.txt, GSC verify, GoatCounter analytics)
- `docs/superpowers/specs/2026-05-29-phase-7-content-audit-design.md` — Phase 7 design spec (content audit — bring the CV up to date)
- `docs/superpowers/specs/2026-05-30-phase-8a-sharpen-positioning-design.md` — Phase 8a design spec (sharpen positioning — Bioinformatics · Data Science)
- `docs/superpowers/specs/2026-05-30-phase-8b-targeted-variants-design.md` — Phase 8b design spec (targeted CV variants — comp-bio · ds-ml from one source)
- `docs/superpowers/specs/2026-05-31-phase-8c-web-variants-design.md` — Phase 8c design spec (web target switcher — client-side variant positioning)
- `docs/superpowers/specs/2026-05-31-phase-9-web-redesign-design.md` — Phase 9 design spec (2026 dark-technical web overhaul)
- `docs/superpowers/specs/2026-06-02-crossref-citation-enrichment-design.md` — Crossref citation-count enrichment design spec (#57)
- `docs/superpowers/plans/2026-06-02-crossref-citation-enrichment.md` — implementation plan for citation-count enrichment (#57)
- `docs/superpowers/specs/2026-06-03-agent-interface-mcp-skill-design.md` — Phase 10 design spec (thin MCP server + Claude skill over content/)
- `docs/superpowers/plans/2026-06-03-agent-interface-mcp-skill.md` — implementation plan for the agent interface (#48)
- `scripts/content_loader.py` + `scripts/bib_loader.py` + `scripts/langstring.py` — the data layer every renderer consumes
- `scripts/render_web_data.py` — the closest pattern for a "Python script that emits JSON for a downstream renderer to consume"; mirror this style
- `docs/superpowers/specs/2026-06-03-phase-11-cover-letter-design.md` — Phase 11 design spec (cover-letter generator)
- `docs/superpowers/plans/2026-06-03-phase-11-cover-letter.md` — implementation plan for the cover-letter generator (#65)

## Local-only files (not in git)

- `assets/photo.jpg` — headshot for the private PDF build, only included when `--photo` is passed. Optional; omit and the PDF renders without a photo. Kept gitignored by convention (PDFs are intentionally photo-less to avoid discrimination per German hiring norms).
- `content.private/private.yaml` — phone + address. Copy from `content.private.example/private.example.yaml` template.
- `applications/` — per-application cover-letter material (job descriptions, drafts, rendered letters). Gitignored; mirror the shape in `applications.example/`.
- `assets/signature.png` — handwritten signature for the cover-letter PDF, included only when present (mirrors the optional `--photo` pattern). Gitignored.

## Don't

- Don't commit PII (`content.private/` is gitignored — keep it that way).
- Don't add `--no-verify` or skip pre-commit hooks.
- Don't add Claude attribution trailers to commits.
- Don't restructure existing files without scope being part of the current task.
- Don't introduce renderers that read content directly from the PDF — content/ is the only source of truth.
