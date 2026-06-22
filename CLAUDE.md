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
| 12a | Digital-twin chat MVP (CV-grounded conversational chat: context compiler + Cloudflare Worker + web widget + guardrails) | ✅ Done (merged 2026-06-16, `--no-ff`, PR #83, commit `7b6dfaa`); Gemini free-tier backend |
| 12b | Digital-twin insights (D1 question log + daily Gemini digest + Cloudflare-Access dashboard) | ✅ Done (merged 2026-06-18, `--no-ff`, PR #86, commit `1791691`); free-tier D1 + Cron Triggers; verbatim questions, 30-day purge, no IP. Worker deploy (D1 create + remote schema + Access policy + `just worker-deploy`) is a separate manual step |
| 12c | Digital-twin lead-capture (consented opt-in contact form: persistent affordance + one-time nudge → `contact_submissions` D1 + best-effort Telegram notify + leads on the 12b dashboard) | ✅ Done (merged 2026-06-19, `--no-ff`, PR #91, commit `f8d2a10`); leads KEPT (no TTL — purpose-driven retention, the deliberate flip vs 12b's 30-day questions); Telegram notifier graceful no-op when unconfigured; reuses 12a Turnstile/CORS + a per-IP 3/day submit cap. Rate-limit slot spent only after a successful store (a 502 never burns one). Worker deploy (remote schema re-apply + `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` secrets — both kept out of the public repo) is a separate manual step |
| 13 | `master-cv/` overlay (gitignored life-database superset feeding the twin + a `dist/master-cv.md` lookup export; CV stays sharp) | ✅ Done (merged YYYY-MM-DD, `--no-ff`, PR #NN, commit `xxxxxxx`); overlay gitignored + PII-guarded, graceful-absence proven (CV-only output byte-identical without it), synthetic `master-cv.example/` committed; first ingest + CV-reconcile (#93) are separate manual/follow-up steps |

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
schema/master-cv.schema.json   overlay validation
master-cv.example/             committed synthetic overlay template
scripts/                  validate.py, bib_loader.py, publications.py, content_loader.py, langstring.py, config.py, render_web_data.py, render_jsonresume.py, render_jsonld.py, render_text.py, render_llms.py, render_chat_context.py, fetch_citations.py, citations.py, agent_core.py, mcp_server.py, cover_letter_core.py, letter_text.py, render_letter.py, letter_lint.py, jd_gap.py, check_pii.py, master_cv_loader.py, render_master_cv.py, profile_union.py
tests/                    pytest suite
pdf/                      Typst PDF renderer (Phase 1; incl. templates/cover-letter.typ for the DIN 5008 letter)
web/                      Astro website (Phase 3)
worker/                   Cloudflare Worker — digital-twin chat proxy (Phase 12a; deploys outside Pages)
.claude/skills/cv/        committed Claude skill (agent interface) — SKILL.md + reference.md
.claude/skills/cover-letter/  committed Claude skill (cover-letter interview + render)
.mcp.json                 Claude Code project-scoped MCP server config
.githooks/pre-commit      committed git PII guard; activate per-clone with `just install-hooks`
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
just build-chat-context # compile the whole CV into one blob → dist/chat-context.md (digital-twin)
just build-master-cv      # content/ + master-cv/ overlay → dist/master-cv.md (lookup artifact)
just worker-dev        # run the digital-twin Worker locally (bundles chat-context.md, wrangler dev)
just worker-deploy     # deploy the digital-twin Worker to Cloudflare (bundles chat-context.md, wrangler deploy)
just refresh-citations # fetch Crossref citation counts → data/citations.json (manual, networked)
just snapshots-update  # regenerate committed renderer golden snapshots (after intentional output changes)
just web-dev           # Astro dev server (regenerates content JSON + JSON-LD)
just web-build         # Production build of web/dist
just mcp-server        # run the CV MCP server (stdio) — point an MCP client at this
just mcp-dev           # MCP Inspector against the server (needs the mcp dep group)
just letter <slug>     # render a cover letter → applications/<slug>/cover-letter-*.{pdf,txt}
just jd-gap <slug>     # advisory JD↔CV keyword report (checklist, not a verdict) for an application
just check-pii         # scan staged files for PII leaks (content.private values + gitignored PII paths)
just install-hooks     # activate the committed git hooks (run once per clone — sets core.hooksPath=.githooks)
```

**First-clone setup:** run `just install-hooks` once to activate the git pre-commit PII guard.

validate + test + lint must all be green before merging anything.

## Conventions

- **TDD for non-trivial Python.** Tests first, watch them fail, then implement.
- **Tests never touch `content.private/`.** The real `private.yaml` is PII outside git's
  protection — tests write private overlays only under `tmp_path` (PDF build: via the
  `CV_PRIVATE_YAML` env override). A session-wide autouse guard in `tests/conftest.py`
  fails the run if any test mutates the real file (issue #77).
- **Golden snapshots.** Renderer outputs (`resume.json`, `person.jsonld`, `cv-{en,de}.txt`, `llms.txt`, web `content.*.json`) are byte-snapshotted with syrupy under `tests/__snapshots__/`; CI fails on unintended drift. Regenerate intentionally with `just snapshots-update` and eyeball the diff. `scripts/validate.py` also hard-fails reversed periods and advisory-warns implausible dates.
- **ATS guard.** The built PDF's text layer is CI-verified (`tests/test_ats_pdf.py` via the `ats-guard` job — name/email/headings/umlauts round-trip through `pdftotext`); the `release` job depends on it. Note: Typst letter-spacing makes `pdftotext` emit intra-word spaces in styled headings (e.g. `SELECTED PROJECTS` → `PROJ ECTS`), so the guard asserts only cleanly-extracting headings (`PROFILE`/`SKILLS`/`EDUCATION`/`PUBLICATIONS`) — don't re-add spaced ones. `/llms.txt` (llmstxt.org site map) is generated into `web/public/` for the deployed site (gitignored, like `person.jsonld`).
- **Atomic commits.** One logical change per commit. Plain commit messages — no Claude attribution / co-authored-by trailers unless explicitly requested.
- **Per-phase branches.** Phase N work happens on `phase-N-<topic>` branch, merged to `main` with `--no-ff` at the end of the phase to preserve the boundary in history.
- **Deploys outside GitHub Pages.** The digital-twin Worker (`worker/`) is the first repo
  component that deploys to Cloudflare (via `just worker-deploy` / `wrangler`), not GitHub
  Pages. The Pages build only needs the generated `dist/chat-context.md`; the Worker is
  deployed separately and holds `GEMINI_API_KEY` as a Worker secret (never in git). Inference
  uses the Google Gemini free tier via a best-first **model cascade** in `src/gemini.ts`
  (`gemini-3.5-flash` → `gemini-2.5-flash` → `gemini-2.5-flash-lite`): each model has its own
  free-tier daily request cap (20 / 250 / 1000), so on a daily-quota 429 (or transient 503/500)
  the Worker falls through to the next model — keeping the twin reachable on ~1,270 combined
  free requests/day instead of dying at 20. No out-of-pocket cost at expected traffic; also
  bounded by `MAX_TOKENS` + `MONTHLY_CEILING`. The Worker transforms Gemini's native
  SSE back into the browser widget's client envelope, so the frontend contract is unchanged.
  The widget only appears on the deployed site when the Pages build receives
  `PUBLIC_TWIN_ENDPOINT` + `PUBLIC_TURNSTILE_SITE_KEY` — both public values, set as GitHub repo
  *variables* and injected in `pages.yml` (unset → empty → widget renders nothing, the graceful
  default). The Worker deploy itself is still a separate `wrangler` step, never wired into Pages.
  Locally, **don't hand-swap `web/.env`** — Astro loads env files by mode: committed
  `web/.env.development` (local Worker `:8787` + always-pass test Turnstile key) is used by
  `just web-dev`, and committed `web/.env.production` (deployed Worker + real site key) by
  `just web-build`. Both hold only non-secret `PUBLIC_` values; personal overrides go in a
  gitignored `web/.env.local` / `web/.env.*.local`. (`worker/.dev.vars` is likewise local-only —
  `wrangler dev` reads it; prod never does — so it never needs swapping either.)
- **Worker now uses D1 + a Cron Trigger.** Phase 12b adds the `INSIGHTS_DB` D1 binding
  (question log + digests; schema in `worker/schema.sql`, applied via `wrangler d1
  execute`), a daily `scheduled()` digest cron (`[triggers] crons`), and a private
  `GET /twin-insights` HTML route gated by Cloudflare Access + a
  `Cf-Access-Authenticated-User-Email` guard. That route is intentionally excluded
  from the public site surface (sitemap / llms.txt / CNAME). D1 + Cron are free-tier;
  the digest reuses the existing `GEMINI_API_KEY`. D1 logging is fire-and-forget via
  `ctx.waitUntil` — it never blocks the chat stream.
- **Worker also captures consented leads (Phase 12c).** A `POST /lead` route stores
  visitor-opted-in contact details in the `contact_submissions` D1 table (KEPT — not
  auto-purged, unlike the 30-day `questions` log; purpose-driven retention). It reuses
  the 12a Turnstile + CORS guards plus a per-IP 3/day submit cap, and fires a
  best-effort Telegram notification via `ctx.waitUntil` (graceful no-op when
  `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` are unset — both are `wrangler secret`s, so
  the personal chat id never lands in this public repo). Leads surface in the 📇 Leads
  section of the Access-gated `/twin-insights` dashboard. No PII reaches git (leads
  live in D1; the route is off the public surface).
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
- **`master-cv/` is a gitignored superset overlay (Phase 13).** The unfiltered
  life-database (`timeline.yaml` + `inventory.yaml` + `narrative/*.md`) feeding the
  digital twin and the `dist/master-cv.md` lookup export. `content/` is a curated
  *selection* from it. Never committed (`.gitignore` + `check_pii.py` both block it);
  only synthetic `master-cv.example/` is committed. Both consumers share
  `scripts/profile_union.full_profile`; the overlay path resolves from `MASTER_CV_DIR`
  (default `<repo>/master-cv`, the `CV_PRIVATE_YAML` test-override shape). Absent ⇒
  CV-only output, byte-identical (graceful-absence proof). No test reads the real
  overlay — a conftest autouse fixture redirects `MASTER_CV_DIR` to an absent sentinel.
- **PII guard (block-hard).** `scripts/check_pii.py` is one detection core (`scan_files`,
  pure: path + content bytes in, violations out) behind three surfaces — Claude Code
  PreToolUse(Bash) hook (`.claude/settings.local.json` → `--hook`, denies a `git commit`
  that leaks; gitignored so per-machine), committed git pre-commit hook (`.githooks/pre-commit`
  → `--staged`, activated once per clone by `just install-hooks`, no new dependency), and the
  CI `check-pii` step (`--tree`, the post-push backstop). It catches **known values** (the
  guarded `content.private` literals: `phone`, `address.street`, `address.postal_code` —
  `city`/`country` are intentionally public and excluded) and **PII paths** (`content.private/`,
  `applications/`, `assets/{photo,signature}.*`; `content.private.example/` is allowed). Violation
  messages never echo the matched secret. Tests use **synthetic** private values only (a real one
  would self-flag); a drift-guard asserts `ci.yml` + `.githooks/pre-commit` actually invoke it.

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
- `docs/superpowers/specs/2026-06-20-phase-13-master-cv-overlay-design.md` — Phase 13 design spec (master-cv/ overlay)
- `docs/superpowers/plans/2026-06-22-phase-13-master-cv-overlay.md` — implementation plan for the master-cv/ overlay (#92)

## Local-only files (not in git)

- `assets/photo.jpg` — headshot for the private PDF build, only included when `--photo` is passed. Optional; omit and the PDF renders without a photo. Kept gitignored by convention (PDFs are intentionally photo-less to avoid discrimination per German hiring norms).
- `content.private/private.yaml` — phone + address. Copy from `content.private.example/private.example.yaml` template.
- `applications/` — per-application cover-letter material (job descriptions, drafts, rendered letters). Gitignored; mirror the shape in `applications.example/`.
- `assets/signature.png` — handwritten signature for the cover-letter PDF, included only when present (mirrors the optional `--photo` pattern). Gitignored.
- `master-cv/` — the unfiltered superset overlay (`timeline.yaml` + `inventory.yaml` + `narrative/*.md`). Gitignored; mirror the shape in `master-cv.example/`.

## Don't

- Don't commit PII (`content.private/` is gitignored — keep it that way).
- Don't add `--no-verify` or skip pre-commit hooks.
- Don't add Claude attribution trailers to commits.
- Don't restructure existing files without scope being part of the current task.
- Don't introduce renderers that read content directly from the PDF — content/ is the only source of truth.
