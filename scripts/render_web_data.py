"""Render bilingual content JSON for the Astro website.

Produces web/src/data/content.{en,de}.json by composing:
  - scripts.content_loader.load_content (with private_path HARD-CODED to None)
  - scripts.langstring.resolve_langstrings (to flatten langmaps to chosen lang)
  - Publication dataclass → dict conversion
  - Path → str conversion
"""
from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any

from scripts.bib_loader import Publication
from scripts.content_loader import load_content
from scripts.langstring import resolve_langstrings


REPO_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = REPO_ROOT / "content"
OUTPUT_DIR = REPO_ROOT / "web" / "src" / "data"
LANGS = ("en", "de")


def _to_jsonable(obj: Any) -> Any:
    """Recursively convert Publication dataclasses and Path objects to JSON-native types."""
    if isinstance(obj, Publication):
        d = dataclasses.asdict(obj)
        d.pop("raw", None)  # drop bibtex-specific field; not needed for rendering
        # asdict converts tuple → list; that's what we want for JSON
        return _to_jsonable(d)
    if isinstance(obj, Path):
        return obj.as_posix()
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(item) for item in obj]
    return obj


def _extract_overrides(bridge: dict, variant: dict) -> dict:
    """Return only the fields that differ between bridge and variant.
    
    Args:
        bridge: Fully-resolved bridge tree (all keys present)
        variant: Fully-resolved variant tree (all keys present)
    
    Returns:
        Dict with only the keys that differ; empty dict if identical.
    """
    OVERRIDE_KEYS = {"headline", "tagline", "lead_paragraph", "selected_projects"}
    overrides = {}
    for key in OVERRIDE_KEYS:
        bridge_val = bridge.get(key)
        variant_val = variant.get(key)
        if bridge_val != variant_val:
            overrides[key] = variant_val
    return overrides


def render_web_data(*, content_dir: Path = CONTENT_DIR, output_dir: Path = OUTPUT_DIR) -> None:
    """Render content.{en,de}.json into output_dir.

    `private_path` is HARD-CODED to None — the web site must never see PII.
    Tests assert this contract.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    for lang in LANGS:
        tree = load_content(content_dir, private_path=None, lang=lang)
        resolved = resolve_langstrings(tree, lang=lang)
        jsonable = _to_jsonable(resolved)
        out_path = output_dir / f"content.{lang}.json"
        out_path.write_text(
            json.dumps(jsonable, indent=2, sort_keys=False, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        try:
            display = out_path.relative_to(REPO_ROOT)
        except ValueError:
            display = out_path
        print(f"wrote {display}")


def main() -> int:
    render_web_data()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
