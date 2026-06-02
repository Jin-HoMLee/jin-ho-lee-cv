"""Pytest assertions for the JSON-LD renderer (top-level @graph of @id-linked entities)."""
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


def _person_node(doc: dict) -> dict:
    return next(g for g in doc["@graph"] if g["@type"] == "Person")


# --- document shape ---

def test_output_valid_json(doc):
    json.dumps(doc)  # raises if non-serialisable


def test_has_schema_context(doc):
    assert doc["@context"] == "https://schema.org"


def test_root_has_only_context_and_graph(doc):
    assert set(doc.keys()) == {"@context", "@graph"}


def test_graph_has_one_person(doc):
    persons = [g for g in doc["@graph"] if g["@type"] == "Person"]
    assert len(persons) == 1


def test_publications_count_matches_bib(doc):
    pubs = load_publications(CONTENT_DIR / "publications.bib")
    articles = [g for g in doc["@graph"] if g["@type"] == "ScholarlyArticle"]
    assert len(articles) == len(pubs)


# --- Person node ---

def test_person_id_is_orcid(doc):
    content = resolve_langstrings(load_content(CONTENT_DIR, lang="en"), lang="en")
    assert _person_node(doc)["@id"] == content["personal"]["links"]["orcid"]


def test_person_identifier_is_orcid(doc):
    content = resolve_langstrings(load_content(CONTENT_DIR, lang="en"), lang="en")
    ident = _person_node(doc)["identifier"]
    assert ident["@type"] == "PropertyValue" and ident["propertyID"] == "ORCID"
    assert ident["value"] == content["personal"]["links"]["orcid"]


def test_alumni_deduped(doc):
    names = [a["name"] for a in _person_node(doc)["alumniOf"]]
    assert len(names) == len(set(names)), f"duplicate alumniOf: {names}"


def test_no_works_for(doc):
    # Current content has no open-ended role → worksFor omitted (honest, no current employer).
    assert "worksFor" not in _person_node(doc)


def test_works_for_emitted_when_open_ended():
    """If a future role has end:null, the renderer auto-detects it as current employer."""
    content = resolve_langstrings(load_content(CONTENT_DIR, lang="en"), lang="en")
    content["experience"] = [
        {"org": {"name": "Future Corp"}, "role": "Lead", "period": {"start": "2026-01", "end": None}},
        *content["experience"],
    ]
    pubs = load_publications(CONTENT_DIR / "publications.bib")
    person = next(g for g in to_jsonld(content, pubs)["@graph"] if g["@type"] == "Person")
    assert person["worksFor"] == {"@type": "Organization", "name": "Future Corp"}


def test_has_occupation_from_headline(doc):
    names = [o["name"] for o in _person_node(doc)["hasOccupation"]]
    assert names == ["Bioinformatics", "Data Science"]


def test_knows_about_is_curated_content(doc):
    content = resolve_langstrings(load_content(CONTENT_DIR, lang="en"), lang="en")
    assert _person_node(doc)["knowsAbout"] == content["personal"]["knowsAbout"]


def test_sameas_includes_github(doc):
    assert any("github.com" in url for url in _person_node(doc)["sameAs"])


def test_orcid_and_website_in_same_as(doc):
    same_as = _person_node(doc)["sameAs"]
    assert "https://orcid.org/0009-0001-8784-1771" in same_as
    assert "https://jinholee.is-a.dev/" in same_as


def test_image_is_absolute_url(doc):
    assert _person_node(doc)["image"].startswith("https://")


def test_url_uses_pages_base(doc):
    from scripts.config import PAGES_BASE_URL
    assert _person_node(doc)["url"].startswith(PAGES_BASE_URL)


def test_image_uses_pages_base(doc):
    from scripts.config import PAGES_BASE_URL
    assert _person_node(doc)["image"].startswith(PAGES_BASE_URL)


def test_person_award_present(doc):
    award = _person_node(doc)["award"]
    assert "DAAD PROMOS Scholarship" in award
    assert "DeGBS Poster Award" in award


# --- privacy ---

def test_no_pii_in_output(doc):
    """`load_content` is hard-coded to private_path=None — no phone, no full address."""
    text = json.dumps(doc).lower()
    assert "phone" not in text
    assert "telephone" not in text
    for kw in ("strasse", "straße", "street ", "hausnummer"):
        assert kw not in text, f"unexpected PII keyword in output: {kw!r}"


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


# --- ScholarlyArticle nodes ---

def _pub(**over) -> Publication:
    base = dict(
        key="x", title="T", year=2019, type="article", authorship="first",
        authors=("Lee, J.",), venue="Cancers", doi=None, raw={},
    )
    base.update(over)
    return Publication(**base)


def test_scholarly_article_sameas_is_doi():
    [item] = jsonld_publications([_pub(doi="10.3390/cancers11121877")], "https://orcid.org/X", "Lee, J")
    assert item["sameAs"] == ["https://doi.org/10.3390/cancers11121877"]


def test_scholarly_article_no_sameas_without_doi():
    [item] = jsonld_publications([_pub(doi=None)], "https://orcid.org/X", "Lee, J")
    assert "sameAs" not in item


def test_scholarly_article_doi_identifier_and_id():
    [item] = jsonld_publications([_pub(doi="10.3390/cancers11121877")], "https://orcid.org/X", "Lee, J")
    assert item["@id"] == "https://doi.org/10.3390/cancers11121877"
    assert item["identifier"] == {
        "@type": "PropertyValue", "propertyID": "DOI", "value": "10.3390/cancers11121877"
    }


def test_scholarly_article_no_doi_uses_stable_key_fragment():
    [item] = jsonld_publications([_pub(doi=None, key="lee2019_conrad")], "https://orcid.org/X", "Lee, J")
    assert item["@id"].endswith("#publication-lee2019_conrad")
    assert "identifier" not in item


def test_scholarly_article_links_author_to_person():
    [item] = jsonld_publications([_pub(authors=("Lee, J.", "Hausmann, M."))], "https://orcid.org/X", "Lee, J")
    assert {"@id": "https://orcid.org/X"} in item["author"]
    assert {"@type": "Person", "name": "Hausmann, M."} in item["author"]


def test_publication_with_citation_count_emits_interaction_statistic():
    [item] = jsonld_publications(
        [_pub(doi="10.3390/cancers11121877", citation_count=58)],
        "https://orcid.org/X", "Lee, J",
    )
    assert item["interactionStatistic"] == {
        "@type": "InteractionCounter",
        "interactionType": "https://schema.org/CiteAction",
        "userInteractionCount": 58,
    }


def test_publication_without_citation_count_omits_interaction_statistic():
    [item] = jsonld_publications(
        [_pub(doi="10.3390/cancers11121877")], "https://orcid.org/X", "Lee, J",
    )
    assert "interactionStatistic" not in item


# --- CreativeWork (project) nodes ---

def test_graph_includes_project_creativeworks(doc):
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


def test_creativework_has_id_and_creator(doc):
    content = resolve_langstrings(load_content(CONTENT_DIR, lang="en"), lang="en")
    orcid = content["personal"]["links"]["orcid"]
    works = [g for g in doc["@graph"] if g["@type"] == "CreativeWork"]
    for w in works:
        assert w["@id"] == w["url"]
        assert w["creator"] == {"@id": orcid}
