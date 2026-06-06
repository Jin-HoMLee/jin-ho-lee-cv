"""CLI: print the advisory JD↔CV keyword-gap report for an application slug.

Wraps cover_letter_core.jd_keyword_gap so `just jd-gap <slug>` works. The output is
an ADVISORY CHECKLIST, not a verdict: 'evidenced' terms are JD words the CV can back
(emphasize them); 'gaps' are JD words with no CV match (review — a term appearing
literally nowhere in the CV is a "do not claim this" anti-fabrication flag). The list
deliberately over-surfaces; prune the false alarms by hand.
"""

from __future__ import annotations

import argparse
import sys

from scripts.cover_letter_core import jd_keyword_gap


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jd_gap", description=__doc__)
    parser.add_argument("slug", help="Application slug (folder under applications/)")
    args = parser.parse_args(argv)

    try:
        report = jd_keyword_gap(args.slug)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print("EVIDENCED — JD terms your CV can back (emphasize these):")
    for term in report["evidenced"]:
        print(f"  + {term}")
    print("\nGAPS — JD terms with no CV match (review; a term absent everywhere = do not claim):")
    for term in report["gaps"]:
        print(f"  ? {term}")
    print("\n(Advisory checklist, not a verdict — it over-surfaces; prune false alarms.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
