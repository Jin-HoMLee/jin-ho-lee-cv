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


def _experience_text(data, lang):
    return " ".join(bullet[lang] for entry in data["experience"] for bullet in entry["bullets"])


def test_experience_coverage_is_identical_across_targets_and_languages(content_dir):
    """Steer 018: no role, strand, or keyword is dropped for target relevance."""
    inventory = {
        "independent": {
            "en": ("Agentic AI", "Computer Vision", "Bioinformatics"),
            "de": ("Agenten-KI", "Computer Vision", "Bioinformatik"),
        },
        "cintellic": {
            "en": ("Cloud Migration", "Production ML", "Stakeholder Lead"),
            "de": ("Cloud-Migration", "Produktions-ML", "Stakeholder Lead"),
        },
        "neuefische": {"en": ("Coaching", "ML Development"), "de": ("Coaching", "ML-Entwicklung")},
        "research": {
            "en": ("Genomics", "Biophysics", "Neurobiology"),
            "de": ("Genomik", "Biophysik", "Neurobiologie"),
        },
    }
    for lang in ("en", "de"):
        for target in ("bridge", "comp-bio", "ds-ml"):
            data = prepare_data(content_dir, private_path=None, lang=lang, target=target)
            counts = {entry["id"]: len(entry["bullets"]) for entry in data["experience"]}
            assert counts == {
                "independent": 3,
                "cintellic": 3,
                "neuefische": 2,
                "research": 3,
            }, f"{lang}/{target} dropped experience bullets: {counts}"
            for entry_id, markers_by_lang in inventory.items():
                bullets = _entry(data, entry_id)["bullets"]
                labels = " · ".join(bullet[lang] for bullet in bullets)
                for marker in markers_by_lang[lang]:
                    assert marker in labels, f"{lang}/{target} {entry_id} missing {marker!r}"


def test_pdf_projection_does_not_change_canonical_content(content_dir):
    canonical = load_content(content_dir, lang="en", target="comp-bio")
    projected = prepare_data(content_dir, private_path=None, lang="en", target="comp-bio")

    assert len(canonical["publications"]) == 16
    assert len(projected["publications"]) == 4
    # skills sections are now identical and full in every renderer
    assert _skill_items(canonical) == _skill_items(projected)
    assert all("thesis" in education for education in canonical["education"])
    assert all("thesis" not in education for education in projected["education"])


def test_comp_bio_projection_keeps_relevant_quantified_evidence(content_dir):
    data = prepare_data(content_dir, private_path=None, lang="en", target="comp-bio")

    assert data["profile"]["paragraphs"] == []
    assert "11 peer-reviewed" in data["profile"]["tagline"]
    assert len(_entry(data, "independent")["bullets"]) == 3
    assert "Snakemake" in _entry(data, "independent")["bullets"][0]["en"]
    assert "1,000+" in _entry(data, "cintellic")["bullets"][0]["en"]
    assert "100+" in _entry(data, "neuefische")["bullets"][0]["en"]
    assert len(_entry(data, "research")["bullets"]) == 3
    assert "HLA/neoantigen pipelines" in _entry(data, "research")["bullets"][0]["en"]

    skills = _skill_items(data)
    assert {"RNA-Seq", "HLA Typing", "MHCflurry", "Snakemake", "Docker"} <= skills
    # full, identical sections: the general AI/ML + developer tooling is retained too
    assert {"TensorFlow.js", "Claude Code", "WezTerm", "Kimi"} <= skills


def test_pdf_targets_project_experience_and_secondary_detail(content_dir):
    expected_bullets = {
        "bridge": {"independent": 3, "cintellic": 3, "neuefische": 2, "research": 3},
        "comp-bio": {"independent": 3, "cintellic": 3, "neuefische": 2, "research": 3},
        "ds-ml": {"independent": 3, "cintellic": 3, "neuefische": 2, "research": 3},
    }
    expected_awards = {
        "bridge": {"Google Cloud Certified - Associate Cloud Engineer", "DAAD PROMOS Scholarship"},
        "comp-bio": {
            "“Most Patient-Centric Solution” Award",
            "DeGBS Poster Award",
            "DAAD PROMOS Scholarship",
        },
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
        ]
        assert [category["name"] for category in data["volunteer"]["categories"]] == [
            "Sports",
            "Environment",
            "Music",
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
            "Chorister, Aachener Domchor (Aachen Cathedral Choir), 1997-2000",
            "Chorister, Vienna Cathedral Choir (Wiener Domchor)",
            "Chorister, Cappella Palatina (Heidelberg)",
        ]
        assert "Interests" not in volunteer


def test_experience_bullet_order_leads_each_target_focus(content_dir):
    """Steer 023: identical content, but per-target ordering leads focus."""
    expected = {
        "bridge": {
            "independent": [["D4"], ["D2"], ["L5"]],
            "cintellic": [["C2"], ["C1"], ["C1", "C2"]],
            "neuefische": [["D3"], ["D1"]],
            "research": [["L1", "L2"], ["L3"], ["L4"]],
        },
        "comp-bio": {
            "independent": [["L5"], ["D2"], ["D4"]],
            "cintellic": [["C2"], ["C1"], ["C1", "C2"]],
            "neuefische": [["D3"], ["D1"]],
            "research": [["L1", "L2"], ["L3"], ["L4"]],
        },
        "ds-ml": {
            "independent": [["D4"], ["D2"], ["L5"]],
            "cintellic": [["C1"], ["C2"], ["C1", "C2"]],
            "neuefische": [["D1"], ["D3"]],
            "research": [["L1", "L2"], ["L3"], ["L4"]],
        },
    }
    for target, entries in expected.items():
        data = prepare_data(content_dir, private_path=None, lang="en", target=target)
        for entry_id, refs in entries.items():
            assert [bullet["refs"] for bullet in _entry(data, entry_id)["bullets"]] == refs, (
                f"{target}/{entry_id} order wrong"
            )


def test_general_profile_is_broad_and_balanced(content_dir):
    data = prepare_data(content_dir, private_path=None, lang="en", target="bridge")
    tagline = data["profile"]["tagline"].lower()
    assert "data scientist with bioinformatics roots" in tagline
    assert "eight years" in tagline
    assert "11 peer-reviewed" in tagline
    assert "consult" in tagline
    assert "100+" in tagline
    # The tagline stays broad while General carries the complete independent-work balance.
    assert all(term not in tagline for term in ("hla", "neoantigen", "neoepitope"))
    independent = _entry(data, "independent")
    assert [bullet["refs"] for bullet in independent["bullets"]] == [["D4"], ["D2"], ["L5"]]
    assert "on-device Chrome extension" in independent["bullets"][1]["en"]
    assert "2015 SNU computational prototype" in independent["bullets"][2]["en"]
    assert "predict splice neoepitope candidates" in independent["bullets"][2]["en"]
    assert [bullet["refs"] for bullet in _entry(data, "cintellic")["bullets"]] == [
        ["C2"],
        ["C1"],
        ["C1", "C2"],
    ]
    assert [bullet["refs"] for bullet in _entry(data, "neuefische")["bullets"]] == [
        ["D3"],
        ["D1"],
    ]
    research = _entry(data, "research")
    assert [bullet["refs"] for bullet in research["bullets"]] == [
        ["L1", "L2"],
        ["L3"],
        ["L4"],
    ]
    assert "neural progenitor differentiation" in research["bullets"][2]["en"].lower()
    assert [project["id"] for project in data["selected_projects"]] == ["C1", "D1", "L5"]


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
        assert [category["name"] for category in categories] == [
            "Bioinformatics",
            "AI/ML & Developer Tools",
            "Experimental Research",
            "Data & Cloud Engineering",
        ]
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
        experimental = next(
            category for category in categories if category["name"] == "Experimental Research"
        )
        domains = next(
            group for group in experimental["groups"] if group["label"] == "Research Domains"
        )
        assert domains["items"] == [
            "DNA Damage & Repair",
            "Chromatin Architecture",
            "Alu Elements",
            "Extracellular Vesicles",
        ]

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
    l5 = canonical["projects"]["L5"]

    assert independent["role"]["en"] == "Independent Bioinformatics & ML/AI Engineer"
    assert any(
        "Snakemake" in bullet["en"] and bullet["refs"] == ["L5"]
        for bullet in independent["bullets"]
    )
    assert "capstone" in neuefische["bullets"][0]["en"].lower()
    assert "unpublished computational proof of concept" in l1["outcome"].lower()
    assert "validat" not in " ".join(l1["contributions"] + [l1["outcome"]]).lower()
    assert "validat" not in " ".join([l5["summary"], *l5["contributions"], l5["outcome"]]).lower()


def test_pdf_project_links_follow_language_routes(content_dir):
    en = prepare_data(content_dir, private_path=None, lang="en", target="comp-bio")
    de = prepare_data(content_dir, private_path=None, lang="de", target="comp-bio")

    assert en["project_links"]["L5"] == "https://jinholee.is-a.dev/projects/L5/"
    assert de["project_links"]["L5"] == "https://jinholee.is-a.dev/de/projects/L5/"
    assert en["selected_projects"][0]["web_url"] == en["project_links"]["L5"]
    assert de["selected_projects"][0]["web_url"] == de["project_links"]["L5"]
