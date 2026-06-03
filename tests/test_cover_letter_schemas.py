"""The cover-letter schemas are valid Draft 2020-12 and the committed examples validate."""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator
from ruamel.yaml import YAML

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = REPO_ROOT / "schema"
EXAMPLE_DIR = REPO_ROOT / "applications.example"
_yaml = YAML(typ="safe")


def _load_yaml(path: Path) -> dict:
    return _yaml.load(path.read_text(encoding="utf-8"))


def _load_schema(name: str) -> dict:
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


def test_application_schema_is_valid():
    Draft202012Validator.check_schema(_load_schema("application.schema.json"))


def test_profile_schema_is_valid():
    Draft202012Validator.check_schema(_load_schema("profile.schema.json"))


def test_example_application_validates():
    schema = _load_schema("application.schema.json")
    data = _load_yaml(EXAMPLE_DIR / "example-company-role-2026-06" / "application.example.yaml")
    assert Draft202012Validator(schema).is_valid(data), list(
        Draft202012Validator(schema).iter_errors(data)
    )


def test_example_profile_validates():
    schema = _load_schema("profile.schema.json")
    data = _load_yaml(EXAMPLE_DIR / "profile.example.yaml")
    assert Draft202012Validator(schema).is_valid(data), list(
        Draft202012Validator(schema).iter_errors(data)
    )
