"""Tests for the PDF publications section (issue #43)."""
import shutil
import subprocess
import sys

import pytest

from pdf.build import prepare_data, select_publications
from scripts.bib_loader import Publication, load_publications


def _pub(authorship, key="k", title="T", authors=("Lee, J.",)):
    """Minimal Publication record for exercising select_publications()."""
    return Publication(
        key=key,
        title=title,
        year=2020,
        type="article",
        authorship=authorship,
        authors=authors,
        venue="V",
        doi=None,
        raw={},
        category="research",
    )


def test_select_publications_comp_bio_returns_all_unselected():
    pubs = [_pub("first"), _pub("shared"), _pub("middle")]
    selected, is_selected = select_publications(pubs, "comp-bio")
    assert [p.authorship for p in selected] == ["first", "shared", "middle"]
    assert is_selected is False


def test_select_publications_bridge_keeps_first_and_shared_in_order():
    pubs = [_pub("first", key="a"), _pub("middle", key="b"), _pub("shared", key="c")]
    selected, is_selected = select_publications(pubs, "bridge")
    assert [p.key for p in selected] == ["a", "c"]  # middle dropped, order preserved
    assert is_selected is True


def test_select_publications_ds_ml_keeps_first_and_shared():
    pubs = [_pub("first"), _pub("middle"), _pub("shared")]
    selected, is_selected = select_publications(pubs, "ds-ml")
    assert [p.authorship for p in selected] == ["first", "shared"]
    assert is_selected is True


def test_prepare_data_bridge_selects_first_and_shared_with_selected_heading(content_dir):
    # Assert the subset equals the live bib's first+shared entries (by key, in
    # order) rather than a hardcoded count — resilient to bib edits.
    all_pubs = load_publications(content_dir / "publications.bib")
    expected_keys = [p.key for p in all_pubs if p.authorship in ("first", "shared")]
    result = prepare_data(content_dir, private_path=None, lang="en", target="bridge")
    assert [p["key"] for p in result["publications"]] == expected_keys
    assert result["publications_heading"] == "Publications (selected)"


def test_prepare_data_comp_bio_selects_all_with_plain_heading(content_dir):
    all_pubs = load_publications(content_dir / "publications.bib")
    result = prepare_data(content_dir, private_path=None, lang="en", target="comp-bio")
    assert [p["key"] for p in result["publications"]] == [p.key for p in all_pubs]
    assert result["publications_heading"] == "Publications"


def test_prepare_data_ds_ml_selects_first_and_shared(content_dir):
    all_pubs = load_publications(content_dir / "publications.bib")
    expected_keys = [p.key for p in all_pubs if p.authorship in ("first", "shared")]
    result = prepare_data(content_dir, private_path=None, lang="en", target="ds-ml")
    assert [p["key"] for p in result["publications"]] == expected_keys
    assert result["publications_heading"] == "Publications (selected)"


def test_prepare_data_publications_heading_localized_de(content_dir):
    bridge = prepare_data(content_dir, private_path=None, lang="de", target="bridge")
    comp = prepare_data(content_dir, private_path=None, lang="de", target="comp-bio")
    assert bridge["publications_heading"] == "Publikationen (ausgewählte)"
    assert comp["publications_heading"] == "Publikationen"


def test_prepare_data_publication_entries_have_render_fields(content_dir):
    result = prepare_data(content_dir, private_path=None, lang="en", target="bridge")
    entry = result["publications"][0]
    for field in ("title", "authors", "year", "doi", "venue", "authorship"):
        assert field in entry
    assert isinstance(entry["authors"], list)


def _typst_available():
    return shutil.which("typst") is not None


def _pdftotext_available():
    return shutil.which("pdftotext") is not None


def _norm(s):
    return " ".join(s.split()).lower()


@pytest.mark.skipif(
    not (_typst_available() and _pdftotext_available()),
    reason="needs typst + pdftotext (poppler) to extract and assert PDF text",
)
def test_pdf_bridge_shows_heading_and_omits_middle_author_titles(repo_root, content_dir):
    out = repo_root / "dist" / "cv-en.pdf"
    if out.exists():
        out.unlink()

    build = subprocess.run(
        [sys.executable, "-m", "pdf.build", "--lang", "en"],  # default target = bridge
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    assert build.returncode == 0, f"build failed:\n{build.stderr}"
    assert out.exists()

    text = subprocess.run(
        ["pdftotext", str(out), "-"], capture_output=True, text=True
    ).stdout
    norm = _norm(text)

    # Heading present (section-heading upper-cases it → "PUBLICATIONS (SELECTED)").
    # Letter-spacing in the Typst style causes pdftotext to insert spaces inside
    # words (e.g. "SELE CTED"), so compare with all spaces removed.
    norm_nospace = norm.replace(" ", "")
    assert "publications(selected)" in norm_nospace

    # A first-author title renders; a middle-author-only title does not (bridge = 9).
    pubs = load_publications(content_dir / "publications.bib")
    first = next(p for p in pubs if p.authorship == "first")
    middle = next(p for p in pubs if p.authorship == "middle")
    assert _norm(first.title) in norm
    assert _norm(middle.title) not in norm
