"""Compile the whole public CV into one Markdown context blob for the digital-twin chat.

A richer sibling of render_llms.py: where llms.txt is a slim site map, this is the full
profile + experience + skills + education + project deep-dives + publications that the
chat Worker injects as a system instruction each request. PII-safe by construction — reads only
content/ (never content.private/), mirroring agent_core.read_cv. When a master-cv/ overlay
is present, the full timeline, skill inventory, and personal narrative are appended.
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
    parser.add_argument("--output", type=Path, default=REPO_ROOT / "dist" / "chat-context.md")
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
