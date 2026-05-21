# Design: Machine-Readable, Codified CV

**Date:** 2026-05-21
**Owner:** Jin-Ho Lee
**Repo:** `jin-ho-lee-cv` (sibling of other projects in `~/dev/GitHub/Jin-HoMLee/`)
**Source PDF:** `~/Documents/CV/CV_Bioinformatics/2026-05_CV_Bioinformatics_EA.pdf`

## 1. Goals

Build a version-controlled, machine-readable CV that serves three purposes simultaneously:

1. **Single source of truth.** One canonical content set in YAML + BibTeX; never hand-edit Word/InDesign again.
2. **Multi-format outputs.** Same data renders to PDF (EN + DE), an HTML website, JSON Resume for ATS/external tools, JSON-LD for search engines and LLMs, and ATS-friendly plain text.
3. **Living portfolio website.** GitHub Pages site that doubles as professional identity; CV is one view alongside project deep-dives and publications.

**Non-goal:** pixel-perfect reproduction of the current PDF design. The new PDF is "close but cleaner" — same brand spirit (blue accent, two-column, structured skill groupings, photo), modernized typography.

## 2. Core architectural principle

**Content is content. Renderers are interchangeable scripts that consume it.**

The data files in `content/` know nothing about how they get rendered. If Typst becomes obsolete in five years, the YAML and BibTeX migrate to any other tool in an afternoon. The website framework, the JSON-LD shape, the plain-text format — all replaceable without touching content.

```
                      ┌─ pdf/templates/*.typ     → PDFs (EN + DE)
content/*.yaml ───┐   │
content/*.bib    ─┼──→├─ web/ (Astro)            → GitHub Pages site
content.private/ ─┘   │
   (gitignored)       ├─ scripts/render_jsonresume.py → dist/resume.json
                      ├─ scripts/render_jsonld.py     → schema.org JSON-LD
                      └─ scripts/render_text.py       → ATS-friendly .txt
```

## 3. Tooling decisions

| Concern | Choice | Rationale |
|---|---|---|
| Data format | YAML | Human-editable, supports comments, native multi-line strings, broad tooling. |
| Publications | BibTeX (`.bib`) | Scientific standard, interop with Zotero/Mendeley/Overleaf, DOI-friendly. |
| Validation | JSON Schema | Industry standard, easy CI integration, IDE autocomplete. |
| PDF renderer | Typst | Modern (2023+), readable templates, fast compile, growing CV ecosystem; data layer doesn't care if Typst dies. |
| Website framework | Astro + Tailwind | Content Collections fit YAML naturally; static output; TypeScript-friendly; built-in i18n routing. |
| CI/CD | GitHub Actions | Native to GitHub Pages, free for public repos. |
| Hosting | GitHub Pages | Default to `jin-homlee.github.io/jin-ho-lee-cv`; custom domain optional later. |

## 4. Repo layout

```
jin-ho-lee-cv/
├── README.md
├── content/                          # public, source of truth
│   ├── personal.yaml                 # name, public socials, photo path
│   ├── profile.{en,de}.yaml          # multi-paragraph summary
│   ├── skills.yaml                   # categorized, lang-keyed labels
│   ├── education.yaml
│   ├── experience.yaml               # references projects by id
│   ├── projects/
│   │   ├── L1.{en,de}.yaml           # one file per project, per lang
│   │   ├── L2.{en,de}.yaml
│   │   └── …                         # L1-L4, D1-D3, C1-C2
│   ├── languages.yaml
│   ├── volunteer.yaml
│   └── publications.bib              # BibTeX, single source of truth
├── content.private/                  # gitignored
│   ├── private.yaml                  # phone, full address
│   └── private.example.yaml          # committed template showing keys
├── schema/
│   └── cv.schema.json                # JSON Schema for YAML validation
├── pdf/
│   ├── build.py                      # YAML + BibTeX → Typst → PDF
│   ├── styles.typ                    # colors, fonts, spacing tokens
│   └── templates/
│       ├── cv.typ
│       ├── publications.typ
│       └── projects.typ
├── web/                              # Astro site
│   ├── src/{content,pages,layouts,components}/
│   └── astro.config.mjs
├── scripts/
│   ├── render_jsonresume.py
│   ├── render_jsonld.py
│   ├── render_text.py
│   ├── publications_chart.py         # regenerates chart from .bib
│   └── validate.py                   # JSON Schema + cross-ref check
├── assets/
│   ├── photo.jpg
│   └── publications-chart.svg        # generated, committed for the PDF
├── justfile                          # `just build-private en`, etc.
└── .github/workflows/
    ├── ci.yml                        # validate + build on every PR
    └── deploy.yml                    # publish PDFs + site on main
```

**Notable layout decisions:**
- **One file per project per language** (`projects/L1.en.yaml`). Each project is bulky (role, tech, contributions, outcome); inline `{en:…, de:…}` maps would make files unreadable. Splitting also makes adding Korean later trivial.
- **Short strings are inline-keyed** in language maps (skill labels, section titles). They're tiny and live next to context.
- **Chart committed as SVG.** Keeps PDF build hermetic — no matplotlib in CI for a static asset that changes once a year. Regenerated locally via `just chart`.
- **JSON Schema in `schema/`.** Cheap insurance against typos and broken project-id references in `experience.yaml`.

## 5. Data schemas

Three recurring patterns:

```yaml
# Pattern A — short label, inline language map
title: { en: "Doctoral & Post-Graduate Researcher", de: "Doktorand & Postgraduierter Forscher" }

# Pattern B — date range (machine-readable; renderers handle locale formatting)
period: { start: "2014-06", end: "2022-07" }

# Pattern C — cross-reference to a project; validated by scripts/validate.py
projects: [L1, L2, L3, L4]
```

### 5.1 `personal.yaml`

```yaml
name: { given: "Jin-Ho", family: "Lee" }
headline:
  en: "Bioinformatics | Data Science | Consulting"
  de: "Bioinformatik | Data Science | Beratung"
email: jinho.michael.lee@gmail.com
location: { city: "Mannheim", country: "DE" }   # full address lives in private
links:
  linkedin: "https://linkedin.com/in/jin-holee"
  github:   "https://github.com/Jin-HoMLee"
  rg:       "https://researchgate.net/profile/Jin-Ho-Lee-8"
  orcid:    null                                  # fill if applicable
photo: "assets/photo.jpg"
```

### 5.2 `content.private/private.yaml` (gitignored)

```yaml
phone: "+49 ... ..."
address:
  street: "Example Street 1"
  postal_code: "00000"
  city: "Mannheim"
  country: "GER"
```

### 5.3 `experience.yaml` (one entry shown)

```yaml
- id: cintellic
  org: { name: "Cintellic / International Bank", url: null }
  role:
    en: "Consultant, Lead Business Functional Analyst"
    de: "Berater, Lead Business Functional Analyst"
  period: { start: "2024-05", end: "2025-07" }
  bullets:
    - en: "Architecting the migration of 1,000+ analytical processes to Google Cloud."
      de: "Architektur der Migration von 1.000+ analytischen Prozessen in die Google Cloud."
      refs: [C2]
    - en: "Developing BigQueryML models for anti-financial crime & KYC."
      de: "Entwicklung von BigQueryML-Modellen für Geldwäschebekämpfung & KYC."
      refs: [C1]
```

### 5.4 `projects/L1.en.yaml`

```yaml
id: L1
category: life-science                  # life-science | data-science | consulting
title: "Cancer Neoantigen Discovery – Transcriptome-Wide Splice Analysis"
summary: "Bioinformatics pipeline for identifying novel immunotherapy targets derived from aberrant alternative splicing in RNA-Seq data."
role: "Bioinformatics Research Intern (Seoul National University)"
period: { start: "2018-09", end: "2019-03" }   # fill in actuals
technologies: [Python, R, MapSplice, RNA-Seq, "TCGA Datasets", "MHC-I Prediction Tools"]
contributions:
  - "Developed a discovery pipeline to identify tumor-specific splice junctions across large-scale cancer datasets."
  - "Mapped the epitope landscape by predicting high-affinity MHC-I binding peptides from non-canonical transcripts."
  - "Validated the predictive model by cross-referencing findings with high-impact transcriptomic studies."
  - "Evaluated synergistic strategies for co-targeting mutation-derived and splice-derived neoantigens."
outcome: "Demonstrated that alternative splicing is a viable source for high-affinity epitopes, expanding target discovery beyond traditional somatic mutations."
```

### 5.5 `publications.bib`

Standard BibTeX with a small set of custom fields:

```bibtex
@incollection{lee2021superres,
  author     = {Lee, J. and Hausmann, M.},
  title      = {Super-Resolution Radiation Biology: From Bio-Dosimetry towards Nano-Studies of DNA Repair Mechanisms},
  booktitle  = {DNA - Damages and Repair Mechanisms},
  editor     = {Behzadi, P.},
  year       = {2021},
  type       = {book-chapter},        # custom: article | book-chapter | conference
  authorship = {first},                # custom: first | shared | middle | last | corresponding
  doi        = {…}
}
```

- `authorship` drives the authorship pie chart.
- `type` separates peer-reviewed articles / conference contributions / books.
- Renderers use `pybtex` (Python) to parse; no LaTeX dependency.

## 6. Rendering pipeline

| Output | Tool | Notes |
|---|---|---|
| PDF (EN, DE) | Typst via `pdf/build.py` | Script composes YAML→Typst input, then shells out to `typst compile`. |
| Website (EN, DE) | Astro Content Collections reading `../content/` | Static; deployed to GitHub Pages with `/en/` and `/de/` locale routing. |
| JSON Resume | `scripts/render_jsonresume.py` | Outputs `dist/resume.json` conforming to the JSON Resume schema for ATS interop. |
| JSON-LD | `scripts/render_jsonld.py` | Embedded in website `<head>`; also standalone `dist/person.jsonld`. Uses schema.org `Person` + `ScholarlyArticle`. |
| Plain text | `scripts/render_text.py` | ATS-friendly text dump for old-school applications. |

### 6.1 Private overlay mechanic

`pdf/build.py` does:

```python
public  = load_yaml_tree("content/")
private = load_yaml("content.private/private.yaml")   # missing → public build
merged  = deep_merge(public, private)                  # private wins on conflict
render_typst(merged, lang=args.lang)
```

- **Local builds:** `content.private/private.yaml` is present → PDF includes phone + address. This is the PDF you send to recruiters.
- **CI builds:** `content.private/` is absent → PDF renders with `phone: null` + `location` showing city/country only. This is the *public* PDF attached to GitHub Releases and linked from the website.
- Web/JSON renderers ignore the private overlay by design — PII never reaches GitHub Pages.

## 7. CI/CD

### 7.1 `.github/workflows/ci.yml` (every PR and push)

1. Install Python (with `uv`), Node (with `pnpm`), Typst.
2. `python scripts/validate.py` — JSON Schema check on every YAML, plus cross-reference check (every `refs: [L1]` resolves to a project file; every project `id` unique; every BibTeX `authorship` value is in the allowed set).
3. `python pdf/build.py --lang en --public` and `--lang de --public`.
4. `pnpm --dir web build`.
5. `python scripts/render_jsonresume.py`, `render_jsonld.py`, `render_text.py`.
6. Upload all artifacts so PRs can be previewed before merging.

### 7.2 `.github/workflows/deploy.yml` (push to `main`)

1. Same build as CI.
2. Deploy `web/dist/` to GitHub Pages.
3. Create GitHub Release tagged `cv-YYYY-MM-DD` with public PDFs, JSON Resume, JSON-LD, and plain text attached — gives a permalink per CV version.
4. Update the `latest` release so the website's `/cv.pdf` redirect always points to current.

### 7.3 Local build for the "real" PDF (with PII)

```bash
just build-private en       # → dist-private/cv-en.pdf
just build-private de       # → dist-private/cv-de.pdf
```

`dist-private/` is gitignored. The `justfile` wraps common commands.

## 8. Testing strategy

Three layers, all in CI:

1. **Schema validation.** JSON Schema for every YAML; catches malformed structure.
2. **Reference integrity.** Every `refs: [L1]` resolves; every project `id` is unique; every BibTeX `authorship` value is in the allowed set.
3. **Build smoke tests.** PDFs render without errors; web build succeeds; all output files exist and are non-empty.

**Explicitly skipped:** visual regression on the PDF. Diminishing returns for a one-person CV; manual review catches anything that matters.

## 9. Phasing

Ship MVP fast, expand iteratively. Each phase produces a usable artifact; you can stop or continue at any phase.

| Phase | Scope | Deliverable | Effort |
|---|---|---|---|
| **0 — Scaffold** | Repo init, schema definition, validation script, all content migrated from PDF to YAML + `publications.bib` | All content in `content/` passes `scripts/validate.py` | ~1 session |
| **1 — PDF parity** | Typst template (EN only), private overlay, local build | A PDF that's "close but cleaner" replacing the current one | 1–2 sessions |
| **2 — DE + CI** | German translations across all YAML, GitHub Actions building both PDFs, release automation | Public PDFs auto-built on every push to `main` | ~1 session |
| **3 — Website** | Astro site, GH Pages deploy, i18n routing | `jin-homlee.github.io/jin-ho-lee-cv` live | 1–2 sessions |
| **4 — Discoverability** | JSON Resume + JSON-LD + plain text + chart regeneration | Full multi-format pipeline | ~1 session |
| **5 — Polish** | Custom domain (optional), per-project deep-dive pages, OG images for sharing | Production-grade | as desired |

**Hard gate at Phase 1:** once there's a Typst PDF worth sending out, everything after is additive.

## 10. Open decisions deferred to implementation

- **Astro theme/design language for the website.** Decide when starting Phase 3, after seeing the PDF.
- **Custom domain.** Default to `jin-homlee.github.io/jin-ho-lee-cv`; user can wire a domain later.
- **ORCID auto-sync.** Skipped per design discussion; can be added in Phase 5 if publishing cadence picks up.
- **Korean variant.** Not in scope; the schema accommodates it (add `.kr.yaml` files) but no Korean renderer or font work until needed.
