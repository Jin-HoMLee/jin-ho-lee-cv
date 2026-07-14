"""Validate CV content against the JSON Schema and check cross-references."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from datetime import date
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
            f"{'.'.join(str(p) for p in e.path) or '<root>'}: {e.message}" for e in errors
        )
        raise ValidationError(joined)

    if schema_def == "experience" and known_project_ids is not None:
        for entry in data:
            for bullet in entry.get("bullets", []):
                for ref in bullet.get("refs", []):
                    if ref not in known_project_ids:
                        raise ValidationError(f"unknown project ref {ref!r}")


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
    en = _load_yaml(en_path).get("variants") or {}
    de = _load_yaml(de_path).get("variants") or {}
    if not (isinstance(en, dict) and isinstance(de, dict)):
        return []  # malformed structure; the schema validator reports it
    errors: list[FileError] = []
    for target in sorted(set(en) | set(de)):
        en_val = en.get(target)
        de_val = de.get(target)
        en_keys = set(en_val) if isinstance(en_val, dict) else set()
        de_keys = set(de_val) if isinstance(de_val, dict) else set()
        if en_keys != de_keys:
            errors.append(
                FileError(
                    de_path,
                    f"variant {target!r} key mismatch EN/DE: "
                    f"en={sorted(en_keys)} de={sorted(de_keys)}",
                )
            )
    return errors


def _validate_headline_variant_completeness(content_dir: Path) -> list[FileError]:
    """Each personal headline variant must define both 'en' and 'de' (parity with
    the bilingual base headline)."""
    path = content_dir / "personal.yaml"
    if not path.exists():
        return []
    variants = _load_yaml(path).get("variants") or {}
    if not isinstance(variants, dict):
        return []  # malformed structure; the schema validator reports it
    errors: list[FileError] = []
    for target in sorted(variants):
        spec = variants.get(target)
        headline = spec.get("headline") if isinstance(spec, dict) else None
        if isinstance(headline, dict) and not ({"en", "de"} <= set(headline)):
            errors.append(
                FileError(
                    path,
                    f"variant {target!r} headline must define both 'en' and 'de'",
                )
            )
    return errors


def _iter_periods(content_dir: Path):
    """Yield (path, period_dict) for every period in experience + projects (.en files)."""
    exp_path = content_dir / "experience.yaml"
    if exp_path.exists():
        for entry in _load_yaml(exp_path) or []:
            period = entry.get("period") if isinstance(entry, dict) else None
            if isinstance(period, dict):
                yield exp_path, period
    for proj_path in sorted((content_dir / "projects").glob("*.en.yaml")):
        data = _load_yaml(proj_path)
        period = data.get("period") if isinstance(data, dict) else None
        if isinstance(period, dict):
            yield proj_path, period


def _validate_periods(content_dir: Path) -> list[FileError]:
    """Hard error when a period's end precedes its start (lexicographic on 'YYYY-MM')."""
    errors: list[FileError] = []
    for path, period in _iter_periods(content_dir):
        start, end = period.get("start"), period.get("end")
        if start and end and end < start:
            errors.append(FileError(path, f"period end {end!r} precedes start {start!r}"))
    return errors


def validate_master_cv(master_cv_dir: Path, schema_path: Path) -> list[FileError]:
    """Validate the master-cv overlay if present; graceful skip when absent.

    timeline.yaml → 'timeline' def, inventory.yaml → 'inventory' def. narrative/*.md
    is free-form and unchecked. Absent dir or absent file ⇒ no error.
    """
    if not master_cv_dir.is_dir():
        return []
    errors: list[FileError] = []
    for filename, def_name in (("timeline.yaml", "timeline"), ("inventory.yaml", "inventory")):
        path = master_cv_dir / filename
        if not path.exists():
            continue
        try:
            data = _load_yaml(path)
            validator = _validator_for(def_name, schema_path)
            schema_errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
            if schema_errors:
                joined = "; ".join(
                    f"{'.'.join(str(p) for p in e.path) or '<root>'}: {e.message}"
                    for e in schema_errors
                )
                errors.append(FileError(path, joined))
        except Exception as e:  # malformed YAML, etc.
            errors.append(FileError(path, str(e)))
    return errors


def validate_faq(content_dir: Path, schema_path: Path) -> list[FileError]:
    """Validate content/faq.yaml: schema-valid, bilingual, unique ids, no script breakout.

    faq.yaml is a REQUIRED content file (Phase 14) - absence is an error, not a skip.

    FAQ text is inlined into a `<script type="application/ld+json">` block on the site,
    and faq.yaml is agent-editable via agent_core.apply_edit (which gates on validate_tree).
    A "</script" substring would close that tag early and let the rest parse as markup, so
    reject it here. FaqSection.astro also escapes "<" at render time; this is the earlier,
    louder of the two backstops - a bad edit never reaches content/ at all.
    """
    path = content_dir / "faq.yaml"
    if not path.exists():
        return [FileError(path, "faq.yaml missing")]
    try:
        data = _load_yaml(path)
        validator = _validator_for("faq", schema_path)
        schema_errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
        if schema_errors:
            joined = "; ".join(
                f"{'.'.join(str(p) for p in e.path) or '<root>'}: {e.message}"
                for e in schema_errors
            )
            return [FileError(path, joined)]
    except Exception as e:  # malformed YAML
        return [FileError(path, str(e))]

    ids = [entry["id"] for entry in data["faqs"]]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        return [FileError(path, f"duplicate FAQ id(s): {dupes}")]

    errors: list[FileError] = []
    for entry in data["faqs"]:
        for field in ("question", "answer"):
            for lang, text in entry[field].items():
                if "</script" in text.lower():
                    errors.append(
                        FileError(
                            path,
                            f"{entry['id']}: {field}.{lang} contains '</script' - it would "
                            "break out of the FAQPage JSON-LD script tag",
                        )
                    )
    return errors


def date_warnings(content_dir: Path, *, today: date | None = None) -> list[FileError]:
    """Advisory (non-failing) warnings for implausible period years.

    Flags any year > today.year + 5 (likely a typo) or < 2014 (predates this CV's
    earliest real activity). `today` is injectable for deterministic tests.
    """
    today = today or date.today()
    ceiling = today.year + 5
    warnings: list[FileError] = []
    for path, period in _iter_periods(content_dir):
        for ym in (period.get("start"), period.get("end")):
            # Skip null/absent and any non-'YYYY-MM' value, so this stays safe to
            # call in isolation (schema guarantees the format in the main pipeline).
            if not (isinstance(ym, str) and ym[:4].isdigit()):
                continue
            year = int(ym[:4])
            if year > ceiling:
                warnings.append(FileError(path, f"implausible future date {ym!r} (> {ceiling})"))
            elif year < 2014:
                warnings.append(FileError(path, f"implausibly early date {ym!r} (< 2014)"))
    return warnings


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
                    errors.append(
                        FileError(
                            selected_path,
                            f"references unknown project id(s): {unknown}",
                        )
                    )
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
        errors.append(
            FileError(
                project_dir / f"{missing_id}.de.yaml",
                "missing DE counterpart for EN project file",
            )
        )
    for missing_id in de_ids - en_ids:
        errors.append(
            FileError(
                project_dir / f"{missing_id}.en.yaml",
                "missing EN counterpart for DE project file",
            )
        )

    errors.extend(_validate_profile_variant_parity(content_dir))
    errors.extend(_validate_headline_variant_completeness(content_dir))
    errors.extend(_validate_publications(content_dir))
    errors.extend(_validate_periods(content_dir))
    errors.extend(validate_faq(content_dir, schema_path.parent / "faq.schema.json"))
    return errors


def main() -> int:
    repo_root = Path(__file__).parent.parent
    content_dir = repo_root / "content"
    schema_path = repo_root / "schema" / "cv.schema.json"

    if not content_dir.exists():
        print(f"ERROR: no content/ directory at {content_dir}", file=sys.stderr)
        return 2

    errors = validate_tree(content_dir, schema_path)

    master_cv_dir = Path(os.environ.get("MASTER_CV_DIR", repo_root / "master-cv"))
    master_cv_schema = repo_root / "schema" / "master-cv.schema.json"
    errors.extend(validate_master_cv(master_cv_dir, master_cv_schema))

    # faq.yaml is validated inside validate_tree() now (also gates agent edits
    # via scripts.agent_core, which calls validate_tree exclusively) - do not
    # call validate_faq() again here, or a broken faq.yaml would be reported twice.

    for warn in date_warnings(content_dir):
        print(f"WARN: {warn}", file=sys.stderr)

    if errors:
        print(f"FAIL: {len(errors)} validation error(s)", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    print("OK: all content files validate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
