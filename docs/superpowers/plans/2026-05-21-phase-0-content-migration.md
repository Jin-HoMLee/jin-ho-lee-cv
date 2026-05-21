# Phase 0 — Content Migration & Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate all CV content from the source PDF into a validated YAML + BibTeX content tree, with a Python loader that merges public content with a gitignored private overlay.

**Architecture:** Content lives in `content/` (public, YAML + BibTeX) and `content.private/` (gitignored, YAML overlay for PII). A `content_loader` module deep-merges the two into a single Python dict consumed by downstream renderers (not yet built). All YAML is validated against a JSON Schema. Cross-references between `experience.yaml` and `projects/` are checked. The BibTeX file is parsed with `pybtex` and exposed as structured data with custom fields (`type`, `authorship`).

**Tech Stack:** Python 3.12, `uv` for dependency management, `ruamel.yaml` for round-trip YAML, `jsonschema` for validation, `pybtex` for BibTeX parsing, `pytest` for testing, `just` for task running.

**Source material:** Content is migrated from `~/Documents/CV/CV_Bioinformatics/2026-05_CV_Bioinformatics_EA.pdf`. Phase 0 covers **EN only**; German variants are deferred to Phase 2.

**Spec reference:** `docs/superpowers/specs/2026-05-21-codified-cv-design.md`

---

## File Structure

Files created in this plan, grouped by responsibility:

| File | Responsibility |
|---|---|
| `README.md` | Brief project intro + quickstart for `just validate` |
| `.gitignore` | Ignore `content.private/`, `dist*/`, Python/Node caches |
| `pyproject.toml` | Python project config; `uv`-managed deps |
| `justfile` | `just validate`, `just test` commands |
| `schema/cv.schema.json` | JSON Schema for all `content/*.yaml` files |
| `content/personal.yaml` | Name, headline, public socials, photo path |
| `content/profile.en.yaml` | Multi-paragraph profile summary, EN |
| `content/skills.yaml` | Categorized skill labels |
| `content/education.yaml` | Degree entries |
| `content/experience.yaml` | Roles with project cross-refs |
| `content/projects/{L1..L4,D1..D3,C1,C2}.en.yaml` | One file per project, EN |
| `content/languages.yaml` | Spoken languages with proficiency |
| `content/volunteer.yaml` | Volunteer & interests grouped by domain |
| `content/publications.bib` | BibTeX, single source of truth for publications |
| `content.private.example/private.example.yaml` | Committed template showing required private keys |
| `scripts/__init__.py` | Empty marker |
| `scripts/content_loader.py` | Load YAML tree + merge private overlay |
| `scripts/bib_loader.py` | Parse `publications.bib`, expose structured records |
| `scripts/validate.py` | CLI: schema validation + cross-reference check |
| `tests/__init__.py` | Empty marker |
| `tests/conftest.py` | Pytest fixtures (paths to content, fixture loaders) |
| `tests/test_content_loader.py` | Loader + merge tests |
| `tests/test_bib_loader.py` | BibTeX parsing tests |
| `tests/test_validate.py` | Validation suite tests (positive + negative) |
| `tests/fixtures/invalid_yaml/` | Broken YAML files for negative tests |

**Decomposition principles applied:**
- `content_loader`, `bib_loader`, and `validate` are separate modules with one responsibility each.
- The CLI (`validate.py`) is a thin wrapper around the validation logic so the logic itself stays testable in isolation.
- Test fixtures live next to tests, not mixed with real content.

---

## Task 1: Repo skeleton

**Files:**
- Create: `README.md`
- Create: `.gitignore`
- Create: `pyproject.toml`
- Create: `justfile`

- [ ] **Step 1: Create `.gitignore`**

```gitignore
# PII overlay — never committed
content.private/

# Build outputs
dist/
dist-private/

# Python
__pycache__/
*.pyc
.pytest_cache/
.ruff_cache/
.venv/
*.egg-info/

# Node (Phase 3+)
node_modules/

# OS
.DS_Store
```

- [ ] **Step 2: Create `pyproject.toml`**

```toml
[project]
name = "jin-ho-lee-cv"
version = "0.1.0"
description = "Machine-readable, codified CV"
requires-python = ">=3.12"
dependencies = [
    "ruamel.yaml>=0.18",
    "jsonschema>=4.23",
    "pybtex>=0.24",
]

[dependency-groups]
dev = [
    "pytest>=8.3",
    "pytest-cov>=5.0",
    "ruff>=0.7",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]

[tool.ruff]
line-length = 100
target-version = "py312"
```

- [ ] **Step 3: Create `justfile`**

```just
# Run the validation suite
validate:
    uv run python -m scripts.validate

# Run unit tests
test:
    uv run pytest -v

# Run lint
lint:
    uv run ruff check .

# Format
fmt:
    uv run ruff format .
```

- [ ] **Step 4: Create `README.md`**

```markdown
# Jin-Ho Lee — Codified CV

Machine-readable, version-controlled CV. Single source of truth in YAML + BibTeX; renderers produce PDF, website, JSON Resume, JSON-LD, and plain text.

See `docs/superpowers/specs/` for the architectural spec and `docs/superpowers/plans/` for active implementation plans.

## Quickstart

```bash
uv sync
just validate    # check all content is well-formed
just test        # run unit tests
```

## Layout

- `content/` — public source of truth (YAML + BibTeX)
- `content.private/` — gitignored PII overlay (phone, address)
- `schema/cv.schema.json` — JSON Schema for content
- `scripts/` — loader, validator, future renderers
- `tests/` — pytest suite
```

- [ ] **Step 5: Initialize uv project and verify**

Run from repo root (`jin-ho-lee-cv/`):
```bash
uv sync
```
Expected: creates `.venv/` and `uv.lock`. No errors.

- [ ] **Step 6: Commit**

```bash
git add .gitignore pyproject.toml justfile README.md uv.lock
git commit -m "chore: initialize repo skeleton with uv + justfile"
```

---

## Task 2: Pytest scaffolding

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/test_smoke.py`
- Create: `scripts/__init__.py`

- [ ] **Step 1: Create empty package markers**

```bash
touch scripts/__init__.py tests/__init__.py
```

- [ ] **Step 2: Create `tests/conftest.py`**

```python
"""Shared pytest fixtures."""
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
CONTENT_DIR = REPO_ROOT / "content"
SCHEMA_PATH = REPO_ROOT / "schema" / "cv.schema.json"
FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture
def content_dir() -> Path:
    return CONTENT_DIR


@pytest.fixture
def schema_path() -> Path:
    return SCHEMA_PATH


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR
```

- [ ] **Step 3: Write a smoke test**

`tests/test_smoke.py`:
```python
"""Smoke test confirming pytest discovery works."""


def test_pytest_runs():
    assert 1 + 1 == 2
```

- [ ] **Step 4: Run tests, verify passing**

```bash
just test
```
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add tests/ scripts/__init__.py
git commit -m "test: scaffold pytest with shared fixtures"
```

---

## Task 3: JSON Schema for CV content

**Files:**
- Create: `schema/cv.schema.json`

**Purpose:** Defines the shape of every `content/*.yaml` file. The schema is per-file (each YAML file maps to a `$defs` definition); the validator looks up the right definition by filename.

- [ ] **Step 1: Create `schema/cv.schema.json`**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Jin-Ho Lee CV content schema",
  "$defs": {
    "LangString": {
      "type": "object",
      "properties": {
        "en": { "type": "string", "minLength": 1 },
        "de": { "type": "string", "minLength": 1 }
      },
      "required": ["en"],
      "additionalProperties": false
    },
    "DateYM": {
      "type": "string",
      "pattern": "^[0-9]{4}-(0[1-9]|1[0-2])$",
      "description": "Year-month, e.g. '2024-05'"
    },
    "Period": {
      "type": "object",
      "properties": {
        "start": { "$ref": "#/$defs/DateYM" },
        "end": {
          "oneOf": [
            { "$ref": "#/$defs/DateYM" },
            { "type": "null" }
          ]
        }
      },
      "required": ["start"],
      "additionalProperties": false
    },
    "ProjectId": {
      "type": "string",
      "pattern": "^[LDC][0-9]+$"
    },
    "personal": {
      "type": "object",
      "properties": {
        "name": {
          "type": "object",
          "properties": {
            "given": { "type": "string", "minLength": 1 },
            "family": { "type": "string", "minLength": 1 }
          },
          "required": ["given", "family"],
          "additionalProperties": false
        },
        "headline": { "$ref": "#/$defs/LangString" },
        "email": { "type": "string", "format": "email" },
        "location": {
          "type": "object",
          "properties": {
            "city": { "type": "string" },
            "country": { "type": "string" }
          },
          "required": ["city", "country"],
          "additionalProperties": false
        },
        "links": {
          "type": "object",
          "additionalProperties": {
            "oneOf": [{ "type": "string", "format": "uri" }, { "type": "null" }]
          }
        },
        "photo": { "type": "string" }
      },
      "required": ["name", "headline", "email", "location", "links"],
      "additionalProperties": false
    },
    "profile": {
      "type": "object",
      "properties": {
        "tagline": { "type": "string" },
        "paragraphs": {
          "type": "array",
          "items": { "type": "string", "minLength": 1 },
          "minItems": 1
        }
      },
      "required": ["paragraphs"],
      "additionalProperties": false
    },
    "skills": {
      "type": "object",
      "properties": {
        "categories": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "name": { "$ref": "#/$defs/LangString" },
              "groups": {
                "type": "array",
                "items": {
                  "type": "object",
                  "properties": {
                    "label": { "$ref": "#/$defs/LangString" },
                    "items": {
                      "type": "array",
                      "items": { "type": "string" },
                      "minItems": 1
                    }
                  },
                  "required": ["label", "items"],
                  "additionalProperties": false
                }
              }
            },
            "required": ["name", "groups"],
            "additionalProperties": false
          },
          "minItems": 1
        }
      },
      "required": ["categories"],
      "additionalProperties": false
    },
    "education": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "degree": { "$ref": "#/$defs/LangString" },
          "institution": { "type": "string" },
          "location": { "type": "string" },
          "year": { "type": "integer", "minimum": 1900, "maximum": 2100 }
        },
        "required": ["degree", "institution", "year"],
        "additionalProperties": false
      },
      "minItems": 1
    },
    "experience": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": { "type": "string", "pattern": "^[a-z][a-z0-9_-]*$" },
          "org": {
            "type": "object",
            "properties": {
              "name": { "type": "string" },
              "url": { "oneOf": [{ "type": "string", "format": "uri" }, { "type": "null" }] }
            },
            "required": ["name"],
            "additionalProperties": false
          },
          "role": { "$ref": "#/$defs/LangString" },
          "period": { "$ref": "#/$defs/Period" },
          "bullets": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "en": { "type": "string", "minLength": 1 },
                "de": { "type": "string", "minLength": 1 },
                "refs": {
                  "type": "array",
                  "items": { "$ref": "#/$defs/ProjectId" }
                }
              },
              "required": ["en"],
              "additionalProperties": false
            },
            "minItems": 1
          }
        },
        "required": ["id", "org", "role", "period", "bullets"],
        "additionalProperties": false
      },
      "minItems": 1
    },
    "project": {
      "type": "object",
      "properties": {
        "id": { "$ref": "#/$defs/ProjectId" },
        "category": { "enum": ["life-science", "data-science", "consulting"] },
        "title": { "type": "string", "minLength": 1 },
        "summary": { "type": "string", "minLength": 1 },
        "role": { "type": "string", "minLength": 1 },
        "period": { "$ref": "#/$defs/Period" },
        "technologies": {
          "type": "array",
          "items": { "type": "string" },
          "minItems": 1
        },
        "contributions": {
          "type": "array",
          "items": { "type": "string", "minLength": 1 },
          "minItems": 1
        },
        "outcome": { "type": "string", "minLength": 1 }
      },
      "required": ["id", "category", "title", "summary", "role", "technologies", "contributions", "outcome"],
      "additionalProperties": false
    },
    "languages": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": { "$ref": "#/$defs/LangString" },
          "proficiency": { "enum": ["native", "fluent", "basic", "passive"] }
        },
        "required": ["name", "proficiency"],
        "additionalProperties": false
      },
      "minItems": 1
    },
    "volunteer": {
      "type": "object",
      "properties": {
        "categories": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "name": { "$ref": "#/$defs/LangString" },
              "entries": {
                "type": "array",
                "items": { "type": "string" },
                "minItems": 1
              }
            },
            "required": ["name", "entries"],
            "additionalProperties": false
          },
          "minItems": 1
        }
      },
      "required": ["categories"],
      "additionalProperties": false
    }
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add schema/cv.schema.json
git commit -m "feat: add JSON Schema for CV content"
```

---

## Task 4: Validation suite — negative tests first

**Files:**
- Create: `tests/test_validate.py`
- Create: `tests/fixtures/invalid_yaml/missing_required.yaml`
- Create: `tests/fixtures/invalid_yaml/wrong_type.yaml`
- Create: `tests/fixtures/invalid_yaml/bad_project_ref.yaml`
- Create: `scripts/validate.py`

This is the TDD core of Phase 0. Write tests first against a not-yet-existing `validate()` API, watch them fail, then implement.

- [ ] **Step 1: Write the failing test for schema violation detection**

`tests/test_validate.py`:
```python
"""Tests for scripts.validate — content validation suite."""
from pathlib import Path

import pytest

from scripts.validate import ValidationError, validate_file, validate_tree


FIXTURES = Path(__file__).parent / "fixtures" / "invalid_yaml"


def test_missing_required_field_fails(schema_path):
    """personal.yaml without required 'email' should fail validation."""
    bad = FIXTURES / "missing_required.yaml"
    with pytest.raises(ValidationError) as exc:
        validate_file(bad, schema_def="personal", schema_path=schema_path)
    assert "email" in str(exc.value)


def test_wrong_type_fails(schema_path):
    """personal.yaml with email as integer should fail validation."""
    bad = FIXTURES / "wrong_type.yaml"
    with pytest.raises(ValidationError):
        validate_file(bad, schema_def="personal", schema_path=schema_path)


def test_broken_project_ref_fails(content_dir, schema_path, tmp_path):
    """experience.yaml with refs: [Z9] should fail cross-reference check."""
    # Fixture: copy content/ to tmp_path, then inject bad ref
    # (Filled in once content exists in Task 5+; for now use FIXTURES file)
    bad = FIXTURES / "bad_project_ref.yaml"
    with pytest.raises(ValidationError) as exc:
        validate_file(bad, schema_def="experience", schema_path=schema_path,
                      known_project_ids={"L1", "L2"})
    assert "Z9" in str(exc.value) or "unknown project" in str(exc.value).lower()


def test_validate_tree_returns_empty_on_clean_content(content_dir, schema_path):
    """validate_tree on the real content/ should produce no errors (once migrated)."""
    errors = validate_tree(content_dir, schema_path)
    assert errors == [], f"Unexpected validation errors: {errors}"
```

- [ ] **Step 2: Create invalid fixture files**

`tests/fixtures/invalid_yaml/missing_required.yaml`:
```yaml
name:
  given: "Test"
  family: "User"
headline:
  en: "Test headline"
# email deliberately missing
location:
  city: "Anywhere"
  country: "ZZ"
links: {}
```

`tests/fixtures/invalid_yaml/wrong_type.yaml`:
```yaml
name:
  given: "Test"
  family: "User"
headline:
  en: "Test headline"
email: 12345
location:
  city: "Anywhere"
  country: "ZZ"
links: {}
```

`tests/fixtures/invalid_yaml/bad_project_ref.yaml`:
```yaml
- id: test_role
  org:
    name: "Test Co"
    url: null
  role:
    en: "Tester"
  period:
    start: "2020-01"
    end: "2021-01"
  bullets:
    - en: "Did things."
      refs: [Z9]
```

- [ ] **Step 3: Run tests, expect import error**

```bash
just test
```
Expected: `ImportError: cannot import name 'ValidationError' from 'scripts.validate'`. Failures confirm tests are wired up.

- [ ] **Step 4: Implement `scripts/validate.py`**

```python
"""Validate CV content against the JSON Schema and check cross-references."""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from jsonschema import Draft202012Validator
from ruamel.yaml import YAML


yaml = YAML(typ="safe")


class ValidationError(Exception):
    """Raised when content fails schema or cross-reference validation."""


@dataclass
class FileError:
    path: Path
    message: str

    def __str__(self) -> str:
        return f"{self.path}: {self.message}"


def _load_yaml(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return yaml.load(f)


def _load_schema(schema_path: Path) -> dict:
    with schema_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _validator_for(schema_def: str, schema_path: Path) -> Draft202012Validator:
    full = _load_schema(schema_path)
    definition = full["$defs"].get(schema_def)
    if definition is None:
        raise ValidationError(f"Unknown schema definition: {schema_def!r}")
    # Resolve $ref against the parent schema
    sub = {**definition, "$defs": full["$defs"]}
    return Draft202012Validator(sub)


def validate_file(
    path: Path,
    *,
    schema_def: str,
    schema_path: Path,
    known_project_ids: set[str] | None = None,
) -> None:
    """Validate a single YAML file against the given schema definition.

    For `schema_def == "experience"`, also checks that every ref points to a known project.
    Raises ValidationError on failure.
    """
    data = _load_yaml(path)
    validator = _validator_for(schema_def, schema_path)
    errors = sorted(validator.iter_errors(data), key=lambda e: e.path)
    if errors:
        joined = "; ".join(
            f"{'.'.join(str(p) for p in e.path) or '<root>'}: {e.message}"
            for e in errors
        )
        raise ValidationError(f"Schema violation in {path.name}: {joined}")

    if schema_def == "experience" and known_project_ids is not None:
        for entry in data:
            for bullet in entry.get("bullets", []):
                for ref in bullet.get("refs", []):
                    if ref not in known_project_ids:
                        raise ValidationError(
                            f"unknown project ref {ref!r} in {path.name}"
                        )


def _enumerate_project_ids(content_dir: Path) -> set[str]:
    ids: set[str] = set()
    for p in (content_dir / "projects").glob("*.en.yaml"):
        ids.add(p.name.split(".")[0])
    return ids


# Mapping from filename glob → schema definition name
_FILE_RULES: list[tuple[str, str]] = [
    ("personal.yaml", "personal"),
    ("profile.*.yaml", "profile"),
    ("skills.yaml", "skills"),
    ("education.yaml", "education"),
    ("experience.yaml", "experience"),
    ("languages.yaml", "languages"),
    ("volunteer.yaml", "volunteer"),
]


def validate_tree(content_dir: Path, schema_path: Path) -> list[FileError]:
    """Validate every recognized file under content/. Returns list of errors (empty = clean)."""
    errors: list[FileError] = []
    project_ids = _enumerate_project_ids(content_dir)

    for pattern, def_name in _FILE_RULES:
        for path in content_dir.glob(pattern):
            try:
                kwargs = {}
                if def_name == "experience":
                    kwargs["known_project_ids"] = project_ids
                validate_file(path, schema_def=def_name, schema_path=schema_path, **kwargs)
            except ValidationError as e:
                errors.append(FileError(path, str(e)))

    for path in (content_dir / "projects").glob("*.yaml"):
        try:
            validate_file(path, schema_def="project", schema_path=schema_path)
        except ValidationError as e:
            errors.append(FileError(path, str(e)))

    return errors


def main(argv: Iterable[str] = sys.argv[1:]) -> int:
    repo_root = Path(__file__).parent.parent
    content_dir = repo_root / "content"
    schema_path = repo_root / "schema" / "cv.schema.json"

    if not content_dir.exists():
        print(f"ERROR: no content/ directory at {content_dir}", file=sys.stderr)
        return 2

    errors = validate_tree(content_dir, schema_path)
    if errors:
        print(f"FAIL: {len(errors)} validation error(s)", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    print("OK: all content files validate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run tests — negative tests should now pass; tree test still fails (no content yet)**

```bash
just test
```
Expected:
- `test_missing_required_field_fails` PASS
- `test_wrong_type_fails` PASS
- `test_broken_project_ref_fails` PASS
- `test_validate_tree_returns_empty_on_clean_content` FAIL (no content/ yet) — leave failing until Task 14

- [ ] **Step 6: Commit**

```bash
git add scripts/validate.py tests/test_validate.py tests/fixtures/
git commit -m "feat: schema validator with cross-reference check"
```

---

## Task 5: Migrate `personal.yaml` + `profile.en.yaml`

**Files:**
- Create: `content/personal.yaml`
- Create: `content/profile.en.yaml`

**Source:** PDF page 1 — header (name, contact box) + Profile section.

- [ ] **Step 1: Write `content/personal.yaml`**

```yaml
name:
  given: "Jin-Ho"
  family: "Lee"
headline:
  en: "Bioinformatics | Data Science | Consulting"
email: "jinho.michael.lee@gmail.com"
location:
  city: "Mannheim"
  country: "DE"
links:
  linkedin: "https://linkedin.com/in/jin-holee"
  github:   "https://github.com/Jin-HoMLee"
  researchgate: "https://researchgate.net/profile/Jin-Ho-Lee-8"
  orcid: null
photo: "assets/photo.jpg"
```

- [ ] **Step 2: Write `content/profile.en.yaml`**

```yaml
tagline: "Data science and bioinformatics lover with expertise in ML, Computer Vision, GenAI, and Cloud Engineering."
paragraphs:
  - "I bridge wet-lab research and production AI, with a track record of 10+ peer-reviewed papers and managing 1,000+ cloud analytical processes. My experience spans finance, healthcare, neuroscience, genomics, immunology."
  - "Happy to contribute my open, curious, and adaptive work ethos to meaningful projects, combining deep biological expertise with industry-grade Data Science in a great team!"
```

- [ ] **Step 3: Run validator**

```bash
just validate
```
Expected: error about missing other files, but `personal.yaml` and `profile.en.yaml` themselves report OK. (Validator doesn't yet require their presence; later tasks add the rest.)

- [ ] **Step 4: Commit**

```bash
git add content/personal.yaml content/profile.en.yaml
git commit -m "feat(content): migrate personal + profile (EN)"
```

---

## Task 6: Migrate `skills.yaml`, `languages.yaml`, `volunteer.yaml`

**Files:**
- Create: `content/skills.yaml`
- Create: `content/languages.yaml`
- Create: `content/volunteer.yaml`

**Source:** PDF page 1 — Skills box, Languages box, Volunteer & Interests section.

- [ ] **Step 1: Write `content/skills.yaml`**

```yaml
categories:
  - name:
      en: "Bioinformatics & ML"
    groups:
      - label: { en: "Genomics" }
        items: ["NGS", "RNA-Seq", "SNV Calling", "Splice Analysis"]
      - label: { en: "Immunology" }
        items: ["MHC-I Prediction", "HLA Typing", "Neoepitopes"]
      - label: { en: "Nanoscopy" }
        items: ["Spatial Point-Pattern", "Cluster Analysis (DBSCAN)"]

  - name:
      en: "Biotech Wet-Lab"
    groups:
      - label: { en: "Models" }
        items: ["Cancer/Tumor", "3D Cell Culture", "Neural Progenitors"]
      - label: { en: "Imaging" }
        items: ["Super-Resolution", "Confocal", "Fluorescence"]
      - label: { en: "Assays" }
        items: ["FISH", "IF", "qPCR", "FACS"]

  - name:
      en: "Data & Engineering"
    groups:
      - label: { en: "AI & Vision" }
        items: ["TensorFlow", "Keras", "LSTMs", "OpenCV"]
      - label: { en: "Eng & Tools" }
        items: ["Python (Exp)", "R", "SQL", "Docker", "Git", "dbt"]
      - label: { en: "Cloud" }
        items: ["GCP", "BigQuery", "Vertex AI", "Looker"]
```

- [ ] **Step 2: Write `content/languages.yaml`**

```yaml
- name: { en: "German" }
  proficiency: native
- name: { en: "English" }
  proficiency: fluent
- name: { en: "Korean" }
  proficiency: native
- name: { en: "French" }
  proficiency: basic
- name: { en: "Latin" }
  proficiency: passive
```

- [ ] **Step 3: Write `content/volunteer.yaml`**

```yaml
categories:
  - name: { en: "Community" }
    entries:
      - "Jülicher Tafel e.V."
      - "In via - Café Gemeinsam"
      - "Amnesty International"
      - "Florence-Nightingale-Krankenhaus"

  - name: { en: "Environment" }
    entries:
      - "Foodsharing e.V. (Operations Manager)"
      - "Österreichisches Waldgarten-Institut"
      - "Hofwaerts"

  - name: { en: "Sports" }
    entries:
      - "UBC Mannheim"
      - "Sobell Badminton Club"
      - "ASD Gymnase"
      - "BSG Jülich 1963 e.V."
      - "WAT Simmering"
      - "TSG 1889 Dossenheim e.V."
      - "HTV 1846 e.V."

  - name: { en: "Other" }
    entries:
      - "Choir"
      - "KingShot"
      - "Chrome Extensions"
      - "Vanlife"
```

- [ ] **Step 4: Run validator on the new files**

```bash
just validate
```
Expected: `personal.yaml`, `profile.en.yaml`, `skills.yaml`, `languages.yaml`, `volunteer.yaml` all OK (other files not yet present).

- [ ] **Step 5: Commit**

```bash
git add content/skills.yaml content/languages.yaml content/volunteer.yaml
git commit -m "feat(content): migrate skills, languages, volunteer (EN)"
```

---

## Task 7: Migrate `education.yaml`

**Files:**
- Create: `content/education.yaml`

**Source:** PDF page 1 — Education section.

- [ ] **Step 1: Write `content/education.yaml`**

```yaml
- degree:
    en: "M.Sc. Molecular Biotechnology"
  institution: "Heidelberg University"
  location: "Heidelberg, Germany"
  year: 2019

- degree:
    en: "B.Sc. Molecular Biotechnology"
  institution: "Heidelberg University"
  location: "Heidelberg, Germany"
  year: 2014
```

- [ ] **Step 2: Validate**

```bash
just validate
```
Expected: education.yaml OK.

- [ ] **Step 3: Commit**

```bash
git add content/education.yaml
git commit -m "feat(content): migrate education (EN)"
```

---

## Task 8: Migrate `experience.yaml`

**Files:**
- Create: `content/experience.yaml`

**Source:** PDF page 1 — Experiences section. Note: the appendix has cross-refs `[L1]–[L4]`, `[D1]–[D3]`, `[C1]`, `[C2]` — these are encoded as `refs:` on bullets.

- [ ] **Step 1: Write `content/experience.yaml`**

```yaml
- id: cintellic
  org:
    name: "Cintellic / International Bank"
    url: null
  role:
    en: "Consultant, Lead Business Functional Analyst"
  period:
    start: "2024-05"
    end: "2025-07"
  bullets:
    - en: "Scale: Architecting the migration of 1,000+ analytical processes to Google Cloud."
      refs: [C2]
    - en: "AI in Production: Developing BigQueryML models for anti-financial crime & KYC."
      refs: [C1]
    - en: "Stakeholder Lead: Bridging technical data engineering with business requirements for high-stakes banking."
      refs: [C1, C2]

- id: neuefische
  org:
    name: "neuefische GmbH"
    url: null
  role:
    en: "Data Science Trainee, Associate & Coach"
  period:
    start: "2023-02"
    end: "2024-04"
  bullets:
    - en: "Coaching: Instructed 100+ specialists in Python, SQL, and ML lifecycles."
      refs: [D3]
    - en: "ML Development: Independently engineered a Real-Time ASL Recognition system using LSTMs, MediaPipe, and TensorFlow."
      refs: [D1]

- id: research
  org:
    name: "FZ Jülich / KIP / NCT / SNU / DKFZ"
    url: null
  role:
    en: "Doctoral & Post-Graduate Researcher"
  period:
    start: "2014-06"
    end: "2022-07"
  bullets:
    - en: "Genomics & Immunotherapy: Engineered in silico pipelines for HLA Typing and Neoantigen Discovery from cancer patient NGS and RNA-Seq splice junction data."
      refs: [L1, L2]
    - en: "Biophysics & Imaging: Managed end-to-end Super-Resolution Microscopy projects; from wet-lab research to spatial point-pattern data analysis (MATLAB/Python) for studying chromatin."
      refs: [L3]
    - en: "Neurobiology: Investigated radiation effects on Neural Progenitor Differentiation using 3D cell models and the role of extracellular vesicles."
      refs: [L4]
    - en: "Scientific Impact: Authored 10+ peer-reviewed papers, secured third-party funding, and mentored 10+ students."
      refs: []
```

- [ ] **Step 2: Validate — expect cross-ref failures (projects not yet migrated)**

```bash
just validate
```
Expected: failure complaining that L1, L2, …, C2 are unknown project refs. This confirms the cross-reference logic works.

**Do not commit yet.** Validation is red until Task 9 migrates the projects; we commit `experience.yaml` together with the projects to keep `main` green at every commit.

---

## Task 9: Migrate project files L1–L4, D1–D3, C1–C2

**Files (one per project):**
- Create: `content/projects/L1.en.yaml`
- Create: `content/projects/L2.en.yaml`
- Create: `content/projects/L3.en.yaml`
- Create: `content/projects/L4.en.yaml`
- Create: `content/projects/D1.en.yaml`
- Create: `content/projects/D2.en.yaml`
- Create: `content/projects/D3.en.yaml`
- Create: `content/projects/C1.en.yaml`
- Create: `content/projects/C2.en.yaml`

**Source:** PDF pages 4–7 (List of Projects).

Each file follows the same shape. Below is the full content for **L1** as the canonical example; the others follow the same structure with content copied from their respective PDF sections. **Do not** abbreviate — type each file out in full.

- [ ] **Step 1: Create `content/projects/L1.en.yaml`**

```yaml
id: L1
category: life-science
title: "Cancer Neoantigen Discovery – Transcriptome-Wide Splice Analysis"
summary: "Bioinformatics pipeline for identifying novel immunotherapy targets derived from aberrant alternative splicing in RNA-Seq data."
role: "Bioinformatics Research Intern (Seoul National University)"
period:
  start: "2018-09"
  end: "2019-03"
technologies:
  - "Python"
  - "R"
  - "MapSplice"
  - "RNA-Seq"
  - "TCGA Datasets"
  - "MHC-I Prediction Tools"
contributions:
  - "Developed a discovery pipeline to identify tumor-specific splice junctions across large-scale cancer datasets."
  - "Mapped the epitope landscape by predicting high-affinity MHC-I binding peptides from non-canonical transcripts."
  - "Validated the predictive model by cross-referencing findings with high-impact transcriptomic studies."
  - "Evaluated synergistic strategies for co-targeting mutation-derived and splice-derived neoantigens."
outcome: "Demonstrated that alternative splicing is a viable source for high-affinity epitopes, expanding target discovery beyond traditional somatic mutations."
```

- [ ] **Step 2: Create `content/projects/L2.en.yaml`**

```yaml
id: L2
category: life-science
title: "Personalized Immunotherapy – High-Throughput HLA Typing Pipeline"
summary: "Bioinformatics workflow for identifying patient-specific cancer targets and automating HLA genotyping from Next-Generation Sequencing (NGS) data."
role: "Bioinformatics Bachelor Thesis Student (NCT Heidelberg)"
period:
  start: "2013-10"
  end: "2014-06"
technologies:
  - "Python"
  - "R"
  - "HLAMiner"
  - "Seq2HLA"
  - "NetMHCPan (Neural Networks)"
  - "Shell Scripting"
contributions:
  - "Developed an in silico genotyping pipeline to extract HLA alleles directly from Whole-Exome Sequencing (WXS) data."
  - "Implemented predictive modeling using ANNs (NetMHCPan) to screen missense mutations for MHC-I binding affinity."
  - "Engineered a consensus methodology integrating multiple HLA typing algorithms to resolve sequence ambiguities and improve diagnostic reliability."
  - "Validated the pipeline by analyzing binding specificities across HLA alleles to mitigate genotyping errors in vaccine design."
outcome: "Demonstrated the feasibility of a fully computational approach to neoantigen discovery, significantly reducing costs and lead times compared to traditional PCR-based clinical assays."
```

- [ ] **Step 3: Create `content/projects/L3.en.yaml`**

```yaml
id: L3
category: life-science
title: "Experimental Biophysics — Chromatin Nano-Architecture & DNA Repair"
summary: "Advanced research utilizing super-resolution microscopy and computational analysis to investigate DNA repair mechanisms and chromatin nano-architecture."
role: "Graduate Researcher / Master's Candidate"
period:
  start: "2017-05"
  end: "2018-08"
technologies:
  - "MATLAB"
  - "Linux"
  - "R"
  - "Python"
  - "COMBO-FISH"
  - "SPDM"
  - "DBSCAN"
contributions:
  - "Experimental Design: Developed and executed research projects focused on DNA repair pathways and super-resolution imaging of chromatin structures."
  - "Data Analysis & Modeling: Leveraged MATLAB, R, and Python to process complex imaging data and perform quantitative analysis of nano-scale structures."
  - "Academic Leadership: Managed international research collaborations and mentored several Bachelor and Master's students throughout the project lifecycle."
outcome: "Published research findings in multiple peer-reviewed journals and secured third-party funding for continued scientific investigations."
```

- [ ] **Step 4: Create `content/projects/L4.en.yaml`**

```yaml
id: L4
category: life-science
title: "Neural Stem Cell Research – Radiation Effects on 3D Differentiation"
summary: "Scientific research project investigating the impact of ionizing radiation and extracellular vesicles on human neural progenitor cell differentiation."
role: "Doctoral Researcher (RWTH Aachen, Forschungszentrum Jülich)"
period:
  start: "2018-09"
  end: "2022-07"
technologies:
  - "3D Cell Culture Modeling"
  - "qPCR"
  - "Fluorescence Microscopy"
  - "FACS"
  - "Biochemistry"
  - "ImageJ"
  - "MS Office"
contributions:
  - "Experimental Design: Developed and executed a multi-year research project at the intersection of radiation biology and neuroscience."
  - "Leadership & Mentoring: Supervised and guided students, junior researchers, and technical staff through complex laboratory workflows."
  - "Scientific Communication: Secured third-party funding, established research collaborations, and published findings in peer-reviewed journals."
outcome: "Successfully identified new insights into neural radiation responses and presented results at international scientific conferences."
```

- [ ] **Step 5: Create `content/projects/D1.en.yaml`**

```yaml
id: D1
category: data-science
title: "SignMeUp – Real-Time American Sign Language (ASL) Recognition"
summary: "Machine learning pipeline and application prototype for real-time ASL gesture recognition, designed for integration into a digital sign language learning app."
role: "Project Manager / Data Scientist (neuefische GmbH)"
period:
  start: "2023-09"
  end: "2023-12"
technologies:
  - "Python"
  - "TensorFlow (Keras)"
  - "LSTM"
  - "MediaPipe"
  - "OpenCV"
  - "Google Cloud"
  - "Scikit-Learn"
  - "MLflow"
contributions:
  - "Project Leadership: Defined project scope, managed team communication, and delivered stakeholder presentations."
  - "Model Development: Designed and optimized an LSTM neural network to classify temporal sequences of ASL gestures."
  - "Data Engineering: Developed a pipeline for real-time landmark extraction, feature engineering, and data cleaning from video feeds."
outcome: "Delivered a functional prototype for real-time inference, enabling instant feedback for sign language learners."
```

- [ ] **Step 6: Create `content/projects/D2.en.yaml`**

```yaml
id: D2
category: data-science
title: "Shuttle Insights – AI Badminton Match Analysis"
summary: "Computer vision system for analyzing badminton gameplay from video recordings."
role: "Data Scientist / Developer"
period:
  start: "2024-01"
  end: "2024-04"
technologies:
  - "Python"
  - "OpenCV"
  - "TensorFlow"
  - "MediaPipe"
contributions:
  - "Developed a computer vision pipeline for detecting players and tracking shuttle trajectories."
  - "Implemented pose estimation models to analyze player movement patterns."
  - "Extracted gameplay metrics such as rally duration and player positioning."
outcome: "Functional prototype capable of generating match statistics and movement analytics."
```

- [ ] **Step 7: Create `content/projects/D3.en.yaml`**

```yaml
id: D3
category: data-science
title: "Data Science Bootcamp Program"
summary: "Professional training program for transitioning participants into data science careers."
role: "Data Science Coach (neuefische GmbH)"
period:
  start: "2023-09"
  end: "2024-04"
technologies:
  - "Python"
  - "Pandas"
  - "NumPy"
  - "Scikit-Learn"
  - "TensorFlow"
  - "SQL"
  - "Docker"
  - "dbt"
  - "Google Cloud"
contributions:
  - "Delivered lectures on Python, machine learning, SQL, and data visualization."
  - "Mentored students throughout the data science lifecycle."
  - "Supervised capstone projects and technical presentations."
  - "Developed and improved training materials."
outcome: "Successfully supported multiple cohorts in developing industry-ready data science skills."
```

- [ ] **Step 8: Create `content/projects/C1.en.yaml`**

```yaml
id: C1
category: consulting
title: "Anti-Financial Crime – Know Your Customer (KYC) Platform"
summary: "Cloud migration and analytics environment development for financial crime detection at a large international bank."
role: "Lead Business Functional Analyst (Cintellic GmbH)"
period:
  start: "2024-08"
  end: "2025-07"
technologies:
  - "Google Cloud Platform"
  - "BigQuery"
  - "Python"
  - "SAS"
  - "Looker"
contributions:
  - "Expanded the Python-based analytics environment in Google Cloud."
  - "Migrated legacy SAS reporting workflows to Python-based pipelines."
  - "Explored BI capabilities using Looker and prepared the data model."
  - "Conducted stakeholder management and requirements analysis."
  - "Supported AML risk analysis through ad-hoc investigations of customer relationships."
outcome: "Enabled transition of legacy reporting processes into a scalable cloud-based analytics environment."
```

- [ ] **Step 9: Create `content/projects/C2.en.yaml`**

```yaml
id: C2
category: consulting
title: "Hyper-Personalized Digital Customer Platform"
summary: "Data model development supporting hyper-personalized customer communication during migration of customer data infrastructure to Google Cloud."
role: "Lead Business Functional Analyst (Cintellic GmbH)"
period:
  start: "2024-05"
  end: "2024-10"
technologies:
  - "Google Cloud Platform"
  - "BigQuery"
  - "SQL"
  - "Python"
contributions:
  - "Conducted requirements analysis with business and analytics stakeholders."
  - "Mapped data tables from legacy systems to the new cloud architecture."
  - "Supported integration of over 1000 analytical processes into the cloud platform."
outcome: "Enabled scalable data infrastructure for personalized marketing initiatives."
```

- [ ] **Step 10: Run validator — should now be clean**

```bash
just validate
```
Expected: `OK: all content files validate`. Cross-references in `experience.yaml` resolve because all 9 project ids now exist.

- [ ] **Step 11: Commit experience + projects together (keeps `main` green)**

```bash
git add content/experience.yaml content/projects/
git commit -m "feat(content): migrate experience + all 9 project files (EN)"
```

---

## Task 10: Migrate `publications.bib`

**Files:**
- Create: `content/publications.bib`

**Source:** PDF pages 2–3 (List of Publications). The `authorship` field is *custom* — used by the eventual chart renderer; not consumed by standard BibTeX tools.

Some publications are missing DOIs in the source PDF. Leave the `doi` field absent; **do not** invent DOI values. The user can fill them in later (see "Known follow-ups" at the bottom of this plan).

- [ ] **Step 1: Write `content/publications.bib`**

```bibtex
@incollection{lee2021superres_dna_repair,
  author     = {Lee, J. and Hausmann, M.},
  title      = {Super-Resolution Radiation Biology: From Bio-Dosimetry towards Nano-Studies of {DNA} Repair Mechanisms},
  booktitle  = {DNA - Damages and Repair Mechanisms},
  editor     = {Behzadi, P.},
  year       = {2021},
  type       = {book-chapter},
  authorship = {first}
}

@article{hausmann2020_3d_dna_fish,
  author     = {Hausmann, M. and Lee, J. and others},
  title      = {{3D} {DNA} {FISH} for analyses of chromatin-nuclear architecture},
  journal    = {Epigenetics Methods},
  year       = {2020},
  type       = {article},
  authorship = {shared}
}

@article{scherthan2019_ra223,
  author     = {Scherthan, H. and Lee, J. and others},
  title      = {Nanostructure of Clustered {DNA} Damage in Leukocytes after In-Solution Irradiation with the Alpha Emitter {Ra-223}},
  journal    = {Cancers},
  volume     = {11},
  number     = {12},
  year       = {2019},
  type       = {article},
  authorship = {shared}
}

@article{lee2019_combofish,
  author     = {Lee, J. and others},
  title      = {{COMBO-FISH}: A versatile tool beyond standard {FISH} to study chromatin organization by fluorescence light microscopy},
  journal    = {OBM Genetics},
  year       = {2019},
  type       = {article},
  authorship = {first}
}

@article{pagacova2019_metalnp,
  author     = {Pagacova, E. and Stefancikova, L. and Schmidt-Kaler, F. and Hildenbrand, G. and Vicar, T. and Depes, D. and Lee, J. and others},
  title      = {Challenges and contradictions of metal nano-particle applications for radio-sensitivity enhancement in cancer therapy},
  journal    = {International Journal of Molecular Sciences},
  volume     = {20},
  year       = {2019},
  type       = {article},
  authorship = {middle}
}

@article{bobkova2018_53bp1,
  author     = {Bobkova, E. and Depes, D. and Lee, J. and others},
  title      = {Recruitment of {53BP1} Proteins for {DNA} Repair and Persistence of Repair Clusters Differ for Cell Types as Detected by Single Molecule Localization Microscopy},
  journal    = {International Journal of Molecular Sciences},
  volume     = {19},
  year       = {2018},
  type       = {article},
  authorship = {middle}
}

@article{depes2018_gh2ax,
  author     = {Depes, D. and Lee, J. and others},
  title      = {Single-molecule localization microscopy as a promising tool for {gammaH2AX}/{53BP1} foci exploration},
  journal    = {The European Physical Journal D},
  volume     = {72},
  year       = {2018},
  type       = {article},
  authorship = {shared}
}

@article{hausmann2018_h2ax_h3k9,
  author     = {Hausmann, M. and Wagner, E. and Lee, J. and others},
  title      = {Super-Resolution Localization Microscopy of Radiation-Induced Histone {H2AX}-Phosphorylation in relation to {H3K9}-Trimethylation in {HeLa} Cells},
  journal    = {Nanoscale},
  volume     = {10},
  year       = {2018},
  type       = {article},
  authorship = {middle}
}

@article{eryilmaz2018_mre11,
  author     = {Eryilmaz, M. and Schmitt, E. and Krufczik, M. and Theda, F. and Lee, J. and others},
  title      = {Localization Microscopy Analyses of {MRE11} Clusters in {3D}-Conserved Cell Nuclei of Different Cell Lines},
  journal    = {Cancers},
  volume     = {10},
  year       = {2018},
  type       = {article},
  authorship = {middle}
}

@article{hausmann2017_challenges,
  author     = {Hausmann, M. and Ilic, N. and Pilarczyk, G. and Lee, J. and others},
  title      = {Challenges for Super-Resolution Localization Microscopy and Biomolecular Fluorescent Nano-Probing in Cancer Research},
  journal    = {International Journal of Molecular Sciences},
  volume     = {18},
  year       = {2017},
  type       = {article},
  authorship = {middle}
}

@article{krufczik2017_alu,
  author     = {Krufczik, M. and Sievers, A. and Hausmann, A. and Lee, J. and others},
  title      = {Combining Low Temperature Fluorescence {DNA}-Hybridization, Immunostaining, and Super-Resolution Localization Microscopy for Nano-Structure Analysis of {ALU} Elements and Their Influence on Chromatin Structure},
  journal    = {International Journal of Molecular Sciences},
  volume     = {18},
  year       = {2017},
  type       = {article},
  authorship = {middle}
}

@inproceedings{lee2021_degbs,
  author     = {Lee, J.},
  title      = {{DeGBS} 2021 Conference Contribution},
  booktitle  = {Deutsche Gesellschaft f\"ur Biologische Strahlenforschung},
  year       = {2021},
  address    = {Online},
  month      = sep,
  type       = {conference},
  authorship = {first}
}

@inproceedings{lee2019_conrad,
  author     = {Lee, J.},
  title      = {Mechanisms and Challenges for Understanding Radiation Induced Changes in Chromatin Nanoarchitecture and Repair Complex Formation},
  booktitle  = {ConRad 2019 - Global Conference on Radiation Topics},
  address    = {Munich, Germany},
  year       = {2019},
  month      = may,
  type       = {conference},
  authorship = {first}
}

@inproceedings{lee2018_dro,
  author     = {Lee, J.},
  title      = {Mechanisms and challenges for understanding radiation induced changes in chromatin nanoarchitecture},
  booktitle  = {Dny radia\v{c}n\'i ochrany ({DRO} 2018)},
  address    = {Mikulov, Czech Republic},
  year       = {2018},
  month      = nov,
  type       = {conference},
  authorship = {first}
}

@book{lee2025_marketing_automation,
  author     = {Lee, J. and Eckhardt, C.},
  title      = {Marketing Automation Tool Selection \& Implementation @{DeutschlandCard}},
  booktitle  = {Essentials of Modern Marketing, Germany Edition},
  publisher  = {Independently published},
  year       = {2025},
  type       = {book},
  authorship = {first}
}
```

- [ ] **Step 2: Commit**

```bash
git add content/publications.bib
git commit -m "feat(content): migrate publications.bib (15 entries)"
```

---

## Task 11: BibTeX loader with tests

**Files:**
- Create: `scripts/bib_loader.py`
- Create: `tests/test_bib_loader.py`

**Purpose:** Parse `publications.bib` into a structured form: list of records grouped by `type`, with `authorship` counts for the chart. Used by future renderers (PDF, JSON-LD).

- [ ] **Step 1: Write the failing tests**

`tests/test_bib_loader.py`:
```python
"""Tests for scripts.bib_loader."""
from pathlib import Path

import pytest

from scripts.bib_loader import (
    AUTHORSHIP_VALUES,
    BIB_TYPES,
    Publication,
    authorship_counts,
    load_publications,
)


BIB_PATH = Path(__file__).parent.parent / "content" / "publications.bib"


def test_loads_all_entries():
    pubs = load_publications(BIB_PATH)
    assert len(pubs) >= 15, f"expected 15+ entries, got {len(pubs)}"


def test_publications_have_required_fields():
    for pub in load_publications(BIB_PATH):
        assert pub.key
        assert pub.title
        assert pub.year >= 2017
        assert pub.year <= 2030
        assert pub.type in BIB_TYPES, f"unknown type {pub.type} on {pub.key}"
        assert pub.authorship in AUTHORSHIP_VALUES, (
            f"unknown authorship {pub.authorship} on {pub.key}"
        )


def test_publications_sorted_by_year_desc():
    pubs = load_publications(BIB_PATH)
    years = [p.year for p in pubs]
    assert years == sorted(years, reverse=True)


def test_authorship_counts_sums_to_total():
    pubs = load_publications(BIB_PATH)
    counts = authorship_counts(pubs)
    assert sum(counts.values()) == len(pubs)


def test_missing_authorship_field_raises():
    """A bib entry without the custom 'authorship' field should fail loading."""
    bad = Path(__file__).parent / "fixtures" / "invalid_yaml" / "missing_authorship.bib"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_text(
        "@article{x, author={X}, title={T}, year={2020}, journal={J}, type={article}}\n"
    )
    with pytest.raises(ValueError, match="authorship"):
        load_publications(bad)
```

- [ ] **Step 2: Run, watch them fail (ImportError)**

```bash
just test
```
Expected: ImportError on `scripts.bib_loader`.

- [ ] **Step 3: Implement `scripts/bib_loader.py`**

```python
"""Load publications.bib and expose structured records with custom fields."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from pybtex.database import parse_file


BIB_TYPES = {"article", "book-chapter", "conference", "book"}
AUTHORSHIP_VALUES = {"first", "shared", "middle", "last", "corresponding"}


@dataclass(frozen=True)
class Publication:
    key: str
    title: str
    year: int
    type: str
    authorship: str
    authors: list[str]
    venue: str | None
    raw: dict


def _venue(entry) -> str | None:
    fields = entry.fields
    return (
        fields.get("journal")
        or fields.get("booktitle")
        or fields.get("publisher")
    )


def _parse_entry(key: str, entry) -> Publication:
    fields = entry.fields
    for required in ("title", "year", "type", "authorship"):
        if required not in fields:
            raise ValueError(f"{key}: missing required field {required!r}")
    if fields["type"] not in BIB_TYPES:
        raise ValueError(f"{key}: unknown type {fields['type']!r}")
    if fields["authorship"] not in AUTHORSHIP_VALUES:
        raise ValueError(f"{key}: unknown authorship {fields['authorship']!r}")

    authors = [str(p) for p in entry.persons.get("author", [])]
    return Publication(
        key=key,
        title=fields["title"],
        year=int(fields["year"]),
        type=fields["type"],
        authorship=fields["authorship"],
        authors=authors,
        venue=_venue(entry),
        raw=dict(fields),
    )


def load_publications(bib_path: Path) -> list[Publication]:
    """Parse a .bib file into Publication records, sorted by year (newest first)."""
    bib = parse_file(str(bib_path))
    pubs = [_parse_entry(key, entry) for key, entry in bib.entries.items()]
    return sorted(pubs, key=lambda p: p.year, reverse=True)


def authorship_counts(pubs: Iterable[Publication]) -> dict[str, int]:
    """Return a {authorship_value: count} dict, suitable for the pie chart."""
    return dict(Counter(p.authorship for p in pubs))
```

- [ ] **Step 4: Run tests, expect passing**

```bash
just test
```
Expected: all bib_loader tests pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/bib_loader.py tests/test_bib_loader.py
git commit -m "feat: BibTeX loader with authorship counts"
```

---

## Task 12: Private overlay — content_loader with tests

**Files:**
- Create: `scripts/content_loader.py`
- Create: `tests/test_content_loader.py`
- Create: `content.private.example/private.example.yaml`

**Purpose:** Load the public content tree, optionally merge a private overlay, and return a unified dict that downstream renderers consume.

- [ ] **Step 1: Write the failing tests**

`tests/test_content_loader.py`:
```python
"""Tests for scripts.content_loader."""
from pathlib import Path

import pytest

from scripts.content_loader import (
    deep_merge,
    load_content,
)


def test_deep_merge_overlays_leaf_values():
    base = {"a": 1, "b": {"c": 2}}
    overlay = {"b": {"c": 3, "d": 4}}
    result = deep_merge(base, overlay)
    assert result == {"a": 1, "b": {"c": 3, "d": 4}}


def test_deep_merge_does_not_mutate_inputs():
    base = {"a": {"x": 1}}
    overlay = {"a": {"y": 2}}
    deep_merge(base, overlay)
    assert base == {"a": {"x": 1}}
    assert overlay == {"a": {"y": 2}}


def test_load_content_without_private_returns_public_only(content_dir):
    content = load_content(content_dir, private_path=None)
    assert "personal" in content
    assert "phone" not in content["personal"]
    assert "address" not in content["personal"]


def test_load_content_with_private_merges_overlay(content_dir, tmp_path):
    private = tmp_path / "private.yaml"
    private.write_text(
        'phone: "+49 000 0000000"\n'
        'address:\n'
        '  street: "Teststraße 1"\n'
        '  postal_code: "00000"\n'
        '  city: "Testville"\n'
        '  country: "ZZ"\n'
    )
    content = load_content(content_dir, private_path=private)
    assert content["personal"]["phone"] == "+49 000 0000000"
    assert content["personal"]["address"]["city"] == "Testville"


def test_load_content_includes_all_sections(content_dir):
    content = load_content(content_dir, private_path=None)
    for key in ("personal", "profile", "skills", "education",
                "experience", "projects", "languages", "volunteer", "publications"):
        assert key in content, f"missing {key} in loaded content"


def test_load_content_projects_keyed_by_id(content_dir):
    content = load_content(content_dir, private_path=None)
    assert "L1" in content["projects"]
    assert content["projects"]["L1"]["category"] == "life-science"
```

- [ ] **Step 2: Run, watch them fail**

```bash
just test
```
Expected: ImportError on `scripts.content_loader`.

- [ ] **Step 3: Implement `scripts/content_loader.py`**

```python
"""Load CV content from YAML tree + optional private overlay."""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from scripts.bib_loader import load_publications


yaml = YAML(typ="safe")


def deep_merge(base: dict, overlay: dict) -> dict:
    """Recursive dict merge — overlay wins on conflict, nested dicts merged."""
    result = copy.deepcopy(base)
    for key, value in overlay.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return yaml.load(f)


def _load_projects(projects_dir: Path, lang: str = "en") -> dict[str, dict]:
    out: dict[str, dict] = {}
    for path in sorted(projects_dir.glob(f"*.{lang}.yaml")):
        proj = _load_yaml(path)
        out[proj["id"]] = proj
    return out


def load_content(
    content_dir: Path,
    *,
    private_path: Path | None = None,
    lang: str = "en",
) -> dict:
    """Load full content tree.

    Returns a dict with keys: personal, profile, skills, education, experience,
    projects (dict keyed by id), languages, volunteer, publications (list of records).

    If private_path is provided and the file exists, its contents are merged into
    content["personal"].
    """
    personal = _load_yaml(content_dir / "personal.yaml")
    if private_path is not None and private_path.exists():
        private = _load_yaml(private_path)
        personal = deep_merge(personal, private)

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
    }
    return content
```

- [ ] **Step 4: Create the example private overlay**

`content.private.example/private.example.yaml`:
```yaml
# Copy this file to `content.private/private.yaml` and fill in values.
# That directory is gitignored — your real data never enters the repo.
phone: "+49 ... ..."
address:
  street: "Example Street 1"
  postal_code: "00000"
  city: "Example City"
  country: "DE"
```

- [ ] **Step 5: Run tests**

```bash
just test
```
Expected: all content_loader tests pass.

- [ ] **Step 6: Commit**

```bash
git add scripts/content_loader.py tests/test_content_loader.py content.private.example/
git commit -m "feat: content loader with private overlay merge"
```

---

## Task 13: End-to-end validation + integration smoke

**Files:**
- Modify: `tests/test_validate.py` (add tree-clean test verification)
- Modify: `scripts/validate.py` (also validate `publications.bib` via bib_loader)

- [ ] **Step 1: Extend `scripts/validate.py` to validate the bib file**

Add this function to `scripts/validate.py`:

```python
def _validate_publications(content_dir: Path) -> list[FileError]:
    bib_path = content_dir / "publications.bib"
    if not bib_path.exists():
        return [FileError(bib_path, "publications.bib missing")]
    try:
        from scripts.bib_loader import load_publications  # local import avoids cycles
        load_publications(bib_path)
    except Exception as e:
        return [FileError(bib_path, str(e))]
    return []
```

Then modify `validate_tree` to call it:

```python
def validate_tree(content_dir: Path, schema_path: Path) -> list[FileError]:
    """Validate every recognized file under content/. Returns list of errors (empty = clean)."""
    errors: list[FileError] = []
    project_ids = _enumerate_project_ids(content_dir)

    for pattern, def_name in _FILE_RULES:
        for path in content_dir.glob(pattern):
            try:
                kwargs = {}
                if def_name == "experience":
                    kwargs["known_project_ids"] = project_ids
                validate_file(path, schema_def=def_name, schema_path=schema_path, **kwargs)
            except ValidationError as e:
                errors.append(FileError(path, str(e)))

    for path in (content_dir / "projects").glob("*.yaml"):
        try:
            validate_file(path, schema_def="project", schema_path=schema_path)
        except ValidationError as e:
            errors.append(FileError(path, str(e)))

    errors.extend(_validate_publications(content_dir))
    return errors
```

- [ ] **Step 2: Run validator from CLI — should be clean**

```bash
just validate
```
Expected output:
```
OK: all content files validate
```

- [ ] **Step 3: Run full test suite**

```bash
just test
```
Expected: all tests pass, including `test_validate_tree_returns_empty_on_clean_content`.

- [ ] **Step 4: Run an integration smoke from a Python REPL or quick script**

```bash
uv run python -c "
from pathlib import Path
from scripts.content_loader import load_content
content = load_content(Path('content'), private_path=None)
print(f'Loaded {len(content[\"projects\"])} projects, {len(content[\"publications\"])} publications')
print(f'Profile paragraphs: {len(content[\"profile\"][\"paragraphs\"])}')
print(f'Personal email: {content[\"personal\"][\"email\"]}')
assert 'phone' not in content['personal'], 'phone leaked from private!'
print('OK')
"
```
Expected:
```
Loaded 9 projects, 15 publications
Profile paragraphs: 2
Personal email: jinho.michael.lee@gmail.com
OK
```

- [ ] **Step 5: Commit**

```bash
git add scripts/validate.py
git commit -m "feat: validate publications.bib as part of validate-tree"
```

---

## Task 14: CI workflow for validation

**Files:**
- Create: `.github/workflows/ci.yml`

**Purpose:** Run validation + tests on every push and PR. (PDF/web builds come in later phases.)

- [ ] **Step 1: Create `.github/workflows/ci.yml`**

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v3
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
```

- [ ] **Step 2: Run local equivalents to confirm CI will pass**

```bash
just validate && just test && uv run ruff check .
```
Expected: no errors from any of the three.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: validate + test + lint on every push"
```

---

## Done criteria

Phase 0 is complete when **all** of the following are true:

- `just validate` exits 0
- `just test` passes (all tests, including the negative fixtures and the tree-clean test)
- `uv run ruff check .` exits 0
- Running the smoke script from Task 13 prints the expected output
- `git log --oneline` shows clean atomic commits, one per task
- The repo can be cloned fresh, `uv sync && just validate && just test` works without network access to anything beyond PyPI

## Known follow-ups (deferred — not Phase 0)

These are noted for the next plan to pick up, not gaps to close now:

- **Missing DOI values** in `publications.bib`. Source PDF doesn't include them. User to add when ready.
- **Project periods** for some entries are approximate (`L1`, `L2`, `L3`, `D1`, `D2`, `D3`). Source PDF only lists year ranges or partial dates. User to confirm.
- **DE translations** — Phase 2.
- **PDF rendering** — Phase 1 (next plan).
- **Publication chart regeneration script** — Phase 4 (or rolled into Phase 1 if the static SVG is needed first).
