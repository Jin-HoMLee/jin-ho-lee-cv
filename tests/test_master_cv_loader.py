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
    (dir_ / "opinions.md").write_text("# How I think\n\nI value reproducibility.\n", encoding="utf-8")


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
    assert mcv.opinions is not None
    assert "I value reproducibility." in mcv.opinions


def test_resolves_from_env(tmp_path, monkeypatch):
    _seed(tmp_path / "mcv")
    monkeypatch.setenv("MASTER_CV_DIR", str(tmp_path / "mcv"))
    mcv = load_master_cv()
    assert mcv is not None and mcv.timeline[0]["type"] == "research"


def test_opinions_none_when_file_absent(tmp_path):
    (tmp_path / "mcv").mkdir()
    mcv = load_master_cv(tmp_path / "mcv")
    assert mcv is not None and mcv.opinions is None


def test_present_dir_with_missing_files_is_tolerant(tmp_path):
    (tmp_path / "mcv").mkdir()
    mcv = load_master_cv(tmp_path / "mcv")
    assert mcv == MasterCV(timeline=[], inventory={}, narrative={})
