"""Tests for the web variants metadata emitted by render_web_data.

The website renders four positioning fields that vary per target:
  headline         (sticky header)   <- personal.headline
  tagline          (profile intro)   <- profile.tagline
  lead_paragraph   (profile intro)   <- profile.paragraphs[0]
  second_paragraph (profile intro)   <- profile.paragraphs[1]

The variants JSON must carry these four text fields, a derived CodeHero stack,
and a resolved Skills tree per target. The site uses the latter to swap the visible
Skills section without reimplementing the content resolver in the browser. There are no
`selected_projects` values (the site groups projects by category and never
consumes selected_projects). These tests assert positioning correctness, not
merely structural validity.
"""

from __future__ import annotations

import json

import pytest

from scripts.render_web_data import _extract_overrides, render_web_data

TARGETS = ("comp-bio", "ds-ml")
TEXT_OVERRIDE_KEYS = {"headline", "tagline", "lead_paragraph", "second_paragraph"}
OVERRIDE_KEYS = TEXT_OVERRIDE_KEYS | {"hero_stack", "skills"}


@pytest.fixture(scope="module")
def rendered(tmp_path_factory):
    """Render bridge + variants JSON into a hermetic temp dir (not the gitignored copy)."""
    out = tmp_path_factory.mktemp("web_data")
    render_web_data(output_dir=out)
    data = {}
    for lang in ("en", "de"):
        data[lang] = {
            "bridge": json.loads((out / f"content.{lang}.json").read_text()),
            "variants": json.loads((out / f"content.{lang}.variants.json").read_text()),
        }
    return data


def test_variants_files_keyed_by_target(rendered):
    """Each variants file is a dict keyed by exactly the known targets."""
    for lang in ("en", "de"):
        variants = rendered[lang]["variants"]
        assert isinstance(variants, dict)
        assert set(variants) == set(TARGETS), f"{lang}: unexpected target keys {set(variants)}"


def test_variants_have_all_positioning_fields(rendered):
    """Every target carries all four positioning fields as non-empty strings.

    Regression guard: the original extractor read top-level keys and emitted only
    `selected_projects`, silently dropping every rendered positioning field.
    """
    for lang in ("en", "de"):
        for target in TARGETS:
            overrides = rendered[lang]["variants"][target]
            assert set(overrides) == OVERRIDE_KEYS, (
                f"{lang}/{target}: keys {set(overrides)} != {OVERRIDE_KEYS}"
            )
            for key in TEXT_OVERRIDE_KEYS:
                assert isinstance(overrides[key], str) and overrides[key].strip(), (
                    f"{lang}/{target}.{key} must be a non-empty string"
                )
            assert overrides["hero_stack"]
            assert all(isinstance(item, str) and item for item in overrides["hero_stack"])


def test_ds_ml_hero_stack_uses_ml_engineering_and_cloud_leads(rendered):
    for lang in ("en", "de"):
        assert rendered[lang]["variants"]["ds-ml"]["hero_stack"] == [
            "NGS",
            "TensorFlow",
            "Python (Expert)",
            "GCP",
        ]


def test_variants_carry_resolved_complementary_skills(rendered):
    for lang in ("en", "de"):
        bridge = rendered[lang]["bridge"]["skills"]
        for target in TARGETS:
            skills = rendered[lang]["variants"][target]["skills"]
            assert skills != bridge
            assert skills["categories"]
            assert all(category["groups"] for category in skills["categories"])

        def items(skills):
            return {
                item
                for category in skills["categories"]
                for group in category["groups"]
                for item in group["items"]
            }

        comp_bio = rendered[lang]["variants"]["comp-bio"]["skills"]
        ds_ml = rendered[lang]["variants"]["ds-ml"]["skills"]
        assert "TCRdock" in items(comp_bio)
        assert "TCRdock" not in items(ds_ml)
        assert "LSTMs" in items(ds_ml)
        assert "Claude Code" in items(ds_ml)


def test_variants_no_selected_projects(rendered):
    """selected_projects must never appear — the web does not render it."""
    for lang in ("en", "de"):
        for target in TARGETS:
            assert "selected_projects" not in rendered[lang]["variants"][target], (
                f"{lang}/{target} leaked selected_projects"
            )


def test_variants_differ_from_bridge(rendered):
    """Each override value differs from the corresponding bridge value."""
    for lang in ("en", "de"):
        bridge = rendered[lang]["bridge"]
        bridge_vals = {
            "headline": bridge["personal"]["headline"],
            "tagline": bridge["profile"]["tagline"],
            "lead_paragraph": bridge["profile"]["paragraphs"][0],
            "second_paragraph": bridge["profile"]["paragraphs"][1],
        }
        for target in TARGETS:
            overrides = rendered[lang]["variants"][target]
            for key in TEXT_OVERRIDE_KEYS:
                assert overrides[key] != bridge_vals[key], (
                    f"{lang}/{target}.{key} == bridge value; override is a no-op"
                )
            assert overrides["skills"] != bridge["skills"]


def test_variants_en_de_parity(rendered):
    """EN and DE must expose identical target keys and identical override-key sets."""
    en, de = rendered["en"]["variants"], rendered["de"]["variants"]
    assert en.keys() == de.keys()
    for target in en:
        assert set(en[target]) == set(de[target]), (
            f"{target}: EN keys {set(en[target])} != DE keys {set(de[target])}"
        )


# --- _extract_overrides unit tests -------------------------------------------------


def _tree(headline="H", tagline="T", paras=("lead", "shared")):
    return {
        "personal": {"headline": headline},
        "profile": {"tagline": tagline, "paragraphs": list(paras)},
    }


def test_extract_identical_trees_returns_empty():
    bridge = _tree()
    assert _extract_overrides(bridge, _tree()) == {}


def test_extract_headline_difference_only():
    bridge = _tree()
    variant = _tree(headline="Computational Biology")
    assert _extract_overrides(bridge, variant) == {"headline": "Computational Biology"}


def test_extract_tagline_and_lead():
    bridge = _tree()
    variant = _tree(tagline="ships ML", paras=("new lead", "shared"))
    assert _extract_overrides(bridge, variant) == {
        "tagline": "ships ML",
        "lead_paragraph": "new lead",
    }


def test_extract_second_paragraph_difference():
    """A paragraphs[1] difference is emitted as second_paragraph (Phase 8c+)."""
    bridge = _tree(paras=("lead", "shared"))
    variant = _tree(paras=("lead", "tuned second"))
    assert _extract_overrides(bridge, variant) == {"second_paragraph": "tuned second"}


def test_extract_both_paragraphs_difference():
    bridge = _tree(paras=("lead", "second"))
    variant = _tree(paras=("new lead", "new second"))
    assert _extract_overrides(bridge, variant) == {
        "lead_paragraph": "new lead",
        "second_paragraph": "new second",
    }


def test_extract_never_emits_selected_projects():
    """A top-level selected_projects difference must be ignored — not web-rendered."""
    bridge = {**_tree(), "selected_projects": ["A"]}
    variant = {**_tree(), "selected_projects": ["B", "C"]}
    assert _extract_overrides(bridge, variant) == {}


def test_extract_emits_resolved_skills_tree_without_selected_projects():
    """The browser receives resolved skills, not variant instructions."""
    bridge = {**_tree(), "skills": {"categories": [{"groups": [{"label": "A", "items": ["1"]}]}]}}
    skills = {"categories": [{"groups": [{"label": "A", "items": ["1", "detail"]}]}]}
    variant = {**_tree(headline="variant"), "skills": skills, "selected_projects": ["B"]}
    overrides = _extract_overrides(bridge, variant)
    assert overrides["skills"] == skills
    assert "hero_stack" not in overrides
    assert "selected_projects" not in overrides
