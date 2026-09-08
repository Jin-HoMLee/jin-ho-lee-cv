"""Tests for the Phase 8b target axis (bridge | comp-bio | ds-ml)."""

from __future__ import annotations

import pytest
from ruamel.yaml import YAML

from pdf.build import _pdf_filename, _parse_args as _pdf_parse_args, prepare_data
from scripts.content_loader import (
    _resolve_personal_target,
    _resolve_profile_target,
    _resolve_skills_target,
    _select_project_ids,
    load_content,
)
from scripts.langstring import resolve_langstrings
from scripts.render_text import _txt_filename, render
from scripts.validate import (
    _validate_headline_variant_completeness,
    _validate_profile_variant_parity,
    _validate_skills_variant_references,
    validate_tree,
)

_yaml = YAML(typ="safe")


def _write(path, data):
    with path.open("w", encoding="utf-8") as f:
        _yaml.dump(data, f)


def test_resolve_profile_target_overrides_tagline_and_lead_keeps_rest():
    profile = {
        "tagline": "BRIDGE tagline",
        "paragraphs": ["BRIDGE lead", "SHARED second"],
        "variants": {
            "comp-bio": {"tagline": "CB tagline", "lead_paragraph": "CB lead"},
        },
    }
    out = _resolve_profile_target(profile, "comp-bio")
    assert out["tagline"] == "CB tagline"
    assert out["paragraphs"] == ["CB lead", "SHARED second"]
    assert "variants" not in out


def test_resolve_profile_target_bridge_is_noop_but_strips_variants():
    profile = {
        "tagline": "BRIDGE tagline",
        "paragraphs": ["BRIDGE lead", "SHARED second"],
        "variants": {"comp-bio": {"tagline": "CB tagline"}},
    }
    out = _resolve_profile_target(profile, "bridge")
    assert out["tagline"] == "BRIDGE tagline"
    assert out["paragraphs"] == ["BRIDGE lead", "SHARED second"]
    assert "variants" not in out


def test_resolve_profile_target_partial_override_inherits_bridge_tagline():
    profile = {
        "tagline": "BRIDGE tagline",
        "paragraphs": ["BRIDGE lead", "SHARED second"],
        "variants": {"ds-ml": {"lead_paragraph": "DS lead"}},
    }
    out = _resolve_profile_target(profile, "ds-ml")
    assert out["tagline"] == "BRIDGE tagline"  # not overridden → inherited
    assert out["paragraphs"] == ["DS lead", "SHARED second"]


def test_resolve_personal_target_replaces_headline():
    personal = {
        "headline": {"en": "BRIDGE", "de": "BRIDGE-DE"},
        "email": "x@y.z",
        "variants": {"comp-bio": {"headline": {"en": "CB", "de": "CB-DE"}}},
    }
    out = _resolve_personal_target(personal, "comp-bio")
    assert out["headline"] == {"en": "CB", "de": "CB-DE"}
    assert out["email"] == "x@y.z"
    assert "variants" not in out


def test_resolve_personal_target_bridge_is_noop_but_strips_variants():
    personal = {
        "headline": {"en": "BRIDGE", "de": "BRIDGE-DE"},
        "email": "x@y.z",
        "variants": {"comp-bio": {"headline": {"en": "CB", "de": "CB-DE"}}},
    }
    out = _resolve_personal_target(personal, "bridge")
    assert out["headline"] == {"en": "BRIDGE", "de": "BRIDGE-DE"}
    assert out["email"] == "x@y.z"
    assert "variants" not in out


def test_load_content_rejects_unknown_target(content_dir):
    with pytest.raises(ValueError, match="unknown target"):
        load_content(content_dir, target="nope")


def test_load_content_strips_variants_key_from_personal_and_profile(content_dir):
    content = load_content(content_dir, lang="en", target="bridge")
    assert "variants" not in content["personal"]
    assert "variants" not in content["profile"]
    assert all("variants" not in category for category in content["skills"]["categories"])


def _skills_fixture():
    return {
        "categories": [
            {
                "name": {"en": "Bio"},
                "groups": [
                    {"label": {"en": "Core"}, "items": ["a", "b"]},
                    {"label": {"en": "Optional"}, "items": ["c"]},
                ],
                "variants": {
                    "comp-bio": {"group_items": {"Core": ["a", "b", "detail"]}},
                    "ds-ml": {"omit_groups": ["Optional"]},
                },
            },
            {
                "name": {"en": "Other"},
                "groups": [{"label": {"en": "Shared"}, "items": ["e"]}],
                "variants": {"comp-bio": {"omit": True}},
            },
        ]
    }


def test_resolve_skills_target_replaces_and_reduces_data_driven_groups():
    comp_bio = _resolve_skills_target(_skills_fixture(), "comp-bio")
    assert [category["name"]["en"] for category in comp_bio["categories"]] == ["Bio"]
    groups = {group["label"]["en"]: group["items"] for group in comp_bio["categories"][0]["groups"]}
    assert groups == {"Core": ["a", "b", "detail"], "Optional": ["c"]}

    ds_ml = _resolve_skills_target(_skills_fixture(), "ds-ml")
    assert [group["label"]["en"] for group in ds_ml["categories"][0]["groups"]] == ["Core"]
    assert ds_ml["categories"][0]["groups"][0]["items"] == ["a", "b"]


def test_resolve_skills_target_bridge_strips_variant_instructions():
    bridge = _resolve_skills_target(_skills_fixture(), "bridge")
    assert bridge["categories"][0]["groups"][0]["items"] == ["a", "b"]
    assert len(bridge["categories"]) == 2
    assert all("variants" not in category for category in bridge["categories"])


def test_skills_are_complementary_in_web_targets_and_full_in_bridge(content_dir):
    def resolved(target, web_projection=False):
        return resolve_langstrings(
            load_content(
                content_dir,
                lang="en",
                target=target,
                web_projection=web_projection,
            ),
            lang="en",
        )["skills"]

    trees = {
        "bridge": resolved("bridge"),
        "web-bridge": resolved("bridge", web_projection=True),
        "comp-bio": resolved("comp-bio", web_projection=True),
        "ds-ml": resolved("ds-ml", web_projection=True),
    }

    def items(target):
        return {
            item
            for category in trees[target]["categories"]
            for group in category["groups"]
            for item in group["items"]
        }

    assert {"TCRdock", "PostgreSQL", "Nix", "Claude Code"} <= items("bridge")
    assert "TCRdock" not in items("web-bridge")
    assert "PostgreSQL" not in items("web-bridge")
    assert {"MapSplice", "TCRdock", "MHCflurry"} <= items("comp-bio")
    assert {"LSTMs", "OpenCV", "BigQueryML", "Claude Code"} <= items("ds-ml")
    assert "TCRdock" not in items("ds-ml")
    assert "Claude Code" not in items("comp-bio")


def test_skills_variant_references_reject_unknown_groups(tmp_path):
    _write(
        tmp_path / "skills.yaml",
        {
            "categories": [
                {
                    "name": {"en": "Cat"},
                    "groups": [
                        {"label": {"en": "Real"}, "items": ["x"]},
                        {"label": {"en": "Real"}, "items": ["y"]},
                    ],
                    "variants": {
                        "comp-bio": {
                            "omit_groups": ["Typo"],
                            "group_items": {"Missing": ["z"]},
                        }
                    },
                }
            ]
        },
    )
    errors = _validate_skills_variant_references(tmp_path)
    messages = " ".join(error.message for error in errors)
    assert "Typo" in messages
    assert "Missing" in messages
    assert "duplicate base Skills group label" in messages


def test_skills_variant_references_scope_labels_to_their_category(tmp_path):
    _write(
        tmp_path / "skills.yaml",
        {
            "categories": [
                {
                    "name": {"en": "First"},
                    "groups": [{"label": {"en": "Shared"}, "items": ["x"]}],
                    "variants": {"comp-bio": {"group_items": {"Shared": ["y"]}}},
                },
                {
                    "name": {"en": "Second"},
                    "groups": [{"label": {"en": "Shared"}, "items": ["z"]}],
                    "variants": {"ds-ml": {"omit_groups": ["Shared"]}},
                },
            ]
        },
    )
    assert _validate_skills_variant_references(tmp_path) == []


def test_prepare_data_resolves_target_skills_for_pdf(content_dir):
    bridge = prepare_data(content_dir, private_path=None, lang="en", target="bridge")
    comp_bio = prepare_data(content_dir, private_path=None, lang="de", target="comp-bio")
    ds_ml = prepare_data(content_dir, private_path=None, lang="en", target="ds-ml")

    def all_items(data):
        return {
            item
            for category in data["skills"]["categories"]
            for group in category["groups"]
            for item in group["items"]
        }

    assert "TCRdock" in all_items(bridge)
    assert "TCRdock" in all_items(comp_bio)
    assert "LSTMs" in all_items(ds_ml)


def test_select_project_ids_returns_target_order():
    m = {"bridge": ["L5", "L1"], "comp-bio": ["L1", "L2", "L5"]}
    assert _select_project_ids(m, "comp-bio") == ["L1", "L2", "L5"]


def test_select_project_ids_falls_back_to_bridge_when_target_absent():
    m = {"bridge": ["L5", "L1", "L2"]}  # no ds-ml key
    assert _select_project_ids(m, "ds-ml") == ["L5", "L1", "L2"]


def _ids(projects):
    return [p["id"] for p in projects]


def test_load_content_bridge_project_order(content_dir):
    content = load_content(content_dir, lang="en", target="bridge")
    assert _ids(content["selected_projects"]) == ["L5", "L1", "L2"]


def test_load_content_comp_bio_project_order(content_dir):
    content = load_content(content_dir, lang="en", target="comp-bio")
    assert _ids(content["selected_projects"]) == ["L1", "L2", "L5"]


def test_load_content_ds_ml_project_order(content_dir):
    content = load_content(content_dir, lang="en", target="ds-ml")
    assert _ids(content["selected_projects"]) == ["C1", "D1", "D2", "D4", "D5"]


def test_profile_variant_parity_flags_key_mismatch(tmp_path):
    _write(
        tmp_path / "profile.en.yaml",
        {
            "tagline": "t",
            "paragraphs": ["a", "b"],
            "variants": {"comp-bio": {"tagline": "x", "lead_paragraph": "y"}},
        },
    )
    _write(
        tmp_path / "profile.de.yaml",
        {
            "tagline": "t",
            "paragraphs": ["a", "b"],
            "variants": {"comp-bio": {"tagline": "x"}},  # missing lead_paragraph
        },
    )
    errors = _validate_profile_variant_parity(tmp_path)
    assert errors
    assert "comp-bio" in str(errors[0])


def test_profile_variant_parity_passes_when_symmetric(tmp_path):
    payload = {
        "tagline": "t",
        "paragraphs": ["a", "b"],
        "variants": {"ds-ml": {"tagline": "x", "lead_paragraph": "y"}},
    }
    _write(tmp_path / "profile.en.yaml", payload)
    _write(tmp_path / "profile.de.yaml", payload)
    assert _validate_profile_variant_parity(tmp_path) == []


def test_headline_variant_completeness_flags_missing_de(tmp_path):
    _write(
        tmp_path / "personal.yaml",
        {
            "headline": {"en": "B", "de": "B"},
            "variants": {"comp-bio": {"headline": {"en": "only-en"}}},
        },
    )
    errors = _validate_headline_variant_completeness(tmp_path)
    assert errors
    assert "comp-bio" in str(errors[0])


def test_headline_variant_completeness_passes_when_bilingual(tmp_path):
    _write(
        tmp_path / "personal.yaml",
        {
            "headline": {"en": "B", "de": "B"},
            "variants": {"comp-bio": {"headline": {"en": "x", "de": "y"}}},
        },
    )
    assert _validate_headline_variant_completeness(tmp_path) == []


def test_headline_variant_completeness_does_not_crash_on_non_dict_headline(tmp_path):
    # A non-iterable headline is schema-invalid; the parity validator must not
    # crash on it (the schema validator reports the structural error).
    _write(
        tmp_path / "personal.yaml",
        {
            "headline": {"en": "B", "de": "B"},
            "variants": {"comp-bio": {"headline": 123}},
        },
    )
    assert _validate_headline_variant_completeness(tmp_path) == []


def test_profile_variant_parity_does_not_crash_on_non_dict_variants(tmp_path):
    # variants as a list is schema-invalid; the parity validator must not crash.
    _write(
        tmp_path / "profile.en.yaml",
        {
            "tagline": "t",
            "paragraphs": ["a", "b"],
            "variants": ["comp-bio"],
        },
    )
    _write(
        tmp_path / "profile.de.yaml",
        {
            "tagline": "t",
            "paragraphs": ["a", "b"],
            "variants": ["comp-bio"],
        },
    )
    assert _validate_profile_variant_parity(tmp_path) == []


def test_validate_tree_no_secondary_error_on_flat_list_selected_projects(tmp_path, schema_path):
    # A legacy flat-list selected_projects.yaml is schema-invalid; the schema
    # reports the type error, and the cross-ref walk must not add a confusing
    # "'list' object has no attribute 'values'" secondary error.
    _write(tmp_path / "selected_projects.yaml", ["L1", "L2"])
    msgs = " ".join(str(e) for e in validate_tree(tmp_path, schema_path))
    assert "has no attribute" not in msgs


def _resolved(content_dir, lang, target):
    return resolve_langstrings(load_content(content_dir, lang=lang, target=target), lang=lang)


def test_comp_bio_headline_en_de(content_dir):
    en = _resolved(content_dir, "en", "comp-bio")["personal"]["headline"]
    de = _resolved(content_dir, "de", "comp-bio")["personal"]["headline"]
    assert en == "Computational Biology · Cancer Genomics"
    assert de == "Computational Biology · Krebsgenomik"


def test_ds_ml_headline_en_de(content_dir):
    en = _resolved(content_dir, "en", "ds-ml")["personal"]["headline"]
    de = _resolved(content_dir, "de", "ds-ml")["personal"]["headline"]
    assert en == "Data Science · Machine Learning"
    assert de == "Data Science · Machine Learning"


def test_comp_bio_tagline_and_lead_paragraph(content_dir):
    profile = _resolved(content_dir, "en", "comp-bio")["profile"]
    assert profile["tagline"].startswith("Bioinformatician")


def test_ds_ml_tagline_and_lead_paragraph(content_dir):
    profile = _resolved(content_dir, "en", "ds-ml")["profile"]
    assert profile["tagline"].startswith("Data scientist shipping")


def test_second_paragraph_varies_by_target(content_dir):
    # Phase 8c+: the second profile paragraph is now a per-target override.
    # comp-bio and ds-ml each tune it to their audience; all three differ.
    bridge = _resolved(content_dir, "en", "bridge")["profile"]["paragraphs"][1]
    cb = _resolved(content_dir, "en", "comp-bio")["profile"]["paragraphs"][1]
    ds = _resolved(content_dir, "en", "ds-ml")["profile"]["paragraphs"][1]
    assert bridge != cb
    assert bridge != ds
    assert cb != ds


def test_resolve_profile_target_overrides_second_paragraph():
    profile = {
        "tagline": "BRIDGE tagline",
        "paragraphs": ["BRIDGE lead", "BRIDGE second"],
        "variants": {"ds-ml": {"second_paragraph": "DS second"}},
    }
    out = _resolve_profile_target(profile, "ds-ml")
    assert out["paragraphs"] == ["BRIDGE lead", "DS second"]


def test_resolve_profile_target_overrides_both_paragraphs():
    profile = {
        "tagline": "BRIDGE tagline",
        "paragraphs": ["BRIDGE lead", "BRIDGE second"],
        "variants": {"comp-bio": {"lead_paragraph": "CB lead", "second_paragraph": "CB second"}},
    }
    out = _resolve_profile_target(profile, "comp-bio")
    assert out["paragraphs"] == ["CB lead", "CB second"]


def test_experience_is_shared_across_targets(content_dir):
    bridge = _resolved(content_dir, "en", "bridge")["experience"]
    cb = _resolved(content_dir, "en", "comp-bio")["experience"]
    ds = _resolved(content_dir, "en", "ds-ml")["experience"]
    assert bridge == cb == ds


def test_pdf_filename_bridge_is_unsuffixed():
    assert _pdf_filename("en", "bridge") == "cv-en.pdf"
    assert _pdf_filename("de", "bridge") == "cv-de.pdf"


def test_pdf_filename_variants_are_suffixed():
    assert _pdf_filename("en", "comp-bio") == "cv-en-comp-bio.pdf"
    assert _pdf_filename("de", "ds-ml") == "cv-de-ds-ml.pdf"


def test_pdf_parse_args_target_default_and_choices():
    assert _pdf_parse_args(["--lang", "en"]).target == "bridge"
    assert _pdf_parse_args(["--lang", "en", "--target", "comp-bio"]).target == "comp-bio"
    with pytest.raises(SystemExit):
        _pdf_parse_args(["--lang", "en", "--target", "nope"])


def test_txt_filename_bridge_and_variant():
    assert _txt_filename("en", "bridge") == "cv-en.txt"
    assert _txt_filename("en", "comp-bio") == "cv-en-comp-bio.txt"


def test_render_text_threads_target():
    bridge = render("en", "bridge")
    cb = render("en", "comp-bio")
    assert bridge != cb
    assert "Computational Biology · Cancer Genomics" in cb
