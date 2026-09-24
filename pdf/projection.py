"""Concise, target-aware projection for the application PDF renderer.

This module selects from canonical CV facts; it never rewrites claims. Other
renderers continue to receive the complete content tree.
"""

from __future__ import annotations

import copy
from typing import Any

REPRESENTATIVE_PUBLICATION_KEYS = (
    "lee2021superres_dna_repair",
    "hausmann2020_3d_dna_fish",
    "lee2019_combofish",
)

_EXPERIENCE_BULLETS = {
    "bridge": {
        "independent": (0,),
        "cintellic": (0, 1),
        "neuefische": (0, 1),
        "research": (0, 1),
    },
    "comp-bio": {
        "independent": (),
        "cintellic": (0,),
        "neuefische": (0,),
        "research": (0, 1),
    },
    "ds-ml": {
        "independent": (0, 1),
        "cintellic": (0, 1, 2),
        "neuefische": (0, 1),
        "research": (0,),
    },
}

_AWARD_TITLES = {
    "bridge": {
        "Google Cloud Certified - Associate Cloud Engineer",
        "DAAD PROMOS Scholarship",
    },
    "comp-bio": {"DeGBS Poster Award", "DAAD PROMOS Scholarship"},
    "ds-ml": {
        "Google Cloud Certified - Associate Cloud Engineer",
        "“Most Patient-Centric Solution” Award",
    },
}

_SKILL_CATEGORIES = {
    "bridge": {
        "Bioinformatics & ML",
        "AI & Developer Tooling",
        "Biotech Wet-Lab",
        "Data & Engineering",
    },
    "comp-bio": {"Bioinformatics & ML", "Biotech Wet-Lab", "Data & Engineering"},
    "ds-ml": {"AI & Developer Tooling", "Data & Engineering", "Bioinformatics & ML"},
}


def _english(value: str | dict[str, str]) -> str:
    return value["en"] if isinstance(value, dict) else value


def project_pdf_content(content: dict[str, Any], *, target: str, lang: str) -> dict[str, Any]:
    """Return a concise application-PDF view without mutating ``content``."""
    result = copy.deepcopy(content)

    # The target-specific tagline is the compact positioning block. Detailed
    # evidence remains visible in Experience, Projects, and Publications.
    result["profile"]["paragraphs"] = []

    bullet_indices = _EXPERIENCE_BULLETS[target]
    for entry in result["experience"]:
        entry["bullets"] = [
            entry["bullets"][index]
            for index in bullet_indices[entry["id"]]
            if index < len(entry["bullets"])
        ]

    allowed_categories = _SKILL_CATEGORIES[target]
    result["skills"]["categories"] = [
        category
        for category in result["skills"]["categories"]
        if _english(category["name"]) in allowed_categories
    ]

    for education in result["education"]:
        education.pop("thesis", None)

    result["languages"] = [
        language for language in result["languages"] if language["proficiency"] != "passive"
    ]

    environment = next(
        category
        for category in result["volunteer"]["categories"]
        if _english(category["name"]) == "Environment"
    )
    result["volunteer"] = {
        "categories": [{"name": environment["name"], "entries": environment["entries"][:1]}]
    }

    allowed_awards = _AWARD_TITLES[target]
    result["awards"] = [
        award for award in result["awards"] if _english(award["title"]) in allowed_awards
    ]

    all_publications = result["publications"]
    by_key = {publication.key: publication for publication in all_publications}
    missing = [key for key in REPRESENTATIVE_PUBLICATION_KEYS if key not in by_key]
    if missing:
        raise ValueError(f"representative PDF publication key(s) missing: {missing}")
    result["selected_publications"] = [by_key[key] for key in REPRESENTATIVE_PUBLICATION_KEYS]

    website = result["personal"]["links"]["website"].rstrip("/")
    language_prefix = "/de" if lang == "de" else ""
    project_links = {
        project_id: f"{website}{language_prefix}/projects/{project_id}/"
        for project_id in result["projects"]
    }
    result["project_links"] = project_links
    for project in result["selected_projects"]:
        project["web_url"] = project_links[project["id"]]

    return result
