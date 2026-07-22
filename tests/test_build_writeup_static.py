"""Static-HTML guard for the 'Ask my CV' build write-up (issue #140).

AI crawlers do not execute JavaScript, so the crawler-critical strings of the
article - title, every section heading, the twin invitation, the BlogPosting
JSON-LD, and the footer surfacing on both index languages - must be in the
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
WRITEUP = DIST / "writeups" / "ask-my-cv" / "index.html"
INDEX_EN = DIST / "index.html"
INDEX_DE = DIST / "de" / "index.html"

REPO_URL = "https://github.com/Jin-HoMLee/jin-ho-lee-cv"
TITLE = "Ask my CV"
SECTION_HEADINGS = [
    "Don't read my CV. Ask it.",
    "One source of truth, many renderers",
    "The twin: full context, not retrieval",
    "Running an LLM for free, reliably",
    "Guardrails, and keeping PII out",
    "Built by directing an agent",
    "What it cost, and where to look",
]
WRITEUP_PATH = "/writeups/ask-my-cv/"

pytestmark = pytest.mark.skipif(
    not WRITEUP.exists(),
    reason="needs a built site (run: just web-build)",
)


@pytest.fixture(scope="module")
def html() -> str:
    return WRITEUP.read_text(encoding="utf-8")


def test_title_in_static_html(html):
    assert TITLE in html


def test_every_section_heading_in_static_html(html):
    for heading in SECTION_HEADINGS:
        pattern = rf"<h2[^>]*>{re.escape(heading)}</h2>"
        assert re.search(pattern, html), (
            f"section heading {heading!r} not found as an <h2> element in raw HTML"
        )


def test_twin_invitation_in_static_html(html):
    # The whole point of the post: a live, crawler-visible invitation to ask the twin.
    assert "ask it something" in html.lower()


def test_repo_linkout_in_static_html(html):
    assert REPO_URL in html


def _ldjson_blocks(html: str) -> list[str]:
    return re.findall(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', html, flags=re.S)


def test_blogposting_jsonld_is_present_correct_and_escaped(html):
    article = None
    for raw in _ldjson_blocks(html):
        assert "<" not in raw, "inline JSON-LD carries a raw '<' (lost \\u003c escaping)"
        data = json.loads(raw)
        if isinstance(data, dict) and data.get("@type") == "BlogPosting":
            article = data
    assert article is not None, "no BlogPosting JSON-LD on the build write-up"
    assert article["headline"] == TITLE
    author = article["author"]
    name = author["name"] if isinstance(author, dict) else author
    assert name == "Jin-Ho Lee"
    assert article["isBasedOn"] == REPO_URL


@pytest.mark.skipif(not INDEX_EN.exists(), reason="needs a built site")
def test_en_footer_links_to_build_writeup():
    html = INDEX_EN.read_text(encoding="utf-8")
    assert WRITEUP_PATH in html
    assert "How this site was built" in html


@pytest.mark.skipif(not INDEX_DE.exists(), reason="needs a built site")
def test_de_footer_links_to_build_writeup_in_english():
    html = INDEX_DE.read_text(encoding="utf-8")
    assert WRITEUP_PATH in html
    assert "Read in English" in html


@pytest.mark.skipif(not WRITEUP.exists(), reason="needs a built site")
def test_build_writeup_is_in_sitemap():
    sitemaps = list(DIST.glob("sitemap*.xml"))
    assert sitemaps, "no sitemap emitted by the build"
    joined = "".join(p.read_text(encoding="utf-8") for p in sitemaps)
    assert "writeups/ask-my-cv" in joined, "build write-up route missing from sitemap"
