"""Tests for the PDF publications section (issue #43)."""
from pdf.build import select_publications
from scripts.bib_loader import Publication


def _pub(authorship, key="k", title="T", authors=("Lee, J.",)):
    """Minimal Publication record for exercising select_publications()."""
    return Publication(
        key=key,
        title=title,
        year=2020,
        type="article",
        authorship=authorship,
        authors=authors,
        venue="V",
        doi=None,
        raw={},
        category="research",
    )


def test_select_publications_comp_bio_returns_all_unselected():
    pubs = [_pub("first"), _pub("shared"), _pub("middle")]
    selected, is_selected = select_publications(pubs, "comp-bio")
    assert [p.authorship for p in selected] == ["first", "shared", "middle"]
    assert is_selected is False


def test_select_publications_bridge_keeps_first_and_shared_in_order():
    pubs = [_pub("first", key="a"), _pub("middle", key="b"), _pub("shared", key="c")]
    selected, is_selected = select_publications(pubs, "bridge")
    assert [p.key for p in selected] == ["a", "c"]  # middle dropped, order preserved
    assert is_selected is True


def test_select_publications_ds_ml_keeps_first_and_shared():
    pubs = [_pub("first"), _pub("middle"), _pub("shared")]
    selected, is_selected = select_publications(pubs, "ds-ml")
    assert [p.authorship for p in selected] == ["first", "shared"]
    assert is_selected is True
