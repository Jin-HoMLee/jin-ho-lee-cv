"""Tests for scripts.validate — content validation suite."""
from pathlib import Path

import pytest

from scripts.validate import ValidationError, validate_file, validate_tree


FIXTURES = Path(__file__).parent / "fixtures" / "invalid_yaml"


def test_missing_required_field_fails(schema_path):
    """personal.yaml without required 'email' should fail validation."""
    bad = FIXTURES / "missing_required.yaml"
    with pytest.raises(ValidationError) as exc:
        validate_file(bad, schema_def="personal", schema_path=schema_path)
    assert "email" in str(exc.value)


def test_wrong_type_fails(schema_path):
    """personal.yaml with email as integer should fail validation."""
    bad = FIXTURES / "wrong_type.yaml"
    with pytest.raises(ValidationError):
        validate_file(bad, schema_def="personal", schema_path=schema_path)


def test_broken_project_ref_fails(content_dir, schema_path, tmp_path):
    """experience.yaml with refs: [L99] should fail cross-reference check."""
    bad = FIXTURES / "bad_project_ref.yaml"
    with pytest.raises(ValidationError) as exc:
        validate_file(bad, schema_def="experience", schema_path=schema_path,
                      known_project_ids={"L1", "L2"})
    assert "L99" in str(exc.value) or "unknown project" in str(exc.value).lower()


def test_validate_tree_returns_empty_on_clean_content(content_dir, schema_path):
    """validate_tree on the real content/ should produce no errors (once migrated)."""
    errors = validate_tree(content_dir, schema_path)
    assert errors == [], f"Unexpected validation errors: {errors}"


def _write_minimal_content_tree(content: Path) -> None:
    """Write the minimal set of valid top-level content files for parity tests."""
    (content / "personal.yaml").write_text(
        "name:\n  given: Test\n  family: User\n"
        "email: t@example.com\n"
        "location: { city: X, country: DE }\n"
        "links: { linkedin: null, github: null, researchgate: null, orcid: null }\n"
        "photo: assets/photo.jpg\n"
        "headline: { en: T }\n"
    )
    (content / "profile.en.yaml").write_text("tagline: T\nparagraphs: [P]\n")
    (content / "skills.yaml").write_text("categories: []\n")
    (content / "education.yaml").write_text("[]\n")
    (content / "experience.yaml").write_text("[]\n")
    (content / "languages.yaml").write_text("[]\n")
    (content / "volunteer.yaml").write_text("categories: []\n")
    (content / "publications.bib").write_text("")
    (content / "labels.yaml").write_text(
        "sections: { profile: { en: P }, experience: { en: E }, "
        "education: { en: E }, skills: { en: S }, languages: { en: L }, volunteer: { en: V } }\n"
        "months_abbr: []\n"
        "proficiency: { native: { en: n }, fluent: { en: f }, basic: { en: b }, passive: { en: p } }\n"
    )


_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schema" / "cv.schema.json"


def test_de_en_project_file_parity_fails_on_missing_de(tmp_path):
    """validate_tree should report an error when an .en.yaml exists without matching .de.yaml."""
    content = tmp_path / "content"
    (content / "projects").mkdir(parents=True)
    _write_minimal_content_tree(content)

    # The asymmetry: L1 exists in EN but not DE
    (content / "projects" / "L1.en.yaml").write_text(
        "id: L1\ncategory: life-science\ntitle: T\nsummary: S\n"
        "role: R\nperiod: { start: '2020-01', end: '2020-02' }\n"
        "technologies: [X]\ncontributions: [C]\noutcome: O\n"
    )

    errors = validate_tree(content, _SCHEMA_PATH)
    assert any("L1.de.yaml" in str(e) for e in errors), (
        f"expected missing-DE-file error, got: {errors}"
    )


def test_malformed_doi_in_bib_fails_validate_tree(tmp_path):
    """A malformed doi in publications.bib must surface as a validation error."""
    content = tmp_path / "content"
    (content / "projects").mkdir(parents=True)
    _write_minimal_content_tree(content)
    (content / "publications.bib").write_text(
        "@article{x, author={Lee, J.}, title={T}, year={2019}, journal={J}, "
        "type={article}, authorship={first}, doi={not-a-doi}}\n"
    )
    errors = validate_tree(content, _SCHEMA_PATH)
    assert any("doi" in str(e) for e in errors), f"expected a doi error, got: {errors}"


def test_de_en_project_file_parity_fails_on_missing_en(tmp_path):
    """validate_tree should also catch DE-only project files (something's wrong if EN is missing)."""
    content = tmp_path / "content"
    (content / "projects").mkdir(parents=True)
    _write_minimal_content_tree(content)

    (content / "projects" / "L1.de.yaml").write_text(
        "id: L1\ncategory: life-science\ntitle: T\nsummary: S\n"
        "role: R\nperiod: { start: '2020-01', end: '2020-02' }\n"
        "technologies: [X]\ncontributions: [C]\noutcome: O\n"
    )

    errors = validate_tree(content, _SCHEMA_PATH)
    assert any("L1.en.yaml" in str(e) for e in errors), (
        f"expected missing-EN-file error, got: {errors}"
    )
