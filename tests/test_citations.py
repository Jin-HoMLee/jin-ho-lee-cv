from __future__ import annotations

import json
from pathlib import Path

from scripts.bib_loader import Publication, load_publications
from scripts.citations import enrich_publications, load_citation_cache

REPO_ROOT = Path(__file__).resolve().parent.parent
BIB_PATH = REPO_ROOT / "content" / "publications.bib"
CACHE_PATH = REPO_ROOT / "data" / "citations.json"


def _pub(**over) -> Publication:
    base = dict(
        key="x", title="T", year=2019, type="article", authorship="first",
        authors=("Lee, J.",), venue="Cancers", doi=None, raw={},
    )
    base.update(over)
    return Publication(**base)


def test_load_cache_reads_counts(tmp_path):
    f = tmp_path / "citations.json"
    f.write_text(json.dumps({"counts": {"10.1/a": 5, "10.2/b": 12}}), encoding="utf-8")
    assert load_citation_cache(f) == {"10.1/a": 5, "10.2/b": 12}


def test_load_cache_reads_counts_from_full_document(tmp_path):
    # Mirrors the real shape that fetch_citations.refresh() writes (Task 3/5):
    # the reader must extract `counts` and ignore the metadata fields.
    f = tmp_path / "citations.json"
    f.write_text(json.dumps({
        "_generated_by": "just refresh-citations — do not hand-edit",
        "source": "crossref",
        "fetched_at": "2026-06-02",
        "counts": {"10.1/a": 5},
    }), encoding="utf-8")
    assert load_citation_cache(f) == {"10.1/a": 5}


def test_load_cache_missing_file_is_empty(tmp_path):
    assert load_citation_cache(tmp_path / "nope.json") == {}


def test_load_cache_garbage_is_empty(tmp_path):
    f = tmp_path / "citations.json"
    f.write_text("{not json", encoding="utf-8")
    assert load_citation_cache(f) == {}


def test_load_cache_non_int_values_dropped(tmp_path):
    f = tmp_path / "citations.json"
    payload = {"counts": {"10.1/a": 5, "10.2/b": "oops", "10.3/c": None}}
    f.write_text(json.dumps(payload), encoding="utf-8")
    assert load_citation_cache(f) == {"10.1/a": 5}


def test_enrich_sets_count_for_matching_doi():
    pubs = [_pub(doi="10.1/a"), _pub(doi="10.2/b")]
    out = enrich_publications(pubs, {"10.1/a": 7})
    assert out[0].citation_count == 7
    assert out[1].citation_count is None


def test_enrich_pub_without_doi_stays_none():
    out = enrich_publications([_pub(doi=None)], {"10.1/a": 7})
    assert out[0].citation_count is None


def test_enrich_does_not_mutate_inputs():
    pubs = [_pub(doi="10.1/a")]
    enrich_publications(pubs, {"10.1/a": 7})
    assert pubs[0].citation_count is None  # original untouched (frozen → new objects)


def test_committed_cache_has_no_orphan_dois():
    """Every DOI in data/citations.json must map to a real publication (no stale keys)."""
    cache = load_citation_cache(CACHE_PATH)
    pub_dois = {p.doi for p in load_publications(BIB_PATH) if p.doi}
    assert set(cache) <= pub_dois
