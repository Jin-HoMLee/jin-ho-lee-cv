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
            independent_n = 2 if target == "comp-bio" else 3
            counts = {entry["id"]: len(entry["bullets"]) for entry in data["experience"]}
            assert counts == {
                "independent": independent_n,
                "cintellic": 3,
                "neuefische": 2,
                "research": 3,
            }, f"{lang}/{target} dropped experience bullets: {counts}"
            for entry_id, markers_by_lang in inventory.items():
                bullets = _entry(data, entry_id)["bullets"]
                labels = " · ".join(bullet[lang] for bullet in bullets)
                markers = markers_by_lang[lang]
                if target == "comp-bio" and entry_id == "independent":
                    markers = tuple(
                        marker for marker in markers if marker not in ("Agentic AI", "Agenten-KI")
                    )
                for marker in markers:
                    assert marker in labels, f"{lang}/{target} {entry_id} missing {marker!r}"


def test_pdf_projection_does_not_change_canonical_content(content_dir):
    canonical = load_content(content_dir, lang="en", target="comp-bio")
    projected = prepare_data(content_dir, private_path=None, lang="en", target="comp-bio")

    assert len(canonical["publications"]) == 16
    assert len(projected["publications"]) == 4
    # Comp-bio PDFs omit dropped agent-persona tooling; other groups stay identical.
    pdf_omitted = {"Claude Code", "Codex", "OpenCode", "Pi", "Grok", "Cursor", "Kimi"}
    assert _skill_items(projected).isdisjoint(pdf_omitted)
    assert _skill_items(canonical) - pdf_omitted == _skill_items(projected)
    assert all("thesis" in education for education in canonical["education"])
    assert all("thesis" not in education for education in projected["education"])


def test_comp_bio_projection_keeps_relevant_quantified_evidence(content_dir):
    data = prepare_data(content_dir, private_path=None, lang="en", target="comp-bio")

    assert data["profile"]["paragraphs"] == []
    assert "Twelve peer-reviewed" in data["profile"]["tagline"]
    assert "doctorate not awarded" not in data["profile"]["tagline"]
    assert "M.Sc." in data["profile"]["tagline"]
    assert len(_entry(data, "independent")["bullets"]) == 2
    assert "Snakemake" in _entry(data, "independent")["bullets"][0]["en"]
    assert "1,000+" in _entry(data, "cintellic")["bullets"][0]["en"]
    assert "100+" in _entry(data, "neuefische")["bullets"][0]["en"]
    assert len(_entry(data, "research")["bullets"]) == 3
    assert "NCT/DKFZ" in _entry(data, "research")["bullets"][0]["en"]
    assert "not SNU splice-candidate validation" in _entry(data, "research")["bullets"][0]["en"]
    assert "doctorate not awarded" in _entry(data, "research")["role"]

    skills = _skill_items(data)
    assert {"RNA-Seq", "HLA Typing", "MHCflurry", "Snakemake", "Docker"} <= skills
    assert {"TensorFlow.js", "WezTerm"} <= skills
    assert {"Claude Code", "Codex", "OpenCode", "Grok", "Cursor", "Kimi"}.isdisjoint(skills)


def test_pdf_targets_project_experience_and_secondary_detail(content_dir):
    expected_bullets = {
        "bridge": {"independent": 3, "cintellic": 3, "neuefische": 2, "research": 3},
        "comp-bio": {"independent": 2, "cintellic": 3, "neuefische": 2, "research": 3},
        "ds-ml": {"independent": 3, "cintellic": 3, "neuefische": 2, "research": 3},
    }
    expected_awards = {
        "bridge": {"Google Cloud Certified - Associate Cloud Engineer", "DAAD PROMOS Scholarship"},
        "comp-bio": {
            "“Most Patient-Centric Solution” Award",
            "DeGBS Poster Award",
            "Selected for admission — Vienna BioCenter PhD Programme",
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
            "independent": [["L5"], ["D2"]],
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
    assert "12 peer-reviewed" in tagline
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
    expected_order = {
        "bridge": [
            "AI/ML & Developer Tools",
            "Bioinformatics",
            "Data & Cloud Engineering",
            "Experimental Research",
        ],
        "comp-bio": [
            "Bioinformatics",
            "AI/ML & Developer Tools",
            "Data & Cloud Engineering",
            "Experimental Research",
        ],
    }
    for target in ("bridge", "comp-bio"):
        data = prepare_data(content_dir, private_path=None, lang="en", target=target)
        categories = data["skills"]["categories"]
        assert {category["name"] for category in categories} == full
        assert [category["name"] for category in categories] == expected_order[target]
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
    l1_text = " ".join(l1["contributions"] + [l1["outcome"]]).lower()
    assert "validated neoantigen" not in l1_text
    assert "tumor-specific" not in l1_text
    assert "no experimental validation" in l1["outcome"].lower()
    assert "validat" not in " ".join([l5["summary"], *l5["contributions"], l5["outcome"]]).lower()


def test_pdf_project_links_follow_language_routes(content_dir):
    en = prepare_data(content_dir, private_path=None, lang="en", target="comp-bio")
    de = prepare_data(content_dir, private_path=None, lang="de", target="comp-bio")

    assert en["project_links"]["L5"] == "https://jinholee.is-a.dev/projects/L5/"
    assert de["project_links"]["L5"] == "https://jinholee.is-a.dev/de/projects/L5/"
    assert en["selected_projects"][0]["web_url"] == en["project_links"]["L5"]
    assert de["selected_projects"][0]["web_url"] == de["project_links"]["L5"]


def test_comp_bio_pdf_honesty_boundaries_for_application_export(content_dir):
    data = prepare_data(content_dir, private_path=None, lang="en", target="comp-bio")
    research = _entry(data, "research")
    independent = _entry(data, "independent")
    genomics = research["bullets"][0]["en"]
    tagline = data["profile"]["tagline"]

    assert research["role"] == "Doctoral & Post-Graduate Researcher (doctorate not awarded)"
    assert "PhD" not in research["role"]
    assert "Dr." not in research["role"]
    assert "M.Sc." in tagline
    assert "doctorate not awarded" not in tagline
    assert "NCT/DKFZ" in genomics
    assert "not SNU splice-candidate validation" in genomics
    assert [project["id"] for project in data["selected_projects"]] == ["L5", "L2", "L1"]
    assert "unpublished" in data["selected_projects"][2]["outcome"].lower()
    assert "patent" in data["selected_projects"][2]["outcome"].lower()
    assert "Unpublished" in data["selected_projects"][1]["outcome"]
    assert "not claimed as already run on SLURM" in data["selected_projects"][0]["outcome"]
    assert all(bullet.get("refs") != ["D4"] for bullet in independent["bullets"])
    assert "4 selected of 12 peer-reviewed" in data["publications_summary"]
    assert "long-read" not in tagline.lower()
    assert "proteomic" not in tagline.lower()
    assert "mass spectrometry" not in tagline.lower()
    assert "multi-omics" not in tagline.lower()
    assert "multiomics" not in tagline.lower()
