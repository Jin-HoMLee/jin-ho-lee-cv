"""Load the gitignored master-cv/ overlay (the unfiltered life-database superset).

Mirrors the content.private/ pattern: present on the user's machine, never committed,
gracefully absent (returns None) on CI and fresh clones. Path resolves from the
MASTER_CV_DIR env (default <repo>/master-cv) so tests point it at a fixture overlay —
the same override shape as CV_PRIVATE_YAML.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from ruamel.yaml import YAML

yaml = YAML(typ="safe")

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DIR = REPO_ROOT / "master-cv"


@dataclass(frozen=True)
class MasterCV:
    timeline: list[dict]
    inventory: dict[str, list[str]]
    narrative: dict[str, str]  # filename stem -> markdown text
    opinions: str | None = None  # raw opinions.md text; None when absent


def _resolve_dir(path: Path | None) -> Path:
    if path is not None:
        return Path(path)
    env = os.environ.get("MASTER_CV_DIR")
    return Path(env) if env else DEFAULT_DIR


def load_master_cv(path: Path | None = None) -> MasterCV | None:
    """Parse the overlay dir; return None when it is absent."""
    base = _resolve_dir(path)
    if not base.is_dir():
        return None

    timeline: list[dict] = []
    tl = base / "timeline.yaml"
    if tl.exists():
        timeline = yaml.load(tl.read_text(encoding="utf-8")) or []

    inventory: dict[str, list[str]] = {}
    iv = base / "inventory.yaml"
    if iv.exists():
        inventory = yaml.load(iv.read_text(encoding="utf-8")) or {}

    narrative: dict[str, str] = {}
    nd = base / "narrative"
    if nd.is_dir():
        for md in sorted(nd.glob("*.md")):
            narrative[md.stem] = md.read_text(encoding="utf-8")

    opinions: str | None = None
    op = base / "opinions.md"
    if op.exists():
        opinions = op.read_text(encoding="utf-8")

    return MasterCV(
        timeline=timeline, inventory=inventory, narrative=narrative, opinions=opinions
    )
