"""Render the CV as section-headed ATS-friendly plain text."""
from __future__ import annotations

import argparse
import textwrap
from pathlib import Path

from scripts.bib_loader import Publication, load_publications
from scripts.content_loader import load_content
from scripts.langstring import resolve_langstrings


from scripts.config import PAGES_BASE_URL

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = REPO_ROOT / "content"
SITE_URL = f"{PAGES_BASE_URL}/"
DIVIDER = "=" * 80
SECTION_LABELS = {
    "profile":           {"en": "PROFILE",           "de": "PROFIL"},
    "experience":        {"en": "EXPERIENCE",        "de": "BERUFSERFAHRUNG"},
    "selected_projects": {"en": "SELECTED PROJECTS", "de": "AUSGEWÄHLTE PROJEKTE"},
    "education":         {"en": "EDUCATION",         "de": "AUSBILDUNG"},
    "awards":            {"en": "AWARDS",            "de": "AUSZEICHNUNGEN"},
    "skills":            {"en": "SKILLS",            "de": "KENNTNISSE"},
    "languages":         {"en": "LANGUAGES",         "de": "SPRACHEN"},
    "volunteer":         {"en": "VOLUNTEER",         "de": "EHRENAMTLICH"},
    "publications":      {"en": "PUBLICATIONS",      "de": "PUBLIKATIONEN"},
}
PRESENT = {"en": "present", "de": "heute"}
PERIOD_CONNECTOR = {"en": "to", "de": "bis"}


def _wrap(paragraph: str, width: int = 80) -> str:
    """Wrap a paragraph at `width` columns. Leaves lines with URLs un-wrapped."""
    if "http" in paragraph:
        return paragraph
    return "\n".join(textwrap.wrap(paragraph, width=width)) or paragraph


def _section(name: str, body: str) -> str:
    return f"{DIVIDER}\n{name}\n{DIVIDER}\n{body}".rstrip()


def _header(content: dict) -> str:
    personal = content["personal"]
    name = f"{personal['name']['given']} {personal['name']['family']}"
    location = f"{personal['location']['city']}, {personal['location']['country']}"
    links = [personal["email"], SITE_URL]
    links.extend(v for v in (personal.get("links") or {}).values() if v)
    return f"{name.upper()}\n{personal['headline']} - {location}\n" + " | ".join(links)


def _profile(content: dict) -> str:
    return "\n\n".join(_wrap(p) for p in content["profile"]["paragraphs"])


def _experience(content: dict, lang: str) -> str:
    out: list[str] = []
    for exp in content["experience"]:
        period_end = exp["period"].get("end") or PRESENT[lang]
        title_line = f"{exp['role']} - {exp['org']['name']}".strip()
        period_line = f"{exp['period']['start']} {PERIOD_CONNECTOR[lang]} {period_end}"
        block = [f"{title_line}    ({period_line})"]
        for b in exp.get("bullets", []):
            block.append(f"  - {b[lang]}")
        out.append("\n".join(block))
    return "\n\n".join(out)


def _selected_projects(content: dict, lang: str) -> str:
    out: list[str] = []
    outcome_label = {"en": "Outcome", "de": "Ergebnis"}[lang]
    for proj in content["selected_projects"]:
        period_end = proj["period"].get("end") or PRESENT[lang]
        period = f"{proj['period']['start']} {PERIOD_CONNECTOR[lang]} {period_end}"
        block = [
            f"{proj['title']}    ({period})",
            f"  {proj['role']}",
            "  " + _wrap(proj["summary"], width=78).replace("\n", "\n  "),
            "  " + _wrap(f"{outcome_label}: {proj['outcome']}", width=78).replace("\n", "\n  "),
        ]
        out.append("\n".join(block))
    return "\n\n".join(out)


def _education(content: dict) -> str:
    lines = []
    for e in content["education"]:
        major = f", {e['field']}" if e.get("field") else ""
        lines.append(f"{e['year']}  {e['degree']}{major} - {e['institution']} ({e['location']})")
    return "\n".join(lines)


def _awards(content: dict) -> str:
    lines = []
    for a in content["awards"]:
        lines.append(f"{a['year']}  {a['title']} - {a['issuer']}")
        if a.get("note"):
            lines.append(f"  {a['note']}")
    return "\n".join(lines)


def _skills(content: dict) -> str:
    out: list[str] = []
    for cat in content["skills"]["categories"]:
        out.append(cat["name"])
        for grp in cat["groups"]:
            items = ", ".join(grp["items"])
            out.append(f"  {grp['label']}: {items}")
    return "\n".join(out)


def _languages(content: dict) -> str:
    return "\n".join(f"  {lang['name']}: {lang['proficiency']}" for lang in content["languages"])


def _volunteer(content: dict) -> str:
    out: list[str] = []
    for cat in content["volunteer"]["categories"]:
        out.append(cat["name"])
        for entry in cat["entries"]:
            out.append(f"  - {entry}")
    return "\n".join(out)


def _publications(pubs: list[Publication]) -> str:
    out: list[str] = []
    for p in pubs:
        authors = ", ".join(p.authors)
        venue = f" - {p.venue}" if p.venue else ""
        block = f"{p.year}  {p.title}\n  {authors}{venue}"
        if p.doi:
            block += f"\n  https://doi.org/{p.doi}"
        out.append(block)
    return "\n\n".join(out)


def render(lang: str) -> str:
    """Return the full plain-text CV for the given language."""
    content = resolve_langstrings(load_content(CONTENT_DIR, lang=lang), lang=lang)
    pubs = load_publications(CONTENT_DIR / "publications.bib")
    L = SECTION_LABELS

    sections = [
        _header(content),
        _section(L["profile"][lang],           _profile(content)),
        _section(L["experience"][lang],        _experience(content, lang)),
        _section(L["selected_projects"][lang], _selected_projects(content, lang)),
        _section(L["education"][lang],         _education(content)),
        _section(L["awards"][lang],            _awards(content)),
        _section(L["skills"][lang],            _skills(content)),
        _section(L["languages"][lang],         _languages(content)),
        _section(L["volunteer"][lang],         _volunteer(content)),
        _section(L["publications"][lang],      _publications(pubs)),
    ]
    return "\n\n".join(sections) + "\n"


def _print_wrote(output: Path) -> None:
    """Print 'wrote <path>' using a repo-relative path when possible, absolute otherwise."""
    try:
        rel = output.relative_to(REPO_ROOT)
    except ValueError:
        rel = output
    print(f"wrote {rel}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lang", choices=("en", "de"), required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output path (default: dist/cv-{lang}.txt)",
    )
    args = parser.parse_args(argv)

    output = args.output or REPO_ROOT / "dist" / f"cv-{args.lang}.txt"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render(args.lang), encoding="utf-8")
    _print_wrote(output)


if __name__ == "__main__":
    main()
