"""Pytest assertions for the JSON Resume renderer."""
from __future__ import annotations

import json
import re
from pathlib import Path

import jsonschema
import pytest

from scripts.bib_loader import load_publications
from scripts.content_loader import load_content
from scripts.langstring import resolve_langstrings
from scripts.render_jsonresume import to_jsonresume


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
    assert basics["name"] == f"{content['personal']['name']['given']} {content['personal']['name']['family']}"
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


def test_pii_never_reaches_dump(tmp_path, monkeypatch):
    """Even if a private overlay exists in the repo, the renderer must never include it.

    `to_jsonresume` only takes resolved content + pubs as arguments, so the contract
    is enforced inside `main()` — verify the actual CLI path doesn't leak PII.
    """
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
        output = tmp_path / "resume.json"
        from scripts.render_jsonresume import main
        main(["--output", str(output)])
        text = output.read_text()
        assert marker_phone not in text, "PII leaked: private phone in resume.json"
        assert marker_street not in text, "PII leaked: private street in resume.json"
    finally:
        if cleanup_file and private_yaml.exists():
            private_yaml.unlink()
        if cleanup_dir and private_dir.exists():
            private_dir.rmdir()


def test_basics_url_uses_pages_base(doc):
    from scripts.config import PAGES_BASE_URL
    assert doc["basics"]["url"].startswith(PAGES_BASE_URL)
