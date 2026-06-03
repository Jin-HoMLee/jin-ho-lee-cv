---
name: cover-letter
description: >-
  Draft a tailored cover letter for a real job: paste the job description, do a
  short interview, and render a CV-matching PDF + plain text grounded strictly in
  the codified CV. Use when writing a cover letter / Anschreiben for a specific
  application.
allowed-tools: Bash(just letter *), Bash(just validate), Read, Write, Edit
---

# Cover letter — agent guide

Generate a job-specific cover letter grounded **strictly** in the codified CV plus
the user's interview answers. The CV (`content/`) is read-only here; everything you
write lands under the gitignored `applications/` overlay — **never** commit it, and
**never** edit `content/` from this flow.

## Golden rules
- **Never fabricate.** Every factual claim must trace to the CV or an explicit
  interview answer. Surface each unmet JD requirement to the user; honor their
  per-gap decision (transferable / omit / supply a real example) verbatim.
- **Salary only on request.** `profile.yaml`'s `salary_expectation` is context for
  you only — render it into a letter only if the JD asks for a Gehaltsvorstellung
  **and** the user confirms.
- **PII stays private.** The PDF merges the address from `content.private/` at render
  time and is gitignored. Never read or paste `content.private/` content.
- Default the letter language to the JD's language (German JD → DIN 5008 Anschreiben).

## Flow
1. **Intake** — user pastes the JD (or a path). Detect language, extract
   company / role / requirements, derive a sanitized slug
   (`<company>-<role>-<YYYY-MM>`), and scaffold `applications/<slug>/` with `job.md`
   + a draft `application.yaml` (use `applications.example/` as the shape).
2. **Profile check** — read `applications/profile.yaml`. If missing/incomplete, run
   the **one-time** evergreen interview (motivation, work style, availability,
   relocation, preferences) and write `profile.yaml`. Otherwise reuse it.
3. **Gap analysis** — match JD requirements against the CV + profile; list each
   requirement not clearly met.
4. **Interview** — ask why-this-company, which CV experiences/projects to emphasize,
   and walk every gap (the user decides each). Save `interview.yaml`.
5. **Draft** — write the body into `draft.md`, grounded strictly in CV + profile +
   interview answers. Plain paragraphs separated by blank lines (no salutation or
   closing — those are added at render time). Show it to the user.
6. **Revise** — edit `draft.md` per the user's wording changes.
7. **Render** — `just letter <slug>` → validates, then writes the full and
   body-only text files (and the PDF when Typst is installed) into the
   application folder.

See `reference.md` for the file/field map, the `just` recipe, and DIN 5008 / EN
business-letter conventions.
