"""Citation-count enrichment: read the committed Crossref cache, attach counts to publications.

The cache (data/citations.json) is a generated, committed lockfile produced by
scripts/fetch_citations.py (`just refresh-citations`). This module is the ONLY reader of
that cache and never touches the network — every renderer enriches offline and degrades
gracefully when a DOI (or the whole cache) is absent.
"""
from __future__ import annotations

import dataclasses
import json
from pathlib import Path

from scripts.bib_loader import Publication


def load_citation_cache(path: Path) -> dict[str, int]:
    """Read the committed citation cache → {doi: count}.

    A missing or unparseable file (or a malformed ``counts`` block) yields an empty dict —
    the offline-degrade contract: renderers then emit no counts rather than failing.
    """
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {}
    if not isinstance(raw, dict):
        return {}
    counts = raw.get("counts", {})
    if not isinstance(counts, dict):
        return {}
    return {
        str(doi): n
        for doi, n in counts.items()
        if isinstance(n, int) and not isinstance(n, bool)
    }


def enrich_publications(pubs: list[Publication], cache: dict[str, int]) -> list[Publication]:
    """Return NEW Publication records with citation_count set from the cache by DOI.

    A publication whose DOI is absent from the cache (or which has no DOI) keeps
    citation_count=None. Inputs are never mutated (Publication is frozen).
    """
    out: list[Publication] = []
    for p in pubs:
        count = cache.get(p.doi) if p.doi else None
        out.append(dataclasses.replace(p, citation_count=count))
    return out
