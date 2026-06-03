# Agent Interface (MCP server + skill) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the codified CV operable by an agent — read structured content, propose/apply schema-gated edits, and re-run renderers — via one Python core wrapped by a thin MCP server and documented by a committed Claude skill.

**Architecture:** A pure-Python core `scripts/agent_core.py` holds all behaviour and every PII/path/subprocess guard. `scripts/mcp_server.py` is a thin FastMCP (official `mcp` SDK) stdio wrapper mapping 1:1 to the core. `.claude/skills/cv/` is prose teaching an agent to drive the same operations with its own Edit + `just` tools. Tests enforce anti-drift.

**Tech Stack:** Python 3.12, `uv`, `pytest`, `ruff`, the official `mcp[cli]` SDK (FastMCP), `pydantic`, existing `content_loader`/`validate`/`render_*` modules + `just` recipes.

**Spec:** [docs/superpowers/specs/2026-06-03-agent-interface-mcp-skill-design.md](../specs/2026-06-03-agent-interface-mcp-skill-design.md)

---

## File structure

| File | Responsibility |
|---|---|
| `scripts/agent_core.py` (new) | Shared core: `_safe_content_path`, `read_cv`, `list_content_files`, `validate_cv`, `propose_edit`, `apply_edit`, `rerun_renderers` |
| `scripts/mcp_server.py` (new) | FastMCP wrapper: Pydantic result models + 6 tools + `run()` |
| `.claude/skills/cv/SKILL.md` (new) | Agent-facing skill (prose, frontmatter) |
| `.claude/skills/cv/reference.md` (new) | Recipe + content cheat-sheet (drift-guarded) |
| `.mcp.json` (new) | Claude Code project-scoped server config |
| `tests/test_agent_core.py` (new) | Core unit tests (PII, traversal, propose/apply/rerun) |
| `tests/test_mcp_server.py` (new) | MCP smoke + annotations + core↔server parity |
| `tests/test_skill_docs.py` (new) | Doc drift-guards |
| `pyproject.toml` (edit) | Add `[dependency-groups] mcp` |
| `justfile` (edit) | `mcp-server`, `mcp-dev` recipes |
| `CLAUDE.md` (edit) | Layout, Commands, Conventions, Phasing |

**Note on imports & ruff:** each task adds only the imports its code uses, so `just lint` stays green at every commit. Do not import a module before the task that uses it.

**Note on CI:** `.github/workflows/ci.yml` already runs `uv sync --all-groups` then `uv run pytest`, so the new `mcp` group is installed and all new tests run in CI with no workflow edit.

---

### Task 1: Core module scaffold + `_safe_content_path` (the security spine)

**Files:**
- Create: `scripts/agent_core.py`
- Test: `tests/test_agent_core.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_agent_core.py`:

```python
"""Tests for the agent-facing core (read/validate/propose/apply/rerun)."""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

from scripts import agent_core

REPO_ROOT = Path(__file__).resolve().parent.parent
REAL_CONTENT = REPO_ROOT / "content"


@pytest.fixture
def cv_tree(tmp_path: Path) -> Path:
    """A writable copy of content/ plus a sibling content.private/ as PII bait."""
    content = tmp_path / "content"
    shutil.copytree(REAL_CONTENT, content)
    private = tmp_path / "content.private"
    private.mkdir()
    (private / "private.yaml").write_text(
        "phone: '+49 555 SECRET'\naddress:\n  city: Nowhere\n", encoding="utf-8"
    )
    return content


@pytest.mark.parametrize(
    "bad",
    [
        "/etc/passwd",
        "../content.private/private.yaml",
        "projects/../../content.private/private.yaml",
        "personal.txt",
        "../secret.yaml",
        ".hidden.yaml",
    ],
)
def test_safe_path_rejects(cv_tree, bad):
    with pytest.raises(ValueError):
        agent_core._safe_content_path(bad, content_dir=cv_tree)


def test_safe_path_rejects_symlink_escape(cv_tree):
    (cv_tree / "leak.yaml").symlink_to(cv_tree.parent / "content.private" / "private.yaml")
    with pytest.raises(ValueError):
        agent_core._safe_content_path("leak.yaml", content_dir=cv_tree)


def test_safe_path_accepts_real_file(cv_tree):
    p = agent_core._safe_content_path("personal.yaml", content_dir=cv_tree)
    assert p == (cv_tree / "personal.yaml").resolve()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_agent_core.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.agent_core'`.

- [ ] **Step 3: Create the module with constants + `_safe_content_path`**

Create `scripts/agent_core.py`:

```python
"""Agent-facing core: read, validate, propose/apply edits, re-render the CV.

Shared foundation for the MCP server (scripts/mcp_server.py) and the Claude
skill (.claude/skills/cv/). Pure Python, no MCP/CLI coupling. Every path / PII /
subprocess guard lives here so both surfaces inherit it.
"""
from __future__ import annotations

from pathlib import Path, PurePosixPath

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = REPO_ROOT / "content"
SCHEMA_PATH = REPO_ROOT / "schema" / "cv.schema.json"


def _safe_content_path(rel_path: str, *, content_dir: Path = CONTENT_DIR) -> Path:
    """Resolve a content-relative path safely, or raise ValueError.

    Blocks absolute paths, '..'/dot segments, non-.yaml targets, symlink escapes
    out of content/, and anything resolving under content.private/.
    """
    pure = PurePosixPath(rel_path)
    if pure.is_absolute() or rel_path.startswith(("/", "\\")):
        raise ValueError(f"path must be relative to content/: {rel_path!r}")
    if any(part in ("..", ".") or part.startswith(".") for part in pure.parts):
        raise ValueError(f"illegal path segment in {rel_path!r}")
    if pure.suffix != ".yaml":
        raise ValueError(f"only .yaml files are editable: {rel_path!r}")
    resolved = (content_dir / rel_path).resolve()
    content_root = content_dir.resolve()
    if content_root != resolved and content_root not in resolved.parents:
        raise ValueError(f"path escapes content/: {rel_path!r}")
    if "content.private" in resolved.parts:
        raise ValueError(f"refusing content.private path: {rel_path!r}")
    return resolved
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_agent_core.py -v`
Expected: PASS (8 cases). Then `uv run ruff check scripts/agent_core.py tests/test_agent_core.py` → clean.

- [ ] **Step 5: Commit**

```bash
git add scripts/agent_core.py tests/test_agent_core.py
git commit -m "feat: agent_core path-safety guard (#48)"
```

---

### Task 2: `read_cv` — PII-safe read + section filter

**Files:**
- Modify: `scripts/agent_core.py`
- Test: `tests/test_agent_core.py`

- [ ] **Step 1: Add failing tests** (append to `tests/test_agent_core.py`)

```python
def test_read_cv_never_leaks_pii(cv_tree):
    out = agent_core.read_cv(content_dir=cv_tree)
    blob = repr(out)
    assert "SECRET" not in blob
    assert "Nowhere" not in blob


def test_read_cv_section_filter(cv_tree):
    full = agent_core.read_cv(content_dir=cv_tree)
    assert {"personal", "experience", "education"} <= set(full)
    edu = agent_core.read_cv(section="education", content_dir=cv_tree)
    assert set(edu) == {"education"}
    with pytest.raises(ValueError):
        agent_core.read_cv(section="nope", content_dir=cv_tree)


def test_read_cv_rejects_bad_target(cv_tree):
    with pytest.raises(ValueError):
        agent_core.read_cv(target="bogus", content_dir=cv_tree)
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_agent_core.py -k read_cv -v`
Expected: FAIL — `AttributeError: module 'scripts.agent_core' has no attribute 'read_cv'`.

- [ ] **Step 3: Implement** — add imports + `SECTIONS` + `read_cv` to `scripts/agent_core.py`

Add these imports below the existing `from pathlib import ...` line:

```python
from scripts.content_loader import TARGETS, load_content
from scripts.langstring import resolve_langstrings
from scripts.render_web_data import _to_jsonable
```

Add this constant after `SCHEMA_PATH`:

```python
SECTIONS = (
    "personal", "profile", "skills", "education", "experience", "projects",
    "selected_projects", "languages", "volunteer", "awards", "publications", "labels",
)
```

Add this function (after `_safe_content_path`):

```python
def read_cv(
    lang: str = "en",
    target: str = "bridge",
    section: str | None = None,
    *,
    content_dir: Path = CONTENT_DIR,
) -> dict:
    """Load the CV content tree (LangStrings resolved, JSON-able), PII excluded.

    Never passes private_path, so content.private/ can never surface. `section`,
    if given, must be one of SECTIONS and returns {section: value}.
    """
    if target not in TARGETS:
        raise ValueError(f"unknown target {target!r}; expected one of {TARGETS}")
    tree = load_content(content_dir, private_path=None, lang=lang, target=target)
    data = _to_jsonable(resolve_langstrings(tree, lang))
    if section is None:
        return data
    if section not in SECTIONS:
        raise ValueError(f"unknown section {section!r}; expected one of {SECTIONS}")
    return {section: data.get(section)}
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_agent_core.py -k read_cv -v`
Expected: PASS (3 cases). Then `uv run ruff check scripts/agent_core.py` → clean.

- [ ] **Step 5: Commit**

```bash
git add scripts/agent_core.py tests/test_agent_core.py
git commit -m "feat: agent_core read_cv (PII-safe, section filter) (#48)"
```

---

### Task 3: `list_content_files` — relative, sorted, leak-proof

**Files:**
- Modify: `scripts/agent_core.py`
- Test: `tests/test_agent_core.py`

- [ ] **Step 1: Add failing tests**

```python
def test_list_content_files_relative_sorted(cv_tree):
    files = agent_core.list_content_files(content_dir=cv_tree)
    assert files == sorted(files)
    assert "personal.yaml" in files
    assert any(f.startswith("projects/") for f in files)
    assert all(not f.startswith("/") for f in files)
    assert "publications.bib" not in files
    assert not any("content.private" in f for f in files)


def test_list_content_files_excludes_symlink_to_private(cv_tree):
    (cv_tree / "leak.yaml").symlink_to(cv_tree.parent / "content.private" / "private.yaml")
    files = agent_core.list_content_files(content_dir=cv_tree)
    assert "leak.yaml" not in files
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_agent_core.py -k list_content_files -v`
Expected: FAIL — no attribute `list_content_files`.

- [ ] **Step 3: Implement** — add to `scripts/agent_core.py` (no new imports):

```python
def list_content_files(*, content_dir: Path = CONTENT_DIR) -> list[str]:
    """List editable content YAML as sorted, content-relative posix paths.

    Excludes content.private/ (even via symlink) and non-.yaml files.
    """
    content_root = content_dir.resolve()
    out: list[str] = []
    for p in content_root.rglob("*.yaml"):
        rp = p.resolve()
        if content_root != rp and content_root not in rp.parents:
            continue
        if "content.private" in rp.parts:
            continue
        out.append(rp.relative_to(content_root).as_posix())
    return sorted(out)
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_agent_core.py -k list_content_files -v`
Expected: PASS (2 cases). Then `uv run ruff check scripts/agent_core.py` → clean.

- [ ] **Step 5: Commit**

```bash
git add scripts/agent_core.py tests/test_agent_core.py
git commit -m "feat: agent_core list_content_files (#48)"
```

---

### Task 4: `validate_cv` — standalone validation

**Files:**
- Modify: `scripts/agent_core.py`
- Test: `tests/test_agent_core.py`

- [ ] **Step 1: Add failing tests**

```python
def test_validate_cv_clean(cv_tree):
    res = agent_core.validate_cv(content_dir=cv_tree)
    assert res["valid"] is True
    assert res["errors"] == []


def test_validate_cv_detects_break(cv_tree):
    (cv_tree / "personal.yaml").write_text("{}\n", encoding="utf-8")
    res = agent_core.validate_cv(content_dir=cv_tree)
    assert res["valid"] is False
    assert res["errors"]
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_agent_core.py -k validate_cv -v`
Expected: FAIL — no attribute `validate_cv`.

- [ ] **Step 3: Implement** — add import + function to `scripts/agent_core.py`

Add import (next to the other `from scripts...` imports):

```python
from scripts.validate import date_warnings, validate_tree
```

Add function:

```python
def validate_cv(*, content_dir: Path = CONTENT_DIR, schema_path: Path = SCHEMA_PATH) -> dict:
    """Validate the content tree (schema + cross-refs + parity + periods + bib).

    Returns {"valid": bool, "errors": list[str], "warnings": list[str]}.
    """
    errors = validate_tree(content_dir, schema_path)
    warnings = date_warnings(content_dir)
    return {
        "valid": not errors,
        "errors": [str(e) for e in errors],
        "warnings": [str(w) for w in warnings],
    }
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_agent_core.py -k validate_cv -v`
Expected: PASS (2 cases). `uv run ruff check scripts/agent_core.py` → clean.

- [ ] **Step 5: Commit**

```bash
git add scripts/agent_core.py tests/test_agent_core.py
git commit -m "feat: agent_core validate_cv (#48)"
```

---

### Task 5: `propose_edit` — dry-run, full-tree validation, zero source mutation

**Files:**
- Modify: `scripts/agent_core.py`
- Test: `tests/test_agent_core.py`

- [ ] **Step 1: Add failing tests**

```python
def test_propose_edit_clean_change(cv_tree):
    rel = "personal.yaml"
    current = (cv_tree / rel).read_text(encoding="utf-8")
    res = agent_core.propose_edit(rel, current + "\n# harmless comment\n", content_dir=cv_tree)
    assert res["valid"] is True
    assert res["diff"]  # non-empty unified diff
    assert (cv_tree / rel).read_text(encoding="utf-8") == current  # source untouched


def test_propose_edit_schema_break(cv_tree):
    rel = "personal.yaml"
    current = (cv_tree / rel).read_text(encoding="utf-8")
    res = agent_core.propose_edit(rel, "{}\n", content_dir=cv_tree)
    assert res["valid"] is False
    assert res["errors"]
    assert (cv_tree / rel).read_text(encoding="utf-8") == current


def test_propose_edit_unpaired_project_rejected(cv_tree):
    res = agent_core.propose_edit("projects/ZZ.de.yaml", "id: ZZ\n", content_dir=cv_tree)
    assert res["valid"] is False  # missing ZZ.en.yaml / invalid project


def test_propose_edit_cleans_tempdir(cv_tree, monkeypatch):
    created = []
    real_td = tempfile.TemporaryDirectory

    class Recording(real_td):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            created.append(Path(self.name))

    monkeypatch.setattr(agent_core.tempfile, "TemporaryDirectory", Recording)
    agent_core.propose_edit("personal.yaml", "{}\n", content_dir=cv_tree)
    assert created and all(not p.exists() for p in created)
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_agent_core.py -k propose_edit -v`
Expected: FAIL — no attribute `propose_edit`.

- [ ] **Step 3: Implement** — add imports + function

Add imports at top of `scripts/agent_core.py` (stdlib group, alphabetical with existing):

```python
import difflib
import shutil
import tempfile
```

Add function:

```python
def propose_edit(
    rel_path: str,
    new_content: str,
    *,
    content_dir: Path = CONTENT_DIR,
    schema_path: Path = SCHEMA_PATH,
) -> dict:
    """Dry-run an edit: validate the whole would-be tree, return a diff. No write.

    Returns {"diff": str, "valid": bool, "errors": list[str], "warnings": list[str]}.
    """
    dst_rel = _safe_content_path(rel_path, content_dir=content_dir).relative_to(
        content_dir.resolve()
    )
    target_file = content_dir / dst_rel
    current = target_file.read_text(encoding="utf-8") if target_file.exists() else ""

    with tempfile.TemporaryDirectory() as tmp:
        tmp_content = Path(tmp) / "content"
        shutil.copytree(content_dir, tmp_content)  # content/ only — never PII sibling
        edited = tmp_content / dst_rel
        edited.parent.mkdir(parents=True, exist_ok=True)
        edited.write_text(new_content, encoding="utf-8")
        errors = validate_tree(tmp_content, schema_path)
        warnings = date_warnings(tmp_content)

    diff = "".join(
        difflib.unified_diff(
            current.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=dst_rel.as_posix(),
            tofile=dst_rel.as_posix(),
            n=3,
        )
    )
    return {
        "diff": diff,
        "valid": not errors,
        "errors": [str(e) for e in errors],
        "warnings": [str(w) for w in warnings],
    }
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_agent_core.py -k propose_edit -v`
Expected: PASS (4 cases). `uv run ruff check scripts/agent_core.py` → clean.

- [ ] **Step 5: Commit**

```bash
git add scripts/agent_core.py tests/test_agent_core.py
git commit -m "feat: agent_core propose_edit (dry-run, full-tree validation) (#48)"
```

---

### Task 6: `apply_edit` — validate-then-write, atomic, refuses on any error

**Files:**
- Modify: `scripts/agent_core.py`
- Test: `tests/test_agent_core.py`

- [ ] **Step 1: Add failing tests**

```python
def test_apply_edit_writes_on_valid(cv_tree):
    rel = "personal.yaml"
    new = (cv_tree / rel).read_text(encoding="utf-8") + "\n# applied\n"
    res = agent_core.apply_edit(rel, new, content_dir=cv_tree)
    assert res["applied"] is True
    assert (cv_tree / rel).read_text(encoding="utf-8") == new
    assert not agent_core.validate_tree(cv_tree, agent_core.SCHEMA_PATH)


def test_apply_edit_refuses_invalid(cv_tree):
    rel = "personal.yaml"
    current = (cv_tree / rel).read_text(encoding="utf-8")
    res = agent_core.apply_edit(rel, "{}\n", content_dir=cv_tree)
    assert res["applied"] is False
    assert res["errors"]
    assert (cv_tree / rel).read_text(encoding="utf-8") == current  # byte-identical


@pytest.mark.parametrize("bad", ["../content.private/private.yaml", "/abs.yaml", "x.txt"])
def test_apply_edit_refuses_unsafe_path(cv_tree, bad):
    with pytest.raises(ValueError):
        agent_core.apply_edit(bad, "id: x\n", content_dir=cv_tree)
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_agent_core.py -k apply_edit -v`
Expected: FAIL — no attribute `apply_edit`.

- [ ] **Step 3: Implement** — add import + function

Add import (stdlib group):

```python
import os
```

Add function:

```python
def apply_edit(
    rel_path: str,
    new_content: str,
    *,
    content_dir: Path = CONTENT_DIR,
    schema_path: Path = SCHEMA_PATH,
) -> dict:
    """Validate the would-be tree, then atomically write only if it validates.

    Returns {"applied": bool, "errors": list[str], "warnings": list[str]}.
    """
    result = propose_edit(rel_path, new_content, content_dir=content_dir, schema_path=schema_path)
    if not result["valid"]:
        return {"applied": False, "errors": result["errors"], "warnings": result["warnings"]}

    dst = _safe_content_path(rel_path, content_dir=content_dir)
    dst.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=str(dst.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(new_content)
        os.replace(tmp_path, dst)  # atomic within the same directory
    except BaseException:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise
    return {"applied": True, "errors": [], "warnings": result["warnings"]}
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_agent_core.py -k apply_edit -v`
Expected: PASS (4 cases). `uv run ruff check scripts/agent_core.py` → clean.

- [ ] **Step 5: Commit**

```bash
git add scripts/agent_core.py tests/test_agent_core.py
git commit -m "feat: agent_core apply_edit (atomic validated write) (#48)"
```

---

### Task 7: `rerun_renderers` — whitelisted, injection-proof, graceful

**Files:**
- Modify: `scripts/agent_core.py`
- Test: `tests/test_agent_core.py`

- [ ] **Step 1: Add failing tests**

```python
def test_resolve_recipes_rejects_invalid_which():
    with pytest.raises(ValueError):
        agent_core._resolve_recipes("formats; rm -rf /")


def test_resolve_recipes_skips_missing_tools(monkeypatch):
    monkeypatch.setattr(agent_core.shutil, "which", lambda tool: None)
    to_run, skipped = agent_core._resolve_recipes("all")
    assert "build-formats" in to_run
    assert {"build", "build-de", "web-build"} <= set(skipped)


def test_rerun_renderers_validate_first(cv_tree):
    (cv_tree / "personal.yaml").write_text("{}\n", encoding="utf-8")
    res = agent_core.rerun_renderers(content_dir=cv_tree)
    assert res["ok"] is False
    assert res["ran"] == []


def test_rerun_renderers_invokes_just_list_form(cv_tree, monkeypatch):
    calls = []

    class FakeProc:
        returncode = 0
        stdout = "ok"
        stderr = ""

    monkeypatch.setattr(agent_core.subprocess, "run", lambda argv, **kw: calls.append((argv, kw)) or FakeProc())
    monkeypatch.setattr(agent_core.shutil, "which", lambda tool: "/usr/bin/" + tool)
    res = agent_core.rerun_renderers("formats", content_dir=cv_tree)
    assert res["ok"] is True
    assert res["ran"] == ["build-formats"]
    argv, kw = calls[0]
    assert argv == ["just", "build-formats"]
    assert kw.get("shell") in (None, False)
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_agent_core.py -k "resolve_recipes or rerun_renderers" -v`
Expected: FAIL — no attribute `_resolve_recipes`.

- [ ] **Step 3: Implement** — add import + constant + two functions

Add import (stdlib group):

```python
import subprocess
```

Add constant (after `SECTIONS`):

```python
# which-group -> ordered (just recipe, required tool on PATH or None)
_RECIPE_PLAN = {
    "formats": [("build-formats", None)],
    "pdf": [("build", "typst"), ("build-de", "typst")],
    "web": [("web-build", "pnpm")],
}
```

Add functions:

```python
def _resolve_recipes(which: str) -> tuple[list[str], list[str]]:
    """Return (to_run, skipped) recipe names for `which`, honoring tool availability."""
    if which not in {"formats", "pdf", "web", "all"}:
        raise ValueError(f"unknown which {which!r}; expected formats|pdf|web|all")
    groups = ["formats", "pdf", "web"] if which == "all" else [which]
    to_run: list[str] = []
    skipped: list[str] = []
    for group in groups:
        for recipe, tool in _RECIPE_PLAN[group]:
            if tool is not None and shutil.which(tool) is None:
                skipped.append(recipe)
            else:
                to_run.append(recipe)
    return to_run, skipped


def rerun_renderers(
    which: str = "formats",
    *,
    content_dir: Path = CONTENT_DIR,
    schema_path: Path = SCHEMA_PATH,
) -> dict:
    """Validate-first, then run the whitelisted `just` recipes for `which`.

    Renderers always operate on the repo's real content/ (via `just`, cwd=REPO_ROOT);
    `content_dir` only governs the validate-first gate. pdf/web skip gracefully when
    Typst/pnpm are absent; refresh-citations is never invoked.
    Returns {"ran": list[str], "ok": bool, "skipped": list[str], "output": dict[str, str]}.
    """
    to_run, skipped = _resolve_recipes(which)
    errors = validate_tree(content_dir, schema_path)
    if errors:
        return {
            "ran": [],
            "ok": False,
            "skipped": to_run + skipped,
            "output": {"validate": "\n".join(str(e) for e in errors)},
        }
    ran: list[str] = []
    output: dict[str, str] = {}
    ok = True
    for recipe in to_run:
        proc = subprocess.run(
            ["just", recipe], cwd=REPO_ROOT, capture_output=True, text=True, timeout=600
        )
        ran.append(recipe)
        output[recipe] = (proc.stdout or "") + (proc.stderr or "")
        if proc.returncode != 0:
            ok = False
    return {"ran": ran, "ok": ok, "skipped": skipped, "output": output}
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_agent_core.py -v`
Expected: PASS (entire file — ~24 cases). `uv run ruff check scripts/agent_core.py tests/test_agent_core.py` → clean.

- [ ] **Step 5: Commit**

```bash
git add scripts/agent_core.py tests/test_agent_core.py
git commit -m "feat: agent_core rerun_renderers (whitelisted, graceful) (#48)"
```

---

### Task 8: MCP dependency + thin FastMCP server + server tests

**Files:**
- Modify: `pyproject.toml`
- Create: `scripts/mcp_server.py`
- Test: `tests/test_mcp_server.py`

- [ ] **Step 1: Add the `mcp` dependency group** to `pyproject.toml`

Add a new group under the existing `[dependency-groups]` table (after the `dev = [...]` list):

```toml
mcp = [
    "mcp[cli]>=1.12",
]
```

- [ ] **Step 2: Sync the group**

Run: `uv sync --group mcp`
Expected: resolves and installs `mcp` (+ pydantic, anyio…); updates `uv.lock`.

- [ ] **Step 3: Write the failing server tests**

Create `tests/test_mcp_server.py`:

```python
"""Tests for the thin MCP server (skipped if the mcp SDK is absent)."""
from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("mcp")

from scripts import agent_core, mcp_server  # noqa: E402

EXPECTED_TOOLS = {
    "get_cv_content", "list_cv_files", "validate_cv",
    "propose_edit", "apply_edit", "rerun_renderers",
}


def _tools():
    return {t.name: t for t in asyncio.run(mcp_server.mcp.list_tools())}


def test_tools_listed():
    assert set(_tools()) == EXPECTED_TOOLS


def test_tool_annotations():
    tools = _tools()
    for name in ("get_cv_content", "list_cv_files", "validate_cv", "propose_edit"):
        assert tools[name].annotations.readOnlyHint is True
    assert tools["apply_edit"].annotations.readOnlyHint is False
    assert tools["apply_edit"].annotations.destructiveHint is True
    assert tools["rerun_renderers"].annotations.readOnlyHint is False


def test_get_cv_content_returns_tree():
    out = mcp_server.get_cv_content()
    assert isinstance(out, dict) and "personal" in out


def test_core_server_parity():
    rel = "personal.yaml"
    current = (agent_core.CONTENT_DIR / rel).read_text(encoding="utf-8")
    server = mcp_server.propose_edit(rel, current).model_dump()
    core = agent_core.propose_edit(rel, current)
    assert server == core
```

- [ ] **Step 4: Run to verify failure**

Run: `uv run --group mcp pytest tests/test_mcp_server.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.mcp_server'`.

- [ ] **Step 5: Implement the server**

Create `scripts/mcp_server.py`:

```python
"""Thin MCP server exposing the CV agent core over stdio (FastMCP).

Each tool maps 1:1 to scripts.agent_core; the only added logic is Pydantic
result shaping and MCP tool annotations. Run: `uv run --group mcp python -m scripts.mcp_server`.
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel

from scripts import agent_core

mcp = FastMCP("jin-ho-lee-cv")


class ProposeResult(BaseModel):
    diff: str
    valid: bool
    errors: list[str]
    warnings: list[str]


class ApplyResult(BaseModel):
    applied: bool
    errors: list[str]
    warnings: list[str]


class ValidateResult(BaseModel):
    valid: bool
    errors: list[str]
    warnings: list[str]


class RenderResult(BaseModel):
    ran: list[str]
    ok: bool
    skipped: list[str]
    output: dict[str, str]


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False))
def get_cv_content(lang: str = "en", target: str = "bridge", section: str | None = None) -> dict:
    """Load the CV content tree (LangStrings resolved) for a language and target variant."""
    return agent_core.read_cv(lang=lang, target=target, section=section)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False))
def list_cv_files() -> list[str]:
    """List the editable content YAML files as content-relative paths."""
    return agent_core.list_content_files()


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False))
def validate_cv() -> ValidateResult:
    """Validate the current content tree (schema + cross-refs + parity + periods + bib)."""
    return ValidateResult(**agent_core.validate_cv())


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False))
def propose_edit(path: str, new_content: str) -> ProposeResult:
    """Dry-run an edit: return a unified diff + full-tree validation. Writes nothing."""
    return ProposeResult(**agent_core.propose_edit(path, new_content))


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=False
    )
)
def apply_edit(path: str, new_content: str) -> ApplyResult:
    """Validate then write an edit to content/. Refuses if the tree would not validate."""
    return ApplyResult(**agent_core.apply_edit(path, new_content))


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False
    )
)
def rerun_renderers(which: str = "formats") -> RenderResult:
    """Re-run renderers (formats|pdf|web|all); validate-first, skip pdf/web if tools absent."""
    return RenderResult(**agent_core.rerun_renderers(which))


def run() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    run()
```

- [ ] **Step 6: Run to verify pass**

Run: `uv run --group mcp pytest tests/test_mcp_server.py -v`
Expected: PASS (4 cases).

> If `test_tools_listed`/`test_core_server_parity` error because `@mcp.tool` does not return the bare function in the installed SDK version, adapt the direct-call tests to call via `asyncio.run(mcp_server.mcp.call_tool(name, args))` and read `.structuredContent`; keep `list_tools()` for names/annotations. Do not change the server's behaviour to satisfy the test.

- [ ] **Step 7: Confirm skip-without-group + lint**

Run: `uv run pytest tests/test_mcp_server.py -v` (no `--group mcp`)
Expected: SKIPPED (importorskip) — proves `just test` stays green without the group.
Run: `uv run ruff check scripts/mcp_server.py tests/test_mcp_server.py` → clean.

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml uv.lock scripts/mcp_server.py tests/test_mcp_server.py
git commit -m "feat: thin FastMCP server over agent_core (#48)"
```

---

### Task 9: `just` recipes + `.mcp.json` client config

**Files:**
- Modify: `justfile`
- Create: `.mcp.json`

- [ ] **Step 1: Add recipes** to the end of `justfile`

```just
# Run the CV MCP server (stdio) — point an MCP client at this
mcp-server:
    uv run --group mcp python -m scripts.mcp_server

# Launch the MCP Inspector against the server for interactive testing
mcp-dev:
    uv run --group mcp mcp dev scripts/mcp_server.py
```

- [ ] **Step 2: Create `.mcp.json`** (repo root)

```json
{
  "mcpServers": {
    "jin-ho-lee-cv": {
      "command": "uv",
      "args": ["run", "--group", "mcp", "python", "-m", "scripts.mcp_server"]
    }
  }
}
```

- [ ] **Step 3: Smoke-check the server boots over stdio**

Run: `uv run --group mcp python -c "from scripts import mcp_server; import asyncio; print(sorted(t.name for t in asyncio.run(mcp_server.mcp.list_tools())))"`
Expected: prints the 6 tool names. (Avoids leaving a blocking stdio process running.)

- [ ] **Step 4: Commit**

```bash
git add justfile .mcp.json
git commit -m "feat: just mcp-server/mcp-dev recipes + .mcp.json (#48)"
```

---

### Task 10: The skill — `SKILL.md` + `reference.md` + drift-guards

**Files:**
- Create: `.claude/skills/cv/SKILL.md`
- Create: `.claude/skills/cv/reference.md`
- Test: `tests/test_skill_docs.py`

- [ ] **Step 1: Write the failing drift-guard tests**

Create `tests/test_skill_docs.py`:

```python
"""Drift-guards for the CV skill docs (no mcp dependency)."""
from __future__ import annotations

import re
from pathlib import Path

from scripts import agent_core

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO_ROOT / ".claude" / "skills" / "cv"
JUSTFILE = REPO_ROOT / "justfile"


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


def test_skill_docs_exist():
    assert (SKILL_DIR / "SKILL.md").is_file()
    assert (SKILL_DIR / "reference.md").is_file()


def test_skill_recipes_exist():
    referenced = set(re.findall(r"just ([a-z][a-z0-9-]*)", _docs_text()))
    missing = referenced - _justfile_recipes()
    assert not missing, f"skill docs reference unknown just recipes: {missing}"


def test_skill_documents_all_sections():
    ref = (SKILL_DIR / "reference.md").read_text(encoding="utf-8")
    missing = [s for s in agent_core.SECTIONS if s not in ref]
    assert not missing, f"reference.md is missing sections: {missing}"


def test_skill_frontmatter_has_name_and_description():
    text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    assert text.startswith("---")
    fm = text.split("---", 2)[1]
    assert re.search(r"^name:\s*\S", fm, re.M)
    assert re.search(r"^description:\s*\S", fm, re.M)
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_skill_docs.py -v`
Expected: FAIL — `test_skill_docs_exist` fails (files absent).

- [ ] **Step 3: Create `.claude/skills/cv/SKILL.md`**

```markdown
---
name: cv
description: >-
  Read, edit (schema-validated), and re-render Jin-Ho Lee's codified CV. Use when
  changing content/ YAML, adding or altering a project, experience, skill, award, or
  publication, checking validation, or rebuilding machine formats.
allowed-tools: Bash(just validate), Bash(just build-formats), Bash(just test), Read, Edit
---

# Codified CV — agent guide

This repo is a machine-readable CV. **`content/` (YAML + BibTeX) is the only source of
truth.** Renderers (PDF, web, JSON Resume, JSON-LD, plain text) consume it — never edit a
renderer to change content.

## Golden rules
- Never read or write `content.private/` (phone, address — gitignored PII).
- Every content change must pass `just validate` before commit.
- Don't hand-edit generated files (`data/citations.json`, snapshots, `dist/`).

## Content model
- **Sections** (top-level under `content/`): `personal`, `profile`, `skills`, `education`,
  `experience`, `projects`, `selected_projects`, `languages`, `volunteer`, `awards`,
  `publications` (from `publications.bib`), `labels`.
- **LangStrings**: short strings are inline `{ en: "...", de: "..." }` maps; long prose lives
  in per-language files (`profile.en.yaml`/`profile.de.yaml`,
  `projects/L1.en.yaml`/`projects/L1.de.yaml`). `en` is required.
- **Variants**: positioning targets `bridge` (default), `comp-bio`, `ds-ml` under a
  `variants:` key (headline / tagline / paragraphs only).
- **Cross-refs**: `experience` bullets carry `refs: [L1, C2]` → `projects/<id>.en.yaml`.
  Every ref must resolve, and every project needs both `.en.yaml` and `.de.yaml`.

## Edit loop
1. Read the file you intend to change (e.g. `content/experience.yaml`).
2. `Edit` the YAML. Keep `{ en, de }` parity for any LangString you touch.
3. Validate — current state:
   !`just validate`
4. Rebuild machine formats: `just build-formats`
5. Eyeball the diff:
   !`git -C . diff --stat`
6. Commit (atomic, plain message, no attribution trailers).

## Error recovery
- `unknown project ref 'X'` → add `content/projects/X.en.yaml` + `X.de.yaml`, or fix the ref.
- EN/DE parity error → you edited only one language; edit the matching file too.
- Reversed-period error → `end` precedes `start` (`YYYY-MM`); fix the dates.

## Programmatic twin (MCP server)
For clients that prefer tools over shell, `scripts/mcp_server.py` exposes the same operations
over MCP (stdio): `get_cv_content`, `list_cv_files`, `validate_cv`, `propose_edit` (dry-run
diff + validation), `apply_edit` (validated write), `rerun_renderers`. Launch with
`just mcp-server`; full tool + recipe map in `reference.md`.
```

- [ ] **Step 4: Create `.claude/skills/cv/reference.md`**

```markdown
# CV reference — recipes & content map

## Just recipes
| Recipe | Does |
|---|---|
| `just validate` | JSON-Schema + cross-ref + bib validation (green before commit) |
| `just test` | pytest suite |
| `just lint` | ruff check |
| `just fmt` | ruff format |
| `just build-formats` | resume.json + person.jsonld + plain text + llms.txt |
| `just build` / `just build-de` | EN / DE public PDF (needs Typst) |
| `just build-targets` | all six target × lang PDFs |
| `just web-build` | static Astro site (needs pnpm) |
| `just mcp-server` | run the CV MCP server (stdio) |
| `just mcp-dev` | MCP Inspector against the server |

## Content sections
- `personal` — name, headline, email, location, links, knowsAbout, highlight_stats
- `profile` — tagline + paragraphs (per-language file)
- `skills` — categorized skill groups
- `education` — degrees / institutions
- `experience` — roles with periods, bullets, `refs`
- `projects` — per-id, per-language project deep-dives
- `selected_projects` — featured-project ordering per target
- `languages` — spoken-language proficiency
- `volunteer` — volunteering
- `awards` — title / issuer / year
- `publications` — from `publications.bib` (+ citation counts from `data/citations.json`)
- `labels` — UI section labels (LangStrings)

## Targets
`bridge` (default), `comp-bio`, `ds-ml` — positioning variants overriding headline /
tagline / profile paragraphs only.

## MCP tools
| Tool | Hint | Does |
|---|---|---|
| `get_cv_content(lang, target, section)` | read-only | load resolved content tree |
| `list_cv_files()` | read-only | list editable YAML paths |
| `validate_cv()` | read-only | validate current tree |
| `propose_edit(path, new_content)` | read-only | diff + validation, no write |
| `apply_edit(path, new_content)` | destructive | validated write |
| `rerun_renderers(which)` | — | rebuild formats / pdf / web / all |
```

- [ ] **Step 5: Run to verify pass**

Run: `uv run pytest tests/test_skill_docs.py -v`
Expected: PASS (4 cases). `uv run ruff check tests/test_skill_docs.py` → clean.

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/cv/SKILL.md .claude/skills/cv/reference.md tests/test_skill_docs.py
git commit -m "feat: CV agent skill (SKILL.md + reference) with drift-guards (#48)"
```

---

### Task 11: Update CLAUDE.md + full green gate

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add the new files to the Layout block**

In `CLAUDE.md` under the `scripts/` line of the Layout code block, add `agent_core.py, mcp_server.py` to the scripts list, and add these lines after the `web/` line:

```
.claude/skills/cv/        committed Claude skill (agent interface) — SKILL.md + reference.md
.mcp.json                 Claude Code project-scoped MCP server config
```

- [ ] **Step 2: Add the Commands**

In the `## Commands` block, add:

```bash
just mcp-server        # run the CV MCP server (stdio) — point an MCP client at this
just mcp-dev           # MCP Inspector against the server (needs the mcp dep group)
```

- [ ] **Step 3: Add a Conventions bullet**

Append to `## Conventions`:

```markdown
- **Agent interface.** `scripts/agent_core.py` is the pure-Python core (`read_cv`,
  `list_content_files`, `validate_cv`, `propose_edit`, `apply_edit`, `rerun_renderers`);
  `scripts/mcp_server.py` (FastMCP, `mcp` dep group) and `.claude/skills/cv/` are thin
  mirrors of it. PII can never leak — `read_cv` forces `private_path=None` and edit paths
  pass `_safe_content_path` (no `..`/symlink/`content.private`). Edits are gated by the
  full `validate_tree`; the skill docs are drift-guarded against the `justfile`/schema.
```

- [ ] **Step 4: Add the Phasing row**

In the Phasing table, add after the Phase 9 row:

```markdown
| 10 | Agent interface (MCP server + skill over `content/` + validate) | ✅ Done (merged 2026-06-03, PR #TBD) |
```

(Update `PR #TBD` and commit hash when the branch merges.)

- [ ] **Step 5: Add the spec + plan to "Files to read before any phase"**

Append these two bullets to that list:

```markdown
- `docs/superpowers/specs/2026-06-03-agent-interface-mcp-skill-design.md` — Phase 10 design spec (thin MCP server + Claude skill over content/)
- `docs/superpowers/plans/2026-06-03-agent-interface-mcp-skill.md` — implementation plan for the agent interface (#48)
```

- [ ] **Step 6: Full green gate**

Run each and confirm:
- `uv run --group mcp pytest -v --tb=short` → all pass (incl. mcp + skill-doc tests)
- `uv run python -m scripts.validate` → `OK: all content files validate`
- `uv run ruff check .` → clean
- `uv run ruff format --check .` → clean (run `just fmt` if needed, then re-stage)

- [ ] **Step 7: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: record agent interface (Phase 10) in CLAUDE.md (#48)"
```

---

## Self-Review

**Spec coverage:**
- Read content → Task 2 (`read_cv`) + Task 8 tool. ✓
- Propose gated by schema/validate → Tasks 5 + 6 (full-tree `validate_tree`). ✓
- Re-run renderers → Task 7 + Task 8 tool. ✓
- Path/PII/injection guards → Task 1 (`_safe_content_path`), Tasks 2/3 (PII), Task 7 (whitelist). ✓
- MCP server + annotations + structured output + entry point + dep + client config → Tasks 8 + 9. ✓
- Skill + drift-guard → Task 10. ✓
- CLAUDE.md update → Task 11. ✓
- Future-public seam → already satisfied (`content_dir`/`schema_path` params throughout). ✓

**Trimmed vs. spec (intentional, low-risk):** the optional `[project.scripts] cv-mcp` console entry is dropped — the repo has no `[build-system]`, so adding console scripts risks the build; `just mcp-server` / `python -m scripts.mcp_server` cover invocation. Section-name drift is guarded as a *completeness* check (`reference.md` documents every `SECTIONS` entry) rather than fragile prose parsing.

**Type consistency:** core dict keys (`diff/valid/errors/warnings`, `applied`, `ran/ok/skipped/output`) match the Pydantic models in Task 8 exactly. `_resolve_recipes`/`rerun_renderers`/`SECTIONS`/`_RECIPE_PLAN` names are consistent across Tasks 7/8/10.

**Placeholder scan:** every code/test step contains complete code; the only `TBD` is the post-merge PR number in the CLAUDE.md Phasing row (correct — it doesn't exist yet).
