"""Tests for the reusable publication-list attachment renderer."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path

import pytest
from pypdf import PdfReader

from scripts.render_publications import prepare_data, render_publications


def test_prepare_data_is_full_bilingual_and_public(content_dir):
    en = prepare_data(content_dir, lang="en")
    de = prepare_data(content_dir, lang="de")

    assert en["labels"]["title"] == "Complete publication list"
    assert de["labels"]["title"] == "Vollständige Publikationsliste"
    assert [group["label"] for group in en["publications"]] == [
        "Research records",
        "Applied / off-domain",
    ]
    assert [group["label"] for group in de["publications"]] == [
        "Forschungsbeiträge",
        "Beitrag aus einem angewandten/themenfremden Bereich",
    ]
    assert sum(group["items_count"] for group in en["publications"]) == 16
    assert "12 peer-reviewed publications" in en["summary"]
    assert "12 begutachtete Publikationen" in de["summary"]
    assert "address" not in en["personal"]
    assert "phone" not in en["personal"]
    assert all("raw" not in item for group in en["publications"] for subgroup in group["groups"] for item in subgroup["items"])


@pytest.mark.skipif(
    shutil.which("typst") is None or shutil.which("pdftotext") is None,
    reason="needs typst + pdftotext to inspect rendered publication PDFs",
)
def test_publication_list_pdf_is_a4_linked_and_extractable(content_dir, tmp_path: Path):
    for lang, title, summary_marker in (
        ("en", "PUBLICATIONS", "Complete publication list"),
        ("de", "PUBLIKATIONEN", "Vollständige Publikationsliste"),
    ):
        out = render_publications(lang=lang, content_dir=content_dir, output=tmp_path / f"pub-{lang}.pdf")
        reader = PdfReader(str(out))
        assert len(reader.pages) == 2
        assert float(reader.pages[0].mediabox.width) == pytest.approx(595.276, abs=0.01)
        assert float(reader.pages[0].mediabox.height) == pytest.approx(841.89, abs=0.01)
        text = subprocess.run(
            ["pdftotext", str(out), "-"], capture_output=True, text=True, check=True
        ).stdout
        assert "Jin-Ho Lee" in text
        assert title in text
        assert summary_marker in text
        assert "COMBO-FISH" in text
        assert "https://" not in text  # labels stay readable; URLs are link annotations
        annotations = [
            annotation
            for page in reader.pages
            for annotation in (page.get("/Annots") or [])
        ]
        assert annotations
        assert any("doi.org" in str(annotation.get_object().get("/A", {}).get("/URI", "")) for annotation in annotations)

        fonts = subprocess.run(["pdffonts", str(out)], capture_output=True, text=True, check=True).stdout
        assert "IBMPlexSans" in fonts


def test_publication_list_build_is_deterministic(content_dir, tmp_path: Path):
    first = render_publications(lang="en", content_dir=content_dir, output=tmp_path / "first.pdf")
    second = render_publications(lang="en", content_dir=content_dir, output=tmp_path / "second.pdf")
    assert hashlib.sha256(first.read_bytes()).digest() == hashlib.sha256(second.read_bytes()).digest()
