"""Drift-guards for the cover-letter skill docs (justfile recipes + schema fields)."""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO_ROOT / ".claude" / "skills" / "cover-letter"
JUSTFILE = REPO_ROOT / "justfile"
SCHEMA_DIR = REPO_ROOT / "schema"


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


def _schema_props(name: str) -> set[str]:
    schema = json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))
    return set(schema.get("properties", {}))


def test_skill_docs_exist():
    assert (SKILL_DIR / "SKILL.md").is_file()
    assert (SKILL_DIR / "reference.md").is_file()


def test_skill_recipes_exist():
    referenced = set(re.findall(r"just ([a-z][a-z0-9-]*)", _docs_text()))
    missing = referenced - _justfile_recipes()
    assert not missing, f"skill docs reference unknown just recipes: {missing}"


def test_skill_documents_application_fields():
    ref = (SKILL_DIR / "reference.md").read_text(encoding="utf-8")
    missing = [f for f in _schema_props("application.schema.json") if f not in ref]
    assert not missing, f"reference.md is missing application fields: {missing}"


def test_skill_documents_profile_fields():
    ref = (SKILL_DIR / "reference.md").read_text(encoding="utf-8")
    missing = [f for f in _schema_props("profile.schema.json") if f not in ref]
    assert not missing, f"reference.md is missing profile fields: {missing}"


def test_skill_frontmatter_has_name_and_description():
    text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    assert text.startswith("---")
    fm = text.split("---", 2)[1]
    assert re.search(r"^name:\s*\S", fm, re.M)
    assert re.search(r"^description:\s*\S", fm, re.M)
