# Design: Phase 8a — Sharpen positioning

**Date:** 2026-05-30
**Owner:** Jin-Ho Lee
**Parent spec:** [`2026-05-21-codified-cv-design.md`](./2026-05-21-codified-cv-design.md)
**Predecessor work:** Phase 7 content audit (merged 2026-05-29), Education-to-sidebar styling (PR #35)

## 1. Context — first of a three-part arc

The CV infrastructure and content are complete and accurate (six phases + Phase 7 audit shipped). This release targets a different axis: **how the CV positions the candidate** for the two job markets actually being pursued — **bioinformatics / computational biology** and **data science / ML**.

Brainstormed scope spans three coupled but independently-shippable parts:

| Part | Theme | Surface | Status |
|---|---|---|---|
| **8a** | **Sharpen positioning** | `content/` copy only | **this spec** |
| 8b | Targeted CV variants (comp-bio vs ds-ml builds from one source) | schema + loader + renderers + CI | future |
| 8c | Visual showcase refresh (hero, career-arc, target switcher) | web | future |

8a ships first because it is cheap, re-renders into a strictly-better CV on day one, and **defines what a "positioning" is** — which de-risks the 8b variant data-model design. 8a produces the single canonical (audience-shared) positioning that 8b will later branch per target.

## 2. Problem

Positioning today lives in three bilingual fields, and all three read as **100% bioinformatics with zero data-science signal**:

- `personal.yaml → headline`: `Cancer Immunogenomics | Bioinformatics`
- `profile.{en,de}.yaml → tagline`: a dense, genomics-only one-liner (also the meta description + OG share-image headline)
- `profile.{en,de}.yaml → paragraphs`: a profile body whose **first sentence leads with cloud migration** — the one direction *not* being targeted (data/analytics engineering), burying the genomics + publications differentiator in sentence two.

For a recruiter's 10-second skim, the headline sells the wrong thing to a DS/ML reader, and the right thing is invisible.

## 3. Goal

After 8a, all renderers (PDF EN/DE, web, JSON Resume, JSON-LD, plain text, OG images, meta description) carry a positioning that:

- Reads credibly to **both** a comp-bio and a data-science recruiter ("Bridge" direction — genomics depth and data science weighted equally).
- Leads with the differentiator (data scientist + cancer-genomics + publication record), with the cloud/banking work demoted to supporting evidence.
- Stays factually identical to today's content — **no invented facts or metrics**.
- Maintains EN/DE parity.

## 4. The copy (locked EN; DE proposed below)

### 4.1 Headline — `personal.yaml`

| Lang | Before | After |
|---|---|---|
| en | `Cancer Immunogenomics \| Bioinformatics` | `Bioinformatics · Data Science` |
| de | `Tumor-Immunogenomik \| Bioinformatik` | `Bioinformatik · Data Science` |

Separator changes from `|` to `·` (middot, U+00B7). Trivial; verify it renders in the Typst PDF (IBM Plex Sans covers it).

### 4.2 Tagline — `profile.{en,de}.yaml` (~138 chars, meta-description length)

- **en:** `Data scientist with cancer-genomics roots — HLA typing & neoantigen discovery on real-patient data, production ML on GCP, 10+ publications.`
- **de (proposed):** `Data Scientist mit Wurzeln in der Krebsgenomik — HLA-Typisierung & Neoantigen-Identifizierung an echten Patientendaten, Produktiv-ML auf GCP, 10+ Publikationen.`

Trimmed from today's tagline: "deep", "peer-reviewed", the explicit WES/TCGA RNA-Seq/splice-junction detail — kept the highest-signal keywords within meta-description length.

### 4.3 Profile body — `profile.{en,de}.yaml → paragraphs`

**Decision:** split the single dense paragraph into **two** — (1) genomics + publications proof, (2) industry application. This reads better on web/PDF *and* tightens the JSON-LD `description` (= `paragraphs[0]`) down to the pure differentiator instead of trailing into banking work.

**en:**

> **¶1** Data scientist with deep roots in cancer genomics. Engineered in-silico pipelines for HLA typing and neoantigen discovery from real-patient NGS and RNA-Seq data, backed by 10+ peer-reviewed publications — first- and shared-first author in Cancers, Epigenetics Methods, and OBM Genetics — grounded in wet-lab training and pipeline development at DKFZ, NCT, FZ Jülich, KIP, and SNU.
>
> **¶2** Now applying that rigor in industry: architected the migration of 1,000+ analytical processes to Google Cloud, shipped BigQueryML models for anti-financial-crime & KYC, and coached 100+ specialists in Python, SQL & ML; secured third-party funding and supervised 10+ students.

**de (proposed):**

> **¶1** Data Scientist mit tiefen Wurzeln in der Krebsgenomik. Entwicklung von In-silico-Pipelines zur HLA-Typisierung und Neoantigen-Identifizierung aus realen Patienten-NGS- und RNA-Seq-Daten, gestützt auf 10+ peer-reviewed Publikationen — als Erstautor sowie mit geteilter Erstautorschaft in Cancers, Epigenetics Methods und OBM Genetics —, aufbauend auf Wet-Lab-Ausbildung und Pipeline-Entwicklung an DKFZ, NCT, FZ Jülich, KIP und SNU.
>
> **¶2** Diese Sorgfalt nun in der Industrie: Architektur der Migration von 1.000+ analytischen Prozessen in die Google Cloud, Entwicklung von BigQueryML-Modellen für Geldwäscheprävention & KYC sowie Schulung von 100+ Fachkräften in Python, SQL & ML; Einwerbung von Drittmitteln und Betreuung von 10+ Studierenden.

Every number above already exists in `content/` (1,000+ processes, 10+ publications, 100+ specialists, 10+ students). Nothing invented. The DE copy is a proposed starting point; refinement during implementation is allowed as long as it stays parallel to EN.

## 5. Propagation — why 6 fields re-render everything

| Field | Source | Flows into |
|---|---|---|
| `headline` | `personal.yaml` | PDF header (`header.typ`), web `Header.astro`, plain-text header (`render_text.py`), JSON Resume `basics.label`, JSON-LD `jobTitle` |
| `tagline` | `profile.{en,de}.yaml` | PDF lead line (`profile.typ`), web `ProfileSection.astro`, **meta description** (`BaseLayout.astro`), **OG image headline** (`og/[...path].ts`) |
| `paragraphs` | `profile.{en,de}.yaml` | PDF body, web profile, plain text, JSON Resume `basics.summary` (joined `\n\n`), JSON-LD `description` = `paragraphs[0]` |

No renderer code changes — these are existing field reads. The checked-in generated files `web/src/data/content.{en,de}.json` must be **regenerated and committed** (they are build artifacts kept in git for the Astro build).

## 6. Non-goals

- **No experience-bullet edits.** User chose restructure-only; bullets are already strong and carry their own numbers. A metrics pass (real outcome figures) is deferred to a future increment.
- **No invented metrics or facts.**
- **No schema changes** — existing fields, new values.
- **No section reordering / web layout changes** — that is 8c.
- **No per-target variants** — that is 8b. 8a is the single shared positioning.
- **No job-title rewrites** in `experience.yaml` (the Cintellic consulting title is the real title).

## 7. Definition of done

1. `just validate` green (schema unchanged).
2. `just test` green — update any assertion that breaks. (Audit confirms no test hardcodes the current marketing copy; expected breakage ≈ none. Optionally add light assertions that the new tagline/headline appear and that `paragraphs[0]` leads with "Data scientist".)
3. `just lint` green.
4. `just build` + `just build-de` → PDFs show new header label, tagline lead line, re-led two-paragraph body.
5. `just build-formats` + `just build-text` → JSON Resume `label`/`summary`, JSON-LD `jobTitle`/`description`, and plain text carry the new copy.
6. `just web-build` → regenerates `content.{en,de}.json` (committed) and OG images; meta description = new tagline. Verify the EN and DE OG share images render the new tagline.
7. EN/DE parity confirmed on every surface.

## 8. Open detail

- **Separator glyph:** default `·`; revert to `|` if the PDF font or any consumer mishandles the middot.

## 9. Commits / branch

Per repo convention (atomic commits, per-phase branch, PR merge): branch `phase-8a-sharpen-positioning`. Suggested atomic commits:

1. `content: re-lead profile body and sharpen tagline (EN)` — `profile.en.yaml`.
2. `content: German parity for sharpened positioning` — `profile.de.yaml`.
3. `content: reposition headline to Bioinformatics · Data Science` — `personal.yaml` (EN + DE).
4. `build: regenerate web content JSON + machine formats` — generated artifacts; update tests if needed.

(An issue can be opened to track 8a and the branch linked via `gh issue develop`; optional given the small scope.)
