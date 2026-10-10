"""Tests for scripts.content_loader."""

import pytest

from scripts.content_loader import (
    _resolve_experience_target,
    deep_merge,
    load_content,
)


def test_deep_merge_overlays_leaf_values():
    base = {"a": 1, "b": {"c": 2}}
    overlay = {"b": {"c": 3, "d": 4}}
    result = deep_merge(base, overlay)
    assert result == {"a": 1, "b": {"c": 3, "d": 4}}


def test_resolve_experience_target_keeps_appended_bullets():
    """Canonical bullets are reordered; tailoring-appended bullets stay last."""
    canonical = {
        "id": "independent",
        "bullets": [
            {"en": "a", "de": "a", "refs": []},
            {"en": "b", "de": "b", "refs": []},
            {"en": "c", "de": "c", "refs": []},
        ],
    }
    # comp-bio independent order is (2, 1, 0); no extra bullet → unchanged count.
    assert [b["en"] for b in _resolve_experience_target([canonical], "comp-bio")[0]["bullets"]] == [
        "c",
        "b",
        "a",
    ]

    # A bullet appended beyond the canonical order (index 3) survives, last.
    with_extra = {
        "id": "independent",
        "bullets": canonical["bullets"]
        + [
            {"en": "d", "de": "d", "refs": []},
        ],
    }
    assert [
        b["en"] for b in _resolve_experience_target([with_extra], "comp-bio")[0]["bullets"]
    ] == [
        "c",
        "b",
        "a",
        "d",
    ]


def test_deep_merge_does_not_mutate_inputs():
    base = {"a": {"x": 1}}
    overlay = {"a": {"y": 2}}
    deep_merge(base, overlay)
    assert base == {"a": {"x": 1}}
    assert overlay == {"a": {"y": 2}}


def test_load_content_without_private_returns_public_only(content_dir):
    content = load_content(content_dir, private_path=None)
    assert "personal" in content
    assert "phone" not in content["personal"]
    assert "address" not in content["personal"]


def test_load_content_with_private_merges_overlay(content_dir, tmp_path):
    private = tmp_path / "private.yaml"
    private.write_text(
        'phone: "+49 000 0000000"\n'
        "address:\n"
        '  street: "Teststraße 1"\n'
        '  postal_code: "00000"\n'
        '  city: "Testville"\n'
        '  country: "ZZ"\n'
    )
    content = load_content(content_dir, private_path=private)
    assert content["personal"]["phone"] == "+49 000 0000000"
    assert content["personal"]["address"]["city"] == "Testville"


def test_load_content_includes_all_sections(content_dir):
    content = load_content(content_dir, private_path=None)
    for key in (
        "personal",
        "profile",
        "skills",
        "education",
        "experience",
        "projects",
        "languages",
        "volunteer",
        "awards",
        "publications",
        "labels",
    ):
        assert key in content, f"missing {key} in loaded content"


def test_load_content_projects_keyed_by_id(content_dir):
    content = load_content(content_dir, private_path=None)
    assert "L1" in content["projects"]
    assert content["projects"]["L1"]["category"] == "life-science"


def test_load_content_nonexistent_private_is_ignored(content_dir, tmp_path):
    """A private_path that doesn't exist should be silently ignored, not error."""
    ghost = tmp_path / "does_not_exist.yaml"
    content = load_content(content_dir, private_path=ghost)
    assert "phone" not in content["personal"]
    assert "address" not in content["personal"]


def test_load_content_rejects_id_filename_mismatch(tmp_path):
    """A project file whose id field doesn't match its filename should raise."""
    fake = tmp_path / "content"
    fake.mkdir()
    (fake / "personal.yaml").write_text(
        "name:\n  given: T\n  family: U\n"
        "headline:\n  en: H\n"
        "email: a@b.com\n"
        "location: {city: X, country: Y}\n"
        "links: {}\n"
    )
    (fake / "profile.en.yaml").write_text("paragraphs:\n  - p\n")
    (fake / "skills.yaml").write_text(
        "categories:\n  - name: {en: A}\n    groups:\n      - label: {en: B}\n        items: [x]\n"
    )
    (fake / "education.yaml").write_text("- degree: {en: D}\n  institution: I\n  year: 2020\n")
    (fake / "experience.yaml").write_text(
        "- id: x\n"
        "  org: {name: O}\n"
        "  role: {en: R}\n"
        "  period: {start: '2020-01', end: '2021-01'}\n"
        "  bullets:\n    - en: b\n"
    )
    (fake / "languages.yaml").write_text("- name: {en: English}\n  proficiency: fluent\n")
    (fake / "volunteer.yaml").write_text("categories:\n  - name: {en: A}\n    entries: [x]\n")
    (fake / "publications.bib").write_text(
        "@article{x, author={X}, title={T}, year={2020},"
        " journal={J}, type={article}, authorship={first}}\n"
    )
    projects_dir = fake / "projects"
    projects_dir.mkdir()
    (projects_dir / "L1.en.yaml").write_text(
        "id: L99\n"  # mismatch: filename says L1 but id field says L99
        "category: life-science\n"
        "title: t\n"
        "summary: s\n"
        "role: r\n"
        "period: {start: '2020-01'}\n"
        "technologies: [a]\n"
        "contributions: [c]\n"
        "outcome: o\n"
    )
    with pytest.raises(ValueError, match="does not match filename"):
        load_content(fake, private_path=None)


def test_corrected_project_periods(content_dir):
    content = load_content(content_dir, private_path=None, lang="en")
    projects = content["projects"]
    assert projects["L1"]["period"] == {"start": "2015-08", "end": "2015-11"}
    assert projects["L2"]["period"] == {"start": "2014-04", "end": "2014-05"}
    assert projects["L3"]["period"]["start"] == "2017-02"


def test_research_entry_start_not_after_earliest_subproject(content_dir):
    content = load_content(content_dir, private_path=None, lang="en")
    research = next(e for e in content["experience"] if e["id"] == "research")
    assert research["period"]["start"] == "2014-04"


def test_skills_sections_are_full_and_identical_with_ds_ml_dropping_experimental(content_dir):
    bridge = load_content(content_dir, private_path=None, lang="en", target="bridge")

    def items(content):
        return {
            item
            for category in content["skills"]["categories"]
            for group in category["groups"]
            for item in group["items"]
        }

    assert {
        "MapSplice",
        "TCRdock",
        "Nix",
        "WezTerm",
        "Claude Code",
        "Snakemake",
        "Pi",
        "Grok",
        "Cursor",
        "Kimi",
    } <= items(bridge)

    web_bridge = load_content(
        content_dir,
        private_path=None,
        lang="en",
        target="bridge",
        web_projection=True,
    )
    assert items(web_bridge) == items(bridge)

    comp_bio = load_content(content_dir, private_path=None, lang="en", target="comp-bio")
    assert items(comp_bio) == items(bridge)

    ds_ml = load_content(content_dir, private_path=None, lang="en", target="ds-ml")
    assert {"LSTMs", "TCRdock", "Claude Code", "Kimi"} <= items(ds_ml)
    assert {"FISH", "qPCR", "FACS", "Super-Resolution"}.isdisjoint(items(ds_ml))

    def names(content):
        return [category["name"]["en"] for category in content["skills"]["categories"]]

    assert names(bridge) == [
        "AI/ML & Developer Tools",
        "Bioinformatics",
        "Data & Cloud Engineering",
        "Experimental Research",
    ]
    assert names(comp_bio) == [
        "Bioinformatics",
        "AI/ML & Developer Tools",
        "Data & Cloud Engineering",
        "Experimental Research",
    ]
    assert names(ds_ml) == [
        "AI/ML & Developer Tools",
        "Data & Cloud Engineering",
        "Bioinformatics",
    ]
    assert names(
        load_content(content_dir, lang="en", target="ds-ml", web_projection=True)
    ) == names(ds_ml)

    bioinformatics = next(
        c for c in comp_bio["skills"]["categories"] if c["name"]["en"] == "Bioinformatics"
    )
    groups = {g["label"]["en"]: g["items"] for g in bioinformatics["groups"]}
    assert "MapSplice" in groups["Bioinformatics Workflows"]
    assert "samtools/bcftools" in groups["Bioinformatics Workflows"]

    all_skill_items = [
        item
        for category in bridge["skills"]["categories"]
        for group in category["groups"]
        for item in group["items"]
    ]
    assert len(all_skill_items) == len(set(all_skill_items))


def test_public_languages_omit_french_and_italian(content_dir):
    content = load_content(content_dir, private_path=None, lang="en")
    names = {lang["name"]["en"] for lang in content["languages"]}
    assert names == {"German", "English", "Korean", "Latin"}


def test_awards_loaded(content_dir):
    content = load_content(content_dir, private_path=None, lang="en")
    assert "awards" in content
    titles = {a["title"]["en"] for a in content["awards"]}
    assert "DAAD PROMOS Scholarship" in titles
    assert "DeGBS Poster Award" in titles


def test_research_genomics_bullet_mentions_variant_calling(content_dir):
    content = load_content(content_dir, private_path=None, lang="en")
    research = next(e for e in content["experience"] if e["id"] == "research")
    first_bullet = research["bullets"][0]["en"]
    assert "SNV" in first_bullet and "colorectal" in first_bullet.lower()


def test_faq_is_loaded_and_resolves_to_language(content_dir):
    from scripts.content_loader import load_content
    from scripts.langstring import resolve_langstrings

    en = resolve_langstrings(load_content(content_dir, lang="en"), lang="en")
    de = resolve_langstrings(load_content(content_dir, lang="de"), lang="de")

    en_faqs = en["faq"]["faqs"]
    de_faqs = de["faq"]["faqs"]
    assert len(en_faqs) == len(de_faqs) >= 5
    assert isinstance(en_faqs[0]["question"], str)
    assert isinstance(en_faqs[0]["answer"], str)
    # Same ids, in the same order, across languages.
    assert [f["id"] for f in en_faqs] == [f["id"] for f in de_faqs]
    # The DE text is genuinely German, not an EN fallback.
    assert en_faqs[0]["question"] != de_faqs[0]["question"]


def test_profile_answer_block_is_a_plain_string(content_dir):
    from scripts.content_loader import load_content

    for lang in ("en", "de"):
        profile = load_content(content_dir, lang=lang)["profile"]
        block = profile["answer_block"]
        assert isinstance(block, str) and block.strip()
        words = len(block.split())
        assert 35 <= words <= 70, f"{lang} answer_block is {words} words; target 40-60"
