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
    "comp-bio": ("HLA", "Snakemake", "MHCflurry", "11"),
    "ds-ml": ("BigQueryML", "Python", "TensorFlow"),
}

SKILL_CATEGORY_LABELS = {
    "en": [
        "Bioinformatics",
        "Experimental Research",
        "AI/ML & Developer Tools",
        "Data & Cloud Engineering",
    ],
    "de": [
        "Bioinformatik",
        "Experimentelle Forschung",
        "KI/ML & Entwicklerwerkzeuge",
        "Daten- & Cloud-Engineering",
    ],
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
        category_labels = SKILL_CATEGORY_LABELS[lang]
        if target == "ds-ml":
            # ds-ml flows two columns of unequal height (AI/ML + Data/Cloud vs
            # Bioinformatics); both extractors must carry all three and must not
            # carry Experimental Research.
            present = [label for label in category_labels if label in skill_region]
            assert set(present) == {category_labels[2], category_labels[0], category_labels[3]}
            assert category_labels[1] not in skill_region
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
        assert {f"{prefix}/projects/{pid}/" for pid in ("L1", "L2", "L5")} <= urls
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
