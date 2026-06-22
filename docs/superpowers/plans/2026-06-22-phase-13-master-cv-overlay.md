# Phase 13 — `master-cv/` overlay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce a gitignored `master-cv/` overlay holding the unfiltered superset of Jin-Ho Lee's history, feeding the digital twin and a new human-lookup export, without touching the sharp `content/` CV or any existing renderer.

**Architecture:** A new `master_cv_loader` parses three plain files (`timeline.yaml`, `inventory.yaml`, `narrative/*.md`) from an overlay dir resolved via the `MASTER_CV_DIR` env (default `<repo>/master-cv`), returning `None` when absent. One shared `profile_union.full_profile(content, pubs, master_cv)` helper assembles the CV + master-cv union Markdown; both `render_chat_context` (twin) and a new `render_master_cv` (the `dist/master-cv.md` lookup artifact) call it. When the overlay is absent, output is byte-identical to today (graceful-absence proof). The overlay is `.gitignore`d and blocked by `check_pii`; a committed synthetic `master-cv.example/` doubles as the test fixture.

**Tech Stack:** Python 3 (ruamel.yaml, jsonschema, syrupy snapshots), pytest, `just` recipes. No new dependencies.

## Global Constraints

- **No changes to `content/` or the CV renderers** (PDF/web/JSON Resume/JSON-LD/plain-text/llms.txt). CV stays sharp. Deferred CV fixes are issue [#93](https://github.com/Jin-HoMLee/jin-ho-lee-cv/issues/93), not this phase.
- **`master-cv/` is never committed.** `.gitignore` + `check_pii.py` both block it. Only the synthetic `master-cv.example/` is committed.
- **No test ever reads the real `master-cv/`.** Every test resolves the overlay through `MASTER_CV_DIR`; a conftest autouse fixture redirects that env to an absent sentinel by default, and a session guard fails the run if the real dir is mutated.
- **Graceful absence is byte-exact.** `render_chat_context.render()` with no overlay must produce output identical to today's committed snapshot (CI has no overlay and must stay green).
- **Light, permissive schema.** `id` + `type` required, `type` is an enum, dates are `YYYY` / `YYYY-MM` / null; `additionalProperties: true` everywhere (personal DB, not ATS).
- **DRY:** exactly one union helper — `profile_union.full_profile`. The two renderers differ only by output destination/purpose.
- **References are not duplicated.** They stay in `applications/references.md` per existing policy.
- **No `--no-verify`, no Claude attribution trailers, atomic commits, TDD for non-trivial Python.**

---

### Task 1: master-cv JSON Schema

**Files:**
- Create: `schema/master-cv.schema.json`
- Test: `tests/test_master_cv_schema.py`

**Interfaces:**
- Produces: a schema file with `$defs.timeline` (array), `$defs.inventory` (object of string-arrays), and `$defs.TimelineEntry`. Validated using the existing `scripts.validate._validator_for(def_name, schema_path)` helper, exactly like `cv.schema.json`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_master_cv_schema.py
"""Schema validation for the master-cv/ overlay (timeline + inventory)."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.validate import ValidationError, _validator_for

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / "schema" / "master-cv.schema.json"


def _errors(def_name, data):
    validator = _validator_for(def_name, SCHEMA_PATH)
    return sorted(validator.iter_errors(data), key=lambda e: list(e.path))


def test_valid_timeline_entry_passes():
    data = [{"id": "imp-vienna-2019", "type": "research", "start": "2019-08", "end": "2019-10"}]
    assert _errors("timeline", data) == []


def test_timeline_entry_requires_id_and_type():
    assert _errors("timeline", [{"title": "no id or type"}])


def test_timeline_rejects_unknown_type():
    assert _errors("timeline", [{"id": "x", "type": "not-a-type"}])


def test_timeline_accepts_year_only_and_null_dates():
    data = [{"id": "x", "type": "certificate", "start": "2099", "end": None}]
    assert _errors("timeline", data) == []


def test_timeline_rejects_malformed_date():
    assert _errors("timeline", [{"id": "x", "type": "award", "start": "2099-13"}])


def test_timeline_allows_extra_type_specific_fields():
    data = [{"id": "x", "type": "education", "field": "Bioinformatics", "thesis": "T"}]
    assert _errors("timeline", data) == []


def test_valid_inventory_passes():
    assert _errors("inventory", {"programming": ["Python", "R"], "domains": ["GenAI"]}) == []


def test_inventory_rejects_non_string_list_values():
    assert _errors("inventory", {"programming": [1, 2, 3]})


def test_validator_for_unknown_def_raises():
    with pytest.raises(ValidationError):
        _validator_for("nonexistent", SCHEMA_PATH)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_master_cv_schema.py -v`
Expected: FAIL — `FileNotFoundError` / cannot open `schema/master-cv.schema.json`.

- [ ] **Step 3: Write the schema**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Jin-Ho Lee master-CV overlay schema",
  "$defs": {
    "DateLoose": {
      "oneOf": [
        { "type": "string", "pattern": "^[0-9]{4}(-(0[1-9]|1[0-2]))?$" },
        { "type": "null" }
      ],
      "description": "YYYY or YYYY-MM, or null for undated/ongoing"
    },
    "TimelineEntry": {
      "type": "object",
      "properties": {
        "id": { "type": "string", "pattern": "^[a-z0-9]+(-[a-z0-9]+)*$" },
        "type": {
          "type": "string",
          "enum": ["employment", "research", "internship", "education", "certificate", "award", "volunteering"]
        },
        "title": { "type": "string" },
        "org": { "type": "string" },
        "location": { "type": "string" },
        "start": { "$ref": "#/$defs/DateLoose" },
        "end": { "$ref": "#/$defs/DateLoose" },
        "tags": { "type": "array", "items": { "type": "string" } },
        "summary": { "type": "string" }
      },
      "required": ["id", "type"],
      "additionalProperties": true
    },
    "timeline": {
      "type": "array",
      "items": { "$ref": "#/$defs/TimelineEntry" }
    },
    "inventory": {
      "type": "object",
      "additionalProperties": {
        "type": "array",
        "items": { "type": "string" }
      }
    }
  }
}
```

Note: `_validator_for` builds `{**definition, "$defs": full["$defs"]}` so the `$ref`s resolve. `timeline`/`inventory` must live as top-level `$defs` keys (not just `TimelineEntry`) for `_validator_for("timeline", …)` to find them.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_master_cv_schema.py -v`
Expected: PASS (all 9 tests).

- [ ] **Step 5: Commit**

```bash
git add schema/master-cv.schema.json tests/test_master_cv_schema.py
git commit -m "feat(13): master-cv overlay JSON Schema (timeline + inventory)"
```

---

### Task 2: committed synthetic `master-cv.example/` template

**Files:**
- Create: `master-cv.example/timeline.yaml`
- Create: `master-cv.example/inventory.yaml`
- Create: `master-cv.example/narrative/career-story.md`
- Create: `master-cv.example/narrative/personal.md`
- Test: `tests/test_master_cv_example.py`

**Interfaces:**
- Produces: a committed, **synthetic** overlay that (a) documents the `master-cv/` shape for the user and (b) is the deterministic fixture reused by the loader, validate, union, and snapshot tests via `MASTER_CV_DIR`. It must exercise every section renderer: multiple `type` values, a multi-key inventory, and ≥1 narrative file.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_master_cv_example.py
"""The committed synthetic master-cv.example/ must validate against the schema."""

from __future__ import annotations

from pathlib import Path

from ruamel.yaml import YAML

from scripts.validate import _validator_for

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_DIR = REPO_ROOT / "master-cv.example"
SCHEMA_PATH = REPO_ROOT / "schema" / "master-cv.schema.json"
yaml = YAML(typ="safe")


def _load(name):
    return yaml.load((EXAMPLE_DIR / name).read_text(encoding="utf-8"))


def test_example_timeline_validates():
    validator = _validator_for("timeline", SCHEMA_PATH)
    assert list(validator.iter_errors(_load("timeline.yaml"))) == []


def test_example_inventory_validates():
    validator = _validator_for("inventory", SCHEMA_PATH)
    assert list(validator.iter_errors(_load("inventory.yaml"))) == []


def test_example_covers_multiple_entry_types():
    types = {e["type"] for e in _load("timeline.yaml")}
    # Must exercise the breadth the real overlay carries.
    assert {"research", "internship", "education", "certificate", "award", "volunteering"} <= types


def test_example_has_narrative_files():
    stems = {p.stem for p in (EXAMPLE_DIR / "narrative").glob("*.md")}
    assert {"career-story", "personal"} <= stems
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_master_cv_example.py -v`
Expected: FAIL — `master-cv.example/` does not exist.

- [ ] **Step 3: Create the synthetic template files**

`master-cv.example/timeline.yaml`:

```yaml
# Synthetic template for the gitignored master-cv/ overlay.
# Copy this directory to `master-cv/` and replace every value with your real
# history. `master-cv/` is gitignored; `master-cv.example/` (this dir) is committed
# and must contain SYNTHETIC data only. Schema: schema/master-cv.schema.json.
#
# Flat chronological list. Required per entry: id (kebab-case), type.
# type ∈ employment|research|internship|education|certificate|award|volunteering
# dates: "YYYY" or "YYYY-MM" or null (null end ⇒ ongoing). Extra fields allowed.
- id: example-research-2099
  type: research
  title: "Example Doctoral Researcher"
  org: "Example Institute of Synthetic Studies"
  location: "Example City, Exampleland"
  start: "2099-01"
  end: "2099-06"
  tags: ["example-domain", "synthetic-method"]
  summary: "Synthetic placeholder describing example research work."
- id: example-internship-2098
  type: internship
  title: "Example Data Intern"
  org: "Example Analytics GmbH"
  location: "Example City"
  start: "2098-07"
  end: "2098-09"
  tags: ["sql", "dashboards"]
  summary: "Synthetic placeholder internship summary."
- id: example-msc-2097
  type: education
  title: "M.Sc. Example Science"
  org: "Example University"
  location: "Example City"
  start: "2095-10"
  end: "2097-09"
  field: "Example Field"
  thesis: "A Synthetic Thesis Title"
  summary: "Synthetic degree record with type-specific field/thesis keys."
- id: example-cert-cloud
  type: certificate
  title: "Example Cloud Certificate"
  org: "Example Cloud"
  issuer: "Example Cloud"
  status: "in-progress"
  start: "2099"
  summary: "Synthetic in-progress certificate (year-only date)."
- id: example-award-hack
  type: award
  title: "Example Hackathon Winner"
  org: "Example Hack 2099"
  start: "2099-03"
  summary: "Synthetic award record."
- id: example-volunteering
  type: volunteering
  title: "Example Volunteer Mentor"
  org: "Example Community"
  start: "2096"
  end: null
  summary: "Synthetic ongoing volunteering (null end)."
```

`master-cv.example/inventory.yaml`:

```yaml
# Full skill/tool/domain/industry SUPERSET (a generous reservoir, not the sharp CV).
# Keys are free-form; values must be string lists. SYNTHETIC data only.
programming: ["Example-Lang", "Pseudocode"]
ml_ai: ["example-ml-lib", "example-nn-framework"]
data_eng: ["ExampleQuery", "example-orchestrator", "Docker"]
databases: ["ExampleDB"]
cloud: ["Example Cloud"]
domains: ["Example Domain A", "Example Domain B"]
industries: ["Example Industry"]
```

`master-cv.example/narrative/career-story.md`:

```markdown
# Career story (synthetic template)

Replace this with the warm, first-person throughline a CV can't hold: what moved
you between fields, the motivation behind the pivots, the threads that connect
otherwise-separate roles. The digital twin reads this verbatim to answer "why"
questions with your real voice.

This file is committed only as a SYNTHETIC example. Your real version lives in the
gitignored `master-cv/narrative/` and never enters the repo.
```

`master-cv.example/narrative/personal.md`:

```markdown
# Personal (synthetic template)

Interests, languages spoken and to what level, anecdotes, the human detail that
makes a conversation feel like a conversation. SYNTHETIC placeholder text only.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_master_cv_example.py -v`
Expected: PASS (all 4 tests).

- [ ] **Step 5: Commit**

```bash
git add master-cv.example tests/test_master_cv_example.py
git commit -m "feat(13): committed synthetic master-cv.example/ template + fixture"
```

---

### Task 3: `master_cv_loader` + test isolation guards

**Files:**
- Create: `scripts/master_cv_loader.py`
- Modify: `tests/conftest.py` (add autouse env redirect + session mutation guard)
- Test: `tests/test_master_cv_loader.py`

**Interfaces:**
- Produces:
  - `MasterCV` — frozen dataclass: `timeline: list[dict]`, `inventory: dict[str, list[str]]`, `narrative: dict[str, str]` (filename stem → markdown text).
  - `load_master_cv(path: Path | None = None) -> MasterCV | None` — resolves dir from `path`, else `MASTER_CV_DIR` env, else `<repo>/master-cv`; returns `None` when the dir is absent; parses the three sources (each optional within a present dir).
- Consumes: nothing from earlier tasks (schema not enforced here — validation lives in `validate.py`, Task 4).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_master_cv_loader.py
"""Loader for the gitignored master-cv/ overlay."""

from __future__ import annotations

from pathlib import Path

from scripts.master_cv_loader import MasterCV, load_master_cv


def _seed(dir_: Path):
    dir_.mkdir(parents=True, exist_ok=True)
    (dir_ / "timeline.yaml").write_text(
        '- id: a-b\n  type: research\n  title: "T"\n  start: "2099-01"\n', encoding="utf-8"
    )
    (dir_ / "inventory.yaml").write_text('programming: ["Python"]\n', encoding="utf-8")
    nd = dir_ / "narrative"
    nd.mkdir()
    (nd / "career-story.md").write_text("# Story\n\nbody\n", encoding="utf-8")


def test_returns_none_when_dir_absent(tmp_path):
    assert load_master_cv(tmp_path / "nope") is None


def test_parses_present_overlay(tmp_path):
    _seed(tmp_path / "mcv")
    mcv = load_master_cv(tmp_path / "mcv")
    assert isinstance(mcv, MasterCV)
    assert mcv.timeline[0]["id"] == "a-b"
    assert mcv.inventory == {"programming": ["Python"]}
    assert "career-story" in mcv.narrative
    assert mcv.narrative["career-story"].startswith("# Story")


def test_resolves_from_env(tmp_path, monkeypatch):
    _seed(tmp_path / "mcv")
    monkeypatch.setenv("MASTER_CV_DIR", str(tmp_path / "mcv"))
    mcv = load_master_cv()
    assert mcv is not None and mcv.timeline[0]["type"] == "research"


def test_present_dir_with_missing_files_is_tolerant(tmp_path):
    (tmp_path / "mcv").mkdir()
    mcv = load_master_cv(tmp_path / "mcv")
    assert mcv == MasterCV(timeline=[], inventory={}, narrative={})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_master_cv_loader.py -v`
Expected: FAIL — `ModuleNotFoundError: scripts.master_cv_loader`.

- [ ] **Step 3: Write the loader**

```python
# scripts/master_cv_loader.py
"""Load the gitignored master-cv/ overlay (the unfiltered life-database superset).

Mirrors the content.private/ pattern: present on the user's machine, never committed,
gracefully absent (returns None) on CI and fresh clones. Path resolves from the
MASTER_CV_DIR env (default <repo>/master-cv) so tests point it at a fixture overlay —
the same override shape as CV_PRIVATE_YAML.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from ruamel.yaml import YAML

yaml = YAML(typ="safe")

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DIR = REPO_ROOT / "master-cv"


@dataclass(frozen=True)
class MasterCV:
    timeline: list[dict]
    inventory: dict[str, list[str]]
    narrative: dict[str, str]  # filename stem -> markdown text


def _resolve_dir(path: Path | None) -> Path:
    if path is not None:
        return Path(path)
    env = os.environ.get("MASTER_CV_DIR")
    return Path(env) if env else DEFAULT_DIR


def load_master_cv(path: Path | None = None) -> MasterCV | None:
    """Parse the overlay dir; return None when it is absent."""
    base = _resolve_dir(path)
    if not base.is_dir():
        return None

    timeline: list[dict] = []
    tl = base / "timeline.yaml"
    if tl.exists():
        timeline = yaml.load(tl.read_text(encoding="utf-8")) or []

    inventory: dict[str, list[str]] = {}
    iv = base / "inventory.yaml"
    if iv.exists():
        inventory = yaml.load(iv.read_text(encoding="utf-8")) or {}

    narrative: dict[str, str] = {}
    nd = base / "narrative"
    if nd.is_dir():
        for md in sorted(nd.glob("*.md")):
            narrative[md.stem] = md.read_text(encoding="utf-8")

    return MasterCV(timeline=timeline, inventory=inventory, narrative=narrative)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_master_cv_loader.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Add the conftest isolation guards**

Edit `tests/conftest.py`. Add a `REAL_MASTER_CV` constant near the other path constants:

```python
REAL_MASTER_CV = REPO_ROOT / "master-cv"
```

Then add two fixtures (place after `real_private_yaml_guard`):

```python
@pytest.fixture(autouse=True)
def _isolate_master_cv(monkeypatch):
    """Default every test away from the real (gitignored) master-cv/ overlay.

    No test may read the user's real personal superset. Tests that need a synthetic
    overlay call monkeypatch.setenv('MASTER_CV_DIR', <fixture>) themselves, which wins
    over this default (the test's setenv runs after this autouse fixture).
    """
    monkeypatch.setenv("MASTER_CV_DIR", str(REPO_ROOT / "master-cv-TEST-SENTINEL-absent"))


@pytest.fixture(scope="session", autouse=True)
def real_master_cv_guard():
    """Fail the session if any test mutates the real master-cv/ overlay (issue #92).

    Like real_private_yaml_guard: the overlay is user data outside git's protection.
    """
    def _snapshot():
        return sorted(p.name for p in REAL_MASTER_CV.iterdir()) if REAL_MASTER_CV.is_dir() else None

    before = _snapshot()
    yield
    if _snapshot() != before:
        raise AssertionError(
            "A test mutated the real master-cv/ overlay. Tests must point MASTER_CV_DIR "
            "at a fixture under tmp_path or master-cv.example/, never the real dir (issue #92)."
        )
```

- [ ] **Step 6: Run the full suite to confirm the autouse fixture breaks nothing**

Run: `uv run pytest tests/test_master_cv_loader.py tests/test_render_chat_context.py -v`
Expected: PASS. (The loader tests pass their own `path=` so the env sentinel is irrelevant to them; chat-context tests are unaffected because the overlay isn't wired in yet.)

- [ ] **Step 7: Commit**

```bash
git add scripts/master_cv_loader.py tests/test_master_cv_loader.py tests/conftest.py
git commit -m "feat(13): master_cv_loader + test isolation guards for the overlay"
```

---

### Task 4: validate `master-cv/` when present

**Files:**
- Modify: `scripts/validate.py`
- Test: `tests/test_validate.py` (append)

**Interfaces:**
- Produces: `validate_master_cv(master_cv_dir: Path, schema_path: Path) -> list[FileError]` — validates `timeline.yaml` against the `timeline` def and `inventory.yaml` against the `inventory` def of `schema/master-cv.schema.json`; returns `[]` when the dir is absent (graceful skip). `narrative/*.md` is free-form and not validated. `main()` wires it in using the env-resolved dir.
- Consumes: `_validator_for` and `FileError` from `scripts.validate`; schema from Task 1.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_validate.py`:

```python
def test_validate_master_cv_absent_is_clean(tmp_path):
    from scripts.validate import validate_master_cv

    schema = REPO_ROOT / "schema" / "master-cv.schema.json"
    assert validate_master_cv(tmp_path / "nope", schema) == []


def test_validate_master_cv_example_is_clean():
    from scripts.validate import validate_master_cv

    schema = REPO_ROOT / "schema" / "master-cv.schema.json"
    assert validate_master_cv(REPO_ROOT / "master-cv.example", schema) == []


def test_validate_master_cv_catches_bad_type(tmp_path):
    from scripts.validate import validate_master_cv

    schema = REPO_ROOT / "schema" / "master-cv.schema.json"
    (tmp_path / "timeline.yaml").write_text(
        '- id: x\n  type: not-a-real-type\n', encoding="utf-8"
    )
    errors = validate_master_cv(tmp_path, schema)
    assert errors and any("timeline.yaml" in str(e) for e in errors)
```

Confirm `tests/test_validate.py` already defines `REPO_ROOT` (it does, near the top). If a given test file scopes it differently, use `Path(__file__).resolve().parent.parent`.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_validate.py -k master_cv -v`
Expected: FAIL — `ImportError: cannot import name 'validate_master_cv'`.

- [ ] **Step 3: Implement `validate_master_cv` and wire it into `main()`**

Add to `scripts/validate.py` (after `_validate_periods`):

```python
def validate_master_cv(master_cv_dir: Path, schema_path: Path) -> list[FileError]:
    """Validate the master-cv overlay if present; graceful skip when absent.

    timeline.yaml → 'timeline' def, inventory.yaml → 'inventory' def. narrative/*.md
    is free-form and unchecked. Absent dir or absent file ⇒ no error.
    """
    if not master_cv_dir.is_dir():
        return []
    errors: list[FileError] = []
    for filename, def_name in (("timeline.yaml", "timeline"), ("inventory.yaml", "inventory")):
        path = master_cv_dir / filename
        if not path.exists():
            continue
        try:
            data = _load_yaml(path)
            validator = _validator_for(def_name, schema_path)
            schema_errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
            if schema_errors:
                joined = "; ".join(
                    f"{'.'.join(str(p) for p in e.path) or '<root>'}: {e.message}"
                    for e in schema_errors
                )
                errors.append(FileError(path, joined))
        except Exception as e:  # malformed YAML, etc.
            errors.append(FileError(path, str(e)))
    return errors
```

Then, in `main()`, after the CV `errors = validate_tree(...)` line and before the `date_warnings` loop, add:

```python
    import os

    master_cv_dir = Path(os.environ.get("MASTER_CV_DIR", repo_root / "master-cv"))
    master_cv_schema = repo_root / "schema" / "master-cv.schema.json"
    errors.extend(validate_master_cv(master_cv_dir, master_cv_schema))
```

(`repo_root` is already defined at the top of `main()`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_validate.py -k master_cv -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Confirm `just validate` still passes with no overlay**

Run: `MASTER_CV_DIR=/tmp/definitely-absent uv run python -m scripts.validate`
Expected: `OK: all content files validate` (exit 0) — the absent overlay is skipped.

- [ ] **Step 6: Commit**

```bash
git add scripts/validate.py tests/test_validate.py
git commit -m "feat(13): validate master-cv/ overlay when present (graceful skip)"
```

---

### Task 5: shared `full_profile` helper + twin picks up the overlay

**Files:**
- Create: `scripts/profile_union.py`
- Modify: `scripts/render_chat_context.py`
- Test: `tests/test_profile_union.py`

**Interfaces:**
- Produces: `profile_union.full_profile(content: dict, pubs: list[Publication], master_cv: MasterCV | None = None) -> str` — the union Markdown body (no trailing newline). Section helpers `_identity/_profile/_skills/_experience/_education/_projects/_publications` move here verbatim from `render_chat_context`; new `_full_timeline/_full_inventory/_narrative` append only when `master_cv` is present and non-empty.
- Consumes: `MasterCV` (Task 3), `Publication` (`scripts.bib_loader`).
- `render_chat_context.render()` becomes a thin caller: `full_profile(content, pubs, load_master_cv()) + "\n"`. Module-level `CONTENT_DIR` / `main()` / arg parsing stay (the existing snapshot + `test_render_chat_context.py` rely on `rcc.CONTENT_DIR` and `rcc.render`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_profile_union.py
"""The shared CV + master-cv union helper."""

from __future__ import annotations

from pathlib import Path

from scripts.bib_loader import load_publications
from scripts.content_loader import load_content
from scripts.langstring import resolve_langstrings
from scripts.master_cv_loader import MasterCV
from scripts.profile_union import full_profile

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = REPO_ROOT / "content"


def _facts():
    content = resolve_langstrings(load_content(CONTENT_DIR, lang="en"), lang="en")
    pubs = load_publications(CONTENT_DIR / "publications.bib")
    return content, pubs


def test_absent_overlay_is_cv_only():
    content, pubs = _facts()
    out = full_profile(content, pubs, None)
    assert "## Profile" in out and "## Publications" in out
    assert "master record" not in out  # no master-cv sections


def test_present_overlay_appends_master_sections():
    content, pubs = _facts()
    mcv = MasterCV(
        timeline=[{"id": "imp-vienna-2019", "type": "research", "title": "Doctoral Researcher",
                   "org": "IMP", "start": "2019-08", "end": "2019-10",
                   "summary": "Structural biology work.", "tags": ["structural biology"]}],
        inventory={"programming": ["Python", "Perl"]},
        narrative={"career-story": "# Career story\n\nThe throughline."},
    )
    out = full_profile(content, pubs, mcv)
    assert "## Full Timeline (master record)" in out
    assert "Doctoral Researcher" in out and "Structural biology work." in out
    assert "## Full Skill & Domain Inventory (master record)" in out
    assert "Perl" in out
    assert "## Personal Narrative (master record)" in out
    assert "The throughline." in out


def test_empty_overlay_adds_no_sections():
    content, pubs = _facts()
    mcv = MasterCV(timeline=[], inventory={}, narrative={})
    assert full_profile(content, pubs, mcv) == full_profile(content, pubs, None)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_profile_union.py -v`
Expected: FAIL — `ModuleNotFoundError: scripts.profile_union`.

- [ ] **Step 3: Create `profile_union.py` (move CV helpers verbatim + add master-cv sections)**

```python
# scripts/profile_union.py
"""Assemble the CV (+ optional master-cv overlay) into one Markdown union.

The single DRY union helper shared by render_chat_context (the digital twin) and
render_master_cv (the dist/master-cv.md lookup artifact). When master_cv is None or
empty, the output is exactly the CV-only blob — the graceful-absence guarantee that
keeps the twin's committed snapshot byte-identical without the overlay.
"""

from __future__ import annotations

from scripts.bib_loader import Publication
from scripts.master_cv_loader import MasterCV


def _identity(content: dict) -> str:
    personal = content["personal"]
    profile = content["profile"]
    name = f"{personal['name']['given']} {personal['name']['family']}"
    return f"# {name} — {personal['headline']}\n\n> {profile['tagline']}"


def _profile(content: dict) -> str:
    return "\n\n".join(["## Profile", *content["profile"]["paragraphs"]])


def _skills(content: dict) -> str:
    lines = ["## Skills"]
    for category in content["skills"]["categories"]:
        for group in category["groups"]:
            lines.append(f"- **{group['label']}**: {', '.join(group['items'])}")
    return "\n".join(lines)


def _experience(content: dict) -> str:
    lines = ["## Experience"]
    for job in content["experience"]:
        role = job["role"]
        org = job["org"]["name"]
        period = job["period"]
        start = period["start"]
        end = period.get("end") or "present"
        lines.append(f"### {role} — {org} ({start}–{end})")
        for bullet in job["bullets"]:
            lines.append(f"- {bullet['en']}")
    return "\n".join(lines)


def _education(content: dict) -> str:
    lines = ["## Education"]
    for ed in content["education"]:
        lines.append(f"- {ed['degree']}, {ed['institution']} ({ed['year']})")
    return "\n".join(lines)


def _projects(content: dict) -> str:
    lines = ["## Selected Projects"]
    for p in content["selected_projects"]:
        lines.append(f"### {p['title']}")
        lines.append(p["summary"])
        for detail in p["contributions"]:
            lines.append(f"- {detail}")
    return "\n".join(lines)


def _publications(pubs: list[Publication]) -> str:
    lines = ["## Publications"]
    for p in pubs:
        venue = f", {p.venue}" if p.venue else ""
        year = f" ({p.year})" if p.year else ""
        lines.append(f"- {p.title}{venue}{year}")
    return "\n".join(lines)


# ---- master-cv overlay sections (appended only when present) ---------------


def _full_timeline(master_cv: MasterCV) -> str:
    lines = ["## Full Timeline (master record)"]
    for e in master_cv.timeline:
        title = e.get("title") or e["id"]
        org = f" — {e['org']}" if e.get("org") else ""
        start, end = e.get("start"), e.get("end")
        dates = f" ({start or '?'}–{end or 'present'})" if (start or end) else ""
        lines.append(f"### {title}{org}{dates}")
        loc = f" · {e['location']}" if e.get("location") else ""
        lines.append(f"_{e['type']}{loc}_")
        if e.get("summary"):
            lines.append(e["summary"])
        if e.get("tags"):
            lines.append(f"Tags: {', '.join(e['tags'])}")
    return "\n".join(lines)


def _full_inventory(master_cv: MasterCV) -> str:
    lines = ["## Full Skill & Domain Inventory (master record)"]
    for key, items in master_cv.inventory.items():
        label = key.replace("_", " ").title()
        lines.append(f"- **{label}**: {', '.join(items)}")
    return "\n".join(lines)


def _narrative(master_cv: MasterCV) -> str:
    blocks = ["## Personal Narrative (master record)"]
    for stem in sorted(master_cv.narrative):
        blocks.append(master_cv.narrative[stem].rstrip())
    return "\n\n".join(blocks)


def full_profile(content: dict, pubs: list[Publication], master_cv: MasterCV | None = None) -> str:
    """Full CV (+ master-cv overlay when present) as one Markdown blob, no trailing newline."""
    blocks = [
        _identity(content),
        _profile(content),
        _skills(content),
        _experience(content),
        _education(content),
        _projects(content),
        _publications(pubs),
    ]
    if master_cv is not None:
        if master_cv.timeline:
            blocks.append(_full_timeline(master_cv))
        if master_cv.inventory:
            blocks.append(_full_inventory(master_cv))
        if master_cv.narrative:
            blocks.append(_narrative(master_cv))
    return "\n\n".join(blocks)
```

- [ ] **Step 4: Refactor `render_chat_context.py` to use the helper**

Replace the section-helper functions and `render()` in `scripts/render_chat_context.py`. Delete the seven `_identity/_profile/_skills/_experience/_education/_projects/_publications` functions (now in `profile_union`) and rewrite the imports + `render()`:

```python
from scripts.content_loader import load_content
from scripts.langstring import resolve_langstrings
from scripts.bib_loader import load_publications
from scripts.master_cv_loader import load_master_cv
from scripts.profile_union import full_profile

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = REPO_ROOT / "content"


def render() -> str:
    content = resolve_langstrings(load_content(CONTENT_DIR, lang="en"), lang="en")
    pubs = load_publications(CONTENT_DIR / "publications.bib")
    master_cv = load_master_cv()
    return full_profile(content, pubs, master_cv) + "\n"
```

Leave `main()` and the argparse `--output` block unchanged. The module docstring stays accurate; optionally append a sentence noting the master-cv overlay is appended when present.

- [ ] **Step 5: Run the new + existing chat-context tests**

Run: `uv run pytest tests/test_profile_union.py tests/test_render_chat_context.py -v`
Expected: PASS. (The autouse sentinel makes `render()` CV-only, so `test_render_chat_context.py` is unaffected.)

- [ ] **Step 6: Verify the chat-context golden snapshot is byte-identical (graceful absence)**

Run: `uv run pytest tests/test_snapshots.py::test_chat_context_md -v`
Expected: PASS with **no snapshot change** — proves the refactor produced byte-identical CV-only output. If syrupy reports a mismatch, the refactor diverged; fix it rather than regenerating.

- [ ] **Step 7: Commit**

```bash
git add scripts/profile_union.py scripts/render_chat_context.py tests/test_profile_union.py
git commit -m "feat(13): share full_profile helper; twin appends master-cv when present"
```

---

### Task 6: `render_master_cv` export + `just build-master-cv` + union snapshots

**Files:**
- Create: `scripts/render_master_cv.py`
- Modify: `justfile`
- Modify: `tests/test_snapshots.py` (add two overlay snapshots)
- Test: `tests/test_render_master_cv.py`

**Interfaces:**
- Produces: `render_master_cv.render() -> str` and `render_master_cv.main(argv=None)` writing `dist/master-cv.md`. Reuses `full_profile` + `load_master_cv` (same body shape as chat-context; the difference is destination/purpose — the bundled twin context vs the human lookup artifact).
- Consumes: `full_profile` (Task 5), `load_master_cv` (Task 3).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_render_master_cv.py
"""The dist/master-cv.md lookup-artifact renderer."""

from __future__ import annotations

from pathlib import Path

from scripts import render_master_cv

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_DIR = REPO_ROOT / "master-cv.example"


def test_render_includes_master_sections_with_overlay(monkeypatch):
    monkeypatch.setenv("MASTER_CV_DIR", str(EXAMPLE_DIR))
    out = render_master_cv.render()
    assert "## Full Timeline (master record)" in out
    assert "Example Doctoral Researcher" in out
    assert "## Full Skill & Domain Inventory (master record)" in out
    assert "## Personal Narrative (master record)" in out


def test_render_is_cv_only_without_overlay(monkeypatch):
    monkeypatch.setenv("MASTER_CV_DIR", str(REPO_ROOT / "absent-overlay"))
    out = render_master_cv.render()
    assert "## Profile" in out
    assert "master record" not in out


def test_main_writes_file(tmp_path, monkeypatch):
    monkeypatch.setenv("MASTER_CV_DIR", str(EXAMPLE_DIR))
    out = tmp_path / "master-cv.md"
    render_master_cv.main(["--output", str(out)])
    assert out.read_text(encoding="utf-8").endswith("\n")
    assert "Example Doctoral Researcher" in out.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_render_master_cv.py -v`
Expected: FAIL — `ModuleNotFoundError: scripts.render_master_cv`.

- [ ] **Step 3: Write `render_master_cv.py`**

```python
# scripts/render_master_cv.py
"""Compile content/ + the master-cv/ overlay into dist/master-cv.md.

The single "look up anything about me" artifact: the full union, plainly formatted.
Shares full_profile with render_chat_context (DRY); when the overlay is absent it
degrades to the CV-only blob, exactly like the twin context.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from scripts.bib_loader import load_publications
from scripts.content_loader import load_content
from scripts.langstring import resolve_langstrings
from scripts.master_cv_loader import load_master_cv
from scripts.profile_union import full_profile

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = REPO_ROOT / "content"


def render() -> str:
    content = resolve_langstrings(load_content(CONTENT_DIR, lang="en"), lang="en")
    pubs = load_publications(CONTENT_DIR / "publications.bib")
    master_cv = load_master_cv()
    return full_profile(content, pubs, master_cv) + "\n"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=REPO_ROOT / "dist" / "master-cv.md")
    args = parser.parse_args(argv)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(), encoding="utf-8")
    try:
        rel = args.output.relative_to(REPO_ROOT)
    except ValueError:
        rel = args.output
    print(f"wrote {rel}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_render_master_cv.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Add the `just build-master-cv` recipe**

In `justfile`, immediately after the `build-chat-context` recipe (around line 98), add:

```makefile
# Compile the full master-CV (content/ + master-cv/ overlay) → dist/master-cv.md (lookup artifact)
build-master-cv:
    uv run python -m scripts.render_master_cv
```

Leave `build-formats` unchanged (it stays CV-public; the master-cv export is overlay-dependent and run on demand).

- [ ] **Step 6: Add the two overlay golden snapshots**

In `tests/test_snapshots.py`, add `render_master_cv` to the `from scripts import (...)` block, define `EXAMPLE_DIR = REPO_ROOT / "master-cv.example"` near the top (add `REPO_ROOT` if not already imported — use `Path(__file__).resolve().parent.parent`), and add:

```python
def test_master_cv_md(tmp_path, snapshot, monkeypatch):
    monkeypatch.setenv("MASTER_CV_DIR", str(EXAMPLE_DIR))
    out = tmp_path / "master-cv.md"
    render_master_cv.main(["--output", str(out)])
    assert out.read_text(encoding="utf-8") == snapshot.use_extension(_TextSnap)


def test_chat_context_with_overlay_md(tmp_path, snapshot, monkeypatch):
    monkeypatch.setenv("MASTER_CV_DIR", str(EXAMPLE_DIR))
    out = tmp_path / "chat-context-overlay.md"
    render_chat_context.main(["--output", str(out)])
    assert out.read_text(encoding="utf-8") == snapshot.use_extension(_TextSnap)
```

- [ ] **Step 7: Generate the new snapshots and verify**

Run: `just snapshots-update`
Then: `uv run pytest tests/test_snapshots.py -v`
Expected: PASS. New snapshot files appear under `tests/__snapshots__/test_snapshots/` for `test_master_cv_md` and `test_chat_context_with_overlay_md`; the existing `test_chat_context_md` snapshot is **unchanged**. Eyeball the new snapshots: they must contain the synthetic example data (`Example Doctoral Researcher`, `Example-Lang`) and no real PII.

- [ ] **Step 8: Commit**

```bash
git add scripts/render_master_cv.py justfile tests/test_render_master_cv.py \
        tests/test_snapshots.py tests/__snapshots__/test_snapshots/
git commit -m "feat(13): render_master_cv export + build-master-cv + overlay snapshots"
```

---

### Task 7: block `master-cv/` from commits (gitignore + PII guard)

**Files:**
- Modify: `.gitignore`
- Modify: `scripts/check_pii.py`
- Test: `tests/test_check_pii.py` (append)

**Interfaces:**
- Produces: `master-cv/` added to `PII_PATH_ROOTS` in `check_pii`, so a staged/tracked file under `master-cv/` is a hard violation across all three surfaces (hook, pre-commit, CI). `master-cv.example/` is **not** matched (its prefix is `master-cv.` not `master-cv/`), so it stays committable.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_check_pii.py` (reuse the module's existing `scan_files` / `Violation` imports):

```python
def test_master_cv_path_is_blocked():
    files = [("master-cv/timeline.yaml", b"id: x")]
    violations = scan_files(files, set())
    assert violations and violations[0].path == "master-cv/timeline.yaml"


def test_master_cv_example_is_allowed():
    files = [("master-cv.example/timeline.yaml", b"id: x")]
    assert scan_files(files, set()) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_check_pii.py -k master_cv -v`
Expected: FAIL — `test_master_cv_path_is_blocked` asserts a violation that isn't raised yet.

- [ ] **Step 3: Add `master-cv/` to the blocked roots**

In `scripts/check_pii.py`, extend `PII_PATH_ROOTS`:

```python
PII_PATH_ROOTS = (
    "content.private/",
    "applications/",
    "master-cv/",
    "assets/photo.*",
    "assets/signature.*",
)
```

(Do **not** add anything to `PII_PATH_ALLOW`: `master-cv.example/` does not start with `master-cv/`, so it is already safe. The existing `test_master_cv_example_is_allowed` proves it.)

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_check_pii.py -k master_cv -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Add `master-cv/` to `.gitignore`**

Append to `.gitignore`:

```gitignore
# Phase 13 — master-cv/ overlay (gitignored superset feeding the twin; example template stays committed)
master-cv/
```

- [ ] **Step 6: Verify the guard and gitignore end-to-end**

Run: `uv run python -m scripts.check_pii --tree`
Expected: `OK: no PII leaks detected` (no tracked file lives under `master-cv/`).

Run: `mkdir -p master-cv && touch master-cv/timeline.yaml && git status --porcelain master-cv/ ; rm -rf master-cv`
Expected: empty output (git ignores `master-cv/`). The `rm -rf master-cv` cleanup is part of the command.

- [ ] **Step 7: Commit**

```bash
git add .gitignore scripts/check_pii.py tests/test_check_pii.py
git commit -m "feat(13): gitignore + PII-guard block master-cv/ (example stays committed)"
```

---

### Task 8: full green gate + CLAUDE.md update

**Files:**
- Modify: `CLAUDE.md` (Phasing table row + conventions note + layout/commands)

**Interfaces:**
- Consumes: everything above must be green before this task lands.

- [ ] **Step 1: Run the full verification gate**

Run: `just validate && just test && just lint && just fmt`
Expected: validate `OK`, all pytest green, ruff check clean, ruff format reports no changes. Fix any failure before proceeding — do not edit CLAUDE.md over a red gate.

- [ ] **Step 2: Add the Phase 13 row to the Phasing table**

In `CLAUDE.md`, append a row after the `12c` row:

```markdown
| 13 | `master-cv/` overlay (gitignored life-database superset feeding the twin + a `dist/master-cv.md` lookup export; CV stays sharp) | ✅ Done (merged YYYY-MM-DD, `--no-ff`, PR #NN, commit `xxxxxxx`); overlay gitignored + PII-guarded, graceful-absence proven (CV-only output byte-identical without it), synthetic `master-cv.example/` committed; first ingest + CV-reconcile (#93) are separate manual/follow-up steps |
```

(Fill the date/PR/commit at merge time — the finishing-a-development-branch step supplies them.)

- [ ] **Step 3: Add a conventions note**

In the Conventions section of `CLAUDE.md`, add a bullet:

```markdown
- **`master-cv/` is a gitignored superset overlay (Phase 13).** The unfiltered
  life-database (`timeline.yaml` + `inventory.yaml` + `narrative/*.md`) feeding the
  digital twin and the `dist/master-cv.md` lookup export. `content/` is a curated
  *selection* from it. Never committed (`.gitignore` + `check_pii.py` both block it);
  only synthetic `master-cv.example/` is committed. Both consumers share
  `scripts/profile_union.full_profile`; the overlay path resolves from `MASTER_CV_DIR`
  (default `<repo>/master-cv`, the `CV_PRIVATE_YAML` test-override shape). Absent ⇒
  CV-only output, byte-identical (graceful-absence proof). No test reads the real
  overlay — a conftest autouse fixture redirects `MASTER_CV_DIR` to an absent sentinel.
```

- [ ] **Step 4: Update the Layout, Commands, and Files-to-read sections**

In `CLAUDE.md`:
- **Layout** `scripts/` line: add `master_cv_loader.py, render_master_cv.py, profile_union.py`. Add `master-cv.example/   committed synthetic overlay template` and `schema/master-cv.schema.json   overlay validation` to the tree.
- **Commands**: add `just build-master-cv      # content/ + master-cv/ overlay → dist/master-cv.md (lookup artifact)`.
- **Files to read before any phase**: add `docs/superpowers/specs/2026-06-20-phase-13-master-cv-overlay-design.md` and `docs/superpowers/plans/2026-06-22-phase-13-master-cv-overlay.md`.
- **Local-only files (not in git)**: add `master-cv/ — the unfiltered superset overlay (timeline.yaml + inventory.yaml + narrative/*.md). Gitignored; mirror the shape in master-cv.example/.`

- [ ] **Step 5: Re-run the gate to confirm docs didn't break anything**

Run: `just test && just lint`
Expected: green (the check_pii drift-guard and any doc-drift guards still pass).

- [ ] **Step 6: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(13): master-cv/ overlay — Phasing row + conventions"
```

---

### Task 9: first ingest (manual, with the user — no commit)

> This task produces the **real** `master-cv/` overlay on the user's machine from their comprehensive history table. It is gitignored and **must never be committed**. Do this interactively with the user (the history table is theirs); it is not a code change and lands no commit — analogous to the `worker-deploy` manual step.

- [ ] **Step 1: Scaffold the real overlay from the template**

Run: `cp -r master-cv.example master-cv`
Then replace every synthetic value in `master-cv/timeline.yaml`, `master-cv/inventory.yaml`, and `master-cv/narrative/*.md` with the user's real history, working from their table: all ~25 positions/internships/degrees/certificates/awards/volunteering (incl. IMP Vienna, Bundeswehr Radiobiology, KRIBB, MPI Medical Research, RLP AgroScience, Tutoria, every certificate including the fishing/badminton licenses, the hackathon award, the DAAD RISE grant-acquisition + recruiting fact typed `employment`/`research` not `award`, and `status: in-progress` for the GCP cert); the full skill/tool/domain/industry superset; and seed `narrative/career-story.md` + `personal.md` with the softer material (interests, language detail). References stay in `applications/references.md` — point to them, don't duplicate.

- [ ] **Step 2: Validate and build the lookup artifact**

Run: `just validate && just build-master-cv`
Expected: validate `OK` (now also validating the real overlay), and `wrote dist/master-cv.md`. Open `dist/master-cv.md` and eyeball the union for completeness and accuracy.

- [ ] **Step 3: Confirm the overlay is NOT staged and the guard agrees**

Run: `git status --porcelain master-cv/ && uv run python -m scripts.check_pii --staged`
Expected: empty `git status` output (gitignored) and `OK: no PII leaks detected`. If `master-cv/` ever shows as tracked, stop — it must stay gitignored.

- [ ] **Step 4: Refresh the twin context (optional, when deploying)**

The richer context flows into the twin automatically on the next `just worker-deploy` (it bundles a fresh `chat-context.md` built with the now-present overlay). No code change needed — just redeploy when ready.

---

## Self-Review

**1. Spec coverage:**
- `master-cv/` structure (timeline/inventory/narrative) → Tasks 2, 3. ✓
- `schema/master-cv.schema.json` light validation → Task 1. ✓
- `master_cv_loader.load_master_cv -> MasterCV | None`, `MASTER_CV_DIR` env override → Task 3. ✓
- `render_master_cv.py` → `dist/master-cv.md` → Task 6. ✓
- `render_chat_context` appends overlay when present, graceful no-op absent → Task 5. ✓
- shared `full_profile(content, master_cv)` helper (DRY) → Task 5 (signature carries `pubs` too, since publications aren't in the `content` dict the chat-context uses; an intentional, documented widening of the spec's 2-arg shorthand). ✓
- `validate.py` validates overlay only if present → Task 4. ✓
- `justfile build-master-cv` → Task 6. ✓
- `.gitignore` ignores `master-cv/`, keeps example → Task 7. ✓
- `check_pii.py` blocks `master-cv/` → Task 7. ✓
- `master-cv.example/` committed synthetic template → Task 2. ✓
- CLAUDE.md Phasing row + convention → Task 8. ✓
- Safety: never committed (Task 7), never snapshotted with real data (synthetic example fixture, Tasks 2/6), conftest tripwire + env redirect (Task 3), graceful-absence byte-identical proof (Task 5 step 6). ✓
- First ingest → Task 9 (manual, no commit). ✓

**2. Placeholder scan:** No "TBD"/"handle edge cases"/"similar to Task N" — every code step shows full code. The CLAUDE.md merge metadata (date/PR/commit) is deliberately filled at merge time by the finishing step, not a placeholder in code.

**3. Type consistency:** `MasterCV(timeline, inventory, narrative)` is defined in Task 3 and consumed with those exact field names in Tasks 4/5/6. `load_master_cv(path=None)` and `full_profile(content, pubs, master_cv=None)` signatures match across all call sites. `validate_master_cv(master_cv_dir, schema_path)` matches its test and `main()` wiring. Section heading strings (`"## Full Timeline (master record)"`, `"## Full Skill & Domain Inventory (master record)"`, `"## Personal Narrative (master record)"`) are identical between `profile_union.py` (Task 5) and every assertion (Tasks 5/6).
