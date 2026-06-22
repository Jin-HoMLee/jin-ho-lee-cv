"""Assemble the CV (+ optional master-cv overlay) into one Markdown union.

The single DRY union helper shared by render_chat_context (the digital twin) and
render_master_cv (the dist/master-cv.md lookup artifact). When master_cv is None or
empty, the output is exactly the CV-only blob — the graceful-absence guarantee that
keeps the twin's committed snapshot byte-identical without the overlay.
"""

from __future__ import annotations

from scripts.bib_loader import Publication
from scripts.master_cv_loader import MasterCV


def _identity(content: dict) -> str:
    personal = content["personal"]
    profile = content["profile"]
    name = f"{personal['name']['given']} {personal['name']['family']}"
    return f"# {name} — {personal['headline']}\n\n> {profile['tagline']}"


def _profile(content: dict) -> str:
    return "\n\n".join(["## Profile", *content["profile"]["paragraphs"]])


def _skills(content: dict) -> str:
    lines = ["## Skills"]
    for category in content["skills"]["categories"]:
        for group in category["groups"]:
            lines.append(f"- **{group['label']}**: {', '.join(group['items'])}")
    return "\n".join(lines)


def _experience(content: dict) -> str:
    lines = ["## Experience"]
    for job in content["experience"]:
        role = job["role"]
        org = job["org"]["name"]
        period = job["period"]
        start = period["start"]
        end = period.get("end") or "present"
        lines.append(f"### {role} — {org} ({start}–{end})")
        for bullet in job["bullets"]:
            lines.append(f"- {bullet['en']}")
    return "\n".join(lines)


def _education(content: dict) -> str:
    lines = ["## Education"]
    for ed in content["education"]:
        lines.append(f"- {ed['degree']}, {ed['institution']} ({ed['year']})")
    return "\n".join(lines)


def _projects(content: dict) -> str:
    lines = ["## Selected Projects"]
    for p in content["selected_projects"]:
        lines.append(f"### {p['title']}")
        lines.append(p["summary"])
        for detail in p["contributions"]:
            lines.append(f"- {detail}")
    return "\n".join(lines)


def _publications(pubs: list[Publication]) -> str:
    lines = ["## Publications"]
    for p in pubs:
        venue = f", {p.venue}" if p.venue else ""
        year = f" ({p.year})" if p.year else ""
        lines.append(f"- {p.title}{venue}{year}")
    return "\n".join(lines)


# ---- master-cv overlay sections (appended only when present) ---------------


def _full_timeline(master_cv: MasterCV) -> str:
    lines = ["## Full Timeline (master record)"]
    for e in master_cv.timeline:
        title = e.get("title") or e["id"]
        org = f" — {e['org']}" if e.get("org") else ""
        start, end = e.get("start"), e.get("end")
        dates = f" ({start or '?'}–{end or 'present'})" if (start or end) else ""
        lines.append(f"### {title}{org}{dates}")
        loc = f" · {e['location']}" if e.get("location") else ""
        lines.append(f"_{e['type']}{loc}_")
        if e.get("summary"):
            lines.append(e["summary"])
        if e.get("tags"):
            lines.append(f"Tags: {', '.join(e['tags'])}")
    return "\n".join(lines)


def _full_inventory(master_cv: MasterCV) -> str:
    lines = ["## Full Skill & Domain Inventory (master record)"]
    for key, items in master_cv.inventory.items():
        label = key.replace("_", " ").title()
        lines.append(f"- **{label}**: {', '.join(items)}")
    return "\n".join(lines)


def _narrative(master_cv: MasterCV) -> str:
    blocks = ["## Personal Narrative (master record)"]
    for stem in sorted(master_cv.narrative):
        blocks.append(master_cv.narrative[stem].rstrip())
    return "\n\n".join(blocks)


def full_profile(content: dict, pubs: list[Publication], master_cv: MasterCV | None = None) -> str:
    """Full CV (+ master-cv overlay when present) as one Markdown blob, no trailing newline."""
    blocks = [
        _identity(content),
        _profile(content),
        _skills(content),
        _experience(content),
        _education(content),
        _projects(content),
        _publications(pubs),
    ]
    if master_cv is not None:
        if master_cv.timeline:
            blocks.append(_full_timeline(master_cv))
        if master_cv.inventory:
            blocks.append(_full_inventory(master_cv))
        if master_cv.narrative:
            blocks.append(_narrative(master_cv))
    return "\n\n".join(blocks)
