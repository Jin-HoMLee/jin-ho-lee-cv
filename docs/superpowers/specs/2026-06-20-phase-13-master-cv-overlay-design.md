# Phase 13 — `master-cv/` overlay (master-CV / life-database) — Design

**Date:** 2026-06-20
**Status:** Approved (brainstorm complete; ready for plan)
**Issue:** [#92](https://github.com/Jin-HoMLee/jin-ho-lee-cv/issues/92) (Phase 13) · follow-up CV reconciliation: [#93](https://github.com/Jin-HoMLee/jin-ho-lee-cv/issues/93)

## Problem

There is no single ground-truth place that holds **all** of Jin-Ho Lee's
biographical history. `content/` is deliberately **sharp** — a curated CV (3
consolidated experience blocks, ~12 skills, 2 awards, 8 project deep-dives),
the product of Phases 7/8a/8b. That curation is correct and must be preserved:
the rendered CV should contain only the relevant facts.

But the sharp CV is a *selection*. The superset — every internship, every
certificate, the full skill inventory, dated volunteering, personal narrative —
lives nowhere structured. It's wanted for four jobs:

1. **Digital twin** — richer, more personal conversation grounded in the full history.
2. **Lookup** — one place to answer "when exactly was KRIBB? what was that cert?".
3. **Cover-letter / CV selection** — the superset to decide include/exclude per application.
4. **Future CV variants** — the reservoir a new focus is selected from.

This is the well-documented **"master CV" / "master resume"** pattern: keep one
complete, unfiltered record; cut tailored versions from it. The twin simply
treats that master-CV as its **knowledge base** (Karpathy "LLM wiki" pattern —
plain files an agent reads directly).

## Goal

Introduce a **`master-cv/`** overlay holding the unfiltered superset, feeding the
twin and human/agent lookups, **without touching the sharp CV or any existing
renderer**. Seed it with the user's comprehensive history table.

## Non-goals / out of scope

- **No changes to `content/` or the CV renderers** (PDF/web/JSON/text/llms). The
  CV stays sharp. CV-side improvements surfaced during the gap analysis (M.Sc.
  major, thesis titles, the hackathon award, GCP cert, the RISE grant-acquisition
  fact) are deliberately deferred to a **separate follow-up issue**, not Phase 13.
- **No vector store / RAG engine.** The twin already injects a compiled Markdown
  blob; we extend that blob. Plain-files-an-agent-reads, no retrieval infra.
- **References stay in `applications/references.md`** per existing policy; the
  master-cv points to them, does not duplicate them.

## Privacy model (three tiers)

| Layer | Path | Feeds | Visibility |
|---|---|---|---|
| True PII | `content.private/` | nothing public; never the twin | gitignored |
| Sharp CV | `content/` | all renderers **+** twin | committed (public) |
| **Master-CV** | **`master-cv/`** (new) | twin **+** lookups + cover-letter/CV selection | **gitignored overlay** |

`content/` is a curated **selection** from the superset `master-cv/`. Because the
repo is public and the twin answers public visitors, `master-cv/` is a
**gitignored local overlay** (mirrors `content.private/` + `applications/`): it is
never committed, never world-readable as raw files, but is present on the user's
machine at `just worker-deploy` time, so the twin still receives the full data.

## Architecture

### `master-cv/` structure (hybrid: structured spine + narrative)

```
master-cv/                     # gitignored — user's machine; bundled into twin at deploy
  timeline.yaml                # structured spine: full chronology
  inventory.yaml               # full skills/tools/domains/industries superset
  narrative/                   # Markdown — warm personal layer for the twin
    career-story.md            #   motivations, throughlines, why-moved
    personal.md                #   interests, language detail, anecdotes
master-cv.example/             # COMMITTED template (synthetic data) — documents the shape
schema/master-cv.schema.json   # light validation for timeline.yaml + inventory.yaml
```

Name is final: `master-cv/` (documented best-practice term; matches the repo's CV
identity; the twin is its first consumer).

#### `timeline.yaml` — the structured spine

A flat, chronological list of entries. Every position, internship, degree,
certificate, award, and volunteering stint Jin has ever had — the complete raw
archive (~25 entries), including the items that are *also* on the sharp CV (those
appear here as raw facts; `content/` holds the *rewritten/curated* phrasing — the
two are different representations, so there is no field-level duplication of a
single source of truth).

Entry shape (common fields + type-specific optional fields):

```yaml
- id: imp-vienna-2019            # unique kebab-case slug
  type: research                 # employment|research|internship|education|certificate|award|volunteering
  title: "Doctoral Researcher"   # role / degree / certificate name / award name
  org: "Research Institute of Molecular Pathology (IMP)"
  location: "Vienna, Austria"
  start: "2019-08"               # YYYY-MM (or YYYY); null allowed for undated
  end: "2019-10"                 # null/omitted ⇒ ongoing
  tags: ["structural biology", "biochemistry"]
  summary: "Short factual description of the work."
  # type-specific optional: degree/field/thesis (education), issuer/status (certificate/award)
```

`schema/master-cv.schema.json` validates structure lightly: `id`+`type` required,
`type` is an enum, dates are `YYYY` or `YYYY-MM` or null. Permissive on
type-specific extras (`additionalProperties` allowed) — this is a personal DB,
not a formal ATS record.

#### `inventory.yaml` — the full skills/tools superset

Flat, generous lists (superset of `content/skills.yaml`), e.g.:

```yaml
programming: ["Python", "R", "SQL", "MATLAB", "Perl"]
ml_ai: ["scikit-learn", "TensorFlow", "Keras", "LSTM", "OpenCV", "MediaPipe", "OpenAI / DALL·E 3"]
data_eng: ["BigQuery", "dbt", "Docker", "Pydantic", "Snakemake", "Conda"]
databases: ["PostgreSQL", "MySQL", "BigQuery", "DBeaver"]
bi: ["Looker", "MicroStrategy"]
cloud: ["Google Cloud", "Vertex AI"]
bioinformatics: [...]
domains: ["Marketing Automation", "Campaign Management", "Loyalty Programs", "Generative AI", ...]
industries: ["Financial Services", "Scientific Research", "EdTech / Bootcamps", "Digital Health"]
```

Keys are free-form; the schema only checks that values are string lists.

#### `narrative/*.md` — the personal layer

Free-form Markdown for the warmth the twin needs (motivations, throughlines,
anecdotes, language/interest detail) that does not fit YAML. Compiled verbatim
into the twin context and the master-cv export.

### Data flow

- **CV renderers** (PDF/web/JSON/text/llms) → read `content/` **only**. *(unchanged)*
- **Twin** (`render_chat_context.py`) → `content/` **+** `master-cv/`, **graceful
  no-op when the overlay is absent** (exactly like `content.private/`: CI and any
  clone without the overlay still compiles a valid, CV-only twin context).
- **New master-cv export** (`render_master_cv.py` → `dist/master-cv.md`) → the full
  union, plainly formatted = the single "look up anything about me" artifact.

`render_chat_context.py` and `render_master_cv.py` share **one** union helper
(`full_profile(content, master_cv)`), DRY. The chat-context wraps it with the
twin's system framing; the export presents it plainly.

### New / changed code

- `scripts/master_cv_loader.py` (new) — `load_master_cv(path) -> MasterCV | None`
  (parses `timeline.yaml`, `inventory.yaml`, `narrative/*.md`; returns `None` when
  the overlay dir is absent); light schema validation. Overlay path resolved from
  `MASTER_CV_DIR` env (default `<repo>/master-cv`) so tests can point at a
  `tmp_path` fixture — mirrors the `CV_PRIVATE_YAML` test-override pattern.
- `scripts/render_master_cv.py` (new) — builds `dist/master-cv.md` from
  `content/` + `master-cv/`.
- `scripts/render_chat_context.py` (edit) — append master-cv sections when the
  overlay is present; unchanged output when absent.
- `schema/master-cv.schema.json` (new) — light validation.
- `scripts/validate.py` (edit) — validate `master-cv/` **only if present**
  (graceful skip keeps CI green without the overlay).
- `justfile` (edit) — `just build-master-cv`; `build-chat-context` keeps working;
  `worker-dev`/`worker-deploy` pick up the richer context automatically.
- `.gitignore` (edit) — ignore `master-cv/` (keep `master-cv.example/`).
- `scripts/check_pii.py` (edit) — add `master-cv/` as a blocked PII path (commit guard).
- `master-cv.example/` (new, committed) — synthetic template.
- `CLAUDE.md` (edit, final task) — Phasing row + a `master-cv/` convention note.

### Safety (non-negotiable)

- **Never committed:** `.gitignore` + `check_pii.py` both block `master-cv/`.
- **Never snapshotted with real data:** the twin's golden snapshot tests use a
  **synthetic fixture overlay** (committed under `tests/`), never the real
  `master-cv/`. A session-wide guard (extending the `content.private/` tripwire in
  `tests/conftest.py`) fails the run if any test reads the real overlay dir.
- **Graceful absence proven:** a test asserts `render_chat_context` with no
  overlay produces exactly the current CV-only output (so CI, which has no
  overlay, stays byte-identical and green).

## First ingest — the history table → `master-cv/`

The entire table is transcribed into `master-cv/`:

- **`timeline.yaml`** — all ~25 positions/internships/degrees/certs/awards/
  volunteering with dates + tags, including the granular research stops omitted
  from the sharp CV (IMP Vienna, Bundeswehr Radiobiology, KRIBB, MPI Medical
  Research, RLP AgroScience, Tutoria, …), every certificate (incl. the
  fishing/badminton licenses — it is the complete record), the hackathon award,
  the DAAD RISE **grant-acquisition + recruiting** fact (typed `employment`/
  research credit, not `award`), and `status: in-progress` for the GCP cert.
- **`inventory.yaml`** — the full skill/tool/domain/industry superset.
- **`narrative/`** — seeded from the table's softer material (interests, language
  detail) plus a starter `career-story.md` the user can expand.

This ingest is committed only into the **gitignored** overlay on the user's
machine; the `master-cv.example/` template (committed) shows the shape with
**synthetic** data only.

## Testing strategy (TDD)

- `master_cv_loader`: parses a `tmp_path` fixture overlay; returns `None` when absent.
- `render_master_cv`: golden snapshot against a **synthetic fixture** overlay.
- `render_chat_context`: existing snapshot stays **CV-only** (graceful-absence
  proof); a **new** test with the fixture overlay snapshots the union (synthetic).
- `check_pii`: `master-cv/` is a blocked path; extend the ci.yml/pre-commit
  drift-guard.
- `validate.py`: validates a fixture overlay; skips gracefully when absent.
- `conftest.py`: tripwire fails if any test touches the real `master-cv/`.

## Process

Standard repo phase flow: this brainstorm → this spec → `writing-plans` →
subagent-driven execution with review checkpoints → `--no-ff` merge to `main`.
The plan's final task updates the CLAUDE.md Phasing table (new Phase 13 row) and
the conventions section. A follow-up issue captures the deferred CV-reconciliation
fixes.
