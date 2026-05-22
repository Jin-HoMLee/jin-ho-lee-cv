"""Detect missing `de:` keys by comparing en/de resolved content trees."""
from __future__ import annotations

from pathlib import Path

from scripts.content_loader import load_content
from scripts.langstring import resolve_langstrings


REPO_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = REPO_ROOT / "content"


def _flatten_strings(tree, prefix=""):
    """Yield (path, value) for every string leaf in the tree."""
    if isinstance(tree, dict):
        for k, v in tree.items():
            yield from _flatten_strings(v, prefix=f"{prefix}.{k}")
    elif isinstance(tree, list):
        for i, item in enumerate(tree):
            yield from _flatten_strings(item, prefix=f"{prefix}[{i}]")
    elif isinstance(tree, str):
        yield (prefix, tree)


# Paths that legitimately don't change between en and de.
# - URLs, emails, brand/proper nouns, paths, enum values, periods (YYYY-MM strings),
#   technology names, organization names.
_ALLOWED_IDENTICAL_PREFIXES = (
    ".personal.email",
    ".personal.links",
    ".personal.location",
    ".personal.name",
    ".personal.photo",
    ".publications",        # bibtex records are language-agnostic raw data
    ".labels.months_abbr",  # short month abbreviations (Jan, Feb, ...) coincide en/de
    ".experience[",         # entries — org names are identical; period dates identical
    ".education[",          # entries — institution names, locations are identical
    ".projects.",           # project records — technologies, ids, period are identical
    ".skills.",             # items[] are tech names (verbatim across langs)
    ".volunteer.",          # entries[] are org names
    ".languages[",          # proficiency enum values
)


def _is_allowed_identical(path: str, value: str) -> bool:
    """Filter out fields where it's correct for EN == DE."""
    # All numeric / date-shaped / URL / email / single-char / pure-identifier strings
    if not value or value.isdigit():
        return True
    if value.startswith(("http://", "https://", "mailto:")):
        return True
    if "@" in value and "." in value and " " not in value:  # email-shaped
        return True
    # Period strings like "2024-05"
    if len(value) == 7 and value[4] == "-" and value[:4].isdigit() and value[5:].isdigit():
        return True
    # Path-shaped values
    if value.startswith("assets/") or value.endswith((".yaml", ".typ", ".bib")):
        return True
    # Allow-list of paths that legitimately are identical
    return any(path.startswith(p) for p in _ALLOWED_IDENTICAL_PREFIXES)


def test_de_resolves_distinctly_from_en():
    """Walk the en and de resolved trees; flag any user-visible string that's identical."""
    en_tree = resolve_langstrings(load_content(CONTENT_DIR, lang="en"), lang="en")
    de_tree = resolve_langstrings(load_content(CONTENT_DIR, lang="de"), lang="de")

    en_strings = dict(_flatten_strings(en_tree))
    de_strings = dict(_flatten_strings(de_tree))

    suspicious = []
    for path, en_value in en_strings.items():
        de_value = de_strings.get(path)
        if de_value == en_value and not _is_allowed_identical(path, en_value):
            suspicious.append((path, en_value))

    assert not suspicious, (
        "Found user-visible strings identical between EN and DE (suggests missing `de:` key):\n"
        + "\n".join(f"  {p}: {v!r}" for p, v in suspicious[:20])
    )
