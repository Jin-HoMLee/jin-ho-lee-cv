"""Tests for scripts/publications.py — variant publication policy + aggregate."""
import pytest
from pathlib import Path

from scripts.bib_loader import Publication
from scripts.bib_loader import load_publications
from scripts.publications import (
    format_publication_summary,
    publication_mode,
    publication_summary,
)

CONTENT_DIR = Path(__file__).resolve().parent.parent / "content"


def _pub(authorship="first", type="article", category="research", year=2020, key="k"):
    return Publication(
        key=key, title="T", year=year, type=type, authorship=authorship,
        authors=("Lee, J.",), venue="V", doi=None, raw={}, category=category,
    )


def test_publication_mode_comp_bio_is_full():
    assert publication_mode("comp-bio") == "full"


def test_publication_mode_bridge_and_ds_ml_are_aggregate():
    assert publication_mode("bridge") == "aggregate"
    assert publication_mode("ds-ml") == "aggregate"


def test_summary_peer_reviewed_excludes_conference_and_applied():
    pubs = [
        _pub(type="article", authorship="first", year=2018),
        _pub(type="article", authorship="middle", year=2019),
        _pub(type="book-chapter", authorship="first", year=2020),     # peer-reviewed
        _pub(type="conference", authorship="first", year=2021),       # NOT peer-reviewed
        _pub(type="book-chapter", authorship="first", category="applied", year=2025),  # excluded
    ]
    s = publication_summary(pubs)
    assert s.peer_reviewed == 3        # 2 articles + 1 research book chapter
    assert s.conferences == 1
    assert s.pr_first == 2             # article first + chapter first
    assert s.pr_shared == 0
    assert s.pr_coauthor == 1          # the middle article
    assert (s.year_start, s.year_end) == (2018, 2021)  # research only; excludes 2025


def test_summary_folds_coauthor_buckets():
    pubs = [
        _pub(type="article", authorship="middle"),
        _pub(type="article", authorship="last"),
        _pub(type="article", authorship="corresponding"),
    ]
    assert publication_summary(pubs).pr_coauthor == 3


def test_format_fills_placeholders_with_en_dash_span():
    template = "{peer_reviewed} PR ({pr_first}/{pr_shared}/{pr_coauthor}) + {conferences} conf, {span}."
    pubs = [
        _pub(type="article", authorship="first", year=2017),
        _pub(type="conference", authorship="first", year=2019),
    ]
    assert format_publication_summary(template, pubs) == "1 PR (1/0/0) + 1 conf, 2017–2019."


def test_live_bib_aggregate_numbers():
    pubs = load_publications(CONTENT_DIR / "publications.bib")
    s = publication_summary(pubs)
    assert (s.peer_reviewed, s.pr_first, s.pr_shared, s.pr_coauthor, s.conferences) == (11, 2, 3, 6, 3)
    assert (s.year_start, s.year_end) == (2017, 2021)
    assert format_publication_summary("{span}", pubs) == "2017–2021"


def test_summary_year_span_falls_back_to_all_pubs_when_no_research():
    # All-applied corpus: research is empty, so the span falls back to all pubs.
    pubs = [
        _pub(category="applied", year=2023, key="a"),
        _pub(category="applied", year=2025, key="b"),
    ]
    s = publication_summary(pubs)
    assert (s.year_start, s.year_end) == (2023, 2025)
    # No research items → every count bucket is zero.
    assert (s.peer_reviewed, s.pr_first, s.pr_shared, s.pr_coauthor, s.conferences) == (0, 0, 0, 0, 0)


def test_summary_raises_on_empty_list():
    with pytest.raises(ValueError):
        publication_summary([])
