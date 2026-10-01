"""Tests for the Stage 3 export recipe (scripts/export_application.py)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from scripts import export_application as ea
from scripts.cover_letter_core import _resolve_apps_dir

REPO_ROOT = Path(__file__).resolve().parent.parent
_yaml = YAML(typ="safe")

FAKE_PDF = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n"


@pytest.fixture
def apps(tmp_path: Path) -> Path:
    d = tmp_path / "applications"
    d.mkdir()
    return d


def _write_package(
    apps: Path,
    slug: str = "iso-2026-09",
    *,
    language: str = "en",
    tailoring: str = "",
    status: str | None = None,
    status_note: str | None = None,
) -> Path:
    pkg = apps / slug
    pkg.mkdir(parents=True)
    lines = [f"language: {language}"]
    if status is not None:
        lines.append(f"status: {status}")
    if status_note is not None:
        lines.append(f"status_note: {status_note!r}")
    (pkg / "application.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if tailoring:
        (pkg / "cv-tailoring.md").write_text(tailoring, encoding="utf-8")
    return pkg


def _fake_build(tmp_path: Path):
    """A build_pdf callable that writes a fake PDF and returns its path."""

    def _build(lang: str, target: str) -> Path:
        fake = tmp_path / "built" / f"cv-{lang}-{target}.pdf"
        fake.parent.mkdir(parents=True, exist_ok=True)
        fake.write_bytes(FAKE_PDF)
        return fake

    return _build


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# --- variant + policy resolution ------------------------------------------------


def test_parse_tailoring_variant_from_cv_token():
    assert ea.parse_tailoring("Start from `cv-en-comp-bio`.")["variant"] == "comp-bio"


def test_parse_tailoring_variant_from_key():
    assert ea.parse_tailoring("variant: ds-ml\n")["variant"] == "ds-ml"
    assert ea.parse_tailoring("target: bridge\n")["variant"] == "bridge"


def test_parse_tailoring_defaults_to_bridge():
    assert ea.parse_tailoring(None)["variant"] == "bridge"
    assert ea.parse_tailoring("no target here")["variant"] == "bridge"


def test_parse_tailoring_honesty_markers():
    assert (
        ea.parse_tailoring("Honesty scope: general-honesty-first")["content_policy"]
        == "general-honesty-first"
    )
    # "general-honesty-first" must win over the bare "honesty-first" substring.
    assert ea.parse_tailoring("honesty-first only")["content_policy"] == "honesty-first"
    assert ea.parse_tailoring("gated on an honesty gate")["content_policy"] == "honesty gate"


# --- end-to-end export ----------------------------------------------------------


def test_export_resolves_variant_lang_and_writes_manifest(apps, tmp_path: Path):
    slug = "iso-2026-09"
    _write_package(
        apps,
        slug,
        language="en",
        tailoring="Start from cv-en-comp-bio. Honesty scope (final): general-honesty-first",
        status="draft",
        status_note="captain-approved; awaiting human submit",
    )
    manifest = ea.export_application_cv(slug, apps_dir=apps, build_pdf=_fake_build(tmp_path))

    # PDF copied into the package + hashed in the manifest.
    pdf = apps / slug / "artifacts" / "cv-en-comp-bio.pdf"
    assert pdf.read_bytes() == FAKE_PDF
    assert manifest["cv"]["pdf_path"] == "artifacts/cv-en-comp-bio.pdf"
    assert manifest["cv"]["pdf_sha256"] == _sha256(FAKE_PDF)

    # variant + lang + policy resolved from the package.
    assert manifest["cv"]["variant"] == "comp-bio"
    assert manifest["cv"]["lang"] == "en"
    assert manifest["cv"]["content_policy"] == "general-honesty-first"
    assert manifest["cv"]["repo"] == "jin-ho-lee-cv"
    assert manifest["cv"]["git_sha"] == ea.git_head_sha()

    # submit fields read from application.yaml; absent ones are null.
    assert manifest["submit"] == {
        "status": "draft",
        "status_note": "captain-approved; awaiting human submit",
        "submitted_at": None,
        "confirmation_ref": None,
    }

    # no letter PDF → no letter section.
    assert "letter" not in manifest

    # manifest is written back to disk and round-trips.
    on_disk = _yaml.load((apps / slug / "attachment-manifest.yaml").read_text())
    assert on_disk == manifest


def test_export_records_letter_when_present(apps, tmp_path: Path):
    slug = "iso-2026-09"
    _write_package(apps, slug, language="en", tailoring="variant: comp-bio")
    letter_pdf = apps / slug / "cover-letter-en.pdf"
    letter_pdf.write_bytes(FAKE_PDF)

    manifest = ea.export_application_cv(slug, apps_dir=apps, build_pdf=_fake_build(tmp_path))

    assert manifest["letter"]["source"] == "draft.md"
    assert manifest["letter"]["pdf_path"] == "cover-letter-en.pdf"
    assert manifest["letter"]["pdf_sha256"] == _sha256(FAKE_PDF)
    assert manifest["letter"]["rendered_at"]


def test_export_env_override_path(monkeypatch, tmp_path: Path):
    """No apps_dir arg → the package resolves through APPLICATIONS_DIR (Stage 1)."""
    apps = tmp_path / "standalone-apps"
    slug = "iso-2026-09"
    _write_package(apps, slug, language="en", tailoring="variant: comp-bio")
    monkeypatch.setenv("APPLICATIONS_DIR", str(apps))

    manifest = ea.export_application_cv(slug, build_pdf=_fake_build(tmp_path))

    assert (apps / slug / "attachment-manifest.yaml").exists()
    assert (apps / slug / "artifacts" / "cv-en-comp-bio.pdf").exists()
    assert manifest["slug"] == slug


def test_export_honesty_gate_never_touches_content(apps, tmp_path: Path):
    slug = "iso-2026-09"
    _write_package(apps, slug, language="en", tailoring="Honesty scope: general-honesty-first")
    personal = REPO_ROOT / "content" / "personal.yaml"
    before = personal.read_bytes()

    manifest = ea.export_application_cv(slug, apps_dir=apps, build_pdf=_fake_build(tmp_path))

    assert manifest["cv"]["content_policy"] == "general-honesty-first"
    assert personal.read_bytes() == before


def test_export_missing_language_raises(apps, tmp_path: Path):
    _write_package(apps, "iso-2026-09", language="xx")
    with pytest.raises(ValueError):
        ea.export_application_cv("iso-2026-09", apps_dir=apps, build_pdf=_fake_build(tmp_path))


def test_export_missing_package_raises(apps, tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        ea.export_application_cv("nope", apps_dir=apps, build_pdf=_fake_build(tmp_path))


def test_export_missing_application_yaml_raises(apps, tmp_path: Path):
    (apps / "bare").mkdir()
    with pytest.raises(FileNotFoundError):
        ea.export_application_cv("bare", apps_dir=apps, build_pdf=_fake_build(tmp_path))


def test_resolve_apps_dir_shared_with_letter_core(monkeypatch, tmp_path: Path):
    """The export uses the same env contract as the cover-letter engine."""
    target = tmp_path / "job-applications"
    monkeypatch.setenv("APPLICATIONS_DIR", str(target))
    assert ea._resolve_apps_dir() == target == _resolve_apps_dir()
