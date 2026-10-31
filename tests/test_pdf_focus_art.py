"""Regression tests for approved target-specific PDF focus artwork."""

from pathlib import Path
from xml.etree import ElementTree


REPO_ROOT = Path(__file__).parent.parent
SVG_NS = {"svg": "http://www.w3.org/2000/svg"}


def test_ds_ml_focus_art_matches_final_approved_neural_network_mark():
    root = ElementTree.parse(REPO_ROOT / "pdf/assets/focus-production-ml.svg").getroot()

    assert root.attrib["viewBox"] == "0 0 160 58"
    assert root.attrib["aria-label"] == "Neural-network production ML graph"

    opacity_group = root.find("./svg:g", SVG_NS)
    line_group, node_group = list(opacity_group)
    assert opacity_group.attrib == {"opacity": ".62"}
    assert line_group.attrib == {
        "fill": "none",
        "stroke": "#294b78",
        "stroke-width": "1.15",
        "opacity": ".8",
    }
    assert node_group.attrib == {"fill": "#294b78"}
    assert root.findall(".//svg:rect", SVG_NS) == []
    assert [path.attrib["d"] for path in root.findall(".//svg:path", SVG_NS)] == [
        "M18 14 L58 10 M18 14 L58 23 M18 29 L58 23 M18 29 L58 35 M18 44 L58 35 M18 44 L58 48",
        "M58 10 L103 18 M58 23 L103 18 M58 23 L103 40 M58 35 L103 18 M58 35 L103 40 M58 48 L103 40",
        "M103 18 L139 29 M103 40 L139 29",
    ]
    assert [
        (circle.attrib["cx"], circle.attrib["cy"], circle.attrib["r"])
        for circle in root.findall(".//svg:circle", SVG_NS)
    ] == [
        ("139", "29", "11"),
        ("139", "29", "17"),
        ("18", "14", "2.4"),
        ("18", "29", "2.4"),
        ("18", "44", "2.4"),
        ("58", "10", "2.2"),
        ("58", "23", "2.2"),
        ("58", "35", "2.2"),
        ("58", "48", "2.2"),
        ("103", "18", "2.7"),
        ("103", "40", "2.7"),
        ("139", "29", "3.2"),
    ]


def test_comp_bio_focus_art_matches_website_helix_with_restrained_nodes():
    root = ElementTree.parse(REPO_ROOT / "pdf/assets/focus-genomics.svg").getroot()

    assert root.attrib["viewBox"] == "0 0 500 230"
    assert root.attrib["aria-label"] == "Computational biology DNA helix"
    line_group = root.find("./svg:g", SVG_NS)
    assert line_group is not None
    assert line_group.attrib == {
        "fill": "none",
        "stroke": "#294b78",
        "stroke-width": "2.6",
        "stroke-linecap": "round",
        "stroke-linejoin": "round",
    }
    assert [path.attrib["d"] for path in line_group.findall("./svg:path", SVG_NS)] == [
        "M30 45V185M70 60V170M110 90V140M150 90V140M190 60V170M230 45V185M270 60V170M310 90V140M350 90V140M390 60V170M430 45V185M470 60V170"
    ]
    assert [
        polyline.attrib["points"] for polyline in line_group.findall("./svg:polyline", SVG_NS)
    ] == [
        "30,45 70,60 110,90 150,140 190,170 230,185 270,170 310,140 350,90 390,60 430,45 470,60",
        "30,185 70,170 110,140 150,90 190,60 230,45 270,60 310,90 350,140 390,170 430,185 470,170",
    ]
    rung_path = line_group.findall("./svg:path", SVG_NS)[0]
    assert rung_path.attrib["stroke-width"] == "1.7"

    node_group = root.findall("./svg:g", SVG_NS)[1]
    assert node_group.attrib == {"fill": "#a17a45"}
    nodes = [
        (circle.attrib["cx"], circle.attrib["cy"], circle.attrib["r"])
        for circle in node_group.findall("./svg:circle", SVG_NS)
    ]
    assert len(nodes) == 12
    assert all(radius == "3.2" for _, _, radius in nodes)
    assert {(x, y) for x, y, _ in nodes} == {
        ("30", "45"),
        ("70", "170"),
        ("110", "90"),
        ("150", "90"),
        ("190", "170"),
        ("230", "45"),
        ("270", "170"),
        ("310", "90"),
        ("350", "90"),
        ("390", "170"),
        ("430", "45"),
        ("470", "170"),
    }


def test_default_focus_art_matches_website_network_geometry():
    root = ElementTree.parse(REPO_ROOT / "pdf/assets/focus-cross-domain.svg").getroot()

    assert root.attrib["viewBox"] == "0 0 500 230"
    assert [path.attrib["d"] for path in root.findall(".//svg:path", SVG_NS)] == [
        "M42 160L136 76L238 150L342 54L458 156",
        "M136 76L202 32M238 150L292 204M342 54L390 112",
    ]
    assert [
        (circle.attrib["cx"], circle.attrib["cy"], circle.attrib["r"])
        for circle in root.findall(".//svg:circle", SVG_NS)
    ] == [
        ("42", "160", "9"),
        ("136", "76", "13"),
        ("238", "150", "10"),
        ("342", "54", "14"),
        ("458", "156", "10"),
        ("202", "32", "7"),
        ("292", "204", "7"),
        ("390", "112", "7"),
    ]
    assert root.findall(".//svg:rect", SVG_NS) == []


def test_comp_bio_stock_and_tailored_exports_share_focus_asset():
    template = (REPO_ROOT / "pdf/templates/cv.typ").read_text(encoding="utf-8")
    exporter = (REPO_ROOT / "scripts/export_application.py").read_text(encoding="utf-8")

    assert 'image("../assets/focus-" + layout.focus.art + ".svg"' in template
    assert "build(lang, variant, content_dir, tailored=bool(applied))" in exporter
    projection = (REPO_ROOT / "pdf/projection.py").read_text(encoding="utf-8")
    assert '"comp-bio": {' in projection
    assert '"art": "genomics"' in projection
