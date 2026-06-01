"""Render an llms.txt site map (https://llmstxt.org) — a concise, LLM-friendly index
derived from the same YAML + bib as every other renderer (single source of truth).

A cheap discoverability aid (honoured by Anthropic/Perplexity), NOT a replacement
for the JSON-LD entity graph.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from scripts.bib_loader import Publication, load_publications
from scripts.config import PAGES_BASE_URL, RELEASES_BASE_URL
from scripts.content_loader import load_content
from scripts.langstring import resolve_langstrings

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = REPO_ROOT / "content"

_LINK_LABELS = {
    "github": "GitHub",
    "linkedin": "LinkedIn",
    "researchgate": "ResearchGate",
    "website": "Website",
    "orcid": "ORCID",
}


def _projects_section(content: dict) -> str:
    lines = ["## Selected Projects"]
    for p in content["selected_projects"]:
        lines.append(f"- [{p['title']}]({PAGES_BASE_URL}/projects/{p['id']}/): {p['summary']}")
    return "\n".join(lines)


def _publications_section(pubs: list[Publication]) -> str:
    lines = ["## Publications"]
    for p in pubs:
        suffix = f": {p.venue}, {p.year}" if p.venue else f": {p.year}"
        if p.doi:
            lines.append(f"- [{p.title}](https://doi.org/{p.doi}){suffix}")
        else:
            lines.append(f"- {p.title}{suffix}")
    return "\n".join(lines)


def _formats_section() -> str:
    return "\n".join([
        "## CV & machine-readable formats",
        f"- [CV (PDF, EN)]({RELEASES_BASE_URL}/cv-en.pdf)",
        f"- [CV (PDF, DE)]({RELEASES_BASE_URL}/cv-de.pdf)",
        f"- [JSON Resume]({RELEASES_BASE_URL}/resume.json)",
        f"- [JSON-LD (schema.org)]({PAGES_BASE_URL}/person.jsonld)",
        f"- [Plain text (EN)]({RELEASES_BASE_URL}/cv-en.txt)",
    ])


def _links_section(personal: dict) -> str:
    lines = ["## Links"]
    links = personal.get("links") or {}
    for key, label in _LINK_LABELS.items():
        if url := links.get(key):
            lines.append(f"- [{label}]({url})")
    return "\n".join(lines)


def render() -> str:
    content = resolve_langstrings(load_content(CONTENT_DIR, lang="en"), lang="en")
    pubs = load_publications(CONTENT_DIR / "publications.bib")
    personal = content["personal"]
    profile = content["profile"]
    name = f"{personal['name']['given']} {personal['name']['family']}"
    blocks = [
        f"# {name} — {personal['headline']}",
        f"> {profile['tagline']}",
        profile["paragraphs"][0],
        _projects_section(content),
        _publications_section(pubs),
        _formats_section(),
        _links_section(personal),
    ]
    return "\n\n".join(blocks) + "\n"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=REPO_ROOT / "dist" / "llms.txt")
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
