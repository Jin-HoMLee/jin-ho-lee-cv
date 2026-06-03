"""Tests for the agent-facing core (read/validate/propose/apply/rerun)."""
from __future__ import annotations

import shutil
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
