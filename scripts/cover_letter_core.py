"""Cover-letter core: storage, validation, and render orchestration.

Pure Python, mirrors scripts/agent_core.py conventions. Every path / PII /
subprocess guard lives here. Reads content/ read-only (via agent_core.read_cv)
for grounding; writes ONLY into the gitignored applications/ overlay.
"""

from __future__ import annotations

import io
import json
import os
import re
import tempfile
from pathlib import Path, PurePosixPath

from jsonschema import Draft202012Validator
from ruamel.yaml import YAML

_yaml = YAML(typ="safe")
_yaml.default_flow_style = False

REPO_ROOT = Path(__file__).resolve().parent.parent
APPS_DIR = REPO_ROOT / "applications"
PROFILE_SCHEMA = REPO_ROOT / "schema" / "profile.schema.json"

ALLOWED_SUFFIXES = {".yaml", ".md", ".txt", ".pdf"}
_GAP_DECISIONS = {"transferable", "omit", "example"}


# --- path safety & low-level IO -------------------------------------------------


def _safe_application_path(rel: str, *, apps_dir: Path = APPS_DIR) -> Path:
    """Resolve an applications-relative path safely, or raise ValueError.

    Blocks absolute paths, '..'/dot segments, disallowed suffixes, symlink
    escapes, and anything resolving outside apps_dir. An empty suffix is treated
    as a slug directory and allowed.
    """
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


def _atomic_write(rel: str, text: str, *, apps_dir: Path = APPS_DIR) -> Path:
    """Atomically write text to a guarded applications-relative path."""
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


def _write_yaml(rel: str, data: dict, *, apps_dir: Path = APPS_DIR) -> None:
    buf = io.StringIO()
    _yaml.dump(data, buf)
    _atomic_write(rel, buf.getvalue(), apps_dir=apps_dir)


def _schema_errors(data: dict, schema_path: Path) -> list[str]:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    return [
        f"{'/'.join(str(p) for p in e.path) or '<root>'}: {e.message}"
        for e in validator.iter_errors(data)
    ]


# --- profile (evergreen) --------------------------------------------------------


def read_profile(*, apps_dir: Path = APPS_DIR) -> dict:
    """Return the evergreen profile dict, or {} if absent."""
    p = apps_dir / "profile.yaml"
    return _read_yaml(p) if p.exists() else {}


def write_profile(data: dict, *, apps_dir: Path = APPS_DIR) -> None:
    """Validate against profile.schema.json, then atomically write profile.yaml."""
    errors = _schema_errors(data, PROFILE_SCHEMA)
    if errors:
        raise ValueError("invalid profile: " + "; ".join(errors))
    _write_yaml("profile.yaml", data, apps_dir=apps_dir)


# --- applications (per-job) -----------------------------------------------------


def list_applications(*, apps_dir: Path = APPS_DIR) -> list[str]:
    """Sorted slugs (directories only, excluding dotfiles and profile.yaml)."""
    if not apps_dir.exists():
        return []
    return sorted(p.name for p in apps_dir.iterdir() if p.is_dir() and not p.name.startswith("."))


def create_application(slug: str, *, job_text: str, meta: dict, apps_dir: Path = APPS_DIR) -> str:
    """Scaffold applications/<slug>/ with job.md + application.yaml. Returns the slug.

    Refuses to overwrite an existing application. Validation of application.yaml
    is deferred to validate_application (the skill fills it in iteratively).
    """
    slug = _sanitize_slug(slug)
    app_dir = _safe_application_path(slug, apps_dir=apps_dir)
    if app_dir.exists():
        raise FileExistsError(f"application already exists: {slug}")
    app_dir.mkdir(parents=True)
    _atomic_write(f"{slug}/job.md", job_text, apps_dir=apps_dir)
    _write_yaml(f"{slug}/application.yaml", meta, apps_dir=apps_dir)
    return slug


def read_application(slug: str, *, apps_dir: Path = APPS_DIR) -> dict:
    """Bundle {application, job, interview, draft}; missing parts are None."""
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


def save_interview(slug: str, data: dict, *, apps_dir: Path = APPS_DIR) -> None:
    """Validate-light (gap decisions) then atomically write interview.yaml."""
    for gap in data.get("gaps") or []:
        if gap.get("decision") not in _GAP_DECISIONS:
            raise ValueError(
                f"invalid gap decision {gap.get('decision')!r}; expected one of {_GAP_DECISIONS}"
            )
    _write_yaml(f"{_sanitize_slug(slug)}/interview.yaml", data, apps_dir=apps_dir)


def save_draft(slug: str, body: str, *, apps_dir: Path = APPS_DIR) -> None:
    """Atomically write the editable letter body to draft.md."""
    _atomic_write(f"{_sanitize_slug(slug)}/draft.md", body, apps_dir=apps_dir)
