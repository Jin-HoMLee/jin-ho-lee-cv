# Phase 8a — Sharpen Positioning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reposition the CV so every renderer leads with a "Bioinformatics · Data Science" bridge identity (genomics depth + production data science) instead of leading with cloud-migration work, by editing three content YAML files — no renderer code changes.

**Architecture:** Positioning lives in three bilingual fields — `personal.yaml → headline`, `profile.{en,de}.yaml → tagline`, and `profile.{en,de}.yaml → paragraphs`. All renderers (PDF, web, JSON Resume, JSON-LD, plain text, OG images, meta description) read these existing fields, so changing the values re-renders everything. A focused regression test (`tests/test_positioning.py`) loads the content tree and asserts the new copy; each content edit is bundled with its assertions so every commit lands green. No build artifacts are committed (`web/src/data/*.json` and `dist/` are gitignored and regenerated in CI).

**Tech Stack:** YAML content, Python 3.12 + `uv`, pytest, `ruamel.yaml` loader (`scripts/content_loader.py`), `just` task runner, Typst (PDF), Astro (web).

**Spec:** [`docs/superpowers/specs/2026-05-30-phase-8a-sharpen-positioning-design.md`](../specs/2026-05-30-phase-8a-sharpen-positioning-design.md)

---

## Prerequisites

- Work happens on branch `phase-8a-sharpen-positioning` (already created off `main`; the spec is committed there). Confirm with `git branch --show-current`.
- The regression test uses the existing `content_dir` pytest fixture (defined in `tests/conftest.py:18`, returns the repo `content/` dir) and `load_content` from `scripts/content_loader.py`. `load_content(content_dir, lang="en"|"de")` returns the raw tree: `["personal"]["headline"]` is the `{en, de}` map; `["profile"]["tagline"]` and `["profile"]["paragraphs"]` come from `profile.<lang>.yaml`.

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `tests/test_positioning.py` | Regression assertions for the Phase 8a copy (EN + DE tagline/body, headline) | Create (Task 1), extend (Tasks 2–3) |
| `content/profile.en.yaml` | EN tagline + profile body | Modify (Task 1) |
| `content/profile.de.yaml` | DE tagline + profile body | Modify (Task 2) |
| `content/personal.yaml` | Bilingual headline (role label) | Modify (Task 3) |

---

## Task 1: Sharpen EN tagline + re-lead EN profile body

**Files:**
- Create: `tests/test_positioning.py`
- Modify: `content/profile.en.yaml`

- [ ] **Step 1: Write the failing test**

Create `tests/test_positioning.py` with exactly this content:

```python
"""Regression assertions for the Phase 8a positioning copy.

These guard the "Bioinformatics · Data Science" repositioning: the tagline and
profile body must lead with the data-science + cancer-genomics differentiator,
and the cloud-migration work must be demoted to the second profile paragraph.
"""
from __future__ import annotations

from scripts.content_loader import load_content


def test_en_tagline_leads_with_data_science(content_dir):
    profile = load_content(content_dir, lang="en")["profile"]
    assert profile["tagline"].startswith("Data scientist")
    assert "production ML on GCP" in profile["tagline"]
    # the old genomics-only framing is gone
    assert "Bioinformatics Engineer specializing" not in profile["tagline"]


def test_en_profile_body_is_two_paragraphs_led_by_differentiator(content_dir):
    paragraphs = load_content(content_dir, lang="en")["profile"]["paragraphs"]
    assert len(paragraphs) == 2
    assert paragraphs[0].startswith("Data scientist with deep roots in cancer genomics")
    # cloud-migration work is demoted out of the opening paragraph
    assert "Google Cloud" not in paragraphs[0]
    assert "Google Cloud" in paragraphs[1]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_positioning.py -v`
Expected: both tests FAIL — `test_en_tagline_leads_with_data_science` fails the `startswith("Data scientist")` assertion (current tagline starts with "Bioinformatics Engineer specializing"), and `test_en_profile_body_is_two_paragraphs_led_by_differentiator` fails `len(paragraphs) == 2` (currently 1).

- [ ] **Step 3: Edit the EN content**

Replace the entire contents of `content/profile.en.yaml` with:

```yaml
tagline: "Data scientist with cancer-genomics roots — HLA typing & neoantigen discovery on real-patient data, production ML on GCP, 10+ publications."
paragraphs:
  - "Data scientist with deep roots in cancer genomics. Engineered in-silico pipelines for HLA typing and neoantigen discovery from real-patient NGS and RNA-Seq data, backed by 10+ peer-reviewed publications — first- and shared-first author in Cancers, Epigenetics Methods, and OBM Genetics — grounded in wet-lab training and pipeline development at DKFZ, NCT, FZ Jülich, KIP, and SNU."
  - "Now applying that rigor in industry: architected the migration of 1,000+ analytical processes to Google Cloud, shipped BigQueryML models for anti-financial-crime & KYC, and coached 100+ specialists in Python, SQL & ML; secured third-party funding and supervised 10+ students."
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_positioning.py -v`
Expected: both EN tests PASS.

- [ ] **Step 5: Run validation to confirm content is well-formed**

Run: `just validate`
Expected: exits 0 (schema unchanged — these are existing fields with new values).

- [ ] **Step 6: Commit**

```bash
git add tests/test_positioning.py content/profile.en.yaml
git commit -m "content: re-lead profile body and sharpen tagline (EN)"
```

---

## Task 2: German parity — sharpen DE tagline + re-lead DE profile body

**Files:**
- Modify: `tests/test_positioning.py`
- Modify: `content/profile.de.yaml`

- [ ] **Step 1: Write the failing test**

Append these two functions to the end of `tests/test_positioning.py`:

```python
def test_de_tagline_leads_with_data_science(content_dir):
    profile = load_content(content_dir, lang="de")["profile"]
    assert profile["tagline"].startswith("Data Scientist")
    assert "Krebsgenomik" in profile["tagline"]


def test_de_profile_body_is_two_paragraphs_led_by_differentiator(content_dir):
    paragraphs = load_content(content_dir, lang="de")["profile"]["paragraphs"]
    assert len(paragraphs) == 2
    assert paragraphs[0].startswith("Data Scientist mit tiefen Wurzeln in der Krebsgenomik")
    assert "Google Cloud" not in paragraphs[0]
    assert "Google Cloud" in paragraphs[1]
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `uv run pytest tests/test_positioning.py -k de -v`
Expected: both DE tests FAIL (current DE tagline starts with "Bioinformatiker mit Fokus", body is 1 paragraph).

- [ ] **Step 3: Edit the DE content**

Replace the entire contents of `content/profile.de.yaml` with:

```yaml
tagline: "Data Scientist mit Wurzeln in der Krebsgenomik — HLA-Typisierung & Neoantigen-Identifizierung an echten Patientendaten, Produktiv-ML auf GCP, 10+ Publikationen."
paragraphs:
  - "Data Scientist mit tiefen Wurzeln in der Krebsgenomik. Entwicklung von In-silico-Pipelines zur HLA-Typisierung und Neoantigen-Identifizierung aus realen Patienten-NGS- und RNA-Seq-Daten, gestützt auf 10+ peer-reviewed Publikationen — als Erstautor sowie mit geteilter Erstautorschaft in Cancers, Epigenetics Methods und OBM Genetics —, aufbauend auf Wet-Lab-Ausbildung und Pipeline-Entwicklung an DKFZ, NCT, FZ Jülich, KIP und SNU."
  - "Diese Sorgfalt nun in der Industrie: Architektur der Migration von 1.000+ analytischen Prozessen in die Google Cloud, Entwicklung von BigQueryML-Modellen für Geldwäscheprävention & KYC sowie Schulung von 100+ Fachkräften in Python, SQL & ML; Einwerbung von Drittmitteln und Betreuung von 10+ Studierenden."
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_positioning.py -v`
Expected: all four tests (EN + DE) PASS.

- [ ] **Step 5: Run validation**

Run: `just validate`
Expected: exits 0.

- [ ] **Step 6: Commit**

```bash
git add tests/test_positioning.py content/profile.de.yaml
git commit -m "content: German parity for sharpened positioning"
```

---

## Task 3: Reposition the headline (EN + DE)

**Files:**
- Modify: `tests/test_positioning.py`
- Modify: `content/personal.yaml:4-6`

- [ ] **Step 1: Write the failing test**

Append this function to the end of `tests/test_positioning.py`:

```python
def test_headline_repositioned_to_bioinformatics_data_science(content_dir):
    headline = load_content(content_dir)["personal"]["headline"]
    assert headline["en"] == "Bioinformatics · Data Science"
    assert headline["de"] == "Bioinformatik · Data Science"
```

- [ ] **Step 2: Run the new test to verify it fails**

Run: `uv run pytest tests/test_positioning.py -k headline -v`
Expected: FAIL — current `headline.en` is `"Cancer Immunogenomics | Bioinformatics"`.

- [ ] **Step 3: Edit the headline**

In `content/personal.yaml`, replace the `headline:` block (lines 4–6):

```yaml
headline:
  en: "Cancer Immunogenomics | Bioinformatics"
  de: "Tumor-Immunogenomik | Bioinformatik"
```

with:

```yaml
headline:
  en: "Bioinformatics · Data Science"
  de: "Bioinformatik · Data Science"
```

Leave every other field in `personal.yaml` (name, email, location, links, photo) unchanged.

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_positioning.py -v`
Expected: all five tests PASS.

- [ ] **Step 5: Run validation**

Run: `just validate`
Expected: exits 0.

- [ ] **Step 6: Commit**

```bash
git add tests/test_positioning.py content/personal.yaml
git commit -m "content: reposition headline to Bioinformatics · Data Science"
```

---

## Task 4: Full verification across every renderer (no commit)

This task commits nothing. It confirms the new copy renders correctly in all six outputs and that the `·` middot survives the Typst PDF. Every output here is gitignored.

**Files:** none modified.

- [ ] **Step 1: Green on the full quality gate**

Run: `just validate && just test && just lint`
Expected: validation exits 0; pytest reports all tests pass (including the 5 new positioning tests); ruff reports no errors.
If any *pre-existing* test fails because it asserted the old copy: update that assertion to the new value and note it in the commit from the task that introduced the change. (Audit found none hardcode the marketing copy, so this is not expected.)

- [ ] **Step 2: Build both PDFs and confirm the copy + glyph render**

Run: `just build && just build-de`
Expected: `dist/cv-en.pdf` and `dist/cv-de.pdf` are produced with no Typst error. Open each and confirm: the header shows "Bioinformatics · Data Science" / "Bioinformatik · Data Science" (the `·` renders, not a tofu box), the bold tagline lead line is the new one, and the profile body shows **two** paragraphs with the industry sentence second.
If the `·` does not render in the PDF, fall back to `|` in `personal.yaml` (per spec §8) and re-run this step.

- [ ] **Step 3: Build the machine formats and grep for the new copy**

Run:
```bash
just build-formats
grep -l "Bioinformatics · Data Science" dist/person.jsonld dist/resume.json dist/cv-en.txt
grep "Data scientist with deep roots in cancer genomics" dist/cv-en.txt
```
Expected: the headline string is found in all three files (JSON-LD `jobTitle`, JSON Resume `basics.label`, plain-text header); the profile lead sentence is found in `dist/cv-en.txt`. Confirm `dist/cv-de.txt` exists and carries the DE copy.

- [ ] **Step 4: Regenerate web data + verify meta/OG source**

Run:
```bash
just web-data
grep -o '"tagline": "[^"]*"' web/src/data/content.en.json
```
Expected: the regenerated `content.en.json` shows the new EN tagline (this is the value the web meta description and OG share-image headline read from). Optionally run `just web-build` for a full Astro build to confirm OG images render and the site builds clean.

- [ ] **Step 5: Confirm working tree is clean of artifacts**

Run: `git status --short`
Expected: only gitignored build outputs are absent from the listing (no `dist/`, no `web/src/data/*.json`). The working tree should be clean — all three content commits are already made and nothing here is staged.

---

## Task 5: Update the CLAUDE.md phase table

Per repo convention, every plan's final task keeps `CLAUDE.md` authoritative. Its `## Phasing` table currently stops at Phase 6, so this task also catches up the missing Phase 7 row.

**Files:**
- Modify: `CLAUDE.md` (the `## Phasing` table)

- [ ] **Step 1: Add the missing rows**

In `CLAUDE.md`, change the line under `## Phasing` from "Six phases, sequential." to "Eight phases (0–8), sequential." and append two rows after the Phase 6 row:

```markdown
| 7 | Content audit (bring CV up to date) | ✅ Done (merged 2026-05-29, PR #33, commit `b731222`) |
| 8a | Sharpen positioning (Bioinformatics · Data Science) | 🚧 In progress (branch `phase-8a-sharpen-positioning`) |
```

The DOI-fields work merged 2026-05-29 was a standalone feat, not a phase — it gets no row.

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add Phase 7 + 8a rows to the CLAUDE.md phasing table"
```

No code touched, so no test/lint run is needed.

- [ ] **Step 3: At merge, flip 8a to Done**

When finishing the branch (next section), edit the Phase 8a row status from `🚧 In progress …` to `✅ Done (merged <fill: date>, commit \`<fill: --no-ff merge hash>\`)`, substituting the real merge date and merge-commit hash. Do this on the PR (or a fast follow-up) so `main` reflects the completed phase.

---

## Self-Review (completed during planning)

- **Spec coverage:** headline (Task 3), tagline (Tasks 1–2), profile body re-lead + 2-paragraph split (Tasks 1–2), EN/DE parity (Tasks 1–3), all-renderer verification + OG/meta + PDF glyph (Task 4), no-artifact-commit invariant (Task 4 Step 5), CLAUDE.md phase-table currency (Task 5, per the 2026-05-30 repo convention — not in the spec but required by the convention added that day). Non-goals (no bullet edits, no schema change, no layout change) respected — no task touches `experience.yaml`, `schema/`, or web layout.
- **Placeholder scan:** none — every YAML body and test function is written out in full.
- **Type consistency:** test calls use the real API — `load_content(content_dir, lang=...)`, `["profile"]["tagline"]`, `["profile"]["paragraphs"]`, `["personal"]["headline"]["en"|"de"]` — matching `scripts/content_loader.py` and how renderers read these fields.

---

## After implementation

All commits are on `phase-8a-sharpen-positioning`. Finish via the `superpowers:finishing-a-development-branch` skill — open a PR to `main` (per repo convention, merged with `--no-ff`). Verify each Test plan checkbox in the PR body before considering the PR done.
