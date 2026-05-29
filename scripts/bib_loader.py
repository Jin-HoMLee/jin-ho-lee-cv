"""Load publications.bib and expose structured records with custom fields."""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from pybtex.database import parse_file


BIB_TYPES = {"article", "book-chapter", "conference", "book"}
AUTHORSHIP_VALUES = {"first", "shared", "middle", "last", "corresponding"}

# DOI = "10." + registrant digits + "/" + suffix. Suffix is case-insensitive but
# the registrant is always digits; no flag needed.
_DOI_RE = re.compile(r"^10\.\d{4,}/\S+$")


@dataclass(frozen=True)
class Publication:
    key: str
    title: str
    year: int
    type: str
    authorship: str
    authors: tuple[str, ...]
    venue: str | None
    doi: str | None
    raw: dict


def _venue(entry) -> str | None:
    fields = entry.fields
    return (
        fields.get("journal")
        or fields.get("booktitle")
        or fields.get("publisher")
    )


def _normalize_doi(value: str) -> str:
    """Reduce a pasted DOI (resolver URL or 'doi:'-prefixed) to bare 10.xxxx/yyy."""
    v = value.strip()
    if v.lower().startswith("doi:"):
        v = v[len("doi:"):].strip()
    marker = "doi.org/"
    idx = v.lower().find(marker)
    if idx != -1:
        v = v[idx + len(marker):].strip()
    return v


def _doi(key: str, fields) -> str | None:
    raw = fields.get("doi")
    if raw is None:
        return None
    value = _normalize_doi(str(raw))
    if not value:
        return None
    if not _DOI_RE.match(value):
        raise ValueError(f"{key}: malformed doi {value!r} (expected '10.xxxx/...')")
    return value


def _parse_entry(key: str, entry) -> Publication:
    fields = entry.fields
    for required in ("title", "year", "type", "authorship"):
        if required not in fields:
            raise ValueError(f"{key}: missing required field {required!r}")
    if fields["type"] not in BIB_TYPES:
        raise ValueError(f"{key}: unknown type {fields['type']!r}")
    if fields["authorship"] not in AUTHORSHIP_VALUES:
        raise ValueError(f"{key}: unknown authorship {fields['authorship']!r}")

    authors = tuple(str(p) for p in entry.persons.get("author", []))
    return Publication(
        key=key,
        title=fields["title"],
        year=int(fields["year"]),
        type=fields["type"],
        authorship=fields["authorship"],
        authors=authors,
        venue=_venue(entry),
        doi=_doi(key, fields),
        raw=dict(fields),
    )


def load_publications(bib_path: Path) -> list[Publication]:
    """Parse a .bib file into Publication records, sorted by year (newest first)."""
    bib = parse_file(str(bib_path))
    pubs = [_parse_entry(key, entry) for key, entry in bib.entries.items()]
    return sorted(pubs, key=lambda p: p.year, reverse=True)


def authorship_counts(pubs: Iterable[Publication]) -> dict[str, int]:
    """Return a {authorship_value: count} dict, suitable for the pie chart."""
    return dict(Counter(p.authorship for p in pubs))
