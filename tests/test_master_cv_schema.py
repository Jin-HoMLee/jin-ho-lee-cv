"""Schema validation for the master-cv/ overlay (timeline + inventory)."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.validate import ValidationError, _validator_for

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / "schema" / "master-cv.schema.json"


def _errors(def_name, data):
    validator = _validator_for(def_name, SCHEMA_PATH)
    return sorted(validator.iter_errors(data), key=lambda e: list(e.path))


def test_valid_timeline_entry_passes():
    data = [{"id": "imp-vienna-2019", "type": "research", "start": "2019-08", "end": "2019-10"}]
    assert _errors("timeline", data) == []


def test_timeline_entry_requires_id_and_type():
    assert _errors("timeline", [{"title": "no id or type"}])


def test_timeline_rejects_unknown_type():
    assert _errors("timeline", [{"id": "x", "type": "not-a-type"}])


def test_timeline_accepts_year_only_and_null_dates():
    data = [{"id": "x", "type": "certificate", "start": "2099", "end": None}]
    assert _errors("timeline", data) == []


def test_timeline_rejects_malformed_date():
    assert _errors("timeline", [{"id": "x", "type": "award", "start": "2099-13"}])


def test_timeline_allows_extra_type_specific_fields():
    data = [{"id": "x", "type": "education", "field": "Bioinformatics", "thesis": "T"}]
    assert _errors("timeline", data) == []


def test_valid_inventory_passes():
    assert _errors("inventory", {"programming": ["Python", "R"], "domains": ["GenAI"]}) == []


def test_inventory_rejects_non_string_list_values():
    assert _errors("inventory", {"programming": [1, 2, 3]})


def test_validator_for_unknown_def_raises():
    with pytest.raises(ValidationError):
        _validator_for("nonexistent", SCHEMA_PATH)
