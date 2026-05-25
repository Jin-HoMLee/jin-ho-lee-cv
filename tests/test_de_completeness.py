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


# Path substrings that mark a leaf value as legitimately invariant across EN/DE.
# Checked with `substring in path`, so they target specific leaf field names
# regardless of array index.  Deliberately narrow — do NOT blanket-cover whole
# subtrees; that would hide genuine missing-translation bugs.
#
# Rationale for each entry:
#   .personal.email / .name. / .location. / .photo / .links.
#       → contact details and proper nouns
#   .publications
#       → raw BibTeX records are language-agnostic
#   .institution
#       → university / organisation proper noun (education entries)
#   .location
#       → city / country strings are proper nouns (e.g. "Heidelberg, Germany")
#   .org.
#       → employer proper noun + URL (experience entries)
#   .bullets[
#       → structured {en, de, refs} dicts that are NOT resolved to a single
#         language by resolve_langstrings (structural limitation); both the
#         .en and .de sub-leaves appear in both trees unchanged
#   .period.start / .period.end
#       → YYYY-MM date strings
#   .id
#       → internal enum keys (experience IDs, project IDs, etc.)
#   .proficiency
#       → enum key ("native", "fluent", "basic", "passive") — language invariant
#   .items[
#       → tech / brand name lists inside skill groups
#   .technologies[
#       → tech stack lists inside project records
#   .entries[
#       → organisation names inside volunteer category entries
#   .category
#       → project category enum ("consulting", "data-science", "life-science")
#   .labels.months_abbr
#       → short month abbreviations: several coincide in EN and DE
#       (Jan, Feb, Apr, Jun, Jul, Aug, Sep, Nov)
#   .role
#       → job titles that are English proper nouns used verbatim in German
#         (e.g. "Data Science Trainee, Associate & Coach"); the resolver
#         cannot distinguish "de: provided but equals en:" from "de: missing",
#         so we allow .role to be identical without raising a false positive
_INVARIANT_PATH_SUBSTRINGS = (
    # Personal contact details / proper nouns
    ".personal.email",
    ".personal.name.",
    ".personal.location.",
    ".personal.photo",
    ".personal.links.",
    # Publications — raw BibTeX, language-agnostic
    ".publications",
    # Education — institution is a proper noun; location is a city/country string
    ".institution",
    ".location",
    # Experience — employer proper nouns + structural bullets subtree
    ".org.",
    ".bullets[",
    # Period dates (YYYY-MM)
    ".period.start",
    ".period.end",
    # ID fields — internal enum keys, not user-visible translated strings
    # Matches both array-index paths (.experience[0].id) and dict-key paths (.projects.C1.id)
    ".id",
    # Language proficiency enum values
    ".proficiency",
    # Tech / brand name lists
    ".items[",
    ".technologies[",
    # Volunteer organisation names
    ".entries[",
    # Project category enum
    ".category",
    # Short month abbreviations (some coincide in EN/DE)
    ".labels.months_abbr",
)

# Exact paths that are legitimately identical in EN and DE, but cannot be captured
# by the generic substring rules above without risking false negatives on
# neighbouring translatable fields.
#
# Rationale for each entry:
#   Skill group labels "Assays", "Eng & Tools", "Cloud" — English technical terms
#       adopted verbatim in German; de: is explicitly provided with the same value.
#   Experience / project .role paths where the English job title IS the German title
#       (e.g. "Data Science Trainee, Associate & Coach") — English term used in DE.
#       These are pin-pointed by path so the test still catches regressions on roles
#       that DO have a German translation (e.g. experience[0].role "Consultant" → "Berater").
_INVARIANT_EXACT = frozenset(
    {
        # Skill category / group labels — English tech terms used verbatim in German
        ".skills.categories[1].name",              # "Biotech Wet-Lab"
        ".skills.categories[1].groups[2].label",   # "Assays"
        ".skills.categories[2].groups[1].label",   # "Eng & Tools"
        ".skills.categories[2].groups[2].label",   # "Cloud"
        # Experience roles — English job-title strings used verbatim in German
        ".experience[1].role",  # "Data Science Trainee, Associate & Coach"
        # Project roles — English job-title strings used verbatim in German
        ".projects.C1.role",    # "Lead Business Functional Analyst (Cintellic GmbH)"
        ".projects.C2.role",    # "Lead Business Functional Analyst (Cintellic GmbH)"
        ".projects.D3.role",    # "Data Science Coach (neuefische GmbH)"
    }
)


def _is_allowed_identical(path: str, value: str) -> bool:
    """Return True when EN == DE is expected and not evidence of a missing translation."""
    # Empty, pure-numeric, or single-character values are trivially invariant
    if not value or value.isdigit() or len(value) == 1:
        return True
    # URLs and email addresses are language-agnostic
    if value.startswith(("http://", "https://", "mailto:")):
        return True
    if "@" in value and "." in value and " " not in value:
        return True
    # Period strings like "2024-05"
    if len(value) == 7 and value[4] == "-" and value[:4].isdigit() and value[5:].isdigit():
        return True
    # File-path-shaped values
    if value.startswith("assets/") or value.endswith((".yaml", ".typ", ".bib")):
        return True
    # Precise path-substring allow-list (see _INVARIANT_PATH_SUBSTRINGS for rationale)
    if any(s in path for s in _INVARIANT_PATH_SUBSTRINGS):
        return True
    # Exact path allow-list for known same-value fields (see _INVARIANT_EXACT for rationale)
    return path in _INVARIANT_EXACT


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
