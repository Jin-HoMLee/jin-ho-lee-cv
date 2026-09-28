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


def _english(value: str | dict[str, str]) -> str:
    return value["en"] if isinstance(value, dict) else value


def project_pdf_content(content: dict[str, Any], *, target: str, lang: str) -> dict[str, Any]:
    """Return a concise application-PDF view without mutating ``content``."""
    result = copy.deepcopy(content)

    # The target-specific tagline is the compact positioning block. Detailed
    # evidence remains visible in Experience, Projects, and Publications.
    result["profile"]["paragraphs"] = []

    # Experience ordering is resolved in content_loader for every renderer; the
    # PDF shares that target-ordered, identical-content experience as-is.

    for education in result["education"]:
        education.pop("thesis", None)

    result["languages"] = [
        language for language in result["languages"] if language["proficiency"] != "passive"
    ]

    # Keep the concise, role-based volunteer categories in every target. The
    # Environment list stays to its lead entry; Community remains web-only.
    volunteer_keep = {"Environment", "Sports", "Music"}
    result["volunteer"] = {
        "categories": [
            {
                "name": category["name"],
                "entries": (
                    category["entries"][:1]
                    if _english(category["name"]) == "Environment"
                    else category["entries"]
                ),
            }
            for category in result["volunteer"]["categories"]
            if _english(category["name"]) in volunteer_keep
        ]
    }

    allowed_awards = _AWARD_TITLES[target]
    result["awards"] = [
        award for award in result["awards"] if _english(award["title"]) in allowed_awards
    ]
    if target == "bridge":
        # The scholarship remains visible; its immunotherapy-specific internship
        # note belongs in the focused biological view rather than the General CV.
        for award in result["awards"]:
            if _english(award["title"]) == "DAAD PROMOS Scholarship":
                award.pop("note", None)

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
