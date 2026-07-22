"""Guards for the public reuse contract introduced in issue #140."""

from pathlib import Path
import tomllib

REPO_ROOT = Path(__file__).resolve().parent.parent
LICENSE = REPO_ROOT / "LICENSE"
REUSE_TOML = REPO_ROOT / "REUSE.toml"
MIT_LICENSE = REPO_ROOT / "LICENSES" / "MIT.txt"
RESERVED_LICENSE = REPO_ROOT / "LICENSES" / "LicenseRef-All-Rights-Reserved.txt"
README = REPO_ROOT / "README.md"
REUSE_GUIDE = REPO_ROOT / "docs" / "reuse.md"

EXCLUDED_PERSONAL_MATERIALS = (
    "content/",
    "web/src/pages/writeups/",
    "docs/build-post/",
    "web/public/photo.jpg",
    "web/src/assets/digital-twin-photo.png",
    "tests/__snapshots__/",
    "docs/superpowers/plans/2026-07-20-phase-15-splice-writeup.md",
    "docs/superpowers/plans/2026-07-22-build-post.md",
)

RESERVED_PATTERNS = (
    "content/**",
    "web/src/pages/writeups/**",
    "docs/build-post/**",
    "web/public/photo.jpg",
    "web/src/assets/digital-twin-photo.png",
    "tests/__snapshots__/**",
    "docs/superpowers/plans/2026-07-20-phase-15-splice-writeup.md",
    "docs/superpowers/plans/2026-07-22-build-post.md",
)


def _read_required(path: Path) -> str:
    assert path.exists(), f"required reuse-contract file is missing: {path.relative_to(REPO_ROOT)}"
    return path.read_text(encoding="utf-8")


def test_license_is_the_standard_mit_grant():
    text = _read_required(LICENSE)

    assert text.startswith("MIT License\n")
    assert "Permission is hereby granted, free of charge" in text


def test_file_level_license_map_scopes_mit_and_reserved_material():
    license_map = tomllib.loads(_read_required(REUSE_TOML))
    annotations = license_map["annotations"]

    assert license_map["version"] == 1
    assert annotations[0]["path"] == "**"
    assert annotations[0]["SPDX-License-Identifier"] == "MIT"

    reserved = annotations[-1]
    assert reserved["precedence"] == "override"
    assert reserved["SPDX-License-Identifier"] == "LicenseRef-All-Rights-Reserved"
    assert set(reserved["path"]) == set(RESERVED_PATTERNS)

    assert "Permission is hereby granted, free of charge" in _read_required(MIT_LICENSE)
    assert "No permission is granted" in _read_required(RESERVED_LICENSE)


def test_reuse_guide_excludes_and_reserves_personal_materials():
    text = _read_required(REUSE_GUIDE)

    assert "software, schemas, reusable templates" in text
    assert "`REUSE.toml`" in text
    for path in EXCLUDED_PERSONAL_MATERIALS:
        assert f"`{path}`" in text, f"reuse guide does not name excluded path {path}"
    assert "All rights reserved" in text


def test_readme_links_the_reuse_guide_and_sets_expectations():
    text = _read_required(README)

    assert "[reuse guide](docs/reuse.md)" in text
    assert "not a one-command template" in text


def test_reuse_guide_covers_the_current_manual_adaptation_path():
    text = _read_required(REUSE_GUIDE)

    required_details = (
        "content/",
        "content.private/",
        "content.private.example/private.example.yaml",
        "web/.env.production",
        ".github/workflows/pages.yml",
        "PUBLIC_ANALYTICS_ENDPOINT",
        "GSC_VERIFY",
        "PUBLIC_TWIN_ENDPOINT",
        "web/src/components/DigitalTwin.astro",
        ".nvmrc",
        "pnpm",
        "just validate",
        "just test",
        "just build",
        "just web-build",
        "just build-formats",
    )
    for detail in required_details:
        assert detail in text, f"reuse guide omits {detail}"
