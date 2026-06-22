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
