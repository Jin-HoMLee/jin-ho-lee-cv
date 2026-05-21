"""Tests for scripts.bib_loader."""
from pathlib import Path

import pytest

from scripts.bib_loader import (
    AUTHORSHIP_VALUES,
    BIB_TYPES,
    authorship_counts,
    load_publications,
)


BIB_PATH = Path(__file__).parent.parent / "content" / "publications.bib"


def test_loads_all_entries():
    pubs = load_publications(BIB_PATH)
    assert len(pubs) >= 15, f"expected 15+ entries, got {len(pubs)}"


def test_publications_have_required_fields():
    for pub in load_publications(BIB_PATH):
        assert pub.key
        assert pub.title
        assert pub.year >= 2017
        assert pub.year <= 2030
        assert pub.type in BIB_TYPES, f"unknown type {pub.type} on {pub.key}"
        assert pub.authorship in AUTHORSHIP_VALUES, (
            f"unknown authorship {pub.authorship} on {pub.key}"
        )


def test_publications_sorted_by_year_desc():
    pubs = load_publications(BIB_PATH)
    years = [p.year for p in pubs]
    assert years == sorted(years, reverse=True)


def test_authorship_counts_sums_to_total():
    pubs = load_publications(BIB_PATH)
    counts = authorship_counts(pubs)
    assert sum(counts.values()) == len(pubs)


def test_missing_authorship_field_raises(tmp_path):
    """A bib entry without the custom 'authorship' field should fail loading."""
    bad = tmp_path / "missing_authorship.bib"
    bad.write_text(
        "@article{x, author={X}, title={T}, year={2020}, journal={J}, type={article}}\n"
    )
    with pytest.raises(ValueError, match="authorship"):
        load_publications(bad)
