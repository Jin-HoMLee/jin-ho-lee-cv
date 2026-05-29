"""Tests for scripts.content_loader."""
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
                "experience", "projects", "languages", "volunteer", "publications", "labels"):
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


def test_load_content_rejects_id_filename_mismatch(tmp_path):
    """A project file whose id field doesn't match its filename should raise."""
    fake = tmp_path / "content"
    fake.mkdir()
    (fake / "personal.yaml").write_text(
        "name:\n  given: T\n  family: U\n"
        "headline:\n  en: H\n"
        "email: a@b.com\n"
        "location: {city: X, country: Y}\n"
        "links: {}\n"
    )
    (fake / "profile.en.yaml").write_text("paragraphs:\n  - p\n")
    (fake / "skills.yaml").write_text(
        "categories:\n"
        "  - name: {en: A}\n"
        "    groups:\n"
        "      - label: {en: B}\n"
        "        items: [x]\n"
    )
    (fake / "education.yaml").write_text(
        "- degree: {en: D}\n  institution: I\n  year: 2020\n"
    )
    (fake / "experience.yaml").write_text(
        "- id: x\n"
        "  org: {name: O}\n"
        "  role: {en: R}\n"
        "  period: {start: '2020-01', end: '2021-01'}\n"
        "  bullets:\n    - en: b\n"
    )
    (fake / "languages.yaml").write_text(
        "- name: {en: English}\n  proficiency: fluent\n"
    )
    (fake / "volunteer.yaml").write_text(
        "categories:\n"
        "  - name: {en: A}\n"
        "    entries: [x]\n"
    )
    (fake / "publications.bib").write_text(
        "@article{x, author={X}, title={T}, year={2020},"
        " journal={J}, type={article}, authorship={first}}\n"
    )
    projects_dir = fake / "projects"
    projects_dir.mkdir()
    (projects_dir / "L1.en.yaml").write_text(
        "id: L99\n"  # mismatch: filename says L1 but id field says L99
        "category: life-science\n"
        "title: t\n"
        "summary: s\n"
        "role: r\n"
        "period: {start: '2020-01'}\n"
        "technologies: [a]\n"
        "contributions: [c]\n"
        "outcome: o\n"
    )
    with pytest.raises(ValueError, match="does not match filename"):
        load_content(fake, private_path=None)


def test_corrected_project_periods(content_dir):
    content = load_content(content_dir, private_path=None, lang="en")
    projects = content["projects"]
    assert projects["L1"]["period"] == {"start": "2015-08", "end": "2015-11"}
    assert projects["L2"]["period"] == {"start": "2014-04", "end": "2014-05"}
    assert projects["L3"]["period"]["start"] == "2017-02"


def test_research_entry_start_not_after_earliest_subproject(content_dir):
    content = load_content(content_dir, private_path=None, lang="en")
    research = next(e for e in content["experience"] if e["id"] == "research")
    assert research["period"]["start"] == "2014-04"


def test_skills_additions_present(content_dir):
    content = load_content(content_dir, private_path=None, lang="en")
    bioml = next(c for c in content["skills"]["categories"] if c["name"]["en"] == "Bioinformatics & ML")
    groups = {g["label"]["en"]: g["items"] for g in bioml["groups"]}
    assert "MapSplice" in groups["Genomics"]
    assert "samtools/bcftools" in groups["Genomics"]
    assert "Structural Biology" in groups
    assert set(groups["Structural Biology"]) == {"TCRdock", "AlphaFold v2", "Mol*"}


def test_italian_language_present(content_dir):
    content = load_content(content_dir, private_path=None, lang="en")
    names = {lang["name"]["en"] for lang in content["languages"]}
    assert "Italian" in names
