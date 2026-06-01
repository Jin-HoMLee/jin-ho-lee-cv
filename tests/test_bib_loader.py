"""Tests for scripts.bib_loader."""
from pathlib import Path

import pytest

from scripts.bib_loader import (
    AUTHORSHIP_VALUES,
    BIB_TYPES,
    _clean_tex,
    authorship_counts,
    load_publications,
)


BIB_PATH = Path(__file__).parent.parent / "content" / "publications.bib"


def test_loads_all_entries():
    pubs = load_publications(BIB_PATH)
    assert len(pubs) >= 15, f"expected 15+ entries, got {len(pubs)}"


def test_publications_have_required_fields():
    for pub in load_publications(BIB_PATH):
        assert pub.key
        assert pub.title
        assert pub.year >= 2017
        assert pub.year <= 2030
        assert pub.type in BIB_TYPES, f"unknown type {pub.type} on {pub.key}"
        assert pub.authorship in AUTHORSHIP_VALUES, (
            f"unknown authorship {pub.authorship} on {pub.key}"
        )


def test_real_bib_doi_presence():
    """The journal/chapter entries carry DOIs; conference talks + self-pub don't.

    Asserted as a floor (not an exact count) to stay robust as publications are
    added, mirroring test_loads_all_entries. load_publications() already raises
    on any malformed DOI, so this guards against DOIs being silently dropped.
    """
    pubs = load_publications(BIB_PATH)
    with_doi = [p for p in pubs if p.doi is not None]
    assert len(with_doi) >= 11, f"expected 11+ entries with DOI, got {len(with_doi)}"

    by_key = {p.key: p for p in pubs}
    for key in (
        "lee2021_degbs",
        "lee2019_conrad",
        "lee2018_dro",
        "lee2025_marketing_automation",
    ):
        assert by_key[key].doi is None, f"{key} should have no DOI"


def test_category_defaults_to_research_when_absent(tmp_path):
    bib = tmp_path / "nocat.bib"
    bib.write_text(
        "@article{x, author={Lee, J.}, title={T}, year={2019}, "
        "journal={J}, type={article}, authorship={first}}\n"
    )
    assert load_publications(bib)[0].category == "research"


def test_category_applied_parsed(tmp_path):
    bib = tmp_path / "applied.bib"
    bib.write_text(
        "@incollection{x, author={Lee, J.}, title={T}, year={2025}, "
        "booktitle={B}, type={book-chapter}, authorship={first}, category={applied}}\n"
    )
    assert load_publications(bib)[0].category == "applied"


def test_unknown_category_raises(tmp_path):
    bib = tmp_path / "badcat.bib"
    bib.write_text(
        "@article{x, author={Lee, J.}, title={T}, year={2019}, "
        "journal={J}, type={article}, authorship={first}, category={bogus}}\n"
    )
    with pytest.raises(ValueError, match="category"):
        load_publications(bib)


def test_publications_sorted_research_then_applied_then_year_desc():
    pubs = load_publications(BIB_PATH)
    first_applied = next(
        (i for i, p in enumerate(pubs) if p.category == "applied"), len(pubs)
    )
    assert all(p.category == "research" for p in pubs[:first_applied])
    assert all(p.category == "applied" for p in pubs[first_applied:])
    research_years = [p.year for p in pubs if p.category == "research"]
    applied_years = [p.year for p in pubs if p.category == "applied"]
    assert research_years == sorted(research_years, reverse=True)
    assert applied_years == sorted(applied_years, reverse=True)


def test_authorship_counts_sums_to_total():
    pubs = load_publications(BIB_PATH)
    counts = authorship_counts(pubs)
    assert sum(counts.values()) == len(pubs)


def test_missing_authorship_field_raises(tmp_path):
    """A bib entry without the custom 'authorship' field should fail loading."""
    bad = tmp_path / "missing_authorship.bib"
    bad.write_text(
        "@article{x, author={X}, title={T}, year={2020}, journal={J}, type={article}}\n"
    )
    with pytest.raises(ValueError, match="authorship"):
        load_publications(bad)


def test_doi_extracted_when_present(tmp_path):
    bib = tmp_path / "doi.bib"
    bib.write_text(
        "@article{x, author={Lee, J.}, title={T}, year={2019}, "
        "journal={Cancers}, type={article}, authorship={first}, "
        "doi={10.3390/cancers11121877}}\n"
    )
    assert load_publications(bib)[0].doi == "10.3390/cancers11121877"


def test_doi_is_none_when_absent(tmp_path):
    bib = tmp_path / "nodoi.bib"
    bib.write_text(
        "@article{x, author={Lee, J.}, title={T}, year={2019}, "
        "journal={Cancers}, type={article}, authorship={first}}\n"
    )
    assert load_publications(bib)[0].doi is None


def test_doi_empty_or_whitespace_field_is_none(tmp_path):
    """An empty or whitespace-only doi field normalizes to None, not a ValueError."""
    bib = tmp_path / "emptydoi.bib"
    bib.write_text(
        "@article{a, author={Lee, J.}, title={A}, year={2019}, journal={J}, "
        "type={article}, authorship={first}, doi={}}\n"
        "@article{b, author={Lee, J.}, title={B}, year={2018}, journal={J}, "
        "type={article}, authorship={first}, doi={   }}\n"
    )
    by_key = {p.key: p for p in load_publications(bib)}
    assert by_key["a"].doi is None
    assert by_key["b"].doi is None


def test_doi_normalizes_resolver_url_and_label(tmp_path):
    bib = tmp_path / "urls.bib"
    bib.write_text(
        "@article{a, author={Lee, J.}, title={A}, year={2019}, journal={J}, "
        "type={article}, authorship={first}, doi={https://doi.org/10.3390/aaa}}\n"
        "@article{b, author={Lee, J.}, title={B}, year={2018}, journal={J}, "
        "type={article}, authorship={first}, doi={doi:10.1000/bbb}}\n"
        "@article{c, author={Lee, J.}, title={C}, year={2017}, journal={J}, "
        "type={article}, authorship={first}, doi={DOI:10.1000/ccc}}\n"
        "@article{d, author={Lee, J.}, title={D}, year={2016}, journal={J}, "
        "type={article}, authorship={first}, doi={http://doi.org/10.3390/ddd}}\n"
        "@article{e, author={Lee, J.}, title={E}, year={2015}, journal={J}, "
        "type={article}, authorship={first}, doi={HTTP://DOI.ORG/10.3390/eee}}\n"
    )
    by_key = {p.key: p for p in load_publications(bib)}
    assert by_key["a"].doi == "10.3390/aaa"  # https:// resolver
    assert by_key["b"].doi == "10.1000/bbb"  # lowercase doi: label
    assert by_key["c"].doi == "10.1000/ccc"  # uppercase DOI: label
    assert by_key["d"].doi == "10.3390/ddd"  # http:// resolver
    assert by_key["e"].doi == "10.3390/eee"  # mixed-case HTTP://DOI.ORG/


def test_malformed_doi_raises(tmp_path):
    bib = tmp_path / "bad.bib"
    bib.write_text(
        "@article{x, author={Lee, J.}, title={T}, year={2019}, journal={J}, "
        "type={article}, authorship={first}, doi={not-a-doi}}\n"
    )
    with pytest.raises(ValueError, match="doi"):
        load_publications(bib)


# --- _clean_tex: BibTeX brace / LaTeX accent normalization (issue #41) ---


def test_clean_tex_strips_protective_braces():
    assert _clean_tex(r"{3D} {DNA} {FISH}") == "3D DNA FISH"


def test_clean_tex_preserves_at_inside_braces():
    # @{DeutschlandCard}: braces protect the case; the @ is part of the title.
    assert _clean_tex(r"@{DeutschlandCard}") == "@DeutschlandCard"


def test_clean_tex_decodes_umlaut():
    assert _clean_tex(r"f\"ur") == "für"


def test_clean_tex_decodes_caron_and_acute():
    # The caron form \v{c} is the one the web cleanTex misses.
    assert _clean_tex(r"radia\v{c}n\'i") == "radiační"


def test_clean_tex_decodes_braced_accent_form():
    assert _clean_tex(r"f\"{u}r") == "für"


def test_clean_tex_decodes_latex_special_escape():
    assert _clean_tex(r"Selection \& Implementation") == "Selection & Implementation"


def test_clean_tex_leaves_plain_text_untouched():
    assert _clean_tex("Cancers") == "Cancers"
    assert _clean_tex("T") == "T"


@pytest.mark.parametrize(
    "text",
    [
        "R&D",  # bare ampersand is not an escape
        "50% increase",  # bare percent
        "$100 budget",  # bare dollar
        "$E=mc^2$",  # math mode: \^ needs a letter, never fires on digits
        "Fig.~3",  # LaTeX NBSP tilde without a following accent letter
    ],
)
def test_clean_tex_preserves_unescaped_specials(text):
    """Only backslash-escaped forms decode; bare specials/math/NBSP pass through."""
    assert _clean_tex(text) == text


@pytest.mark.parametrize(
    "raw",
    [
        r"{3D} {DNA} {FISH}",
        r"f\"ur",
        r"radia\v{c}n\'i",
        r"f\"{u}r",
        r"Selection \& Implementation",
        "already clean",
    ],
)
def test_clean_tex_is_idempotent(raw):
    once = _clean_tex(raw)
    assert _clean_tex(once) == once


def test_real_bib_has_no_latex_residue():
    """Every user-facing field of the live bib parses free of braces/backslashes.

    This is the guard: any future un-decoded accent or brace fails the build
    instead of leaking into person.jsonld / resume.json / cv-*.txt / web JSON.
    """
    for pub in load_publications(BIB_PATH):
        fields = {"title": pub.title}
        if pub.venue is not None:
            fields["venue"] = pub.venue
        for i, author in enumerate(pub.authors):
            fields[f"author[{i}]"] = author
        for name, value in fields.items():
            assert not (set(value) & set("{}\\")), (
                f"{pub.key}.{name} has LaTeX residue: {value!r}"
            )
