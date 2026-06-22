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
