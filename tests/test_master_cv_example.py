"""The committed synthetic master-cv.example/ must validate against the schema."""

from __future__ import annotations

from pathlib import Path

from ruamel.yaml import YAML

from scripts.validate import _validator_for

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_DIR = REPO_ROOT / "master-cv.example"
SCHEMA_PATH = REPO_ROOT / "schema" / "master-cv.schema.json"
yaml = YAML(typ="safe")


def _load(name):
    return yaml.load((EXAMPLE_DIR / name).read_text(encoding="utf-8"))


def test_example_timeline_validates():
    validator = _validator_for("timeline", SCHEMA_PATH)
    assert list(validator.iter_errors(_load("timeline.yaml"))) == []


def test_example_inventory_validates():
    validator = _validator_for("inventory", SCHEMA_PATH)
    assert list(validator.iter_errors(_load("inventory.yaml"))) == []


def test_example_covers_multiple_entry_types():
    types = {e["type"] for e in _load("timeline.yaml")}
    # Must exercise the breadth the real overlay carries (all 7 enum types).
    assert {
        "employment",
        "research",
        "internship",
        "education",
        "certificate",
        "award",
        "volunteering",
    } <= types


def test_example_has_narrative_files():
    stems = {p.stem for p in (EXAMPLE_DIR / "narrative").glob("*.md")}
    assert {"career-story", "personal"} <= stems
