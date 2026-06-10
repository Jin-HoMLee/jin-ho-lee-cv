"""Smoke test: --private overlay produces a different PDF in dist-private/.

These tests drive the build via the CV_PRIVATE_YAML override so they point at a
temp private.yaml and NEVER read, write, or delete the real content.private/
(see issue #77 — the old fixture mutated the real PII file). Every test asserts
the real file is byte-identical afterward.
"""

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

# Synthetic overlay — never real values.
_FAKE_PRIVATE = (
    'phone: "+49 000 0000000"\n'
    "address:\n"
    '  street: "Teststr. 1"\n'
    '  postal_code: "00000"\n'
    '  city: "Testville"\n'
    '  country: "ZZ"\n'
)


@pytest.fixture
def real_private_untouched(repo_root):
    """Snapshot the real private.yaml and assert the test never touched it."""
    real = repo_root / "content.private" / "private.yaml"
    before = real.read_bytes() if real.exists() else None
    yield real
    after = real.read_bytes() if real.exists() else None
    assert after == before, "test mutated the real content.private/private.yaml!"


@pytest.fixture
def fake_private_yaml(tmp_path, monkeypatch):
    """A temp private.yaml wired in via CV_PRIVATE_YAML (subprocess inherits it)."""
    private_file = tmp_path / "content.private" / "private.yaml"
    private_file.parent.mkdir(parents=True)
    private_file.write_text(_FAKE_PRIVATE)
    monkeypatch.setenv("CV_PRIVATE_YAML", str(private_file))
    return private_file


def test_private_build_produces_pdf_different_from_public(
    repo_root, fake_private_yaml, real_private_untouched
):
    """Public and private builds should produce byte-different PDFs.

    The private build's PDF will contain the phone number rendered in the header,
    so the file bytes must differ from the public build.
    """
    public_out = repo_root / "dist" / "cv-en.pdf"
    private_out = repo_root / "dist-private" / "cv-en.pdf"

    for p in (public_out, private_out):
        if p.exists():
            p.unlink()

    # Public build ignores --private entirely, so CV_PRIVATE_YAML is irrelevant here.
    r_pub = subprocess.run(
        [sys.executable, "-m", "pdf.build", "--lang", "en"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    assert r_pub.returncode == 0, f"public build failed: {r_pub.stderr}"
    assert public_out.exists()

    # Private build — inherits CV_PRIVATE_YAML (the temp overlay) from the fixture.
    r_priv = subprocess.run(
        [sys.executable, "-m", "pdf.build", "--lang", "en", "--private"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    assert r_priv.returncode == 0, f"private build failed: {r_priv.stderr}"
    assert private_out.exists()

    assert public_out.read_bytes() != private_out.read_bytes(), (
        "private and public PDFs are byte-identical; overlay did not affect output"
    )


def test_private_build_fails_when_private_yaml_missing(
    repo_root, tmp_path, monkeypatch, real_private_untouched
):
    """If --private is passed but the (overridden) private.yaml is absent, exit non-zero."""
    missing = tmp_path / "content.private" / "private.yaml"  # never created
    monkeypatch.setenv("CV_PRIVATE_YAML", str(missing))

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
