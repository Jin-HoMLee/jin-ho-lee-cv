"""Render the CV as schema.org Person JSON-LD."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.bib_loader import Publication, load_publications
from scripts.config import PAGES_BASE_URL
from scripts.content_loader import load_content
from scripts.langstring import resolve_langstrings


REPO_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = REPO_ROOT / "content"
SITE_URL = f"{PAGES_BASE_URL}/"
PHOTO_URL = f"{PAGES_BASE_URL}/photo.jpg"


def _same_as(personal: dict) -> list[str]:
    return [v for v in (personal.get("links") or {}).values() if v]


def _alumni_of(content: dict) -> list[dict]:
    return [
        {"@type": "EducationalOrganization", "name": e["institution"]}
        for e in content["education"]
    ]


def _knows_about(content: dict) -> list[str]:
    out: list[str] = []
    for cat in content["skills"]["categories"]:
        for grp in cat["groups"]:
            out.extend(grp["items"])
    return out


def _works_for(content: dict) -> dict | None:
    """First experience entry whose period.end is null is the current employer."""
    for exp in content["experience"]:
        if exp["period"].get("end") in (None, "present"):
            return {"@type": "Organization", "name": exp["org"]["name"]}
    return None


def _publications(pubs: list[Publication]) -> list[dict]:
    out = []
    for p in pubs:
        item: dict = {
            "@type": "ScholarlyArticle",
            "name": p.title,
            "datePublished": str(p.year),
            "author": [{"@type": "Person", "name": a} for a in p.authors],
        }
        if p.venue:
            item["isPartOf"] = {"@type": "Periodical", "name": p.venue}
        out.append(item)
    return out


def _projects(content: dict) -> list[dict]:
    """One CreativeWork per project, URL points at the eventual /projects/{id}/ page."""
    out = []
    for pid, proj in content["projects"].items():
        item: dict = {
            "@type": "CreativeWork",
            "name": proj["title"],
            "url": f"{PAGES_BASE_URL}/projects/{pid}/",
            "description": proj["summary"],
            "dateCreated": proj["period"]["start"],
            "keywords": list(proj.get("technologies", [])),
        }
        out.append(item)
    return out


def to_jsonld(content: dict, pubs: list[Publication]) -> dict:
    """Compose the schema.org Person JSON-LD document."""
    personal = content["personal"]
    profile = content["profile"]
    name = f"{personal['name']['given']} {personal['name']['family']}"

    doc: dict = {
        "@context": "https://schema.org",
        "@type": "Person",
        "name": name,
        "url": SITE_URL,
        "image": PHOTO_URL,
        "email": f"mailto:{personal['email']}",
        "jobTitle": personal["headline"],
        "description": profile["paragraphs"][0],
        "address": {
            "@type": "PostalAddress",
            "addressLocality": personal["location"]["city"],
            "addressCountry": personal["location"]["country"],
        },
        "sameAs": _same_as(personal),
        "alumniOf": _alumni_of(content),
        "knowsAbout": _knows_about(content),
    }
    if (works_for := _works_for(content)) is not None:
        doc["worksFor"] = works_for

    doc["@graph"] = _publications(pubs) + _projects(content)
    return doc


def _print_wrote(output: Path) -> None:
    """Print 'wrote <path>' using a repo-relative path when possible, absolute otherwise."""
    try:
        rel = output.relative_to(REPO_ROOT)
    except ValueError:
        rel = output
    print(f"wrote {rel}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "dist" / "person.jsonld",
        help="Output path (default: dist/person.jsonld)",
    )
    args = parser.parse_args(argv)

    content = resolve_langstrings(load_content(CONTENT_DIR, lang="en"), lang="en")
    pubs = load_publications(CONTENT_DIR / "publications.bib")
    doc = to_jsonld(content, pubs)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _print_wrote(args.output)


if __name__ == "__main__":
    main()
