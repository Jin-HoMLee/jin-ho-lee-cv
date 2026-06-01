"""Variant-aware publication rendering policy + aggregate summary.

Shared by the PDF (pdf/build.py), website (scripts/render_web_data.py) and
plain-text (scripts/render_text.py) renderers so all three agree on (a) which
targets show the full per-paper list vs. a one-line aggregate, and (b) the exact
wording of that aggregate. The machine formats (JSON Resume, JSON-LD) bypass this
and always emit the full structured list.
"""
from __future__ import annotations

from dataclasses import dataclass

from scripts.bib_loader import Publication

_PEER_REVIEWED_TYPES = ("article", "book-chapter")  # conference contributions are not
_COAUTHOR = ("middle", "last", "corresponding")      # everything that isn't first/shared
EN_DASH = "–"


def publication_mode(target: str) -> str:
    """Return "full" for the academic variant, "aggregate" for everyone else.

    comp-bio foregrounds the verbatim list; bridge/ds-ml collapse it to a derived
    summary line + ORCID pointer (de-emphasize-don't-delete).
    """
    # Any target other than comp-bio is treated as aggregate (safe default).
    return "full" if target == "comp-bio" else "aggregate"


@dataclass(frozen=True)
class PublicationSummary:
    peer_reviewed: int   # research articles + book chapters
    pr_first: int        # …of which first-author
    pr_shared: int       # …shared-first
    pr_coauthor: int     # …co-author (middle/last/corresponding)
    conferences: int     # research conference contributions (all first-author)
    year_start: int
    year_end: int


def publication_summary(pubs: list[Publication]) -> PublicationSummary:
    """Derive the honest, type-segmented aggregate from the research publications.

    Only ``category == "research"`` entries are summarized (the lone applied piece
    is off-domain and excluded). Peer-reviewed = research articles + book chapters;
    conference contributions are counted separately. ``pr_coauthor`` folds
    middle/last/corresponding. The span is the research-body min/max year.
    """
    if not pubs:
        raise ValueError("publication_summary() requires at least one publication")
    research = [p for p in pubs if p.category == "research"]
    peer = [p for p in research if p.type in _PEER_REVIEWED_TYPES]
    years = [p.year for p in research] or [p.year for p in pubs]
    return PublicationSummary(
        peer_reviewed=len(peer),
        pr_first=sum(1 for p in peer if p.authorship == "first"),
        pr_shared=sum(1 for p in peer if p.authorship == "shared"),
        pr_coauthor=sum(1 for p in peer if p.authorship in _COAUTHOR),
        conferences=sum(1 for p in research if p.type == "conference"),
        year_start=min(years),
        year_end=max(years),
    )


def format_publication_summary(template: str, pubs: list[Publication]) -> str:
    """Fill a resolved (single-language) label template with derived figures.

    The template owns the prose + per-language word order; only the derived counts
    and the span are substituted, so nothing is hardcoded. The template may
    reference only these named fields: peer_reviewed, pr_first, pr_shared,
    pr_coauthor, conferences, span.
    """
    s = publication_summary(pubs)
    span = f"{s.year_start}{EN_DASH}{s.year_end}"
    return template.format(
        peer_reviewed=s.peer_reviewed, pr_first=s.pr_first, pr_shared=s.pr_shared,
        pr_coauthor=s.pr_coauthor, conferences=s.conferences, span=span,
    )
