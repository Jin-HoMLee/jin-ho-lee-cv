"""Static-HTML guard for the Phase 15 splice-neoepitope write-up (issue #128).

AI crawlers do not execute JavaScript, so every crawler-critical string of the
article - title, section headings, the amplifier disclaimer, each figure's
static fallback, the Article JSON-LD, and the CV cross-link - must be in the
server-rendered HTML. Skip-guarded locally (needs a web build); the CI
`web-guard` job and `just web-guard` build web/dist first.
"""

from __future__ import annotations

import json
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
    # Strip the inline <script> block: its define:vars serialization repeats
    # TUMOR/NORMAL_SHARED/EXCLUSIVE as literal text, which would let the
    # assertions below pass via the (JS-only, never executed by a crawler)
    # script constant even if the crawler-visible fallback markup were wrong.
    figure_html = re.sub(r"<script.*?</script>", "", figure_html, flags=re.DOTALL)
    assert "tumor_exclusive" in figure_html
    assert "normal_shared" in figure_html
    # Both raw counts must be present with JS off (illustrative, labelled).
    assert "1,204" in figure_html  # illustrative tumor junctions
    assert "312" in figure_html  # illustrative tumor-exclusive after filtering


ILLUSTRATIVE_PEPTIDES = ["KLYQVEYAF", "SLLQHLIGL", "RTYGPVFMV", "AEFGQKLTV", "NQFPDVLLM"]


def test_binding_widget_fallback_is_a_ranked_table(html):
    assert 'data-figure="binding-score"' in html
    # Scope to the figure element itself and strip its inline <script>: a
    # script serializing content as literal text could let the assertions
    # below pass via JS-only text a crawler never executes, even if the
    # crawler-visible fallback markup were wrong (see test_junction_filter_
    # fallback_shows_sets above for the same pattern).
    match = re.search(r'<figure[^>]*data-figure="binding-score"[^>]*>.*?</figure>', html, re.DOTALL)
    assert match, "binding-score figure element not found in raw HTML"
    figure_html = re.sub(r"<script.*?</script>", "", match.group(0), flags=re.DOTALL)
    assert "illustrative" in figure_html.lower()
    for pep in ILLUSTRATIVE_PEPTIDES:
        assert pep in figure_html, f"illustrative peptide {pep!r} missing from raw HTML"


def _ldjson_blocks(html: str) -> list[str]:
    return re.findall(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', html, flags=re.S)


def test_article_jsonld_is_present_correct_and_escaped(html):
    article = None
    for raw in _ldjson_blocks(html):
        # Injection points escape '<' to <; a raw '<' means a lost escape.
        assert "<" not in raw, "inline JSON-LD carries a raw '<' (lost \\u003c escaping)"
        data = json.loads(raw)
        if isinstance(data, dict) and data.get("@type") in ("Article", "ScholarlyArticle"):
            article = data
    assert article is not None, "no Article/ScholarlyArticle JSON-LD on the write-up"
    assert article["headline"] == TITLE
    author = article["author"]
    name = author["name"] if isinstance(author, dict) else author
    assert name == "Jin-Ho Lee"
    assert article["isBasedOn"] == REPO_URL


WRITEUP_PATH = "/writeups/splice-neoepitopes/"


@pytest.mark.skipif(not INDEX_EN.exists(), reason="needs a built site")
def test_en_card_links_to_writeup():
    html = INDEX_EN.read_text(encoding="utf-8")
    assert WRITEUP_PATH in html
    assert "Read the write-up" in html


@pytest.mark.skipif(not INDEX_DE.exists(), reason="needs a built site")
def test_de_card_links_to_writeup_in_english():
    html = INDEX_DE.read_text(encoding="utf-8")
    assert WRITEUP_PATH in html
    assert "Read in English" in html


@pytest.mark.skipif(not WRITEUP.exists(), reason="needs a built site")
def test_writeup_is_in_sitemap():
    sitemaps = list((DIST).glob("sitemap*.xml"))
    assert sitemaps, "no sitemap emitted by the build"
    joined = "".join(p.read_text(encoding="utf-8") for p in sitemaps)
    assert "writeups/splice-neoepitopes" in joined, "write-up route missing from sitemap"
