"""Vendor the CV repo's general-version source + build/export machinery.

Copies a self-contained snapshot of the CV repo's PDF-build machinery and
`content/` master into an applications repo under `cv-blueprint/`, so the
applications repo can build the three general variants (bridge, comp-bio,
ds-ml) and a per-position tailored variant entirely locally — no round-trip to
a CV repo checkout.

The snapshot records the CV git SHA it came from in `cv-blueprint/.cv-sha`;
`scripts/export_application.py` reads that marker when it runs from inside a
vendored snapshot, so the freeze manifest records the *source* CV commit, not
the applications repo's HEAD.

Usage (run from a CV repo checkout at the ref you want to freeze):

    python -m scripts.vendor_cv_blueprint --apps-dir /path/to/applications

Or resolve the apps repo the usual way (APPLICATIONS_DIR / CV_ROOT):

    python -m scripts.vendor_cv_blueprint

The destination `cv-blueprint/` is wiped and rebuilt each run, so the sync is
idempotent and never leaves stale files behind. Build artifacts (dist/,
pdf/.cache/) and PII paths are excluded from the snapshot and gitignored there.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from scripts.applications_io import _resolve_apps_dir

REPO_ROOT = Path(__file__).resolve().parent.parent

BLUEPRINT_DIR = "cv-blueprint"
CV_SHA_FILE = ".cv-sha"

# Directories vendored whole. Everything else is copied file-by-file so the
# snapshot stays minimal (no tests, no web/, no worker/, no cover-letter chain).
DIRS = ("content", "pdf")

FILES = (
    "scripts/__init__.py",
    "scripts/applications_io.py",
    "scripts/bib_loader.py",
    "scripts/content_loader.py",
    "scripts/export_application.py",
    "scripts/langstring.py",
    "scripts/publications.py",
    "schema/application.schema.json",
    ".typstversion",
)

# The per-position tailoring example, flattened into the snapshot root for
# reference (the real per-package tailoring.yaml lives beside application.yaml).
TAILORING_EXAMPLE = "applications.example/example-company-role-2026-06/tailoring.example.yaml"

# Build artifacts and PII paths that must never land in the snapshot. Written as
# cv-blueprint/.gitignore so a vendored build stays clean in the apps repo.
BLUEPRINT_GITIGNORE = """\
# Build artifacts produced by the vendored pdf.build / export_application.
dist/
dist-private/
pdf/.cache/
__pycache__/
*.pyc

# PII / likeness paths used only by the private CV build (never vendored).
content.private/
assets/photo.jpg
assets/signature.png
"""

BLUEPRINT_README = """\
# cv-blueprint/ — vendored CV build snapshot

A self-contained copy of the **general** CV versions and the build/export
machinery from the `jin-ho-lee-cv` repo, vendored here so this applications repo
can build CV variants entirely locally (no round-trip to a CV checkout).

- `.cv-sha` records the exact CV git SHA this snapshot came from.
- `content/` is the CV `content/` master (the three general variants: bridge,
  comp-bio, ds-ml).
- `pdf/` + `scripts/` are the Typst PDF build machinery and the export recipe.
- `tailoring.example.yaml` shows the per-position tailoring shape.

## Build the three general variants

    cd cv-blueprint
    python -m pdf.build --lang en --target bridge
    python -m pdf.build --lang en --target comp-bio
    python -m pdf.build --lang en --target ds-ml
    python -m pdf.build --lang de --target bridge   # …and so on

Outputs land in `cv-blueprint/dist/` (gitignored).

## Build a per-position tailored variant

    cd cv-blueprint
    python -m scripts.export_application <slug>

This reads the local `cv-blueprint/content/`, applies `<slug>/tailoring.yaml`
to a temporary copy (never touching `content/` or the general variants), builds
the PDF, and writes `<slug>/attachment-manifest.yaml` recording the `.cv-sha`.
The apps root is the snapshot's parent, so the package resolves beside
`cv-blueprint/` automatically.

## Refresh from the CV repo

Run `scripts/vendor_cv_blueprint.py` from a CV repo checkout at the default
branch (see the runbook in the CV repo's `docs/runbooks/`). The sync wipes and
rebuilds this directory and bumps `.cv-sha`.
"""


def _git_head_sha(source: Path) -> str:
    proc = subprocess.run(
        ["git", "-C", str(source), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git rev-parse HEAD failed in {source}: {proc.stderr.strip()}")
    return proc.stdout.strip()


def _ignore_transient(src_dir: str, names: list[str]) -> set[str]:
    return {n for n in names if n in ("__pycache__", ".cache", ".DS_Store")}


def _copy_tree(src: Path, dst: Path, rel: str) -> None:
    target = dst / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, target, ignore=_ignore_transient, dirs_exist_ok=True)


def _copy_file(src: Path, dst: Path, rel: str) -> None:
    target = dst / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, target)


def vendor_blueprint(
    *,
    apps_dir: Path | None = None,
    source: Path | None = None,
    cv_sha: str | None = None,
) -> dict:
    """Build (or refresh) `<apps>/cv-blueprint/` and return a summary dict."""
    apps_root = _resolve_apps_dir(apps_dir)
    source = Path(source).resolve() if source is not None else REPO_ROOT
    blueprint = apps_root / BLUEPRINT_DIR

    for rel in DIRS:
        src = source / rel
        if not src.is_dir():
            raise FileNotFoundError(f"missing source directory: {src}")
    for rel in FILES + (TAILORING_EXAMPLE,):
        src = source / rel
        if not src.is_file():
            raise FileNotFoundError(f"missing source file: {src}")

    if cv_sha is None:
        cv_sha = _git_head_sha(source)

    # Wipe + rebuild so a refresh never leaves stale files behind.
    if blueprint.exists():
        shutil.rmtree(blueprint)
    blueprint.mkdir(parents=True)

    for rel in DIRS:
        _copy_tree(source / rel, blueprint, rel)
    for rel in FILES:
        _copy_file(source / rel, blueprint, rel)

    _copy_file(source / TAILORING_EXAMPLE, blueprint, "tailoring.example.yaml")
    (blueprint / CV_SHA_FILE).write_text(cv_sha + "\n", encoding="utf-8")
    (blueprint / ".gitignore").write_text(BLUEPRINT_GITIGNORE, encoding="utf-8")
    (blueprint / "README.md").write_text(BLUEPRINT_README, encoding="utf-8")

    return {
        "blueprint": str(blueprint),
        "apps_dir": str(apps_root),
        "source": str(source),
        "cv_sha": cv_sha,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="vendor_cv_blueprint", description=__doc__)
    parser.add_argument(
        "--apps-dir",
        default=None,
        help="Applications repo root (default: $APPLICATIONS_DIR / $CV_ROOT/applications)",
    )
    parser.add_argument(
        "--source",
        default=None,
        help="CV repo checkout to vendor from (default: this repo)",
    )
    parser.add_argument(
        "--cv-sha",
        default=None,
        help="Record this SHA instead of the source checkout's HEAD",
    )
    args = parser.parse_args(argv)

    try:
        summary = vendor_blueprint(
            apps_dir=Path(args.apps_dir) if args.apps_dir else None,
            source=Path(args.source) if args.source else None,
            cv_sha=args.cv_sha,
        )
    except (FileNotFoundError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"vendored CV blueprint → {summary['blueprint']}")
    print(f"cv_sha: {summary['cv_sha']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
