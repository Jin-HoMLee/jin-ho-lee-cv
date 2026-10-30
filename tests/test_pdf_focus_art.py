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
