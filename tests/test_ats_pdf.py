"""ATS guard: the built PDF must have an extractable text layer with name, email,
section headings, and umlauts round-tripping through a parser (pdftotext/poppler).

Turns "ATS-clean" from an assumption into a verified property. Skip-guarded locally;
the CI `ats-guard` job installs Typst + poppler so it actually runs there.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def _have(tool: str) -> bool:
    return shutil.which(tool) is not None


pytestmark = pytest.mark.skipif(
    not (_have("typst") and _have("pdftotext")),
    reason="needs typst + pdftotext (poppler) to build a PDF and extract its text layer",
)


def _build_and_extract(lang: str) -> str:
    """Build the bridge PDF (→ dist/cv-{lang}.pdf, pdf.build has no --output) and extract text."""
    out = REPO_ROOT / "dist" / f"cv-{lang}.pdf"
    if out.exists():
        out.unlink()
    r = subprocess.run(
        [sys.executable, "-m", "pdf.build", "--lang", lang, "--target", "bridge"],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    assert r.returncode == 0, f"PDF build failed:\n{r.stderr}"
    assert out.exists(), f"expected {out} to be written"
    return subprocess.run(
        ["pdftotext", str(out), "-"], check=True, capture_output=True, text=True
    ).stdout


def test_en_pdf_text_layer():
    text = _build_and_extract("en")
    assert len(text) > 800, "PDF appears to have no real text layer (image-only?)"
    assert "Jin-Ho Lee" in text
    assert "jinho.michael.lee@gmail.com" in text
    # Section headings that extract cleanly (NOT 'SELECTED PROJECTS' — Typst
    # letter-spacing makes pdftotext emit 'PROJ ECTS').
    for heading in ("PROFILE", "SKILLS", "EDUCATION", "PUBLICATIONS"):
        assert heading in text, f"missing section heading {heading!r}"
    # Umlaut round-trips (FZ Jülich) — proves Unicode extraction, not mojibake.
    assert "Jülich" in text


def test_de_pdf_text_layer():
    text = _build_and_extract("de")
    assert "Jin-Ho Lee" in text
    # At least one umlaut/ß-bearing token survives extraction.
    assert any(ch in text for ch in "äöüßÄÖÜ"), "no umlaut/ß round-tripped in the DE PDF"
