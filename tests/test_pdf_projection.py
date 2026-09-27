"""Renderer-specific PDF projection tests.

The canonical content remains complete; the application PDF deliberately selects
relevant evidence so each target is concise without changing source claims.
"""

from pdf.build import prepare_data
from scripts.content_loader import load_content


def _skill_items(data):
    return {
        item
        for category in data["skills"]["categories"]
        for group in category["groups"]
        for item in group["items"]
    }


def _entry(data, entry_id):
    return next(entry for entry in data["experience"] if entry["id"] == entry_id)


def test_pdf_projection_does_not_change_canonical_content(content_dir):
    canonical = load_content(content_dir, lang="en", target="comp-bio")
    projected = prepare_data(content_dir, private_path=None, lang="en", target="comp-bio")

    assert len(canonical["publications"]) == 15
    assert len(projected["publications"]) == 3
    # skills sections are now identical and full in every renderer
    assert _skill_items(canonical) == _skill_items(projected)
    assert all("thesis" in education for education in canonical["education"])
    assert all("thesis" not in education for education in projected["education"])


def test_comp_bio_projection_keeps_relevant_quantified_evidence(content_dir):
    data = prepare_data(content_dir, private_path=None, lang="en", target="comp-bio")

    assert data["profile"]["paragraphs"] == []
    assert "11 peer-reviewed" in data["profile"]["tagline"]
    assert len(_entry(data, "independent")["bullets"]) == 1
    assert "Snakemake" in _entry(data, "independent")["bullets"][0]["en"]
    assert "1,000+" in _entry(data, "cintellic")["bullets"][0]["en"]
    assert "100+" in _entry(data, "neuefische")["bullets"][0]["en"]
    assert len(_entry(data, "research")["bullets"]) == 2
    assert "HLA Typing" in _entry(data, "research")["bullets"][0]["en"]

    skills = _skill_items(data)
    assert {"RNA-Seq", "HLA Typing", "MHCflurry", "Snakemake", "Docker"} <= skills
    # full, identical sections: the general AI/ML + developer tooling is retained too
    assert {"TensorFlow.js", "Claude Code", "WezTerm", "Kimi"} <= skills


def test_pdf_targets_project_experience_and_secondary_detail(content_dir):
    expected_bullets = {
        "bridge": {"independent": 1, "cintellic": 2, "neuefische": 2, "research": 2},
        "comp-bio": {"independent": 1, "cintellic": 1, "neuefische": 1, "research": 2},
        "ds-ml": {"independent": 2, "cintellic": 3, "neuefische": 2, "research": 1},
    }
    expected_awards = {
        "bridge": {"Google Cloud Certified - Associate Cloud Engineer", "DAAD PROMOS Scholarship"},
        "comp-bio": {"DeGBS Poster Award", "DAAD PROMOS Scholarship"},
        "ds-ml": {
            "Google Cloud Certified - Associate Cloud Engineer",
            "“Most Patient-Centric Solution” Award",
        },
    }

    for target, bullet_counts in expected_bullets.items():
        data = prepare_data(content_dir, private_path=None, lang="en", target=target)
        assert {entry["id"]: len(entry["bullets"]) for entry in data["experience"]} == bullet_counts
        assert {award["title"] for award in data["awards"]} == expected_awards[target]
        assert [language["name"] for language in data["languages"]] == [
            "German",
            "English",
            "Korean",
            "French",
            "Italian",
        ]
        volunteer = {
            category["name"]: category["entries"] for category in data["volunteer"]["categories"]
        }
        assert volunteer["Environment"] == ["Foodsharing e.V. (Operations Manager)"]
        assert volunteer["Sports"] == [
            "Training supervisor, Badminton, BSG Jülich 1963 e.V. (2022–present)",
            "Coach, Badminton youth talent group & 2nd-grade elementary school, TSG 1889 Dossenheim e.V. (2017–2018)",
        ]
        assert volunteer["Music"] == [
            "Chorister, Aachener Domchor (Aachen Cathedral Choir), 1997-2000"
        ]
        assert "Interests" not in volunteer


def test_general_profile_is_broad_and_balanced(content_dir):
    data = prepare_data(content_dir, private_path=None, lang="en", target="bridge")
    narrative = " ".join(
        [data["profile"]["tagline"]]
        + [bullet["en"] for entry in data["experience"] for bullet in entry["bullets"]]
        + [project["title"] + " " + project["outcome"] for project in data["selected_projects"]]
        + [
            " ".join(str(award.get(key, "")) for key in ("title", "issuer", "note"))
            for award in data["awards"]
        ]
    )

    tagline = data["profile"]["tagline"].lower()
    assert "data scientist with bioinformatics roots" in tagline
    assert "eight years" in tagline
    assert "11 peer-reviewed" in tagline
    assert "consult" in tagline
    assert "100+" in tagline
    # the profile narrative stays broad; the skill inventory is full and shared
    assert all(term not in narrative.lower() for term in ("hla", "neoantigen", "neoepitope"))
    assert [project["id"] for project in data["selected_projects"]] == ["C1", "D1", "L3"]
    assert "Neural Progenitor Differentiation" in _entry(data, "research")["bullets"][1]["en"]


def test_pdf_skills_use_non_overlapping_source_backed_groups(content_dir):
    full = {
        "Bioinformatics",
        "AI/ML & Developer Tools",
        "Data & Cloud Engineering",
        "Experimental Research",
    }
    for target in ("bridge", "comp-bio"):
        data = prepare_data(content_dir, private_path=None, lang="en", target=target)
        categories = data["skills"]["categories"]
        assert {category["name"] for category in categories} == full
        items = [
            item
            for category in categories
            for group in category["groups"]
            for item in group["items"]
        ]
        assert len(items) == len(set(items)), f"{target} repeats a skill across taxonomy groups"
        labels = {group["label"] for category in categories for group in category["groups"]}
        assert "Applied AI" not in labels
        assert "AI & ML" not in labels

    ds = prepare_data(content_dir, private_path=None, lang="en", target="ds-ml")
    assert {category["name"] for category in ds["skills"]["categories"]} == full - {
        "Experimental Research"
    }
    ds_items = [
        item
        for category in ds["skills"]["categories"]
        for group in category["groups"]
        for item in group["items"]
    ]
    assert len(ds_items) == len(set(ds_items))


def test_source_grounded_role_coaching_and_2015_claims(content_dir):
    canonical = load_content(content_dir, lang="en", target="bridge")
    independent = _entry(canonical, "independent")
    neuefische = _entry(canonical, "neuefische")
    l1 = canonical["projects"]["L1"]

    assert independent["role"]["en"] == "Independent Bioinformatics & ML/AI Engineer"
    assert any(
        "Snakemake" in bullet["en"] and bullet["refs"] == ["L5"]
        for bullet in independent["bullets"]
    )
    assert "capstone" in neuefische["bullets"][0]["en"].lower()
    assert "unpublished computational proof of concept" in l1["outcome"].lower()
    assert "validat" not in " ".join(l1["contributions"] + [l1["outcome"]]).lower()


def test_pdf_project_links_follow_language_routes(content_dir):
    en = prepare_data(content_dir, private_path=None, lang="en", target="comp-bio")
    de = prepare_data(content_dir, private_path=None, lang="de", target="comp-bio")

    assert en["project_links"]["L1"] == "https://jinholee.is-a.dev/projects/L1/"
    assert de["project_links"]["L1"] == "https://jinholee.is-a.dev/de/projects/L1/"
    assert en["selected_projects"][0]["web_url"] == en["project_links"]["L1"]
    assert de["selected_projects"][0]["web_url"] == de["project_links"]["L1"]
