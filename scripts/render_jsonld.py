"""Render the CV as a schema.org @graph (JSON-LD).

The output is a top-level ``@graph`` of ``@id``-linked entities (Person + works),
optimized for **AI/LLM entity resolution and knowledge-graph ingestion** — NOT for
SEO rich results (Google surfaces no Person rich result and dropped EstimatedSalary
in June 2025). The Person ``@id`` is the ORCID URI; authored works link back to it
via ``author`` / ``creator: {"@id": <orcid>}``.
"""
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
    """Educational organizations, deduped by name (order-preserving)."""
    seen: set[str] = set()
    out: list[dict] = []
    for e in content["education"]:
        inst = e["institution"]
        if inst not in seen:
            seen.add(inst)
            out.append({"@type": "EducationalOrganization", "name": inst})
    return out


def _knows_about(content: dict) -> list[str]:
    """Curated, disambiguated topics from content (single source of truth)."""
    return list(content["personal"].get("knowsAbout", []))


def _has_occupation(content: dict) -> list[dict]:
    """One Occupation per facet of the (resolved) headline, split on '·'."""
    headline = content["personal"]["headline"]
    return [
        {"@type": "Occupation", "name": part.strip()}
        for part in headline.split("·")
        if part.strip()
    ]


def _works_for(content: dict) -> dict | None:
    """Current employer = first experience entry whose period.end is null/absent.

    Returns None today (all roles have dated ends) — so worksFor is omitted — but
    auto-detects a current role if one is ever added, keeping the renderer correct.
    """
    for exp in content["experience"]:
        if exp["period"].get("end") in (None, "present"):
            return {"@type": "Organization", "name": exp["org"]["name"]}
    return None


def _publications(pubs: list[Publication], person_id: str, author_prefix: str) -> list[dict]:
    out = []
    for p in pubs:
        doi_url = f"https://doi.org/{p.doi}" if p.doi else None
        item: dict = {
            "@type": "ScholarlyArticle",
            # DOI URL is the canonical persistent ID; fall back to the stable bib key
            # (NOT an enumeration index, which shifts when the bib is reordered).
            "@id": doi_url or f"{PAGES_BASE_URL}/#publication-{p.key}",
            "name": p.title,
            "datePublished": str(p.year),
            "author": [
                {"@id": person_id} if a.startswith(author_prefix) else {"@type": "Person", "name": a}
                for a in p.authors
            ],
        }
        if p.venue:
            item["isPartOf"] = {"@type": "Periodical", "name": p.venue}
        if p.doi:
            item["sameAs"] = [doi_url]
            item["identifier"] = {"@type": "PropertyValue", "propertyID": "DOI", "value": p.doi}
        out.append(item)
    return out


def _projects(content: dict, person_id: str) -> list[dict]:
    """One CreativeWork per project; @id == its eventual /projects/{id}/ page URL."""
    out = []
    for pid, proj in content["projects"].items():
        url = f"{PAGES_BASE_URL}/projects/{pid}/"
        out.append({
            "@type": "CreativeWork",
            "@id": url,
            "name": proj["title"],
            "url": url,
            "description": proj["summary"],
            "dateCreated": proj["period"]["start"],
            "keywords": list(proj.get("technologies", [])),
            "creator": {"@id": person_id},
        })
    return out


def _person(content: dict) -> dict:
    """The Person node — @id is the ORCID URI (canonical entity identifier)."""
    personal = content["personal"]
    profile = content["profile"]
    name = f"{personal['name']['given']} {personal['name']['family']}"
    orcid = personal["links"].get("orcid")
    person: dict = {
        "@type": "Person",
        "@id": orcid or f"{SITE_URL}#person",
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
    }
    # Only claim an ORCID identifier when a real ORCID is present (don't label the
    # site-URL @id fallback as an ORCID value).
    if orcid:
        person["identifier"] = {"@type": "PropertyValue", "propertyID": "ORCID", "value": orcid}
    person["sameAs"] = _same_as(personal)
    person["alumniOf"] = _alumni_of(content)
    person["knowsAbout"] = _knows_about(content)
    person["hasOccupation"] = _has_occupation(content)
    if (works_for := _works_for(content)) is not None:
        person["worksFor"] = works_for
    if content["awards"]:
        person["award"] = [a["title"] for a in content["awards"]]
    return person


def to_jsonld(content: dict, pubs: list[Publication]) -> dict:
    """Compose the schema.org @graph (see module docstring for the entity-resolution rationale)."""
    person = _person(content)
    person_id = person["@id"]
    # Match the author entry that is the CV owner (his own bib) by "Family, G" prefix,
    # derived from content rather than hardcoded.
    pname = content["personal"]["name"]
    author_prefix = f"{pname['family']}, {pname['given'][0]}"
    return {
        "@context": "https://schema.org",
        "@graph": [
            person,
            *_publications(pubs, person_id, author_prefix),
            *_projects(content, person_id),
        ],
    }


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
