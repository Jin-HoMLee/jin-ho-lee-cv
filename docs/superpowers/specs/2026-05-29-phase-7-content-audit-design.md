# Design: Phase 7 — Content audit (bring CV up to date)

**Date:** 2026-05-29
**Owner:** Jin-Ho Lee
**Parent spec:** [`2026-05-21-codified-cv-design.md`](./2026-05-21-codified-cv-design.md)
**Predecessor work:** DOI fields (merged 2026-05-29, commit `f270ea6`)
**Issue:** [#18 — Content audit: bring CV up to date](https://github.com/Jin-HoMLee/jin-ho-lee-cv/issues/18)

## 1. Scope

The CV infrastructure is complete (six phases shipped); this phase reconciles the **content** against ground truth. The user supplied a comprehensive career table (2012–2026), which was diffed against every `content/` file. The finding: the content is **deliberately curated** toward a "Cancer Immunogenomics | Bioinformatics" positioning, **not stale** — so this phase fixes factual/date errors, tightens link hygiene, and adds two **on-theme** reinforcements, while respecting the curation.

Chosen scope (of three options brainstormed): **B — Correctness + on-theme reinforcement.** Correctness fixes plus the highest-value on-theme additions (B.Sc. *Bioinformatics* major; a minimal Awards section). Rejected: A (correctness only — leaves real on-theme signal on the table) and C (full reconciliation — re-expands the history that was just pruned).

Six workstreams, independent in code, bundled under one phase/branch:

1. **Date & factual corrections** (content-only).
2. **Settled additions** — skills + Italian language (content-only).
3. **Identity / links** — ORCID + website (content-only).
4. **Publications ordering** — deprioritize the off-theme 2025 marketing chapter (renderer logic).
5. **On-theme schema additions** — education `field` + a new `awards` section (schema + renderers).
6. **Research-bullet enrichment** — fold a variant-calling phrase into the research entry (content-only).

## 2. Goal

After Phase 7:

- Every date in `content/` matches the user's ground-truth table (most importantly L1/SNU = 2015-08→2015-11, not 2018–2019).
- EN and DE profile openers agree and neither asserts a "current" Cintellic role (the user is between roles as of 2026-05).
- `skills.yaml` surfaces the splice-aligner, variant-handling, and TCR-pMHC structural-modeling tools that back the immunogenomics narrative.
- `languages.yaml` lists Italian; `personal.yaml` carries the ORCID iD and the live-site URL.
- The publications list leads with peer-reviewed science; the 2025 marketing chapter is retained but no longer headlines.
- The B.Sc. *Bioinformatics* major and a competitive **DAAD PROMOS → SNU** scholarship (the funding behind the flagship L1 work) are visible.
- `just validate && just test && just lint` are green; `just build-formats && just build-text && just web-build` regenerate cleanly with EN/DE parity.

## 3. Non-goals

- **No certificates / references / interests sections.** Only the GCP cert is on-theme and it is unearned; references are real third parties (publishing names/contact on a public site is a consent/privacy issue); interests are off-theme. Explicitly out.
- **No un-collapsing the research history.** The single `research` experience entry stays a roll-up of the 2012–2022 positions; the ~12 distinct historical roles are not re-expanded.
- **No M.Sc. major.** *Biophysical Chemistry* is off-theme (the imaging/biophysics strand the curation de-emphasized); the new education `field` is populated for the B.Sc. only.
- **No DOI rework.** Just merged; untouched here.
- **`volunteer.yaml` untouched.** The user confirmed the 7 orgs beyond the table are real.
- **No new long-form prose / profile rewrite** beyond the DE opener parity fix and the one research-bullet enrichment phrase.
- **Marketing chapter not dropped.** Kept (deprioritized via ordering), per user choice.

## 4. Workstream 1 — Date & factual corrections (content-only)

All project date edits apply to **both** `.en.yaml` and `.de.yaml` (period fields are language-neutral but duplicated per file).

| Target | Current | New | Rationale |
|---|---|---|---|
| `projects/L1` period | 2018-09 → 2019-03 | **2015-08 → 2015-11** | SNU neoantigen internship was Aug–Nov 2015 (table). Flagship on-theme project; was wrong by ~3 years. Makes L5's "2015 SNU" reference consistent. |
| `projects/L2` period | 2013-10 → 2014-06 | **2014-04 → 2014-05** | NCT bachelor-thesis work (HLA typing) was Apr–May 2014 (table). |
| `projects/L3` period start | 2017-05 | **2017-02** | KIP researcher started Feb 2017 (table); end 2018-08 unchanged. |
| `projects/L4` period | 2018-09 → 2022-07 | **unchanged** | Deliberately retained roll-up of the full doctoral track (Bundeswehr 2018 / IMP Vienna 2019 / FZ Jülich 2020–22). Defensible; not an error. |
| `experience.yaml` `research` start | 2014-06 | **2014-04** | Must not post-date its earliest referenced sub-project (L2 = 2014-04 after the fix above). |
| `profile.de.yaml` opener | "Aktuelle Industrietätigkeit bei Cintellic …" (asserts current) | past/neutral framing matching the EN opener | User is between roles; EN already neutral. Bring DE to parity, no "current" claim. Keep all other DE claims/journals/counts identical to EN. |

No experience-entry org renaming is required (the "Cintellic / International Bank" label correctly captures the employer-of-record + bank-assignment structure and the ended span).

## 5. Workstream 2 — Settled additions (content-only)

- **`skills.yaml`** (`Bioinformatics & ML` category):
  - `Genomics` group: add `MapSplice` (the L1 aligner) and `samtools/bcftools`. (`HISAT2/STAR` already present — do not duplicate.)
  - Add a **new `Structural Biology` sub-group** with `TCRdock / AlphaFold v2` and `Mol*` (currently only in the L5 project tech list). A dedicated sub-group makes the TCR-pMHC structural capability legible vs. burying it in `Immunology`.
  - Item strings are language-neutral; only the group `label` needs `{ en, de }` (DE label for the new sub-group: `Strukturbiologie`).
- **`languages.yaml`:** add `{ name: { en: "Italian", de: "Italienisch" }, proficiency: "basic" }`. The schema enum already permits `basic`.

## 6. Workstream 3 — Identity / links (content-only)

- **`personal.yaml` `links`:**
  - `orcid: "0009-0001-8784-1771"` (currently `null`). Valid ORCID (checksum verified); empty profile is fine — it is a persistent identifier.
  - add `website: "https://jinholee.is-a.dev/"`.
  - `researchgate` kept; `linkedin`/`github` unchanged.
- Downstream (no renderer change needed): JSON-LD `sameAs` and JSON Resume `profiles` already filter falsy and will pick up both new links; the ORCID resolver URL is `https://orcid.org/0009-0001-8784-1771`. Confirm `linkedin`/`github`/`researchgate`/`website` all emit, and `orcid` no longer drops out as null.

## 7. Workstream 4 — Publications ordering (renderer logic)

Keep `lee2025_marketing_automation` in `publications.bib`. Today the renderers sort by year descending, which floats the 2025 marketing chapter to the **top** — the opposite of the user's "keep, deprioritize" intent.

**Approach:** introduce a stable secondary sort so **peer-reviewed science sorts before applied/industry**, then year-descending within each group. Implementation centralizes in `scripts/bib_loader.py` (the single ordering authority all renderers consume) so text / JSON Resume / JSON-LD / web stay consistent with no per-renderer logic.

- Classification: derive an ordering rank from the existing `type` field plus a small explicit exclusion. The marketing chapter is `type: book-chapter`, `authorship: first`, but is the **applied/industry** outlier; the 2021 IntechOpen chapter is also `book-chapter` but is research. A clean discriminator is needed.
- **Decision:** add an optional `category` field to the relevant `.bib` entry (`category = {applied}`) read by `bib_loader`, defaulting to `research` when absent. Ordering rank: `research` (0) → `applied` (1); within rank, year-descending (current behavior preserved). This is a content-source signal (consistent with "content is the source of truth"), not renderer-embedded business logic.
- Rejected alternative: hard-coding the bib key or grouping under visible "Research" / "Applied" headings across all renderers (more surface area; the sort achieves the user's intent with one ordering change).

TDD: a `bib_loader` test asserting the applied entry sorts last despite being newest; renderer tests already cover list emission.

## 8. Workstream 5 — On-theme schema additions

### 8a. Education `field` (major)

- **`schema/cv.schema.json`:** add optional `field` (LangString) to the education item (`additionalProperties: false`, so the key must be declared). Not required.
- **`content/education.yaml`:** B.Sc. entry gets `field: { en: "Bioinformatics", de: "Bioinformatik" }`. M.Sc. left without `field` (off-theme — acceptable asymmetry).
- **Renderers (6 touch-points):** `scripts/render_text.py`, `scripts/render_jsonresume.py` (maps to the native `area` field), `scripts/render_jsonld.py`, `pdf/` education template, `web/src/components/EducationSection.astro`, `web/src/types/content.ts`. Each renders the field only when present; DE parity via the LangString.

### 8b. Awards section

A new top-level content section. Cross-cutting but small in payload.

- **`schema/cv.schema.json`:** new `awards` `$def` — array of objects `{ title: LangString (required), issuer: string (required), year: integer (required), note?: LangString }`.
- **`content/awards.yaml`:** new file (LangString fields carry EN+DE):
  - DAAD PROMOS — `title: { en: "DAAD PROMOS Scholarship", de: "DAAD-PROMOS-Stipendium" }`, `issuer: "DAAD"`, `year: 2015`, `note: { en: "Research internship at Seoul National University (Bio & Health Informatics Lab)", de: "Forschungspraktikum an der Seoul National University (Bio & Health Informatics Lab)" }`.
  - DeGBS Poster Award — `title: { en: "DeGBS Poster Award", de: "DeGBS-Posterpreis" }`, `issuer: "Deutsche Gesellschaft für Biologische Strahlenforschung"`, `year: 2021`.
- **Plumbing:** `scripts/validate.py` `_FILE_RULES` entry for `awards.yaml`; `scripts/content_loader.py` loads the key; `content/labels.yaml` gets an `awards` section label `{ en: "Awards", de: "Auszeichnungen" }`.
- **Renderers (5):** `render_text.py` (new section in the section list + label), `render_jsonresume.py` (native `awards` array: `title`/`awarder`/`date`/`summary`), `render_jsonld.py` (`Person.award` array of strings), `render_web_data.py` + a new `web/src/components/AwardsSection.astro` wired into the page in both langs, and the `pdf/` Typst template (new section). `web/src/types/content.ts` gains the `Award` type.

## 9. Workstream 6 — Research-bullet enrichment (content-only)

- **`experience.yaml` `research` entry:** extend the genomics/immunogenomics bullet (EN + DE) with a short clause referencing clinical variant-calling depth — the NCT colorectal SNV-calling validation (Jan–May 2016) and DKFZ patient-NGS DNA-breakage work (Dec 2014–Feb 2015) — without adding separate positions. One phrase, not a new entry; preserves the collapsed history while strengthening the bioinformatics signal. No length blow-out (the PDF Selected-Projects/experience layout must still fit).

## 10. Testing & validation

- **TDD** for logic changes: the `bib_loader` ordering rank (Workstream 4) and any new renderer emit branches (education `field`, awards section) get tests first.
- **Schema/validation:** `just validate` must pass with the new `field` and `awards.yaml`; add a validate-tree test that a malformed `awards.yaml` (missing required key) fails.
- **Parity:** existing EN/DE parity tests extended to cover `awards.yaml` and the education `field`.
- **Regeneration & spot-check:** `just build-formats && just build-text && just web-build`; verify in each output: L1 reads 2015; ORCID + website present in JSON-LD/JSON Resume; Italian present; the marketing chapter sorts last; B.Sc. shows the Bioinformatics major; the two awards render with EN/DE labels.
- **Gate:** `just validate && just test && just lint` all green before the PR.

## 11. Sequencing (for the implementation plan)

Tasks are mostly independent; suggested order groups content-only work before schema/renderer work:

1. Date & factual corrections (WS1) — content-only, fast, high-value.
2. Settled skills + Italian (WS2) and identity links (WS3) — content-only.
3. Publications ordering (WS4) — `bib_loader` + `.bib` `category` + test.
4. Education `field` (WS5a) — schema + 6 renderers + test.
5. Awards section (WS5b) — schema + content + plumbing + 5 renderers + tests.
6. Research-bullet enrichment (WS6) — content-only, last (depends on nothing).
7. Full regeneration + EN/DE spot-check + gate.

## 12. Open questions

None. All defaults confirmed during brainstorming: scope B; L4 roll-up kept; new Structural Biology sub-group; marketing chapter deprioritized via sort; both DAAD PROMOS + DeGBS awards included; research-bullet enrichment included; volunteer untouched; ORCID `0009-0001-8784-1771`.
