"""Static-HTML facts guard (Phase 14, issue #113).

AI crawlers do not execute JavaScript (Vercel/MERJ, 500M fetches). Two properties:

  1. PUBLIC TIER PRESENT  - the core content/ facts are in the raw served HTML.
  2. DEEP TIER ABSENT     - the deliberately twin-exclusive master-cv/ overlay is not.

Property 2 is proven DYNAMICALLY against the synthetic master-cv.example/ overlay:
both the CI `web-guard` job and the `just web-guard` recipe export
MASTER_CV_DIR=master-cv.example for the render_web_data/render_jsonld steps before
building web/dist, so if any renderer on the web pipeline ever started honouring
the overlay, the example's sentinel strings (`Example-Lang`, `ExampleDB`, ...)
would land in content.*.json and then index.html, and
test_deep_tier_stays_off_the_public_surface below would go red. Verified live:
temporarily wiring a sentinel into scripts.render_web_data's output made this
test fail; reverting made it pass again (see the Phase 14 final-fixes report).
Outside `web-guard` (e.g. a bare `just web-build` with no MASTER_CV_DIR
override), this is inert - the renderers never read that env var at all -
which is exactly what test_web_import_boundary.py proves STATICALLY: the
web-facing modules (content_loader, render_web_data, render_jsonld) never
import - even transitively - the master-cv/ overlay loader in the first place.

Skip-guarded locally (needs a web build); the CI `web-guard` job builds web/dist first.
"""

from __future__ import annotations

import html
import json
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from scripts.bib_loader import load_publications

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = REPO_ROOT / "content"
EXAMPLE_OVERLAY = REPO_ROOT / "master-cv.example"
INDEX_EN = REPO_ROOT / "web" / "dist" / "index.html"
INDEX_DE = REPO_ROOT / "web" / "dist" / "de" / "index.html"
EXPERIENCE_ARCHIVE_EN = REPO_ROOT / "web" / "dist" / "experience" / "index.html"
EXPERIENCE_ARCHIVE_DE = REPO_ROOT / "web" / "dist" / "de" / "experience" / "index.html"
EDUCATION_ARCHIVE_EN = REPO_ROOT / "web" / "dist" / "education" / "index.html"
EDUCATION_ARCHIVE_DE = REPO_ROOT / "web" / "dist" / "de" / "education" / "index.html"

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


def test_jhl_identity_mark_is_static_and_bilingual():
    """The identity mark survives SSG and remains unambiguous without JS."""
    personal = _load("personal.yaml")
    legacy_mark = "J" + "L"
    for page in (INDEX_EN, INDEX_DE):
        rendered = page.read_text(encoding="utf-8")
        name = f"{personal['name']['given']} {personal['name']['family']}"
        assert f'aria-label="JHL — {name}"' in rendered
        assert ">JHL</a>" in rendered
        assert f">{legacy_mark}</a>" not in rendered

    favicon = (REPO_ROOT / "web" / "public" / "favicon.svg").read_text(encoding="utf-8")
    assert ">JHL</text>" in favicon
    assert f">{legacy_mark}</text>" not in favicon


def test_every_employer_in_static_html(html_en):
    for entry in _load("experience.yaml"):
        org = entry["org"]["name"]
        assert org in html_en, f"employer {org!r} is not in the raw HTML (JS-only?)"


def test_every_degree_and_institution_in_static_html(html_en):
    for entry in _load("education.yaml"):
        assert entry["institution"] in html_en
        assert entry["degree"]["en"] in html_en


def test_answer_block_is_front_loaded_in_static_html(html_en):
    """The concise liftable answer block must be server-rendered, not JS-injected."""
    block = yaml.load((CONTENT_DIR / "profile.en.yaml").read_text(encoding="utf-8"))["answer_block"]
    assert len(block) <= 180
    assert 'data-cv-field="answer-block"' in html_en
    assert block in html_en


def test_a_plus_identity_hero_contract_matches_pages_smoke(html_en):
    """The PR web guard must cover the fields asserted by the Pages smoke check."""
    for page in (html_en, INDEX_DE.read_text(encoding="utf-8")):
        assert 'data-cv-field="headline"' in page
        assert 'data-cv-field="answer-block"' in page
        for removed_field in ("tagline", "lead", "second"):
            assert f'data-cv-field="{removed_field}"' not in page


def test_opening_uses_original_portrait_and_skills_first_sidebar(html_en):
    assert 'src="/photo.jpg"' in html_en
    hero_source = (REPO_ROOT / "web" / "src" / "components" / "IdentityHero.astro").read_text(
        "utf-8"
    )
    assert "filter:grayscale(1) contrast(1.05)" in hero_source
    assert "From evidence to impact" in html_en
    assert "Von Evidenz zu Wirkung" in INDEX_DE.read_text(encoding="utf-8")
    assert 'id="profile"' not in html_en
    content_start = html_en.index('class="editorial-content"')
    sidebar_start = html_en.index("<aside", content_start)
    sidebar_end = html_en.index("</aside>", sidebar_start)
    sidebar = html_en[sidebar_start:sidebar_end]
    assert 'id="skills"' in sidebar
    assert sidebar.index('id="skills"') < sidebar.index('id="education"')


def test_selected_project_titles_in_static_html(html_en):
    for pid in _load("selected_projects.yaml")["bridge"]:
        title = yaml.load(
            (CONTENT_DIR / "projects" / f"{pid}.en.yaml").read_text(encoding="utf-8")
        )["title"]
        assert title in html_en, f"project {pid} title {title!r} is not in the raw HTML"


def test_publication_titles_in_static_html(html_en):
    """`PublicationsList.astro` renders every entry into the `data-cv-pub="full"`
    block (hidden by CSS/JS toggle, not omitted from the markup), so every
    cleaned title from the real loader must be in the raw HTML - verified by
    inspecting the component and grepping the built page before writing this
    assertion. Loading via scripts.bib_loader (not raw BibTeX) means this
    guards the actual LaTeX-cleaning the renderer depends on.

    Note: this is a raw substring check against unescaped titles. A title
    containing HTML-special characters (e.g. '&') is entity-escaped ('&amp;')
    in the visible publication list, so such a title would only satisfy this
    assertion via the inline ScholarlyArticle JSON-LD block (`"name": p.title`
    in scripts/render_jsonld.py - a legitimate, unescaped crawler surface in
    its own right), not the visible HTML. Acceptable as shipped; no current
    publication title hits this case.
    """
    for pub in load_publications(CONTENT_DIR / "publications.bib"):
        assert pub.title in html_en, (
            f"publication {pub.key} title {pub.title!r} is not in the raw HTML"
        )


def test_complete_public_archives_are_static_and_bilingual():
    history = _load("history.yaml")
    pages = {
        "en": (
            EXPERIENCE_ARCHIVE_EN.read_text(encoding="utf-8"),
            EDUCATION_ARCHIVE_EN.read_text(encoding="utf-8"),
        ),
        "de": (
            EXPERIENCE_ARCHIVE_DE.read_text(encoding="utf-8"),
            EDUCATION_ARCHIVE_DE.read_text(encoding="utf-8"),
        ),
    }
    assert sum(len(chapter["entries"]) for chapter in history["experience_chapters"]) == 22
    assert len(history["education"]) == 12
    for lang, (experience_html, education_html) in pages.items():
        experience_html = html.unescape(experience_html)
        education_html = html.unescape(education_html)
        for chapter in history["experience_chapters"]:
            for entry in chapter["entries"]:
                assert entry["role"][lang] in experience_html
                assert entry["org"][lang] in experience_html
        for entry in history["education"]:
            assert entry["degree"][lang] in education_html
            assert entry["institution"][lang] in education_html


def test_complete_archive_routes_are_in_sitemap():
    sitemap_index = REPO_ROOT / "web" / "dist" / "sitemap-index.xml"
    sitemap = sitemap_index.read_text(encoding="utf-8")
    assert "sitemap-0.xml" in sitemap
    route_map = (REPO_ROOT / "web" / "dist" / "sitemap-0.xml").read_text(encoding="utf-8")
    for route in ("archive", "education", "experience", "projects", "publications", "skills"):
        assert f"/{route}/" in route_map
        assert f"/de/{route}/" in route_map


def test_complete_archive_routes_have_og_images():
    og_dir = REPO_ROOT / "web" / "dist" / "og"
    for slug in (
        "archive-en",
        "archive-de",
        "education-all-en",
        "education-all-de",
        "experience-en",
        "experience-de",
        "projects-all-en",
        "projects-all-de",
        "publications-all-en",
        "publications-all-de",
        "skills-all-en",
        "skills-all-de",
    ):
        assert (og_dir / f"{slug}.png").is_file()


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
    return [v for v in values if v.lower().startswith("example") or v.lower() == "pseudocode"]


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
