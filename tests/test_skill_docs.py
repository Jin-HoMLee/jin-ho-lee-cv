"""Drift-guards for the CV skill docs (no mcp dependency)."""
from __future__ import annotations

import re
from pathlib import Path

from scripts import agent_core

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO_ROOT / ".claude" / "skills" / "cv"
JUSTFILE = REPO_ROOT / "justfile"


def _justfile_recipes() -> set[str]:
    recipes = set()
    for line in JUSTFILE.read_text(encoding="utf-8").splitlines():
        if line[:1].isspace() or line.startswith("#"):
            continue
        m = re.match(r"^([a-z][a-z0-9-]*)(\s+[^:]*)?:", line)
        if m:
            recipes.add(m.group(1))
    return recipes


def _docs_text() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in SKILL_DIR.glob("*.md"))


def test_skill_docs_exist():
    assert (SKILL_DIR / "SKILL.md").is_file()
    assert (SKILL_DIR / "reference.md").is_file()


def test_skill_recipes_exist():
    referenced = set(re.findall(r"just ([a-z][a-z0-9-]*)", _docs_text()))
    missing = referenced - _justfile_recipes()
    assert not missing, f"skill docs reference unknown just recipes: {missing}"


def test_skill_documents_all_sections():
    ref = (SKILL_DIR / "reference.md").read_text(encoding="utf-8")
    missing = [s for s in agent_core.SECTIONS if s not in ref]
    assert not missing, f"reference.md is missing sections: {missing}"


def test_skill_frontmatter_has_name_and_description():
    text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    assert text.startswith("---")
    fm = text.split("---", 2)[1]
    assert re.search(r"^name:\s*\S", fm, re.M)
    assert re.search(r"^description:\s*\S", fm, re.M)
