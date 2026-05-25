"""Pytest assertions for the plain-text renderer."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

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
    for section in ("PROFILE", "EXPERIENCE", "EDUCATION", "SKILLS", "LANGUAGES", "VOLUNTEER", "PUBLICATIONS"):
        assert section in en_text, f"missing section header: {section}"


def test_section_headers_present_de(de_text):
    # uppercase translations from labels.yaml
    for section in ("PROFIL", "BERUFSERFAHRUNG", "AUSBILDUNG", "KENNTNISSE", "SPRACHEN", "EHRENAMTLICH", "PUBLIKATIONEN"):
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


def test_pii_never_reaches_main_output(tmp_path):
    """Even if a private overlay exists, the main() CLI must not include it."""
    private_dir = REPO_ROOT / "content.private"
    private_yaml = private_dir / "private.yaml"
    marker_phone = "+49-555-PYTEST-MARKER"
    marker_street = "Pytest-Marker-Strasse 99"
    cleanup_dir = not private_dir.exists()
    cleanup_file = not private_yaml.exists()
    try:
        private_dir.mkdir(exist_ok=True)
        private_yaml.write_text(
            f"personal:\n"
            f"  phone: '{marker_phone}'\n"
            f"  location:\n"
            f"    street: '{marker_street}'\n",
            encoding="utf-8",
        )
        output = tmp_path / "cv-en.txt"
        from scripts.render_text import main
        main(["--lang", "en", "--output", str(output)])
        text = output.read_text()
        assert marker_phone not in text, "PII leaked: private phone in cv-en.txt"
        assert marker_street not in text, "PII leaked: private street in cv-en.txt"
    finally:
        if cleanup_file and private_yaml.exists():
            private_yaml.unlink()
        if cleanup_dir and private_dir.exists():
            private_dir.rmdir()
