"""Tests for the CV_PRIVATE_YAML override in pdf.build (no Typst needed)."""

from pathlib import Path

from pdf.build import REPO_ROOT, _private_yaml_path


def test_private_yaml_path_defaults_to_repo_content_private(monkeypatch):
    monkeypatch.delenv("CV_PRIVATE_YAML", raising=False)
    assert _private_yaml_path() == REPO_ROOT / "content.private" / "private.yaml"


def test_private_yaml_path_honors_env_override(monkeypatch, tmp_path):
    target = tmp_path / "content.private" / "private.yaml"
    monkeypatch.setenv("CV_PRIVATE_YAML", str(target))
    assert _private_yaml_path() == Path(str(target))
