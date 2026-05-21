"""Smoke test: public PDF build produces a valid PDF."""
import shutil
import subprocess
import sys

import pytest


def _typst_available() -> bool:
    return shutil.which("typst") is not None


pytestmark = pytest.mark.skipif(
    not _typst_available(),
    reason="typst CLI not installed; install via 'brew install typst' to run PDF tests.",
)


def test_public_build_produces_valid_pdf(repo_root):
    """Run `python -m pdf.build --lang en` and assert dist/cv-en.pdf exists + valid."""
    dist = repo_root / "dist"
    out = dist / "cv-en.pdf"
    if out.exists():
        out.unlink()

    result = subprocess.run(
        [sys.executable, "-m", "pdf.build", "--lang", "en"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, f"build failed:\nstdout={result.stdout}\nstderr={result.stderr}"
    assert out.exists(), f"expected {out} to be created"
    assert out.stat().st_size > 500, "PDF suspiciously small"

    with out.open("rb") as f:
        magic = f.read(5)
    assert magic == b"%PDF-", f"not a PDF (magic bytes: {magic!r})"
