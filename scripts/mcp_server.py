"""Thin MCP server exposing the CV agent core over stdio (FastMCP).

Each tool maps 1:1 to scripts.agent_core; the only added logic is Pydantic
result shaping and MCP tool annotations. Run: `uv run --group mcp python -m scripts.mcp_server`.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel

from scripts import agent_core

mcp = FastMCP("jin-ho-lee-cv")


class ProposeResult(BaseModel):
    diff: str
    valid: bool
    errors: list[str]
    warnings: list[str]


class ApplyResult(BaseModel):
    applied: bool
    errors: list[str]
    warnings: list[str]


class ValidateResult(BaseModel):
    valid: bool
    errors: list[str]
    warnings: list[str]


class RenderResult(BaseModel):
    ran: list[str]
    ok: bool
    skipped: list[str]
    output: dict[str, str]


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False
    )
)
def get_cv_content(lang: str = "en", target: str = "bridge", section: str | None = None) -> dict:
    """Load the CV content tree (LangStrings resolved) for a language and target variant."""
    return agent_core.read_cv(lang=lang, target=target, section=section)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False
    )
)
def list_cv_files() -> list[str]:
    """List the editable content YAML files as content-relative paths."""
    return agent_core.list_content_files()


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False
    )
)
def validate_cv() -> ValidateResult:
    """Validate the current content tree (schema + cross-refs + parity + periods + bib)."""
    return ValidateResult(**agent_core.validate_cv())


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False
    )
)
def propose_edit(path: str, new_content: str) -> ProposeResult:
    """Dry-run an edit: return a unified diff + full-tree validation. Writes nothing."""
    return ProposeResult(**agent_core.propose_edit(path, new_content))


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=False
    )
)
def apply_edit(path: str, new_content: str) -> ApplyResult:
    """Validate then write an edit to content/. Refuses if the tree would not validate."""
    return ApplyResult(**agent_core.apply_edit(path, new_content))


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False
    )
)
def rerun_renderers(which: str = "formats") -> RenderResult:
    """Re-run renderers (formats|pdf|web|all); validate-first, skip pdf/web if tools absent."""
    return RenderResult(**agent_core.rerun_renderers(which))


def run() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    run()
