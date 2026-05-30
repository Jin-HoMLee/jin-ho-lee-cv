"""Regression assertions for the Phase 8a positioning copy.

These guard the "Bioinformatics · Data Science" repositioning: the tagline and
profile body must lead with the data-science + cancer-genomics differentiator,
and the cloud-migration work must be demoted to the second profile paragraph.
"""
from __future__ import annotations

from scripts.content_loader import load_content


def test_en_tagline_leads_with_data_science(content_dir):
    profile = load_content(content_dir, lang="en")["profile"]
    assert profile["tagline"].startswith("Data scientist")
    assert "production ML on GCP" in profile["tagline"]
    # the old genomics-only framing is gone
    assert "Bioinformatics Engineer specializing" not in profile["tagline"]


def test_en_profile_body_is_two_paragraphs_led_by_differentiator(content_dir):
    paragraphs = load_content(content_dir, lang="en")["profile"]["paragraphs"]
    assert len(paragraphs) == 2
    assert paragraphs[0].startswith("Data scientist with deep roots in cancer genomics")
    # cloud-migration work is demoted out of the opening paragraph
    assert "Google Cloud" not in paragraphs[0]
    assert "Google Cloud" in paragraphs[1]


def test_de_tagline_leads_with_data_science(content_dir):
    profile = load_content(content_dir, lang="de")["profile"]
    assert profile["tagline"].startswith("Data Scientist")
    assert "Krebsgenomik" in profile["tagline"]


def test_de_profile_body_is_two_paragraphs_led_by_differentiator(content_dir):
    paragraphs = load_content(content_dir, lang="de")["profile"]["paragraphs"]
    assert len(paragraphs) == 2
    assert paragraphs[0].startswith("Data Scientist mit tiefen Wurzeln in der Krebsgenomik")
    assert "Google Cloud" not in paragraphs[0]
    assert "Google Cloud" in paragraphs[1]


def test_headline_repositioned_to_bioinformatics_data_science(content_dir):
    headline = load_content(content_dir)["personal"]["headline"]
    assert headline["en"] == "Bioinformatics · Data Science"
    assert headline["de"] == "Bioinformatik · Data Science"
