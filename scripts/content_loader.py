"""Load CV content from YAML tree + optional private overlay."""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from scripts.bib_loader import load_publications


yaml = YAML(typ="safe")


def deep_merge(base: dict, overlay: dict) -> dict:
    """Recursive dict merge — overlay wins on conflict, nested dicts merged."""
    result = copy.deepcopy(base)
    for key, value in overlay.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return yaml.load(f)


def _load_projects(projects_dir: Path, lang: str = "en") -> dict[str, dict]:
    out: dict[str, dict] = {}
    for path in sorted(projects_dir.glob(f"*.{lang}.yaml")):
        proj = _load_yaml(path)
        if "id" not in proj:
            raise ValueError(f"{path}: missing required 'id' field")
        out[proj["id"]] = proj
    return out


def load_content(
    content_dir: Path,
    *,
    private_path: Path | None = None,
    lang: str = "en",
) -> dict[str, Any]:
    """Load full content tree.

    Returns a dict with keys: personal, profile, skills, education, experience,
    projects (dict keyed by id), languages, volunteer, publications (list of records).

    If private_path is provided and the file exists, its contents are merged into
    content["personal"].
    """
    personal = _load_yaml(content_dir / "personal.yaml")
    if private_path is not None and private_path.exists():
        private = _load_yaml(private_path)
        personal = deep_merge(personal, private)

    content = {
        "personal": personal,
        "profile": _load_yaml(content_dir / f"profile.{lang}.yaml"),
        "skills": _load_yaml(content_dir / "skills.yaml"),
        "education": _load_yaml(content_dir / "education.yaml"),
        "experience": _load_yaml(content_dir / "experience.yaml"),
        "projects": _load_projects(content_dir / "projects", lang=lang),
        "languages": _load_yaml(content_dir / "languages.yaml"),
        "volunteer": _load_yaml(content_dir / "volunteer.yaml"),
        "publications": load_publications(content_dir / "publications.bib"),
    }
    return content
