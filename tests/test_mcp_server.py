"""Tests for the thin MCP server (skipped if the mcp SDK is absent)."""

from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("mcp")

from scripts import agent_core, mcp_server  # noqa: E402

EXPECTED_TOOLS = {
    "get_cv_content",
    "list_cv_files",
    "validate_cv",
    "propose_edit",
    "apply_edit",
    "rerun_renderers",
}


def _tools():
    return {t.name: t for t in asyncio.run(mcp_server.mcp.list_tools())}


def test_tools_listed():
    assert set(_tools()) == EXPECTED_TOOLS


def test_tool_annotations():
    tools = _tools()
    for name in ("get_cv_content", "list_cv_files", "validate_cv", "propose_edit"):
        ann = tools[name].annotations
        assert ann.readOnlyHint is True
        assert ann.destructiveHint is False
        assert ann.idempotentHint is True
        assert ann.openWorldHint is False
    assert tools["apply_edit"].annotations.readOnlyHint is False
    assert tools["apply_edit"].annotations.destructiveHint is True
    assert tools["apply_edit"].annotations.idempotentHint is False
    assert tools["rerun_renderers"].annotations.readOnlyHint is False
    assert tools["rerun_renderers"].annotations.idempotentHint is True


def test_get_cv_content_returns_tree():
    out = mcp_server.get_cv_content()
    assert isinstance(out, dict) and "personal" in out


def test_core_server_parity():
    rel = "personal.yaml"
    current = (agent_core.CONTENT_DIR / rel).read_text(encoding="utf-8")
    server = mcp_server.propose_edit(rel, current).model_dump()
    core = agent_core.propose_edit(rel, current)
    assert server == core
    # get_cv_content is a thin pass-through to read_cv — assert byte-identical too.
    assert mcp_server.get_cv_content() == agent_core.read_cv()
