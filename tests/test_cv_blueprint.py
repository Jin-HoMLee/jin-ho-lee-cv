"""Tests for the cv-blueprint vendoring + local-tailoring decoupling.

The applications repo holds a self-contained `cv-blueprint/` snapshot (CV
`content/` + the minimal PDF build/export machinery + a `.cv-sha` marker) so a
per-position export runs entirely locally, with no round-trip to a CV checkout.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from ruamel.yaml import YAML

from scripts import applications_io
from scripts import export_application as ea
from scripts import vendor_cv_blueprint as vcb

REPO_ROOT = Path(__file__).resolve().parent.parent
_yaml = YAML(typ="safe")

FAKE_PDF = b"%PDF-1.4 fake\n"

_TAILORING_YAML = (
    "profile:\n"
    "  comp-bio:\n"
    "    tagline:\n"
    '      en: "Tailored EN tagline"\n'
    '      de: "Tailored DE tagline"\n'
    "projects:\n"
    "  L2:\n"
    "    outcome:\n"
    '      en: "Tailored EN outcome"\n'
    '      de: "Tailored DE outcome"\n'
    "experience:\n"
    "  research:\n"
    "    append:\n"
    '      - en: "Leadership & Mentoring: EN bullet"\n'
    '        de: "Führung & Mentoring: DE bullet"\n'
    "        refs: [L4]\n"
)


def _write_package(apps: Path, slug: str, *, tailoring_yaml: str | None = None) -> Path:
    pkg = apps / slug
    pkg.mkdir(parents=True)
    (pkg / "application.yaml").write_text("language: en\n", encoding="utf-8")
    (pkg / "cv-tailoring.md").write_text("variant: comp-bio\n", encoding="utf-8")
    if tailoring_yaml is not None:
        (pkg / "tailoring.yaml").write_text(tailoring_yaml, encoding="utf-8")
    return pkg


# --- applications_io vendored-blueprint detection ------------------------------


def test_is_vendored_blueprint_and_vendored_cv_sha(tmp_path: Path):
    assert not applications_io.is_vendored_blueprint(tmp_path)
    assert applications_io.vendored_cv_sha(tmp_path) is None

    (tmp_path / ".cv-sha").write_text("deadbeef\n", encoding="utf-8")
    assert applications_io.is_vendored_blueprint(tmp_path)
    assert applications_io.vendored_cv_sha(tmp_path) == "deadbeef"


def test_resolve_apps_dir_vendored_returns_parent(monkeypatch):
    """A vendored snapshot defaults its apps root to the snapshot's parent."""
    monkeypatch.setattr(applications_io, "is_vendored_blueprint", lambda root=None: True)
    monkeypatch.delenv("APPLICATIONS_DIR", raising=False)
    monkeypatch.delenv("CV_ROOT", raising=False)
    assert applications_io._resolve_apps_dir() == applications_io.REPO_ROOT.parent


# --- vendor_blueprint ----------------------------------------------------------


def test_vendor_blueprint_builds_minimal_snapshot(tmp_path: Path):
    apps = tmp_path / "applications"
    apps.mkdir()

    summary = vcb.vendor_blueprint(apps_dir=apps, cv_sha="abcdef1234567890")
    bp = apps / "cv-blueprint"

    assert summary["cv_sha"] == "abcdef1234567890"
    assert (bp / ".cv-sha").read_text(encoding="utf-8").strip() == "abcdef1234567890"

    # general-version source vendored whole
    assert (bp / "content" / "personal.yaml").is_file()
    assert (bp / "content" / "publications.bib").is_file()
    assert (bp / "content" / "experience.yaml").is_file()
    # build machinery vendored whole
    assert (bp / "pdf" / "build.py").is_file()
    assert (bp / "pdf" / "projection.py").is_file()
    assert (bp / "pdf" / "styles.typ").is_file()
    assert (bp / "pdf" / "templates" / "cv.typ").is_file()
    # minimal scripts subset vendored
    assert (bp / "scripts" / "export_application.py").is_file()
    assert (bp / "scripts" / "content_loader.py").is_file()
    assert (bp / "scripts" / "applications_io.py").is_file()
    assert (bp / "scripts" / "bib_loader.py").is_file()
    assert (bp / "scripts" / "langstring.py").is_file()
    assert (bp / "scripts" / "publications.py").is_file()
    # heavy cover-letter chain is deliberately NOT vendored
    assert not (bp / "scripts" / "cover_letter_core.py").exists()
    assert not (bp / "scripts" / "agent_core.py").exists()
    assert not (bp / "scripts" / "render_web_data.py").exists()
    # tailoring example, schema, gitignore, readme
    assert (bp / "tailoring.example.yaml").is_file()
    assert (bp / "schema" / "application.schema.json").is_file()
    assert (bp / ".typstversion").is_file()
    gitignore = (bp / ".gitignore").read_text(encoding="utf-8")
    assert "dist/" in gitignore
    assert "content.private/" in gitignore
    assert "__pycache__/" in gitignore
    assert (bp / "README.md").is_file()

    # refresh is idempotent and bumps the recorded SHA
    vcb.vendor_blueprint(apps_dir=apps, cv_sha="ffffffffffffffff")
    assert (bp / ".cv-sha").read_text(encoding="utf-8").strip() == "ffffffffffffffff"


def test_vendor_blueprint_records_source_git_head(tmp_path: Path):
    apps = tmp_path / "applications"
    apps.mkdir()
    summary = vcb.vendor_blueprint(apps_dir=apps)
    assert summary["cv_sha"] == ea.git_head_sha()


def test_git_head_sha_reads_vendored_marker(tmp_path: Path):
    (tmp_path / ".cv-sha").write_text("cafe1234\n", encoding="utf-8")
    assert ea.git_head_sha(tmp_path) == "cafe1234"


# --- vendored export runs locally (no CV checkout) -----------------------------


def test_vendored_export_builds_and_records_cv_sha(tmp_path: Path):
    apps = tmp_path / "applications"
    apps.mkdir()
    slug = "daina-test-2026-10"
    _write_package(apps, slug, tailoring_yaml=_TAILORING_YAML)
    vcb.vendor_blueprint(apps_dir=apps, cv_sha="beefbeefbeefbeef")
    blueprint = apps / "cv-blueprint"

    snippet = """
import json, os, sys
from pathlib import Path
sys.path.insert(0, os.getcwd())
from scripts import export_application as ea

def fake_build(lang, target, content_dir=None):
    out = Path(os.getcwd()) / "dist" / f"cv-{lang}-{target}.pdf"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(b"%PDF-1.4 fake\\n")
    return out

m = ea.export_application_cv("daina-test-2026-10", build_pdf=fake_build)
print(json.dumps({
    "git_sha": m["cv"]["git_sha"],
    "variant": m["cv"]["variant"],
    "pdf_path": m["cv"]["pdf_path"],
    "tailoring": m["cv"].get("tailoring"),
    "apps_dir": str(ea._resolve_apps_dir()),
}))
"""
    env = {k: v for k, v in os.environ.items() if k not in ("APPLICATIONS_DIR", "CV_ROOT")}
    proc = subprocess.run(
        [sys.executable, "-c", snippet],
        cwd=str(blueprint),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout.strip().splitlines()[-1])

    # The manifest freezes the *vendored* CV SHA, not the apps repo's HEAD.
    assert out["git_sha"] == "beefbeefbeefbeef"
    assert out["variant"] == "comp-bio"
    assert out["pdf_path"] == "artifacts/cv-en-comp-bio.pdf"
    # The vendored export resolves the apps root as the snapshot's parent.
    assert out["apps_dir"] == str(apps.resolve())
    # tailoring.yaml applied (all three override kinds), recorded in the manifest.
    assert out["tailoring"]["file"] == "tailoring.yaml"
    assert out["tailoring"]["applied"] == [
        {
            "kind": "profile_tagline",
            "variant": "comp-bio",
            "en": "Tailored EN tagline",
            "de": "Tailored DE tagline",
        },
        {
            "kind": "project_outcome",
            "id": "L2",
            "en": "Tailored EN outcome",
            "de": "Tailored DE outcome",
        },
        {
            "kind": "experience_bullet",
            "entry": "research",
            "en": "Leadership & Mentoring: EN bullet",
            "de": "Führung & Mentoring: DE bullet",
            "refs": ["L4"],
        },
    ]

    # The built PDF was staged into the package and the manifest written locally.
    assert (apps / slug / "artifacts" / "cv-en-comp-bio.pdf").read_bytes() == FAKE_PDF
    manifest = _yaml.load((apps / slug / "attachment-manifest.yaml").read_text())
    assert manifest["cv"]["git_sha"] == "beefbeefbeefbeef"
    assert manifest["cv"]["pdf_path"] == "artifacts/cv-en-comp-bio.pdf"


def test_vendored_export_leaves_general_variants_untouched(tmp_path: Path):
    """Tailoring applies to a temp copy only; the vendored content stays general."""
    apps = tmp_path / "applications"
    apps.mkdir()
    slug = "daina-test-2026-10"
    _write_package(apps, slug, tailoring_yaml=_TAILORING_YAML)
    vcb.vendor_blueprint(apps_dir=apps, cv_sha="beefbeefbeefbeef")
    blueprint = apps / "cv-blueprint"

    l2_before = (blueprint / "content" / "projects" / "L2.en.yaml").read_bytes()
    prof_before = (blueprint / "content" / "profile.en.yaml").read_bytes()

    from scripts.content_loader import load_content

    content_dir, _applied = ea.apply_overrides(
        blueprint / "content",
        ea.load_tailoring_overrides(apps / slug),
    )
    try:
        l2 = _yaml.load((content_dir / "projects" / "L2.en.yaml").read_text())
        assert l2["outcome"] == "Tailored EN outcome"
    finally:
        import shutil

        shutil.rmtree(content_dir.parent, ignore_errors=True)

    # The vendored general content is byte-identical after tailoring.
    assert (blueprint / "content" / "projects" / "L2.en.yaml").read_bytes() == l2_before
    assert (blueprint / "content" / "profile.en.yaml").read_bytes() == prof_before

    # And the general variant (no tailoring) still resolves to the general wording.
    general = load_content(blueprint / "content", lang="en", target="comp-bio")
    assert "real-patient" not in general["projects"]["L2"]["outcome"]
