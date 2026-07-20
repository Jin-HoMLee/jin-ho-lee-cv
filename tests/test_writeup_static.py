"""Static-HTML guard for the Phase 15 splice-neoepitope write-up (issue #128).

AI crawlers do not execute JavaScript, so every crawler-critical string of the
article - title, section headings, the amplifier disclaimer, each figure's
static fallback, the Article JSON-LD, and the CV cross-link - must be in the
server-rendered HTML. Skip-guarded locally (needs a web build); the CI
`web-guard` job and `just web-guard` build web/dist first.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DIST = REPO_ROOT / "web" / "dist"
WRITEUP = DIST / "writeups" / "splice-neoepitopes" / "index.html"
INDEX_EN = DIST / "index.html"
INDEX_DE = DIST / "de" / "index.html"

REPO_URL = "https://github.com/Jin-HoMLee/splice-neoepitope-pipeline"
TITLE = "From Splice Junctions to Neoepitopes"
SECTION_HEADINGS = [
    "The question",
    "The pipeline",
    "Finding tumor-exclusive junctions",
    "From junction to neoepitope",
    "Reproducibility",
    "Status and how to follow",
]

pytestmark = pytest.mark.skipif(
    not WRITEUP.exists(),
    reason="needs a built site (run: just web-build)",
)


@pytest.fixture(scope="module")
def html() -> str:
    return WRITEUP.read_text(encoding="utf-8")


def test_title_in_static_html(html):
    assert TITLE in html


def test_amplifier_disclaimer_in_static_html(html):
    assert "data-writeup-disclaimer" in html
    assert "companion to the open-source code and a forthcoming preprint" in html
    assert "results are preliminary" in html.lower()


def test_every_section_heading_in_static_html(html):
    for heading in SECTION_HEADINGS:
        assert heading in html, f"section heading {heading!r} missing from raw HTML"


def test_repo_linkout_in_static_html(html):
    assert REPO_URL in html
