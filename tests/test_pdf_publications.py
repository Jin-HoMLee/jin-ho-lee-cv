"""Tests for the PDF publications section (issues #43, #46)."""

import shutil
import subprocess
import sys

import pytest

from pdf.build import prepare_data
from scripts.bib_loader import load_publications
from scripts.publications import publication_summary


def test_prepare_data_comp_bio_full_list(content_dir):
    all_pubs = load_publications(content_dir / "publications.bib")
    result = prepare_data(content_dir, private_path=None, lang="en", target="comp-bio")
    assert result["publications_mode"] == "full"
    assert [p["key"] for p in result["publications"]] == [p.key for p in all_pubs]
    assert result["publications_heading"] == "Publications"
    assert result["publications_summary"] is None
    assert result["publications_pointer"] is None


def test_prepare_data_bridge_aggregate(content_dir):
    s = publication_summary(load_publications(content_dir / "publications.bib"))
    result = prepare_data(content_dir, private_path=None, lang="en", target="bridge")
    assert result["publications_mode"] == "aggregate"
    assert result["publications_heading"] == "Publications"
    assert f"{s.peer_reviewed} peer-reviewed publications" in result["publications_summary"]
    assert (
        f"{s.conferences} first-author conference contributions" in result["publications_summary"]
    )
    assert result["publications_pointer"] == "Full list & metrics:"


def test_prepare_data_ds_ml_aggregate(content_dir):
    s = publication_summary(load_publications(content_dir / "publications.bib"))
    result = prepare_data(content_dir, private_path=None, lang="en", target="ds-ml")
    assert result["publications_mode"] == "aggregate"
    assert f"{s.peer_reviewed} peer-reviewed publications" in result["publications_summary"]
    assert result["publications_pointer"] == "Full list & metrics:"


def test_prepare_data_de_aggregate_localized(content_dir):
    result = prepare_data(content_dir, private_path=None, lang="de", target="bridge")
    assert result["publications_heading"] == "Publikationen"
    assert "begutachtete Publikationen" in result["publications_summary"]
    assert result["publications_pointer"] == "Vollständige Liste:"


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
def test_pdf_bridge_aggregate_vs_comp_bio_full(repo_root, content_dir):
    pubs = load_publications(content_dir / "publications.bib")
    middle = next(p for p in pubs if p.authorship == "middle")

    def build(target, name):
        out = repo_root / "dist" / name
        if out.exists():
            out.unlink()
        r = subprocess.run(
            [sys.executable, "-m", "pdf.build", "--lang", "en", "--target", target],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        assert r.returncode == 0, f"build failed:\n{r.stderr}"
        assert out.exists()
        return subprocess.run(["pdftotext", str(out), "-"], capture_output=True, text=True).stdout

    bridge = _norm(build("bridge", "cv-en.pdf"))
    compbio = _norm(build("comp-bio", "cv-en-comp-bio.pdf"))

    # bridge → aggregate: ORCID pointer present, the middle-author paper title absent.
    assert "orcid.org/0009-0001-8784-1771" in bridge.replace(" ", "")
    # Hyphen-insensitive: pdftotext drops a hyphen when a title word wraps at it.
    assert _norm(middle.title).replace("-", "") not in bridge.replace("-", "")
    # comp-bio → full list: the middle-author paper title present.
    assert _norm(middle.title).replace("-", "") in compbio.replace("-", "")
