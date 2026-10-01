"""Stage 3 export recipe: build a tailored CV PDF for an application package.

Paired-repos handoff contract (data/cv-applications-architecture-workflow):
the CV repo owns the export recipe; the applications repo is the consumer. This
script resolves a package via the Stage 1 env contract (APPLICATIONS_DIR /
CV_ROOT/applications), reads its `cv-tailoring.md` for the target variant and
`application.yaml` for the language, builds that variant PDF with the existing
`pdf.build` (build-target) machinery, copies it into `<package>/artifacts/`, and
writes the `<package>/attachment-manifest.yaml` freeze record (§4.2).

Honesty-first: a `general-honesty-first` (or any honesty gate) declared in
`cv-tailoring.md` is recorded as `cv.content_policy` and the export still runs,
but the PDF is built from `content/` exactly as-is — this script never reads
`content/` for writing and never invents or alters honesty wording. `content/`
is only ever consumed read-only by `pdf.build.prepare_data`.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from ruamel.yaml import YAML

from pdf import build as pdf_build
from scripts.cover_letter_core import (
    _atomic_write,
    _resolve_apps_dir,
    _safe_application_path,
    _sanitize_slug,
    read_application,
)

_yaml = YAML(typ="safe")
_yaml.default_flow_style = False

REPO_ROOT = Path(__file__).resolve().parent.parent
CV_REPO_NAME = "jin-ho-lee-cv"
TARGETS = ("bridge", "comp-bio", "ds-ml")

# Order matters: "honesty-first" is a substring of "general-honesty-first", so the
# more specific marker must be checked first.
_HONESTY_MARKERS = (
    "general-honesty-first",
    "honesty-first",
    "honesty-gate",
    "honesty gate",
)


# --- small, pure helpers --------------------------------------------------------


def sha256_file(path: Path) -> str:
    """Hex SHA-256 of a file's bytes."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def git_head_sha(repo_root: Path = REPO_ROOT) -> str:
    """Current HEAD commit of the CV repo (the SHA this export freezes)."""
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git rev-parse HEAD failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def _mtime_iso(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat(
        timespec="seconds"
    )


def _dump_yaml(data: dict) -> str:
    buf = io.StringIO()
    _yaml.dump(data, buf)
    return buf.getvalue()


# --- variant + policy resolution from cv-tailoring.md ----------------------------


def parse_tailoring(text: str | None) -> dict:
    """Resolve {variant, content_policy} from a `cv-tailoring.md` body.

    Variant precedence:
      1. an explicit ``variant:`` / ``target:`` key line,
      2. a ``cv-<lang>-<target>`` token (e.g. ``cv-en-comp-bio``),
      3. a bare target token.
    Falls back to ``bridge`` when nothing matches. `content_policy` is the most
    specific honesty marker found (``general-honesty-first`` etc.), else None.
    """
    variant = "bridge"
    content_policy = None

    if text:
        lower = text.lower()

        explicit = re.search(r"^\s*(?:variant|target)\s*:\s*([a-z0-9-]+)", text, re.MULTILINE)
        if explicit and explicit.group(1) in TARGETS:
            variant = explicit.group(1)
        else:
            token = re.search(r"cv-[a-z]{2}-([a-z0-9-]+)", lower)
            if token and token.group(1) in TARGETS:
                variant = token.group(1)
            else:
                for t in ("comp-bio", "ds-ml", "bridge"):
                    if re.search(rf"\b{re.escape(t)}\b", lower):
                        variant = t
                        break

        for marker in _HONESTY_MARKERS:
            if marker in lower:
                content_policy = marker
                break

    return {"variant": variant, "content_policy": content_policy}


def _resolve_language(application: dict) -> str:
    lang = application.get("language")
    if lang not in ("en", "de"):
        raise ValueError(f"application.yaml has no valid 'language' (en|de); got {lang!r}")
    return lang


# --- build + stage + manifest ---------------------------------------------------


def _build_to_dist(lang: str, target: str) -> Path:
    """Build the targeted public PDF via the existing `just build-target` machinery.

    Returns the built path under dist/. Public build only (no --private): the
    attached CV variant is the public one; phone/address belong to the letter.
    """
    rc = pdf_build.main(["--lang", lang, "--target", target])
    if rc != 0:
        raise RuntimeError(f"pdf.build exited {rc}")
    return REPO_ROOT / "dist" / pdf_build._pdf_filename(lang, target)


def _stage_pdf(src: Path, package_dir: Path, rel: str) -> tuple[str, str]:
    """Copy a built PDF into the package under `rel`; return (rel, sha256)."""
    dest = package_dir / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return rel, sha256_file(dest)


def _detect_letter(package_dir: Path, lang: str) -> dict | None:
    """Return the letter section when a rendered letter PDF is present, else None."""
    pdf = package_dir / f"cover-letter-{lang}.pdf"
    if not pdf.is_file():
        return None
    return {
        "source": "draft.md",
        "pdf_path": pdf.name,
        "pdf_sha256": sha256_file(pdf),
        "rendered_at": _mtime_iso(pdf),
    }


def _submit_fields(application: dict) -> dict:
    """The four submit fields read from application.yaml where available (else null)."""
    return {
        key: application.get(key)
        for key in ("status", "status_note", "submitted_at", "confirmation_ref")
    }


def export_application_cv(slug: str, *, apps_dir: Path | None = None, build_pdf=None) -> dict:
    """Build + stage a tailored CV PDF for `slug` and write its freeze manifest.

    `build_pdf` is an injectable ``callable(lang, target) -> Path`` returning the
    built PDF's path (defaults to `_build_to_dist`, the real Typst build). Tests
    pass a fake to avoid a Typst compile.
    """
    apps_dir = _resolve_apps_dir(apps_dir)
    slug = _sanitize_slug(slug)
    package_dir = _safe_application_path(slug, apps_dir=apps_dir)
    if not package_dir.is_dir():
        raise FileNotFoundError(f"no such application: {slug}")

    application = read_application(slug, apps_dir=apps_dir)["application"]
    if not application:
        raise FileNotFoundError(f"no application.yaml for application: {slug}")
    lang = _resolve_language(application)

    tailoring_path = package_dir / "cv-tailoring.md"
    tailoring = tailoring_path.read_text(encoding="utf-8") if tailoring_path.exists() else None
    parsed = parse_tailoring(tailoring)
    variant = parsed["variant"]
    content_policy = parsed["content_policy"]

    if content_policy:
        print(
            f"note: content_policy={content_policy} — building from content/ as-is; "
            "no wording changes",
            file=sys.stderr,
        )

    build = build_pdf or _build_to_dist
    built = build(lang, variant)
    pdf_rel, pdf_sha = _stage_pdf(
        built, package_dir, f"artifacts/{pdf_build._pdf_filename(lang, variant)}"
    )

    manifest: dict = {
        "slug": slug,
        "cv": {
            "repo": CV_REPO_NAME,
            "git_sha": git_head_sha(),
            "variant": variant,
            "lang": lang,
            "pdf_path": pdf_rel,
            "pdf_sha256": pdf_sha,
            "content_policy": content_policy,
        },
    }
    letter = _detect_letter(package_dir, lang)
    if letter is not None:
        manifest["letter"] = letter
    manifest["submit"] = _submit_fields(application)

    _atomic_write(f"{slug}/attachment-manifest.yaml", _dump_yaml(manifest), apps_dir=apps_dir)
    return manifest


# --- CLI ------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="export_application", description=__doc__)
    parser.add_argument("slug", help="Application slug (folder under applications/)")
    args = parser.parse_args(argv)

    try:
        manifest = export_application_cv(args.slug)
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    cv = manifest["cv"]
    print(f"exported {cv['pdf_path']} (sha256 {cv['pdf_sha256'][:12]}…)")
    print(f"wrote applications/{args.slug}/attachment-manifest.yaml")
    return 0


if __name__ == "__main__":
    sys.exit(main())
