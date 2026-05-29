# Phase 7 — Content Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reconcile `content/` against ground truth — fix date/factual errors, add on-theme skills/Italian/ORCID/website, deprioritize the off-theme 2025 publication, and add a B.Sc. major + a minimal Awards section — keeping EN/DE parity and regenerating all renderers cleanly.

**Architecture:** `content/*.yaml` + `publications.bib` are the single source of truth. `scripts/content_loader.py` loads them into one dict; `scripts/bib_loader.py` parses publications; five renderers consume the dict (`scripts/render_text.py`, `scripts/render_jsonresume.py`, `scripts/render_jsonld.py`, `scripts/render_web_data.py` → web JSON, and `pdf/templates/*.typ`). `schema/cv.schema.json` + `scripts/validate.py` enforce structure. Adding a new section = new `$def` + `_FILE_RULES` tuple + `content_loader` key + `labels.yaml` label + per-renderer emit.

**Tech Stack:** Python 3 (pybtex, jsonschema), Astro + TypeScript + Tailwind (web), Typst (PDF), pytest, `just`, `uv`.

**Conventions:** TDD (test first, watch fail, implement). Atomic commits, plain messages, no attribution trailers, no `--no-verify`. Run targeted tests with `uv run python -m pytest <path> -q`; full gate is `just validate && just test && just lint`. All LangString edits must carry both `en` and `de` (enforced by `tests/test_de_completeness.py`).

**Design decisions (settled in the spec):** Awards live in the **main column, right after Education** in every renderer. Publication ordering is driven by a new `category` bib field (`research` default, `applied` for the marketing chapter), sorted research-before-applied then year-desc. ORCID stored as the full resolver URL. L4 dates unchanged.

---

## File Structure

**Modify (content):** `content/projects/L1.en.yaml`, `L1.de.yaml`, `L2.en.yaml`, `L2.de.yaml`, `L3.en.yaml`, `L3.de.yaml`; `content/experience.yaml`; `content/profile.de.yaml`; `content/skills.yaml`; `content/languages.yaml`; `content/personal.yaml`; `content/education.yaml`; `content/labels.yaml`; `content/publications.bib`.
**Create (content):** `content/awards.yaml`.
**Modify (code):** `scripts/bib_loader.py`; `scripts/content_loader.py`; `scripts/validate.py`; `schema/cv.schema.json`; `scripts/render_text.py`; `scripts/render_jsonresume.py`; `scripts/render_jsonld.py`; `web/src/types/content.ts`; `web/src/components/EducationSection.astro`; `web/src/pages/index.astro`; `web/src/pages/de/index.astro`; `pdf/templates/cv.typ`; `pdf/templates/education.typ`.
**Create (code):** `web/src/components/AwardsSection.astro`; `pdf/templates/awards.typ`.
**Modify (tests):** `tests/test_bib_loader.py`, `tests/test_content_loader.py`, `tests/test_validate.py`, `tests/test_render_text.py`, `tests/test_render_jsonresume.py`, `tests/test_render_jsonld.py`, `tests/test_render_web_data.py`, `tests/test_build_data.py`.
**Regenerated artifacts (commit at the end):** `web/src/data/content.en.json`, `web/src/data/content.de.json`.

---

## Task 1: Date & factual corrections (content-only)

Fix L1/L2/L3 project dates, the `research` experience start, and the German profile opener.

**Files:**
- Modify: `content/projects/L1.en.yaml:6-8`, `content/projects/L1.de.yaml:6-8`, `content/projects/L2.en.yaml:6-8`, `content/projects/L2.de.yaml:6-8`, `content/projects/L3.en.yaml:6-8`, `content/projects/L3.de.yaml:6-8`
- Modify: `content/experience.yaml` (research entry `period.start`)
- Modify: `content/profile.de.yaml:3`
- Test: `tests/test_content_loader.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_content_loader.py`:

```python
def test_corrected_project_periods(content_dir):
    content = load_content(content_dir, private_path=None, lang="en")
    projects = content["projects"]
    assert projects["L1"]["period"] == {"start": "2015-08", "end": "2015-11"}
    assert projects["L2"]["period"] == {"start": "2014-04", "end": "2014-05"}
    assert projects["L3"]["period"]["start"] == "2017-02"


def test_research_entry_start_not_after_earliest_subproject(content_dir):
    content = load_content(content_dir, private_path=None, lang="en")
    research = next(e for e in content["experience"] if e["id"] == "research")
    assert research["period"]["start"] == "2014-04"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_content_loader.py::test_corrected_project_periods tests/test_content_loader.py::test_research_entry_start_not_after_earliest_subproject -q`
Expected: FAIL (periods still `2018-09`/`2013-10`/`2017-05`; research start `2014-06`).

- [ ] **Step 3: Apply the content edits**

`content/projects/L1.en.yaml` and `content/projects/L1.de.yaml` — replace lines 6-8:

```yaml
period:
  start: "2015-08"
  end: "2015-11"
```

`content/projects/L2.en.yaml` and `content/projects/L2.de.yaml` — replace lines 6-8:

```yaml
period:
  start: "2014-04"
  end: "2014-05"
```

`content/projects/L3.en.yaml` and `content/projects/L3.de.yaml` — replace lines 6-8:

```yaml
period:
  start: "2017-02"
  end: "2018-08"
```

`content/experience.yaml` — in the `research` entry, change `period.start` from `"2014-06"` to:

```yaml
  period:
    start: "2014-04"
    end: "2022-07"
```

`content/profile.de.yaml:3` — replace the paragraph opener. Change the start from `"Aktuelle Industrietätigkeit bei Cintellic: Architektur der Migration` to `"Bei Cintellic: Architektur der Migration` (drop the "Aktuelle Industrietätigkeit" current-role framing; keep the rest of the paragraph identical). The full corrected `paragraphs` first item:

```yaml
  - "Bei Cintellic: Architektur der Migration von 1.000+ analytischen Prozessen in die Google Cloud. Forschungshintergrund: 10+ peer-reviewed Publikationen, darunter als Erstautor sowie mit geteilter Erstautorschaft in Cancers, Epigenetics Methods und OBM Genetics zu Super-Resolution-Chromatin und Strahlenbiologie, aufbauend auf Wet-Lab-Ausbildung und Bioinformatik-Pipeline-Entwicklung an DKFZ, NCT, FZ Jülich, KIP und SNU; Einwerbung von Drittmitteln und Betreuung von 10+ Studierenden."
```

- [ ] **Step 4: Run tests + validation to verify they pass**

Run: `uv run python -m pytest tests/test_content_loader.py -q && just validate`
Expected: PASS; `OK: all content files validate`.

- [ ] **Step 5: Commit**

```bash
git add content/projects/L1.*.yaml content/projects/L2.*.yaml content/projects/L3.*.yaml content/experience.yaml content/profile.de.yaml tests/test_content_loader.py
git commit -m "content: correct L1/L2/L3 project dates, research start, and DE profile opener"
```

---

## Task 2: Skills + languages additions (content-only)

Add MapSplice, samtools/bcftools, a Structural Biology sub-group, and Italian.

**Files:**
- Modify: `content/skills.yaml:6-11` (Bioinformatics & ML category)
- Modify: `content/languages.yaml`
- Test: `tests/test_content_loader.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_content_loader.py`:

```python
def test_skills_additions_present(content_dir):
    content = load_content(content_dir, private_path=None, lang="en")
    bioml = next(c for c in content["skills"]["categories"] if c["name"]["en"] == "Bioinformatics & ML")
    groups = {g["label"]["en"]: g["items"] for g in bioml["groups"]}
    assert "MapSplice" in groups["Genomics"]
    assert "samtools/bcftools" in groups["Genomics"]
    assert "Structural Biology" in groups
    assert set(groups["Structural Biology"]) == {"TCRdock", "AlphaFold v2", "Mol*"}


def test_italian_language_present(content_dir):
    content = load_content(content_dir, private_path=None, lang="en")
    names = {lang["name"]["en"] for lang in content["languages"]}
    assert "Italian" in names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_content_loader.py::test_skills_additions_present tests/test_content_loader.py::test_italian_language_present -q`
Expected: FAIL.

- [ ] **Step 3: Apply the content edits**

`content/skills.yaml` — in the `Bioinformatics & ML` category, update the `Genomics` group items and insert a `Structural Biology` group after `Immunology`:

```yaml
      - label: { en: "Genomics", de: "Genomik" }
        items: ["NGS", "RNA-Seq", "WES", "SNV Calling", "Splice Analysis", "MapSplice", "HISAT2/STAR", "samtools/bcftools", "bedtools"]
      - label: { en: "Immunology", de: "Immunologie" }
        items: ["MHC-I Prediction", "HLA Typing", "OptiType", "MHCflurry", "Neoepitopes"]
      - label: { en: "Structural Biology", de: "Strukturbiologie" }
        items: ["TCRdock", "AlphaFold v2", "Mol*"]
      - label: { en: "Nanoscopy", de: "Nanoskopie" }
        items: ["Spatial Point-Pattern", "Cluster Analysis (DBSCAN)"]
```

`content/languages.yaml` — insert Italian after French (before Latin):

```yaml
- name: { en: "French", de: "Französisch" }
  proficiency: basic
- name: { en: "Italian", de: "Italienisch" }
  proficiency: basic
- name: { en: "Latin", de: "Latein" }
  proficiency: passive
```

- [ ] **Step 4: Run tests + validation**

Run: `uv run python -m pytest tests/test_content_loader.py -q && just validate`
Expected: PASS; validate OK.

- [ ] **Step 5: Commit**

```bash
git add content/skills.yaml content/languages.yaml tests/test_content_loader.py
git commit -m "content: add MapSplice/samtools, Structural Biology skills group, and Italian"
```

---

## Task 3: Identity links — ORCID + website (content-only)

**Files:**
- Modify: `content/personal.yaml:11-15` (links)
- Test: `tests/test_render_jsonld.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_render_jsonld.py` (uses the module-scoped `doc` fixture that renders from real content):

```python
def test_orcid_and_website_in_same_as(doc):
    same_as = doc["sameAs"]
    assert "https://orcid.org/0009-0001-8784-1771" in same_as
    assert "https://jinholee.is-a.dev/" in same_as
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_render_jsonld.py::test_orcid_and_website_in_same_as -q`
Expected: FAIL (orcid is null; website absent).

- [ ] **Step 3: Apply the content edit**

`content/personal.yaml` — replace the `links` block:

```yaml
links:
  linkedin: "https://linkedin.com/in/jin-holee"
  github:   "https://github.com/Jin-HoMLee"
  researchgate: "https://researchgate.net/profile/Jin-Ho-Lee-8"
  website: "https://jinholee.is-a.dev/"
  orcid: "https://orcid.org/0009-0001-8784-1771"
```

- [ ] **Step 4: Run tests + validation**

Run: `uv run python -m pytest tests/test_render_jsonld.py tests/test_render_jsonresume.py -q && just validate`
Expected: PASS; validate OK (link values are valid `uri` strings).

- [ ] **Step 5: Commit**

```bash
git add content/personal.yaml tests/test_render_jsonld.py
git commit -m "content: wire ORCID iD and website link into personal links"
```

---

## Task 4: Publications ordering — deprioritize the marketing chapter

Add a `category` bib field (`research` default, `applied` for the 2025 chapter) and sort research-before-applied, then year-descending.

**Files:**
- Modify: `scripts/bib_loader.py:13-18, 21-31, 64, 67-88, 91-95`
- Modify: `content/publications.bib` (lee2025_marketing_automation entry)
- Test: `tests/test_bib_loader.py`

- [ ] **Step 1: Write the failing tests**

In `tests/test_bib_loader.py`, ADD these tests and REPLACE the existing `test_publications_sorted_by_year_desc`:

```python
def test_category_defaults_to_research_when_absent(tmp_path):
    bib = tmp_path / "nocat.bib"
    bib.write_text(
        "@article{x, author={Lee, J.}, title={T}, year={2019}, "
        "journal={J}, type={article}, authorship={first}}\n"
    )
    assert load_publications(bib)[0].category == "research"


def test_category_applied_parsed(tmp_path):
    bib = tmp_path / "applied.bib"
    bib.write_text(
        "@incollection{x, author={Lee, J.}, title={T}, year={2025}, "
        "booktitle={B}, type={book-chapter}, authorship={first}, category={applied}}\n"
    )
    assert load_publications(bib)[0].category == "applied"


def test_unknown_category_raises(tmp_path):
    bib = tmp_path / "badcat.bib"
    bib.write_text(
        "@article{x, author={Lee, J.}, title={T}, year={2019}, "
        "journal={J}, type={article}, authorship={first}, category={bogus}}\n"
    )
    with pytest.raises(ValueError, match="category"):
        load_publications(bib)


def test_publications_sorted_research_then_applied_then_year_desc():
    pubs = load_publications(BIB_PATH)
    first_applied = next(
        (i for i, p in enumerate(pubs) if p.category == "applied"), len(pubs)
    )
    assert all(p.category == "research" for p in pubs[:first_applied])
    assert all(p.category == "applied" for p in pubs[first_applied:])
    research_years = [p.year for p in pubs if p.category == "research"]
    applied_years = [p.year for p in pubs if p.category == "applied"]
    assert research_years == sorted(research_years, reverse=True)
    assert applied_years == sorted(applied_years, reverse=True)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/test_bib_loader.py -q`
Expected: FAIL (`Publication` has no `category`; `_category` undefined).

- [ ] **Step 3: Implement in `scripts/bib_loader.py`**

(a) After line 14 (`AUTHORSHIP_VALUES = ...`), add:

```python
CATEGORY_VALUES = {"research", "applied"}
CATEGORY_RANK = {"research": 0, "applied": 1}
```

(b) In the `Publication` dataclass (lines 21-31), add `category` as the LAST field, after `raw: dict` (it has a default, so it must come last):

```python
@dataclass(frozen=True)
class Publication:
    key: str
    title: str
    year: int
    type: str
    authorship: str
    authors: tuple[str, ...]
    venue: str | None
    doi: str | None
    raw: dict
    category: str = "research"
```

(c) Immediately after the `_doi` function (after line 64), add:

```python
def _category(key: str, fields) -> str:
    raw = fields.get("category")
    if raw is None:
        return "research"
    value = str(raw).strip().lower()
    if value not in CATEGORY_VALUES:
        raise ValueError(
            f"{key}: unknown category {value!r} (expected one of {sorted(CATEGORY_VALUES)})"
        )
    return value
```

(d) In `_parse_entry` (the `return Publication(...)` call), add `category=_category(key, fields),` after `raw=dict(fields),`:

```python
    return Publication(
        key=key,
        title=fields["title"],
        year=int(fields["year"]),
        type=fields["type"],
        authorship=fields["authorship"],
        authors=authors,
        venue=_venue(entry),
        doi=_doi(key, fields),
        raw=dict(fields),
        category=_category(key, fields),
    )
```

(e) Replace `load_publications` (lines 91-95):

```python
def load_publications(bib_path: Path) -> list[Publication]:
    """Parse a .bib file into Publication records.

    Sorted research-category first, then applied-category; year-descending
    (newest first) within each category. Sort is stable, so same-(category, year)
    entries keep their original .bib order.
    """
    bib = parse_file(str(bib_path))
    pubs = [_parse_entry(key, entry) for key, entry in bib.entries.items()]
    return sorted(pubs, key=lambda p: (CATEGORY_RANK[p.category], -p.year))
```

- [ ] **Step 4: Tag the applied entry in `content/publications.bib`**

In the `@incollection{lee2025_marketing_automation,` entry, add a `category` field after the `authorship` line:

```bibtex
  type       = {book-chapter},
  authorship = {first},
  category   = {applied}
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_bib_loader.py -q`
Expected: PASS (the 2025 entry now sorts after all research entries; research run is year-desc).

- [ ] **Step 6: Commit**

```bash
git add scripts/bib_loader.py content/publications.bib tests/test_bib_loader.py
git commit -m "feat: order publications research-first via bib category field"
```

---

## Task 5: Education `field` (major) — schema + renderers

Add an optional `field` LangString to education; populate the B.Sc. with "Bioinformatics"; surface it in text, JSON Resume (`area`), web, and PDF. (JSON-LD intentionally unchanged — schema.org has no clean major property.)

**Files:**
- Modify: `schema/cv.schema.json:119-133`
- Modify: `content/education.yaml`
- Modify: `scripts/render_text.py:86-90`
- Modify: `scripts/render_jsonresume.py:82`
- Modify: `web/src/types/content.ts:35-40`
- Modify: `web/src/components/EducationSection.astro:15-23`
- Modify: `pdf/templates/education.typ:9-15`
- Test: `tests/test_render_jsonresume.py`, `tests/test_render_text.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_render_jsonresume.py` (uses the module `doc` fixture):

```python
def test_bsc_education_area_is_bioinformatics(doc):
    bsc = next(e for e in doc["education"] if e["studyType"].startswith("B.Sc."))
    assert bsc["area"] == "Bioinformatics"
```

Add to `tests/test_render_text.py`:

```python
def test_education_includes_bsc_major():
    out = render("en")
    assert "Bioinformatics" in out
```

(If `render` is not already imported in `tests/test_render_text.py`, add `from scripts.render_text import render` at the top alongside the existing imports.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/test_render_jsonresume.py::test_bsc_education_area_is_bioinformatics tests/test_render_text.py::test_education_includes_bsc_major -q`
Expected: FAIL (`area` is `""`; no major in text).

- [ ] **Step 3: Schema — add the optional `field` property**

`schema/cv.schema.json` — in the `education` items `properties` (lines 123-128), add a `field` line after `degree`:

```json
        "properties": {
          "degree": { "$ref": "#/$defs/LangString" },
          "field": { "$ref": "#/$defs/LangString" },
          "institution": { "type": "string" },
          "location": { "type": "string" },
          "year": { "type": "integer", "minimum": 1900, "maximum": 2100 }
        },
```

(Leave `"required"` unchanged — `field` stays optional.)

- [ ] **Step 4: Content — add the B.Sc. major**

`content/education.yaml` — add a `field` LangString to the B.Sc. entry only (the second item):

```yaml
- degree:
    en: "B.Sc. Molecular Biotechnology"
    de: "B.Sc. Molekulare Biotechnologie"
  field:
    en: "Bioinformatics"
    de: "Bioinformatik"
  institution: "Heidelberg University"
  location: "Heidelberg, Germany"
  year: 2014
```

- [ ] **Step 5: Renderers — surface `field`**

`scripts/render_jsonresume.py:82` — replace `"area": "",` with:

```python
            "area": edu.get("field", ""),
```

`scripts/render_text.py` — replace `_education` (lines 86-90) with a loop that appends the major when present:

```python
def _education(content: dict) -> str:
    lines = []
    for e in content["education"]:
        major = f", {e['field']}" if e.get("field") else ""
        lines.append(f"{e['year']}  {e['degree']}{major} - {e['institution']} ({e['location']})")
    return "\n".join(lines)
```

`web/src/types/content.ts` — add `field?: string;` to the `Education` interface:

```typescript
export interface Education {
  degree: string;
  field?: string;
  institution: string;
  location: string;
  year: number;
}
```

`web/src/components/EducationSection.astro` — inside the `education.map(...)` block, add a `field` line after the degree `<p>` (lines 17-18 region):

```jsx
      <div>
        <p class="text-sm font-semibold text-neutral-900">{ed.degree}</p>
        {ed.field && <p class="text-sm text-neutral-700">{ed.field}</p>}
        <p class="text-sm text-neutral-700">{ed.institution} · {ed.location}</p>
        <p class="text-xs text-neutral-500">{ed.year}</p>
      </div>
```

`pdf/templates/education.typ` — inside the per-entry content block (lines 9-15), render `field` after the degree, mirroring the optional-`location` idiom:

```typst
      {
        text(weight: 600)[#entry.degree]
        if "field" in entry {
          linebreak()
          text(size: size-small, style: "italic", fill: muted)[#entry.field]
        }
        linebreak()
        text(size: size-small, fill: muted)[
          #entry.institution#if "location" in entry { " · " + entry.location }
        ]
      },
```

- [ ] **Step 6: Run tests + validation**

Run: `uv run python -m pytest tests/test_render_jsonresume.py tests/test_render_text.py -q && just validate`
Expected: PASS; validate OK.

- [ ] **Step 7: Commit**

```bash
git add schema/cv.schema.json content/education.yaml scripts/render_text.py scripts/render_jsonresume.py web/src/types/content.ts web/src/components/EducationSection.astro pdf/templates/education.typ tests/test_render_jsonresume.py tests/test_render_text.py
git commit -m "feat: add optional education field (major); surface B.Sc. Bioinformatics"
```

---

## Task 6: Awards section — data layer

New `awards` section: schema `$def`, `content/awards.yaml`, validation rule, loader key, label, and TS types. (Renderers come in Task 7.)

**Files:**
- Modify: `schema/cv.schema.json` (new `awards` `$def` after `volunteer`)
- Create: `content/awards.yaml`
- Modify: `scripts/validate.py:94-103` (`_FILE_RULES`)
- Modify: `scripts/content_loader.py:56-58` (docstring), `:77-89` (content dict)
- Modify: `content/labels.yaml:1-8` (sections map)
- Modify: `web/src/types/content.ts` (new `Award`, `ContentData.awards`, `Labels.sections.awards`)
- Test: `tests/test_validate.py`, `tests/test_content_loader.py`, `tests/test_render_web_data.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_content_loader.py`:

```python
def test_awards_loaded(content_dir):
    content = load_content(content_dir, private_path=None, lang="en")
    assert "awards" in content
    titles = {a["title"]["en"] for a in content["awards"]}
    assert "DAAD PROMOS Scholarship" in titles
    assert "DeGBS Poster Award" in titles
```

Add to `tests/test_validate.py`:

```python
def test_malformed_awards_fails(schema_path, tmp_path):
    """An award missing the required 'issuer' should fail validation."""
    bad = tmp_path / "awards.yaml"
    bad.write_text("- title: { en: \"X\" }\n  year: 2020\n")
    with pytest.raises(ValidationError):
        validate_file(bad, schema_def="awards", schema_path=schema_path)
```

In `tests/test_render_web_data.py`, add `"awards"` to the `expected_keys` set in `test_round_trip_structural_keys` (lines 30-35):

```python
    expected_keys = {
        "personal", "profile", "skills", "education", "experience",
        "projects", "selected_projects", "languages", "volunteer",
        "publications", "labels", "awards",
    }
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/test_content_loader.py::test_awards_loaded tests/test_validate.py::test_malformed_awards_fails tests/test_render_web_data.py::test_round_trip_structural_keys -q`
Expected: FAIL (no awards `$def`/file/key).

- [ ] **Step 3: Schema — add the `awards` `$def`**

`schema/cv.schema.json` — after the `volunteer` `$def` closing brace (the last `$def`, ~line 240), add a comma and a new `awards` `$def` (still inside the top-level `$defs` object):

```json
    "awards": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "title": { "$ref": "#/$defs/LangString" },
          "issuer": { "type": "string" },
          "year": { "type": "integer", "minimum": 1900, "maximum": 2100 },
          "note": { "$ref": "#/$defs/LangString" }
        },
        "required": ["title", "issuer", "year"],
        "additionalProperties": false
      },
      "minItems": 1
    }
```

- [ ] **Step 4: Create `content/awards.yaml`**

```yaml
- title:
    en: "DAAD PROMOS Scholarship"
    de: "DAAD-PROMOS-Stipendium"
  issuer: "DAAD"
  year: 2015
  note:
    en: "Funded the Seoul National University research internship (Bio & Health Informatics Lab) on splice-junction neoantigen discovery."
    de: "Förderung des Forschungspraktikums an der Seoul National University (Bio & Health Informatics Lab) zur Splice-Junction-Neoantigen-Identifizierung."

- title:
    en: "DeGBS Poster Award"
    de: "DeGBS-Posterpreis"
  issuer: "Deutsche Gesellschaft für Biologische Strahlenforschung"
  year: 2021
```

- [ ] **Step 5: Register in `validate.py`, `content_loader.py`, `labels.yaml`**

`scripts/validate.py` — append to `_FILE_RULES` (after the `volunteer` tuple, line 102):

```python
    ("volunteer.yaml", "volunteer"),
    ("awards.yaml", "awards"),
]
```

`scripts/content_loader.py` — add the `awards` key to the `content` dict (after the `volunteer` line, ~line 86):

```python
        "volunteer": _load_yaml(content_dir / "volunteer.yaml"),
        "awards": _load_yaml(content_dir / "awards.yaml"),
        "publications": load_publications(content_dir / "publications.bib"),
        "labels": _load_yaml(content_dir / "labels.yaml"),
```

`scripts/content_loader.py` — update the `load_content` docstring key list (lines 56-58) to include `awards` (and `labels`, which the current docstring omits):

```python
    Returns a dict with keys: personal, profile, skills, education, experience,
    projects (dict keyed by id), selected_projects, languages, volunteer, awards,
    publications (list of records), labels.
```

`content/labels.yaml` — add an `awards` row to the `sections:` map (after `education`, line 5):

```yaml
  education:         { en: "Education",         de: "Ausbildung" }
  awards:            { en: "Awards",            de: "Auszeichnungen" }
  skills:            { en: "Skills",            de: "Kenntnisse" }
```

- [ ] **Step 6: TypeScript types**

`web/src/types/content.ts` — add an `Award` interface (near `Volunteer`, ~line 74):

```typescript
export interface Award {
  title: string;
  issuer: string;
  year: number;
  note?: string;
}
```

Add `awards: Award[];` to `ContentData` (after `volunteer`):

```typescript
  volunteer: Volunteer;
  awards: Award[];
  publications: Publication[];
```

Add `awards: string;` to `Labels.sections` (after `education`):

```typescript
  sections: {
    profile: string;
    experience: string;
    education: string;
    awards: string;
    skills: string;
    languages: string;
    volunteer: string;
  };
```

- [ ] **Step 7: Run tests + validation**

Run: `uv run python -m pytest tests/test_content_loader.py tests/test_validate.py tests/test_render_web_data.py -q && just validate`
Expected: PASS; `OK: all content files validate` (real `awards.yaml` is schema-valid).

- [ ] **Step 8: Commit**

```bash
git add schema/cv.schema.json content/awards.yaml scripts/validate.py scripts/content_loader.py content/labels.yaml web/src/types/content.ts tests/test_content_loader.py tests/test_validate.py tests/test_render_web_data.py
git commit -m "feat: add awards section (schema, content, loader, validation, types)"
```

---

## Task 7: Awards section — renderers

Emit awards in plain text, JSON Resume, JSON-LD, web (new component + both pages), and PDF — all in the main column right after Education.

**Files:**
- Modify: `scripts/render_text.py:19-28` (labels), new `_awards`, `:128-145` (render order)
- Modify: `scripts/render_jsonresume.py` (new `_awards`, `to_jsonresume`)
- Modify: `scripts/render_jsonld.py:80-108` (`to_jsonld`)
- Create: `web/src/components/AwardsSection.astro`
- Modify: `web/src/pages/index.astro`, `web/src/pages/de/index.astro`
- Create: `pdf/templates/awards.typ`
- Modify: `pdf/templates/cv.typ`
- Test: `tests/test_render_text.py`, `tests/test_render_jsonresume.py`, `tests/test_render_jsonld.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_render_text.py`:

```python
def test_awards_section_renders():
    out = render("en")
    assert "AWARDS" in out
    assert "DAAD PROMOS Scholarship" in out

def test_awards_section_renders_de():
    out = render("de")
    assert "AUSZEICHNUNGEN" in out
```

Add to `tests/test_render_jsonresume.py`:

```python
def test_awards_array_present(doc):
    titles = {a["title"] for a in doc["awards"]}
    assert "DAAD PROMOS Scholarship" in titles
    daad = next(a for a in doc["awards"] if a["title"] == "DAAD PROMOS Scholarship")
    assert daad["awarder"] == "DAAD"
    assert daad["date"] == "2015-01-01"
    assert "summary" in daad
```

Add to `tests/test_render_jsonld.py`:

```python
def test_person_award_present(doc):
    assert "DAAD PROMOS Scholarship" in doc["award"]
    assert "DeGBS Poster Award" in doc["award"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/test_render_text.py tests/test_render_jsonresume.py tests/test_render_jsonld.py -q -k "award or Awards"`
Expected: FAIL (no awards emitted; `doc["award"]`/`doc["awards"]` missing).

- [ ] **Step 3: Plain text — `scripts/render_text.py`**

Add an `awards` entry to `SECTION_LABELS` (after `education`, line 22):

```python
    "education":         {"en": "EDUCATION",         "de": "AUSBILDUNG"},
    "awards":            {"en": "AWARDS",            "de": "AUSZEICHNUNGEN"},
    "skills":            {"en": "SKILLS",            "de": "KENNTNISSE"},
```

Add a `_awards` emitter near the other section emitters (e.g. after `_education`):

```python
def _awards(content: dict) -> str:
    lines = []
    for a in content["awards"]:
        lines.append(f"{a['year']}  {a['title']} - {a['issuer']}")
        if a.get("note"):
            lines.append(f"  {a['note']}")
    return "\n".join(lines)
```

In `render()`, insert the awards section into the `sections` list right after the education line (line 139):

```python
        _section(L["education"][lang],         _education(content)),
        _section(L["awards"][lang],            _awards(content)),
        _section(L["skills"][lang],            _skills(content)),
```

- [ ] **Step 4: JSON Resume — `scripts/render_jsonresume.py`**

Add an `_awards` builder (near `_volunteer`, ~line 116) using the native JSON Resume award fields:

```python
def _awards(content: dict) -> list[dict]:
    out = []
    for a in content["awards"]:
        entry = {
            "title": a["title"],
            "date": f"{a['year']}-01-01",
            "awarder": a["issuer"],
        }
        if a.get("note"):
            entry["summary"] = a["note"]
        out.append(entry)
    return out
```

Add `"awards": _awards(content),` to the `to_jsonresume` return dict (after `"volunteer"`):

```python
        "volunteer": _volunteer(content),
        "awards": _awards(content),
        "projects": _projects(content),
        "publications": _publications(pubs),
    }
```

- [ ] **Step 5: JSON-LD — `scripts/render_jsonld.py`**

In `to_jsonld`, after the `worksFor` conditional and before the `doc["@graph"] = ...` line (~line 106), add:

```python
    if content["awards"]:
        doc["award"] = [a["title"] for a in content["awards"]]

    doc["@graph"] = _publications(pubs) + _projects(content)
    return doc
```

- [ ] **Step 6: Web — create `web/src/components/AwardsSection.astro`**

```astro
---
import type { Award, Labels } from "../types/content";

interface Props {
  awards: Award[];
  labels: Labels;
}

const { awards, labels } = Astro.props;
---
<section id="awards" class="py-6">
  <h2 class="mb-3 text-xs font-semibold uppercase tracking-wider text-neutral-500">
    {labels.sections.awards}
  </h2>
  <div class="space-y-3">
    {awards.map((a) => (
      <div>
        <p class="text-sm font-semibold text-neutral-900">{a.title} <span class="font-normal text-neutral-500">· {a.year}</span></p>
        <p class="text-sm text-neutral-700">{a.issuer}</p>
        {a.note && <p class="text-xs text-neutral-500">{a.note}</p>}
      </div>
    ))}
  </div>
</section>
```

- [ ] **Step 7: Web — wire into both pages (main column, after Education)**

`web/src/pages/index.astro` — add the import after the `PublicationsList` import (line 13):

```astro
import PublicationsList from "../components/PublicationsList.astro";
import AwardsSection from "../components/AwardsSection.astro";
```

and place the component after `<EducationSection ... />` in the main column:

```astro
      <EducationSection education={data.education} labels={data.labels} />
      <AwardsSection awards={data.awards} labels={data.labels} />
      <PublicationsList publications={data.publications} lang="en" />
```

`web/src/pages/de/index.astro` — same change, but the import uses `../../`:

```astro
import PublicationsList from "../../components/PublicationsList.astro";
import AwardsSection from "../../components/AwardsSection.astro";
```

```astro
      <EducationSection education={data.education} labels={data.labels} />
      <AwardsSection awards={data.awards} labels={data.labels} />
      <PublicationsList publications={data.publications} lang="de" />
```

- [ ] **Step 8: PDF — create `pdf/templates/awards.typ`**

```typst
#import "../styles.typ": *

#let awards(entries, labels) = {
  section-heading(labels.sections.awards)

  for entry in entries {
    grid(
      columns: (1fr, auto),
      align: (left, right),
      {
        text(weight: 600)[#entry.title]
        linebreak()
        text(size: size-small, fill: muted)[#entry.issuer]
        if "note" in entry {
          linebreak()
          text(size: size-small, fill: muted)[#entry.note]
        }
      },
      text(size: size-small, fill: muted)[#entry.year],
    )
    v(space-paragraph)
  }
}
```

- [ ] **Step 9: PDF — wire into `pdf/templates/cv.typ`**

Add the import after the `education.typ` import (line 6):

```typst
#import "education.typ": education
#import "awards.typ": awards
```

Add the call in the main-column block, after `education(...)`:

```typst
        education(data.education, data.labels)
        awards(data.awards, data.labels)
```

- [ ] **Step 10: Run tests + validation**

Run: `uv run python -m pytest tests/test_render_text.py tests/test_render_jsonresume.py tests/test_render_jsonld.py -q && just validate`
Expected: PASS; validate OK.

- [ ] **Step 11: Commit**

```bash
git add scripts/render_text.py scripts/render_jsonresume.py scripts/render_jsonld.py web/src/components/AwardsSection.astro web/src/pages/index.astro web/src/pages/de/index.astro pdf/templates/awards.typ pdf/templates/cv.typ tests/test_render_text.py tests/test_render_jsonresume.py tests/test_render_jsonld.py
git commit -m "feat: render awards section across text, JSON Resume, JSON-LD, web, PDF"
```

---

## Task 8: Research-bullet enrichment (content-only)

Fold the NCT colorectal SNV-calling + DKFZ NGS variant work into the research entry's genomics bullet.

**Files:**
- Modify: `content/experience.yaml` (research entry, first bullet en + de)
- Test: `tests/test_content_loader.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_content_loader.py`:

```python
def test_research_genomics_bullet_mentions_variant_calling(content_dir):
    content = load_content(content_dir, private_path=None, lang="en")
    research = next(e for e in content["experience"] if e["id"] == "research")
    first_bullet = research["bullets"][0]["en"]
    assert "SNV" in first_bullet and "colorectal" in first_bullet.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_content_loader.py::test_research_genomics_bullet_mentions_variant_calling -q`
Expected: FAIL.

- [ ] **Step 3: Apply the content edit**

`content/experience.yaml` — replace the first research bullet's `en` and `de` text (keep `refs: [L1, L2]`):

```yaml
    - en: "Genomics & Immunotherapy: Engineered in silico pipelines for HLA Typing and Neoantigen Discovery from cancer-patient NGS and RNA-Seq splice-junction data; validated SNV calls against gold-standard sequencing in clinical colorectal-cancer cohorts (NCT/DKFZ)."
      de: "Genomik & Immuntherapie: Entwicklung von in-silico-Pipelines zur HLA-Typisierung und Neoantigen-Discovery aus NGS- und RNA-Seq-Splice-Junction-Daten von Krebspatienten; Validierung von SNV-Calls gegen Goldstandard-Sequenzierung in klinischen Kolorektal-Kohorten (NCT/DKFZ)."
      refs: [L1, L2]
```

- [ ] **Step 4: Run test + validation**

Run: `uv run python -m pytest tests/test_content_loader.py -q && just validate`
Expected: PASS; validate OK.

- [ ] **Step 5: Commit**

```bash
git add content/experience.yaml tests/test_content_loader.py
git commit -m "content: fold clinical variant-calling (NCT/DKFZ) into research bullet"
```

---

## Task 9: Full regeneration, build verification, and gate

Regenerate the committed web JSON, verify all renderers + the Astro/PDF builds, run the full gate, and spot-check.

**Files:**
- Regenerated: `web/src/data/content.en.json`, `web/src/data/content.de.json`
- (build artifacts under `dist/` are not committed)

- [ ] **Step 1: Run the full gate**

Run: `just validate && just test && just lint`
Expected: validate OK; all tests pass; ruff clean.

- [ ] **Step 2: Regenerate machine formats + text and spot-check**

Run: `just build-formats && just build-text`
Then verify (from repo root):

```bash
grep -c "doi.org" dist/resume.json
grep -n "2015-08\|2015" dist/cv-en.txt | head
grep -n "orcid.org/0009-0001-8784-1771" dist/person.jsonld
grep -n "AWARDS\|DAAD PROMOS" dist/cv-en.txt
grep -n "AUSZEICHNUNGEN" dist/cv-de.txt
python3 -c "import json; d=json.load(open('dist/resume.json')); print('awards:', [a['title'] for a in d['awards']]); print('first pub:', d['publications'][0]['name'] if d['publications'] else None); print('last pub:', d['publications'][-1]['name'] if d['publications'] else None)"
```

Expected: ORCID URL present; AWARDS/AUSZEICHNUNGEN headers present; `resume.json` lists both awards; the first publication is a research entry (2021 chapter) and the LAST is the 2025 marketing chapter (deprioritized).

- [ ] **Step 3: Regenerate + build the website**

Run: `just web-build`
Expected: `render_web_data` regenerates `web/src/data/content.{en,de}.json`; `astro check` + build succeed (new `AwardsSection`, `Award` type, and education `field` all type-check). Confirm the awards section + B.Sc. major appear:

```bash
python3 -c "import json; d=json.load(open('web/src/data/content.en.json')); print('awards' in d, [a['title'] for a in d['awards']]); print('bsc field:', [e.get('field') for e in d['education']])"
```

Expected: `True ['DAAD PROMOS Scholarship', 'DeGBS Poster Award']`; B.Sc. field `Bioinformatics`.

- [ ] **Step 4: Commit the regenerated web data**

```bash
git add web/src/data/content.en.json web/src/data/content.de.json
git commit -m "chore: regenerate web content JSON for content audit"
```

(If `just web-build` produced no diff because a prior task already regenerated it, skip this commit.)

---

## Self-Review

**Spec coverage:**
- WS1 (dates/factual) → Task 1 (L1/L2/L3, research start, DE opener). ✓
- WS2 (skills + Italian) → Task 2. ✓
- WS3 (ORCID + website) → Task 3. ✓
- WS4 (publications ordering) → Task 4. ✓
- WS5a (education field) → Task 5. ✓
- WS5b (awards) → Tasks 6 (data) + 7 (renderers). ✓
- WS6 (research bullet) → Task 8. ✓
- Validation/regeneration/gate → Task 9. ✓

**Placeholder scan:** No TBD/TODO; every code step shows complete before/after. ✓

**Type consistency:** `Publication.category` (default `"research"`) used by `CATEGORY_RANK`/`_category` in Task 4; `Award` TS interface fields (`title/issuer/year/note?`) defined in Task 6 match `AwardsSection.astro` usage and `awards.yaml` shape in Tasks 6/7; JSON Resume award keys (`title/awarder/date/summary`) match the fixture; `Education.field?` defined in Task 5 matches `EducationSection.astro` and `render_jsonresume` `edu.get("field", "")`. ✓

**Non-goals honored:** No certificates/references/interests; volunteer untouched; L4 unchanged; JSON-LD education unchanged. ✓
