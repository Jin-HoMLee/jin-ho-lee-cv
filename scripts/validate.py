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
    """Enumerate project IDs from filenames in content/projects/*.en.yaml.

    Note: only the filename portion is checked here. Content-level filename-vs-id
    consistency is enforced by scripts.content_loader._load_projects.
    """
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
    ("selected_projects.yaml", "selected_projects"),
    ("languages.yaml", "languages"),
    ("volunteer.yaml", "volunteer"),
    ("awards.yaml", "awards"),
]


def _validate_publications(content_dir: Path) -> list[FileError]:
    bib_path = content_dir / "publications.bib"
    if not bib_path.exists():
        return [FileError(bib_path, "publications.bib missing")]
    try:
        from scripts.bib_loader import load_publications  # local import avoids cycles
        load_publications(bib_path)
    except Exception as e:
        return [FileError(bib_path, str(e))]
    return []


def _validate_profile_variant_parity(content_dir: Path) -> list[FileError]:
    """profile.en.yaml and profile.de.yaml must declare the same variant targets
    with the same overridden keys (EN/DE positioning parity)."""
    en_path = content_dir / "profile.en.yaml"
    de_path = content_dir / "profile.de.yaml"
    if not (en_path.exists() and de_path.exists()):
        return []
    en = (_load_yaml(en_path).get("variants") or {})
    de = (_load_yaml(de_path).get("variants") or {})
    if not (isinstance(en, dict) and isinstance(de, dict)):
        return []  # malformed structure; the schema validator reports it
    errors: list[FileError] = []
    for target in sorted(set(en) | set(de)):
        en_val = en.get(target)
        de_val = de.get(target)
        en_keys = set(en_val) if isinstance(en_val, dict) else set()
        de_keys = set(de_val) if isinstance(de_val, dict) else set()
        if en_keys != de_keys:
            errors.append(FileError(
                de_path,
                f"variant {target!r} key mismatch EN/DE: "
                f"en={sorted(en_keys)} de={sorted(de_keys)}",
            ))
    return errors


def _validate_headline_variant_completeness(content_dir: Path) -> list[FileError]:
    """Each personal headline variant must define both 'en' and 'de' (parity with
    the bilingual base headline)."""
    path = content_dir / "personal.yaml"
    if not path.exists():
        return []
    variants = (_load_yaml(path).get("variants") or {})
    if not isinstance(variants, dict):
        return []  # malformed structure; the schema validator reports it
    errors: list[FileError] = []
    for target in sorted(variants):
        spec = variants.get(target)
        headline = spec.get("headline") if isinstance(spec, dict) else None
        if isinstance(headline, dict) and not ({"en", "de"} <= set(headline)):
            errors.append(FileError(
                path,
                f"variant {target!r} headline must define both 'en' and 'de'",
            ))
    return errors


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

    selected_path = content_dir / "selected_projects.yaml"
    if selected_path.exists():
        try:
            selected = _load_yaml(selected_path)
            if isinstance(selected, dict):  # else the schema validator reports the type error
                all_ids = {pid for order in selected.values() for pid in order}
                unknown = sorted(pid for pid in all_ids if pid not in project_ids)
                if unknown:
                    errors.append(FileError(
                        selected_path,
                        f"references unknown project id(s): {unknown}",
                    ))
        except Exception as e:
            errors.append(FileError(selected_path, str(e)))

    for path in (content_dir / "projects").glob("*.yaml"):
        try:
            validate_file(path, schema_def="project", schema_path=schema_path)
        except ValidationError as e:
            errors.append(FileError(path, str(e)))

    # Project DE-EN file parity
    project_dir = content_dir / "projects"
    en_ids = {p.name.split(".")[0] for p in project_dir.glob("*.en.yaml")}
    de_ids = {p.name.split(".")[0] for p in project_dir.glob("*.de.yaml")}
    for missing_id in en_ids - de_ids:
        errors.append(FileError(
            project_dir / f"{missing_id}.de.yaml",
            "missing DE counterpart for EN project file",
        ))
    for missing_id in de_ids - en_ids:
        errors.append(FileError(
            project_dir / f"{missing_id}.en.yaml",
            "missing EN counterpart for DE project file",
        ))

    errors.extend(_validate_profile_variant_parity(content_dir))
    errors.extend(_validate_headline_variant_completeness(content_dir))
    errors.extend(_validate_publications(content_dir))
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
