"""Agent-facing core: read, validate, propose/apply edits, re-render the CV.

Shared foundation for the MCP server (scripts/mcp_server.py) and the Claude
skill (.claude/skills/cv/). Pure Python, no MCP/CLI coupling. Every path / PII /
subprocess guard lives here so both surfaces inherit it.
"""
from __future__ import annotations

from pathlib import Path, PurePosixPath

from scripts.content_loader import TARGETS, load_content
from scripts.langstring import resolve_langstrings
from scripts.render_web_data import _to_jsonable

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = REPO_ROOT / "content"
SCHEMA_PATH = REPO_ROOT / "schema" / "cv.schema.json"

SECTIONS = (
    "personal", "profile", "skills", "education", "experience", "projects",
    "selected_projects", "languages", "volunteer", "awards", "publications", "labels",
)


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
