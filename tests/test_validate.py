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
