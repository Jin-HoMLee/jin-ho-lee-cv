"""Tests for the PDF publications section (issues #43, #46)."""

import shutil
import subprocess
import sys

import pytest

from pdf.build import prepare_data
from scripts.bib_loader import load_publications
from scripts.publications import publication_summary


def test_prepare_data_comp_bio_selected_publications(content_dir):
    all_pubs = load_publications(content_dir / "publications.bib")
    result = prepare_data(content_dir, private_path=None, lang="en", target="comp-bio")

    assert len(all_pubs) == 15  # the canonical bibliography remains complete
    assert result["publications_mode"] == "selected"
    assert [p["key"] for p in result["publications"]] == [
        "lee2021superres_dna_repair",
        "hausmann2020_3d_dna_fish",
        "lee2019_combofish",
    ]
    assert result["publications_heading"] == "Selected Publications"
    assert "3 selected of 11 peer-reviewed research publications" in result["publications_summary"]
    assert "15 bibliography records total" in result["publications_summary"]
    assert result["publications_pointer"] == "Full list & metrics:"
    assert [link["label"] for link in result["publication_links"]] == [
        "ORCID",
        "Google Scholar",
        "Web CV",
    ]


def test_prepare_data_bridge_aggregate(content_dir):
    s = publication_summary(load_publications(content_dir / "publications.bib"))
    result = prepare_data(content_dir, private_path=None, lang="en", target="bridge")
    assert result["publications_mode"] == "aggregate"
    assert result["publications_heading"] == "Publications"
    assert (
        f"{s.peer_reviewed} peer-reviewed research publications" in result["publications_summary"]
    )
    assert f"{s.total_records} bibliography records total" in result["publications_summary"]
    assert result["publications_pointer"] == "Full list & metrics:"
    assert [link["label"] for link in result["publication_links"]] == [
        "ORCID",
        "Google Scholar",
        "Web CV",
    ]


def test_prepare_data_ds_ml_aggregate(content_dir):
    s = publication_summary(load_publications(content_dir / "publications.bib"))
    result = prepare_data(content_dir, private_path=None, lang="en", target="ds-ml")
    assert result["publications_mode"] == "aggregate"
    assert (
        f"{s.peer_reviewed} peer-reviewed research publications" in result["publications_summary"]
    )
    assert result["publications_pointer"] == "Full list & metrics:"


def test_prepare_data_de_aggregate_localized(content_dir):
    result = prepare_data(content_dir, private_path=None, lang="de", target="bridge")
    assert result["publications_heading"] == "Publikationen"
    assert "begutachtete Forschungspublikationen" in result["publications_summary"]
    assert result["publications_pointer"] == "Vollständige Liste:"


def test_prepare_data_comp_bio_de_selected_summary_localized(content_dir):
    result = prepare_data(content_dir, private_path=None, lang="de", target="comp-bio")
    assert result["publications_heading"] == "Ausgewählte Publikationen"
    assert (
        "3 ausgewählte von 11 begutachteten Forschungspublikationen"
        in result["publications_summary"]
    )
    assert "insgesamt 15 Bibliografie-Datensätze" in result["publications_summary"]
    assert [link["label"] for link in result["publication_links"]] == [
        "ORCID",
        "Google Scholar",
        "Web-Lebenslauf",
    ]


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
def test_pdf_bridge_aggregate_vs_comp_bio_selected(repo_root, content_dir):
    pubs = load_publications(content_dir / "publications.bib")
    selected_title = next(p.title for p in pubs if p.key == "lee2019_combofish")
    omitted_title = next(p.title for p in pubs if p.authorship == "middle")

    def build(target, name):
        out = repo_root / "dist" / name
        if out.exists():
            out.unlink()
        r = subprocess.run(
            [sys.executable, "-m", "pdf.build", "--lang", "en", "--target", target],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        assert r.returncode == 0, f"build failed:\n{r.stderr}"
        assert out.exists()
        return subprocess.run(
            ["pdftotext", str(out), "-"], capture_output=True, text=True, check=True
        ).stdout

    bridge = _norm(build("bridge", "cv-en.pdf"))
    compbio = _norm(build("comp-bio", "cv-en-comp-bio.pdf"))

    # bridge → aggregate: publication links are visible, individual titles are absent.
    assert "orcid" in bridge
    assert "google scholar" in bridge
    assert _norm(selected_title).replace("-", "") not in bridge.replace("-", "")
    # comp-bio → three representative records, not the complete bibliography.
    assert _norm(selected_title).replace("-", "") in compbio.replace("-", "")
    assert _norm(omitted_title).replace("-", "") not in compbio.replace("-", "")
    assert "3 selected of 11 peer-reviewed" in compbio
    assert "15 bibliography records total" in compbio


@pytest.mark.skipif(
    not (_typst_available() and _pdftotext_available()),
    reason="needs typst + pdftotext (poppler) to extract and assert PDF text",
)
def test_pdf_comp_bio_keeps_full_skills_sections(repo_root):
    """The Comp Bio PDF keeps the full, identical four skills sections."""
    expected = {
        "en": (
            "Genomics",
            "Immunoinformatics",
            "Bioinformatics Workflows",
            "Machine Learning",
            "AI Agents",
            "Browser ML Delivery",
        ),
        "de": (
            "Genomik",
            "Immunoinformatik",
            "Bioinformatik-Workflows",
            "Maschinelles Lernen",
            "KI-Agenten",
            "Browser-ML-Auslieferung",
        ),
    }

    for lang in ("en", "de"):
        out = repo_root / "dist" / f"cv-{lang}-comp-bio.pdf"
        if out.exists():
            out.unlink()
        result = subprocess.run(
            [sys.executable, "-m", "pdf.build", "--lang", lang, "--target", "comp-bio"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, f"build failed:\n{result.stderr}"
        text = subprocess.run(
            ["pdftotext", str(out), "-"], capture_output=True, text=True, check=True
        ).stdout
        normalized = _norm(text)
        for label in expected[lang]:
            assert _norm(label) in normalized
        for agent in ("Claude Code", "Codex", "OpenCode", "Pi", "Grok", "Cursor", "Kimi"):
            assert _norm(agent) in normalized
