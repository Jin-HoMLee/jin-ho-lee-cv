"""Tests for the PDF publications section (issue #43)."""
from pdf.build import prepare_data, select_publications
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


def test_prepare_data_bridge_selects_nine_with_selected_heading(content_dir):
    result = prepare_data(content_dir, private_path=None, lang="en", target="bridge")
    assert len(result["publications"]) == 9
    assert result["publications_heading"] == "Publications (selected)"
    assert all(p["authorship"] in ("first", "shared") for p in result["publications"])


def test_prepare_data_comp_bio_selects_all_with_plain_heading(content_dir):
    result = prepare_data(content_dir, private_path=None, lang="en", target="comp-bio")
    assert len(result["publications"]) == 15
    assert result["publications_heading"] == "Publications"


def test_prepare_data_ds_ml_selects_nine(content_dir):
    result = prepare_data(content_dir, private_path=None, lang="en", target="ds-ml")
    assert len(result["publications"]) == 9
    assert result["publications_heading"] == "Publications (selected)"


def test_prepare_data_publications_heading_localized_de(content_dir):
    bridge = prepare_data(content_dir, private_path=None, lang="de", target="bridge")
    comp = prepare_data(content_dir, private_path=None, lang="de", target="comp-bio")
    assert bridge["publications_heading"] == "Publikationen (ausgewählte)"
    assert comp["publications_heading"] == "Publikationen"


def test_prepare_data_publication_entries_have_render_fields(content_dir):
    result = prepare_data(content_dir, private_path=None, lang="en", target="bridge")
    entry = result["publications"][0]
    for field in ("title", "authors", "year", "doi", "venue", "authorship"):
        assert field in entry
    assert isinstance(entry["authors"], list)
