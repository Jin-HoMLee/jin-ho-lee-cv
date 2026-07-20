"""Static-HTML guard for the Phase 15 splice-neoepitope write-up (issue #128).

AI crawlers do not execute JavaScript, so every crawler-critical string of the
article - title, section headings, the amplifier disclaimer, each figure's
static fallback, the Article JSON-LD, and the CV cross-link - must be in the
server-rendered HTML. Skip-guarded locally (needs a web build); the CI
`web-guard` job and `just web-guard` build web/dist first.
"""

from __future__ import annotations

import re
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

PIPELINE_STEPS = [
    "RNA-Seq FASTQ",
    "Alignment (HISAT2 / STAR)",
    "Junction extraction",
    "Tumor-vs-normal filtering (GENCODE)",
    "Translation to 9-mers",
    "HLA typing (OptiType)",
    "MHC-I binding (MHCflurry)",
    "TCR-pMHC structural validation",
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
        pattern = rf"<h2[^>]*>{re.escape(heading)}</h2>"
        assert re.search(pattern, html), (
            f"section heading {heading!r} not found as an <h2> element in raw HTML "
            f"(a substring match elsewhere in prose does not count)"
        )


def test_repo_linkout_in_static_html(html):
    assert REPO_URL in html


def test_pipeline_explorer_fallback_lists_every_step(html):
    assert 'data-figure="pipeline-explorer"' in html
    for step in PIPELINE_STEPS:
        assert step in html, f"pipeline step {step!r} missing from raw HTML (JS-only?)"


def test_junction_filter_fallback_shows_sets(html):
    assert 'data-figure="junction-filter"' in html
    # Scope to the figure element itself: unrelated CSS elsewhere on the page
    # (e.g. "0.3125rem" in the twin-widget styles baked into every page) can
    # contain "312" as an accidental substring, which would let a whole-page
    # substring check pass even if this figure's own count were wrong.
    match = re.search(
        r'<figure[^>]*data-figure="junction-filter"[^>]*>.*?</figure>', html, re.DOTALL
    )
    assert match, "junction-filter figure element not found in raw HTML"
    figure_html = match.group(0)
    assert "tumor_exclusive" in figure_html
    assert "normal_shared" in figure_html
    # Both raw counts must be present with JS off (illustrative, labelled).
    assert "1,204" in figure_html  # illustrative tumor junctions
    assert "312" in figure_html  # illustrative tumor-exclusive after filtering
