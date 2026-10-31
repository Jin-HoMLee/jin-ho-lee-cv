"""Render the complete bilingual publication-list attachment as a Typst PDF.

The bibliography remains owned by ``content/publications.bib``. This renderer
only prepares a presentation view and writes a self-contained PDF to ``dist/``
(or to an explicitly supplied output path for an application handoff).
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from scripts.content_loader import load_content
from scripts.langstring import resolve_langstrings
from scripts.publications import format_publication_summary

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = REPO_ROOT / "content"

_TYPE_LABELS = {
    "en": {
        "article": "Peer-reviewed articles",
        "book-chapter": "Book chapters",
        "conference": "Conference contributions",
        "book": "Books",
    },
    "de": {
        "article": "Peer-Review-Artikel",
        "book-chapter": "Buchkapitel",
        "conference": "Konferenzbeiträge",
        "book": "Bücher",
    },
}


def _to_jsonable(value: Any) -> Any:
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        data = dataclasses.asdict(value)
        data.pop("raw", None)
        return {key: _to_jsonable(item) for key, item in data.items()}
    if isinstance(value, dict):
        return {key: _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(item) for item in value]
    return value


def prepare_data(content_dir: Path = CONTENT_DIR, *, lang: str = "en") -> dict[str, Any]:
    """Prepare the language-resolved, full-bibliography attachment view."""
    if lang not in ("en", "de"):
        raise ValueError(f"unsupported language {lang!r}; expected en or de")

    raw = load_content(
        content_dir,
        private_path=None,
        lang=lang,
        target="bridge",
        web_projection=True,
    )
    resolved = resolve_langstrings(raw, lang=lang)
    publications = raw["publications"]
    labels = resolved["labels"]["publications"]
    type_labels = _TYPE_LABELS[lang]

    grouped: list[dict[str, Any]] = []
    for category, label_key in (("research", "research_label"), ("applied", "applied_label")):
        category_items = [pub for pub in publications if pub.category == category]
        groups: list[dict[str, Any]] = []
        for pub_type in ("article", "book-chapter", "conference", "book"):
            items = [pub for pub in category_items if pub.type == pub_type]
            if items:
                groups.append(
                    {
                        "label": type_labels[pub_type],
                        "items": [_to_jsonable(item) for item in items],
                    }
                )
        if category_items:
            grouped.append(
                {
                    "label": labels[label_key],
                    "items_count": len(category_items),
                    "groups": groups,
                }
            )

    links = resolved["personal"]["links"]
    link_labels = labels["link_labels"]
    publication_links = []
    for key, label_key in (
        ("orcid", "orcid"),
        ("googlescholar", "google_scholar"),
        ("website", "web_cv"),
    ):
        url = links.get(key)
        if url is not None:
            publication_links.append(
                {
                    "label": link_labels[label_key],
                    "url": url,
                }
            )

    summary = format_publication_summary(labels["summary"], publications)
    return {
        "personal": resolved["personal"],
        "summary": summary,
        "publications": grouped,
        "publication_links": publication_links,
        "labels": {
            "title": "Complete publication list" if lang == "en" else "Vollständige Publikationsliste",
            "provenance": (
                "Generated from the version-controlled bibliography."
                if lang == "en"
                else "Aus der versionierten Bibliografie generiert."
            ),
            "links": "Profiles & metrics:" if lang == "en" else "Profile & Kennzahlen:",
        },
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="render_publications",
        description="Render the complete publication-list attachment via Typst.",
    )
    parser.add_argument("--lang", choices=("en", "de"), default="en")
    parser.add_argument("--content-dir", default=None)
    parser.add_argument(
        "--output",
        default=None,
        help="PDF path (default: dist/publications-{lang}.pdf)",
    )
    return parser.parse_args(argv)


def render_publications(
    *,
    lang: str = "en",
    content_dir: Path = CONTENT_DIR,
    output: Path | None = None,
) -> Path:
    """Prepare and compile one publication-list PDF; return its path."""
    data = prepare_data(content_dir, lang=lang)
    cache_dir = REPO_ROOT / "pdf" / ".cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache = cache_dir / "publications.json"
    cache.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    out = Path(output) if output is not None else REPO_ROOT / "dist" / f"publications-{lang}.pdf"
    if not out.is_absolute():
        out = REPO_ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)

    template = REPO_ROOT / "pdf" / "templates" / "publication-list.typ"
    result = subprocess.run(
        [
            "typst",
            "compile",
            "--root",
            str(REPO_ROOT),
            "--input",
            f"lang={lang}",
            str(template),
            str(out),
        ],
        check=False,
        env={**os.environ, "SOURCE_DATE_EPOCH": os.environ.get("SOURCE_DATE_EPOCH", "0")},
    )
    if result.returncode != 0:
        raise RuntimeError(f"typst compile failed (exit {result.returncode})")
    return out


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    content_dir = Path(args.content_dir) if args.content_dir else CONTENT_DIR
    try:
        output = render_publications(lang=args.lang, content_dir=content_dir, output=args.output)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"Wrote {output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
