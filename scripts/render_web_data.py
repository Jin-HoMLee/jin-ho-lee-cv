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
    """Return the web-rendered positioning fields that differ from bridge.

    Reads from the *nested* resolved tree (not top level):
      headline       <- personal.headline   (rendered in the sticky header)
      tagline        <- profile.tagline      (rendered in the profile intro)
      lead_paragraph <- profile.paragraphs[0] (the lead; paragraphs[1] is shared)

    A key is included only when the variant value differs from bridge.
    `selected_projects` is intentionally excluded: the website renders projects
    grouped by category and never consumes it, so emitting it produced a
    payload of the one field the web ignores while dropping the three it shows.

    Args:
        bridge: Fully-resolved bridge tree.
        variant: Fully-resolved variant tree.

    Returns:
        Dict with only the differing text fields; empty dict if none differ.
    """
    overrides: dict[str, str] = {}

    b_headline = bridge.get("personal", {}).get("headline")
    v_headline = variant.get("personal", {}).get("headline")
    if v_headline is not None and v_headline != b_headline:
        overrides["headline"] = v_headline

    b_tagline = bridge.get("profile", {}).get("tagline")
    v_tagline = variant.get("profile", {}).get("tagline")
    if v_tagline is not None and v_tagline != b_tagline:
        overrides["tagline"] = v_tagline

    b_paras = bridge.get("profile", {}).get("paragraphs") or []
    v_paras = variant.get("profile", {}).get("paragraphs") or []
    b_lead = b_paras[0] if b_paras else None
    v_lead = v_paras[0] if v_paras else None
    if v_lead is not None and v_lead != b_lead:
        overrides["lead_paragraph"] = v_lead

    return overrides


def render_web_data(*, content_dir: Path = CONTENT_DIR, output_dir: Path = OUTPUT_DIR) -> None:
    """Render content.{en,de}.json and content.{en,de}.variants.json into output_dir.

    `private_path` is HARD-CODED to None — the web site must never see PII.
    Tests assert this contract.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Render bridge JSON
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

    # Render variants metadata
    for lang in LANGS:
        variants_dict = {}
        bridge_tree = load_content(content_dir, private_path=None, lang=lang, target="bridge")
        bridge_resolved = resolve_langstrings(bridge_tree, lang=lang)
        
        for target in ["comp-bio", "ds-ml"]:
            variant_tree = load_content(content_dir, private_path=None, lang=lang, target=target)
            variant_resolved = resolve_langstrings(variant_tree, lang=lang)
            overrides = _extract_overrides(bridge_resolved, variant_resolved)
            variants_dict[target] = overrides
        
        jsonable_variants = _to_jsonable(variants_dict)
        out_path = output_dir / f"content.{lang}.variants.json"
        out_path.write_text(
            json.dumps(jsonable_variants, indent=2, sort_keys=False, ensure_ascii=False) + "\n",
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
