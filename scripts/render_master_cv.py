"""Compile content/ + the master-cv/ overlay into dist/master-cv.md.

The single "look up anything about me" artifact: the full union, plainly formatted.
Shares full_profile with render_chat_context (DRY); when the overlay is absent it
degrades to the CV-only blob, exactly like the twin context.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from scripts.bib_loader import load_publications
from scripts.content_loader import load_content
from scripts.langstring import resolve_langstrings
from scripts.master_cv_loader import load_master_cv
from scripts.profile_union import full_profile

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = REPO_ROOT / "content"


def render() -> str:
    content = resolve_langstrings(load_content(CONTENT_DIR, lang="en"), lang="en")
    pubs = load_publications(CONTENT_DIR / "publications.bib")
    master_cv = load_master_cv()
    return full_profile(content, pubs, master_cv) + "\n"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=REPO_ROOT / "dist" / "master-cv.md")
    args = parser.parse_args(argv)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(), encoding="utf-8")
    try:
        rel = args.output.relative_to(REPO_ROOT)
    except ValueError:
        rel = args.output
    print(f"wrote {rel}")


if __name__ == "__main__":
    main()
