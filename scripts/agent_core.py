"""Agent-facing core: read, validate, propose/apply edits, re-render the CV.

Shared foundation for the MCP server (scripts/mcp_server.py) and the Claude
skill (.claude/skills/cv/). Pure Python, no MCP/CLI coupling. Every path / PII /
subprocess guard lives here so both surfaces inherit it.
"""
from __future__ import annotations

from pathlib import Path, PurePosixPath

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = REPO_ROOT / "content"
SCHEMA_PATH = REPO_ROOT / "schema" / "cv.schema.json"


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
