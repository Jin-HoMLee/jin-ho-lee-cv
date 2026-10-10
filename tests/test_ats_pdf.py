"""ATS and PDF-navigation regression guard for every public PDF variant.

The guard uses Poppler and pypdf as independent extractors. It verifies a single
section order, unsplit labels, target keywords, a real text layer, two-page limit,
and that links/bookmarks are metadata over ordinary visible text.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from pypdf import PdfReader

from scripts.export_application import export_application_cv

REPO_ROOT = Path(__file__).resolve().parent.parent
VARIANTS = [(lang, target) for lang in ("en", "de") for target in ("bridge", "comp-bio", "ds-ml")]

SECTION_LABELS = {
    "en": {
        "profile": "PROFILE",
        "skills": "SKILLS",
        "experience": "EXPERIENCE",
        "projects": "SELECTED PROJECTS",
        "education": "EDUCATION",
        "publications": "PUBLICATIONS",
        "selected_publications": "SELECTED PUBLICATIONS",
        "awards": "AWARDS & CERTIFICATIONS",
        "languages": "LANGUAGES",
        "volunteer": "VOLUNTEER",
    },
    "de": {
        "profile": "PROFIL",
        "skills": "KENNTNISSE",
        "experience": "BERUFSERFAHRUNG",
        "projects": "AUSGEWÄHLTE PROJEKTE",
        "education": "AUSBILDUNG",
        "publications": "PUBLIKATIONEN",
        "selected_publications": "AUSGEWÄHLTE PUBLIKATIONEN",
        "awards": "AUSZEICHNUNGEN & ZERTIFIKATE",
        "languages": "SPRACHEN",
        "volunteer": "EHRENAMTLICH",
    },
}

TARGET_KEYWORDS = {
    "bridge": ("GCP", "100+", "Python"),
    "comp-bio": ("HLA", "Snakemake", "MHCflurry", "100+"),
    "ds-ml": ("BigQueryML", "Python", "TensorFlow"),
}

# Expected PDF reading order (left column top→bottom, then right) must match
# content/skills.yaml category_order per target.
SKILL_CATEGORY_LABELS = {
    "en": {
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
        "ds-ml": [
            "AI/ML & Developer Tools",
            "Data & Cloud Engineering",
            "Bioinformatics",
        ],
    },
    "de": {
        "bridge": [
            "KI/ML & Entwicklerwerkzeuge",
            "Bioinformatik",
            "Daten- & Cloud-Engineering",
            "Experimentelle Forschung",
        ],
        "comp-bio": [
            "Bioinformatik",
            "KI/ML & Entwicklerwerkzeuge",
            "Daten- & Cloud-Engineering",
            "Experimentelle Forschung",
        ],
        "ds-ml": [
            "KI/ML & Entwicklerwerkzeuge",
            "Daten- & Cloud-Engineering",
            "Bioinformatik",
        ],
    },
}

EXPERIMENTAL_LABEL = {
    "en": "Experimental Research",
    "de": "Experimentelle Forschung",
}


def _have(tool: str) -> bool:
    return shutil.which(tool) is not None


pytestmark = pytest.mark.skipif(
    not (_have("typst") and _have("pdftotext")),
    reason="needs typst + pdftotext (poppler) to build and inspect PDFs",
)


def _filename(lang: str, target: str) -> str:
    return f"cv-{lang}.pdf" if target == "bridge" else f"cv-{lang}-{target}.pdf"


def _outline_titles(items) -> list[str]:
    titles = []
    for item in items:
        if isinstance(item, list):
            titles.extend(_outline_titles(item))
        else:
            title = getattr(item, "title", None)
            if title:
                titles.append(str(title))
    return titles


def _link_counts(reader: PdfReader) -> tuple[int, int, set[str]]:
    external = internal = 0
    urls: set[str] = set()
    for page in reader.pages:
        for reference in page.get("/Annots", []):
            annotation = reference.get_object()
            if annotation.get("/Subtype") != "/Link":
                continue
            action = annotation.get("/A")
            if action is not None and action.get_object().get("/S") == "/URI":
                external += 1
                urls.add(str(action.get_object()["/URI"]))
            elif annotation.get("/Dest") is not None or (
                action is not None and action.get_object().get("/S") == "/GoTo"
            ):
                internal += 1
    return external, internal, urls


@pytest.fixture(scope="module", params=VARIANTS, ids=lambda pair: f"{pair[0]}-{pair[1]}")
def built_pdf(request):
    lang, target = request.param
    out = REPO_ROOT / "dist" / _filename(lang, target)
    if out.exists():
        out.unlink()
    result = subprocess.run(
        [sys.executable, "-m", "pdf.build", "--lang", lang, "--target", target],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"PDF build failed:\n{result.stderr}"
    assert out.exists(), f"expected {out} to be written"

    poppler = subprocess.run(
        ["pdftotext", str(out), "-"], check=True, capture_output=True, text=True
    ).stdout
    reader = PdfReader(out)
    pypdf_text = "\n".join(page.extract_text() or "" for page in reader.pages)
    return lang, target, out, reader, poppler, pypdf_text


def _expected_headings(lang: str, target: str) -> list[str]:
    labels = SECTION_LABELS[lang]
    publication_key = "selected_publications" if target == "comp-bio" else "publications"
    return [
        labels["profile"],
        labels["skills"],
        labels["experience"],
        labels["projects"],
        labels["education"],
        labels[publication_key],
        labels["awards"],
        labels["languages"],
        labels["volunteer"],
    ]


def _assert_heading_order(text: str, headings: list[str], extractor: str) -> None:
    # Match complete, standalone section lines: the clickable contents line also
    # mentions several section names and must never mask a shuffled body stream.
    lines = [line.strip() for line in text.splitlines()]
    positions = []
    for heading in headings:
        matches = [index for index, line in enumerate(lines) if line == heading]
        assert len(matches) == 1, (
            f"{extractor}: missing, split, or duplicated section label {heading!r}: {matches}"
        )
        positions.append(matches[0])
    assert positions == sorted(positions), f"{extractor}: wrong section order: {positions}"


def test_all_variants_are_two_page_flat_text_in_one_order(built_pdf):
    lang, target, _, reader, poppler, pypdf_text = built_pdf
    headings = _expected_headings(lang, target)

    assert len(reader.pages) <= 2, f"{lang}/{target} grew to {len(reader.pages)} pages"
    for extractor, text in (("poppler", poppler), ("pypdf", pypdf_text)):
        assert len(text) > 800, f"{extractor}: PDF appears image-only or incomplete"
        assert "Jin-Ho Lee" in text
        assert "jinho.michael.lee@gmail.com" in text
        _assert_heading_order(text, headings, extractor)
        for keyword in TARGET_KEYWORDS[target]:
            assert keyword in text, f"{extractor}: missing target keyword {keyword!r}"

        skill_region = text.split(headings[1], 1)[1].split(headings[2], 1)[0]
        category_labels = SKILL_CATEGORY_LABELS[lang][target]
        present = [label for label in category_labels if label in skill_region]
        assert set(present) == set(category_labels), (
            f"{extractor}: skills membership {present} != {category_labels}"
        )
        if target == "ds-ml":
            # Unequal two-column height (AI/ML + Data/Cloud vs Bioinformatics)
            # makes extractor reading order non-linear; membership is the guard.
            assert EXPERIMENTAL_LABEL[lang] not in skill_region
        else:
            positions = [skill_region.index(label) for label in category_labels]
            assert positions == sorted(positions), (
                f"{extractor}: wrong skills reading order: {positions}"
            )

        removed_languages = (
            ("French", "Italian") if lang == "en" else ("Französisch", "Italienisch")
        )
        assert all(language not in text for language in removed_languages)

    if lang == "en":
        assert "Jülich" in poppler and "Jülich" in pypdf_text
    else:
        assert any(ch in poppler for ch in "äöüßÄÖÜ")
        assert any(ch in pypdf_text for ch in "äöüßÄÖÜ")


def _page_text(pdf: Path, page: int) -> list[str]:
    """Non-empty, stripped lines of a single PDF page via Poppler."""
    text = subprocess.run(
        ["pdftotext", "-f", str(page), "-l", str(page), "-layout", str(pdf), "-"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return [line.strip() for line in text.splitlines() if line.strip()]


def test_comp_bio_experience_completes_page_one(built_pdf):
    """The comp-bio variant must break the page after the complete Experience
    section: page 1 ends once Experience is done and page 2 opens directly with
    Selected Projects, in every language.

    This is a deliberate comp-bio-only layout promise (captain request); the
    bridge and ds-ml variants keep their natural flow. If an experience bullet
    ever spills onto page 2, that page's first line is the stray bullet rather
    than the Selected Projects heading, so the assertion below catches it.
    """
    lang, target, out, _, _, _ = built_pdf
    if target != "comp-bio":
        pytest.skip("page-1 Experience boundary is a comp-bio-only promise")

    labels = SECTION_LABELS[lang]
    page1 = _page_text(out, 1)
    page2 = _page_text(out, 2)

    assert labels["experience"] in page1
    assert labels["projects"] not in page1, "Selected Projects leaked onto page 1"
    assert page2[0] == labels["projects"], (
        f"{lang}/comp-bio page 2 starts with {page2[0]!r}, not {labels['projects']!r} "
        "- an Experience bullet spilled past page 1"
    )


def test_all_variants_have_outline_and_navigation_links(built_pdf):
    lang, target, _, reader, poppler, _ = built_pdf
    headings = _expected_headings(lang, target)
    outline = _outline_titles(reader.outline)

    for heading in headings:
        assert heading in outline, f"missing bookmark {heading!r}; got {outline}"

    external, internal, urls = _link_counts(reader)
    assert external >= 8, "expected contact, project, and publication web links"
    assert internal >= 6, "expected the compact contents line to link to major sections"
    assert "https://orcid.org/0009-0001-8784-1771" in urls
    assert any(url.startswith("https://scholar.google.com/citations?") for url in urls)
    prefix = "https://jinholee.is-a.dev/de" if lang == "de" else "https://jinholee.is-a.dev"
    assert f"{prefix}/#publications" in urls
    if target == "comp-bio":
        assert {f"{prefix}/projects/{pid}/" for pid in ("L5", "L2", "L1")} <= urls
    assert "ORCID" in poppler and "Google Scholar" in poppler


def test_all_variants_avoid_fragile_pdf_interactivity(built_pdf):
    _, _, _, reader, _, _ = built_pdf
    root = reader.trailer["/Root"]

    assert "/AcroForm" not in root
    assert "/OCProperties" not in root
    assert "/OpenAction" not in root
    assert "/AA" not in root
    names = root.get("/Names")
    assert names is None or "/JavaScript" not in names.get_object()
    forbidden_annotations = {"/RichMedia", "/Screen", "/Widget", "/Movie", "/Sound"}
    for page in reader.pages:
        assert "/AA" not in page
        for reference in page.get("/Annots", []):
            annotation = reference.get_object()
            assert annotation.get("/Subtype") not in forbidden_annotations
            action = annotation.get("/A")
            assert action is None or action.get_object().get("/S") != "/JavaScript"


# --- tailored exports (per-package tailoring.yaml) ------------------------------

# The DAiNA package's captain-approved tailoring wording: a longer comp-bio
# tagline plus one appended Mentoring bullet on the research entry. Without the
# tailored compaction the appended bullet is the stray first line of page two.
_TAILORED_TAGLINE = {
    "en": (
        "Computational biology / bioinformatics: hands-on NGS workflows on real-patient "
        "WES/NGS data (HLA typing, patient-specific cancer-target screening) and predicted "
        "splice-derived MHC-I neoepitope candidates."
    ),
    "de": (
        "Computational Biology / Bioinformatik: praktische NGS-Workflows mit realen "
        "Patient:innen-WES/NGS-Daten (HLA-Typisierung, patientenspezifisches "
        "Krebstarget-Screening) und vorhergesagte splice-abgeleitete "
        "MHC-I-Neoepitop-Kandidaten."
    ),
}

_TAILORED_BULLET = {
    "en": (
        "Mentoring: Co-selected two DAAD scholarship interns (CV and motivation-letter "
        "screening, interviews) with the supervisor."
    ),
    "de": (
        "Mentoring: Mitauswahl von zwei DAAD-geförderten Praktikumsplätzen (Sichtung von "
        "Lebenslauf und Motivationsschreiben, Interviews) gemeinsam mit dem Betreuer."
    ),
}


def _write_tailored_package(apps: Path, slug: str, lang: str) -> None:
    """Minimal applications/ package whose tailoring.yaml matches the DAiNA shape."""
    pkg = apps / slug
    pkg.mkdir(parents=True)
    (pkg / "application.yaml").write_text(f"language: {lang}\n", encoding="utf-8")
    (pkg / "cv-tailoring.md").write_text("variant: comp-bio\n", encoding="utf-8")
    (pkg / "tailoring.yaml").write_text(
        "profile:\n"
        "  comp-bio:\n"
        "    tagline:\n"
        f'      en: "{_TAILORED_TAGLINE["en"]}"\n'
        f'      de: "{_TAILORED_TAGLINE["de"]}"\n'
        "experience:\n"
        "  research:\n"
        "    append:\n"
        f'      - en: "{_TAILORED_BULLET["en"]}"\n'
        f'        de: "{_TAILORED_BULLET["de"]}"\n'
        "        refs: [L4]\n",
        encoding="utf-8",
    )


@pytest.mark.parametrize("lang", ["en", "de"])
def test_tailored_export_keeps_complete_experience_on_page_one(lang: str, tmp_path: Path):
    """A tailored comp-bio export keeps the whole Experience section on page one.

    The extra `tailoring.yaml` bullet must land on page one with the rest of
    Experience and page two must still open with Selected Projects - the same
    promise the general comp-bio variant makes. Built end-to-end through the
    export recipe so the `--tailored` layout switch is covered too.
    """
    apps = tmp_path / "applications"
    _write_tailored_package(apps, "daina-2026", lang)

    manifest = export_application_cv("daina-2026", apps_dir=apps)
    assert manifest["cv"]["variant"] == "comp-bio"
    assert manifest["cv"]["tailoring"]["applied"], "tailoring must be applied"
    pdf = apps / "daina-2026" / manifest["cv"]["pdf_path"]

    labels = SECTION_LABELS[lang]
    page1 = _page_text(pdf, 1)
    page2 = _page_text(pdf, 2)

    assert len(PdfReader(pdf).pages) <= 2
    assert labels["experience"] in page1
    assert any("DAAD" in line for line in page1), "appended bullet must be on page 1"
    assert labels["projects"] not in page1, "Selected Projects leaked onto page 1"
    assert page2[0] == labels["projects"], (
        f"{lang}/tailored-comp-bio page 2 starts with {page2[0]!r}, not "
        f"{labels['projects']!r} - the appended Experience bullet spilled past page 1"
    )
