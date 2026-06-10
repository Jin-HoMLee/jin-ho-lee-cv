"""Pytest assertions for the JSON Resume renderer."""

from __future__ import annotations

import json
import re
from pathlib import Path

import jsonschema
import pytest

from scripts.bib_loader import Publication, load_publications
from scripts.content_loader import load_content
from scripts.langstring import resolve_langstrings
from scripts.render_jsonresume import _publications as jsonresume_publications, to_jsonresume


REPO_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = REPO_ROOT / "content"
SCHEMA_PATH = REPO_ROOT / "tests" / "fixtures" / "jsonresume-schema.json"


@pytest.fixture(scope="module")
def doc() -> dict:
    content = resolve_langstrings(load_content(CONTENT_DIR, lang="en"), lang="en")
    pubs = load_publications(CONTENT_DIR / "publications.bib")
    return to_jsonresume(content, pubs)


def test_output_validates_against_schema_fixture(doc):
    schema = json.loads(SCHEMA_PATH.read_text())
    jsonschema.validate(instance=doc, schema=schema)


def test_basics_round_trip(doc):
    content = resolve_langstrings(load_content(CONTENT_DIR, lang="en"), lang="en")
    basics = doc["basics"]
    assert (
        basics["name"]
        == f"{content['personal']['name']['given']} {content['personal']['name']['family']}"
    )
    assert basics["email"] == content["personal"]["email"]
    assert basics["summary"]  # non-empty
    assert any(p["network"].lower() == "github" for p in basics["profiles"])


def test_all_experience_entries_present(doc):
    content = resolve_langstrings(load_content(CONTENT_DIR, lang="en"), lang="en")
    assert len(doc["work"]) == len(content["experience"])


def test_all_publications_present(doc):
    pubs = load_publications(CONTENT_DIR / "publications.bib")
    assert len(doc["publications"]) == len(pubs)


def test_dates_iso_8601(doc):
    iso = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    for entry in doc["work"] + doc.get("education", []):
        if "startDate" in entry:
            assert iso.match(entry["startDate"]), f"bad startDate: {entry['startDate']!r}"
        if "endDate" in entry:
            assert iso.match(entry["endDate"]), f"bad endDate: {entry['endDate']!r}"


def test_skills_flattened_from_categories(doc):
    """Each (category, group) pair becomes one entry in flat skills[]."""
    content = resolve_langstrings(load_content(CONTENT_DIR, lang="en"), lang="en")
    expected_count = sum(len(cat["groups"]) for cat in content["skills"]["categories"])
    assert len(doc["skills"]) == expected_count


def test_pii_never_reaches_dump(tmp_path, private_leak_check):
    """Even if a private overlay exists in the repo, the renderer must never include it.

    `to_jsonresume` only takes resolved content + pubs as arguments, so the contract
    is enforced inside `main()` — verify the actual CLI path doesn't leak PII.
    """
    from scripts.render_jsonresume import main

    private_leak_check(lambda out: main(["--output", str(out)]), tmp_path / "resume.json")


def test_basics_url_uses_pages_base(doc):
    from scripts.config import PAGES_BASE_URL

    assert doc["basics"]["url"].startswith(PAGES_BASE_URL)


def _pub(**over) -> Publication:
    base = dict(
        key="x",
        title="T",
        year=2019,
        type="article",
        authorship="first",
        authors=("Lee, J.",),
        venue="Cancers",
        doi=None,
        raw={},
    )
    base.update(over)
    return Publication(**base)


def test_publication_url_is_doi_when_present():
    [entry] = jsonresume_publications([_pub(doi="10.3390/cancers11121877")])
    assert entry["url"] == "https://doi.org/10.3390/cancers11121877"


def test_publication_url_omitted_when_no_doi():
    [entry] = jsonresume_publications([_pub(doi=None)])
    assert "url" not in entry


def test_bsc_education_area_is_bioinformatics(doc):
    bsc = next(e for e in doc["education"] if e["studyType"].startswith("B.Sc."))
    assert bsc["area"] == "Bioinformatics"


def test_awards_array_present(doc):
    titles = {a["title"] for a in doc["awards"]}
    assert "DAAD PROMOS Scholarship" in titles
    daad = next(a for a in doc["awards"] if a["title"] == "DAAD PROMOS Scholarship")
    assert daad["awarder"] == "DAAD"
    assert daad["date"] == "2015-01-01"
    assert "summary" in daad


# --- #42: period-end edge cases (characterization of existing _work behavior) ---
from scripts.render_jsonresume import _work, _pad_end  # noqa: E402


def _exp(period):
    return {
        "experience": [
            {
                "org": {"name": "Org"},
                "role": "Dev",
                "period": period,
                "bullets": [],
            }
        ]
    }


def test_work_dated_end_emits_enddate():
    w = _work(_exp({"start": "2024-05", "end": "2025-07"}))[0]
    assert w["startDate"] == "2024-05-01"
    assert w["endDate"] == _pad_end("2025-07")


def test_work_null_end_omits_enddate():
    w = _work(_exp({"start": "2014-04", "end": None}))[0]
    assert "endDate" not in w


def test_work_absent_end_omits_enddate():
    w = _work(_exp({"start": "2014-04"}))[0]
    assert "endDate" not in w
