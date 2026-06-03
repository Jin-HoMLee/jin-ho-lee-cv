"""Agent-facing core: read, validate, propose/apply edits, re-render the CV.

Shared foundation for the MCP server (scripts/mcp_server.py) and the Claude
skill (.claude/skills/cv/). Pure Python, no MCP/CLI coupling. Every path / PII /
subprocess guard lives here so both surfaces inherit it.
"""

from __future__ import annotations

import difflib
import io
import os
import shutil
import subprocess
import tempfile
from pathlib import Path, PurePosixPath

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from scripts.content_loader import TARGETS, load_content
from scripts.langstring import resolve_langstrings
from scripts.render_web_data import _to_jsonable
from scripts.validate import date_warnings, validate_tree

_yaml = YAML(typ="safe")

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = REPO_ROOT / "content"
SCHEMA_PATH = REPO_ROOT / "schema" / "cv.schema.json"

SECTIONS = (
    "personal",
    "profile",
    "skills",
    "education",
    "experience",
    "projects",
    "selected_projects",
    "languages",
    "volunteer",
    "awards",
    "publications",
    "labels",
)

# which-group -> ordered (just recipe, required tool on PATH or None)
_RECIPE_PLAN = {
    "formats": [("build-formats", None)],
    "pdf": [("build", "typst"), ("build-de", "typst")],
    "web": [("web-build", "pnpm")],
}


def _safe_content_path(rel_path: str, *, content_dir: Path = CONTENT_DIR) -> Path:
    """Resolve a content-relative path safely, or raise ValueError.

    Blocks absolute paths, '..'/dot segments, non-.yaml targets, symlink escapes
    out of content/, and anything resolving under content.private/.
    """
    pure = PurePosixPath(rel_path)
    if pure.is_absolute() or rel_path.startswith(("/", "\\")):
        raise ValueError(f"path must be relative to content/: {rel_path!r}")
    if any(part in ("..", ".") or part.startswith(".") for part in pure.parts):
        raise ValueError(f"illegal path segment in {rel_path!r}")
    if pure.suffix != ".yaml":
        raise ValueError(f"only .yaml files are editable: {rel_path!r}")
    resolved = (content_dir / rel_path).resolve()
    content_root = content_dir.resolve()
    if content_root != resolved and content_root not in resolved.parents:
        raise ValueError(f"path escapes content/: {rel_path!r}")
    if "content.private" in resolved.parts:
        raise ValueError(f"refusing content.private path: {rel_path!r}")
    return resolved


def read_cv(
    lang: str = "en",
    target: str = "bridge",
    section: str | None = None,
    *,
    content_dir: Path = CONTENT_DIR,
) -> dict:
    """Load the CV content tree (LangStrings resolved, JSON-able), PII excluded.

    Never passes private_path, so content.private/ can never surface. `section`,
    if given, must be one of SECTIONS and returns {section: value}.
    """
    if target not in TARGETS:
        raise ValueError(f"unknown target {target!r}; expected one of {TARGETS}")
    tree = load_content(content_dir, private_path=None, lang=lang, target=target)
    data = _to_jsonable(resolve_langstrings(tree, lang))
    if section is None:
        return data
    if section not in SECTIONS:
        raise ValueError(f"unknown section {section!r}; expected one of {SECTIONS}")
    return {section: data.get(section)}


def list_content_files(*, content_dir: Path = CONTENT_DIR) -> list[str]:
    """List editable content YAML as sorted, content-relative posix paths.

    Excludes content.private/ (even via symlink) and non-.yaml files.
    """
    content_root = content_dir.resolve()
    out: list[str] = []
    for p in content_root.rglob("*.yaml"):
        rp = p.resolve()
        if content_root != rp and content_root not in rp.parents:
            continue
        if "content.private" in rp.parts:
            continue
        out.append(rp.relative_to(content_root).as_posix())
    return sorted(out)


def validate_cv(*, content_dir: Path = CONTENT_DIR, schema_path: Path = SCHEMA_PATH) -> dict:
    """Validate the content tree (schema + cross-refs + parity + periods + bib).

    Returns {"valid": bool, "errors": list[str], "warnings": list[str]}.
    """
    errors = validate_tree(content_dir, schema_path)
    warnings = date_warnings(content_dir)
    return {
        "valid": not errors,
        "errors": [str(e) for e in errors],
        "warnings": [str(w) for w in warnings],
    }


def propose_edit(
    rel_path: str,
    new_content: str,
    *,
    content_dir: Path = CONTENT_DIR,
    schema_path: Path = SCHEMA_PATH,
) -> dict:
    """Dry-run an edit: validate the whole would-be tree, return a diff. No write.

    Returns {"diff": str, "valid": bool, "errors": list[str], "warnings": list[str]}.
    """
    dst_rel = _safe_content_path(rel_path, content_dir=content_dir).relative_to(
        content_dir.resolve()
    )
    target_file = content_dir / dst_rel
    current = target_file.read_text(encoding="utf-8") if target_file.exists() else ""

    # Pre-parse: catch malformed YAML before touching the temp tree so callers
    # always get the documented dict (valid:False) rather than an unhandled exception.
    try:
        _yaml.load(io.StringIO(new_content))
    except YAMLError as exc:
        diff = "".join(
            difflib.unified_diff(
                current.splitlines(keepends=True),
                new_content.splitlines(keepends=True),
                fromfile=dst_rel.as_posix(),
                tofile=dst_rel.as_posix(),
                n=3,
            )
        )
        return {
            "diff": diff,
            "valid": False,
            "errors": [f"YAML parse error: {exc}"],
            "warnings": [],
        }

    with tempfile.TemporaryDirectory() as tmp:
        tmp_content = Path(tmp) / "content"
        shutil.copytree(content_dir, tmp_content)  # content/ only — never PII sibling
        edited = tmp_content / dst_rel
        edited.parent.mkdir(parents=True, exist_ok=True)
        edited.write_text(new_content, encoding="utf-8")
        errors = validate_tree(tmp_content, schema_path)
        warnings = date_warnings(tmp_content)

    diff = "".join(
        difflib.unified_diff(
            current.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=dst_rel.as_posix(),
            tofile=dst_rel.as_posix(),
            n=3,
        )
    )
    return {
        "diff": diff,
        "valid": not errors,
        "errors": [str(e) for e in errors],
        "warnings": [str(w) for w in warnings],
    }


def apply_edit(
    rel_path: str,
    new_content: str,
    *,
    content_dir: Path = CONTENT_DIR,
    schema_path: Path = SCHEMA_PATH,
) -> dict:
    """Validate the would-be tree, then atomically write only if it validates.

    Returns {"applied": bool, "errors": list[str], "warnings": list[str]}.
    """
    result = propose_edit(rel_path, new_content, content_dir=content_dir, schema_path=schema_path)
    if not result["valid"]:
        return {"applied": False, "errors": result["errors"], "warnings": result["warnings"]}

    dst = _safe_content_path(rel_path, content_dir=content_dir)
    dst.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=str(dst.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(new_content)
        os.replace(tmp_path, dst)  # atomic within the same directory
    except BaseException:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise
    return {"applied": True, "errors": [], "warnings": result["warnings"]}


def _resolve_recipes(which: str) -> tuple[list[str], list[str]]:
    """Return (to_run, skipped) recipe names for `which`, honoring tool availability."""
    if which not in {"formats", "pdf", "web", "all"}:
        raise ValueError(f"unknown which {which!r}; expected formats|pdf|web|all")
    groups = ["formats", "pdf", "web"] if which == "all" else [which]
    to_run: list[str] = []
    skipped: list[str] = []
    for group in groups:
        for recipe, tool in _RECIPE_PLAN[group]:
            if tool is not None and shutil.which(tool) is None:
                skipped.append(recipe)
            else:
                to_run.append(recipe)
    return to_run, skipped


def rerun_renderers(
    which: str = "formats",
    *,
    content_dir: Path = CONTENT_DIR,
    schema_path: Path = SCHEMA_PATH,
) -> dict:
    """Validate-first, then run the whitelisted `just` recipes for `which`.

    Renderers always operate on the repo's real content/ (via `just`, cwd=REPO_ROOT);
    `content_dir` only governs the validate-first gate. pdf/web skip gracefully when
    Typst/pnpm are absent; refresh-citations is never invoked.
    Returns {"ran": list[str], "ok": bool, "skipped": list[str], "output": dict[str, str]}.
    """
    to_run, skipped = _resolve_recipes(which)
    errors = validate_tree(content_dir, schema_path)
    if errors:
        return {
            "ran": [],
            "ok": False,
            "skipped": to_run + skipped,
            "output": {"validate": "\n".join(str(e) for e in errors)},
        }
    ran: list[str] = []
    output: dict[str, str] = {}
    ok = True
    for recipe in to_run:
        proc = subprocess.run(
            ["just", recipe],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=600,
            shell=False,
        )
        ran.append(recipe)
        output[recipe] = (proc.stdout or "") + (proc.stderr or "")
        if proc.returncode != 0:
            ok = False
    return {"ran": ran, "ok": ok, "skipped": skipped, "output": output}
