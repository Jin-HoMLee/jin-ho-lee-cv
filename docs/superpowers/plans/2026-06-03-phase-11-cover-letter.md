# Phase 11 — Cover Letter Generator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the codified CV produce tailored cover letters for real applications — paste a job description, do a short interview, draft a letter grounded strictly in the CV, and render a CV-matching PDF + plain-text/markdown into a gitignored per-application folder.

**Architecture:** One pure-Python core (`scripts/cover_letter_core.py`) owns all path/PII guards, profile + application storage, validation, and render orchestration. A deterministic text serializer (`scripts/letter_text.py`) and a Typst template (`pdf/templates/cover-letter.typ`) are the renderers; a thin CLI (`scripts/render_letter.py`) wires `just letter <slug>`. A Claude skill (`.claude/skills/cover-letter/`) drives the conversational interview and calls the core. The generator reads `content/` **read-only** (via `agent_core.read_cv`) and writes **only** into a gitignored `applications/` overlay — the "content is the only source of truth" principle is preserved.

**Tech Stack:** Python 3.12, `ruamel.yaml`, `jsonschema` (Draft 2020-12), Typst, `pytest` + `syrupy` golden snapshots, `just`, `uv`. Mirrors the existing `agent_core.py` / `pdf/build.py` / `render_text.py` conventions.

**Spec:** `docs/superpowers/specs/2026-06-03-phase-11-cover-letter-design.md` · **Issue:** [#65](https://github.com/Jin-HoMLee/jin-ho-lee-cv/issues/65)

---

## File structure

| File | Responsibility |
|---|---|
| `schema/application.schema.json` (create) | JSON Schema for `application.yaml` (per-job metadata). |
| `schema/profile.schema.json` (create) | JSON Schema for the evergreen `profile.yaml`. |
| `applications.example/...` (create) | Committed template documenting the folder shape (no real data). |
| `scripts/cover_letter_core.py` (create) | Pure core: path guard, profile/application CRUD, validation, render orchestration. |
| `scripts/letter_text.py` (create) | Deterministic text serializer (`render(letter, sender, flavor)`), snapshot-tested. |
| `scripts/render_letter.py` (create) | Thin CLI wrapping `cover_letter_core.render_letter` for `just letter`. |
| `pdf/templates/cover-letter.typ` (create) | DIN 5008 / EN letter body reusing `styles.typ` + `header.typ`. |
| `.claude/skills/cover-letter/SKILL.md` + `reference.md` (create) | Skill: interview flow + grounding rules + DIN 5008/EN conventions. |
| `.gitignore` (modify) | Ignore `applications/` and `assets/signature.*`. |
| `justfile` (modify) | Add `letter <slug>` recipe. |
| `tests/test_cover_letter_schemas.py` (create) | Schemas valid + example files validate. |
| `tests/test_cover_letter_core.py` (create) | Core guards, CRUD, validation, render. |
| `tests/test_snapshots.py` (modify) | Golden snapshots for the text serializer (both flavors, both langs). |
| `tests/test_letter_pdf.py` (create) | Typst compile-smoke (skip-guarded). |
| `tests/test_cover_letter_skill_docs.py` (create) | Skill drift-guard vs justfile + schemas. |
| `CLAUDE.md` (modify) | Phase 11 row + layout/commands/files-to-read/local-only updates. |

---

## Task 1: Scaffolding — gitignore, schemas, example folder

**Files:**
- Modify: `.gitignore`
- Create: `schema/application.schema.json`
- Create: `schema/profile.schema.json`
- Create: `applications.example/profile.example.yaml`
- Create: `applications.example/example-company-role-2026-06/application.example.yaml`
- Create: `applications.example/example-company-role-2026-06/job.example.md`
- Create: `applications.example/example-company-role-2026-06/interview.example.yaml`
- Create: `applications.example/example-company-role-2026-06/draft.example.md`
- Test: `tests/test_cover_letter_schemas.py`

- [ ] **Step 1: Add gitignore entries**

In `.gitignore`, after the `content.private/` block (the `assets/photo.*` line), add:

```gitignore
# Cover letters — per-application material is private, never committed (this repo is public)
applications/

# Handwritten signature image for cover-letter PDFs (optional, like the photo)
assets/signature.*
```

- [ ] **Step 2: Write the failing schema test**

Create `tests/test_cover_letter_schemas.py`:

```python
"""The cover-letter schemas are valid Draft 2020-12 and the committed examples validate."""

from __future__ import annotations

from pathlib import Path

from jsonschema import Draft202012Validator
from ruamel.yaml import YAML

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = REPO_ROOT / "schema"
EXAMPLE_DIR = REPO_ROOT / "applications.example"
_yaml = YAML(typ="safe")


def _load_yaml(path: Path) -> dict:
    return _yaml.load(path.read_text(encoding="utf-8"))


def _load_schema(name: str) -> dict:
    import json

    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


def test_application_schema_is_valid():
    Draft202012Validator.check_schema(_load_schema("application.schema.json"))


def test_profile_schema_is_valid():
    Draft202012Validator.check_schema(_load_schema("profile.schema.json"))


def test_example_application_validates():
    schema = _load_schema("application.schema.json")
    data = _load_yaml(EXAMPLE_DIR / "example-company-role-2026-06" / "application.example.yaml")
    assert Draft202012Validator(schema).is_valid(data), list(
        Draft202012Validator(schema).iter_errors(data)
    )


def test_example_profile_validates():
    schema = _load_schema("profile.schema.json")
    data = _load_yaml(EXAMPLE_DIR / "profile.example.yaml")
    assert Draft202012Validator(schema).is_valid(data), list(
        Draft202012Validator(schema).iter_errors(data)
    )
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `uv run pytest tests/test_cover_letter_schemas.py -v`
Expected: FAIL — schema files and example files do not exist yet (FileNotFoundError).

- [ ] **Step 4: Create `schema/application.schema.json`**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Cover-letter application metadata",
  "type": "object",
  "properties": {
    "company": { "type": "string", "minLength": 1 },
    "role": { "type": "string", "minLength": 1 },
    "language": { "type": "string", "enum": ["en", "de"] },
    "date": {
      "type": "string",
      "pattern": "^[0-9]{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$",
      "description": "Letter date, ISO YYYY-MM-DD"
    },
    "recipient": {
      "type": ["object", "null"],
      "properties": {
        "name": { "type": ["string", "null"] },
        "company": { "type": ["string", "null"] },
        "address": {
          "type": ["object", "null"],
          "properties": {
            "street": { "type": "string" },
            "postal_code": { "type": "string" },
            "city": { "type": "string" },
            "country": { "type": "string" }
          },
          "additionalProperties": false
        }
      },
      "additionalProperties": false
    },
    "subject": { "type": "string", "minLength": 1 },
    "source": { "type": "string" },
    "url": { "type": "string" },
    "status": { "type": "string", "enum": ["draft", "sent", "interview", "rejected", "offer"] }
  },
  "required": ["company", "role", "language", "date", "subject", "status"],
  "additionalProperties": false
}
```

- [ ] **Step 5: Create `schema/profile.schema.json`**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Evergreen cover-letter profile",
  "$defs": {
    "LangString": {
      "type": "object",
      "properties": {
        "en": { "type": "string", "minLength": 1 },
        "de": { "type": "string", "minLength": 1 }
      },
      "required": ["en"],
      "additionalProperties": false
    }
  },
  "type": "object",
  "properties": {
    "motivation": { "$ref": "#/$defs/LangString" },
    "work_style": { "$ref": "#/$defs/LangString" },
    "availability": { "type": "string" },
    "salary_expectation": { "type": "string" },
    "relocation": { "type": "string" },
    "preferences": { "$ref": "#/$defs/LangString" }
  },
  "additionalProperties": false
}
```

- [ ] **Step 6: Create the example folder files**

`applications.example/profile.example.yaml`:

```yaml
# Evergreen answers, reused across every application. Prose fields are { en, de }.
# Copy this file to applications/profile.yaml and fill in once.
motivation:
  en: "I want to apply computational methods to problems that matter for human health."
  de: "Ich möchte computergestützte Methoden auf Probleme anwenden, die für die menschliche Gesundheit zählen."
work_style:
  en: "Reproducible, well-documented pipelines; close collaboration with wet-lab and clinical teams."
  de: "Reproduzierbare, gut dokumentierte Pipelines; enge Zusammenarbeit mit Labor- und klinischen Teams."
availability: "Available from 2026-09 (3 months' notice)"
salary_expectation: "EUR 65,000–75,000 (context only — never rendered unless the JD asks)"
relocation: "Open to relocation within the Rhine-Neckar region; remote-friendly preferred."
preferences:
  en: "Mid-size research-driven company; genomics or clinical data; hybrid remote."
  de: "Mittelgroßes forschungsgetriebenes Unternehmen; Genomik oder klinische Daten; hybrid."
```

`applications.example/example-company-role-2026-06/application.example.yaml`:

```yaml
company: "Acme Genomics GmbH"
role: "Bioinformatician"
language: "de"
date: "2026-06-03"
recipient:
  name: "Dr. Erika Mustermann"
  company: "Acme Genomics GmbH"
  address:
    street: "Musterstraße 1"
    postal_code: "68159"
    city: "Mannheim"
subject: "Bewerbung als Bioinformatician"
source: "LinkedIn"
url: "https://example.com/jobs/123"
status: "draft"
```

`applications.example/example-company-role-2026-06/job.example.md`:

```markdown
# Bioinformatician (m/w/d) — Acme Genomics GmbH

We are looking for a bioinformatician to build reproducible NGS analysis pipelines.

## Requirements
- MSc/PhD in bioinformatics or related
- Python, Nextflow/Snakemake
- Experience with variant calling
- 5 years of Rust (nice to have)
```

`applications.example/example-company-role-2026-06/interview.example.yaml`:

```yaml
why_company: "Acme's focus on reproducible clinical genomics matches my pipeline work."
emphasis:
  - "L1"
  - "GCP migration"
gaps:
  - requirement: "5 years of Rust"
    decision: "transferable"
    note: "frame C/performance work honestly; no Rust claim"
notes: "Keep it to one page; lead with the pipeline outcome."
```

`applications.example/example-company-role-2026-06/draft.example.md`:

```markdown
mit großem Interesse habe ich Ihre Ausschreibung als Bioinformatician gelesen. In meiner bisherigen Arbeit habe ich reproduzierbare NGS-Pipelines entwickelt und betrieben.

Besonders reizt mich an Acme Genomics der Fokus auf reproduzierbare klinische Genomik. Meine Erfahrung mit der Migration einer Analyse-Pipeline in die Google Cloud Platform zeigt, dass ich Verantwortung für Infrastruktur und Ergebnisqualität übernehme.

Ich freue mich darauf, meine Erfahrung in Ihr Team einzubringen.
```

- [ ] **Step 7: Run the test to verify it passes**

Run: `uv run pytest tests/test_cover_letter_schemas.py -v`
Expected: PASS (4 tests).

- [ ] **Step 8: Commit**

```bash
git add .gitignore schema/application.schema.json schema/profile.schema.json \
  applications.example/ tests/test_cover_letter_schemas.py
git commit -m "feat: cover-letter schemas + example folder + gitignore"
```

---

## Task 2: Core part A — path guard, helpers, profile + application CRUD

**Files:**
- Create: `scripts/cover_letter_core.py`
- Test: `tests/test_cover_letter_core.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_cover_letter_core.py`:

```python
"""Tests for the cover-letter core (paths, profile/application storage, validation, render)."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts import cover_letter_core as clc

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def apps(tmp_path: Path) -> Path:
    """An empty, writable applications/ dir."""
    d = tmp_path / "applications"
    d.mkdir()
    return d


@pytest.mark.parametrize(
    "bad",
    [
        "/etc/passwd",
        "../content/personal.yaml",
        "../../secret.yaml",
        "slug/../../escape.yaml",
        ".hidden/application.yaml",
        "slug/evil.exe",
    ],
)
def test_safe_path_rejects(apps, bad):
    with pytest.raises(ValueError):
        clc._safe_application_path(bad, apps_dir=apps)


def test_safe_path_accepts_dir_and_file(apps):
    assert clc._safe_application_path("acme-bio-2026-06", apps_dir=apps) == (
        apps / "acme-bio-2026-06"
    ).resolve()
    assert clc._safe_application_path("acme-bio-2026-06/draft.md", apps_dir=apps) == (
        apps / "acme-bio-2026-06" / "draft.md"
    ).resolve()


def test_safe_path_rejects_symlink_escape(apps):
    (apps / "leak").symlink_to(REPO_ROOT / "content")
    with pytest.raises(ValueError):
        clc._safe_application_path("leak/personal.yaml", apps_dir=apps)


def test_sanitize_slug():
    assert clc._sanitize_slug("Acme Genomics / Bioinformatician 2026-06") == (
        "acme-genomics-bioinformatician-2026-06"
    )
    with pytest.raises(ValueError):
        clc._sanitize_slug("///")


def test_profile_roundtrip(apps):
    assert clc.read_profile(apps_dir=apps) == {}
    data = {"motivation": {"en": "x"}, "availability": "now"}
    clc.write_profile(data, apps_dir=apps)
    assert clc.read_profile(apps_dir=apps) == data


def test_write_profile_rejects_invalid(apps):
    with pytest.raises(ValueError):
        clc.write_profile({"motivation": {"de": "only-de-no-en"}}, apps_dir=apps)


def test_create_and_read_application(apps):
    slug = clc.create_application(
        "Acme Bio 2026-06",
        job_text="# Job\nDo bioinformatics.\n",
        meta={
            "company": "Acme",
            "role": "Bioinformatician",
            "language": "de",
            "date": "2026-06-03",
            "subject": "Bewerbung",
            "status": "draft",
        },
        apps_dir=apps,
    )
    assert slug == "acme-bio-2026-06"
    bundle = clc.read_application(slug, apps_dir=apps)
    assert bundle["application"]["company"] == "Acme"
    assert "bioinformatics" in bundle["job"]
    assert bundle["interview"] is None
    assert bundle["draft"] is None


def test_create_application_refuses_collision(apps):
    meta = {
        "company": "Acme",
        "role": "Bioinformatician",
        "language": "de",
        "date": "2026-06-03",
        "subject": "Bewerbung",
        "status": "draft",
    }
    clc.create_application("acme-bio-2026-06", job_text="x", meta=meta, apps_dir=apps)
    with pytest.raises(FileExistsError):
        clc.create_application("acme-bio-2026-06", job_text="y", meta=meta, apps_dir=apps)


def test_list_applications_sorted(apps):
    for s in ("b-role-2026-06", "a-role-2026-06"):
        clc.create_application(
            s,
            job_text="x",
            meta={
                "company": "C",
                "role": "R",
                "language": "en",
                "date": "2026-06-03",
                "subject": "S",
                "status": "draft",
            },
            apps_dir=apps,
        )
    assert clc.list_applications(apps_dir=apps) == ["a-role-2026-06", "b-role-2026-06"]


def test_core_never_writes_under_content(apps):
    """All write helpers route through _safe_application_path; content/ is untouchable."""
    with pytest.raises(ValueError):
        clc._atomic_write("../content/personal.yaml", "boom", apps_dir=apps)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_cover_letter_core.py -v`
Expected: FAIL — `scripts.cover_letter_core` does not exist (ImportError).

- [ ] **Step 3: Create `scripts/cover_letter_core.py` with this content**

```python
"""Cover-letter core: storage, validation, and render orchestration.

Pure Python, mirrors scripts/agent_core.py conventions. Every path / PII /
subprocess guard lives here. Reads content/ read-only (via agent_core.read_cv)
for grounding; writes ONLY into the gitignored applications/ overlay.
"""

from __future__ import annotations

import io
import json
import os
import re
import shutil
import subprocess
import tempfile
from datetime import date as _date
from pathlib import Path, PurePosixPath

from jsonschema import Draft202012Validator
from ruamel.yaml import YAML

from scripts import agent_core, letter_text
from scripts.content_loader import load_content
from scripts.langstring import resolve_langstrings
from scripts.render_web_data import _to_jsonable

_yaml = YAML(typ="safe")
_yaml.default_flow_style = False

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = REPO_ROOT / "content"
APPS_DIR = REPO_ROOT / "applications"
APP_SCHEMA = REPO_ROOT / "schema" / "application.schema.json"
PROFILE_SCHEMA = REPO_ROOT / "schema" / "profile.schema.json"
PRIVATE_PATH = REPO_ROOT / "content.private" / "private.yaml"

ALLOWED_SUFFIXES = {".yaml", ".md", ".txt", ".pdf"}
_GAP_DECISIONS = {"transferable", "omit", "example"}

_MONTHS = {
    "en": [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    ],
    "de": [
        "Januar", "Februar", "März", "April", "Mai", "Juni",
        "Juli", "August", "September", "Oktober", "November", "Dezember",
    ],
}


# --- path safety & low-level IO -------------------------------------------------

def _safe_application_path(rel: str, *, apps_dir: Path = APPS_DIR) -> Path:
    """Resolve an applications-relative path safely, or raise ValueError.

    Blocks absolute paths, '..'/dot segments, disallowed suffixes, symlink
    escapes, and anything resolving outside apps_dir. An empty suffix is treated
    as a slug directory and allowed.
    """
    pure = PurePosixPath(rel)
    if pure.is_absolute() or rel.startswith(("/", "\\")):
        raise ValueError(f"path must be relative to applications/: {rel!r}")
    if any(part in ("..", ".") or part.startswith(".") for part in pure.parts):
        raise ValueError(f"illegal path segment in {rel!r}")
    if pure.suffix and pure.suffix not in ALLOWED_SUFFIXES:
        raise ValueError(f"disallowed suffix in {rel!r}")
    resolved = (apps_dir / rel).resolve()
    root = apps_dir.resolve()
    if root != resolved and root not in resolved.parents:
        raise ValueError(f"path escapes applications/: {rel!r}")
    return resolved


def _sanitize_slug(raw: str) -> str:
    """Lowercase, replace non-alphanumerics with hyphens, trim. Raise if empty."""
    s = re.sub(r"[^a-z0-9]+", "-", raw.strip().lower()).strip("-")
    if not s:
        raise ValueError(f"slug is empty after sanitizing: {raw!r}")
    return s


def _atomic_write(rel: str, text: str, *, apps_dir: Path = APPS_DIR) -> Path:
    """Atomically write text to a guarded applications-relative path."""
    dst = _safe_application_path(rel, apps_dir=apps_dir)
    dst.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(dst.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, dst)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    return dst


def _read_yaml(path: Path) -> dict:
    return _yaml.load(path.read_text(encoding="utf-8")) or {}


def _write_yaml(rel: str, data: dict, *, apps_dir: Path = APPS_DIR) -> None:
    buf = io.StringIO()
    _yaml.dump(data, buf)
    _atomic_write(rel, buf.getvalue(), apps_dir=apps_dir)


def _schema_errors(data: dict, schema_path: Path) -> list[str]:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    return [f"{'/'.join(str(p) for p in e.path) or '<root>'}: {e.message}" for e in validator.iter_errors(data)]


# --- profile (evergreen) --------------------------------------------------------

def read_profile(*, apps_dir: Path = APPS_DIR) -> dict:
    """Return the evergreen profile dict, or {} if absent."""
    p = apps_dir / "profile.yaml"
    return _read_yaml(p) if p.exists() else {}


def write_profile(data: dict, *, apps_dir: Path = APPS_DIR) -> None:
    """Validate against profile.schema.json, then atomically write profile.yaml."""
    errors = _schema_errors(data, PROFILE_SCHEMA)
    if errors:
        raise ValueError("invalid profile: " + "; ".join(errors))
    _write_yaml("profile.yaml", data, apps_dir=apps_dir)


# --- applications (per-job) -----------------------------------------------------

def list_applications(*, apps_dir: Path = APPS_DIR) -> list[str]:
    """Sorted slugs (directories only, excluding dotfiles and profile.yaml)."""
    if not apps_dir.exists():
        return []
    return sorted(p.name for p in apps_dir.iterdir() if p.is_dir() and not p.name.startswith("."))


def create_application(slug: str, *, job_text: str, meta: dict, apps_dir: Path = APPS_DIR) -> str:
    """Scaffold applications/<slug>/ with job.md + application.yaml. Returns the slug.

    Refuses to overwrite an existing application. Validation of application.yaml
    is deferred to validate_application (the skill fills it in iteratively).
    """
    slug = _sanitize_slug(slug)
    app_dir = _safe_application_path(slug, apps_dir=apps_dir)
    if app_dir.exists():
        raise FileExistsError(f"application already exists: {slug}")
    app_dir.mkdir(parents=True)
    _atomic_write(f"{slug}/job.md", job_text, apps_dir=apps_dir)
    _write_yaml(f"{slug}/application.yaml", meta, apps_dir=apps_dir)
    return slug


def read_application(slug: str, *, apps_dir: Path = APPS_DIR) -> dict:
    """Bundle {application, job, interview, draft}; missing parts are None."""
    slug = _sanitize_slug(slug)
    app_dir = _safe_application_path(slug, apps_dir=apps_dir)

    def _yaml_or_none(name: str):
        f = app_dir / name
        return _read_yaml(f) if f.exists() else None

    def _text_or_none(name: str):
        f = app_dir / name
        return f.read_text(encoding="utf-8") if f.exists() else None

    return {
        "application": _yaml_or_none("application.yaml"),
        "job": _text_or_none("job.md"),
        "interview": _yaml_or_none("interview.yaml"),
        "draft": _text_or_none("draft.md"),
    }


def save_interview(slug: str, data: dict, *, apps_dir: Path = APPS_DIR) -> None:
    """Validate-light (gap decisions) then atomically write interview.yaml."""
    for gap in data.get("gaps") or []:
        if gap.get("decision") not in _GAP_DECISIONS:
            raise ValueError(f"invalid gap decision {gap.get('decision')!r}; expected one of {_GAP_DECISIONS}")
    _write_yaml(f"{_sanitize_slug(slug)}/interview.yaml", data, apps_dir=apps_dir)


def save_draft(slug: str, body: str, *, apps_dir: Path = APPS_DIR) -> None:
    """Atomically write the editable letter body to draft.md."""
    _atomic_write(f"{_sanitize_slug(slug)}/draft.md", body, apps_dir=apps_dir)
```

> Note: `letter_text` is imported but only used in Task 5's `render_letter`. Task 4 creates `scripts/letter_text.py`; the import resolves once Task 4 lands. To keep Task 2 runnable in isolation, **create `scripts/letter_text.py` as an empty stub now** (`"""Deterministic cover-letter text serializer."""\n`) — Task 4 fills it in. Add the stub in Step 3 alongside the core file.

- [ ] **Step 4: Create the `scripts/letter_text.py` stub**

```python
"""Deterministic cover-letter text serializer."""
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_cover_letter_core.py -v`
Expected: PASS (all Task-2 tests). Render/validation tests come in Tasks 3 and 5.

- [ ] **Step 6: Commit**

```bash
git add scripts/cover_letter_core.py scripts/letter_text.py tests/test_cover_letter_core.py
git commit -m "feat: cover-letter core — path guard + profile/application storage"
```

---

## Task 3: Core part B — interview/draft persistence, cv_facts, validate_application

**Files:**
- Modify: `scripts/cover_letter_core.py` (add `cv_facts`, `validate_application`)
- Test: `tests/test_cover_letter_core.py` (append)

- [ ] **Step 1: Append the failing tests**

Append to `tests/test_cover_letter_core.py`:

```python
def _make_app(apps: Path, slug: str = "acme-bio-2026-06", **overrides) -> str:
    meta = {
        "company": "Acme",
        "role": "Bioinformatician",
        "language": "de",
        "date": "2026-06-03",
        "subject": "Bewerbung",
        "status": "draft",
    }
    meta.update(overrides)
    return clc.create_application(slug, job_text="x", meta=meta, apps_dir=apps)


def test_save_interview_and_draft(apps):
    slug = _make_app(apps)
    clc.save_interview(
        slug,
        {"why_company": "fit", "emphasis": ["L1"], "gaps": [
            {"requirement": "Rust", "decision": "transferable", "note": "C work"}
        ]},
        apps_dir=apps,
    )
    clc.save_draft(slug, "para one\n\npara two\n", apps_dir=apps)
    bundle = clc.read_application(slug, apps_dir=apps)
    assert bundle["interview"]["why_company"] == "fit"
    assert bundle["draft"].startswith("para one")


def test_save_interview_rejects_bad_decision(apps):
    slug = _make_app(apps)
    with pytest.raises(ValueError):
        clc.save_interview(slug, {"gaps": [{"requirement": "x", "decision": "lie"}]}, apps_dir=apps)


def test_cv_facts_is_pii_safe():
    facts = clc.cv_facts(lang="en")
    assert "personal" in facts
    blob = repr(facts)
    # Address/phone live only in content.private/ and must never surface here.
    assert "phone" not in facts["personal"]
    assert "address" not in facts["personal"]
    assert "Musterstraße" not in blob


def test_validate_application_clean(apps):
    slug = _make_app(apps)
    clc.save_draft(slug, "body\n", apps_dir=apps)
    res = clc.validate_application(slug, apps_dir=apps)
    assert res["valid"] is True
    assert res["errors"] == []


def test_validate_application_missing_required_field(apps):
    slug = _make_app(apps)
    # Corrupt application.yaml: drop the required 'subject'.
    data = clc.read_application(slug, apps_dir=apps)["application"]
    del data["subject"]
    clc._write_yaml(f"{slug}/application.yaml", data, apps_dir=apps)
    res = clc.validate_application(slug, apps_dir=apps)
    assert res["valid"] is False
    assert any("subject" in e for e in res["errors"])


def test_validate_application_bad_language(apps):
    slug = _make_app(apps, language="fr")
    res = clc.validate_application(slug, apps_dir=apps)
    assert res["valid"] is False


def test_validate_application_implausible_date_warns(apps):
    slug = _make_app(apps, date="2026-02-30")  # passes regex, not a real calendar day
    clc.save_draft(slug, "body\n", apps_dir=apps)
    res = clc.validate_application(slug, apps_dir=apps)
    assert any("date" in w for w in res["warnings"])


def test_validate_application_missing_draft_warns(apps):
    slug = _make_app(apps)
    res = clc.validate_application(slug, apps_dir=apps)
    assert any("draft" in w for w in res["warnings"])
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_cover_letter_core.py -v -k "validate_application or cv_facts or save_interview or save_draft"`
Expected: FAIL — `cv_facts` / `validate_application` not defined.

- [ ] **Step 3: Append the implementation to `scripts/cover_letter_core.py`**

```python
# --- grounding & validation -----------------------------------------------------

def cv_facts(*, lang: str = "en", target: str = "bridge") -> dict:
    """The single grounding source — a PII-safe reuse of agent_core.read_cv."""
    return agent_core.read_cv(lang=lang, target=target)


def validate_application(slug: str, *, apps_dir: Path = APPS_DIR) -> dict:
    """Schema + sanity checks. Returns {'valid', 'errors', 'warnings'}."""
    slug = _sanitize_slug(slug)
    app_dir = _safe_application_path(slug, apps_dir=apps_dir)
    if not app_dir.is_dir():
        return {"valid": False, "errors": [f"no such application: {slug}"], "warnings": []}
    app_file = app_dir / "application.yaml"
    if not app_file.exists():
        return {"valid": False, "errors": ["missing application.yaml"], "warnings": []}

    data = _read_yaml(app_file)
    errors = _schema_errors(data, APP_SCHEMA)
    warnings: list[str] = []

    raw_date = data.get("date")
    if isinstance(raw_date, str):
        try:
            _date.fromisoformat(raw_date)
        except ValueError:
            warnings.append(f"implausible date: {raw_date!r}")

    if not (app_dir / "draft.md").exists():
        warnings.append("no draft.md yet — nothing to render")

    interview_file = app_dir / "interview.yaml"
    if interview_file.exists():
        for gap in (_read_yaml(interview_file).get("gaps") or []):
            if gap.get("decision") not in _GAP_DECISIONS:
                errors.append(f"invalid gap decision {gap.get('decision')!r}")

    return {"valid": not errors, "errors": errors, "warnings": warnings}
```

- [ ] **Step 4: Run to verify they pass**

Run: `uv run pytest tests/test_cover_letter_core.py -v`
Expected: PASS (all Task-2 + Task-3 tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/cover_letter_core.py tests/test_cover_letter_core.py
git commit -m "feat: cover-letter cv_facts grounding + validate_application"
```

---

## Task 4: Deterministic text serializer + golden snapshots

**Files:**
- Modify: `scripts/letter_text.py` (replace stub with the serializer)
- Modify: `tests/test_snapshots.py` (add letter-text snapshot cases)

- [ ] **Step 1: Write the failing snapshot test**

In `tests/test_snapshots.py`, add the import near the top (after the existing `from scripts.render_text import render as render_text`):

```python
from scripts import letter_text
```

Then append these fixtures + test at the end of the file:

```python
_FIXTURE_LETTER = {
    "en": {
        "lang": "en",
        "date_display": "June 3, 2026",
        "recipient": {
            "name": "Dr. Erika Mustermann",
            "company": "Acme Genomics GmbH",
            "address": {"street": "Sample St 1", "postal_code": "68159", "city": "Mannheim"},
        },
        "subject": "Application: Bioinformatician",
        "salutation": "Dear Dr. Erika Mustermann,",
        "closing": "Sincerely,",
        "signer_name": "Jin-Ho Lee",
        "body_paragraphs": [
            "I am writing to apply for the Bioinformatician role.",
            "My pipeline work maps directly onto your reproducibility goals.",
        ],
    },
    "de": {
        "lang": "de",
        "date_display": "3. Juni 2026",
        "recipient": None,
        "subject": "Bewerbung als Bioinformatician",
        "salutation": "Sehr geehrte Damen und Herren,",
        "closing": "Mit freundlichen Grüßen",
        "signer_name": "Jin-Ho Lee",
        "body_paragraphs": [
            "mit großem Interesse habe ich Ihre Ausschreibung gelesen.",
            "Meine Pipeline-Arbeit passt zu Ihren Reproduzierbarkeitszielen.",
        ],
    },
}
_FIXTURE_SENDER = {
    "name": "Jin-Ho Lee",
    "email": "jinho.michael.lee@gmail.com",
    "location_line": "Mannheim, Germany",
}


@pytest.mark.parametrize("lang", ["en", "de"])
@pytest.mark.parametrize("flavor", ["full", "body"])
def test_letter_text_snapshot(lang, flavor, snapshot):
    out = letter_text.render(_FIXTURE_LETTER[lang], _FIXTURE_SENDER, flavor)
    assert out == snapshot.use_extension(_TextSnap)
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_snapshots.py -k letter_text -v`
Expected: FAIL — `letter_text.render` is an empty stub (AttributeError).

- [ ] **Step 3: Replace `scripts/letter_text.py` with the serializer**

```python
"""Deterministic cover-letter text serializer.

Emits two flavors from the same pre-resolved inputs:
  - "full": sender + date + recipient header + subject + salutation + body + closing
  - "body": salutation -> signature only (for EasyApply-style boxes)

PII note: the "full" sender block uses only the PUBLIC identity (name, email,
city/country). The private street/postal address is rendered only in the PDF,
which merges content.private/ at compile time and is gitignored.
"""

from __future__ import annotations

_FLAVORS = ("full", "body")


def render(letter: dict, sender: dict, flavor: str) -> str:
    """Serialize a cover letter to plain text. `flavor` in {'full', 'body'}."""
    if flavor not in _FLAVORS:
        raise ValueError(f"unknown flavor {flavor!r}; expected one of {_FLAVORS}")

    body = "\n\n".join(letter["body_paragraphs"])
    parts: list[str] = []

    if flavor == "full":
        parts.append(sender["name"])
        if sender.get("location_line"):
            parts.append(sender["location_line"])
        parts.append(sender["email"])
        parts.append("")
        parts.append(letter["date_display"])

        recipient = letter.get("recipient")
        if recipient:
            rec_lines: list[str] = []
            if recipient.get("name"):
                rec_lines.append(recipient["name"])
            if recipient.get("company"):
                rec_lines.append(recipient["company"])
            address = recipient.get("address") or {}
            if address.get("street"):
                rec_lines.append(address["street"])
            pc_city = " ".join(
                x for x in (address.get("postal_code"), address.get("city")) if x
            ).strip()
            if pc_city:
                rec_lines.append(pc_city)
            if rec_lines:
                parts.append("")
                parts.extend(rec_lines)

        parts.append("")
        parts.append(letter["subject"])
        parts.append("")

    parts.append(letter["salutation"])
    parts.append("")
    parts.append(body)
    parts.append("")
    parts.append(letter["closing"])
    parts.append(letter["signer_name"])
    return "\n".join(parts) + "\n"
```

- [ ] **Step 4: Generate the golden snapshots**

Run: `uv run pytest tests/test_snapshots.py -k letter_text --snapshot-update`
Expected: 4 snapshots written under `tests/__snapshots__/test_snapshots/`.

- [ ] **Step 5: Eyeball the generated snapshots, then verify they pass**

Read the 4 new `test_letter_text_snapshot_*.txt` files and confirm they look like real letters (sender block present in `full`, absent in `body`; DE letter has no recipient block; salutation/closing correct).

Run: `uv run pytest tests/test_snapshots.py -k letter_text -v`
Expected: PASS (4 tests).

- [ ] **Step 6: Commit**

```bash
git add scripts/letter_text.py tests/test_snapshots.py tests/__snapshots__/test_snapshots/
git commit -m "feat: deterministic cover-letter text serializer + golden snapshots"
```

---

## Task 5: Render orchestration — date/salutation/closing, assemble, render_letter

**Files:**
- Modify: `scripts/cover_letter_core.py` (add render helpers + `render_letter`)
- Test: `tests/test_cover_letter_core.py` (append)

- [ ] **Step 1: Append the failing tests**

Append to `tests/test_cover_letter_core.py`:

```python
def test_format_date():
    assert clc._format_date("2026-06-03", "en") == "June 3, 2026"
    assert clc._format_date("2026-06-03", "de") == "3. Juni 2026"
    assert clc._format_date("not-a-date", "en") == "not-a-date"  # graceful


def test_salutation_and_closing():
    assert clc._salutation("de", "Dr. Mustermann") == "Sehr geehrte/r Dr. Mustermann,"
    assert clc._salutation("de", None) == "Sehr geehrte Damen und Herren,"
    assert clc._salutation("en", "Dr. Lee") == "Dear Dr. Lee,"
    assert clc._salutation("en", None) == "Dear Hiring Manager,"
    assert clc._closing("de") == "Mit freundlichen Grüßen"
    assert clc._closing("en") == "Sincerely,"


def test_render_letter_text_writes_both_flavors(apps):
    slug = _make_app(apps, language="en", subject="Application: Bioinformatician")
    clc.save_draft(slug, "First paragraph.\n\nSecond paragraph.\n", apps_dir=apps)
    res = clc.render_letter(slug, fmt="text", apps_dir=apps)
    assert res["ok"] is True
    assert "cover-letter-en.txt" in res["rendered"]
    assert "cover-letter-en-body.txt" in res["rendered"]
    full = (apps / slug / "cover-letter-en.txt").read_text(encoding="utf-8")
    body = (apps / slug / "cover-letter-en-body.txt").read_text(encoding="utf-8")
    assert "Jin-Ho Lee" in full          # sender block in full
    assert "First paragraph." in body
    assert "Jin-Ho Lee" in body          # signer line in body
    assert "Dear Hiring Manager," in body  # no recipient name -> generic salutation


def test_render_letter_refuses_invalid(apps):
    slug = _make_app(apps, language="fr")  # invalid language fails schema
    res = clc.render_letter(slug, fmt="text", apps_dir=apps)
    assert res["ok"] is False
    assert res["errors"]
    assert res["rendered"] == []


def test_render_letter_skips_pdf_without_typst(apps, monkeypatch):
    monkeypatch.setattr(clc.shutil, "which", lambda tool: None)
    slug = _make_app(apps, language="en")
    clc.save_draft(slug, "Body.\n", apps_dir=apps)
    res = clc.render_letter(slug, fmt="all", apps_dir=apps)
    assert res["ok"] is True
    assert "cover-letter-en.pdf" in res["skipped"]
    assert "cover-letter-en.txt" in res["rendered"]


def test_render_letter_rejects_bad_fmt(apps):
    slug = _make_app(apps, language="en")
    clc.save_draft(slug, "Body.\n", apps_dir=apps)
    with pytest.raises(ValueError):
        clc.render_letter(slug, fmt="docx", apps_dir=apps)
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_cover_letter_core.py -v -k "render_letter or format_date or salutation"`
Expected: FAIL — render helpers / `render_letter` not defined.

- [ ] **Step 3: Append the implementation to `scripts/cover_letter_core.py`**

```python
# --- rendering ------------------------------------------------------------------

def _format_date(iso: str, lang: str) -> str:
    """'June 3, 2026' (en) / '3. Juni 2026' (de). Returns the raw string on parse failure."""
    try:
        d = _date.fromisoformat(iso)
    except ValueError:
        return iso
    months = _MONTHS.get(lang, _MONTHS["en"])
    month = months[d.month - 1]
    return f"{d.day}. {month} {d.year}" if lang == "de" else f"{month} {d.day}, {d.year}"


def _salutation(lang: str, name: str | None) -> str:
    if lang == "de":
        return f"Sehr geehrte/r {name}," if name else "Sehr geehrte Damen und Herren,"
    return f"Dear {name}," if name else "Dear Hiring Manager,"


def _closing(lang: str) -> str:
    return "Mit freundlichen Grüßen" if lang == "de" else "Sincerely,"


def _split_paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", (text or "").strip()) if p.strip()]


def _signer_name() -> str:
    name = cv_facts()["personal"]["name"]
    return f"{name['given']} {name['family']}"


def _public_sender(lang: str) -> dict:
    """Public identity for the text 'full' flavor — name, email, city/country only."""
    personal = cv_facts(lang=lang)["personal"]
    loc = personal.get("location") or {}
    location_line = ", ".join(x for x in (loc.get("city"), loc.get("country")) if x)
    return {
        "name": f"{personal['name']['given']} {personal['name']['family']}",
        "email": personal["email"],
        "location_line": location_line,
    }


def _assemble_letter(application: dict, draft: str | None, lang: str) -> dict:
    recipient = application.get("recipient")
    name = recipient.get("name") if recipient else None
    return {
        "lang": lang,
        "date_display": _format_date(application["date"], lang),
        "recipient": recipient,
        "subject": application["subject"],
        "salutation": _salutation(lang, name),
        "closing": _closing(lang),
        "signer_name": _signer_name(),
        "body_paragraphs": _split_paragraphs(draft),
    }


def _letter_personal(lang: str) -> dict:
    """Resolved personal block WITH the private address merged (PDF render only).

    This is the one place PII is intentionally merged — exactly like pdf/build.py
    --private. The output PDF is gitignored. Degrades to the public location block
    when content.private/ is absent.
    """
    private = PRIVATE_PATH if PRIVATE_PATH.exists() else None
    raw = load_content(CONTENT_DIR, private_path=private, lang=lang, target="bridge")
    resolved = resolve_langstrings(raw, lang=lang)
    return _to_jsonable(resolved["personal"])


def _render_pdf(slug: str, letter: dict, lang: str, *, apps_dir: Path) -> None:
    data = {"personal": _letter_personal(lang), "letter": letter, "lang": lang}
    cache_dir = REPO_ROOT / "pdf" / ".cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "letter.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    out = _safe_application_path(f"{slug}/cover-letter-{lang}.pdf", apps_dir=apps_dir)
    template = REPO_ROOT / "pdf" / "templates" / "cover-letter.typ"
    has_sig = "1" if (REPO_ROOT / "assets" / "signature.png").exists() else "0"
    proc = subprocess.run(
        [
            "typst", "compile",
            "--root", str(REPO_ROOT),
            "--input", f"lang={lang}",
            "--input", f"has-signature={has_sig}",
            str(template),
            str(out),
        ],
        capture_output=True,
        text=True,
        timeout=600,
        shell=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"typst compile failed (exit {proc.returncode}):\n{proc.stderr}")


def render_letter(slug: str, *, fmt: str = "all", apps_dir: Path = APPS_DIR) -> dict:
    """Validate-first, then render fmt in {'pdf','text','all'} into the app folder.

    PDF skips gracefully when typst is absent. Returns
    {'ok', 'errors', 'rendered': [filenames], 'skipped': [filenames]}.
    """
    if fmt not in {"pdf", "text", "all"}:
        raise ValueError(f"unknown fmt {fmt!r}; expected pdf|text|all")

    slug = _sanitize_slug(slug)
    check = validate_application(slug, apps_dir=apps_dir)
    if not check["valid"]:
        return {"ok": False, "errors": check["errors"], "rendered": [], "skipped": []}

    bundle = read_application(slug, apps_dir=apps_dir)
    lang = bundle["application"]["language"]
    letter = _assemble_letter(bundle["application"], bundle["draft"], lang)
    sender = _public_sender(lang)

    rendered: list[str] = []
    skipped: list[str] = []

    if fmt in {"text", "all"}:
        _atomic_write(
            f"{slug}/cover-letter-{lang}.txt",
            letter_text.render(letter, sender, "full"),
            apps_dir=apps_dir,
        )
        _atomic_write(
            f"{slug}/cover-letter-{lang}-body.txt",
            letter_text.render(letter, sender, "body"),
            apps_dir=apps_dir,
        )
        rendered += [f"cover-letter-{lang}.txt", f"cover-letter-{lang}-body.txt"]

    if fmt in {"pdf", "all"}:
        if shutil.which("typst") is None:
            skipped.append(f"cover-letter-{lang}.pdf")
        else:
            _render_pdf(slug, letter, lang, apps_dir=apps_dir)
            rendered.append(f"cover-letter-{lang}.pdf")

    return {"ok": True, "errors": [], "rendered": rendered, "skipped": skipped}
```

- [ ] **Step 4: Run to verify they pass**

Run: `uv run pytest tests/test_cover_letter_core.py -v`
Expected: PASS (the PDF path is covered by the skip-without-typst test; a real compile is Task 6).

- [ ] **Step 5: Commit**

```bash
git add scripts/cover_letter_core.py tests/test_cover_letter_core.py
git commit -m "feat: cover-letter render_letter orchestration (text + pdf-skip)"
```

---

## Task 6: Typst template, CLI, justfile recipe, PDF compile-smoke

**Files:**
- Create: `pdf/templates/cover-letter.typ`
- Create: `scripts/render_letter.py`
- Modify: `justfile` (add `letter` recipe)
- Test: `tests/test_letter_pdf.py`

- [ ] **Step 1: Write the failing compile-smoke test**

Create `tests/test_letter_pdf.py`:

```python
"""Compile-smoke for the cover-letter PDF: the template compiles to a real file.

Skip-guarded locally (needs typst); runs wherever typst is installed.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from scripts import cover_letter_core as clc

pytestmark = pytest.mark.skipif(
    shutil.which("typst") is None, reason="needs typst to compile the cover-letter PDF"
)

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def apps(tmp_path: Path) -> Path:
    d = tmp_path / "applications"
    d.mkdir()
    return d


def test_cover_letter_pdf_compiles(apps):
    slug = clc.create_application(
        "acme-bio-2026-06",
        job_text="# Job\n",
        meta={
            "company": "Acme Genomics GmbH",
            "role": "Bioinformatician",
            "language": "de",
            "date": "2026-06-03",
            "recipient": {
                "name": "Dr. Erika Mustermann",
                "company": "Acme Genomics GmbH",
                "address": {"street": "Musterstr. 1", "postal_code": "68159", "city": "Mannheim"},
            },
            "subject": "Bewerbung als Bioinformatician",
            "status": "draft",
        },
        apps_dir=apps,
    )
    clc.save_draft(slug, "Absatz eins.\n\nAbsatz zwei.\n", apps_dir=apps)
    res = clc.render_letter(slug, fmt="pdf", apps_dir=apps)
    assert res["ok"] is True, res["errors"]
    out = apps / slug / "cover-letter-de.pdf"
    assert out.exists()
    assert out.stat().st_size > 1000, "PDF looks empty"
```

- [ ] **Step 2: Run to verify it fails (or skips)**

Run: `uv run pytest tests/test_letter_pdf.py -v`
Expected: FAIL if typst is installed (template missing → compile error); SKIPPED if typst absent. If skipped locally, proceed — CI will exercise it.

- [ ] **Step 3: Create `pdf/templates/cover-letter.typ`**

```typst
#import "../styles.typ": *
#import "header.typ": header

#let data = json("../.cache/letter.json")
#let lang = sys.inputs.at("lang", default: "en")
#let has-signature = sys.inputs.at("has-signature", default: "0") == "1"
#let letter = data.letter

#set page(paper: "a4", margin: page-margin)
#set text(font: font-family, size: size-body, fill: body-color)
#set par(leading: 0.6em, justify: true)

// Letterhead — reuses the CV header so the letter visually matches the CV.
#header(data.personal)
#v(10pt)

// Right-aligned date (DIN 5008).
#align(right)[#text(size: size-body)[#letter.date_display]]
#v(6pt)

// Recipient address block.
#if letter.recipient != none {
  let r = letter.recipient
  if r.name != none [#r.name \ ]
  if r.company != none [#r.company \ ]
  if r.address != none {
    let a = r.address
    if "street" in a [#a.street \ ]
    let pc-city = ()
    if "postal_code" in a { pc-city.push(a.postal_code) }
    if "city" in a { pc-city.push(a.city) }
    if pc-city.len() > 0 [#pc-city.join(" ")]
  }
  v(14pt)
}

// Bold subject (Betreff).
#text(weight: 700)[#letter.subject]
#v(10pt)

// Salutation.
#letter.salutation
#v(8pt)

// Body paragraphs.
#for para in letter.body_paragraphs {
  para
  parbreak()
}

#v(6pt)
// Closing + optional signature image + typed name.
#letter.closing
#v(4pt)
#if has-signature {
  image("/assets/signature.png", height: 36pt)
  v(2pt)
}
#letter.signer_name
```

- [ ] **Step 4: Create `scripts/render_letter.py` (thin CLI)**

```python
"""CLI: render a cover letter for an application slug.

Wraps cover_letter_core.render_letter so `just letter <slug>` works. Validates
first; PDF skips gracefully when typst is absent.
"""

from __future__ import annotations

import argparse
import sys

from scripts.cover_letter_core import render_letter


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="render_letter", description=__doc__)
    parser.add_argument("slug", help="Application slug (folder under applications/)")
    parser.add_argument("--fmt", choices=("pdf", "text", "all"), default="all")
    args = parser.parse_args(argv)

    result = render_letter(args.slug, fmt=args.fmt)
    for name in result["rendered"]:
        print(f"wrote applications/{args.slug}/{name}", file=sys.stderr)
    for name in result["skipped"]:
        print(f"skipped {name} (tool unavailable)", file=sys.stderr)
    if not result["ok"]:
        for err in result["errors"]:
            print(f"error: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Add the `letter` recipe to `justfile`**

Add after the `build-text-targets` block (before the llms recipe is fine — keep it near the other build recipes):

```make
# Render a cover letter (validate-first) → applications/<slug>/cover-letter-*.{pdf,txt}
letter slug:
    uv run python -m scripts.render_letter {{slug}}
```

- [ ] **Step 6: Run the compile-smoke test to verify it passes**

Run: `uv run pytest tests/test_letter_pdf.py -v`
Expected: PASS if typst is installed; SKIPPED otherwise (CI runs it).

- [ ] **Step 7: Commit**

```bash
git add pdf/templates/cover-letter.typ scripts/render_letter.py justfile tests/test_letter_pdf.py
git commit -m "feat: cover-letter Typst template + CLI + just letter recipe"
```

---

## Task 7: The cover-letter skill + drift-guard

**Files:**
- Create: `.claude/skills/cover-letter/SKILL.md`
- Create: `.claude/skills/cover-letter/reference.md`
- Test: `tests/test_cover_letter_skill_docs.py`

- [ ] **Step 1: Write the failing drift-guard test**

Create `tests/test_cover_letter_skill_docs.py`:

```python
"""Drift-guards for the cover-letter skill docs (justfile recipes + schema fields)."""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO_ROOT / ".claude" / "skills" / "cover-letter"
JUSTFILE = REPO_ROOT / "justfile"
SCHEMA_DIR = REPO_ROOT / "schema"


def _justfile_recipes() -> set[str]:
    recipes = set()
    for line in JUSTFILE.read_text(encoding="utf-8").splitlines():
        if line[:1].isspace() or line.startswith("#"):
            continue
        m = re.match(r"^([a-z][a-z0-9-]*)(\s+[^:]*)?:", line)
        if m:
            recipes.add(m.group(1))
    return recipes


def _docs_text() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in SKILL_DIR.glob("*.md"))


def _schema_props(name: str) -> set[str]:
    schema = json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))
    return set(schema.get("properties", {}))


def test_skill_docs_exist():
    assert (SKILL_DIR / "SKILL.md").is_file()
    assert (SKILL_DIR / "reference.md").is_file()


def test_skill_recipes_exist():
    referenced = set(re.findall(r"just ([a-z][a-z0-9-]*)", _docs_text()))
    missing = referenced - _justfile_recipes()
    assert not missing, f"skill docs reference unknown just recipes: {missing}"


def test_skill_documents_application_fields():
    ref = (SKILL_DIR / "reference.md").read_text(encoding="utf-8")
    missing = [f for f in _schema_props("application.schema.json") if f not in ref]
    assert not missing, f"reference.md is missing application fields: {missing}"


def test_skill_documents_profile_fields():
    ref = (SKILL_DIR / "reference.md").read_text(encoding="utf-8")
    missing = [f for f in _schema_props("profile.schema.json") if f not in ref]
    assert not missing, f"reference.md is missing profile fields: {missing}"


def test_skill_frontmatter_has_name_and_description():
    text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    assert text.startswith("---")
    fm = text.split("---", 2)[1]
    assert re.search(r"^name:\s*\S", fm, re.M)
    assert re.search(r"^description:\s*\S", fm, re.M)
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_cover_letter_skill_docs.py -v`
Expected: FAIL — skill docs do not exist yet.

- [ ] **Step 3: Create `.claude/skills/cover-letter/SKILL.md`**

```markdown
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
7. **Render** — `just letter <slug>` → validates, then writes the PDF + full and
   body-only text files into the application folder.

See `reference.md` for the file/field map, the `just` recipe, and DIN 5008 / EN
business-letter conventions.
```

- [ ] **Step 4: Create `.claude/skills/cover-letter/reference.md`**

> The drift-guard requires every `application.schema.json` and `profile.schema.json`
> property name to appear verbatim in this file. The tables below include them all.

```markdown
# Cover letter reference — files, fields, conventions

## Just recipes
| Recipe | Does |
|---|---|
| `just letter <slug>` | Validate-first, then render PDF + text into `applications/<slug>/` (PDF skips if Typst is absent). |
| `just validate` | Validate the CV content tree (grounding source). |

## Folder layout (all under gitignored `applications/`)
- `profile.yaml` — evergreen answers, reused across every application.
- `<slug>/job.md` — the pasted job description.
- `<slug>/application.yaml` — per-job metadata (fields below).
- `<slug>/interview.yaml` — per-job answers + gap decisions.
- `<slug>/draft.md` — editable letter body (the working step).
- `<slug>/cover-letter-<lang>.pdf` / `.txt` / `-body.txt` — rendered output.

Copy shapes from the committed `applications.example/` folder.

## `application.yaml` fields
| Field | Meaning |
|---|---|
| `company` | Employer name. |
| `role` | Position title. |
| `language` | Letter language: `en` or `de` (defaults to JD language). |
| `date` | Letter date, ISO `YYYY-MM-DD`. |
| `recipient` | Optional address block: `name`, `company`, `address`. |
| `subject` | Betreff / subject line (bold in the PDF). |
| `source` | Where the job was found (e.g. LinkedIn). |
| `url` | Job posting URL. |
| `status` | `draft` / `sent` / `interview` / `rejected` / `offer`. |

## `profile.yaml` fields (evergreen)
| Field | Meaning |
|---|---|
| `motivation` | Why this field / what drives you (`{ en, de }`). |
| `work_style` | How you work (`{ en, de }`). |
| `availability` | Notice period / earliest start. |
| `salary_expectation` | Range — **context only**, never rendered unless the JD asks + user confirms. |
| `relocation` | Willingness / constraints. |
| `preferences` | Company size, remote, domain (`{ en, de }`). |

## `interview.yaml` fields (per job)
- `why_company` — why this company/role.
- `emphasis` — CV project ids or free text to foreground.
- `gaps` — list of `{ requirement, decision, note }`; `decision` ∈
  `transferable` / `omit` / `example`.
- `notes` — extra context for the draft.

## Letter conventions
- **DIN 5008 (de):** sender letterhead, right-aligned date, recipient block, bold
  Betreff, salutation (`Sehr geehrte Damen und Herren,` or `Sehr geehrte/r <name>,`),
  body, `Mit freundlichen Grüßen`, typed name.
- **English:** same structure; salutation `Dear Hiring Manager,` / `Dear <name>,`,
  closing `Sincerely,`.
- The salutation and closing are added deterministically at render time — `draft.md`
  holds only the body paragraphs.
```

- [ ] **Step 5: Run to verify it passes**

Run: `uv run pytest tests/test_cover_letter_skill_docs.py -v`
Expected: PASS (5 tests).

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/cover-letter/ tests/test_cover_letter_skill_docs.py
git commit -m "feat: cover-letter skill (interview flow + grounding + drift-guard)"
```

---

## Task 8: Documentation — update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add the Phase 11 row to the Phasing table**

After the Phase 10 row, add:

```markdown
| 11 | Cover-letter generator (interview + JD → tailored letter, PDF + text) | ✅ Done (merged <DATE>, PR #<N>, commit `<HASH>`) |
```

(Fill `<DATE>`/`<N>`/`<HASH>` at merge time; until then use `In review (PR #<N>)`.)

- [ ] **Step 2: Update the Layout block**

In the ``` ``` layout fence, add these entries:

```text
applications/             gitignored per-application cover-letter material (profile + per-job folders)
applications.example/     committed template showing the applications/ shape
schema/application.schema.json  schema for application.yaml
schema/profile.schema.json      schema for the evergreen profile.yaml
.claude/skills/cover-letter/    committed Claude skill (cover-letter interview + render)
```

And append to the `scripts/` line: `cover_letter_core.py, letter_text.py, render_letter.py`.
And to the `pdf/` note, mention `templates/cover-letter.typ` (DIN 5008 / EN letter).

- [ ] **Step 3: Add the `just letter` command**

In the Commands block, add:

```bash
just letter <slug>     # render a cover letter → applications/<slug>/cover-letter-*.{pdf,txt}
```

- [ ] **Step 4: Add a Conventions note**

Add a bullet under Conventions:

```markdown
- **Cover letters are a read-only CV consumer.** `applications/` is gitignored
  (this repo is public); the generator reads `content/` via `cover_letter_core.cv_facts`
  (PII-safe `agent_core.read_cv`) and writes only under `applications/`. PDFs merge
  `content.private/` at render time and stay gitignored. Never commit `applications/`.
```

- [ ] **Step 5: Add to "Files to read before any phase"**

```markdown
- `docs/superpowers/specs/2026-06-03-phase-11-cover-letter-design.md` — Phase 11 design spec (cover-letter generator)
- `docs/superpowers/plans/2026-06-03-phase-11-cover-letter.md` — implementation plan for the cover-letter generator (#65)
```

- [ ] **Step 6: Update "Local-only files (not in git)"**

Add:

```markdown
- `applications/` — per-application cover-letter material (job descriptions, drafts, rendered letters). Gitignored; mirror the shape in `applications.example/`.
- `assets/signature.png` — handwritten signature for the cover-letter PDF, included only when present (mirrors the optional `--photo` pattern). Gitignored.
```

- [ ] **Step 7: Run the full gates**

Run: `uv run python -m scripts.validate && uv run pytest -q && uv run ruff check . && uv run ruff format --check scripts/cover_letter_core.py scripts/letter_text.py scripts/render_letter.py tests/test_cover_letter_core.py tests/test_cover_letter_schemas.py tests/test_cover_letter_skill_docs.py tests/test_letter_pdf.py`
Expected: validate OK; all tests pass; ruff check clean; ruff format clean on the new files.

> **Gotcha (from Phase 10):** subagent implementers run `ruff check` but not `ruff format`. Run `uv run ruff format` on every new file before merge, or the format gate bites. Also run `uv run ruff format --check tests/test_snapshots.py justfile`-adjacent edits.

- [ ] **Step 8: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: record Phase 11 cover-letter generator in CLAUDE.md"
```

---

## Self-review (completed during planning)

**Spec coverage:**
- §2 storage (gitignored overlay + example) → Task 1. §2 output (PDF + text + draft) → Tasks 4–6. §2 interview (evergreen profile + per-job) → core Tasks 2–3 + skill Task 7. §2 grounding (never fabricate, flag gaps) → `validate_application` gap-decision check (Task 3) + skill grounding rules (Task 7). §2 language (both, JD-default) → `language` enum + salutation/closing maps (Task 5) + skill (Task 7). §2 form factor (skill + core, MCP deferred) → Tasks 2–7; MCP not built (§10). §2 output location (in-folder) → `render_letter` writes into `apps_dir/<slug>/` (Task 5). §2 tracking (`status`) → schema enum (Task 1).
- §4 data model → schemas + examples (Task 1), CRUD (Tasks 2–3). §4.4 PII/salary → `_letter_personal` merge at render (Task 5) + skill rules (Task 7).
- §5 core functions → all present across Tasks 2/3/5. `_safe_application_path` (Task 2).
- §6 skill 7-step flow + grounding rules → Task 7.
- §7 rendering: Typst template + text serializer (two flavors) + `just letter` → Tasks 4/6.
- §8 testing: TDD core, golden snapshots for text, PDF compile-smoke, skill drift-guard → Tasks 2/3/5 + 4 + 6 + 7.
- §9 conventions / §10 out-of-scope → honored; MCP deliberately not built.

**Placeholder scan:** none — every code step is complete. The only intentional fill-in is the CLAUDE.md merge hash/PR number (unknown until merge), flagged explicitly.

**Type consistency:** `render_letter` returns `{ok, errors, rendered, skipped}` everywhere (Tasks 5/6/CLI). `validate_application`/`validate_cv`-style returns `{valid, errors, warnings}`. `letter_text.render(letter, sender, flavor)` signature is identical in Task 4 (definition), the snapshot test, and Task 5 (callers). The `letter` dict contract (`lang, date_display, recipient, subject, salutation, closing, signer_name, body_paragraphs`) matches between `_assemble_letter` (Task 5), the snapshot fixture (Task 4), and the Typst template (Task 6). `_safe_application_path` is the single write gate used by `_atomic_write`, `create_application`, and `_render_pdf`.
