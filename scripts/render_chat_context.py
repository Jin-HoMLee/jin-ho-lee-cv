"""Compile the whole public CV into one Markdown context blob for the digital-twin chat.

A richer sibling of render_llms.py: where llms.txt is a slim site map, this is the full
profile + experience + skills + education + project deep-dives + publications that the
chat Worker injects as a system instruction each request. PII-safe by construction — reads only
content/ (never content.private/), mirroring agent_core.read_cv.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from scripts.bib_loader import Publication, load_publications
from scripts.content_loader import load_content
from scripts.langstring import resolve_langstrings

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = REPO_ROOT / "content"


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


def render() -> str:
    content = resolve_langstrings(load_content(CONTENT_DIR, lang="en"), lang="en")
    pubs = load_publications(CONTENT_DIR / "publications.bib")
    blocks = [
        _identity(content),
        _profile(content),
        _skills(content),
        _experience(content),
        _education(content),
        _projects(content),
        _publications(pubs),
    ]
    return "\n\n".join(blocks) + "\n"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=REPO_ROOT / "dist" / "chat-context.md")
    args = parser.parse_args(argv)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(), encoding="utf-8")
    try:
        rel = args.output.relative_to(REPO_ROOT)
    except ValueError:
        rel = args.output
    print(f"wrote {rel}")


if __name__ == "__main__":
    main()
