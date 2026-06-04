from __future__ import annotations

import json
from pathlib import Path

from scripts.fetch_citations import build_counts, fetch_citation_count, refresh

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = REPO_ROOT / "content"
BIB_PATH = CONTENT_DIR / "publications.bib"


class _FakeResp:
    """Minimal context-manager stand-in for an http response (no network)."""

    def __init__(self, data: bytes):
        self._data = data

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self) -> bytes:
        return self._data


def test_fetch_parses_is_referenced_by_count():
    def opener(req, timeout):
        return _FakeResp(b'{"message": {"is-referenced-by-count": 58}}')

    assert fetch_citation_count("10.3390/x", mailto="a@b.c", opener=opener) == 58


def test_build_counts_uses_fetched_values():
    def fetch(doi):
        return {"10.a": 10, "10.b": 20}[doi]

    assert build_counts(["10.a", "10.b"], fetch=fetch, prior={}) == {"10.a": 10, "10.b": 20}


def test_build_counts_retains_prior_on_error():
    def fetch(doi):
        if doi == "10.good":
            return 10
        raise RuntimeError("boom")

    counts = build_counts(["10.good", "10.bad", "10.new"], fetch=fetch, prior={"10.bad": 7})
    # good → fetched; bad → retained prior; new → failed with no prior → omitted
    assert counts == {"10.good": 10, "10.bad": 7}


def test_refresh_writes_sorted_documented_cache(tmp_path):
    cache = tmp_path / "citations.json"

    def fetch(doi):
        return len(doi)  # deterministic, no network

    doc = refresh(
        bib_path=BIB_PATH,
        cache_path=cache,
        content_dir=CONTENT_DIR,
        fetch=fetch,
        today="2026-06-02",
    )
    assert doc["_generated_by"] == "just refresh-citations — do not hand-edit"
    assert doc["source"] == "crossref"
    assert doc["fetched_at"] == "2026-06-02"
    assert list(doc["counts"]) == sorted(doc["counts"])  # keys sorted for stable diffs
    on_disk = json.loads(cache.read_text(encoding="utf-8"))
    assert on_disk == doc
