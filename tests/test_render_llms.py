"""Pytest assertions for the llms.txt renderer."""

from __future__ import annotations

from pathlib import Path

from scripts.bib_loader import load_publications
from scripts.config import PAGES_BASE_URL, RELEASES_BASE_URL
from scripts.content_loader import load_content
from scripts.langstring import resolve_langstrings
from scripts.render_llms import render

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = REPO_ROOT / "content"


def _content():
    return resolve_langstrings(load_content(CONTENT_DIR, lang="en"), lang="en")


def test_h1_has_name_and_headline():
    assert render().startswith("# Jin-Ho Lee — Bioinformatics · Data Science\n")


def test_blockquote_summary_present():
    c = _content()
    assert f"> {c['profile']['tagline']}" in render()


def test_all_selected_projects_linked():
    c = _content()
    out = render()
    for p in c["selected_projects"]:
        assert f"]({PAGES_BASE_URL}/projects/{p['id']}/)" in out
        assert p["title"] in out


def test_publications_doi_linked():
    pubs = load_publications(CONTENT_DIR / "publications.bib")
    out = render()
    doi_pubs = [p for p in pubs if p.doi]
    assert doi_pubs, "expected at least one DOI'd pub"
    for p in doi_pubs:
        assert f"(https://doi.org/{p.doi})" in out


def test_formats_and_links_sections():
    out = render()
    assert f"{RELEASES_BASE_URL}/cv-en.pdf" in out
    assert f"{RELEASES_BASE_URL}/resume.json" in out
    assert f"{PAGES_BASE_URL}/person.jsonld" in out
    assert "## Links" in out
    assert "[GitHub](" in out and "[ORCID](" in out


def test_no_pii():
    out = render().lower()
    assert "phone" not in out
    for kw in ("strasse", "straße", "hausnummer"):
        assert kw not in out
