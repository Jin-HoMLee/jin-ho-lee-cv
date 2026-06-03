"""Tests for the cover-letter core (paths, profile/application storage, validation, render)."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts import cover_letter_core as clc

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def apps(tmp_path: Path) -> Path:
    """An empty, writable applications/ dir."""
    d = tmp_path / "applications"
    d.mkdir()
    return d


@pytest.mark.parametrize(
    "bad",
    [
        "/etc/passwd",
        "../content/personal.yaml",
        "../../secret.yaml",
        "slug/../../escape.yaml",
        ".hidden/application.yaml",
        "slug/evil.exe",
    ],
)
def test_safe_path_rejects(apps, bad):
    with pytest.raises(ValueError):
        clc._safe_application_path(bad, apps_dir=apps)


def test_safe_path_accepts_dir_and_file(apps):
    assert clc._safe_application_path("acme-bio-2026-06", apps_dir=apps) == (
        apps / "acme-bio-2026-06"
    ).resolve()
    assert clc._safe_application_path("acme-bio-2026-06/draft.md", apps_dir=apps) == (
        apps / "acme-bio-2026-06" / "draft.md"
    ).resolve()


def test_safe_path_rejects_symlink_escape(apps):
    (apps / "leak").symlink_to(REPO_ROOT / "content")
    with pytest.raises(ValueError):
        clc._safe_application_path("leak/personal.yaml", apps_dir=apps)


def test_sanitize_slug():
    assert clc._sanitize_slug("Acme Genomics / Bioinformatician 2026-06") == (
        "acme-genomics-bioinformatician-2026-06"
    )
    with pytest.raises(ValueError):
        clc._sanitize_slug("///")


def test_profile_roundtrip(apps):
    assert clc.read_profile(apps_dir=apps) == {}
    data = {"motivation": {"en": "x"}, "availability": "now"}
    clc.write_profile(data, apps_dir=apps)
    assert clc.read_profile(apps_dir=apps) == data


def test_write_profile_rejects_invalid(apps):
    with pytest.raises(ValueError):
        clc.write_profile({"motivation": {"de": "only-de-no-en"}}, apps_dir=apps)


def test_create_and_read_application(apps):
    slug = clc.create_application(
        "Acme Bio 2026-06",
        job_text="# Job\nDo bioinformatics.\n",
        meta={
            "company": "Acme",
            "role": "Bioinformatician",
            "language": "de",
            "date": "2026-06-03",
            "subject": "Bewerbung",
            "status": "draft",
        },
        apps_dir=apps,
    )
    assert slug == "acme-bio-2026-06"
    bundle = clc.read_application(slug, apps_dir=apps)
    assert bundle["application"]["company"] == "Acme"
    assert "bioinformatics" in bundle["job"]
    assert bundle["interview"] is None
    assert bundle["draft"] is None


def test_create_application_refuses_collision(apps):
    meta = {
        "company": "Acme",
        "role": "Bioinformatician",
        "language": "de",
        "date": "2026-06-03",
        "subject": "Bewerbung",
        "status": "draft",
    }
    clc.create_application("acme-bio-2026-06", job_text="x", meta=meta, apps_dir=apps)
    with pytest.raises(FileExistsError):
        clc.create_application("acme-bio-2026-06", job_text="y", meta=meta, apps_dir=apps)


def test_list_applications_sorted(apps):
    for s in ("b-role-2026-06", "a-role-2026-06"):
        clc.create_application(
            s,
            job_text="x",
            meta={
                "company": "C",
                "role": "R",
                "language": "en",
                "date": "2026-06-03",
                "subject": "S",
                "status": "draft",
            },
            apps_dir=apps,
        )
    assert clc.list_applications(apps_dir=apps) == ["a-role-2026-06", "b-role-2026-06"]


def test_core_never_writes_under_content(apps):
    """All write helpers route through _safe_application_path; content/ is untouchable."""
    with pytest.raises(ValueError):
        clc._atomic_write("../content/personal.yaml", "boom", apps_dir=apps)
