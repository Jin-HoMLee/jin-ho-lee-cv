# Phase 14 - AEO Entity Presence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Jin-Ho Lee's CV site resolvable and citable by answer engines - external entity anchors (Wikidata + Google Scholar in `sameAs`), a bilingual FAQ with `FAQPage` JSON-LD, a front-loaded answer block, and a CI guard proving the public CV facts live in static HTML.

**Architecture:** Content stays the single source of truth. New `content/faq.yaml` (schema-validated, `{en, de}` langmaps) and a new `answer_block` profile field flow through the existing `content_loader` → `resolve_langstrings` → `render_web_data` pipeline into `web/src/data/content.{en,de}.json`, where a new `FaqSection.astro` renders both the visible `<details>` list and the `FAQPage` JSON-LD from the same data. Two new `personal.yaml` links (Google Scholar now, Wikidata after the off-repo item exists) flow automatically into JSON-LD `sameAs`. A new CI job builds `web/dist` and runs a pytest asserting the public facts are present in raw HTML and the twin-exclusive tier is not.

**Tech Stack:** Python 3.12 (ruamel.yaml, jsonschema, pytest, syrupy), Astro 5 + Tailwind (web), GitHub Actions, uv, just.

## Global Constraints

- **Source of truth:** `content/*.yaml`. Renderers consume; never edit content from inside a renderer.
- **Two-tier visibility:** `content/` is the public tier and MUST be crawler-readable in static HTML. `master-cv/` is deliberately twin-exclusive; crawlers not seeing it is a feature. FAQ answers are grounded in `content/` facts only, never the overlay.
- **LangString:** short user-facing strings are inline `{ en: "...", de: "..." }` maps. FAQ requires BOTH `en` and `de` (schema-enforced).
- **Green gate before every commit:** `just validate && just test && just lint && just fmt`.
- **No em dashes** in any authored prose or code comment; use a plain `-`.
- **Commits:** atomic, one logical change; no Claude attribution / co-authored-by trailers.
- **Snapshots:** renderer outputs are byte-snapshotted with syrupy. Regenerate intentionally with `just snapshots-update` and eyeball the diff; never hand-edit `tests/__snapshots__/`.
- **Branch:** `phase-14-aeo-entity-presence` (already created, linked to issue #113).
- **Canonical Scholar URL:** `https://scholar.google.com/citations?user=QPyM-WoAAAAJ` (no `hl` param).
- **Non-goals:** no `llms.txt` investment, no `robots.txt` change, no FAQ automation, no per-project answer blocks, no `/faq` route, no FAQ in PDF / resume.json / person.jsonld / cv-*.txt / twin chat context.

---

### Task 1: Google Scholar entity anchor

Adds the Scholar profile to `personal.yaml` links so it flows into JSON-LD `sameAs` (automatic - `_same_as` takes every link key except `website`) and JSON Resume `profiles` (needs a display-name mapping).

**Files:**
- Modify: `content/personal.yaml:11-16` (add `googlescholar` link)
- Modify: `scripts/render_jsonresume.py:31-37` (`_network_for` mapping)
- Test: `tests/test_render_jsonresume.py`, `tests/test_render_jsonld.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `personal["links"]["googlescholar"]` - a string URL available to every renderer.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_render_jsonresume.py`:

```python
def test_google_scholar_profile_has_display_network_name(doc):
    """The Scholar link must render as a human network name, not the raw key."""
    networks = {p["network"] for p in doc["basics"]["profiles"]}
    assert "Google Scholar" in networks
    assert "Googlescholar" not in networks
```

Append to `tests/test_render_jsonld.py`:

```python
def test_google_scholar_in_same_as(graph):
    person = next(n for n in graph["@graph"] if n["@type"] == "Person")
    assert "https://scholar.google.com/citations?user=QPyM-WoAAAAJ" in person["sameAs"]
```

If `tests/test_render_jsonld.py` has no `graph` fixture with that exact name, reuse whatever module-level fixture it already defines for the rendered document and adapt the first line accordingly - do not invent a second fixture.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `just test 2>&1 | tail -20` (or `uv run pytest tests/test_render_jsonresume.py tests/test_render_jsonld.py -v`)
Expected: FAIL - `"Google Scholar" in networks` assertion error; Scholar URL missing from `sameAs`.

- [ ] **Step 3: Add the link to content**

In `content/personal.yaml`, inside `links:`, after the `orcid` line:

```yaml
  googlescholar: "https://scholar.google.com/citations?user=QPyM-WoAAAAJ"
```

- [ ] **Step 4: Add the JSON Resume network mapping**

In `scripts/render_jsonresume.py`, extend `_network_for`:

```python
def _network_for(key: str) -> str:
    return {
        "linkedin": "LinkedIn",
        "github": "GitHub",
        "researchgate": "ResearchGate",
        "orcid": "ORCID",
        "googlescholar": "Google Scholar",
        "wikidata": "Wikidata",
    }.get(key, key.title())
```

(`wikidata` is mapped now so Task 7's Q-ID wiring needs no code change.)

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_render_jsonresume.py tests/test_render_jsonld.py -v`
Expected: PASS.

- [ ] **Step 6: Regenerate snapshots and eyeball the diff**

Run: `just snapshots-update && git diff tests/__snapshots__/`
Expected: the Scholar URL appears in `resume.json` profiles, `person.jsonld` `sameAs`, `cv-en.txt` / `cv-de.txt` header link lines, and `llms.txt` if it lists links. No other drift. The PDF is unaffected (its header picks explicit keys only).

- [ ] **Step 7: Green gate and commit**

```bash
just validate && just test && just lint && just fmt
git add content/personal.yaml scripts/render_jsonresume.py tests/ 
git commit -m "aeo(#113): add Google Scholar profile to entity anchors"
```

---

### Task 2: FAQ content file + schema + validation

Creates the curated bilingual FAQ as content, validated like every other content file. Seeded with answers grounded strictly in `content/` facts.

**Files:**
- Create: `content/faq.yaml`
- Create: `schema/faq.schema.json`
- Modify: `scripts/validate.py:93-104` (`_FILE_RULES`), `scripts/validate.py:311-336` (`main`, to pass the FAQ schema path)
- Create: `tests/fixtures/invalid_yaml/faq_duplicate_id.yaml`, `tests/fixtures/invalid_yaml/faq_missing_de.yaml`
- Create: `tests/test_faq_schema.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `content/faq.yaml` shape: `{"faqs": [{"id": str, "question": {"en": str, "de": str}, "answer": {"en": str, "de": str}}, ...]}`
  - `scripts.validate.validate_faq(content_dir: Path, schema_path: Path) -> list[FileError]`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_faq_schema.py`:

```python
"""FAQ content must be schema-valid and fully bilingual (Phase 14, issue #113)."""

from __future__ import annotations

from pathlib import Path

from scripts.validate import validate_faq


REPO_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = REPO_ROOT / "content"
FAQ_SCHEMA = REPO_ROOT / "schema" / "faq.schema.json"
FIXTURES = Path(__file__).parent / "fixtures" / "invalid_yaml"


def test_real_faq_validates():
    assert validate_faq(CONTENT_DIR, FAQ_SCHEMA) == []


def test_real_faq_is_bilingual_and_nonempty():
    from ruamel.yaml import YAML

    data = YAML(typ="safe").load((CONTENT_DIR / "faq.yaml").read_text(encoding="utf-8"))
    faqs = data["faqs"]
    assert len(faqs) >= 5, "seed the FAQ with at least 5 curated entries"
    ids = [f["id"] for f in faqs]
    assert len(ids) == len(set(ids)), "FAQ ids must be unique"
    for entry in faqs:
        for field in ("question", "answer"):
            assert entry[field]["en"].strip(), f"{entry['id']}: empty en {field}"
            assert entry[field]["de"].strip(), f"{entry['id']}: empty de {field}"


def test_duplicate_id_fails(tmp_path):
    content = tmp_path / "content"
    content.mkdir()
    (content / "faq.yaml").write_text(
        (FIXTURES / "faq_duplicate_id.yaml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    errors = validate_faq(content, FAQ_SCHEMA)
    assert errors, "duplicate FAQ id must be reported"
    assert "duplicate" in str(errors[0]).lower()


def test_missing_de_fails(tmp_path):
    content = tmp_path / "content"
    content.mkdir()
    (content / "faq.yaml").write_text(
        (FIXTURES / "faq_missing_de.yaml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    errors = validate_faq(content, FAQ_SCHEMA)
    assert errors, "an en-only FAQ entry must be reported (de is required)"


def test_absent_faq_file_is_an_error(tmp_path):
    content = tmp_path / "content"
    content.mkdir()
    errors = validate_faq(content, FAQ_SCHEMA)
    assert errors, "faq.yaml is a required content file"
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_faq_schema.py -v`
Expected: FAIL with `ImportError: cannot import name 'validate_faq'`.

- [ ] **Step 3: Write the schema**

Create `schema/faq.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Jin-Ho Lee CV FAQ schema",
  "$defs": {
    "BilingualString": {
      "type": "object",
      "properties": {
        "en": { "type": "string", "minLength": 1 },
        "de": { "type": "string", "minLength": 1 }
      },
      "required": ["en", "de"],
      "additionalProperties": false
    },
    "faq": {
      "type": "object",
      "properties": {
        "faqs": {
          "type": "array",
          "minItems": 1,
          "items": {
            "type": "object",
            "properties": {
              "id": { "type": "string", "pattern": "^[a-z][a-z0-9-]*$" },
              "question": { "$ref": "#/$defs/BilingualString" },
              "answer": { "$ref": "#/$defs/BilingualString" }
            },
            "required": ["id", "question", "answer"],
            "additionalProperties": false
          }
        }
      },
      "required": ["faqs"],
      "additionalProperties": false
    }
  }
}
```

- [ ] **Step 4: Write the invalid fixtures**

Create `tests/fixtures/invalid_yaml/faq_duplicate_id.yaml`:

```yaml
faqs:
  - id: what-does-he-do
    question: { en: "Q1?", de: "F1?" }
    answer: { en: "A1.", de: "A1." }
  - id: what-does-he-do
    question: { en: "Q2?", de: "F2?" }
    answer: { en: "A2.", de: "A2." }
```

Create `tests/fixtures/invalid_yaml/faq_missing_de.yaml`:

```yaml
faqs:
  - id: english-only
    question: { en: "Q?", de: "F?" }
    answer: { en: "A." }
```

- [ ] **Step 5: Implement `validate_faq` and wire it into the tree validation**

In `scripts/validate.py`, add after `validate_master_cv`:

```python
def validate_faq(content_dir: Path, schema_path: Path) -> list[FileError]:
    """Validate content/faq.yaml: schema-valid, bilingual, unique ids.

    faq.yaml is a REQUIRED content file (Phase 14) - absence is an error, not a skip.
    """
    path = content_dir / "faq.yaml"
    if not path.exists():
        return [FileError(path, "faq.yaml missing")]
    try:
        data = _load_yaml(path)
        validator = _validator_for("faq", schema_path)
        schema_errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
        if schema_errors:
            joined = "; ".join(
                f"{'.'.join(str(p) for p in e.path) or '<root>'}: {e.message}"
                for e in schema_errors
            )
            return [FileError(path, joined)]
    except Exception as e:  # malformed YAML
        return [FileError(path, str(e))]

    ids = [entry["id"] for entry in data["faqs"]]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        return [FileError(path, f"duplicate FAQ id(s): {dupes}")]
    return []
```

In `main()`, after the `master_cv` block and before the warnings loop:

```python
    faq_schema = repo_root / "schema" / "faq.schema.json"
    errors.extend(validate_faq(content_dir, faq_schema))
```

- [ ] **Step 6: Seed the FAQ content**

Create `content/faq.yaml`. Every answer below is grounded in existing `content/` facts (experience.yaml, education.yaml, projects/, publications.bib, personal.yaml). Answers are written to be liftable: self-contained, subject-first, no pronouns depending on the question.

```yaml
# Curated FAQ for answer engines (Phase 14, issue #113).
#
# GROUNDING RULE: every answer must be derivable from content/ facts alone.
# The master-cv/ overlay is deliberately twin-exclusive - never source an answer
# from it. If an answer needs a fact the CV does not carry, add the fact to
# content/ first, or leave the question to the digital twin.
#
# Refresh manually when the /twin-insights dashboard surfaces new question themes.
faqs:
  - id: who-is-jin-ho-lee
    question:
      en: "Who is Jin-Ho Lee?"
      de: "Wer ist Jin-Ho Lee?"
    answer:
      en: "Jin-Ho Lee is a bioinformatics and data science professional based in Mannheim, Germany. He engineers in-silico pipelines for HLA typing and neoantigen discovery from cancer-patient NGS and RNA-Seq data, and builds production machine learning on Google Cloud. He holds an M.Sc. in Molecular Biotechnology from Heidelberg University and has 10+ peer-reviewed publications."
      de: "Jin-Ho Lee ist Bioinformatiker und Data Scientist mit Sitz in Mannheim. Er entwickelt In-silico-Pipelines zur HLA-Typisierung und Neoantigen-Identifizierung aus NGS- und RNA-Seq-Daten von Krebspatienten und baut produktives Machine Learning auf der Google Cloud. Er hat einen M.Sc. in Molekularer Biotechnologie der Universität Heidelberg und 10+ peer-reviewed Publikationen."

  - id: what-is-his-background
    question:
      en: "What is Jin-Ho Lee's professional background?"
      de: "Welchen beruflichen Hintergrund hat Jin-Ho Lee?"
    answer:
      en: "Jin-Ho Lee spent eight years in doctoral and post-graduate research across FZ Jülich, KIP, NCT, SNU and DKFZ, working on cancer genomics and super-resolution microscopy. He then moved to industry as a data science coach at neuefische and a consultant and lead business functional analyst for an international bank, and now works independently on ML/AI engineering and open-source tooling."
      de: "Jin-Ho Lee forschte acht Jahre als Doktorand und postgraduierter Forscher an FZ Jülich, KIP, NCT, SNU und DKFZ zu Krebsgenomik und hochauflösender Mikroskopie. Anschließend wechselte er in die Industrie als Data-Science-Coach bei neuefische und als Berater und Lead Business Functional Analyst für eine internationale Bank; heute arbeitet er unabhängig an ML/AI-Engineering und Open-Source-Tooling."

  - id: what-are-his-skills
    question:
      en: "What technical skills does Jin-Ho Lee have?"
      de: "Welche technischen Fähigkeiten hat Jin-Ho Lee?"
    answer:
      en: "Jin-Ho Lee works in Python, SQL and R, with machine learning in PyTorch and TensorFlow, bioinformatics pipelines in Snakemake, and cloud data engineering on Google Cloud including BigQuery and BigQueryML. His domain expertise spans cancer genomics, NGS and RNA-Seq analysis, HLA typing, neoantigen discovery, and spatial point-pattern analysis."
      de: "Jin-Ho Lee arbeitet mit Python, SQL und R, mit Machine Learning in PyTorch und TensorFlow, Bioinformatik-Pipelines in Snakemake sowie Cloud Data Engineering auf der Google Cloud inklusive BigQuery und BigQueryML. Seine Fachexpertise umfasst Krebsgenomik, NGS- und RNA-Seq-Analyse, HLA-Typisierung, Neoantigen-Identifizierung und räumliche Punktmusteranalyse."

  - id: what-has-he-published
    question:
      en: "What has Jin-Ho Lee published?"
      de: "Was hat Jin-Ho Lee publiziert?"
    answer:
      en: "Jin-Ho Lee has 10+ peer-reviewed publications, including first-author and shared-first-author papers, in radiation biophysics and super-resolution imaging of DNA-damage repair and chromatin architecture. The full list with citation counts is available via his ORCID record (0009-0001-8784-1771) and Google Scholar profile."
      de: "Jin-Ho Lee hat 10+ peer-reviewed Publikationen, darunter Arbeiten als Erstautor und mit geteilter Erstautorschaft, in der Strahlenbiophysik und der hochauflösenden Bildgebung von DNA-Schadensreparatur und Chromatin-Architektur. Die vollständige Liste mit Zitationszahlen ist über seinen ORCID-Eintrag (0009-0001-8784-1771) und sein Google-Scholar-Profil verfügbar."

  - id: what-does-he-work-on-now
    question:
      en: "What is Jin-Ho Lee working on now?"
      de: "Woran arbeitet Jin-Ho Lee derzeit?"
    answer:
      en: "Jin-Ho Lee currently works independently on agentic AI systems - LLM agents with tool use, planning, routing, multi-agent orchestration and persistent memory - alongside open-source Claude Code tooling, skeleton-based action recognition in computer vision, and a reproducible Snakemake splice-neoepitope discovery pipeline with AlphaFold2 structural validation."
      de: "Jin-Ho Lee arbeitet derzeit unabhängig an agentischen KI-Systemen - LLM-Agenten mit Tool-Nutzung, Planung, Routing, Multi-Agenten-Orchestrierung und persistentem Speicher - sowie an Open-Source-Tooling für Claude Code, skelettbasierter Action Recognition in der Computer Vision und einer reproduzierbaren Snakemake-Pipeline zur Splice-Neoepitop-Identifizierung mit struktureller Validierung via AlphaFold2."

  - id: is-he-available-for-work
    question:
      en: "Is Jin-Ho Lee available for new opportunities?"
      de: "Ist Jin-Ho Lee für neue Positionen verfügbar?"
    answer:
      en: "Jin-Ho Lee is open to roles in bioinformatics, computational biology and data science, based in Mannheim, Germany. The fastest way to reach him is the contact form on this site or the digital twin chat, which answers detailed questions about his experience and can pass on a message."
      de: "Jin-Ho Lee ist offen für Positionen in Bioinformatik, Computational Biology und Data Science, mit Sitz in Mannheim. Der schnellste Weg, ihn zu erreichen, ist das Kontaktformular auf dieser Seite oder der Digital-Twin-Chat, der detaillierte Fragen zu seiner Erfahrung beantwortet und eine Nachricht weiterleiten kann."
```

**After writing:** ask Jin-Ho to open the Access-gated `/twin-insights` dashboard and confirm whether the real question log suggests replacing or adding entries. This seed set is grounded and shippable on its own; the dashboard pass is a refinement, not a blocker.

- [ ] **Step 7: Run the tests to verify they pass**

Run: `uv run pytest tests/test_faq_schema.py -v && just validate`
Expected: PASS; `just validate` prints `OK: all content files validate`.

- [ ] **Step 8: Green gate and commit**

```bash
just validate && just test && just lint && just fmt
git add content/faq.yaml schema/faq.schema.json scripts/validate.py tests/test_faq_schema.py tests/fixtures/invalid_yaml/
git commit -m "aeo(#113): add schema-validated bilingual FAQ content"
```

---

### Task 3: FAQ + answer block through the data pipeline

Loads `faq.yaml` into the content tree and adds the `answer_block` profile field, so both reach `web/src/data/content.{en,de}.json`.

**Files:**
- Modify: `scripts/content_loader.py:115-145` (add the `faq` key)
- Modify: `schema/cv.schema.json:104-129` (`profile` def: add `answer_block`)
- Modify: `content/profile.en.yaml`, `content/profile.de.yaml` (add `answer_block`)
- Modify: `web/src/types/content.ts` (add `FaqEntry`, extend `Profile`, `ContentData`, `Labels`)
- Test: `tests/test_content_loader.py`, `tests/test_render_web_data.py`

**Interfaces:**
- Consumes: `content/faq.yaml` from Task 2.
- Produces:
  - `load_content(...)["faq"]` → `{"faqs": [...]}`; after `resolve_langstrings(lang)` each entry is `{"id": str, "question": str, "answer": str}`.
  - `load_content(...)["profile"]["answer_block"]` → `str` (already language-resolved: it lives in the per-language `profile.{lang}.yaml`, so it is a plain string, NOT a langmap).
  - TS: `interface FaqEntry { id: string; question: string; answer: string }`; `ContentData.faq: { faqs: FaqEntry[] }`; `Profile.answer_block?: string`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_content_loader.py`:

```python
def test_faq_is_loaded_and_resolves_to_language(content_dir):
    from scripts.content_loader import load_content
    from scripts.langstring import resolve_langstrings

    en = resolve_langstrings(load_content(content_dir, lang="en"), lang="en")
    de = resolve_langstrings(load_content(content_dir, lang="de"), lang="de")

    en_faqs = en["faq"]["faqs"]
    de_faqs = de["faq"]["faqs"]
    assert len(en_faqs) == len(de_faqs) >= 5
    assert isinstance(en_faqs[0]["question"], str)
    assert isinstance(en_faqs[0]["answer"], str)
    # Same ids, in the same order, across languages.
    assert [f["id"] for f in en_faqs] == [f["id"] for f in de_faqs]
    # The DE text is genuinely German, not an EN fallback.
    assert en_faqs[0]["question"] != de_faqs[0]["question"]


def test_profile_answer_block_is_a_plain_string(content_dir):
    from scripts.content_loader import load_content

    for lang in ("en", "de"):
        profile = load_content(content_dir, lang=lang)["profile"]
        block = profile["answer_block"]
        assert isinstance(block, str) and block.strip()
        words = len(block.split())
        assert 35 <= words <= 70, f"{lang} answer_block is {words} words; target 40-60"
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_content_loader.py -v -k "faq or answer_block"`
Expected: FAIL with `KeyError: 'faq'`.

- [ ] **Step 3: Load the FAQ in content_loader**

In `scripts/content_loader.py`, inside the dict built by `load_content`, next to the other `_load_yaml` entries (keep it adjacent to `"labels"`):

```python
        "faq": _load_yaml(content_dir / "faq.yaml"),
```

- [ ] **Step 4: Add `answer_block` to the profile schema**

In `schema/cv.schema.json`, in the `profile` `$defs` `properties` block, after `"tagline"`:

```json
        "answer_block": { "type": "string", "minLength": 1 },
```

Leave `required` as `["paragraphs"]` - the field is optional in the schema (a renderer must degrade gracefully), even though both real profile files carry it.

- [ ] **Step 5: Author the answer blocks**

In `content/profile.en.yaml`, add as the FIRST key of the file (before `tagline`):

```yaml
answer_block: "Jin-Ho Lee is a bioinformatics and data science professional in Mannheim, Germany. He builds in-silico pipelines for HLA typing and neoantigen discovery from cancer-patient NGS and RNA-Seq data, and ships production machine learning on Google Cloud. He holds an M.Sc. from Heidelberg University and has 10+ peer-reviewed publications."
```

In `content/profile.de.yaml`, likewise as the FIRST key:

```yaml
answer_block: "Jin-Ho Lee ist Bioinformatiker und Data Scientist in Mannheim. Er entwickelt In-silico-Pipelines zur HLA-Typisierung und Neoantigen-Identifizierung aus NGS- und RNA-Seq-Daten von Krebspatienten und liefert produktives Machine Learning auf der Google Cloud. Er hat einen M.Sc. der Universität Heidelberg und 10+ peer-reviewed Publikationen."
```

Both are within the 40-60 word target the test enforces. Verify with `python3 -c "print(len(open('content/profile.en.yaml').readline().split()))"` if unsure, or just let the test tell you.

- [ ] **Step 6: Extend the TypeScript types**

In `web/src/types/content.ts`:

```typescript
export interface Profile {
  tagline: string;
  answer_block?: string;
  paragraphs: string[];
}

export interface FaqEntry {
  id: string;
  question: string;
  answer: string;
}
export interface Faq {
  faqs: FaqEntry[];
}
```

Extend `Labels.sections` with `faq: string;` and `ContentData` with `faq: Faq;`.

- [ ] **Step 7: Run the tests to verify they pass**

Run: `uv run pytest tests/test_content_loader.py tests/test_render_web_data.py -v`
Expected: PASS.

- [ ] **Step 8: Regenerate snapshots and eyeball the diff**

Run: `just snapshots-update && git diff tests/__snapshots__/`
Expected: `content.en.json` / `content.de.json` gain a `faq` block and `profile.answer_block`. `cv-*.txt`, `resume.json`, `person.jsonld`, `llms.txt` MUST be unchanged - those renderers build explicit structures and ignore unknown content keys. **If any of them changed, stop:** a non-web renderer is leaking FAQ content, which violates the design (FAQ is web-surface only). Fix the renderer, do not accept the snapshot.

- [ ] **Step 9: Green gate and commit**

```bash
just validate && just test && just lint && just fmt
git add scripts/content_loader.py schema/cv.schema.json content/profile.en.yaml content/profile.de.yaml web/src/types/content.ts tests/
git commit -m "aeo(#113): flow FAQ + answer block through the content pipeline"
```

---

### Task 4: FAQ section + FAQPage JSON-LD on the site

Renders the FAQ as a collapsible section on both index pages, with the `FAQPage` structured data generated from the same data so text and schema cannot drift.

**Files:**
- Modify: `content/labels.yaml` (add `sections.faq`)
- Create: `web/src/components/FaqSection.astro`
- Modify: `web/src/pages/index.astro`, `web/src/pages/de/index.astro`
- Create: `tests/test_faq_jsonld.py`

**Interfaces:**
- Consumes: `ContentData.faq` and `Labels.sections.faq` from Task 3.
- Produces: built HTML containing `data-faq-section` and a `<script type="application/ld+json">` block whose JSON has `"@type": "FAQPage"`.

- [ ] **Step 1: Add the section label**

In `content/labels.yaml`, in the `sections:` block after `volunteer:`:

```yaml
  faq:               { en: "FAQ",               de: "FAQ" }
```

Then regenerate the labels-bearing snapshots later in Step 6; `just validate` must stay green now.

- [ ] **Step 2: Write the failing test**

Create `tests/test_faq_jsonld.py`:

```python
"""The built site must carry a FAQPage JSON-LD block matching the visible FAQ (issue #113).

Skip-guarded locally (needs a web build); the CI `web-guard` job builds web/dist first.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from ruamel.yaml import YAML

REPO_ROOT = Path(__file__).resolve().parent.parent
PAGES = {
    "en": REPO_ROOT / "web" / "dist" / "index.html",
    "de": REPO_ROOT / "web" / "dist" / "de" / "index.html",
}

pytestmark = pytest.mark.skipif(
    not all(p.exists() for p in PAGES.values()),
    reason="needs a built site (run: just web-build)",
)


def _faq_page_block(html: str) -> dict:
    """Extract the single ld+json script whose payload is a FAQPage."""
    for raw in re.findall(
        r'<script type="application/ld\+json"[^>]*>(.*?)</script>', html, flags=re.S
    ):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("@type") == "FAQPage":
            return data
    raise AssertionError("no FAQPage JSON-LD block found in the page")


@pytest.fixture(scope="module")
def faq_yaml() -> dict:
    return YAML(typ="safe").load(
        (REPO_ROOT / "content" / "faq.yaml").read_text(encoding="utf-8")
    )


@pytest.mark.parametrize("lang", ["en", "de"])
def test_faq_page_jsonld_matches_content(lang, faq_yaml):
    html = PAGES[lang].read_text(encoding="utf-8")
    block = _faq_page_block(html)

    assert block["@context"] == "https://schema.org"
    questions = block["mainEntity"]
    expected = faq_yaml["faqs"]
    assert len(questions) == len(expected)

    for q, source in zip(questions, expected):
        assert q["@type"] == "Question"
        assert q["name"] == source["question"][lang]
        assert q["acceptedAnswer"]["@type"] == "Answer"
        assert q["acceptedAnswer"]["text"] == source["answer"][lang]


@pytest.mark.parametrize("lang", ["en", "de"])
def test_faq_text_is_in_static_html(lang, faq_yaml):
    """The visible FAQ must be in the HTML itself, not injected by JS - crawlers do not run JS."""
    html = PAGES[lang].read_text(encoding="utf-8")
    assert "data-faq-section" in html
    for entry in faq_yaml["faqs"]:
        assert entry["question"][lang] in html, f"FAQ question {entry['id']} missing from HTML"
        assert entry["answer"][lang] in html, f"FAQ answer {entry['id']} missing from HTML"
```

- [ ] **Step 3: Run to verify it fails**

Run: `just web-build && uv run pytest tests/test_faq_jsonld.py -v`
Expected: FAIL - `AssertionError: no FAQPage JSON-LD block found in the page`.

- [ ] **Step 4: Write the component**

Create `web/src/components/FaqSection.astro`:

```astro
---
import type { Faq, Labels } from "../types/content";

interface Props {
  faq: Faq;
  labels: Labels;
}

const { faq, labels } = Astro.props;

// FAQPage structured data built from the SAME data the section renders below,
// so the visible text and the schema can never drift apart.
const faqPage = {
  "@context": "https://schema.org",
  "@type": "FAQPage",
  mainEntity: faq.faqs.map((entry) => ({
    "@type": "Question",
    name: entry.question,
    acceptedAnswer: { "@type": "Answer", text: entry.answer },
  })),
};
---
<section id="faq" class="py-6" data-faq-section data-reveal>
  <h2 class="eyebrow mb-3">{labels.sections.faq}</h2>
  <div class="flex flex-col gap-2">
    {faq.faqs.map((entry) => (
      <details
        id={`faq-${entry.id}`}
        class="group rounded-lg border border-[var(--border)] bg-[var(--surface)] px-4 py-3"
      >
        <summary
          class="cursor-pointer list-none font-medium text-[var(--text)] marker:content-none
                 flex items-center justify-between gap-3"
        >
          <span>{entry.question}</span>
          <span
            aria-hidden="true"
            class="flex-shrink-0 text-[var(--muted)] transition-transform group-open:rotate-45"
          >+</span>
        </summary>
        <p class="mt-3 leading-relaxed text-[var(--muted)]">{entry.answer}</p>
      </details>
    ))}
  </div>
  <script type="application/ld+json" set:html={JSON.stringify(faqPage)} />
</section>
```

Note: the answer `<p>` is inside `<details>` and therefore present in the served HTML whether or not the element is open - collapsed content is still parsed HTML, which is exactly what a non-JS crawler reads.

- [ ] **Step 5: Mount it on both index pages**

In `web/src/pages/index.astro`, add the import alongside the others:

```astro
import FaqSection from "../components/FaqSection.astro";
```

and place the section after the closing `</div>` of the main content grid, immediately before `</BaseLayout>`:

```astro
  <FaqSection faq={data.faq} labels={data.labels} />
```

Do the same in `web/src/pages/de/index.astro`, with the import path `"../../components/FaqSection.astro"`.

- [ ] **Step 6: Rebuild and run the tests**

Run: `just web-build && uv run pytest tests/test_faq_jsonld.py -v`
Expected: PASS (4 tests: JSON-LD match + static text, EN and DE).

- [ ] **Step 7: Regenerate snapshots and eyeball the diff**

Run: `just snapshots-update && git diff tests/__snapshots__/`
Expected: the new `labels.sections.faq` key appears in the web content JSON snapshots. Non-web renderer snapshots that carry labels may also gain the key - that is fine (it is a label, not FAQ body text). FAQ questions/answers must NOT appear in `cv-*.txt`, `resume.json`, or `person.jsonld`.

- [ ] **Step 8: Visual check**

Run `just web-dev`, open the local site, and confirm the FAQ section renders correctly in BOTH themes (dark and light) and both languages: the `<details>` rows are readable, the `+` marker rotates on open, spacing matches neighbouring sections, and nothing overflows on a narrow viewport. Take a screenshot per the repo's usual Playwright loop. Fix any visual mismatch before committing.

- [ ] **Step 9: Green gate and commit**

```bash
just validate && just test && just lint && just fmt
git add content/labels.yaml web/src/components/FaqSection.astro web/src/pages/index.astro web/src/pages/de/index.astro tests/test_faq_jsonld.py tests/__snapshots__/
git commit -m "aeo(#113): render FAQ section with FAQPage JSON-LD on both index pages"
```

---

### Task 5: Answer block on the profile section

Front-loads the profile with the liftable answer block from Task 3.

**Files:**
- Modify: `web/src/components/ProfileSection.astro:34-39`
- Modify: `.github/workflows/pages.yml` (smoke-check greps)
- Test: covered by `test_answer_block_is_front_loaded_in_static_html` in Task 6's `tests/test_static_facts.py`, plus the build-time grep in Step 2 here.

**Interfaces:**
- Consumes: `Profile.answer_block` from Task 3.
- Produces: built HTML containing `data-cv-field="answer-block"`.

- [ ] **Step 1: Render the answer block**

In `web/src/components/ProfileSection.astro`, inside the `<div>` that holds the prose, BEFORE the tagline `<p>`:

```astro
      {profile.answer_block && (
        <p
          class="text-base leading-relaxed text-[var(--text)]"
          data-cv-field="answer-block"
        >{profile.answer_block}</p>
      )}
```

Keep the existing tagline and paragraph markup unchanged, but change the tagline's `class` margin so the stack still breathes: `class="mt-3 text-lg font-medium text-[var(--text)]"`.

The `answer_block &&` guard honours the schema (the field is optional): absent → nothing renders, no crash.

- [ ] **Step 2: Rebuild and verify the block is in static HTML**

Run:
```bash
just web-build
grep -c 'data-cv-field="answer-block"' web/dist/index.html web/dist/de/index.html
```
Expected: `1` for each page.

- [ ] **Step 3: Add the Pages smoke-check greps**

In `.github/workflows/pages.yml`, in the `Smoke-check build outputs` step, inside the existing `for page in web/dist/index.html web/dist/de/index.html; do` loop that checks Phase 9 elements, add:

```bash
            grep -q 'data-faq-section' "$page" || (echo "FAQ section missing in $page" && exit 1)
            grep -q '"@type":"FAQPage"' "$page" || grep -q '"@type": "FAQPage"' "$page" || (echo "FAQPage JSON-LD missing in $page" && exit 1)
            grep -q 'data-cv-field="answer-block"' "$page" || (echo "Answer block missing in $page" && exit 1)
```

(The double `grep -q` on FAQPage tolerates Astro minifying the JSON with or without a space after the colon.)

- [ ] **Step 4: Visual check**

Run `just web-dev` and confirm the profile section reads well with the new opening paragraph: the answer block sits above the tagline, the visual hierarchy still puts the tagline forward as the styled line, and both themes look right. Screenshot it.

- [ ] **Step 5: Green gate and commit**

```bash
just validate && just test && just lint && just fmt
git add web/src/components/ProfileSection.astro .github/workflows/pages.yml
git commit -m "aeo(#113): front-load the profile with an answer-shaped block"
```

---

### Task 6: Static-HTML facts audit + CI guard

Turns "the public CV is crawler-readable" from an assumption into a CI-verified property, in both directions: public facts present, twin-exclusive tier absent.

**Files:**
- Create: `tests/test_static_facts.py`
- Modify: `.github/workflows/ci.yml` (new `web-guard` job)
- Modify: `justfile` (a `web-guard` recipe for local runs)

**Interfaces:**
- Consumes: the built `web/dist` and `content/` (Tasks 2-5).
- Produces: nothing consumed downstream.

- [ ] **Step 1: Do the one-off audit**

Run:
```bash
just web-build
```
Then read `web/dist/index.html` and confirm, by eye, that each of these appears as literal text in the raw HTML (NOT injected by a client script): full name, headline, every `experience[].org.name`, every `education[].institution` and `degree.en`, every selected project title, and at least one publication title. Note any fact that is missing or JS-only. If something is JS-only, fix the component to render it server-side before writing the test - the test encodes the fixed state, it does not paper over a gap.

- [ ] **Step 2: Write the guard test**

Create `tests/test_static_facts.py`:

```python
"""Static-HTML facts guard (Phase 14, issue #113).

AI crawlers do not execute JavaScript (Vercel/MERJ, 500M fetches). Two properties:

  1. PUBLIC TIER PRESENT  - the core content/ facts are in the raw served HTML.
  2. DEEP TIER ABSENT     - the deliberately twin-exclusive master-cv/ overlay is not.

Property 2 is proven against the synthetic master-cv.example/ overlay: the web
renderer must ignore MASTER_CV_DIR entirely, so pointing it at the example and
re-rendering must not put any overlay-only string on the public surface.

Skip-guarded locally (needs a web build); the CI `web-guard` job builds web/dist first.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from ruamel.yaml import YAML

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = REPO_ROOT / "content"
EXAMPLE_OVERLAY = REPO_ROOT / "master-cv.example"
INDEX_EN = REPO_ROOT / "web" / "dist" / "index.html"
INDEX_DE = REPO_ROOT / "web" / "dist" / "de" / "index.html"

pytestmark = pytest.mark.skipif(
    not (INDEX_EN.exists() and INDEX_DE.exists()),
    reason="needs a built site (run: just web-build)",
)

yaml = YAML(typ="safe")


def _load(name: str):
    return yaml.load((CONTENT_DIR / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def html_en() -> str:
    return INDEX_EN.read_text(encoding="utf-8")


def test_name_and_headline_in_static_html(html_en):
    personal = _load("personal.yaml")
    assert f"{personal['name']['given']} {personal['name']['family']}" in html_en
    assert personal["headline"]["en"] in html_en


def test_every_employer_in_static_html(html_en):
    for entry in _load("experience.yaml"):
        org = entry["org"]["name"]
        assert org in html_en, f"employer {org!r} is not in the raw HTML (JS-only?)"


def test_every_degree_and_institution_in_static_html(html_en):
    for entry in _load("education.yaml"):
        assert entry["institution"] in html_en
        assert entry["degree"]["en"] in html_en


def test_answer_block_is_front_loaded_in_static_html(html_en):
    """The liftable answer block must be server-rendered, not JS-injected."""
    block = yaml.load((CONTENT_DIR / "profile.en.yaml").read_text(encoding="utf-8"))["answer_block"]
    assert 'data-cv-field="answer-block"' in html_en
    assert block in html_en


def test_selected_project_titles_in_static_html(html_en):
    for pid in _load("selected_projects.yaml")["bridge"]:
        title = yaml.load(
            (CONTENT_DIR / "projects" / f"{pid}.en.yaml").read_text(encoding="utf-8")
        )["title"]
        assert title in html_en, f"project {pid} title {title!r} is not in the raw HTML"


def test_person_jsonld_is_served_and_parses(html_en):
    """The Person graph must be inline in the page, not fetched at runtime."""
    assert "application/ld+json" in html_en
    jsonld = json.loads((REPO_ROOT / "web" / "public" / "person.jsonld").read_text("utf-8"))
    person = next(n for n in jsonld["@graph"] if n["@type"] == "Person")
    assert person["sameAs"], "Person.sameAs must carry the external entity anchors"


def _overlay_sentinels() -> list[str]:
    """Distinctive strings that exist ONLY in the synthetic overlay, never in content/."""
    inventory = yaml.load((EXAMPLE_OVERLAY / "inventory.yaml").read_text(encoding="utf-8"))
    values = [v for values in inventory.values() for v in values]
    return [v for v in values if v.startswith("Example") or v == "Pseudocode"]


@pytest.mark.parametrize("page", [INDEX_EN, INDEX_DE], ids=["en", "de"])
def test_deep_tier_stays_off_the_public_surface(page):
    """master-cv/ is twin-exclusive by design - none of it may reach the built site."""
    html = page.read_text(encoding="utf-8")
    sentinels = _overlay_sentinels()
    assert sentinels, "the example overlay yielded no sentinels; the fixture changed"
    for sentinel in sentinels:
        assert sentinel not in html, (
            f"overlay-only string {sentinel!r} reached the public site - "
            "the deep tier must stay twin-exclusive"
        )
```

- [ ] **Step 3: Run to verify it passes on a good build (and would fail on a bad one)**

Run: `just web-build && uv run pytest tests/test_static_facts.py -v`
Expected: PASS.

Then prove the guard bites: temporarily edit `web/src/components/ExperienceSection.astro` to render an employer name only inside a `<script>`-driven placeholder (or simply comment out the org-name output), rebuild, and confirm `test_every_employer_in_static_html` FAILS. Revert the edit immediately and rebuild.

- [ ] **Step 4: Add the local recipe**

In `justfile`, next to the other web recipes:

```make
# Build the site and assert the public CV facts are crawler-readable in static HTML
web-guard:
    just web-build
    uv run pytest tests/test_faq_jsonld.py tests/test_static_facts.py -v
```

- [ ] **Step 5: Add the CI job**

In `.github/workflows/ci.yml`, after the `ats-guard` job:

```yaml
  web-guard:
    needs: validate
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

      - name: Render web JSON
        run: uv run python -m scripts.render_web_data

      - name: Render JSON-LD into web/public/
        run: |
          uv run python -m scripts.render_jsonld
          mkdir -p web/public
          cp dist/person.jsonld web/public/person.jsonld

      - name: Set up Node
        uses: actions/setup-node@v6
        with:
          node-version-file: .nvmrc

      - name: Set up pnpm
        uses: pnpm/action-setup@v6
        with:
          version: 10

      - name: Install web deps
        run: pnpm --dir web install --frozen-lockfile

      - name: Build site
        run: pnpm --dir web build

      - name: Run static-HTML facts + FAQPage guards
        run: uv run pytest tests/test_static_facts.py tests/test_faq_jsonld.py -v
```

This job runs on every PR (unlike `pages.yml`, which is main-only). It does NOT set the twin/analytics env vars - the guard is about CV facts, and those components render nothing without their vars, which is the correct graceful default.

- [ ] **Step 6: Green gate and commit**

```bash
just validate && just test && just lint && just fmt
git add tests/test_static_facts.py .github/workflows/ci.yml justfile
git commit -m "aeo(#113): guard the public CV facts in static HTML on every PR"
```

---

### Task 7: Wikidata entity runbook

The Wikidata item is created off-repo, from Jin-Ho's own account. This task commits the runbook that makes that a repeatable, privacy-bounded procedure, and wires the Q-ID in once the item exists.

**Files:**
- Create: `docs/runbooks/2026-07-wikidata-entity.md`
- Modify (only after the item exists): `content/personal.yaml`

**Interfaces:**
- Consumes: the `wikidata` mapping already added to `_network_for` in Task 1.
- Produces: `personal["links"]["wikidata"]` → flows into `sameAs` automatically.

- [ ] **Step 1: Write the runbook**

Create `docs/runbooks/2026-07-wikidata-entity.md`:

```markdown
# Runbook: Wikidata entity for Jin-Ho Lee

Phase 14 (issue #113). A Wikidata item is the strongest entity anchor for a common-ish name:
it feeds Google's Knowledge Graph and is read directly by LLMs.
The item is created by Jin-Ho's own account, off-repo. This runbook makes that repeatable.

## Privacy boundary (do not cross)

INCLUDE only the professional core:

- instance of (P31) → human (Q5)
- occupation (P106) → bioinformatician / data scientist
- field of work (P101) → bioinformatics, data science
- ORCID iD (P496) → 0009-0001-8784-1771
- GitHub username (P2037) → Jin-HoMLee
- official website (P856) → https://jinholee.is-a.dev/
- country of citizenship (P27)

EXCLUDE, deliberately:

- date of birth
- employer (P108)
- educated at (P69)
- residence, any address, phone number

This is a considered privacy decision, not an oversight.
A future session must not "helpfully" enrich the item with these.

## Notability

Wikidata items for people need to be verifiable against published sources.
The anchor here is the peer-reviewed publication record (DOI-bearing, in `content/publications.bib`)
plus the ORCID record. Every statement added should carry a reference to a published source
(the ORCID record, a paper's DOI, or the official website for P856).
If the item is challenged for notability, the publication record is the defence - do not pad it.

## Steps

1. Log in to https://www.wikidata.org with Jin-Ho's own account (create one if needed).
2. Search first: confirm no item already exists for this Jin-Ho Lee. Several other people share the name -
   check ORCID / affiliation before concluding.
3. Create the item: label "Jin-Ho Lee", description "bioinformatician and data scientist"
   (English), plus a German label/description.
4. Add each statement from the INCLUDE list above, attaching a reference to each.
5. Note the Q-ID (e.g. `Q12345678`).
6. Wire it into the CV (see next section).

## Wiring the Q-ID into the CV

In `content/personal.yaml`, inside `links:`:

    wikidata: "https://www.wikidata.org/wiki/Q<ID>"

`scripts/render_jsonld._same_as` picks up every link key except `website`, so the Wikidata URL
flows into the Person's `sameAs` automatically. `scripts/render_jsonresume._network_for` already
maps `wikidata` → "Wikidata".

Then:

    just validate && just test
    just snapshots-update   # the new URL appears in resume.json / person.jsonld / cv-*.txt
    git diff tests/__snapshots__/   # eyeball, then commit

## Google Scholar

Already wired (Task 1): `https://scholar.google.com/citations?user=QPyM-WoAAAAJ`.
Reference it from the Wikidata item too, if Wikidata's Google Scholar author ID property (P1960) applies.
```

- [ ] **Step 2: Commit the runbook**

```bash
git add docs/runbooks/2026-07-wikidata-entity.md
git commit -m "aeo(#113): add the Wikidata entity runbook"
```

- [ ] **Step 3: Hand the runbook to Jin-Ho**

Tell Jin-Ho the runbook is ready and that creating the item is a manual step on his own Wikidata account. It is NOT a blocker for merging Phase 14: every other item ships without it, and the Q-ID lands in a small follow-up commit (or a follow-up issue) when the item exists.

- [ ] **Step 4 (only once the Q-ID exists): wire it in**

Follow the runbook's "Wiring the Q-ID into the CV" section: add the link, run the green gate, regenerate snapshots, eyeball the diff, commit as `aeo(#113): add the Wikidata entity anchor`.

---

### Task 8: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md` (Phasing table, Layout, Commands, Conventions, files-to-read list)

- [ ] **Step 1: Add the Phase 14 row to the Phasing table**

After the Phase 13 row:

```markdown
| 14 | AEO entity presence (Wikidata + Google Scholar anchors · bilingual FAQ + FAQPage JSON-LD · answer block · static-HTML-facts CI guard) | ✅ Done (merged 2026-07-XX, `--no-ff`, PR #XXX); Wikidata item created off-repo per `docs/runbooks/2026-07-wikidata-entity.md` |
```

Fill in the real date / PR number at merge time.

- [ ] **Step 2: Update Layout**

Add to the `content/` line's neighbourhood and the schema list:

```
schema/faq.schema.json          FAQ validation (bilingual, unique ids)
docs/runbooks/                  operational runbooks (Wikidata entity creation)
```

- [ ] **Step 3: Update Commands**

```bash
just web-guard         # build the site + assert the public CV facts are crawler-readable in static HTML
```

- [ ] **Step 4: Add the convention**

Under Conventions, after the `llms.txt` bullet (which already documents what does NOT work):

```markdown
- **AEO: the public tier must be crawler-readable; the deep tier must not be.** AI crawlers do
  not execute JavaScript, so every `content/` fact the CV wants cited has to be in the served
  HTML - guarded on every PR by the `web-guard` CI job (`tests/test_static_facts.py`), the
  website's answer to the PDF's `ats-guard`. The same test asserts the inverse: no `master-cv/`
  overlay string may reach the public surface. That exclusivity is deliberate - the overlay is
  the twin's alone, and being unable to crawl it is a reason to talk to the twin.
  `content/faq.yaml` (bilingual, schema-validated) drives both the visible FAQ section and the
  `FAQPage` JSON-LD on the index pages, generated from the same data so they cannot drift; FAQ
  answers must be grounded in `content/` facts only, never the overlay. FAQ is a web-surface
  feature: it stays out of the PDF, `resume.json`, `person.jsonld`, `cv-*.txt`, and the twin
  chat context. Entity anchors (`personal.yaml` `links`) flow into JSON-LD `sameAs`
  automatically - adding a link key is all that is needed.
```

- [ ] **Step 5: Add the spec + plan to "Files to read before any phase"**

```markdown
- `docs/superpowers/specs/2026-07-14-phase-14-aeo-entity-presence-design.md` — Phase 14 design spec (AEO entity presence)
- `docs/superpowers/plans/2026-07-14-phase-14-aeo-entity-presence.md` — implementation plan for AEO entity presence (#113)
```

- [ ] **Step 6: Green gate and commit**

```bash
just validate && just test && just lint && just fmt
git add CLAUDE.md
git commit -m "docs(#113): record Phase 14 in the phasing table and conventions"
```

---

## Finishing

Use `superpowers:finishing-a-development-branch`: open the PR against `main`, verify CI is green (including the new `web-guard` job), offer an `@claude review`, then merge with `--no-ff`. The linked branch auto-closes #113 - which is correct here, since the phase merge IS the completion.
