"""Pytest assertions for the plain-text renderer."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from scripts.bib_loader import Publication, load_publications
from scripts.publications import publication_summary
from scripts.render_text import _publications as render_text_publications
from scripts.render_text import render


REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def en_text() -> str:
    return render(lang="en")


@pytest.fixture(scope="module")
def de_text() -> str:
    return render(lang="de")


def test_en_and_de_differ(en_text, de_text):
    """Sanity: the two outputs are not byte-identical (something localised differently)."""
    assert en_text != de_text


def test_section_headers_present_en(en_text):
    for section in (
        "PROFILE",
        "EXPERIENCE",
        "EDUCATION",
        "SKILLS",
        "LANGUAGES",
        "VOLUNTEER",
        "PUBLICATIONS",
    ):
        assert section in en_text, f"missing section header: {section}"


def test_section_headers_present_de(de_text):
    # uppercase translations from labels.yaml
    for section in (
        "PROFIL",
        "BERUFSERFAHRUNG",
        "AUSBILDUNG",
        "KENNTNISSE",
        "SPRACHEN",
        "EHRENAMTLICH",
        "PUBLIKATIONEN",
    ):
        assert section in de_text, f"missing section header: {section}"


def test_no_markdown_chars(en_text, de_text):
    for body in (en_text, de_text):
        for forbidden in ("**", "__", "`", "[", "]("):
            assert forbidden not in body, f"markdown char in plain text: {forbidden!r}"


def test_email_present(en_text):
    assert "@" in en_text


def test_phone_excluded_when_public(en_text, de_text):
    """`load_content` is hard-coded to private_path=None — no phone."""
    for body in (en_text, de_text):
        assert not re.search(r"\+\d{1,3}[\s\d]{6,}", body), "looks like a phone number"


def test_section_divider_is_80_eq(en_text):
    assert "=" * 80 in en_text


def test_no_trailing_whitespace(en_text, de_text):
    for body in (en_text, de_text):
        for i, line in enumerate(body.splitlines(), start=1):
            assert line == line.rstrip(), f"trailing whitespace on line {i}"


def test_pii_never_reaches_main_output(tmp_path, private_leak_check):
    """Even if a private overlay exists, the main() CLI must not include it."""
    from scripts.render_text import main

    private_leak_check(
        lambda out: main(["--lang", "en", "--output", str(out)]), tmp_path / "cv-en.txt"
    )


def test_header_url_uses_pages_base(en_text):
    from scripts.config import PAGES_BASE_URL

    assert PAGES_BASE_URL in en_text, f"PAGES_BASE_URL ({PAGES_BASE_URL!r}) missing from header"


def _pub(**over) -> Publication:
    base = dict(
        key="x",
        title="T",
        year=2019,
        type="article",
        authorship="first",
        authors=("Lee, J.",),
        venue="Cancers",
        doi=None,
        raw={},
    )
    base.update(over)
    return Publication(**base)


def test_publications_include_doi_url_line():
    out = render_text_publications([_pub(doi="10.3390/cancers11121877")])
    assert "  https://doi.org/10.3390/cancers11121877" in out


def test_publications_omit_doi_line_when_absent():
    out = render_text_publications([_pub(doi=None)])
    assert "https://doi.org/" not in out


def test_education_includes_bsc_major():
    out = render("en")
    assert "Bioinformatics" in out


def test_education_includes_msc_major():
    out = render("en")
    assert "Biophysical Chemistry" in out


def test_education_renders_thesis_titles():
    """#93: thesis titles must actually reach the output (not just sit in the schema)."""
    out = render("en")
    assert "HLA Typing from Sequencing Data for Personalized Cancer Immunotherapy" in out
    assert "Single Molecule Localization Microscopy of Nanoprobes" in out
    assert "Thesis:" in out


def test_awards_section_renders():
    out = render("en")
    assert "AWARDS & CERTIFICATIONS" in out
    assert "DAAD PROMOS Scholarship" in out
    assert "DeGBS Poster Award" in out


def test_awards_section_includes_gcp_certification():
    """#93: the completed Google Cloud cert is folded into Awards & Certifications."""
    out = render("en")
    assert "Google Cloud Certified - Associate Cloud Engineer" in out


def test_awards_section_includes_hackathon_award():
    """#93: the 2018 hackathon award is present in Awards & Certifications."""
    out = render("en")
    assert "“Most Patient-Centric Solution” Award" in out
    assert "{Life Science} meets IT Hackathon, Mannheim" in out


def test_awards_section_renders_de():
    out = render("de")
    assert "AUSZEICHNUNGEN & ZERTIFIKATE" in out


CONTENT_DIR = REPO_ROOT / "content"


def test_publications_aggregate_for_bridge_en():
    s = publication_summary(load_publications(CONTENT_DIR / "publications.bib"))
    text = render(lang="en", target="bridge")
    assert f"{s.peer_reviewed} peer-reviewed publications" in text
    assert "Full list & metrics: https://orcid.org/0009-0001-8784-1771" in text


def test_publications_aggregate_for_bridge_de():
    text = render(lang="de", target="bridge")
    assert "begutachtete Publikationen" in text
    assert "Vollständige Liste: https://orcid.org/0009-0001-8784-1771" in text


def test_publications_full_list_for_comp_bio():
    pubs = load_publications(CONTENT_DIR / "publications.bib")
    middle = next(p for p in pubs if p.authorship == "middle")
    full = render(lang="en", target="comp-bio")
    bridge = render(lang="en", target="bridge")
    assert middle.title in full  # verbatim list present
    assert middle.title not in bridge  # aggregate omits per-paper titles


# --- #42: period-end edge cases on the extracted formatter ---


def test_format_period_dated():
    from scripts.render_text import _format_period

    assert _format_period({"start": "2024-05", "end": "2025-07"}, "en") == "2024-05 to 2025-07"


def test_format_period_null_end_en():
    from scripts.render_text import _format_period

    assert _format_period({"start": "2014-04", "end": None}, "en") == "2014-04 to present"


def test_format_period_absent_end_de():
    from scripts.render_text import _format_period

    assert _format_period({"start": "2014-04"}, "de") == "2014-04 bis heute"
