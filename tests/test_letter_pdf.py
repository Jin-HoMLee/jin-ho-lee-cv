"""Compile-smoke for the cover-letter PDF: the template compiles to a real file.

Skip-guarded locally (needs typst); runs wherever typst is installed.
"""

from __future__ import annotations

import shutil
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
            "status": "draft",
        },
        apps_dir=apps,
    )
    clc.save_draft(slug, "Absatz eins.\n\nAbsatz zwei.\n", apps_dir=apps)
    res = clc.render_letter(slug, fmt="pdf", apps_dir=apps)
    assert res["ok"] is True, res["errors"]
    out = apps / slug / "cover-letter-de.pdf"
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
            "status": "draft",
        },
        apps_dir=apps,
    )
    clc.save_draft(slug, "Paragraph one.\n", apps_dir=apps)
    res = clc.render_letter(slug, fmt="pdf", apps_dir=apps)
    assert res["ok"] is True, res["errors"]
    assert (apps / slug / "cover-letter-en.pdf").exists()


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
            "status": "draft",
        },
        apps_dir=apps,
    )
    clc.save_draft(slug, "Paragraph one.\n", apps_dir=apps)
    res = clc.render_letter(slug, fmt="pdf", apps_dir=apps)
    assert res["ok"] is True, res["errors"]
    assert (apps / slug / "cover-letter-en.pdf").exists()
