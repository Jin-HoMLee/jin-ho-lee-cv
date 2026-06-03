"""CLI: render a cover letter for an application slug.

Wraps cover_letter_core.render_letter so `just letter <slug>` works. Validates
first; PDF skips gracefully when typst is absent.
"""

from __future__ import annotations

import argparse
import sys

from scripts.cover_letter_core import render_letter


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="render_letter", description=__doc__)
    parser.add_argument("slug", help="Application slug (folder under applications/)")
    parser.add_argument("--fmt", choices=("pdf", "text", "all"), default="all")
    args = parser.parse_args(argv)

    result = render_letter(args.slug, fmt=args.fmt)
    for name in result["rendered"]:
        print(f"wrote applications/{args.slug}/{name}")
    for name in result["skipped"]:
        print(f"skipped {name} (tool unavailable)")
    if not result["ok"]:
        for err in result["errors"]:
            print(f"error: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
