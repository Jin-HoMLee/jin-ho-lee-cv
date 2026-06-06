---
name: cover-letter
description: >-
  Draft a tailored cover letter for a real job: paste the job description, do a
  short interview, and render a CV-matching PDF + plain text grounded strictly in
  the codified CV. Use when writing a cover letter / Anschreiben for a specific
  application.
allowed-tools: Bash(just letter *), Bash(just jd-gap *), Bash(just validate), Read, Write, Edit
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
3. **Gap analysis** — run `just jd-gap <slug>` for an advisory JD↔CV keyword report
   (a checklist, not a verdict: it over-surfaces — prune the false alarms; a term
   absent from the whole CV is a "do not claim this" flag). Combine it with your own
   read to list each JD requirement not clearly met by the CV + profile.
4. **Interview** — ask, in the user's own words:
   - the specific moment or detail that drew them to *this* company/role (the
     opening hook + the one unfakeable company detail);
   - one concrete moment from the experience to emphasize — problem, what they
     actually did, outcome — captured **verbatim** into `interview.yaml: voice_sample`
     (it is the voice exemplar; do not paraphrase it);
   - which CV experiences/projects to foreground, and a walk through every gap
     (the user decides each).
   If `profile.yaml` has no `joy`, ask once what they genuinely enjoy about this kind
   of work (not what they're good at) and save it to `profile.yaml: joy`.
   Save the per-job answers to `interview.yaml`.
5. **Draft** — write the body into `draft.md`, grounded strictly in CV + profile +
   interview answers (and, if present, the work-style themes in `references.md` —
   paraphrase those, never reuse them verbatim: they are referees' words *about*
   Jin-Ho, not his own). Before drafting, read the "How to write the body" and "AI tells
   & clichés to avoid" sections in `reference.md`, and treat the raw `interview.yaml`
   answers + `profile.yaml` as a `<voice_sample>`: these are Jin-Ho's
   own words — match his diction, sentence rhythm, and formality, and reuse his actual
   phrasings; do **not** upgrade his plain, specific words into polished corporate
   English (that laundering is the main way letters read as AI). Apply the drafting
   principles and the AI-tells list to **every paragraph** — the model will not
   generalize the rule from one paragraph to the rest. Then run a silent self-critique
   pass: score the draft 1–10 on Directness, Rhythm, Authenticity (matches the voice
   sample), Specificity (every claim CV/interview-traceable), and Density (anything
   cuttable); rewrite any sentence that pulls a dimension below 7; re-score once. Plain
   paragraphs separated by blank lines (no salutation or closing — those are added at
   render time). Show the user the revised draft with a one-line note that you ran a
   self-critique pass (not the scores).
6. **Revise** — edit `draft.md` per the user's wording changes.
7. **Render** — `just letter <slug>` → validates, then writes the full and
   body-only text files (and the PDF when Typst is installed) into the
   application folder.

See `reference.md` for the file/field map, the `just` recipe, and DIN 5008 / EN
business-letter conventions.
