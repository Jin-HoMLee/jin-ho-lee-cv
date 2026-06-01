"""Pytest assertions for the JSON-LD renderer."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.bib_loader import Publication, load_publications
from scripts.content_loader import load_content
from scripts.langstring import resolve_langstrings
from scripts.render_jsonld import _publications as jsonld_publications, to_jsonld


REPO_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = REPO_ROOT / "content"


@pytest.fixture(scope="module")
def doc() -> dict:
    content = resolve_langstrings(load_content(CONTENT_DIR, lang="en"), lang="en")
    pubs = load_publications(CONTENT_DIR / "publications.bib")
    return to_jsonld(content, pubs)


def test_output_valid_json(doc):
    json.dumps(doc)  # raises if non-serialisable


def test_has_schema_context(doc):
    assert doc["@context"] == "https://schema.org"


def test_type_is_person(doc):
    assert doc["@type"] == "Person"


def test_publications_count_matches_bib(doc):
    pubs = load_publications(CONTENT_DIR / "publications.bib")
    articles = [g for g in doc.get("@graph", []) if g["@type"] == "ScholarlyArticle"]
    assert len(articles) == len(pubs)


def test_alumni_count_matches_education(doc):
    content = resolve_langstrings(load_content(CONTENT_DIR, lang="en"), lang="en")
    assert len(doc["alumniOf"]) == len(content["education"])


def test_no_pii_in_output(doc):
    """`load_content` is hard-coded to private_path=None — no phone, no full address."""
    text = json.dumps(doc).lower()
    assert "phone" not in text
    assert "telephone" not in text
    for kw in ("strasse", "straße", "street ", "hausnummer"):
        assert kw not in text, f"unexpected PII keyword in output: {kw!r}"


def test_sameas_includes_github(doc):
    assert any("github.com" in url for url in doc.get("sameAs", []))


def test_image_is_absolute_url(doc):
    assert doc["image"].startswith("https://")


def test_url_uses_pages_base(doc):
    from scripts.config import PAGES_BASE_URL
    assert doc["url"].startswith(PAGES_BASE_URL)


def test_image_uses_pages_base(doc):
    from scripts.config import PAGES_BASE_URL
    assert doc["image"].startswith(PAGES_BASE_URL)


def test_graph_includes_project_creativeworks(doc):
    """Every project in content/projects/ should appear in @graph as a CreativeWork."""
    from scripts.content_loader import load_content
    from scripts.langstring import resolve_langstrings
    content = resolve_langstrings(load_content(CONTENT_DIR, lang="en"), lang="en")
    expected_ids = set(content["projects"].keys())
    works = [g for g in doc["@graph"] if g["@type"] == "CreativeWork"]
    assert len(works) == len(expected_ids), f"expected {len(expected_ids)} CreativeWorks, got {len(works)}"
    work_urls = {w["url"] for w in works}
    for pid in expected_ids:
        assert any(pid in url for url in work_urls), f"no CreativeWork URL contains project id {pid!r}"


def test_creativework_urls_use_pages_base(doc):
    from scripts.config import PAGES_BASE_URL
    works = [g for g in doc["@graph"] if g["@type"] == "CreativeWork"]
    for w in works:
        assert w["url"].startswith(PAGES_BASE_URL + "/projects/"), f"unexpected CreativeWork URL: {w['url']!r}"


def test_pii_never_reaches_main_output(tmp_path):
    """Even if a private overlay exists in the repo, main() must not include it."""
    private_dir = REPO_ROOT / "content.private"
    private_yaml = private_dir / "private.yaml"
    marker_phone = "+49-555-PYTEST-MARKER"
    marker_street = "Pytest-Marker-Strasse 99"
    cleanup_dir = not private_dir.exists()
    cleanup_file = not private_yaml.exists()
    try:
        private_dir.mkdir(exist_ok=True)
        private_yaml.write_text(
            f"personal:\n"
            f"  phone: '{marker_phone}'\n"
            f"  location:\n"
            f"    street: '{marker_street}'\n",
            encoding="utf-8",
        )
        output = tmp_path / "person.jsonld"
        from scripts.render_jsonld import main
        main(["--output", str(output)])
        text = output.read_text()
        assert marker_phone not in text, "PII leaked: private phone in person.jsonld"
        assert marker_street not in text, "PII leaked: private street in person.jsonld"
    finally:
        if cleanup_file and private_yaml.exists():
            private_yaml.unlink()
        if cleanup_dir and private_dir.exists():
            private_dir.rmdir()


def _pub(**over) -> Publication:
    base = dict(
        key="x", title="T", year=2019, type="article", authorship="first",
        authors=("Lee, J.",), venue="Cancers", doi=None, raw={},
    )
    base.update(over)
    return Publication(**base)


def test_scholarly_article_sameas_is_doi():
    [item] = jsonld_publications([_pub(doi="10.3390/cancers11121877")])
    assert item["sameAs"] == ["https://doi.org/10.3390/cancers11121877"]


def test_scholarly_article_no_sameas_without_doi():
    [item] = jsonld_publications([_pub(doi=None)])
    assert "sameAs" not in item


def test_orcid_and_website_in_same_as(doc):
    same_as = doc["sameAs"]
    assert "https://orcid.org/0009-0001-8784-1771" in same_as
    assert "https://jinholee.is-a.dev/" in same_as


def test_person_award_present(doc):
    assert "DAAD PROMOS Scholarship" in doc["award"]
    assert "DeGBS Poster Award" in doc["award"]


# --- #42: period-end edge cases (characterization of _works_for selection) ---
from scripts.render_jsonld import _works_for  # noqa: E402


def _content(*ends):
    """Build experience entries; pass None for explicit null end, False to omit the key."""
    exps = []
    for i, e in enumerate(ends):
        period = {"start": "2014-04"}
        if e is not False:
            period["end"] = e
        exps.append({"org": {"name": f"Org{i}"}, "role": "R", "period": period})
    return {"experience": exps}


def test_works_for_picks_null_end_entry():
    wf = _works_for(_content("2020-01", None))
    assert wf is not None and wf["name"] == "Org1"


def test_works_for_none_when_all_dated():
    assert _works_for(_content("2020-01", "2025-07")) is None
