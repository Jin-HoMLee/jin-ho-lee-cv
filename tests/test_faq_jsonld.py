"""The built site must carry a FAQPage JSON-LD block matching the visible FAQ (issue #113).

Skip-guarded locally (needs a web build); the CI `web-guard` job builds web/dist first.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from ruamel.yaml import YAML

REPO_ROOT = Path(__file__).resolve().parent.parent
PAGES = {
    "en": REPO_ROOT / "web" / "dist" / "index.html",
    "de": REPO_ROOT / "web" / "dist" / "de" / "index.html",
}

pytestmark = pytest.mark.skipif(
    not all(p.exists() for p in PAGES.values()),
    reason="needs a built site (run: just web-build)",
)


def _faq_page_block(html: str) -> dict:
    """Extract the single ld+json script whose payload is a FAQPage."""
    for raw in re.findall(
        r'<script type="application/ld\+json"[^>]*>(.*?)</script>', html, flags=re.S
    ):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("@type") == "FAQPage":
            return data
    raise AssertionError("no FAQPage JSON-LD block found in the page")


@pytest.fixture(scope="module")
def faq_yaml() -> dict:
    return YAML(typ="safe").load((REPO_ROOT / "content" / "faq.yaml").read_text(encoding="utf-8"))


@pytest.mark.parametrize("lang", ["en", "de"])
def test_faq_page_jsonld_matches_content(lang, faq_yaml):
    html = PAGES[lang].read_text(encoding="utf-8")
    block = _faq_page_block(html)

    assert block["@context"] == "https://schema.org"
    questions = block["mainEntity"]
    expected = faq_yaml["faqs"]
    assert len(questions) == len(expected)

    for q, source in zip(questions, expected):
        assert q["@type"] == "Question"
        assert q["name"] == source["question"][lang]
        assert q["acceptedAnswer"]["@type"] == "Answer"
        assert q["acceptedAnswer"]["text"] == source["answer"][lang]


@pytest.mark.parametrize("lang", ["en", "de"])
def test_faq_text_is_in_static_html(lang, faq_yaml):
    """The visible FAQ must be in the HTML itself, not injected by JS - crawlers do not run JS."""
    html = PAGES[lang].read_text(encoding="utf-8")
    assert "data-faq-section" in html
    for entry in faq_yaml["faqs"]:
        assert entry["question"][lang] in html, f"FAQ question {entry['id']} missing from HTML"
        assert entry["answer"][lang] in html, f"FAQ answer {entry['id']} missing from HTML"


@pytest.mark.parametrize("lang", ["en", "de"])
def test_inline_jsonld_escapes_angle_brackets(lang):
    """No inline ld+json block may contain a raw '<'.

    Both JSON-LD injection points (FaqSection's FAQPage, BaseLayout's Person graph)
    inline content-derived strings via set:html. A '</script>' substring in any of
    them would close the tag early and let the rest parse as markup. Both escape '<'
    to \\u003c, so a raw '<' inside a block means an injection point lost its escaping.
    Content-independent: it holds no matter what the FAQ or the publications say.
    """
    html = PAGES[lang].read_text(encoding="utf-8")
    blocks = re.findall(
        r'<script type="application/ld\+json"[^>]*>(.*?)</script>', html, flags=re.S
    )
    assert blocks, "expected inline ld+json blocks in the page"
    for raw in blocks:
        assert "<" not in raw, (
            "an inline JSON-LD block carries a raw '<' - the set:html injection point "
            "lost its \\u003c escaping and is open to a </script> breakout"
        )
        json.loads(raw)  # escaping must not have broken the JSON
