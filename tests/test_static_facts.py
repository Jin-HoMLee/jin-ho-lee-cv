"""Static-HTML facts guard (Phase 14, issue #113).

AI crawlers do not execute JavaScript (Vercel/MERJ, 500M fetches). Two properties:

  1. PUBLIC TIER PRESENT  - the core content/ facts are in the raw served HTML.
  2. DEEP TIER ABSENT     - the deliberately twin-exclusive master-cv/ overlay is not.

Property 2 is proven against the synthetic master-cv.example/ overlay: the web
renderer must ignore MASTER_CV_DIR entirely, so pointing it at the example and
re-rendering must not put any overlay-only string on the public surface.

Skip-guarded locally (needs a web build); the CI `web-guard` job builds web/dist first.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from ruamel.yaml import YAML

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = REPO_ROOT / "content"
EXAMPLE_OVERLAY = REPO_ROOT / "master-cv.example"
INDEX_EN = REPO_ROOT / "web" / "dist" / "index.html"
INDEX_DE = REPO_ROOT / "web" / "dist" / "de" / "index.html"

pytestmark = pytest.mark.skipif(
    not (INDEX_EN.exists() and INDEX_DE.exists()),
    reason="needs a built site (run: just web-build)",
)

yaml = YAML(typ="safe")


def _load(name: str):
    return yaml.load((CONTENT_DIR / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def html_en() -> str:
    return INDEX_EN.read_text(encoding="utf-8")


def test_name_and_headline_in_static_html(html_en):
    personal = _load("personal.yaml")
    assert f"{personal['name']['given']} {personal['name']['family']}" in html_en
    assert personal["headline"]["en"] in html_en


def test_every_employer_in_static_html(html_en):
    for entry in _load("experience.yaml"):
        org = entry["org"]["name"]
        assert org in html_en, f"employer {org!r} is not in the raw HTML (JS-only?)"


def test_every_degree_and_institution_in_static_html(html_en):
    for entry in _load("education.yaml"):
        assert entry["institution"] in html_en
        assert entry["degree"]["en"] in html_en


def test_answer_block_is_front_loaded_in_static_html(html_en):
    """The liftable answer block must be server-rendered, not JS-injected."""
    block = yaml.load((CONTENT_DIR / "profile.en.yaml").read_text(encoding="utf-8"))["answer_block"]
    assert 'data-cv-field="answer-block"' in html_en
    assert block in html_en


def test_selected_project_titles_in_static_html(html_en):
    for pid in _load("selected_projects.yaml")["bridge"]:
        title = yaml.load(
            (CONTENT_DIR / "projects" / f"{pid}.en.yaml").read_text(encoding="utf-8")
        )["title"]
        assert title in html_en, f"project {pid} title {title!r} is not in the raw HTML"


def test_person_jsonld_is_served_and_parses(html_en):
    """The Person graph must be inline in the page, not fetched at runtime."""
    assert "application/ld+json" in html_en
    jsonld = json.loads((REPO_ROOT / "web" / "public" / "person.jsonld").read_text("utf-8"))
    person = next(n for n in jsonld["@graph"] if n["@type"] == "Person")
    assert person["sameAs"], "Person.sameAs must carry the external entity anchors"


def _overlay_sentinels() -> list[str]:
    """Distinctive strings that exist ONLY in the synthetic overlay, never in content/."""
    inventory = yaml.load((EXAMPLE_OVERLAY / "inventory.yaml").read_text(encoding="utf-8"))
    values = [v for values in inventory.values() for v in values]
    return [v for v in values if v.startswith("Example") or v == "Pseudocode"]


@pytest.mark.parametrize("page", [INDEX_EN, INDEX_DE], ids=["en", "de"])
def test_deep_tier_stays_off_the_public_surface(page):
    """master-cv/ is twin-exclusive by design - none of it may reach the built site."""
    html = page.read_text(encoding="utf-8")
    sentinels = _overlay_sentinels()
    assert sentinels, "the example overlay yielded no sentinels; the fixture changed"
    for sentinel in sentinels:
        assert sentinel not in html, (
            f"overlay-only string {sentinel!r} reached the public site - "
            "the deep tier must stay twin-exclusive"
        )
