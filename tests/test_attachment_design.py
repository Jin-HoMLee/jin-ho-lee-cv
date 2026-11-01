"""Drift guards for the shared candidate-attachment Typst design system."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SHARED = REPO_ROOT / "pdf/templates/attachment.typ"
VARIANTS = (
    REPO_ROOT / "pdf/templates/cover-letter.typ",
    REPO_ROOT / "pdf/templates/publication-list.typ",
)


def test_attachment_variants_use_shared_primitives():
    shared = SHARED.read_text(encoding="utf-8")
    assert "attachment-document" in shared
    assert "attachment-masthead" in shared
    assert "attachment-section" in shared
    for variant in VARIANTS:
        source = variant.read_text(encoding="utf-8")
        assert '#import "attachment.typ": *' in source
        assert "#attachment-document(" in source


def test_attachment_variants_do_not_redeclare_visual_tokens():
    shared = SHARED.read_text(encoding="utf-8")
    for token in (
        '#let attachment-ink = rgb("#25384a")',
        '#let attachment-blue = rgb("#55718c")',
        '#let attachment-gold = rgb("#a17a45")',
        '#let attachment-sand = rgb("#f6f0e5")',
        '#let attachment-pale-blue = rgb("#edf2f5")',
        'attachment-font = "IBM Plex Sans"',
    ):
        assert token in shared
    for variant in VARIANTS:
        source = variant.read_text(encoding="utf-8")
        assert 'rgb("#' not in source
        assert 'font: "IBM Plex Sans"' not in source


def test_attachment_contract_keeps_semantic_and_privacy_guards():
    letter = (REPO_ROOT / "pdf/templates/cover-letter.typ").read_text(encoding="utf-8")
    publication_list = (REPO_ROOT / "pdf/templates/publication-list.typ").read_text(
        encoding="utf-8"
    )
    assert "letter.include_phone" in letter
    assert "show-phone: letter.include_phone" in letter
    assert "publication.doi" in publication_list
    assert "attachment-publication-meta" in publication_list
    assert "bookmarked: true" in SHARED.read_text(encoding="utf-8")
