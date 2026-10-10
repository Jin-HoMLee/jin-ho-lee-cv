"""Lightweight applications-repo path + IO helpers.

Shared by the cover-letter engine (`cover_letter_core`) and the CV export recipe
(`export_application`). This module is deliberately dependency-light — stdlib +
`ruamel.yaml` only — so a vendored `cv-blueprint/` snapshot can ship the CV
export machinery without dragging in the full cover-letter chain (agent_core,
letter_lint, letter_text, render_web_data, jsonschema).

It is also the one place that knows about the vendored-blueprint layout: a
`cv-blueprint/` snapshot records the CV git SHA it was copied from in a
`.cv-sha` marker, and its default applications root is the snapshot's *parent*
(the applications repo) rather than a nested `applications/` directory.
"""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path, PurePosixPath

from ruamel.yaml import YAML

_yaml = YAML(typ="safe")
_yaml.default_flow_style = False

REPO_ROOT = Path(__file__).resolve().parent.parent

ALLOWED_SUFFIXES = {".yaml", ".md", ".txt", ".pdf"}

# A vendored cv-blueprint/ records the CV git SHA it came from in this marker
# file (written by scripts/vendor_cv_blueprint.py).
CV_SHA_FILE = ".cv-sha"


def is_vendored_blueprint(root: Path | None = None) -> bool:
    """True when `root` is a vendored cv-blueprint/ snapshot (has .cv-sha)."""
    root = Path(root) if root is not None else REPO_ROOT
    return (root / CV_SHA_FILE).is_file()


def vendored_cv_sha(root: Path | None = None) -> str | None:
    """The recorded CV git SHA in a vendored snapshot, else None."""
    root = Path(root) if root is not None else REPO_ROOT
    marker = root / CV_SHA_FILE
    if not marker.is_file():
        return None
    return marker.read_text(encoding="utf-8").strip() or None


def _resolve_apps_dir(apps_dir: Path | None = None) -> Path:
    """Applications root, resolved in precedence order.

    1. explicit `apps_dir` argument,
    2. `$APPLICATIONS_DIR`,
    3. a vendored cv-blueprint/ snapshot → its parent (the applications repo),
    4. `$CV_ROOT/applications`,
    5. this repository's nested `applications/` directory.
    """
    if apps_dir is not None:
        return Path(apps_dir)
    env = os.environ.get("APPLICATIONS_DIR")
    if env:
        return Path(env).expanduser()
    if is_vendored_blueprint():
        return REPO_ROOT.parent
    cv_root = os.environ.get("CV_ROOT")
    return (Path(cv_root).expanduser() if cv_root else REPO_ROOT) / "applications"


def _safe_application_path(rel: str, *, apps_dir: Path | None = None) -> Path:
    """Resolve an applications-relative path safely, or raise ValueError.

    Blocks absolute paths, '..'/dot segments, disallowed suffixes, symlink
    escapes, and anything resolving outside apps_dir. An empty suffix is treated
    as a slug directory and allowed.
    """
    apps_dir = _resolve_apps_dir(apps_dir)
    pure = PurePosixPath(rel)
    if pure.is_absolute() or rel.startswith(("/", "\\")):
        raise ValueError(f"path must be relative to applications/: {rel!r}")
    if any(part in ("..", ".") or part.startswith(".") for part in pure.parts):
        raise ValueError(f"illegal path segment in {rel!r}")
    if pure.suffix and pure.suffix not in ALLOWED_SUFFIXES:
        raise ValueError(f"disallowed suffix in {rel!r}")
    resolved = (apps_dir / rel).resolve()
    root = apps_dir.resolve()
    if root != resolved and root not in resolved.parents:
        raise ValueError(f"path escapes applications/: {rel!r}")
    return resolved


def _sanitize_slug(raw: str) -> str:
    """Lowercase, replace non-alphanumerics with hyphens, trim. Raise if empty."""
    s = re.sub(r"[^a-z0-9]+", "-", raw.strip().lower()).strip("-")
    if not s:
        raise ValueError(f"slug is empty after sanitizing: {raw!r}")
    return s


def _atomic_write(rel: str, text: str, *, apps_dir: Path | None = None) -> Path:
    """Atomically write text to a guarded applications-relative path."""
    apps_dir = _resolve_apps_dir(apps_dir)
    dst = _safe_application_path(rel, apps_dir=apps_dir)
    dst.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(dst.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, dst)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    return dst


def _read_yaml(path: Path) -> dict:
    return _yaml.load(path.read_text(encoding="utf-8")) or {}


def read_application(slug: str, *, apps_dir: Path | None = None) -> dict:
    """Bundle {application, job, interview, draft}; missing parts are None."""
    apps_dir = _resolve_apps_dir(apps_dir)
    slug = _sanitize_slug(slug)
    app_dir = _safe_application_path(slug, apps_dir=apps_dir)

    def _yaml_or_none(name: str):
        f = app_dir / name
        return _read_yaml(f) if f.exists() else None

    def _text_or_none(name: str):
        f = app_dir / name
        return f.read_text(encoding="utf-8") if f.exists() else None

    return {
        "application": _yaml_or_none("application.yaml"),
        "job": _text_or_none("job.md"),
        "interview": _yaml_or_none("interview.yaml"),
        "draft": _text_or_none("draft.md"),
    }
