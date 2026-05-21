"""Validate CV content against the JSON Schema and check cross-references."""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

from jsonschema import Draft202012Validator
from ruamel.yaml import YAML


yaml = YAML(typ="safe")


class ValidationError(Exception):
    """Raised when content fails schema or cross-reference validation."""


@dataclass
class FileError:
    path: Path
    message: str

    def __str__(self) -> str:
        return f"{self.path}: {self.message}"


def _load_yaml(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return yaml.load(f)


def _load_schema(schema_path: Path) -> dict:
    with schema_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _validator_for(schema_def: str, schema_path: Path) -> Draft202012Validator:
    full = _load_schema(schema_path)
    definition = full["$defs"].get(schema_def)
    if definition is None:
        raise ValidationError(f"Unknown schema definition: {schema_def!r}")
    # Resolve $ref against the parent schema
    sub = {**definition, "$defs": full["$defs"]}
    return Draft202012Validator(sub)


def validate_file(
    path: Path,
    *,
    schema_def: str,
    schema_path: Path,
    known_project_ids: set[str] | None = None,
) -> None:
    """Validate a single YAML file against the given schema definition.

    For `schema_def == "experience"`, also checks that every ref points to a known project.
    Raises ValidationError on failure.
    """
    data = _load_yaml(path)
    validator = _validator_for(schema_def, schema_path)
    errors = sorted(validator.iter_errors(data), key=lambda e: e.path)
    if errors:
        joined = "; ".join(
            f"{'.'.join(str(p) for p in e.path) or '<root>'}: {e.message}"
            for e in errors
        )
        raise ValidationError(joined)

    if schema_def == "experience" and known_project_ids is not None:
        for entry in data:
            for bullet in entry.get("bullets", []):
                for ref in bullet.get("refs", []):
                    if ref not in known_project_ids:
                        raise ValidationError(
                            f"unknown project ref {ref!r}"
                        )


def _enumerate_project_ids(content_dir: Path) -> set[str]:
    ids: set[str] = set()
    for p in (content_dir / "projects").glob("*.en.yaml"):
        ids.add(p.name.split(".")[0])
    return ids


# Mapping from filename glob → schema definition name
_FILE_RULES: list[tuple[str, str]] = [
    ("personal.yaml", "personal"),
    ("profile.*.yaml", "profile"),
    ("skills.yaml", "skills"),
    ("education.yaml", "education"),
    ("experience.yaml", "experience"),
    ("languages.yaml", "languages"),
    ("volunteer.yaml", "volunteer"),
]


def validate_tree(content_dir: Path, schema_path: Path) -> list[FileError]:
    """Validate every recognized file under content/. Returns list of errors (empty = clean)."""
    errors: list[FileError] = []
    project_ids = _enumerate_project_ids(content_dir)

    for pattern, def_name in _FILE_RULES:
        for path in content_dir.glob(pattern):
            try:
                kwargs = {}
                if def_name == "experience":
                    kwargs["known_project_ids"] = project_ids
                validate_file(path, schema_def=def_name, schema_path=schema_path, **kwargs)
            except ValidationError as e:
                errors.append(FileError(path, str(e)))

    for path in (content_dir / "projects").glob("*.yaml"):
        try:
            validate_file(path, schema_def="project", schema_path=schema_path)
        except ValidationError as e:
            errors.append(FileError(path, str(e)))

    return errors


def main() -> int:
    repo_root = Path(__file__).parent.parent
    content_dir = repo_root / "content"
    schema_path = repo_root / "schema" / "cv.schema.json"

    if not content_dir.exists():
        print(f"ERROR: no content/ directory at {content_dir}", file=sys.stderr)
        return 2

    errors = validate_tree(content_dir, schema_path)
    if errors:
        print(f"FAIL: {len(errors)} validation error(s)", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    print("OK: all content files validate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
