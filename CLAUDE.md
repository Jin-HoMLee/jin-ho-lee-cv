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
| 13 | `master-cv/` overlay (gitignored life-database superset feeding the twin + a `dist/master-cv.md` lookup export; CV stays sharp) | ✅ Done (merged 2026-06-22, `--no-ff`, PR #94, commit `c46f092`); overlay gitignored + PII-guarded, graceful-absence proven (CV-only output byte-identical without it), synthetic `master-cv.example/` committed; first ingest + CV-reconcile (#93) are separate manual/follow-up steps · opinions overlay added 2026-06-25 (`master-cv/opinions.md` → `## Opinions & Technical Taste` in the twin context; gated persona rule voices them only when asked) |
| 14 | AEO entity presence (Google Scholar entity anchor · bilingual FAQ + `FAQPage` JSON-LD · front-loaded answer block · static-HTML-facts CI guard) | ✅ Done (merged 2026-07-14, `--no-ff`, PR #115 @claude-reviewed). Google Scholar is wired into `personal.links` - it flows into JSON-LD `sameAs` *and* renders as a visible link beside ORCID under the publications summary. A **Wikidata item is still a human follow-up, not yet created** - see `docs/runbooks/2026-07-wikidata-entity.md`; once it exists, pasting the Q-ID into `personal.links.wikidata` needs no code change (`_same_as` takes every link key but `website`; `_network_for` already maps it). @claude review caught a `</script>` breakout in the inline JSON-LD (faq.yaml is agent-editable via `apply_edit`) - fixed in two layers: `validate_faq` rejects the substring, and both injection points escape `<` |
| 15 | Splice-neoepitope research write-up (warm-editorial pilot): long-form `/writeups/splice-neoepitopes/` article amplifying L5, 3 crawler-safe interactive figures, reusable warm-editorial design tokens (seed for a future site-wide restyle), write-ups registry | ✅ Done (merged 2026-07-21, `--no-ff`, PR #129 @claude-reviewed). Amplifier only (companion to code + forthcoming preprint; stakes no scientific claim); English-only (DE card links out); outside the `content/` schema; new `web-guard` guard `tests/test_writeup_static.py` (crawler text + ScholarlyArticle JSON-LD + OG + sitemap + bilingual cross-link). Site-wide warm-editorial restyle deferred to its own future phase |

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
schema/faq.schema.json         FAQ validation (bilingual, unique ids)
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
docs/runbooks/            operational runbooks (Wikidata entity creation)
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
just web-guard         # build the site + assert the public CV facts are crawler-readable in static HTML
just mcp-server        # run the CV MCP server (stdio) — point an MCP client at this
just mcp-dev           # MCP Inspector against the server (needs the mcp dep group)
just letter <slug>     # render a cover letter → applications/<slug>/cover-letter-*.{pdf,txt}
just jd-gap <slug>     # advisory JD↔CV keyword report (checklist, not a verdict) for an application
just check-pii         # scan staged files for PII leaks (content.private values + gitignored PII paths)
just install-hooks     # activate the committed git hooks (run once per clone — sets core.hooksPath=.githooks)
```

**First-clone setup:** run `just install-hooks` once to activate the git pre-commit PII guard.

validate + test + lint must all be green before merging anything.
The Worker has its own suite: `npm --prefix worker test` (vitest) + `npm --prefix worker run typecheck` (tsc - vitest alone does NOT typecheck); CI runs both in the `worker-test` job (#118).

## Conventions

- **TDD for non-trivial Python.** Tests first, watch them fail, then implement.
- **Tests never touch `content.private/`.** The real `private.yaml` is PII outside git's
  protection — tests write private overlays only under `tmp_path` (PDF build: via the
  `CV_PRIVATE_YAML` env override). A session-wide autouse guard in `tests/conftest.py`
  fails the run if any test mutates the real file (issue #77).
- **Golden snapshots.** Renderer outputs (`resume.json`, `person.jsonld`, `cv-{en,de}.txt`, `llms.txt`, web `content.*.json`) are byte-snapshotted with syrupy under `tests/__snapshots__/`; CI fails on unintended drift. Regenerate intentionally with `just snapshots-update` and eyeball the diff. `scripts/validate.py` also hard-fails reversed periods and advisory-warns implausible dates.
- **ATS guard.** The built PDF's text layer is CI-verified (`tests/test_ats_pdf.py` via the `ats-guard` job — name/email/headings/umlauts round-trip through `pdftotext`); the `release` job depends on it. Note: Typst letter-spacing makes `pdftotext` emit intra-word spaces in styled headings (e.g. `SELECTED PROJECTS` → `PROJ ECTS`), so the guard asserts only cleanly-extracting headings (`PROFILE`/`SKILLS`/`EDUCATION`/`PUBLICATIONS`) — don't re-add spaced ones. `/llms.txt` (llmstxt.org site map) is generated into `web/public/` for the deployed site (gitignored, like `person.jsonld`).
- **`llms.txt` is kept but inert as an AEO lever.** A 2026 deep-research pass (Ahrefs 137k-domain study; Otterly 90-day GEO experiment; John Mueller) found no major LLM vendor (OpenAI, Anthropic, Google) consumes external `llms.txt`, and ~97% of files carrying it get zero requests. We keep generating it (cheap, harmless, no downside) but must not treat it as a citation/visibility signal or invest further in it. The real answer-engine levers are entity disambiguation (schema.org `sameAs` → external profiles + a Wikidata item), answer-shaped content, and content freshness - not `llms.txt`.
- **AEO: the public tier must be crawler-readable; the deep tier must not be (Phase 14).**
  AI crawlers do not execute JavaScript, so every `content/` fact the CV wants cited has to be
  in the served HTML. This is guarded on every PR by the `web-guard` CI job, the website's
  answer to the PDF's `ats-guard`: it builds `web/dist` and then runs both
  `tests/test_static_facts.py` and `tests/test_faq_jsonld.py` - `web-guard` is what makes those
  tests actually execute in CI instead of silently skipping (both self-skip locally without a
  build). `test_static_facts.py` checks name, headline, every employer, every degree, every
  selected-project title, every publication title (loaded via `scripts.bib_loader`, so it
  guards the real LaTeX-cleaning), the front-loaded answer block, and the inline Person
  JSON-LD. The same test also asserts the inverse: no sentinel string from the synthetic
  `master-cv.example/` overlay may reach the public surface. (The check reads
  `master-cv.example/` only - it is a proof against the example, not the real gitignored
  overlay, which no test ever touches.) That exclusivity is deliberate - the overlay is the
  twin's alone, and being unable to crawl it is a reason to talk to the twin instead.
  `content/faq.yaml` (bilingual, schema-validated against `schema/faq.schema.json`) drives both
  the visible FAQ section and the `FAQPage` JSON-LD on the index pages, generated from the same
  data so they cannot drift; the FAQ section label is `{ en: "FAQ", de: "Häufige Fragen" }` in
  `content/labels.yaml` (not a literal "FAQ" translation - `tests/test_de_completeness.py`
  forbids identical EN/DE strings). Every FAQ answer must be grounded in a `content/` fact,
  never the `master-cv/` overlay: the availability answer, for example, is grounded in a new
  optional `personal.availability` LangString (`content/personal.yaml`, registered in
  `schema/cv.schema.json`) added specifically so that answer has a real fact to cite instead of
  being asserted from nowhere. `profile.{en,de}.yaml` also gained an `answer_block` field, a
  front-loaded answer-shaped paragraph rendered near the top of the profile section. FAQ and the
  answer block are web-surface features: they stay out of the PDF, `resume.json`,
  `person.jsonld`, `cv-*.txt`, and the twin chat context. Entity anchors (`personal.yaml`
  `links`) flow into JSON-LD `sameAs` automatically - a Google Scholar profile was added this
  way. A Wikidata item is the strongest remaining anchor but is intentionally not yet created;
  it is a documented, privacy-bounded human follow-up (`docs/runbooks/2026-07-wikidata-entity.md`)
  because creating it needs a live human account, not an agent action.
- **Atomic commits.** One logical change per commit. Plain commit messages — no Claude attribution / co-authored-by trailers unless explicitly requested.
- **Per-phase branches.** Phase N work happens on `phase-N-<topic>` branch, merged to `main` with `--no-ff` at the end of the phase to preserve the boundary in history.
- **Deploys outside GitHub Pages.** The digital-twin Worker (`worker/`) is the first repo
  component that deploys to Cloudflare (via `just worker-deploy` / `wrangler`), not GitHub
  Pages. The Pages build only needs the generated `dist/chat-context.md`; the Worker is
  deployed separately and holds `GEMINI_API_KEY` as a Worker secret (never in git). Inference
  uses the Google Gemini free tier via a best-first **model cascade** in `src/gemini.ts`
  (`gemini-3.5-flash` → `gemini-3-flash-preview` → `gemini-3.1-flash-lite` → `gemini-2.5-flash`
  → `gemini-2.5-flash-lite` → `gemini-2.0-flash` → `gemini-2.0-flash-lite` → `gemma-4-26b-a4b-it`):
  each model has its own free-tier daily request cap, so on a daily-quota 429 (or transient
  503/500) the Worker falls through to the next model — chaining eight rungs multiplies the
  combined headroom and keeps the twin reachable long after the top model's quota is
  spent instead of dying at ~20. The quota bucket is keyed by the *resolved* model, so `-latest`/
  `-001`/preview aliases that resolve to an existing rung add nothing; `gemini-3-flash-preview`
  is a distinct bucket and Gemma draws from a *separate* free-tier pool from the Gemini models —
  both verified live as real added headroom (#105). Thinking config is family-specific: the 3.x
  rungs take `thinkingLevel: "low"`, the 2.5 rungs take `thinkingBudget: 0`, and the 2.0 rungs +
  Gemma omit `thinkingConfig` entirely (any thinkingConfig 400s non-retryably on Gemma, and a
  stray budget on 2.0 could too, breaking the chain). Gemma still *thinks by default* and streams
  reasoning as `thought: true` parts (uncloseable), so `geminiChunkToEnvelopes`/`generateText`
  filter those out — raw chain-of-thought never reaches the answer. (The dense `gemma-4-31b-it`
  was rejected: it returns `MALFORMED_RESPONSE`/thoughts-only at our token budget; the lighter MoE
  `gemma-4-26b-a4b-it` answers cleanly — a live-verification catch.)
  Since #97 the cascade ends with a **cross-vendor rung**: when every Gemini/Gemma
  rung fails, the Worker falls through to **Cloudflare Workers AI**
  (`@cf/meta/llama-3.3-70b-instruct-fp8-fast` via the `env.AI` platform binding in
  `src/workersai.ts` - no new secret; free plan, so neuron exhaustion just throws
  and there is no billing surface). It fires on any non-ok Gemini terminal, also
  backs the digest cron, and an absent binding degrades gracefully to Gemini-only.
  The vendor-neutral SSE-to-client-envelope transformer lives in `src/sse.ts`;
  vendor modules supply only a pure chunk-to-envelopes mapper.

  There is no out-of-pocket cost at expected traffic; usage is also
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
- **Cross-references validated.** Every `refs: [L1]` in `experience.yaml` must resolve to a `content/projects/L1.en.yaml` file. Filename and `id:` field must match. Enforced by `scripts/validate.py` and `scripts/content_loader.py`. Every experience bullet **must** carry a `refs:` key (schema-`required`; use `refs: []` for a bullet citing no project) - a refs-less `{en, de}` bullet is all-langmap-keys, so `langstring.resolve_langstrings` would collapse it to a plain string and break every renderer (#99). The schema now fails `just validate` loudly instead.
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
  life-database (`timeline.yaml` + `inventory.yaml` + `narrative/*.md` + `opinions.md`) feeding the
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
- `docs/superpowers/specs/2026-07-14-phase-14-aeo-entity-presence-design.md` - Phase 14 design spec (AEO entity presence)
- `docs/superpowers/plans/2026-07-14-phase-14-aeo-entity-presence.md` - implementation plan for AEO entity presence (#113)
- `docs/superpowers/specs/2026-07-20-splice-neoepitope-writeup-design.md` - Phase 15 design spec (splice-neoepitope research write-up)
- `docs/superpowers/plans/2026-07-20-phase-15-splice-writeup.md` - implementation plan for the splice-neoepitope write-up (#128)

## Local-only files (not in git)

- `assets/photo.jpg` — headshot for the private PDF build, only included when `--photo` is passed. Optional; omit and the PDF renders without a photo. Kept gitignored by convention (PDFs are intentionally photo-less to avoid discrimination per German hiring norms).
- `content.private/private.yaml` — phone + address. Copy from `content.private.example/private.example.yaml` template.
- `applications/` — per-application cover-letter material (job descriptions, drafts, rendered letters). Gitignored; mirror the shape in `applications.example/`.
- `assets/signature.png` — handwritten signature for the cover-letter PDF, included only when present (mirrors the optional `--photo` pattern). Gitignored.
- `master-cv/` — the unfiltered superset overlay (`timeline.yaml` + `inventory.yaml` + `narrative/*.md` + `opinions.md`). Gitignored; mirror the shape in `master-cv.example/`.

## Don't

- Don't commit PII (`content.private/` is gitignored — keep it that way).
- Don't add `--no-verify` or skip pre-commit hooks.
- Don't add Claude attribution trailers to commits.
- Don't restructure existing files without scope being part of the current task.
- Don't introduce renderers that read content directly from the PDF — content/ is the only source of truth.
