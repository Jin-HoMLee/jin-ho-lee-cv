# Cover Letter generation — interview-driven, grounded in the codified CV (Phase 11)

**Date:** 2026-06-03
**Issue:** [#65](https://github.com/Jin-HoMLee/jin-ho-lee-cv/issues/65) — *feat: cover-letter generator — interview + JD → tailored letter (Phase 11)*
**Status:** Design (awaiting user review)

## 1. Goal

Make the codified CV produce **tailored cover letters** for real applications. The user
pastes a job description and does a short interview about the position; the system drafts a
letter **grounded strictly in the CV** (plus the user's interview answers), lets the user
revise it, and renders it to a PDF that **visually matches the CV** plus plain-text/markdown
for web forms (e.g. LinkedIn EasyApply).

This is the natural next consumer of the single source of truth: where the CV is *stable
career facts*, a cover letter is *per-application, job-specific* material. The generator
**reads `content/` read-only** for grounding and **writes only** into a new, gitignored
`applications/` space. The core architectural principle is preserved: **content is content;
the cover letter is just another consumer that never edits it.**

## 2. Decisions (settled in brainstorming)

| # | Decision | Choice |
|---|---|---|
| Storage | where application material lives | **Gitignored `applications/` overlay** (mirrors `content.private/`), with a committed `applications.example/` template. This repo is public — real letters must never be committed. |
| Output | what the user hands an employer | **PDF** (CV-matching letterhead + DIN 5008 layout) **+ plain text/markdown** (full and body-only flavors), with an **editable `draft.md`** as the working step in between. |
| Interview | how the interview scales over many applications | **Reusable evergreen profile + per-job top-up.** A one-time `profile.yaml` (motivation, work style, availability, salary range, relocation, preferences) is reused across all applications; each new application only asks job-specific questions. |
| Grounding | what to do with unmet JD requirements | **Never fabricate; flag gaps interactively.** The letter only claims what's in the CV + interview answers. During the interview the agent surfaces each unmet JD requirement and the user decides per-gap: *transferable / omit / supply a real example.* |
| Language | EN vs DE | **Both, default to the JD's language.** German JD → German Anschreiben (DIN 5008); English JD → English letter. Overridable per application. |
| Form factor | skill vs MCP vs both | **Skill primary + shared pure-Python core; MCP deferred.** The interview is conversational (skill-native); deterministic work (storage, grounding, rendering) lives in `scripts/cover_letter_core.py`, shaped so MCP could mirror it later (the Phase 10 seam) but **not built now** (YAGNI — a gitignored single-user overlay has no second consumer yet). |
| Output location | where rendered files land | **Inside the application folder** — each `applications/<slug>/` is a self-contained package (JD + draft + final PDF + text together). |
| Tracking | application status | A light `status` field on `application.yaml` (`draft`/`sent`/`interview`/`rejected`/`offer`) — grep-able record, **no dashboard or tracking tooling** (documented future). |

These are fixed; the rest of this spec is execution.

## 3. Architecture — one core, a skill, a renderer

```
                ┌──────────────────────────────────┐
                │  scripts/cover_letter_core.py      │  pure Python, no LLM/CLI coupling
                │  read_profile · write_profile      │  all path/PII guards live HERE
                │  list/create/read_application      │  reuses agent_core.read_cv for grounding
                │  save_interview · save_draft        │  + validate.py-style schema checks
                │  cv_facts · validate_application    │
                │  render_letter (pdf|text|all)       │
                └─────────────────┬──────────────────┘
              ┌───────────────────┴────────────────────┐
              ▼                                         ▼
   .claude/skills/cover-letter/SKILL.md       pdf/templates/cover-letter.typ
   prose: runs the interview, gap-flags,        reuses styles.typ + header.typ
   drafts grounded in cv_facts, then calls      (letter visually matches the CV) +
   the core to render. reference.md holds       DIN 5008 / EN business-letter body.
   grounding rules + DIN 5008 conventions.      Text serializer is deterministic.
```

**Why a shared core.** Every deterministic behaviour — and crucially the path/PII guards —
lives in `cover_letter_core.py`, unit-testable with no LLM in the loop. The skill is prose
that drives the user-facing interview and then calls the core. The Typst template and text
serializer are deterministic given fixed inputs (`application.yaml` + `draft.md`), so they
are snapshot/compile testable. The **only** nondeterministic artifact — the drafted body —
is an *input* to the renderer (`draft.md`), guarded by grounding rules + user review, never
a golden file.

**Grounding has exactly one CV source.** `cv_facts()` is a thin reuse of
`agent_core.read_cv` (which forces `private_path=None` — CV facts only, no PII). The letter
can never fork from the CV.

## 4. Data model & layout

```
applications/                          # gitignored (new .gitignore entry)
  profile.yaml                         # evergreen, reused across all applications
  <slug>/                              # slug = <company>-<role>-<YYYY-MM>, sanitized
    application.yaml                   # metadata (company, role, recipient, date, language, source, status)
    job.md                            # the pasted job description
    interview.yaml                    # per-job answers + gap decisions
    draft.md                          # editable letter body (the working step)
    cover-letter-<lang>.pdf           # rendered output (self-contained in the folder)
    cover-letter-<lang>.txt           # rendered text/markdown output
applications.example/                  # COMMITTED template (no real data)
  profile.example.yaml
  example-company-role-2026-06/
    application.example.yaml
    job.example.md
    interview.example.yaml
    draft.example.md
```

### 4.1 `profile.yaml` — evergreen, captured once

```yaml
# Reusable answers. Prose fields are {en, de}. Reused across every application.
motivation:        { en: "...", de: "..." }   # why this field / what drives you
work_style:        { en: "...", de: "..." }
availability:      "..."                       # notice period / earliest start
salary_expectation: "..."                      # range — CONTEXT ONLY, see §4.4
relocation:        "..."                        # willingness / constraints
preferences:       { en: "...", de: "..." }     # company size, remote, domain
```

### 4.2 `application.yaml` — per-job metadata

```yaml
company:  "Acme Genomics GmbH"
role:     "Bioinformatician"
language: "de"                 # letter language; defaults to detected JD language
date:     "2026-06-03"          # letter date (ISO; rendered per locale)
recipient:                      # optional — DIN 5008 address block
  name:    "Dr. Erika Mustermann"   # named contact, or null → "Sehr geehrte Damen und Herren"
  company: "Acme Genomics GmbH"
  address:
    street:      "Musterstraße 1"
    postal_code: "68159"
    city:        "Mannheim"
subject:  "Bewerbung als Bioinformatician"   # Betreff
source:   "LinkedIn EasyApply"
url:      "https://..."
status:   "draft"               # draft | sent | interview | rejected | offer
```

### 4.3 `interview.yaml` — per-job answers + gap decisions

```yaml
why_company: "..."             # why THIS company/role
emphasis:                      # CV experiences/projects to foreground for this JD
  - "L1"                       # CV project id, or free text
  - "GCP migration"
gaps:                          # JD requirements not clearly met, + how to handle each
  - requirement: "5y Rust"
    decision:    "transferable"   # transferable | omit | example
    note:        "frame C/performance work honestly"
notes: "..."                   # any extra context for the draft
```

### 4.4 PII & salary handling

- The **PDF** needs the sender's full address + date for a proper Anschreiben. These come
  from the existing `content.private/private.yaml` overlay, merged **only** at render time —
  exactly like the existing `pdf/build.py --private` path. The rendered file is gitignored.
- `salary_expectation` is **context for the agent only**. It is **never** written into a
  letter unless the JD explicitly requests a Gehaltsvorstellung **and** the user confirms
  during the interview.

## 5. The core — `scripts/cover_letter_core.py`

Pure Python, mirrors `agent_core.py` conventions. Module constants:

```python
REPO_ROOT   = Path(__file__).resolve().parent.parent
APPS_DIR    = REPO_ROOT / "applications"
APP_SCHEMA  = REPO_ROOT / "schema" / "application.schema.json"
PROFILE_SCHEMA = REPO_ROOT / "schema" / "profile.schema.json"
```

### 5.1 Path safety — `_safe_application_path` (the security spine)

Same guard style as `agent_core._safe_content_path`: rejects absolute paths, `..`/dot
segments, non-allowed suffixes, symlink escapes out of `applications/`, and any path
resolving outside `APPS_DIR`. All write functions route through it. (It guards
`applications/`, never `content/` — the cover letter core never writes CV content.)

### 5.2 Functions

| Function | Behaviour |
|---|---|
| `read_profile(*, apps_dir=APPS_DIR)` | Return the evergreen profile dict; `{}` if absent. |
| `write_profile(data, *, apps_dir=APPS_DIR)` | Validate against `profile.schema.json`, atomic write (`mkstemp`+`os.replace`). |
| `list_applications(*, apps_dir=APPS_DIR)` | Sorted slugs (dirs only, excludes `profile.yaml`). |
| `create_application(slug, *, job_text, meta, apps_dir=APPS_DIR)` | Sanitize+guard slug, refuse collision, scaffold the dir, write `job.md` + `application.yaml`. |
| `read_application(slug, *, apps_dir=APPS_DIR)` | Bundle `{application, job, interview, draft}` (missing parts → `None`). |
| `save_interview(slug, data, *, apps_dir=APPS_DIR)` | Validate-light + atomic write `interview.yaml`. |
| `save_draft(slug, body, *, apps_dir=APPS_DIR)` | Atomic write `draft.md`. |
| `cv_facts(*, lang="en", target="bridge")` | Thin reuse of `agent_core.read_cv` (PII-safe) — the grounding source. |
| `validate_application(slug, *, apps_dir=APPS_DIR)` | Schema + sanity (valid language, plausible date, required fields). Returns `{"valid", "errors", "warnings"}`. |
| `render_letter(slug, *, fmt="all", apps_dir=APPS_DIR)` | Validate-first; render `fmt ∈ {pdf, text, all}` into the app folder. PDF via Typst; **skips PDF gracefully if `typst` absent** (returns `skipped`, mirrors `rerun_renderers`). |

Atomic writes reuse the `apply_edit` pattern (`mkstemp` in the target dir + `os.replace`).
Subprocess calls to Typst use `subprocess.run([...], shell=False)`.

## 6. The skill — `.claude/skills/cover-letter/`

`SKILL.md` orchestrates a 7-step flow; `reference.md` holds grounding rules + DIN 5008/EN
conventions and is **drift-guarded** against the `justfile` + schemas (like the `cv` skill).

1. **Intake** — user pastes the JD (or gives a path). Detect language, extract
   company/role/requirements, derive a sanitized slug, scaffold the folder
   (`create_application`), write `job.md` + a draft `application.yaml`.
2. **Profile check** — `read_profile`; if missing/incomplete, run the **one-time** evergreen
   interview and `write_profile`. Otherwise skip.
3. **Gap analysis** — match JD requirements against `cv_facts` + profile; build the gap list.
4. **Per-job interview** — ask why-this-company, which experiences to emphasize, and walk
   each gap (*transferable / omit / example* — user decides every unmet claim). Save to
   `interview.yaml`.
5. **Draft** — generate the body grounded **strictly** in `cv_facts` + profile + interview
   answers, never inventing. `save_draft`; show it to the user.
6. **Revise** — user edits wording; skill updates `draft.md`.
7. **Render** — `render_letter(slug, fmt="all")` → PDF + text into the app folder.

### 6.1 Grounding rules (in `reference.md`)

- Every factual claim must trace to the CV (`cv_facts`) or an explicit interview answer.
- Unmet JD requirements are surfaced to the user, never papered over; the user's per-gap
  decision is honored verbatim.
- Salary appears only on explicit JD request + user confirm (§4.4).
- The agent never edits `content/` (CV facts) from this flow.

## 7. Rendering

### 7.1 PDF — `pdf/templates/cover-letter.typ`

Reuses `pdf/styles.typ` + the existing `header.typ` letterhead so the letter visually
matches the CV (same name/accent/contact block). Adds a DIN 5008 body:

- sender block, right-aligned date,
- recipient address block (named contact or company),
- **bold Betreff / subject line**,
- salutation (`Sehr geehrte Damen und Herren` / `Sehr geehrte/r <name>` / `Dear …`),
- body paragraphs (from `draft.md`),
- closing (`Mit freundlichen Grüßen` / `Sincerely`) + typed name,
- optional signature image if `assets/signature.png` exists (mirrors the optional `--photo`
  pattern; absent → typed name only).

Typst is invoked from `render_letter` (data serialized to a cache JSON, `typst compile` with
`--input` flags), mirroring `pdf/build.py` — but kept separate from the CV build to avoid
coupling.

### 7.2 Text / Markdown — deterministic serializer

Emits two flavors from the same inputs:

- **full** — sender/date/recipient header + subject + salutation + body + closing + name
  (for pasting into an email).
- **body-only** — salutation → signature, no letterhead (what LinkedIn EasyApply-style
  boxes usually want).

Deterministic given `application.yaml` + `draft.md`, so it is golden-snapshot tested.

### 7.3 Justfile

- `just letter <slug>` — validate-first, render all formats into the app folder.
- (PDF skips gracefully when Typst is absent; text always renders.)

## 8. Testing

- **TDD** for the core: path guards (`_safe_application_path` rejects `..`/abs/symlink/
  escape), atomic writes, `create_application` collision refusal, `validate_application`
  catches bad language/date/missing fields, `render_letter` skips PDF when `typst` absent,
  the core **never writes under `content/`**, `cv_facts` carries no PII.
- **Golden snapshots** (syrupy) for the deterministic **text** renderer: fixture
  `application.yaml` + `draft.md` → stable `.txt` (both flavors). Regenerated via
  `just snapshots-update`.
- **PDF**: compile-smoke check on a fixture (asserts `cover-letter.typ` compiles, no text
  round-trip ATS guard needed — a letter is not ATS-parsed like the CV).
- **Skill drift-guard**: every `just` recipe / schema field the skill docs mention must
  exist in the authoritative sources (`justfile`, `*.schema.json`) — never prose-vs-prose.
- **Not tested**: the LLM-drafted body (nondeterministic) — guarded by grounding rules +
  user review, as above.

`just validate`, `just test`, `just lint` must all be green before merge.

## 9. Conventions honored

- `applications/` gitignored; `applications.example/` committed (documents the shape).
- Never commit PII (`content.private/` stays gitignored; letter PDFs that merge it are
  gitignored too).
- Atomic commits, plain messages; branch `phase-11-cover-letter`, `--no-ff` merge to `main`.
- TDD for non-trivial Python; golden snapshots for deterministic renderers.
- The implementation plan's final task updates the **CLAUDE.md phasing table (new Phase 11
  row)** + any changed convention (the "applications overlay" + cover-letter skill).

## 10. Out of scope (documented future / YAGNI)

- **MCP tools** for the cover-letter core — the Phase 10 seam is left open (core takes
  `apps_dir`/schema params), but no MCP surface is built; a gitignored single-user overlay
  has no second consumer yet.
- Application **status dashboard / tracking tooling** — the `status` field exists; no UI.
- Emailing / sending letters, multi-recipient, web UI for letters.
- Auto-scraping JDs from URLs (user pastes the text).
