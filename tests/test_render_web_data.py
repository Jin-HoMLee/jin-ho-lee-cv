"""Tests for scripts/render_web_data.py — dumps bilingual content JSON for Astro."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.bib_loader import Publication, load_publications
from scripts.publications import publication_summary
from scripts.render_web_data import _to_jsonable, render_web_data, OUTPUT_DIR


REPO_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = REPO_ROOT / "content"


@pytest.fixture
def rendered(tmp_path):
    """Render both langs into a tmp_path/web/src/data/ and return the loaded JSON."""
    out_dir = tmp_path / "web" / "src" / "data"
    render_web_data(content_dir=CONTENT_DIR, output_dir=out_dir)
    en = json.loads((out_dir / "content.en.json").read_text(encoding="utf-8"))
    de = json.loads((out_dir / "content.de.json").read_text(encoding="utf-8"))
    return en, de


def test_round_trip_structural_keys(rendered):
    """Both JSON files have the expected top-level keys."""
    en, de = rendered
    expected_keys = {
        "personal", "profile", "skills", "education", "experience",
        "projects", "selected_projects", "languages", "volunteer",
        "publications", "labels", "awards", "publications_aggregate",
    }
    assert set(en.keys()) == expected_keys
    assert set(de.keys()) == expected_keys


def test_langmaps_resolved_to_strings(rendered):
    """No raw {en: ..., de: ...} maps should remain in the dumped JSON."""
    en, _ = rendered
    # personal.headline was a langmap in YAML; should be a plain string after resolution
    assert isinstance(en["personal"]["headline"], str)
    # labels.sections.profile was {en: "Profile", de: "Profil"} — should be "Profile" in EN dump
    assert isinstance(en["labels"]["sections"]["profile"], str)
    assert en["labels"]["sections"]["profile"] == "Profile"


def test_pii_never_reaches_dump(tmp_path):
    """Even with content.private/private.yaml present, no phone or street leaks."""
    # Create a fake private overlay with distinctive values
    private_dir = tmp_path / "content.private"
    private_dir.mkdir()
    (private_dir / "private.yaml").write_text(
        "phone: '+99 999 LEAKED_PHONE_NUMBER'\n"
        "address:\n"
        "  street: 'LEAKED_STREET_NAME 42'\n"
        "  postal_code: '00000'\n"
        "  city: 'Leak City'\n"
        "  country: 'XX'\n",
        encoding="utf-8",
    )

    # render_web_data must NOT accept a private_path argument; it must hard-code None.
    # We verify the contract by checking the dump for the marker strings.
    out_dir = tmp_path / "web" / "src" / "data"
    render_web_data(content_dir=CONTENT_DIR, output_dir=out_dir)

    en_text = (out_dir / "content.en.json").read_text(encoding="utf-8")
    de_text = (out_dir / "content.de.json").read_text(encoding="utf-8")
    assert "LEAKED_PHONE_NUMBER" not in en_text
    assert "LEAKED_PHONE_NUMBER" not in de_text
    assert "LEAKED_STREET_NAME" not in en_text
    assert "LEAKED_STREET_NAME" not in de_text


def test_bilingual_parity(rendered):
    """EN and DE dumps have the same structural shape: same keys, same array lengths, same project ids."""
    en, de = rendered

    # Top-level keys (already covered, but doubles as smoke)
    assert set(en.keys()) == set(de.keys())

    # Experience entries: same count, same ids in same order
    assert len(en["experience"]) == len(de["experience"])
    assert [e["id"] for e in en["experience"]] == [e["id"] for e in de["experience"]]

    # Projects: same id set
    assert set(en["projects"].keys()) == set(de["projects"].keys())

    # Publications: same count and same keys in same order (sorted by year desc)
    assert len(en["publications"]) == len(de["publications"])
    assert [p["key"] for p in en["publications"]] == [p["key"] for p in de["publications"]]


def test_publications_shape(rendered):
    """Each publication has the required fields with allowed enum values."""
    en, _ = rendered
    allowed_types = {"article", "book-chapter", "conference", "book"}
    allowed_authorship = {"first", "shared", "middle", "last", "corresponding"}

    assert en["publications"], "expected at least one publication"
    for pub in en["publications"]:
        assert set(pub.keys()) >= {"key", "title", "year", "type", "authorship", "authors", "venue"}
        assert pub["type"] in allowed_types
        assert pub["authorship"] in allowed_authorship
        assert isinstance(pub["authors"], list)
        assert isinstance(pub["year"], int)
        # raw bibtex dict should NOT be in the dump
        assert "raw" not in pub
        assert "doi" in pub  # optional value, but key is always serialized


def test_output_dir_default_matches_repo_layout():
    """OUTPUT_DIR constant points at web/src/data relative to the repo root."""
    assert OUTPUT_DIR.name == "data"
    assert OUTPUT_DIR.parent.name == "src"
    assert OUTPUT_DIR.parent.parent.name == "web"


def test_publications_aggregate_present(rendered):
    s = publication_summary(load_publications(CONTENT_DIR / "publications.bib"))
    en, de = rendered
    assert f"{s.peer_reviewed} peer-reviewed publications" in en["publications_aggregate"]["summary"]
    assert en["publications_aggregate"]["pointer"] == "Full list & metrics:"
    assert "begutachtete Publikationen" in de["publications_aggregate"]["summary"]
    assert de["publications_aggregate"]["pointer"] == "Vollständige Liste:"


def test_publication_doi_is_serialized():
    pub = Publication(
        key="x", title="T", year=2019, type="article", authorship="first",
        authors=("Lee, J.",), venue="Cancers", doi="10.3390/x", raw={"foo": "bar"},
    )
    d = _to_jsonable(pub)
    assert d["doi"] == "10.3390/x"
    assert "raw" not in d  # bibtex-internal field stays out of the web dump
