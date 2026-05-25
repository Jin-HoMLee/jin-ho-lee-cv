"""Pytest assertions for the JSON-LD renderer."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.bib_loader import load_publications
from scripts.content_loader import load_content
from scripts.langstring import resolve_langstrings
from scripts.render_jsonld import to_jsonld


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
