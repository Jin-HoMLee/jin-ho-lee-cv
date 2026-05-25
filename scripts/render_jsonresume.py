"""Render the CV to a JSON Resume document (https://jsonresume.org/schema/)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.bib_loader import Publication, load_publications
from scripts.content_loader import load_content
from scripts.langstring import resolve_langstrings


REPO_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = REPO_ROOT / "content"
SITE_URL = "https://jin-homlee.github.io/jin-ho-lee-cv/"


def _pad_start(yyyy_mm: str) -> str:
    """'2024-05' → '2024-05-01' (ISO 8601 calendar date)."""
    return f"{yyyy_mm}-01"


def _pad_end(yyyy_mm: str | None) -> str | None:
    """'2024-05' → '2024-05-28' (28 is safe in every month). None passes through."""
    return f"{yyyy_mm}-28" if yyyy_mm else None


def _network_for(key: str) -> str:
    return {
        "linkedin":     "LinkedIn",
        "github":       "GitHub",
        "researchgate": "ResearchGate",
        "orcid":        "ORCID",
    }.get(key, key.title())


def _basics(content: dict) -> dict:
    personal = content["personal"]
    profile = content["profile"]
    name = f"{personal['name']['given']} {personal['name']['family']}"
    profiles = [
        {"network": _network_for(k), "url": v}
        for k, v in (personal.get("links") or {}).items()
        if v
    ]
    return {
        "name": name,
        "label": personal["headline"],
        "email": personal["email"],
        "url": SITE_URL,
        "summary": "\n\n".join(profile["paragraphs"]),
        "location": {
            "city": personal["location"]["city"],
            "countryCode": personal["location"]["country"],
        },
        "profiles": profiles,
    }


def _work(content: dict) -> list[dict]:
    out = []
    for exp in content["experience"]:
        out.append({
            "name": exp["org"]["name"],
            "position": exp["role"],
            "startDate": _pad_start(exp["period"]["start"]),
            **({"endDate": _pad_end(exp["period"]["end"])} if exp["period"].get("end") else {}),
            "summary": " ".join(b["en"] for b in exp["bullets"]) if exp.get("bullets") else "",
            "highlights": [b["en"] for b in exp.get("bullets", [])],
        })
    return out


def _education(content: dict) -> list[dict]:
    out = []
    for edu in content["education"]:
        year = str(edu["year"])
        out.append({
            "institution": edu["institution"],
            "studyType": edu["degree"],
            "area": "",
            "startDate": f"{year}-01-01",
            "endDate": f"{year}-12-31",
        })
    return out


def _skills(content: dict) -> list[dict]:
    out = []
    for cat in content["skills"]["categories"]:
        for grp in cat["groups"]:
            out.append({
                "name": cat["name"],
                "level": grp["label"],
                "keywords": list(grp["items"]),
            })
    return out


def _languages(content: dict) -> list[dict]:
    return [
        {"language": lang["name"], "fluency": lang["proficiency"]}
        for lang in content["languages"]
    ]


def _volunteer(content: dict) -> list[dict]:
    out = []
    for cat in content["volunteer"]["categories"]:
        for entry in cat["entries"]:
            out.append({
                "organization": entry,
                "position": cat["name"],
            })
    return out


def _projects(content: dict) -> list[dict]:
    out = []
    for pid, proj in content["projects"].items():
        out.append({
            "name": proj["title"],
            "description": proj["summary"],
            "highlights": list(proj.get("contributions", [])),
            "keywords": list(proj.get("technologies", [])),
            "startDate": _pad_start(proj["period"]["start"]),
            "endDate": _pad_end(proj["period"]["end"]) or _pad_start(proj["period"]["start"]),
            "roles": [proj["role"]],
        })
    return out


def _publications(pubs: list[Publication]) -> list[dict]:
    return [
        {
            "name": p.title,
            "publisher": p.venue or "",
            "releaseDate": f"{p.year}-01-01",
            "summary": ", ".join(p.authors),
        }
        for p in pubs
    ]


def to_jsonresume(content: dict, pubs: list[Publication]) -> dict:
    """Compose the full JSON Resume document."""
    return {
        "$schema": "https://jsonresume.org/schema/0.0.0/resume.json",
        "basics": _basics(content),
        "work": _work(content),
        "education": _education(content),
        "skills": _skills(content),
        "languages": _languages(content),
        "volunteer": _volunteer(content),
        "projects": _projects(content),
        "publications": _publications(pubs),
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "dist" / "resume.json",
        help="Output path (default: dist/resume.json)",
    )
    args = parser.parse_args(argv)

    content = resolve_langstrings(load_content(CONTENT_DIR, lang="en"), lang="en")
    pubs = load_publications(CONTENT_DIR / "publications.bib")
    doc = to_jsonresume(content, pubs)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {args.output.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
