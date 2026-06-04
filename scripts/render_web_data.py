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
from scripts.citations import enrich_publications, load_citation_cache
from scripts.content_loader import load_content
from scripts.langstring import resolve_langstrings
from scripts.publications import format_publication_summary


REPO_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = REPO_ROOT / "content"
OUTPUT_DIR = REPO_ROOT / "web" / "src" / "data"
CITATIONS_PATH = REPO_ROOT / "data" / "citations.json"
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
      headline         <- personal.headline      (rendered in the sticky header)
      tagline          <- profile.tagline         (rendered in the profile intro)
      lead_paragraph   <- profile.paragraphs[0]   (the lead profile paragraph)
      second_paragraph <- profile.paragraphs[1]   (the second profile paragraph)

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

    b_second = b_paras[1] if len(b_paras) > 1 else None
    v_second = v_paras[1] if len(v_paras) > 1 else None
    if v_second is not None and v_second != b_second:
        overrides["second_paragraph"] = v_second

    return overrides


def render_web_data(
    *,
    content_dir: Path = CONTENT_DIR,
    output_dir: Path = OUTPUT_DIR,
    citations_path: Path = CITATIONS_PATH,
) -> None:
    """Render content.{en,de}.json and content.{en,de}.variants.json into output_dir.

    `private_path` is HARD-CODED to None — the web site must never see PII.
    Tests assert this contract.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    def _dump(obj: Any, filename: str) -> None:
        out_path = output_dir / filename
        out_path.write_text(
            json.dumps(_to_jsonable(obj), indent=2, sort_keys=False, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        try:
            display = out_path.relative_to(REPO_ROOT)
        except ValueError:
            display = out_path
        print(f"wrote {display}")

    citations = load_citation_cache(citations_path)  # parse once; reused across languages
    for lang in LANGS:
        # Load bridge once: it is both the site's static content and the baseline
        # against which variant overrides are diffed.
        bridge_resolved = resolve_langstrings(
            load_content(content_dir, private_path=None, lang=lang, target="bridge"),
            lang=lang,
        )
        bridge_resolved["publications"] = enrich_publications(
            bridge_resolved["publications"], citations
        )
        pub_labels = bridge_resolved["labels"]["publications"]
        bridge_resolved["publications_aggregate"] = {
            "summary": format_publication_summary(
                pub_labels["summary"], bridge_resolved["publications"]
            ),
            "pointer": pub_labels["full_list_pointer"],
        }
        _dump(bridge_resolved, f"content.{lang}.json")

        variants_dict = {}
        for target in ("comp-bio", "ds-ml"):
            variant_resolved = resolve_langstrings(
                load_content(content_dir, private_path=None, lang=lang, target=target),
                lang=lang,
            )
            variants_dict[target] = _extract_overrides(bridge_resolved, variant_resolved)
        _dump(variants_dict, f"content.{lang}.variants.json")


def main() -> int:
    render_web_data()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
