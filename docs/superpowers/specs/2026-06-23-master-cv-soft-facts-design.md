# master-cv soft-facts ingestion — design

**Date:** 2026-06-23
**Topic:** Enrich the `master-cv/` overlay (and thus the digital twin + `dist/master-cv.md`)
with *peer-attested soft facts* — how others experience Jin-Ho to work with — distilled
from real reference documents, with all third-party PII stripped before it reaches the
public twin.

## Problem

The sharp public CV (`content/`) carries hard facts: roles, projects, skills, publications.
It says nothing about *what Jin-Ho is like to work with* — the soft, character-level signal
that only colleagues and referees can attest to. Three real documents hold exactly that:

1. **Reference letters** — academic/professional recommendations.
2. **German Arbeitszeugnis** — the coded employer reference (where phrasing encodes a grade).
3. **Honey shower** — a team farewell ritual: colleagues write unfiltered appreciation notes.

These are *peers describing him*, not self-description — the most credible kind of soft fact,
and ideal grounding for the digital twin when a visitor asks "what's he like to work with?".
But the documents are full of **third-party PII** (referee, manager, and colleague names) and
must never be committed or surfaced publicly verbatim.

## Why the master-cv overlay is the right home

`master-cv/` is the gitignored life-database **superset** that feeds the digital twin and the
`dist/master-cv.md` lookup export; the public CV is a curated *selection* from it. Soft facts
that are deliberately kept out of the sharp CV but should inform the twin belong exactly in
this layer. The overlay is PII-guarded (`.gitignore` + `check_pii.py`) and only a synthetic
`master-cv.example/` is ever committed.

## Design

### 1. Destination — one new narrative file

`master-cv/narrative/how-others-describe-me.md` (gitignored).

No code change is required. `scripts/master_cv_loader.py` globs `narrative/*.md`
(`nd.glob("*.md")`, keyed by filename stem) and `scripts/profile_union.py::_narrative`
concatenates **every** narrative stem in sorted order. A new file is therefore auto-ingested
into both consumers:

- the digital-twin chat-context (`scripts/render_chat_context.py` → the bundle deployed by
  `just worker-deploy`), and
- the `dist/master-cv.md` lookup export (`just build-master-cv`).

The file's own `# How others describe me` H1 becomes its section header in the bundle.

### 2. Sources & handling

The three source PDFs are read from the session scratchpad and **left there** — raw documents
never enter the repo (they carry third-party PII). Only the sanitized, by-trait distillation
lands in the overlay file.

### 3. Structure — by trait, synthesized

The file is organized by **theme/trait** (e.g. *learns fast*, *ownership & reliability*,
*collaboration*, *scientific rigor* — actual themes driven by what the documents say), merging
what all three sources contribute under each trait. Where a trait appears in more than one
source, that convergence is stated explicitly — independent agreement across a referee, an
employer reference, and peers is itself the credibility signal. Light, generic source tags
indicate which *kind* of document a point came from, never which person.

### 4. Sanitization & honesty guardrails

- **Strip all individual names.** Generic attribution only: "a referee", "a former manager",
  "colleagues in a team farewell". No referee/manager/colleague name reaches the twin.
- **Employer.** Referenced only at the role/era level that is *already public* on the CV, and
  never tied to a named individual. (Adjustable to fully-generic if preferred.)
- **Arbeitszeugnis decoded faithfully.** Coded German grades are translated honestly — a top
  grade stays top, a "good" stays good; no inflation of the coded rating.
- **Framed as testimony**, not invented first-person claims ("colleagues described…", not
  "I am…"). Every line traces to a source document — no fabrication.
- **Doctoral research** stays "doctoral research", never "PhD"/"Dr." (standing repo honesty
  rule).

### 5. Committed artifact (the only git-tracked change)

A **synthetic** `master-cv.example/narrative/how-others-describe-me.md`, mirroring the new
file's shape so the public template stays complete (per the CLAUDE.md "synthetic example
committed" convention). The real overlay file remains gitignored and `check_pii.py`-blocked.

## Verification

- `just build-master-cv` and `just build-chat-context` regenerate cleanly and **include** the
  new traits.
- Grep both generated outputs to confirm the traits appear **and** that no stripped name
  leaks into either bundle.
- `just validate` + `just test` green. (Narrative `*.md` is free-form, not schema-validated;
  the change touches no schema. The committed synthetic example must not break any snapshot
  or example-shape test.)

## Out of scope (optional follow-up)

`applications/references.md` (the cover-letter overlay) distills the *same kind* of reference
material for a *different* consumer (cover-letter grounding). It is intentionally kept separate
here. A later, optional task could refresh `references.md` from the same mined notes so both
overlays stay consistent — tracked separately, not part of this change.
