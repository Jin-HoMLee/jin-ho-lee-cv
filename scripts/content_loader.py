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


TARGETS = ("bridge", "comp-bio", "ds-ml")


def _resolve_personal_target(personal: dict, target: str) -> dict:
    """Apply the personal positioning variant for `target`; strip 'variants'.

    Bridge — or any target without an entry — returns the base personal with the
    'variants' key removed. The entire variant dict is deep-merged over the base
    (the schema constrains a personal variant to only `headline`), so a variant
    headline {en,de} map replaces the base headline.
    """
    result = copy.deepcopy(personal)
    variants = result.pop("variants", {})
    if target != "bridge" and target in variants:
        result = deep_merge(result, variants[target])
    return result


def _resolve_profile_target(profile: dict, target: str) -> dict:
    """Apply the profile positioning variant for `target`; strip 'variants'.

    A variant may override `tagline`, `lead_paragraph`, and/or `second_paragraph`.
    `lead_paragraph` replaces paragraphs[0] and `second_paragraph` replaces
    paragraphs[1]; any paragraph not overridden is inherited from bridge. The
    paragraph overrides are guarded by length so a profile with fewer paragraphs
    than the override targets is left untouched rather than raising.
    """
    result = copy.deepcopy(profile)
    variants = result.pop("variants", {})
    override = variants.get(target, {}) if target != "bridge" else {}
    if "tagline" in override:
        result["tagline"] = override["tagline"]
    paragraphs = list(result["paragraphs"])
    if "lead_paragraph" in override and len(paragraphs) >= 1:
        paragraphs[0] = override["lead_paragraph"]
    if "second_paragraph" in override and len(paragraphs) >= 2:
        paragraphs[1] = override["second_paragraph"]
    result["paragraphs"] = paragraphs
    return result


def _resolve_skills_target(
    skills: dict, target: str, *, web_projection: bool = False
) -> dict:
    """Resolve a target Skills view and strip projection instructions.

    A category variant can omit the category, omit selected groups, or replace a
    group's item list with a concise or expanded audience-specific list. The
    ``bridge`` variant is a web-only concise projection;
    the canonical bridge tree is otherwise left intact. Group labels are matched
    by their English label; validation rejects typos and duplicate base labels before
    renderers consume this tree.
    """
    result = copy.deepcopy(skills)
    categories = []
    for category in result["categories"]:
        variants = category.pop("variants", {})
        apply_variant = web_projection or target != "bridge"
        override = variants.get(target, {}) if apply_variant else {}
        if override.get("omit", False):
            continue

        omit_groups = set(override.get("omit_groups", []))
        replacement_items = override.get("group_items", {})
        groups = []
        for group in category["groups"]:
            label_en = group["label"]["en"]
            if label_en in omit_groups:
                continue
            if label_en in replacement_items:
                group = {**group, "items": copy.deepcopy(replacement_items[label_en])}
            groups.append(group)
        if groups:
            categories.append({**category, "groups": groups})

    result["categories"] = categories
    return result


def _select_project_ids(selected_map: dict, target: str) -> list[str]:
    """Return the project-id order for `target`, falling back to the bridge order."""
    return selected_map.get(target, selected_map["bridge"])


def _load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return yaml.load(f)


def _load_projects(projects_dir: Path, lang: str = "en") -> dict[str, dict]:
    out: dict[str, dict] = {}
    for path in sorted(projects_dir.glob(f"*.{lang}.yaml")):
        proj = _load_yaml(path)
        if "id" not in proj:
            raise ValueError(f"{path}: missing required 'id' field")
        expected_id = path.name.split(".")[0]
        if proj["id"] != expected_id:
            raise ValueError(
                f"{path}: id field {proj['id']!r} does not match filename {expected_id!r}"
            )
        if proj["id"] in out:
            raise ValueError(f"{path}: duplicate project id {proj['id']!r}")
        out[proj["id"]] = proj
    return out


def load_content(
    content_dir: Path,
    *,
    private_path: Path | None = None,
    lang: str = "en",
    target: str = "bridge",
    web_projection: bool = False,
) -> dict[str, Any]:
    """Load full content tree.

    Returns a dict with keys: personal, profile, skills, education, experience,
    projects (dict keyed by id), selected_projects (list), languages, volunteer,
    awards (list of records), publications (list of records), labels, faq.

    If private_path is provided and the file exists, its contents are merged into
    content["personal"]. When web_projection is true, the Skills tree uses the
    concise web bridge or target-specific projection.
    """
    if target not in TARGETS:
        raise ValueError(f"unknown target {target!r}; expected one of {TARGETS}")

    personal = _load_yaml(content_dir / "personal.yaml")
    if private_path is not None and private_path.exists():
        private = _load_yaml(private_path)
        personal = deep_merge(personal, private)
    personal = _resolve_personal_target(personal, target)

    projects = _load_projects(content_dir / "projects", lang=lang)
    selected_map = _load_yaml(content_dir / "selected_projects.yaml")
    selected_ids = _select_project_ids(selected_map, target)
    unknown = [pid for pid in selected_ids if pid not in projects]
    if unknown:
        raise ValueError(f"selected_projects.yaml references unknown project id(s): {unknown}")
    selected_projects = [projects[pid] for pid in selected_ids]

    content = {
        "personal": personal,
        "profile": _resolve_profile_target(
            _load_yaml(content_dir / f"profile.{lang}.yaml"), target
        ),
        "skills": _resolve_skills_target(
            _load_yaml(content_dir / "skills.yaml"),
            target,
            web_projection=web_projection,
        ),
        "education": _load_yaml(content_dir / "education.yaml"),
        "experience": _load_yaml(content_dir / "experience.yaml"),
        "projects": projects,
        "selected_projects": selected_projects,
        "languages": _load_yaml(content_dir / "languages.yaml"),
        "volunteer": _load_yaml(content_dir / "volunteer.yaml"),
        "awards": _load_yaml(content_dir / "awards.yaml"),
        "publications": load_publications(content_dir / "publications.bib"),
        "labels": _load_yaml(content_dir / "labels.yaml"),
        "faq": _load_yaml(content_dir / "faq.yaml"),
    }
    return content
