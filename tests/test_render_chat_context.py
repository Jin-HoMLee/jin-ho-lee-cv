"""Pytest assertions for the digital-twin chat-context compiler."""

from __future__ import annotations

from pathlib import Path

from scripts.bib_loader import load_publications
from scripts.content_loader import load_content
from scripts.langstring import resolve_langstrings
from scripts.render_chat_context import render

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = REPO_ROOT / "content"


def _content():
    return resolve_langstrings(load_content(CONTENT_DIR, lang="en"), lang="en")


def test_starts_with_identity_header():
    c = _content()
    name = f"{c['personal']['name']['given']} {c['personal']['name']['family']}"
    out = render()
    assert out.startswith(f"# {name} — {c['personal']['headline']}\n")
    assert c["profile"]["tagline"] in out


def test_includes_full_profile_and_skills():
    c = _content()
    out = render()
    for para in c["profile"]["paragraphs"]:
        assert para in out
    assert "## Skills" in out
    for category in c["skills"]["categories"]:
        for group in category["groups"]:
            assert group["label"] in out
            for item in group["items"]:
                assert item in out


def test_includes_experience_and_education():
    c = _content()
    out = render()
    assert "## Experience" in out
    first = c["experience"][0]
    assert first["role"] in out
    assert first["org"]["name"] in out
    # bullets are {en, de, refs} mixed dicts — the EN text must render verbatim.
    for bullet in first["bullets"]:
        assert bullet["en"] in out
    assert "## Education" in out
    first_edu = c["education"][0]
    assert first_edu["degree"] in out
    assert first_edu["institution"] in out
    assert str(first_edu["year"]) in out


def test_includes_projects_and_publications():
    c = _content()
    out = render()
    assert "## Selected Projects" in out
    for p in c["selected_projects"]:
        assert p["title"] in out
        assert p["summary"] in out
    assert "## Publications" in out
    pubs = load_publications(CONTENT_DIR / "publications.bib")
    assert pubs, "expected at least one publication"
    for pub in pubs:
        assert pub.title in out


def test_no_pii_keywords_in_context():
    out = render().lower()
    assert "phone" not in out
    for kw in ("strasse", "straße", "hausnummer", "postal_code"):
        assert kw not in out


def test_render_never_reads_content_private(tmp_path, monkeypatch):
    secret = "SYNTHETIC-SECRET-0049-DO-NOT-LEAK"
    private = tmp_path / "content.private"
    private.mkdir()
    (private / "private.yaml").write_text(
        f"phone: '{secret}'\naddress:\n  street: '{secret}'\n", encoding="utf-8"
    )
    out = render()
    assert secret not in out
