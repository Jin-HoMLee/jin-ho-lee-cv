"""Tests for scripts.validate — content validation suite."""

from pathlib import Path

import pytest

from scripts.validate import ValidationError, validate_file, validate_tree


FIXTURES = Path(__file__).parent / "fixtures" / "invalid_yaml"
REPO_ROOT = Path(__file__).resolve().parent.parent


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
        validate_file(
            bad, schema_def="experience", schema_path=schema_path, known_project_ids={"L1", "L2"}
        )
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
    (content / "faq.yaml").write_text(
        "faqs:\n  - id: q1\n    question: { en: Q, de: Q }\n    answer: { en: A, de: A }\n"
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


def test_malformed_awards_fails(schema_path, tmp_path):
    """An award missing the required 'issuer' should fail validation."""
    bad = tmp_path / "awards.yaml"
    bad.write_text('- title: { en: "X" }\n  year: 2020\n')
    with pytest.raises(ValidationError):
        validate_file(bad, schema_def="awards", schema_path=schema_path)


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


_PROJECT_STUB = (
    "id: {pid}\ncategory: life-science\ntitle: T\nsummary: S\n"
    "role: R\nperiod: {{ start: '2020-01', end: '2020-02' }}\n"
    "technologies: [X]\ncontributions: [C]\noutcome: O\n"
)


def test_selected_projects_map_unknown_id_fails(tmp_path):
    """selected_projects.yaml whose target list contains an unknown id must surface an error.

    Writes a map-shaped file with a bogus id ZZ9 in the comp-bio target list alongside a
    valid id L1.  Expects validate_tree to return at least one error referencing ZZ9.
    """
    content = tmp_path / "content"
    (content / "projects").mkdir(parents=True)
    _write_minimal_content_tree(content)

    # Provide a valid paired project so L1 is a known id and parity checks pass.
    (content / "projects" / "L1.en.yaml").write_text(_PROJECT_STUB.format(pid="L1"))
    (content / "projects" / "L1.de.yaml").write_text(_PROJECT_STUB.format(pid="L1"))

    # Map shape: bridge is required by schema; comp-bio introduces the unknown id ZZ9.
    (content / "selected_projects.yaml").write_text("bridge: [L1]\ncomp-bio: [L1, ZZ9]\n")

    errors = validate_tree(content, _SCHEMA_PATH)
    assert any("ZZ9" in str(e) for e in errors), (
        f"expected unknown-id error referencing ZZ9, got: {errors}"
    )


# --- #99: refs-less bullets must fail validation loudly ---


def test_refs_less_bullet_fails(schema_path, tmp_path):
    """A bullet with only langmap keys (no `refs:`) collapses to a string in every renderer.

    The schema must require `refs:` so such a bullet fails `just validate` loudly at
    authoring time, instead of latently breaking ~4 renderers at build time (#99).
    """
    bad = tmp_path / "experience.yaml"
    bad.write_text(
        "- id: x\n  org: { name: O }\n  role: { en: R, de: R }\n"
        "  period: { start: '2024-05', end: '2025-07' }\n"
        "  bullets:\n    - { en: 'did a thing', de: 'tat etwas' }\n"
    )
    with pytest.raises(ValidationError) as exc:
        validate_file(bad, schema_def="experience", schema_path=schema_path)
    assert "refs" in str(exc.value)


def test_refs_empty_list_bullet_passes(schema_path, tmp_path):
    """An explicit `refs: []` is the honest way to author a bullet citing no project."""
    good = tmp_path / "experience.yaml"
    good.write_text(
        "- id: x\n  org: { name: O }\n  role: { en: R, de: R }\n"
        "  period: { start: '2024-05', end: '2025-07' }\n"
        "  bullets:\n    - { en: 'did a thing', de: 'tat etwas', refs: [] }\n"
    )
    validate_file(good, schema_def="experience", schema_path=schema_path)


# --- #42: content-integrity (reversed periods + advisory date warnings) ---
from datetime import date  # noqa: E402

_EXP = (
    "- id: x\n  org: {{name: O}}\n  role: {{en: R, de: R}}\n"
    '  period: {{start: "{start}", end: {end}}}\n  bullets: []\n'
)


def _write_exp(tmp_path, start, end):
    end_lit = "null" if end is None else f'"{end}"'
    (tmp_path / "experience.yaml").write_text(_EXP.format(start=start, end=end_lit))
    (tmp_path / "projects").mkdir(exist_ok=True)


def test_reversed_period_is_error(tmp_path):
    from scripts.validate import _validate_periods

    _write_exp(tmp_path, "2025-07", "2024-05")
    errors = _validate_periods(tmp_path)
    assert len(errors) == 1
    assert "end" in str(errors[0]).lower() and "start" in str(errors[0]).lower()


def test_forward_period_is_clean(tmp_path):
    from scripts.validate import _validate_periods

    _write_exp(tmp_path, "2024-05", "2025-07")
    assert _validate_periods(tmp_path) == []


def test_null_end_period_is_clean(tmp_path):
    from scripts.validate import _validate_periods

    _write_exp(tmp_path, "2024-05", None)
    assert _validate_periods(tmp_path) == []


def test_date_warnings_flags_future_and_ancient(tmp_path):
    from scripts.validate import date_warnings

    _write_exp(tmp_path, "2010-01", "2035-01")
    warns = date_warnings(tmp_path, today=date(2026, 6, 1))
    msgs = " ".join(str(w) for w in warns)
    assert "2010-01" in msgs  # < 2014 floor
    assert "2035-01" in msgs  # > 2026 + 5


def test_date_warnings_clean_within_bounds(tmp_path):
    from scripts.validate import date_warnings

    _write_exp(tmp_path, "2024-05", "2025-07")
    assert date_warnings(tmp_path, today=date(2026, 6, 1)) == []


def test_real_content_has_no_integrity_errors_or_warnings(content_dir):
    from scripts.validate import _validate_periods, date_warnings

    assert _validate_periods(content_dir) == []
    assert date_warnings(content_dir, today=date(2026, 6, 1)) == []


def test_date_warnings_boundaries_are_clean(tmp_path):
    """year == 2014 (floor, inclusive-ok) and year == today.year+5 (ceiling, > is False) → no warnings."""
    from scripts.validate import date_warnings

    _write_exp(tmp_path, "2014-01", "2031-12")
    assert date_warnings(tmp_path, today=date(2026, 6, 1)) == []


def test_date_warnings_skips_non_yyyymm(tmp_path):
    """A non-'YYYY-MM' end value (e.g. 'present') is skipped, not crashed — callable in isolation."""
    from scripts.validate import date_warnings

    (tmp_path / "experience.yaml").write_text(
        "- id: x\n  org: {name: O}\n  role: {en: R, de: R}\n"
        '  period: {start: "2024-05", end: "present"}\n  bullets: []\n'
    )
    (tmp_path / "projects").mkdir()
    assert date_warnings(tmp_path, today=date(2026, 6, 1)) == []


# --- Phase 13: master-cv overlay validation ---


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
    (tmp_path / "timeline.yaml").write_text("- id: x\n  type: not-a-real-type\n", encoding="utf-8")
    errors = validate_master_cv(tmp_path, schema)
    assert errors and any("timeline.yaml" in str(e) for e in errors)
