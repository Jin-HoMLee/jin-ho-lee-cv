# Phase 2b — DE Translations + Bilingual CI Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the CV bilingual (EN + DE) — every push to `main` produces a GitHub Release with both `cv-en.pdf` and `cv-de.pdf` attached.

**Architecture:** Three interlocking pieces ship together: (1) new `content/labels.yaml` holds render-time strings (section headings, months, proficiency labels), (2) Typst templates become language-aware by reading from `data.labels` and accepting a `lang` input, (3) the `build-pdf` CI job becomes a `lang: [en, de]` matrix that feeds a single `release` job which attaches both PDFs to one release.

**Tech Stack:** Existing — YAML, BibTeX, Typst, jsonschema, pytest. Adds GitHub Actions matrix strategy + `actions/download-artifact@v7`.

**Spec reference:** [docs/superpowers/specs/2026-05-22-phase-2b-translations-design.md](../specs/2026-05-22-phase-2b-translations-design.md)

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `content/labels.yaml` | Create | Render-time labels: section headings, month abbreviations, proficiency labels. Single source of truth for both PDF and future renderers. |
| `content/personal.yaml` | Modify | Add `de:` to `headline`. |
| `content/experience.yaml` | Modify | Add `de:` to every `role` and every bullet's text field. |
| `content/education.yaml` | Modify | Add `de:` to every `degree`. |
| `content/skills.yaml` | Modify | Add `de:` to every category `name` and group `label`. |
| `content/volunteer.yaml` | Modify | Add `de:` to every category `name`. |
| `content/languages.yaml` | Modify | Add `de:` to every language `name`. |
| `content/profile.de.yaml` | Create | DE prose mirror of `profile.en.yaml`. |
| `content/projects/{L1..L4,D1..D3,C1..C2}.de.yaml` | Create (9 files) | DE mirror of each EN project file. |
| `pdf/build.py` | Modify | Pass `lang=<en|de>` as a Typst `--input`. |
| `pdf/styles.typ` | Modify | (No content changes — `_months` lives in `experience.typ`.) |
| `pdf/templates/cv.typ` | Modify | Read `sys.inputs.lang`; expose as module-level `lang`. |
| `pdf/templates/profile.typ` | Modify | Section heading from `data.labels.sections.profile`. |
| `pdf/templates/experience.typ` | Modify | Section heading from labels; `_months` array from `data.labels.months_abbr`; bullet text from `b.at(lang)`. |
| `pdf/templates/education.typ` | Modify | Section heading from labels. |
| `pdf/templates/sidebar.typ` | Modify | Section headings from labels; proficiency lookup from `data.labels.proficiency`. |
| `scripts/validate.py` | Modify | Add `*.en.yaml`/`*.de.yaml` parity check for projects. |
| `tests/test_validate.py` | Modify | Add tests for the new parity check. |
| `tests/test_de_completeness.py` | Create | Detect missing `de:` keys via en/de tree comparison. |
| `.github/workflows/ci.yml` | Modify | Matrix `build-pdf` + new single `release` job. |
| `justfile` | Modify | Add `build-de` and `build-private-de` recipes. |
| `README.md` | Modify | "Latest CV" line gets EN + DE links. |

**Branch:** already on `phase-2b-translations` (split off `main` at commit `bf3000c`). All implementation lands as commits on this branch; final task merges via PR with `--no-ff`.

**Translation style guide (for tasks that produce DE content):**
- Use Sie/formal register (default for CVs).
- Bullets: noun-phrase or perfect-tense; concise; no first-person pronoun where omittable.
- Keep technology names, brand names, organization names verbatim ("Python", "Cloud", "Cintellic", "neuefische").
- Numbers stay numeric; use German number formatting only where natural ("1.000+" with period as thousands separator, not commas).
- Job titles: translate ("Consultant" → "Berater") per the spec's "Full bilingual" depth.

---

## Task 1: Create `content/labels.yaml`

Single new file. No consumers yet, so the build is unchanged after this commit.

**Files:**
- Create: `content/labels.yaml`

- [ ] **Step 1: Write the file**

Create `content/labels.yaml` with this exact content:

```yaml
sections:
  profile:    { en: "Profile",    de: "Profil" }
  experience: { en: "Experience", de: "Berufserfahrung" }
  education:  { en: "Education",  de: "Ausbildung" }
  skills:     { en: "Skills",     de: "Kenntnisse" }
  languages:  { en: "Languages",  de: "Sprachen" }
  volunteer:  { en: "Volunteer",  de: "Ehrenamtlich" }

months_abbr:
  - { en: "Jan", de: "Jan" }
  - { en: "Feb", de: "Feb" }
  - { en: "Mar", de: "Mär" }
  - { en: "Apr", de: "Apr" }
  - { en: "May", de: "Mai" }
  - { en: "Jun", de: "Jun" }
  - { en: "Jul", de: "Jul" }
  - { en: "Aug", de: "Aug" }
  - { en: "Sep", de: "Sep" }
  - { en: "Oct", de: "Okt" }
  - { en: "Nov", de: "Nov" }
  - { en: "Dec", de: "Dez" }

proficiency:
  native:  { en: "native",  de: "Muttersprache" }
  fluent:  { en: "fluent",  de: "fließend" }
  basic:   { en: "basic",   de: "Grundkenntnisse" }
  passive: { en: "passive", de: "passive Kenntnisse" }
```

- [ ] **Step 2: Update `content_loader.py` to load `labels.yaml`**

Open `scripts/content_loader.py` and modify `load_content` to add a `labels` key. The current `content = {...}` dict (around line 68) needs one new entry:

```python
content = {
    "personal": personal,
    "profile": _load_yaml(content_dir / f"profile.{lang}.yaml"),
    "skills": _load_yaml(content_dir / "skills.yaml"),
    "education": _load_yaml(content_dir / "education.yaml"),
    "experience": _load_yaml(content_dir / "experience.yaml"),
    "projects": _load_projects(content_dir / "projects", lang=lang),
    "languages": _load_yaml(content_dir / "languages.yaml"),
    "volunteer": _load_yaml(content_dir / "volunteer.yaml"),
    "publications": load_publications(content_dir / "publications.bib"),
    "labels": _load_yaml(content_dir / "labels.yaml"),
}
```

- [ ] **Step 3: Verify the loader picks it up**

```bash
uv run python -c "
from pathlib import Path
from scripts.content_loader import load_content
from scripts.langstring import resolve_langstrings
c = load_content(Path('content'), lang='de')
c = resolve_langstrings(c, lang='de')
print(c['labels']['sections']['experience'])
print(c['labels']['months_abbr'][2])
print(c['labels']['proficiency']['native'])
"
```
Expected output:
```
Berufserfahrung
Mär
Muttersprache
```

- [ ] **Step 4: Run the existing test suite to confirm nothing broke**

```bash
uv run pytest -v
```
Expected: all existing tests still pass (`load_content` returning an extra key shouldn't break anything; content_loader tests may need a tiny update if they check exact dict keys — fix any failures by adding `"labels"` to expected key sets).

- [ ] **Step 5: Commit**

```bash
git add content/labels.yaml scripts/content_loader.py tests/
git commit -m "feat: add content/labels.yaml as i18n source for render-time strings"
```

---

## Task 2: Make Typst templates language-aware

One coherent change: every hardcoded English string in the Typst templates is replaced with a lookup against `data.labels` or `data.labels.sections`. Also pass `lang` from `pdf/build.py` to Typst as an input so the experience template can choose the correct bullet language.

**Files:**
- Modify: `pdf/build.py` — pass `--input lang=<en|de>`
- Modify: `pdf/templates/cv.typ` — read `sys.inputs.lang`, expose as module-level `lang`
- Modify: `pdf/templates/profile.typ` — section heading from labels
- Modify: `pdf/templates/experience.typ` — section heading, `_months`, bullet text via `b.at(lang)`
- Modify: `pdf/templates/education.typ` — section heading from labels
- Modify: `pdf/templates/sidebar.typ` — section headings, proficiency lookup

- [ ] **Step 1: Pass `lang` to Typst from `pdf/build.py`**

In `pdf/build.py`, the existing `subprocess.run` call (around line 132-141) currently passes one `--input` for `photo_input`. Add a second `--input` for lang. The full call should become:

```python
result = subprocess.run(
    [
        "typst", "compile",
        "--root", str(REPO_ROOT),
        "--input", photo_input,
        "--input", f"lang={args.lang}",
        str(template),
        str(out_path),
    ],
    check=False,
)
```

- [ ] **Step 2: Read `lang` in `cv.typ` and pass it down**

Open `pdf/templates/cv.typ`. Near the top (after imports), add:

```typst
#let lang = sys.inputs.at("lang", default: "en")
```

(`sys.inputs.at` with default keeps the template usable from `typst compile` without `--input lang=...` — falls back to English.)

This `lang` value is available throughout `cv.typ`. For child templates that need it, pass as a parameter (next steps show how for `experience`).

- [ ] **Step 3: Wire section heading in `profile.typ`**

Open `pdf/templates/profile.typ`. Find the line `section-heading("Profile")` (line 4) and replace with:

```typst
section-heading(data.labels.sections.profile)
```

`data` is the top-level dict already passed to `profile()`. If `data` isn't already a parameter to this function, check the existing call site in `cv.typ` — `profile()` is called with the profile sub-dict, so it doesn't currently receive `data`.

**Important:** The function signatures need to accept the full data dict (or labels specifically). Pick one of two patterns:

- **Pattern A (preferred):** change every section function to accept `labels` as a parameter:
  ```typst
  #let profile(data, labels) = {
    section-heading(labels.sections.profile)
    // ...
  }
  ```
  And in `cv.typ` change the call site to pass `data.labels`.

- **Pattern B:** read labels at module level by importing them into each template — not possible cleanly with current structure (data is runtime-loaded JSON, not import-time).

Use Pattern A throughout this task.

- [ ] **Step 4: Wire section heading + months + bullet text in `experience.typ`**

Open `pdf/templates/experience.typ`. Make these changes:

1. **Delete** the hardcoded `_months` array (line 3):
   ```typst
   #let _months = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
   ```

2. **Change** `_format-ym` to accept a months parameter:
   ```typst
   #let _format-ym(ym, months) = {
     let parts = ym.split("-")
     months.at(int(parts.at(1)) - 1) + " " + parts.at(0)
   }
   ```

3. **Change** `_period` to accept and forward months:
   ```typst
   #let _period(p, months) = {
     let s = _format-ym(p.start, months)
     let e = if "end" in p and p.end != none { _format-ym(p.end, months) } else { "present" }
     s + " – " + e
   }
   ```

4. **Change** `_bullet` to accept `lang`:
   ```typst
   #let _bullet(b, lang) = {
     let txt = b.at(lang)
     let refs = b.at("refs", default: ())
     // ... rest of function unchanged
   }
   ```

5. **Change** the public `experience` function to accept `data, labels, lang`:
   ```typst
   #let experience(data, labels, lang) = {
     section-heading(labels.sections.experience)
     let months = labels.months_abbr

     for entry in data {
       grid(
         columns: (1fr, auto),
         align: (left, right),
         text(weight: 600)[#entry.org.name],
         text(size: size-small, fill: muted)[#_period(entry.period, months)],
       )
       text(style: "italic", fill: muted)[#entry.role]
       v(space-paragraph)

       for bullet in entry.bullets {
         _bullet(bullet, lang)
       }
       v(space-section / 2)
     }
   }
   ```

- [ ] **Step 5: Wire section heading in `education.typ`**

Open `pdf/templates/education.typ`. Replace `section-heading("Education")` with `section-heading(labels.sections.education)`. Add `labels` parameter to the public function.

- [ ] **Step 6: Wire section headings + proficiency in `sidebar.typ`**

Open `pdf/templates/sidebar.typ`. Make these changes:

1. Inside `_skills`:
   ```typst
   #let _skills(skills, labels) = {
     section-heading(labels.sections.skills)
     // ... rest unchanged
   }
   ```

2. Inside `_languages` — wire section heading AND look up proficiency:
   ```typst
   #let _languages(langs, labels) = {
     section-heading(labels.sections.languages)
     for l in langs {
       grid(
         columns: (1fr, auto),
         text(size: size-small)[#l.name],
         text(size: size-small, fill: muted)[#labels.proficiency.at(l.proficiency)],
       )
       v(2pt)
     }
   }
   ```

3. Inside `_volunteer`:
   ```typst
   #let _volunteer(v_data, labels) = {
     section-heading(labels.sections.volunteer)
     // ... rest unchanged
   }
   ```

4. The public `sidebar` function gains a `labels` parameter and forwards:
   ```typst
   #let sidebar(data, labels) = {
     block(...) [
       #_skills(data.skills, labels)
       #_languages(data.languages, labels)
       #_volunteer(data.volunteer, labels)
     ]
   }
   ```

- [ ] **Step 7: Update `cv.typ` call sites**

In `pdf/templates/cv.typ`, update the call sites that invoke `profile()`, `experience()`, `education()`, `sidebar()` to pass the new parameters. The exact call sites depend on the current structure — read `cv.typ` first, then update each invocation to pass `data.labels` (and `lang` where needed).

Example (the function names and exact destructuring depend on the current file):
```typst
#profile(data.profile, data.labels)
#experience(data.experience, data.labels, lang)
#education(data.education, data.labels)
#sidebar(data, data.labels)
```

- [ ] **Step 8: Smoke-test the EN build**

```bash
rm -rf dist/
uv run python -m pdf.build --lang en
ls -la dist/cv-en.pdf
```

Expected: build succeeds, `dist/cv-en.pdf` exists. Visually open the PDF — it should look *identical* to the pre-Phase-2b EN render. (We've added labels.yaml but only with EN values that resolve to the same strings that were previously hardcoded.)

If the PDF differs visually, debug the Typst changes before committing.

- [ ] **Step 9: Run pytest**

```bash
uv run pytest -v
```
Expected: all tests still pass.

- [ ] **Step 10: Commit**

```bash
git add pdf/
git commit -m "feat(pdf): make templates i18n-aware via data.labels and lang input"
```

---

## Task 3: Add DE strings to in-tree YAMLs

Add a `de:` key alongside every existing `en:` key in `personal.yaml`, `experience.yaml`, `education.yaml`, `skills.yaml`, `volunteer.yaml`, `languages.yaml`. Apply the **Translation style guide** at the top of this plan.

**Files:**
- Modify: `content/personal.yaml`, `content/experience.yaml`, `content/education.yaml`, `content/skills.yaml`, `content/volunteer.yaml`, `content/languages.yaml`

- [ ] **Step 1: Read each file and add `de:` siblings**

For each file, read the current YAML, then add a `de:` key next to every `en:` key. Preserve the existing structure exactly. Items arrays in `skills.yaml` and entries arrays in `volunteer.yaml` stay verbatim (they're brand names / org names).

**Reference EN content and concrete DE translations (use these exactly — they've been tuned for the spec):**

`content/personal.yaml` — `headline`:
- EN: `"Bioinformatics | Data Science | Consulting"`
- DE: `"Bioinformatik | Data Science | Beratung"`

`content/education.yaml`:
- `"M.Sc. Molecular Biotechnology"` → `"M.Sc. Molekulare Biotechnologie"`
- `"B.Sc. Molecular Biotechnology"` → `"B.Sc. Molekulare Biotechnologie"`

`content/languages.yaml`:
- `"German"` → `"Deutsch"`
- `"English"` → `"Englisch"`
- `"Korean"` → `"Koreanisch"`
- `"French"` → `"Französisch"`
- `"Latin"` → `"Latein"`

`content/skills.yaml`:
- Categories: `"Bioinformatics & ML"` → `"Bioinformatik & ML"`, `"Biotech Wet-Lab"` → `"Biotech Nasslabor"`, `"Data & Engineering"` → `"Daten & Engineering"`
- Groups under "Bioinformatics & ML": `"Genomics"` → `"Genomik"`, `"Immunology"` → `"Immunologie"`, `"Nanoscopy"` → `"Nanoskopie"`
- Groups under "Biotech Wet-Lab": `"Models"` → `"Modelle"`, `"Imaging"` → `"Bildgebung"`, `"Assays"` → `"Assays"`
- Groups under "Data & Engineering": `"AI & Vision"` → `"KI & Vision"`, `"Eng & Tools"` → `"Eng & Tools"`, `"Cloud"` → `"Cloud"`

`content/volunteer.yaml` categories:
- `"Community"` → `"Soziales"`
- `"Environment"` → `"Umwelt"`
- `"Sports"` → `"Sport"`
- `"Other"` → `"Sonstiges"`

`content/experience.yaml` — three entries (translate every `role` and every `bullets[*].en` to `de`):

For the **`cintellic` entry**:
- Role: `"Consultant, Lead Business Functional Analyst"` → `"Berater, Lead Business Functional Analyst"`
- Bullet 1: `"Scale: Architecting the migration of 1,000+ analytical processes to Google Cloud."` → `"Skalierung: Architektur der Migration von 1.000+ analytischen Prozessen in die Google Cloud."`
- Bullet 2: `"AI in Production: Developing BigQueryML models for anti-financial crime & KYC."` → `"KI in Produktion: Entwicklung von BigQueryML-Modellen für Geldwäscheprävention & KYC."`
- Bullet 3: `"Stakeholder Lead: Bridging technical data engineering with business requirements for high-stakes banking."` → `"Stakeholder Lead: Brückenfunktion zwischen technischem Data Engineering und Fachanforderungen im hochregulierten Bankensektor."`

For the **`neuefische` entry**:
- Role: `"Data Science Trainee, Associate & Coach"` → `"Data Science Trainee, Associate & Coach"` (keep English — industry standard)
- Bullet 1: `"Coaching: Instructed 100+ specialists in Python, SQL, and ML lifecycles."` → `"Coaching: Schulung von 100+ Fachkräften in Python, SQL und ML-Lebenszyklen."`
- Bullet 2: `"ML Development: Independently engineered a Real-Time ASL Recognition system using LSTMs, MediaPipe, and TensorFlow."` → `"ML-Entwicklung: Eigenständige Entwicklung eines Echtzeit-ASL-Erkennungssystems mit LSTMs, MediaPipe und TensorFlow."`

For the **`research` entry**:
- Role: `"Doctoral & Post-Graduate Researcher"` → `"Doktorand & Postgraduierter Forscher"`
- Bullet 1 (Genomics & Immunotherapy): `"Genomics & Immunotherapy: Engineered in silico pipelines for HLA Typing and Neoantigen Discovery from cancer patient NGS and RNA-Seq splice junction data."` → `"Genomik & Immuntherapie: Entwicklung von in-silico-Pipelines zur HLA-Typisierung und Neoantigen-Discovery aus NGS- und RNA-Seq-Splice-Junction-Daten von Krebspatienten."`
- Bullet 2 (Biophysics & Imaging): `"Biophysics & Imaging: Managed end-to-end Super-Resolution Microscopy projects; from wet-lab research to spatial point-pattern data analysis (MATLAB/Python) for studying chromatin."` → `"Biophysik & Bildgebung: End-to-End-Leitung von Super-Resolution-Mikroskopie-Projekten; von Nasslabor-Forschung bis zur räumlichen Punktmuster-Analyse (MATLAB/Python) zur Untersuchung von Chromatin."`
- Bullet 3 (Neurobiology): `"Neurobiology: Investigated radiation effects on Neural Progenitor Differentiation using 3D cell models and the role of extracellular vesicles."` → `"Neurobiologie: Untersuchung von Strahlungseffekten auf die neuronale Vorläuferdifferenzierung mit 3D-Zellmodellen sowie der Rolle extrazellulärer Vesikel."`
- Bullet 4 (Scientific Impact): `"Scientific Impact: Authored 10+ peer-reviewed papers, secured third-party funding, and mentored 10+ students."` → `"Wissenschaftlicher Impact: 10+ peer-reviewte Publikationen, Einwerbung von Drittmitteln und Betreuung von 10+ Studierenden."`

- [ ] **Step 2: Validate the schema**

```bash
just validate
```
Expected: `OK: all content files validate`. If a langmap pattern complains about `de:` keys being unexpected, check `schema/cv.schema.json` for explicit `en`-only constraints and broaden to accept `de:`.

- [ ] **Step 3: Smoke-test DE build**

```bash
uv run python -m pdf.build --lang de
```

Expected: **build fails** because `content/profile.de.yaml` and `content/projects/*.de.yaml` don't exist yet. Specifically, you should see a `FileNotFoundError` for `profile.de.yaml`. That's expected — Tasks 4 and 5 add those files. **Do NOT try to fix this error in Task 3.**

EN build should still work fine:
```bash
uv run python -m pdf.build --lang en
```

- [ ] **Step 4: Commit**

```bash
git add content/personal.yaml content/experience.yaml content/education.yaml content/skills.yaml content/volunteer.yaml content/languages.yaml
git commit -m "feat(content): add DE translations to in-tree YAML files"
```

---

## Task 4: Create `content/profile.de.yaml`

A prose translation of `content/profile.en.yaml`. Subagent drafts; Jin-Ho polishes during PR review.

**Files:**
- Create: `content/profile.de.yaml`

- [ ] **Step 1: Read the EN profile**

```bash
cat content/profile.en.yaml
```

- [ ] **Step 2: Write the DE file**

Create `content/profile.de.yaml` with this structure mirroring the EN file. Translate the `tagline` and each entry in `paragraphs`. Apply the **Translation style guide**.

```yaml
tagline: "Data Science- und Bioinformatik-Enthusiast mit Expertise in ML, Computer Vision, GenAI und Cloud Engineering."
paragraphs:
  - "Ich verbinde Forschung im Nasslabor mit produktiver KI — 10+ peer-reviewte Publikationen und Verantwortung für 1.000+ analytische Cloud-Prozesse. Mein Erfahrungshintergrund reicht von Finance über Healthcare bis zu Neurowissenschaft, Genomik und Immunologie."
  - "Bringe meine offene, neugierige und anpassungsfähige Arbeitshaltung gerne in sinnstiftende Projekte ein — tiefe biologische Expertise kombiniert mit industriegerechter Data Science in einem starken Team!"
```

- [ ] **Step 3: Validate**

```bash
just validate
```
Expected: clean. If validation fails on `profile.de.yaml`, the schema likely uses a `profile` definition that's lang-agnostic (per `_FILE_RULES` in `validate.py`, line 96: `("profile.*.yaml", "profile")` — so DE files are validated by the same rule).

- [ ] **Step 4: Smoke-test DE build (still partial — projects missing)**

```bash
uv run python -m pdf.build --lang de
```

Expected: build still fails, but on a *different* error now — specifically the projects loader trying to find `*.de.yaml` project files. That's expected; Task 5 creates them.

- [ ] **Step 5: Commit**

```bash
git add content/profile.de.yaml
git commit -m "feat(content): add German profile (profile.de.yaml)"
```

---

## Task 5: Create all 9 `content/projects/*.de.yaml` files

For each of `L1, L2, L3, L4, D1, D2, D3, C1, C2`, create a German mirror of the corresponding `.en.yaml` file. Translate `title`, `summary`, `role`, each entry in `contributions`, and `outcome`. Keep `id`, `category`, `period`, and `technologies` verbatim (technologies are brand names like "Python", "TensorFlow", "BigQuery"). Apply the **Translation style guide**.

**Files:**
- Create: `content/projects/L1.de.yaml`, `L2.de.yaml`, `L3.de.yaml`, `L4.de.yaml`, `D1.de.yaml`, `D2.de.yaml`, `D3.de.yaml`, `C1.de.yaml`, `C2.de.yaml`

- [ ] **Step 1: List the EN project files for reference**

```bash
ls content/projects/
for f in content/projects/*.en.yaml; do echo "=== $f ==="; cat "$f"; done | head -200
```

- [ ] **Step 2: For each EN project file, write a DE mirror**

For each `content/projects/<ID>.en.yaml`, create `content/projects/<ID>.de.yaml` with:
- `id:` — same value as EN (e.g. `L1`).
- `category:` — same enum value (e.g. `life-science`).
- `title:` — translate.
- `summary:` — translate; keep technical terms verbatim.
- `role:` — translate.
- `period:` — copy from EN (numeric values, no translation).
- `technologies:` — copy from EN verbatim.
- `contributions:` — translate each entry.
- `outcome:` — translate.

Example reference: for L1, the EN `title` is `"Cancer Neoantigen Discovery – Transcriptome-Wide Splice Analysis"`. A reasonable DE rendering: `"Krebs-Neoantigen-Entdeckung – Transkriptomweite Splice-Analyse"`. Apply the same translation discipline (preserve brand/tech terms; concise, formal register) across all 9 files.

- [ ] **Step 3: Validate**

```bash
just validate
```
Expected: `OK: all content files validate`.

- [ ] **Step 4: Smoke-test DE build (should now fully succeed)**

```bash
rm -rf dist/
uv run python -m pdf.build --lang de
ls -la dist/cv-de.pdf
```
Expected: `dist/cv-de.pdf` exists, ~50-150 KB. Open it visually — confirm:
- Section headings are in German ("Berufserfahrung", "Ausbildung", etc.)
- Month abbreviations are German where applicable ("Mär", "Mai", "Okt", "Dez")
- Bullets render in German
- Brand/tech names remain in English (Python, TensorFlow, etc.)
- Proficiency in languages shows "Muttersprache", "fließend", etc.

- [ ] **Step 5: Smoke-test EN build still works**

```bash
uv run python -m pdf.build --lang en
ls -la dist/cv-en.pdf
```
Expected: succeeds. EN PDF unchanged from Phase 2a output.

- [ ] **Step 6: Commit**

```bash
git add content/projects/*.de.yaml
git commit -m "feat(content): add German translations for all 9 project files"
```

---

## Task 6: Add project DE-EN parity check to `scripts/validate.py` (TDD)

A new validation rule: every `content/projects/<ID>.en.yaml` must have a matching `content/projects/<ID>.de.yaml`, and vice versa.

**Files:**
- Test: `tests/test_validate.py`
- Modify: `scripts/validate.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_validate.py` (don't delete existing tests):

```python
def test_de_en_project_file_parity_fails_on_missing_de(tmp_path):
    """validate_tree should report an error when an .en.yaml exists without matching .de.yaml."""
    from scripts.validate import validate_tree

    # Build a minimal content tree under tmp_path
    content = tmp_path / "content"
    (content / "projects").mkdir(parents=True)

    # Required top-level files (minimal valid stubs)
    (content / "personal.yaml").write_text(
        "name:\n  given: Test\n  family: User\n"
        "email: t@example.com\n"
        "location: { city: X, country: DE }\n"
        "links: { linkedin: null, github: null, researchgate: null, orcid: null }\n"
        "photo: assets/photo.jpg\n"
        "headline: { en: T }\n"
    )
    (content / "profile.en.yaml").write_text("tagline: T\nparagraphs: [P]\n")
    (content / "skills.yaml").write_text("categories: []\n")
    (content / "education.yaml").write_text("[]\n")
    (content / "experience.yaml").write_text("[]\n")
    (content / "languages.yaml").write_text("[]\n")
    (content / "volunteer.yaml").write_text("categories: []\n")
    (content / "publications.bib").write_text("")
    (content / "labels.yaml").write_text(
        "sections: { profile: { en: P }, experience: { en: E }, "
        "education: { en: E }, skills: { en: S }, languages: { en: L }, volunteer: { en: V } }\n"
        "months_abbr: []\n"
        "proficiency: { native: { en: n }, fluent: { en: f }, basic: { en: b }, passive: { en: p } }\n"
    )

    # The asymmetry: L1 exists in EN but not DE
    (content / "projects" / "L1.en.yaml").write_text(
        "id: L1\ncategory: life-science\ntitle: T\nsummary: S\n"
        "role: R\nperiod: { start: '2020-01', end: '2020-02' }\n"
        "technologies: [X]\ncontributions: [C]\noutcome: O\n"
    )

    schema_path = tmp_path / "../../schema/cv.schema.json"
    errors = validate_tree(content, schema_path.resolve())
    assert any("L1.de.yaml" in str(e) for e in errors), (
        f"expected missing-DE-file error, got: {errors}"
    )


def test_de_en_project_file_parity_fails_on_missing_en(tmp_path):
    """validate_tree should also catch DE-only project files (something's wrong if EN is missing)."""
    from scripts.validate import validate_tree

    content = tmp_path / "content"
    (content / "projects").mkdir(parents=True)
    # ... (same scaffolding as above; only difference is the projects/ contents)
    (content / "personal.yaml").write_text(
        "name:\n  given: Test\n  family: User\n"
        "email: t@example.com\n"
        "location: { city: X, country: DE }\n"
        "links: { linkedin: null, github: null, researchgate: null, orcid: null }\n"
        "photo: assets/photo.jpg\n"
        "headline: { en: T }\n"
    )
    (content / "profile.en.yaml").write_text("tagline: T\nparagraphs: [P]\n")
    (content / "skills.yaml").write_text("categories: []\n")
    (content / "education.yaml").write_text("[]\n")
    (content / "experience.yaml").write_text("[]\n")
    (content / "languages.yaml").write_text("[]\n")
    (content / "volunteer.yaml").write_text("categories: []\n")
    (content / "publications.bib").write_text("")
    (content / "labels.yaml").write_text(
        "sections: { profile: { en: P }, experience: { en: E }, "
        "education: { en: E }, skills: { en: S }, languages: { en: L }, volunteer: { en: V } }\n"
        "months_abbr: []\n"
        "proficiency: { native: { en: n }, fluent: { en: f }, basic: { en: b }, passive: { en: p } }\n"
    )

    (content / "projects" / "L1.de.yaml").write_text(
        "id: L1\ncategory: life-science\ntitle: T\nsummary: S\n"
        "role: R\nperiod: { start: '2020-01', end: '2020-02' }\n"
        "technologies: [X]\ncontributions: [C]\noutcome: O\n"
    )

    schema_path = tmp_path / "../../schema/cv.schema.json"
    errors = validate_tree(content, schema_path.resolve())
    assert any("L1.en.yaml" in str(e) for e in errors)
```

- [ ] **Step 2: Run the new tests; expect them to fail**

```bash
uv run pytest tests/test_validate.py::test_de_en_project_file_parity_fails_on_missing_de tests/test_validate.py::test_de_en_project_file_parity_fails_on_missing_en -v
```
Expected: both tests FAIL because `validate_tree` doesn't yet enforce parity.

- [ ] **Step 3: Implement the parity check in `scripts/validate.py`**

Inside `validate_tree`, after the projects loop (around line 132-136), add a parity check before `_validate_publications` is called:

```python
    # Project DE-EN file parity
    project_dir = content_dir / "projects"
    en_ids = {p.name.split(".")[0] for p in project_dir.glob("*.en.yaml")}
    de_ids = {p.name.split(".")[0] for p in project_dir.glob("*.de.yaml")}
    for missing_id in en_ids - de_ids:
        errors.append(FileError(
            project_dir / f"{missing_id}.de.yaml",
            "missing DE counterpart for EN project file"
        ))
    for missing_id in de_ids - en_ids:
        errors.append(FileError(
            project_dir / f"{missing_id}.en.yaml",
            "missing EN counterpart for DE project file"
        ))

    errors.extend(_validate_publications(content_dir))
    return errors
```

- [ ] **Step 4: Run the new tests; expect them to pass**

```bash
uv run pytest tests/test_validate.py -v
```
Expected: all pass.

- [ ] **Step 5: Run full pytest + validate**

```bash
uv run pytest -v
just validate
```
Expected: all green. Real content/ tree has DE files for every project (from Task 5), so the new parity check finds nothing missing.

- [ ] **Step 6: Commit**

```bash
git add scripts/validate.py tests/test_validate.py
git commit -m "feat(validate): enforce DE-EN file parity for projects/"
```

---

## Task 7: Add `tests/test_de_completeness.py`

A regression test that walks the resolved DE content tree and asserts no language fallbacks happened — every langmap that had `en:` should also have a real `de:` value (not the same string falling through). Catches future cases where someone adds a new `en:` field and forgets `de:`.

**Files:**
- Create: `tests/test_de_completeness.py`

- [ ] **Step 1: Write the test file**

Create `tests/test_de_completeness.py`:

```python
"""Detect missing `de:` keys by comparing en/de resolved content trees."""
from __future__ import annotations

from pathlib import Path

import pytest

from scripts.content_loader import load_content
from scripts.langstring import resolve_langstrings


REPO_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = REPO_ROOT / "content"


def _flatten_strings(tree, prefix=""):
    """Yield (path, value) for every string leaf in the tree."""
    if isinstance(tree, dict):
        for k, v in tree.items():
            yield from _flatten_strings(v, prefix=f"{prefix}.{k}")
    elif isinstance(tree, list):
        for i, item in enumerate(tree):
            yield from _flatten_strings(item, prefix=f"{prefix}[{i}]")
    elif isinstance(tree, str):
        yield (prefix, tree)


# Paths that legitimately don't change between en and de.
# - URLs, emails, brand/proper nouns, paths, enum values, periods (YYYY-MM strings),
#   technology names, organization names.
_ALLOWED_IDENTICAL_PREFIXES = (
    ".personal.email",
    ".personal.links",
    ".personal.location",
    ".personal.name",
    ".personal.photo",
    ".publications",        # bibtex records are language-agnostic raw data
    ".experience.[",        # entries — org names are identical; period dates identical
    ".projects.",           # project records — technologies, ids, period are identical
    ".skills.",             # items[] are tech names (verbatim across langs)
    ".volunteer.",          # entries[] are org names
    ".languages.[",         # proficiency enum values
)


def _is_allowed_identical(path: str, value: str) -> bool:
    """Filter out fields where it's correct for EN == DE."""
    # All numeric / date-shaped / URL / email / single-char / pure-identifier strings
    if not value or value.isdigit():
        return True
    if value.startswith(("http://", "https://", "mailto:")):
        return True
    if "@" in value and "." in value and " " not in value:  # email-shaped
        return True
    # Period strings like "2024-05"
    if len(value) == 7 and value[4] == "-" and value[:4].isdigit() and value[5:].isdigit():
        return True
    # Path-shaped values
    if value.startswith("assets/") or value.endswith((".yaml", ".typ", ".bib")):
        return True
    # Allow-list of paths that legitimately are identical
    return any(path.startswith(p) for p in _ALLOWED_IDENTICAL_PREFIXES)


def test_de_resolves_distinctly_from_en():
    """Walk the en and de resolved trees; flag any user-visible string that's identical."""
    en_tree = resolve_langstrings(load_content(CONTENT_DIR, lang="en"), lang="en")
    de_tree = resolve_langstrings(load_content(CONTENT_DIR, lang="de"), lang="de")

    en_strings = dict(_flatten_strings(en_tree))
    de_strings = dict(_flatten_strings(de_tree))

    suspicious = []
    for path, en_value in en_strings.items():
        de_value = de_strings.get(path)
        if de_value == en_value and not _is_allowed_identical(path, en_value):
            suspicious.append((path, en_value))

    assert not suspicious, (
        "Found user-visible strings identical between EN and DE (suggests missing `de:` key):\n"
        + "\n".join(f"  {p}: {v!r}" for p, v in suspicious[:20])
    )
```

- [ ] **Step 2: Run the new test**

```bash
uv run pytest tests/test_de_completeness.py -v
```
Expected: PASS (because Tasks 3, 4, 5 added all the DE strings).

If it fails, the failure message identifies which paths leak through as English. Fix those paths by adding the missing `de:` keys in the appropriate YAML file, then re-run.

- [ ] **Step 3: Sanity-check the test catches regressions (manual)**

Temporarily remove the `de:` key from one bullet in `content/experience.yaml`, run the test, confirm it fails with that bullet's path. Then restore.

```bash
# Manual: edit content/experience.yaml, remove a `de:` line
uv run pytest tests/test_de_completeness.py -v
# Expect: FAIL with path like ".experience.[0].bullets.[1].de"
# Manual: restore the removed line
uv run pytest tests/test_de_completeness.py -v
# Expect: PASS
```

(This step is a sanity check — don't commit any change. It validates the test does what we think.)

- [ ] **Step 4: Run full test suite**

```bash
uv run pytest -v
```
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add tests/test_de_completeness.py
git commit -m "test: add DE completeness check (regression guard for missing translations)"
```

---

## Task 8: Refactor `.github/workflows/ci.yml` — matrix `build-pdf` + single `release` job

Replace the single-language `build-pdf` job with a matrix over `[en, de]`. Add a new `release` job that downloads both artifacts and creates one release with both PDFs. This eliminates the race condition called out in the Phase 2a final review.

**Files:**
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Read the current file**

```bash
cat .github/workflows/ci.yml
```

- [ ] **Step 2: Replace the entire file with the matrix+release structure**

The full new content of `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

permissions:
  contents: read

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6

      - name: Install uv
        uses: astral-sh/setup-uv@v8.1.0
        with:
          version: "latest"

      - name: Set up Python
        run: uv python install 3.12

      - name: Install dependencies
        run: uv sync --all-groups

      - name: Validate content
        run: uv run python -m scripts.validate

      - name: Run tests
        run: uv run pytest -v --tb=short

      - name: Lint
        run: uv run ruff check .

  build-pdf:
    needs: validate
    runs-on: ubuntu-latest
    strategy:
      matrix:
        lang: [en, de]
    steps:
      - uses: actions/checkout@v6

      - name: Install uv
        uses: astral-sh/setup-uv@v8.1.0
        with:
          version: "latest"

      - name: Set up Python
        run: uv python install 3.12

      - name: Install dependencies
        run: uv sync --all-groups

      - name: Read pinned Typst version
        id: typst-version
        run: echo "version=$(cat .typstversion)" >> "$GITHUB_OUTPUT"

      - name: Install Typst
        uses: typst-community/setup-typst@v5
        with:
          typst-version: ${{ steps.typst-version.outputs.version }}

      - name: Install IBM Plex Sans font
        run: |
          sudo apt-get update
          sudo apt-get install -y fonts-ibm-plex
          fc-cache -f

      - name: Build ${{ matrix.lang }} PDF
        run: uv run python -m pdf.build --lang ${{ matrix.lang }}

      - name: Upload PDF artifact
        uses: actions/upload-artifact@v7
        with:
          name: cv-${{ matrix.lang }}-pdf
          path: dist/cv-${{ matrix.lang }}.pdf
          retention-days: 30
          if-no-files-found: error

  release:
    needs: build-pdf
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - name: Download all PDF artifacts
        uses: actions/download-artifact@v7
        with:
          path: dist
          merge-multiple: true

      - name: Compute release metadata
        id: meta
        run: |
          echo "date=$(date -u +%Y-%m-%d)" >> "$GITHUB_OUTPUT"
          echo "short_sha=${GITHUB_SHA::7}" >> "$GITHUB_OUTPUT"

      - name: Create GitHub Release
        uses: softprops/action-gh-release@v3
        with:
          tag_name: cv-${{ steps.meta.outputs.date }}-${{ steps.meta.outputs.short_sha }}
          name: CV ${{ steps.meta.outputs.date }}
          files: |
            dist/cv-en.pdf
            dist/cv-de.pdf
          make_latest: true
          body: |
            Auto-generated CV release from commit ${{ github.sha }}.

            Commit: ${{ github.event.head_commit.message }}

            View commit: ${{ github.server_url }}/${{ github.repository }}/commit/${{ github.sha }}
```

Key changes from Phase 2a's `ci.yml`:
- `build-pdf` has `strategy.matrix.lang: [en, de]`.
- `build-pdf` no longer has `permissions: contents: write` (only `release` writes).
- `build-pdf` artifact uploads unconditionally (was PR-only) — harmless on push runs since `release` consumes them.
- The PR-only upload condition is gone; previously needed because the release step lived in the same job; now `release` is a separate job gated on push-to-main.
- New `release` job: needs build-pdf to finish all matrix entries; downloads via `actions/download-artifact@v7` with `merge-multiple: true` (artifacts named `cv-en-pdf` and `cv-de-pdf` are merged into `dist/`); creates one release with both files.

- [ ] **Step 3: Validate YAML syntax**

```bash
uv run python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))" && echo "YAML OK"
```
Expected: `YAML OK`.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: matrix build-pdf [en, de] + single release job with both PDFs"
```

---

## Task 9: Update `justfile` and `README.md`

Small companion changes.

**Files:**
- Modify: `justfile`
- Modify: `README.md`

- [ ] **Step 1: Read current justfile**

```bash
cat justfile
```

- [ ] **Step 2: Add DE recipes**

Append to `justfile` (before the `clean:` recipe so related ones group together):

```just
# Build the public DE PDF (no PII) → dist/cv-de.pdf
build-de:
    uv run python -m pdf.build --lang de

# Build the private DE PDF (with phone + address) → dist-private/cv-de.pdf
build-private-de:
    uv run python -m pdf.build --lang de --private
```

- [ ] **Step 3: Update the Latest CV line in README.md**

Open `README.md`. The current line is:

```markdown
**Latest CV:** [Download `cv-en.pdf`](https://github.com/Jin-HoMLee/jin-ho-lee-cv/releases/latest/download/cv-en.pdf) — auto-published on every change to `main`.
```

Replace with:

```markdown
**Latest CV:** [EN](https://github.com/Jin-HoMLee/jin-ho-lee-cv/releases/latest/download/cv-en.pdf) · [DE](https://github.com/Jin-HoMLee/jin-ho-lee-cv/releases/latest/download/cv-de.pdf) — auto-published on every change to `main`.
```

- [ ] **Step 4: Smoke-test the new just recipe**

```bash
just clean
just build-de
ls -la dist/cv-de.pdf
```
Expected: `dist/cv-de.pdf` exists.

- [ ] **Step 5: Commit**

```bash
git add justfile README.md
git commit -m "feat: add build-de justfile recipes and DE link in README"
```

---

## Task 10: Local end-to-end smoke test

Final pre-PR verification.

**Files:**
- None (verification only)

- [ ] **Step 1: Clean build of both languages**

```bash
just clean
just build
just build-de
ls -la dist/
```
Expected: both `cv-en.pdf` and `cv-de.pdf` present, both non-empty.

- [ ] **Step 2: Validate all content**

```bash
just validate
just test
just lint
```
Expected: all green.

- [ ] **Step 3: Visually open both PDFs**

```bash
open dist/cv-en.pdf
open dist/cv-de.pdf
```

Visually compare:
- Same layout (1 page each).
- Same font (IBM Plex Sans).
- EN PDF: section headings in English, months in English, proficiency in English ("native", etc.).
- DE PDF: section headings in German ("Berufserfahrung", etc.), months in German where they differ ("Mär", "Mai", "Okt", "Dez"), proficiency in German ("Muttersprache", "fließend").
- Brand/tech names verbatim in both (Python, BigQuery, Cintellic).

If anything looks off, fix on the branch and commit before moving to Task 11.

---

## Task 11: Push branch, open PR, verify CI

**Files:**
- None (CI verification only)

- [ ] **Step 1: Push the branch**

```bash
git push -u origin phase-2b-translations
```

- [ ] **Step 2: Open the PR**

```bash
gh pr create --title "Phase 2b: DE translations + bilingual CI release" --body "$(cat <<'EOF'
## Summary

Makes the CV bilingual. Every push to `main` will publish a release with both `cv-en.pdf` and `cv-de.pdf` attached.

Implements [Phase 2b spec](docs/superpowers/specs/2026-05-22-phase-2b-translations-design.md). Includes the matrix workflow refactor flagged by the Phase 2a final reviewer.

## Translation review

DE translations in:
- `content/labels.yaml` — section headings, months, proficiency labels (drafted from spec §5.1)
- `content/personal.yaml`, `experience.yaml`, `education.yaml`, `skills.yaml`, `volunteer.yaml`, `languages.yaml` — short strings (per Task 3 of the plan, verbatim from plan)
- `content/profile.de.yaml` — multi-paragraph prose (subagent draft, polish welcome)
- `content/projects/*.de.yaml` × 9 — project descriptions (subagent draft, polish welcome)

Review focus: tone/idiom on the prose (`profile.de.yaml` and project `summary`/`contributions`/`outcome`).

## Test plan

- [ ] CI validate + matrix build-pdf both langs + (skipped on PR) release
- [ ] Both `cv-en-pdf` and `cv-de-pdf` artifacts attached to PR run
- [ ] No release created (PR event)
- [ ] After merge: both PDFs in latest release; tags rotated correctly
EOF
)"
```

Capture the PR URL.

- [ ] **Step 3: Watch CI**

```bash
gh pr checks --watch
```
Expected: `validate` passes, then `build-pdf (en)` and `build-pdf (de)` both pass in parallel. The `release` job appears as "skipping" or doesn't run at all (because it's gated on `push` to main, not `pull_request`).

If any job fails, investigate with `gh run view --log-failed` and fix on the branch.

- [ ] **Step 4: Confirm both artifacts attached and no release**

```bash
RUN_ID=$(gh run list --workflow=ci.yml --branch=phase-2b-translations --event=pull_request --limit=1 --json databaseId --jq '.[0].databaseId')
gh api /repos/Jin-HoMLee/jin-ho-lee-cv/actions/runs/$RUN_ID/artifacts --jq '.artifacts[].name'
echo "---"
gh release list --limit 3
```

Expected: artifact names list contains both `cv-en-pdf` and `cv-de-pdf`. Release list shows no `cv-` releases newer than the most recent merge to main (i.e., no premature release).

- [ ] **Step 5: Download artifacts and visually verify**

```bash
gh run download $RUN_ID -D /tmp/phase-2b-check
open /tmp/phase-2b-check/cv-en-pdf/cv-en.pdf
open /tmp/phase-2b-check/cv-de-pdf/cv-de.pdf
```

Confirm both look correct as in Task 10 Step 3.

- [ ] **Step 6: Request `@claude` review (optional)**

```bash
gh pr comment <PR-number> --body "@claude review this PR for spec compliance and code quality"
```

Wait for the cloud Claude action's response. Address any blockers it raises (push additional commits as needed; the artifacts regenerate on each push).

---

## Task 12: Merge with `--no-ff` and verify the production release

Per CLAUDE.md convention: per-phase branches merge to `main` with `--no-ff`.

**Files:**
- None (merge + verification only)

- [ ] **Step 1: Mark PR ready (if still draft) and confirm CI green**

```bash
gh pr ready
gh pr checks
```

- [ ] **Step 2: Merge via `gh pr merge` with `--merge` (no-ff) and delete branch**

```bash
gh pr merge phase-2b-translations --merge --delete-branch -t "Merge Phase 2b: DE translations + bilingual CI release" -b ""
```

The `--merge` flag creates a no-ff merge commit (matching the Phase 2a style). The `--delete-branch` flag removes the branch locally and on remote.

After the command, switch back to a clean main:

```bash
git switch main
git pull
```

- [ ] **Step 3: Watch the post-merge CI run**

```bash
RUN_ID=$(gh run list --workflow=ci.yml --branch=main --event=push --limit=1 --json databaseId --jq '.[0].databaseId')
gh run watch "$RUN_ID" --exit-status --interval 10
```

Use a Bash timeout of 600000ms. Expected: validate passes, both matrix build-pdf jobs pass, release job creates the GitHub Release.

- [ ] **Step 4: Confirm the release has both PDFs**

```bash
gh release list --limit 3
gh release view --json tagName,assets,isLatest
```
Expected: most recent release is tagged `cv-YYYY-MM-DD-<short-sha>`, marked `isLatest: true`, with assets array containing both `cv-en.pdf` and `cv-de.pdf`.

- [ ] **Step 5: Confirm both download URLs resolve**

```bash
curl -sLI -o /dev/null -w "EN: %{http_code}\n" "https://github.com/Jin-HoMLee/jin-ho-lee-cv/releases/latest/download/cv-en.pdf"
curl -sLI -o /dev/null -w "DE: %{http_code}\n" "https://github.com/Jin-HoMLee/jin-ho-lee-cv/releases/latest/download/cv-de.pdf"
```
Expected: both `200`.

- [ ] **Step 6: Update CLAUDE.md status table**

Edit `CLAUDE.md` row 22:
```markdown
| 2b | German translations + DE PDF in CI | Not started |
```

becomes:
```markdown
| 2b | German translations + DE PDF in CI | ✅ Done (merged YYYY-MM-DD, commit `<merge-sha>`) |
```

Use the actual merge date (UTC) and the first 7 chars of the merge commit SHA from `git log -1 --format=%H`.

Open a small follow-up PR (don't push directly to main — auto-mode classifier blocks that):

```bash
git switch -c docs/mark-phase-2b-done
git add CLAUDE.md
git commit -m "docs: mark Phase 2b as done"
git push -u origin docs/mark-phase-2b-done
gh pr create --title "docs: mark Phase 2b as done" --body "Status table update following Phase 2b merge."
gh pr merge --rebase --delete-branch
git switch main && git pull
```

This second merge triggers an extra release (same PDF content, different commit). Acceptable noise.

---

## Self-Review

Mapped against spec sections:

- §1 Scope (full bilingual): covered by Tasks 3, 4, 5 (every visible string gets DE).
- §2 Goal (release with both PDFs, latest URL works for DE): Tasks 8, 11, 12.
- §3 Non-goals: explicitly not touched.
- §4 Architecture: Task 1 (labels), Task 2 (Typst i18n), Task 8 (workflow), with content tasks 3-5 filling in DE data.
- §5.1 `content/labels.yaml`: Task 1 — exact content matches spec.
- §5.2 YAML additions: Task 3 (concrete DE strings provided).
- §5.3 New per-language files: Tasks 4 and 5.
- §5.4 Typst template updates: Task 2 (all template files touched).
- §5.5 Schema/validator: Tasks 6 (validator parity), 7 (DE completeness test).
- §5.6 Workflow refactor: Task 8.
- §5.7 Justfile: Task 9.
- §5.8 README: Task 9.
- §5.9 Translation workflow: implementer drafts everything per concrete instructions; Jin-Ho reviews in the PR.
- §6 Failure modes: covered by tests in Tasks 6 and 7; workflow split eliminates the race.
- §7 Testing strategy: Tasks 6 and 7 plus Task 10 local smoke test plus Task 11 CI verification.
- §8 Migration/rollback: additive; covered.
- §9 Sequencing: implementation choices in Task 8 (matrix + release) match the spec's template for future format additions.
- §10 Open decisions: §10 says "permissive schema + strict test" — Task 6 adds the strict file-parity check; Task 7 adds the strict langmap completeness test; no schema change forced. §10 says "implementation chooses the simpler" for months refactor — Task 2 Step 4 passes months as a function parameter (the simpler option).

No placeholders. Every code/YAML step has concrete content. Every command has expected output. Each task ends with a single atomic commit.
