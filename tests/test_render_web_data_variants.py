"""Tests for the web variants metadata emitted by render_web_data.

The website renders four text positioning fields that vary per target:
  headline         (sticky header)   <- personal.headline
  tagline          (profile intro)   <- profile.tagline
  lead_paragraph   (profile intro)   <- profile.paragraphs[0]
  second_paragraph (profile intro)   <- profile.paragraphs[1]

plus two skills adaptation fields (Phase: skills-per-variant):
  skills_hidden_groups <- skills groups dropped for this target
  skills_group_items   <- skills groups collapsed to fewer items for this target

The variants JSON must carry exactly the four text fields (always present, as
non-empty strings) plus whichever skills fields are non-trivial for that
target, with no bridge values and no `selected_projects` (the site groups
projects by category and never consumes selected_projects). These tests
assert *positioning correctness*, not merely structural validity.
"""

from __future__ import annotations

import json

import pytest

from scripts.render_web_data import _extract_overrides, _extract_skills_overrides, render_web_data

TARGETS = ("comp-bio", "ds-ml")
TEXT_OVERRIDE_KEYS = {"headline", "tagline", "lead_paragraph", "second_paragraph"}
SKILLS_OVERRIDE_KEYS = {"skills_hidden_groups", "skills_group_items"}
ALLOWED_OVERRIDE_KEYS = TEXT_OVERRIDE_KEYS | SKILLS_OVERRIDE_KEYS


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


def test_variants_have_all_text_positioning_fields(rendered):
    """Every target carries all four text positioning fields as non-empty strings.

    Regression guard: the original extractor read top-level keys and emitted only
    `selected_projects`, silently dropping every rendered positioning field.
    """
    for lang in ("en", "de"):
        for target in TARGETS:
            overrides = rendered[lang]["variants"][target]
            assert set(overrides) <= ALLOWED_OVERRIDE_KEYS, (
                f"{lang}/{target}: unexpected keys {set(overrides) - ALLOWED_OVERRIDE_KEYS}"
            )
            assert TEXT_OVERRIDE_KEYS <= set(overrides), (
                f"{lang}/{target}: missing text field(s) {TEXT_OVERRIDE_KEYS - set(overrides)}"
            )
            for key in TEXT_OVERRIDE_KEYS:
                assert isinstance(overrides[key], str) and overrides[key].strip(), (
                    f"{lang}/{target}.{key} must be a non-empty string"
                )


def test_variants_skills_fields_shape(rendered):
    """Both targets adapt Skills; the shapes match `_extract_skills_overrides`."""
    for lang in ("en", "de"):
        for target in TARGETS:
            overrides = rendered[lang]["variants"][target]
            hidden = overrides.get("skills_hidden_groups")
            assert isinstance(hidden, list) and hidden, (
                f"{lang}/{target}: skills_hidden_groups must be a non-empty list"
            )
            assert all(isinstance(label, str) and label for label in hidden)

            group_items = overrides.get("skills_group_items", {})
            assert isinstance(group_items, dict)
            for label, items in group_items.items():
                assert isinstance(label, str) and label
                assert isinstance(items, list) and items
                assert all(isinstance(item, str) and item for item in items)


def test_variants_comp_bio_hides_personal_dev_tooling_groups(rendered):
    for lang in ("en", "de"):
        hidden = set(rendered[lang]["variants"]["comp-bio"]["skills_hidden_groups"])
        # exact label text is language-specific; count + no item-level collapse is not.
        assert len(hidden) == 3
        assert "skills_group_items" not in rendered[lang]["variants"]["comp-bio"]


def test_variants_ds_ml_hides_structural_biology_and_collapses_immunology(rendered):
    for lang in ("en", "de"):
        overrides = rendered[lang]["variants"]["ds-ml"]
        assert len(overrides["skills_hidden_groups"]) == 1
        assert len(overrides["skills_group_items"]) == 1


def test_variants_no_selected_projects(rendered):
    """selected_projects must never appear — the web does not render it."""
    for lang in ("en", "de"):
        for target in TARGETS:
            assert "selected_projects" not in rendered[lang]["variants"][target], (
                f"{lang}/{target} leaked selected_projects"
            )


def test_variants_differ_from_bridge(rendered):
    """Each text override value differs from the corresponding bridge value."""
    for lang in ("en", "de"):
        bridge = rendered[lang]["bridge"]
        bridge_vals = {
            "headline": bridge["personal"]["headline"],
            "tagline": bridge["profile"]["tagline"],
            "lead_paragraph": bridge["profile"]["paragraphs"][0],
            "second_paragraph": bridge["profile"]["paragraphs"][1],
        }
        for target in TARGETS:
            for key in TEXT_OVERRIDE_KEYS:
                value = rendered[lang]["variants"][target][key]
                assert value != bridge_vals[key], (
                    f"{lang}/{target}.{key} == bridge value; override is a no-op"
                )


def test_variants_skills_hidden_groups_absent_from_bridge(rendered):
    """A hidden group's label must not appear as a group label in the bridge skills
    that vanished for no reason — i.e. it really was present in bridge and is
    genuinely absent from the variant (checked in Python in test_variants.py's
    `_resolve_skills_target` tests); here we just confirm the label set is a
    genuine subset of bridge's group labels, catching a typo'd/invented label."""
    for lang in ("en", "de"):
        bridge_labels = {
            g["label"]
            for cat in rendered[lang]["bridge"]["skills"]["categories"]
            for g in cat["groups"]
        }
        for target in TARGETS:
            hidden = rendered[lang]["variants"][target].get("skills_hidden_groups", [])
            assert set(hidden) <= bridge_labels


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


# --- _extract_skills_overrides unit tests --------------------------------------


def _skills(groups):
    """groups: list of (label, items) -> a resolved (post-langstring) skills tree."""
    return {"categories": [{"name": "Cat", "groups": [{"label": la, "items": it} for la, it in groups]}]}


def test_extract_skills_overrides_identical_returns_empty():
    skills = _skills([("A", ["1", "2"])])
    assert _extract_skills_overrides(skills, skills) == {}


def test_extract_skills_overrides_hidden_group():
    bridge = _skills([("A", ["1"]), ("B", ["2"])])
    variant = _skills([("A", ["1"])])
    assert _extract_skills_overrides(bridge, variant) == {"skills_hidden_groups": ["B"]}


def test_extract_skills_overrides_collapsed_items():
    bridge = _skills([("A", ["1", "2", "3"])])
    variant = _skills([("A", ["1"])])
    assert _extract_skills_overrides(bridge, variant) == {"skills_group_items": {"A": ["1"]}}


def test_extract_skills_overrides_hidden_and_collapsed_together():
    bridge = _skills([("A", ["1", "2"]), ("B", ["3"])])
    variant = _skills([("A", ["1"])])
    assert _extract_skills_overrides(bridge, variant) == {
        "skills_hidden_groups": ["B"],
        "skills_group_items": {"A": ["1"]},
    }


def test_extract_skills_overrides_preserves_bridge_order_for_hidden():
    bridge = _skills([("A", ["1"]), ("B", ["2"]), ("C", ["3"])])
    variant = _skills([("B", ["2"])])
    assert _extract_skills_overrides(bridge, variant)["skills_hidden_groups"] == ["A", "C"]


def test_extract_overrides_includes_skills_fields():
    """`_extract_overrides` folds `_extract_skills_overrides` into its result."""
    bridge = {**_tree(), "skills": _skills([("A", ["1"]), ("B", ["2"])])}
    variant = {**_tree(), "skills": _skills([("A", ["1"])])}
    assert _extract_overrides(bridge, variant) == {"skills_hidden_groups": ["B"]}
