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
_COAUTHOR = ("middle", "last", "corresponding")  # everything that isn't first/shared
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
    """Numeric publication facts shared by every human-readable renderer.

    ``total_records`` is the complete BibTeX inventory.  The research subset is
    split into peer-reviewed records and conference contributions; the applied
    subset is deliberately kept out of the research prose.  The two authorship
    views are both retained because the web chart intentionally shows all records,
    while the aggregate sentence describes peer-reviewed research only.
    """

    total_records: int
    research_records: int
    peer_reviewed: int  # research articles + book chapters
    peer_reviewed_articles: int
    peer_reviewed_book_chapters: int
    pr_first: int  # …of which first-author
    pr_shared: int  # …shared-first
    pr_coauthor: int  # …co-author (middle/last/corresponding)
    conferences: int  # research conference contributions (all first-author)
    applied_records: int
    all_first: int
    all_shared: int
    all_coauthor: int
    year_start: int
    year_end: int

    @property
    def research_conferences(self) -> int:
        """Readable alias for the legacy ``conferences`` field."""
        return self.conferences


def publication_summary(pubs: list[Publication]) -> PublicationSummary:
    """Derive the honest, type-segmented aggregate from the BibTeX records.

    Peer-reviewed = research articles + research book chapters; conference
    contributions and the applied/off-domain record are counted separately.
    ``pr_coauthor`` and ``all_coauthor`` fold middle/last/corresponding authorship.
    The span is the research-body min/max year.
    """
    if not pubs:
        raise ValueError("publication_summary() requires at least one publication")
    research = [p for p in pubs if p.category == "research"]
    peer = [p for p in research if p.type in _PEER_REVIEWED_TYPES]
    years = [p.year for p in research] or [p.year for p in pubs]
    return PublicationSummary(
        total_records=len(pubs),
        research_records=len(research),
        peer_reviewed=len(peer),
        peer_reviewed_articles=sum(1 for p in peer if p.type == "article"),
        peer_reviewed_book_chapters=sum(1 for p in peer if p.type == "book-chapter"),
        pr_first=sum(1 for p in peer if p.authorship == "first"),
        pr_shared=sum(1 for p in peer if p.authorship == "shared"),
        pr_coauthor=sum(1 for p in peer if p.authorship in _COAUTHOR),
        conferences=sum(1 for p in research if p.type == "conference"),
        applied_records=sum(1 for p in pubs if p.category == "applied"),
        all_first=sum(1 for p in pubs if p.authorship == "first"),
        all_shared=sum(1 for p in pubs if p.authorship == "shared"),
        all_coauthor=sum(1 for p in pubs if p.authorship in _COAUTHOR),
        year_start=min(years),
        year_end=max(years),
    )


def publication_metrics(pubs: list[Publication]) -> dict[str, object]:
    """Return the generated numeric object consumed by the website and PDF.

    Keeping this object next to the BibTeX policy prevents a renderer from parsing
    prose or reimplementing the category arithmetic.  The chart scope is explicit:
    it is an all-record authorship view, not the peer-reviewed research view.
    """
    s = publication_summary(pubs)
    return {
        "total_records": s.total_records,
        "research_records": s.research_records,
        "peer_reviewed_records": s.peer_reviewed,
        "peer_reviewed_articles": s.peer_reviewed_articles,
        "peer_reviewed_book_chapters": s.peer_reviewed_book_chapters,
        "research_conferences": s.research_conferences,
        "applied_records": s.applied_records,
        "peer_reviewed_authorship": {
            "first": s.pr_first,
            "shared_first": s.pr_shared,
            "coauthor": s.pr_coauthor,
        },
        "all_records_authorship": {
            "first": s.all_first,
            "shared_first": s.all_shared,
            "coauthor": s.all_coauthor,
        },
        "chart_scope": "all-records",
    }


def format_publication_summary(template: str, pubs: list[Publication]) -> str:
    """Fill a resolved (single-language) label template with derived figures.

    The template owns the prose + per-language word order; only derived counts and
    the span are substituted, so nothing is hardcoded in a renderer.
    """
    s = publication_summary(pubs)
    span = f"{s.year_start}{EN_DASH}{s.year_end}"
    return template.format(
        total_records=s.total_records,
        research_records=s.research_records,
        peer_reviewed=s.peer_reviewed,
        peer_reviewed_articles=s.peer_reviewed_articles,
        peer_reviewed_book_chapters=s.peer_reviewed_book_chapters,
        pr_first=s.pr_first,
        pr_shared=s.pr_shared,
        pr_coauthor=s.pr_coauthor,
        conferences=s.conferences,
        research_conferences=s.research_conferences,
        applied_records=s.applied_records,
        span=span,
    )
