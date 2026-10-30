"""Concise, target-aware projection for the application PDF renderer.

This module selects from canonical CV facts; it never rewrites claims. Other
renderers continue to receive the complete content tree.
"""

from __future__ import annotations

import copy
from typing import Any

REPRESENTATIVE_PUBLICATION_KEYS = (
    "lee2021superres_dna_repair",
    "scherthan2019_ra223",
    "lee2019_combofish",
)

# Comp-bio application PDFs omit dropped agent-persona/tooling claims. Other
# renderers keep the canonical Skills/Experience trees.
_PDF_OMIT_SKILL_GROUPS = {
    "comp-bio": {"AI Agents"},
}
_PDF_OMIT_EXPERIENCE_REF_SETS = {
    "comp-bio": {frozenset({"D4"})},
}

_AWARD_TITLES = {
    "bridge": {
        "Google Cloud Certified - Associate Cloud Engineer",
        "DAAD PROMOS Scholarship",
    },
    "comp-bio": {
        "“Most Patient-Centric Solution” Award",
        "DeGBS Poster Award",
        "Received admission — Vienna BioCenter PhD Programme",
        "Genetic manipulation of mammalian cells by lentiviral vectors",
        "DAAD PROMOS Scholarship",
    },
    "ds-ml": {
        "Google Cloud Certified - Associate Cloud Engineer",
        "“Most Patient-Centric Solution” Award",
    },
}


def _english(value: str | dict[str, str]) -> str:
    return value["en"] if isinstance(value, dict) else value


def _omit_pdf_skill_groups(skills: dict[str, Any], *, target: str) -> None:
    omit = _PDF_OMIT_SKILL_GROUPS.get(target)
    if not omit:
        return
    for category in skills.get("categories", []):
        category["groups"] = [
            group for group in category["groups"] if _english(group["label"]) not in omit
        ]


def _omit_pdf_experience_bullets(experience: list[dict[str, Any]], *, target: str) -> None:
    omit_refs = _PDF_OMIT_EXPERIENCE_REF_SETS.get(target)
    if not omit_refs:
        return
    for entry in experience:
        entry["bullets"] = [
            bullet
            for bullet in entry["bullets"]
            if frozenset(bullet.get("refs") or []) not in omit_refs
        ]


def _localized(lang: str, en: str, de: str) -> str:
    return de if lang == "de" else en


def _entry_by_id(data: dict[str, Any], entry_id: str) -> dict[str, Any]:
    return next(entry for entry in data["experience"] if entry["id"] == entry_id)


def _bullet_by_refs(entry: dict[str, Any], refs: list[str], lang: str) -> str:
    bullet = next(bullet for bullet in entry["bullets"] if bullet.get("refs") == refs)
    return bullet[lang]


def _project(data: dict[str, Any], project_id: str) -> dict[str, Any]:
    return data["projects"][project_id]


def _proof(data: dict[str, Any], project_id: str) -> dict[str, Any]:
    project = _project(data, project_id)
    return {
        "source_ids": [project_id],
        "title": project["title"].split(" – ")[0],
        "text": project["summary"],
        "url": data["project_links"][project_id],
        "links": [{"id": project_id, "url": data["project_links"][project_id]}],
    }


def _category(data: dict[str, Any], name: str) -> dict[str, Any]:
    return next(category for category in data["skills"]["categories"] if category["name"] == name)


def _group(category: dict[str, Any], label: str) -> dict[str, Any]:
    return next(group for group in category["groups"] if group["label"] == label)


def _skill_sources(data: dict[str, Any], lang: str) -> dict[str, dict[str, Any]]:
    category_labels = {
        "ai": _localized(lang, "AI/ML & Developer Tools", "KI/ML & Entwicklerwerkzeuge"),
        "bio": _localized(lang, "Bioinformatics", "Bioinformatik"),
        "data": _localized(lang, "Data & Cloud Engineering", "Daten- & Cloud-Engineering"),
    }
    group_labels = {
        "ml": _localized(lang, "Machine Learning", "Maschinelles Lernen"),
        "browser": _localized(lang, "Browser ML Delivery", "ML im Browser"),
        "dev": _localized(lang, "Developer Environments", "Entwicklungsumgebungen"),
        "genomics": _localized(lang, "Genomics", "Genomik"),
        "workflows": _localized(lang, "Bioinformatics Workflows", "Bioinformatik-Workflows"),
        "immuno": _localized(lang, "Immunoinformatics", "Immunoinformatik"),
        "programming": _localized(lang, "Programming & Data", "Programmierung & Daten"),
        "cloud": _localized(lang, "Cloud & Analytics", "Cloud & Analytik"),
        "modelling": _localized(lang, "Computational Modelling", "Computergestützte Modellierung"),
    }
    categories = {key: _category(data, value) for key, value in category_labels.items()}
    return {
        "ml": _group(categories["ai"], group_labels["ml"]),
        "browser": _group(categories["ai"], group_labels["browser"]),
        "dev": _group(categories["ai"], group_labels["dev"]),
        "genomics": _group(categories["bio"], group_labels["genomics"]),
        "workflows": _group(categories["bio"], group_labels["workflows"]),
        "immuno": _group(categories["bio"], group_labels["immuno"]),
        "programming": _group(categories["data"], group_labels["programming"]),
        "cloud": _group(categories["data"], group_labels["cloud"]),
        "modelling": _group(categories["ai"], group_labels["modelling"]),
    }


def _pick(items: list[str], *wanted: str) -> list[str]:
    selected = [item for item in items if item in wanted]
    missing = set(wanted) - set(selected)
    if missing:
        raise ValueError(f"one-page PDF skill item(s) missing: {sorted(missing)}")
    return selected


def build_one_page_layout(data: dict[str, Any], *, target: str, lang: str) -> dict[str, Any]:
    """Build the approved one-page display model from resolved canonical facts."""
    independent = _entry_by_id(data, "independent")
    cintellic = _entry_by_id(data, "cintellic")
    neuefische = _entry_by_id(data, "neuefische")
    research = _entry_by_id(data, "research")

    def entry(
        source_ids: list[str],
        *,
        org: str,
        role: str,
        period: dict[str, Any],
        bullets: list[str],
    ) -> dict[str, Any]:
        return {
            "source_ids": source_ids,
            "org": org,
            "role": role,
            "period": period,
            "bullets": bullets,
        }

    grouped_industry_period = {
        "start": neuefische["period"]["start"],
        "end": cintellic["period"]["end"],
    }
    research_org = "FZ Jülich · IMP Vienna · KIP Heidelberg · NCT/DKFZ · SNU"
    leadership = _localized(
        lang,
        "Secured third-party funding and supervised 10+ students.",
        "Einwerbung von Drittmitteln und Betreuung von 10+ Studierenden.",
    )
    extras = {
        "independent": [bullet[lang] for bullet in independent["bullets"][3:]],
        "cintellic": [bullet[lang] for bullet in cintellic["bullets"][3:]],
        "neuefische": [bullet[lang] for bullet in neuefische["bullets"][2:]],
        "research": [bullet[lang] for bullet in research["bullets"][3:]],
    }

    if target == "bridge":
        experience = [
            entry(
                ["independent"],
                org=independent["org"]["name"],
                role=independent["role"],
                period=independent["period"],
                bullets=[
                    _bullet_by_refs(independent, ["D4"], lang),
                    _bullet_by_refs(independent, ["D2"], lang),
                ]
                + extras["independent"],
            ),
            entry(
                ["cintellic", "neuefische"],
                org="Cintellic GmbH · neuefische GmbH",
                role=_localized(
                    lang, "Industry data & machine learning", "Industrie: Daten & Machine Learning"
                ),
                period=grouped_industry_period,
                bullets=[
                    _bullet_by_refs(cintellic, ["C2"], lang),
                    _bullet_by_refs(neuefische, ["D1"], lang),
                ]
                + extras["cintellic"]
                + extras["neuefische"],
            ),
            entry(
                ["research"],
                org=research_org,
                role=research["role"],
                period=research["period"],
                bullets=[
                    _bullet_by_refs(research, ["L1", "L2"], lang),
                    _bullet_by_refs(research, ["L3"], lang),
                ]
                + extras["research"],
            ),
        ]
        proof_ids = ("C1", "L5")
    elif target == "ds-ml":
        experience = [
            entry(
                ["independent"],
                org=independent["org"]["name"],
                role=independent["role"],
                period=independent["period"],
                bullets=[
                    _bullet_by_refs(independent, ["D4"], lang),
                    _bullet_by_refs(independent, ["D2"], lang),
                ]
                + extras["independent"],
            ),
            entry(
                ["cintellic"],
                org=cintellic["org"]["name"],
                role=cintellic["role"],
                period=cintellic["period"],
                bullets=[
                    _bullet_by_refs(cintellic, ["C1"], lang),
                    _bullet_by_refs(cintellic, ["C2"], lang),
                ]
                + extras["cintellic"],
            ),
            entry(
                ["neuefische"],
                org=neuefische["org"]["name"],
                role=neuefische["role"],
                period=neuefische["period"],
                bullets=[
                    _bullet_by_refs(neuefische, ["D1"], lang),
                    _bullet_by_refs(neuefische, ["D3"], lang),
                ]
                + extras["neuefische"],
            ),
            entry(
                ["research"],
                org=research_org,
                role=_localized(
                    lang, "Scientific research foundation", "Wissenschaftliche Grundlage"
                ),
                period=research["period"],
                bullets=[_bullet_by_refs(research, ["L3"], lang)] + extras["research"],
            ),
        ]
        proof_ids = ("C1", "D1")
    else:
        experience = [
            entry(
                ["independent"],
                org=independent["org"]["name"],
                role=independent["role"],
                period=independent["period"],
                bullets=[_bullet_by_refs(independent, ["L5"], lang)] + extras["independent"],
            ),
            entry(
                ["cintellic", "neuefische"],
                org="Cintellic GmbH · neuefische GmbH",
                role=_localized(
                    lang, "Industry data & machine learning", "Industrie: Daten & Machine Learning"
                ),
                period=grouped_industry_period,
                bullets=[
                    _bullet_by_refs(cintellic, ["C2"], lang),
                    _bullet_by_refs(neuefische, ["D3"], lang),
                ]
                + extras["cintellic"]
                + extras["neuefische"],
            ),
            entry(
                ["research"],
                org=research_org,
                role=research["role"],
                period=research["period"],
                bullets=[
                    _bullet_by_refs(research, ["L1", "L2"], lang),
                    _project(data, "L3")["summary"],
                    _bullet_by_refs(research, ["L4"], lang),
                    leadership,
                ]
                + extras["research"],
            ),
        ]
        proof_ids = ("L5",)

    proofs = [_proof(data, project_id) for project_id in proof_ids]
    if target == "comp-bio":
        l2 = _project(data, "L2")
        l1 = _project(data, "L1")
        proofs.append(
            {
                "source_ids": ["L2", "L1"],
                "title": _localized(lang, "HLA & neoantigen work", "HLA- & Neoantigen-Arbeit"),
                "text": l2["summary"] + " " + l1["summary"],
                "url": data["project_links"]["L2"],
                "links": [
                    {"id": project_id, "url": data["project_links"][project_id]}
                    for project_id in ("L2", "L1")
                ],
            }
        )

    source = _skill_sources(data, lang)
    if target == "bridge":
        skills = [
            {
                "label": "AI / ML",
                "items": _pick(
                    source["ml"]["items"],
                    "TensorFlow",
                    "Keras",
                    "OpenCV",
                    "MLflow",
                    "BigQueryML",
                ),
            },
            {
                "label": _localized(lang, "Data & cloud", "Daten & Cloud"),
                "items": _pick(source["programming"]["items"], "Python (Expert)", "SQL", "dbt")
                + _pick(source["cloud"]["items"], "GCP", "BigQuery"),
            },
            {
                "label": _localized(lang, "Bioinformatics", "Bioinformatik"),
                "items": _pick(source["genomics"]["items"], "NGS", "RNA-Seq", "Splice Analysis")
                + _pick(source["workflows"]["items"], "Snakemake")
                + _pick(source["immuno"]["items"], "HLA Typing"),
            },
        ]
    elif target == "ds-ml":
        skills = [
            {"label": source["ml"]["label"], "items": source["ml"]["items"]},
            {
                "label": _localized(lang, "Engineering", "Engineering"),
                "items": _pick(source["programming"]["items"], "Python (Expert)", "SQL", "dbt")
                + _pick(source["cloud"]["items"], "GCP", "BigQuery")
                + _pick(source["dev"]["items"], "Docker"),
            },
            {"label": source["browser"]["label"], "items": source["browser"]["items"]},
        ]
    else:
        skills = [
            {
                "label": source["genomics"]["label"],
                "items": source["genomics"]["items"],
            },
            {
                "label": source["workflows"]["label"],
                "items": _pick(
                    source["workflows"]["items"],
                    "Snakemake",
                    "HISAT2/STAR",
                    "samtools/bcftools",
                    "OptiType",
                ),
            },
            {
                "label": source["immuno"]["label"],
                "items": source["immuno"]["items"]
                + _pick(source["modelling"]["items"], "MHCflurry"),
            },
        ]

    metric_labels = {
        "processes": _localized(lang, "processes → GCP", "Prozesse → GCP"),
        "coached": _localized(lang, "specialists coached", "Fachkräfte gecoacht"),
        "publications": _localized(lang, "research publications", "Forschungspublikationen"),
        "research": _localized(lang, "research portfolio", "Forschungsportfolio"),
        "certified": _localized(lang, "certified engineer", "zertifizierter Engineer"),
        "wes": "WES · RNA-Seq",
        "mhc": _localized(lang, "MHC-I prediction", "MHC-I-Vorhersage"),
        "workflow": "Snakemake · Cloud",
    }
    if target == "bridge":
        metrics = [
            ("1,000+", "processes"),
            ("100+", "coached"),
            ("12", "publications"),
            ("8 years" if lang == "en" else "8 Jahre", "research"),
        ]
    elif target == "ds-ml":
        metrics = [
            ("1,000+", "processes"),
            ("100+", "coached"),
            ("12", "publications"),
            ("GCP", "certified"),
        ]
    else:
        metrics = [("NGS", "wes"), ("HLA", "mhc"), ("12", "publications"), ("Python", "workflow")]

    focus = {
        "bridge": {
            "art": "cross-domain",
            "title": _localized(lang, "Cross-domain delivery", "Interdisziplinäre Umsetzung"),
            "title_lines": [
                _localized(lang, "Cross-domain delivery", "Interdisziplinäre Umsetzung")
            ],
            "subtitle": _localized(
                lang,
                "Machine learning · cloud · bioinformatics",
                "Machine Learning · Cloud · Bioinformatik",
            ),
        },
        "ds-ml": {
            "art": "production-ml",
            "title": "Production ML & Data Science",
            "title_lines": ["Production ML", "& Data Science"],
            "subtitle": "GCP · BigQueryML · AI systems",
        },
        "comp-bio": {
            "art": "genomics",
            "title": _localized(lang, "Computational biology", "Computational Biology"),
            "title_lines": [_localized(lang, "Computational biology", "Computational Biology")],
            "subtitle": _localized(
                lang,
                "NGS · HLA · splice-derived candidates",
                "NGS · HLA · splice-abgeleitete Kandidaten",
            ),
        },
    }[target]

    profile = data["profile"]["tagline"]
    for marker in (" Maintains a public", " Pflegt eine öffentliche"):
        if marker in profile:
            profile = profile.split(marker, 1)[0]

    gcp_title = "Google Cloud Certified - Associate Cloud Engineer"
    credentials = [award for award in data["awards"] if award["title"] == gcp_title]
    publication_boundary = None
    if target == "comp-bio":
        credentials = [award for award in data["awards"] if "DeGBS" in award["title"]][:1]
        publication_boundary = _localized(
            lang,
            "12 peer-reviewed publications are from the separate experimental-biophysics portfolio—not genomics papers.",
            "12 peer-reviewte Publikationen stammen aus dem separaten Portfolio der experimentellen Biophysik — nicht aus Genomik-Publikationen.",
        )

    return {
        "target": target,
        "monogram": "JL",
        "focus": focus,
        "profile": profile,
        "metrics": [{"value": value, "label": metric_labels[label]} for value, label in metrics],
        "experience": experience,
        "proofs": proofs,
        "skills": skills,
        "education": copy.deepcopy(
            data["education"][:1] if target == "comp-bio" else data["education"]
        ),
        "credentials": credentials,
        "publication_boundary": publication_boundary,
        "languages": copy.deepcopy(data["languages"]),
    }


def project_pdf_content(content: dict[str, Any], *, target: str, lang: str) -> dict[str, Any]:
    """Return a concise application-PDF view without mutating ``content``."""
    result = copy.deepcopy(content)

    # The target-specific tagline is the compact positioning block. Detailed
    # evidence remains visible in Experience, Projects, and Publications.
    result["profile"]["paragraphs"] = []

    # Experience ordering is resolved in content_loader for every renderer; the
    # PDF shares that target-ordered experience, minus export-path omissions.
    _omit_pdf_skill_groups(result["skills"], target=target)
    _omit_pdf_experience_bullets(result["experience"], target=target)

    for education in result["education"]:
        education.pop("thesis", None)

    result["languages"] = [
        language for language in result["languages"] if language["proficiency"] != "passive"
    ]

    # Keep the concise, role-based volunteer categories in every target. The
    # Environment list stays to its lead entry; Community remains web-only.
    volunteer_keep = {"Environment", "Sports", "Music"}
    result["volunteer"] = {
        "categories": [
            {
                "name": category["name"],
                "entries": (
                    category["entries"][:1]
                    if _english(category["name"]) == "Environment"
                    else category["entries"]
                ),
            }
            for category in result["volunteer"]["categories"]
            if _english(category["name"]) in volunteer_keep
        ]
    }

    allowed_awards = _AWARD_TITLES[target]
    result["awards"] = [
        award for award in result["awards"] if _english(award["title"]) in allowed_awards
    ]
    if target == "comp-bio":
        # Keep the focused application PDF compact; the canonical award notes
        # remain available to web and machine-readable renderers.
        for award in result["awards"]:
            if _english(award["title"]) == (
                "Genetic manipulation of mammalian cells by lentiviral vectors"
            ):
                award.pop("note", None)
    if target == "bridge":
        # The scholarship remains visible; its immunotherapy-specific internship
        # note belongs in the focused biological view rather than the General CV.
        for award in result["awards"]:
            if _english(award["title"]) == "DAAD PROMOS Scholarship":
                award.pop("note", None)

    all_publications = result["publications"]
    by_key = {publication.key: publication for publication in all_publications}
    missing = [key for key in REPRESENTATIVE_PUBLICATION_KEYS if key not in by_key]
    if missing:
        raise ValueError(f"representative PDF publication key(s) missing: {missing}")
    result["selected_publications"] = [by_key[key] for key in REPRESENTATIVE_PUBLICATION_KEYS]

    website = result["personal"]["links"]["website"].rstrip("/")
    language_prefix = "/de" if lang == "de" else ""
    project_links = {
        project_id: f"{website}{language_prefix}/projects/{project_id}/"
        for project_id in result["projects"]
    }
    result["project_links"] = project_links
    for project in result["selected_projects"]:
        project["web_url"] = project_links[project["id"]]

    return result
