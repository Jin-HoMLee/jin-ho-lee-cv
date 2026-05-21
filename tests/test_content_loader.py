"""Tests for scripts.content_loader."""
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


def test_load_content_nonexistent_private_is_ignored(content_dir, tmp_path):
    """A private_path that doesn't exist should be silently ignored, not error."""
    ghost = tmp_path / "does_not_exist.yaml"
    content = load_content(content_dir, private_path=ghost)
    assert "phone" not in content["personal"]
    assert "address" not in content["personal"]
