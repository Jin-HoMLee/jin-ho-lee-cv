"""Smoke test: --private overlay produces a different PDF in dist-private/."""

import shutil
import subprocess
import sys

import pytest


def _typst_available() -> bool:
    return shutil.which("typst") is not None


pytestmark = pytest.mark.skipif(
    not _typst_available(),
    reason="typst CLI not installed",
)


@pytest.fixture
def fake_private_yaml(repo_root):
    """Write a temporary content.private/private.yaml; clean up after.

    Build.py reads from REPO_ROOT/content.private/private.yaml unconditionally
    when --private is given, so we have to write there (and restore afterward
    if a real one exists).
    """
    private_dir = repo_root / "content.private"
    private_file = private_dir / "private.yaml"

    had_dir = private_dir.exists()
    backup_content = None
    if private_file.exists():
        backup_content = private_file.read_text()

    private_dir.mkdir(exist_ok=True)
    private_file.write_text(
        'phone: "+49 000 0000000"\n'
        "address:\n"
        '  street: "Teststr. 1"\n'
        '  postal_code: "00000"\n'
        '  city: "Testville"\n'
        '  country: "ZZ"\n'
    )

    yield private_file

    if backup_content is not None:
        private_file.write_text(backup_content)
    else:
        private_file.unlink()
        if not had_dir:
            private_dir.rmdir()


def test_private_build_produces_pdf_different_from_public(repo_root, fake_private_yaml):
    """Public and private builds should produce byte-different PDFs.

    The private build's PDF will contain the phone number rendered in the header,
    so the file bytes must differ from the public build.
    """
    public_out = repo_root / "dist" / "cv-en.pdf"
    private_out = repo_root / "dist-private" / "cv-en.pdf"

    # Clean prior outputs
    for p in (public_out, private_out):
        if p.exists():
            p.unlink()

    # Public build
    r_pub = subprocess.run(
        [sys.executable, "-m", "pdf.build", "--lang", "en"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    assert r_pub.returncode == 0, f"public build failed: {r_pub.stderr}"
    assert public_out.exists()

    # Private build (with fixture overlay)
    r_priv = subprocess.run(
        [sys.executable, "-m", "pdf.build", "--lang", "en", "--private"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    assert r_priv.returncode == 0, f"private build failed: {r_priv.stderr}"
    assert private_out.exists()

    # PDFs must differ — phone got rendered in private build
    assert public_out.read_bytes() != private_out.read_bytes(), (
        "private and public PDFs are byte-identical; overlay did not affect output"
    )


def test_private_build_fails_when_private_yaml_missing(repo_root):
    """If --private is passed but content.private/private.yaml is absent, exit non-zero."""
    private_dir = repo_root / "content.private"
    private_file = private_dir / "private.yaml"

    # Move aside any existing file
    backup = None
    if private_file.exists():
        backup = private_file.read_text()
        private_file.unlink()

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pdf.build", "--lang", "en", "--private"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0, "expected non-zero exit when private.yaml missing"
        assert "does not exist" in result.stderr, (
            f"expected 'does not exist' in stderr; got: {result.stderr!r}"
        )
    finally:
        if backup is not None:
            private_file.write_text(backup)
