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


def test_validate_cv_clean(cv_tree):
    res = agent_core.validate_cv(content_dir=cv_tree)
    assert res["valid"] is True
    assert res["errors"] == []


def test_validate_cv_detects_break(cv_tree):
    (cv_tree / "personal.yaml").write_text("{}\n", encoding="utf-8")
    res = agent_core.validate_cv(content_dir=cv_tree)
    assert res["valid"] is False
    assert res["errors"]


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


def test_propose_edit_malformed_yaml_returns_dict(cv_tree):
    """Malformed YAML must return valid:False (not raise) — the primary LLM failure mode."""
    rel = "personal.yaml"
    current = (cv_tree / rel).read_text(encoding="utf-8")
    res = agent_core.propose_edit(rel, "foo: [unclosed\n", content_dir=cv_tree)
    assert isinstance(res, dict)
    assert res["valid"] is False
    assert res["errors"]
    assert "parse" in res["errors"][0].lower() or "yaml" in res["errors"][0].lower()
    # Source must be completely untouched
    assert (cv_tree / rel).read_text(encoding="utf-8") == current


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

    monkeypatch.setattr(
        agent_core.subprocess, "run", lambda argv, **kw: calls.append((argv, kw)) or FakeProc()
    )
    monkeypatch.setattr(agent_core.shutil, "which", lambda tool: "/usr/bin/" + tool)
    res = agent_core.rerun_renderers("formats", content_dir=cv_tree)
    assert res["ok"] is True
    assert res["ran"] == ["build-formats"]
    argv, kw = calls[0]
    assert argv == ["just", "build-formats"]
    assert kw.get("shell") in (None, False)
