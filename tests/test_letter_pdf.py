"""Compile-smoke for the cover-letter PDF: the template compiles to a real file.

Skip-guarded locally (needs typst); runs wherever typst is installed.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from scripts import cover_letter_core as clc

pytestmark = pytest.mark.skipif(
    shutil.which("typst") is None, reason="needs typst to compile the cover-letter PDF"
)

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def apps(tmp_path: Path) -> Path:
    d = tmp_path / "applications"
    d.mkdir()
    return d


@pytest.mark.parametrize(
    ("language", "subject", "date_text", "include_phone", "phone_present"),
    [
        ("en", "Application: Bioinformatician", "June 3, 2026", None, False),
        ("en", "Application: Bioinformatician", "June 3, 2026", False, False),
        ("en", "Application: Bioinformatician", "June 3, 2026", True, True),
        ("de", "Bewerbung als Bioinformatician", "3. Juni 2026", None, False),
        ("de", "Bewerbung als Bioinformatician", "3. Juni 2026", False, False),
        ("de", "Bewerbung als Bioinformatician", "3. Juni 2026", True, True),
    ],
)
@pytest.mark.skipif(
    shutil.which("pdftotext") is None, reason="needs pdftotext to inspect the compiled PDF"
)
def test_cover_letter_letterhead_phone_opt_in_and_street_omission(
    apps, tmp_path, monkeypatch, language, subject, date_text, include_phone, phone_present
):
    """Only an explicit true opt-in adds phone; street data is never rendered."""
    private = tmp_path / "private.yaml"
    private.write_text(
        "phone: 'TEST-ONLY-PHONE'\n"
        "address:\n"
        "  street: 'TEST-ONLY-STREET'\n"
        "  postal_code: '00000'\n"
        "  city: 'Testville'\n"
        "  country: 'ZZ'\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(clc, "PRIVATE_PATH", private)

    slug = clc.create_application(
        f"letterhead-{language}-2026-06",
        job_text="# Job\n",
        meta={
            "company": "Acme Genomics GmbH",
            "role": "Bioinformatician",
            "language": language,
            "date": "2026-06-03",
            "recipient": {
                "name": "Dr. Erika Mustermann",
                "company": "Acme Genomics GmbH",
                "address": {
                    "street": "Recipient Street 7",
                    "postal_code": "68159",
                    "city": "Mannheim",
                },
            },
            "subject": subject,
            **({"include_phone": include_phone} if include_phone is not None else {}),
        },
        apps_dir=apps,
    )
    clc.save_draft(slug, "The application body remains intact.\n", apps_dir=apps)
    res = clc.render_letter(slug, fmt="pdf", apps_dir=apps)
    assert res["ok"] is True, res["errors"]
    assert f"artifacts/cover-letter-{language}.pdf" in res["rendered"]
    assert not (apps / slug / f"cover-letter-{language}.pdf").exists()

    pdf = apps / slug / "artifacts" / f"cover-letter-{language}.pdf"
    extracted = subprocess.run(
        ["pdftotext", str(pdf), "-"], capture_output=True, text=True, check=True
    ).stdout
    assert "Jin-Ho Lee" in extracted
    assert "jinho.michael.lee@gmail.com" in extracted  # public email remains in the letterhead
    assert "Dr. Erika Mustermann" in extracted
    assert "Recipient Street 7" in extracted  # recipient address is unaffected
    assert date_text in extracted
    assert subject in extracted
    assert "The application body remains intact." in extracted
    if phone_present:
        assert "TEST-ONLY-PHONE" in extracted
    else:
        assert "TEST-ONLY-PHONE" not in extracted
    assert "TEST-ONLY-STREET" not in extracted
    assert "00000" not in extracted
    assert "Testville" not in extracted
    assert "·  ·" not in extracted  # no empty contact slot creates a doubled separator


def test_cover_letter_pdf_compiles(apps):
    slug = clc.create_application(
        "acme-bio-2026-06",
        job_text="# Job\n",
        meta={
            "company": "Acme Genomics GmbH",
            "role": "Bioinformatician",
            "language": "de",
            "date": "2026-06-03",
            "recipient": {
                "name": "Dr. Erika Mustermann",
                "company": "Acme Genomics GmbH",
                "address": {"street": "Musterstr. 1", "postal_code": "68159", "city": "Mannheim"},
            },
            "subject": "Bewerbung als Bioinformatician",
        },
        apps_dir=apps,
    )
    clc.save_draft(slug, "Absatz eins.\n\nAbsatz zwei.\n", apps_dir=apps)
    res = clc.render_letter(slug, fmt="pdf", apps_dir=apps)
    assert res["ok"] is True, res["errors"]
    out = apps / slug / "artifacts" / "cover-letter-de.pdf"
    assert out.exists()
    assert out.stat().st_size > 1000, "PDF looks empty"


def test_cover_letter_pdf_compiles_minimal_recipient(apps):
    """A recipient with only a name (no company/address) must still compile."""
    slug = clc.create_application(
        "min-bio-2026-06",
        job_text="# Job\n",
        meta={
            "company": "Acme",
            "role": "Bioinformatician",
            "language": "en",
            "date": "2026-06-03",
            "recipient": {"name": "Dr. Schmidt"},
            "subject": "Application: Bioinformatician",
        },
        apps_dir=apps,
    )
    clc.save_draft(slug, "Paragraph one.\n", apps_dir=apps)
    res = clc.render_letter(slug, fmt="pdf", apps_dir=apps)
    assert res["ok"] is True, res["errors"]
    assert (apps / slug / "artifacts" / "cover-letter-en.pdf").exists()


def test_cover_letter_pdf_compiles_with_body_markup(apps):
    """A draft using **bold** + a `- ` bullet block compiles to a real PDF."""
    slug = clc.create_application(
        "markup-bio-2026-06",
        job_text="# Job\n",
        meta={
            "company": "Acme",
            "role": "Bioinformatician",
            "language": "en",
            "date": "2026-06-03",
            "subject": "Application: Bioinformatician",
        },
        apps_dir=apps,
    )
    clc.save_draft(
        slug,
        "I led the **pipeline** work, which maps onto your goals:\n\n"
        "- reproducible Snakemake workflows\n"
        "- HLA typing and neoepitope prediction\n\n"
        "I would welcome a conversation.\n",
        apps_dir=apps,
    )
    res = clc.render_letter(slug, fmt="pdf", apps_dir=apps)
    assert res["ok"] is True, res["errors"]
    out = apps / slug / "artifacts" / "cover-letter-en.pdf"
    assert out.exists()
    assert out.stat().st_size > 1000, "PDF looks empty"


def test_cover_letter_pdf_compiles_no_recipient(apps):
    """No recipient block at all must still compile."""
    slug = clc.create_application(
        "norecip-2026-06",
        job_text="# Job\n",
        meta={
            "company": "Acme",
            "role": "Bioinformatician",
            "language": "en",
            "date": "2026-06-03",
            "subject": "Application: Bioinformatician",
        },
        apps_dir=apps,
    )
    clc.save_draft(slug, "Paragraph one.\n", apps_dir=apps)
    res = clc.render_letter(slug, fmt="pdf", apps_dir=apps)
    assert res["ok"] is True, res["errors"]
    assert (apps / slug / "artifacts" / "cover-letter-en.pdf").exists()
