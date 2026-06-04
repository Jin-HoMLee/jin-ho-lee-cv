"""Fetch Crossref citation counts for publication DOIs → data/citations.json.

The ONLY networked code in the project. Run manually via `just refresh-citations`; never on
the build path (CI/builds read the committed cache offline and deterministically). Uses
Crossref's key-free REST API and joins the polite pool via a User-Agent carrying the CV's
public contact email (read from content — single source of truth).

Crossref counts lag and undercount relative to Google Scholar; web and JSON-LD consumers
label the figures "indicative" to avoid overstating them.
"""

from __future__ import annotations

import datetime
import json
import sys
import urllib.request
from pathlib import Path
from typing import Callable

from scripts.bib_loader import load_publications
from scripts.citations import load_citation_cache
from scripts.config import PAGES_BASE_URL
from scripts.content_loader import load_content

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = REPO_ROOT / "content"
BIB_PATH = CONTENT_DIR / "publications.bib"
CACHE_PATH = REPO_ROOT / "data" / "citations.json"
CROSSREF_WORK_URL = "https://api.crossref.org/works/{doi}"
TIMEOUT_S = 30


def _user_agent(mailto: str) -> str:
    """Crossref polite-pool identifier (see crossref.org REST API docs)."""
    return f"jin-ho-lee-cv/1.0 (+{PAGES_BASE_URL}; mailto:{mailto})"


def fetch_citation_count(
    doi: str, *, mailto: str, opener: Callable = urllib.request.urlopen
) -> int:
    """GET Crossref's is-referenced-by-count for one DOI. Raises on any failure.

    `opener` is injectable so tests can supply a fake response without hitting the network.
    """
    req = urllib.request.Request(
        CROSSREF_WORK_URL.format(doi=doi),
        headers={"User-Agent": _user_agent(mailto)},
    )
    with opener(req, timeout=TIMEOUT_S) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return int(payload["message"]["is-referenced-by-count"])


def build_counts(
    dois: list[str], *, fetch: Callable[[str], int], prior: dict[str, int]
) -> dict[str, int]:
    """Fetch each DOI; on per-DOI error, RETAIN the prior cached value (never clobber).

    A DOI that both fails AND has no prior value is omitted. Per-DOI failures are logged to
    stderr (this is the manual operator path) so a silently-retained stale value is visible.
    Callers sort keys on write.
    """
    counts: dict[str, int] = {}
    for doi in dois:
        try:
            counts[doi] = fetch(doi)
        except Exception as exc:
            if doi in prior:
                counts[doi] = prior[doi]
                print(f"  retained prior count for {doi} (fetch failed: {exc})", file=sys.stderr)
            else:
                print(f"  no count for {doi} (fetch failed, no prior): {exc}", file=sys.stderr)
    return counts


def refresh(
    *,
    bib_path: Path = BIB_PATH,
    cache_path: Path = CACHE_PATH,
    content_dir: Path = CONTENT_DIR,
    fetch: Callable[[str], int] | None = None,
    today: str | None = None,
) -> dict:
    """Build the cache document, write it to cache_path, and return it."""
    # Read the CV owner's email from content (single source of truth for contact info).
    mailto = load_content(content_dir, lang="en")["personal"]["email"]
    if fetch is None:
        # Nested name differs from the `fetch` param to avoid any redefinition ambiguity.
        def _default_fetch(doi: str) -> int:
            return fetch_citation_count(doi, mailto=mailto)

        fetch = _default_fetch

    dois = [p.doi for p in load_publications(bib_path) if p.doi]
    prior = load_citation_cache(cache_path)
    counts = build_counts(dois, fetch=fetch, prior=prior)
    doc = {
        "_generated_by": "just refresh-citations — do not hand-edit",
        "source": "crossref",
        "fetched_at": today or datetime.date.today().isoformat(),
        "counts": {doi: counts[doi] for doi in sorted(counts)},
    }
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return doc


def main() -> int:
    doc = refresh()
    print(f"wrote {CACHE_PATH.relative_to(REPO_ROOT)} ({len(doc['counts'])} DOIs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
