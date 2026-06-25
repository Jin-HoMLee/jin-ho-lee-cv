"""The shared CV + master-cv union helper."""

from __future__ import annotations

from pathlib import Path

from scripts.bib_loader import load_publications
from scripts.content_loader import load_content
from scripts.langstring import resolve_langstrings
from scripts.master_cv_loader import MasterCV
from scripts.profile_union import full_profile

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = REPO_ROOT / "content"


def _facts():
    content = resolve_langstrings(load_content(CONTENT_DIR, lang="en"), lang="en")
    pubs = load_publications(CONTENT_DIR / "publications.bib")
    return content, pubs


def test_absent_overlay_is_cv_only():
    content, pubs = _facts()
    out = full_profile(content, pubs, None)
    assert "## Profile" in out and "## Publications" in out
    assert "master record" not in out  # no master-cv sections


def test_present_overlay_appends_master_sections():
    content, pubs = _facts()
    mcv = MasterCV(
        timeline=[
            {
                "id": "imp-vienna-2019",
                "type": "research",
                "title": "Doctoral Researcher",
                "org": "IMP",
                "start": "2019-08",
                "end": "2019-10",
                "summary": "Structural biology work.",
                "tags": ["structural biology"],
            }
        ],
        inventory={"programming": ["Python", "Perl"]},
        narrative={"career-story": "# Career story\n\nThe throughline."},
    )
    out = full_profile(content, pubs, mcv)
    assert "## Full Timeline (master record)" in out
    assert "Doctoral Researcher" in out and "Structural biology work." in out
    assert "## Full Skill & Domain Inventory (master record)" in out
    assert "Perl" in out
    assert "## Personal Narrative (master record)" in out
    assert "The throughline." in out


def test_empty_overlay_adds_no_sections():
    content, pubs = _facts()
    mcv = MasterCV(timeline=[], inventory={}, narrative={})
    assert full_profile(content, pubs, mcv) == full_profile(content, pubs, None)


def test_timeline_renders_extra_type_specific_fields():
    """Type-specific extras (thesis, field, issuer, status, …) must reach the
    output — the schema/example advertise them, so the renderer must not drop them."""
    content, pubs = _facts()
    mcv = MasterCV(
        timeline=[
            {
                "id": "msc",
                "type": "education",
                "title": "M.Sc. Molecular Biotechnology",
                "field": "Biophysical Chemistry",
                "thesis": "A Thesis Title",
                "summary": "Degree summary.",
            },
            {
                "id": "cert",
                "type": "certificate",
                "title": "Cloud Cert",
                "issuer": "Some Issuer",
                "status": "in-progress",
            },
        ],
        inventory={},
        narrative={},
    )
    out = full_profile(content, pubs, mcv)
    assert "Field: Biophysical Chemistry" in out
    assert "Thesis: A Thesis Title" in out
    assert "Issuer: Some Issuer" in out
    assert "Status: in-progress" in out


def test_timeline_extra_fields_skip_none_and_collections():
    """None values and list/dict extras must not produce junk lines (tags render
    via their own line; id/type are structural, not data lines)."""
    content, pubs = _facts()
    mcv = MasterCV(
        timeline=[
            {
                "id": "x",
                "type": "research",
                "title": "T",
                "end": None,
                "tags": ["a", "b"],
                "extra_list": ["should", "not", "render", "as", "kv"],
            }
        ],
        inventory={},
        narrative={},
    )
    out = full_profile(content, pubs, mcv)
    assert "Tags: a, b" in out
    assert "End:" not in out  # None skipped
    assert "Extra list:" not in out  # collections skipped
    assert "Id: x" not in out and "Type: research" not in out  # structural keys


def test_present_opinions_appends_section():
    content, pubs = _facts()
    mcv = MasterCV(
        timeline=[],
        inventory={},
        narrative={},
        opinions="# How I think\n\nI value reproducibility above novelty.",
    )
    out = full_profile(content, pubs, mcv)
    assert "## Opinions & Technical Taste (master record)" in out
    assert "I value reproducibility above novelty." in out


def test_absent_opinions_adds_no_section():
    content, pubs = _facts()
    mcv = MasterCV(timeline=[], inventory={}, narrative={})  # opinions defaults None
    out = full_profile(content, pubs, mcv)
    assert "Opinions & Technical Taste" not in out
