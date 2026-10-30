"""ATS, one-page, and PDF-navigation guards for every public CV variant.

Poppler and pypdf independently verify the semantic stream, section labels,
target evidence, ordinary text layer, A4 one-page contract, and safe links/bookmarks.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
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
        "volunteer": "EHRENAMT",
    },
}

TARGET_KEYWORDS = {
    "bridge": ("GCP", "100+", "Python"),
    "comp-bio": ("HLA", "Snakemake", "MHCflurry", "100+"),
    "ds-ml": ("BigQueryML", "Python", "TensorFlow"),
}

# Curated one-page skill groups, all projected from canonical skill items.
SKILL_CATEGORY_LABELS = {
    "en": {
        "bridge": ["AI / ML", "Data & cloud", "Bioinformatics"],
        "comp-bio": ["Genomics", "Bioinformatics Workflows", "Immunoinformatics"],
        "ds-ml": ["Machine Learning", "Engineering", "Browser ML Delivery"],
    },
    "de": {
        "bridge": ["AI / ML", "Daten & Cloud", "Bioinformatik"],
        "comp-bio": ["Genomik", "Bioinformatik-Workflows", "Immunoinformatik"],
        "ds-ml": ["Maschinelles Lernen", "Engineering", "ML im Browser"],
    },
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
    del target
    labels = SECTION_LABELS[lang]
    # Source-order extractors emit the left 62% column, then the right column.
    return [
        labels["experience"],
        labels["projects"],
        labels["profile"],
        labels["skills"],
        labels["education"],
        labels["publications"],
        labels["awards"],
        labels["languages"],
    ]


def _expected_poppler_headings(lang: str) -> list[str]:
    labels = SECTION_LABELS[lang]
    # Geometry-aware Poppler advances through the asymmetric columns by height.
    return [
        labels["experience"],
        labels["profile"],
        labels["skills"],
        labels["education"],
        labels["projects"],
        labels["publications"],
        labels["awards"],
        labels["languages"],
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


def test_all_variants_are_one_page_flat_text_in_one_order(built_pdf):
    lang, target, _, reader, poppler, pypdf_text = built_pdf
    headings = _expected_headings(lang, target)

    assert len(reader.pages) == 1, f"{lang}/{target} grew to {len(reader.pages)} pages"
    assert reader.pages[0].mediabox.width == pytest.approx(595.276, abs=0.1)
    assert reader.pages[0].mediabox.height == pytest.approx(841.89, abs=0.1)
    for extractor, text in (("poppler", poppler), ("pypdf", pypdf_text)):
        assert len(text) > 800, f"{extractor}: PDF appears image-only or incomplete"
        assert "Jin-Ho Lee" in text
        assert "jinho.michael.lee@gmail.com" in text
        expected_order = _expected_poppler_headings(lang) if extractor == "poppler" else headings
        _assert_heading_order(text, expected_order, extractor)
        for keyword in TARGET_KEYWORDS[target]:
            assert keyword in text, f"{extractor}: missing target keyword {keyword!r}"

        labels = SECTION_LABELS[lang]
        skill_region = text.split(labels["skills"], 1)[1].split(labels["education"], 1)[0]
        category_labels = SKILL_CATEGORY_LABELS[lang][target]
        positions = [skill_region.index(label) for label in category_labels]
        if not (target == "ds-ml" and extractor == "poppler"):
            assert positions == sorted(positions), (
                f"{extractor}: wrong compact skills reading order: {positions}"
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


def test_all_variants_build_deterministically(built_pdf):
    lang, target, out, _, _, _ = built_pdf
    first = out.read_bytes()
    result = subprocess.run(
        [sys.executable, "-m", "pdf.build", "--lang", lang, "--target", target],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"repeat PDF build failed:\n{result.stderr}"
    assert out.read_bytes() == first, f"{lang}/{target} PDF bytes are not deterministic"


def _page_text(pdf: Path, page: int) -> list[str]:
    """Non-empty, stripped lines of a single PDF page via Poppler."""
    text = subprocess.run(
        ["pdftotext", "-f", str(page), "-l", str(page), "-layout", str(pdf), "-"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return [line.strip() for line in text.splitlines() if line.strip()]


def _bbox_lines(pdf: Path):
    """Return page dimensions and visual rows reconstructed from Poppler words."""
    html = subprocess.run(
        ["pdftotext", "-f", "1", "-l", "1", "-bbox-layout", str(pdf), "-"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    root = ET.fromstring(html)
    page = next(element for element in root.iter() if element.tag.endswith("page"))
    rows: list[list[tuple[str, tuple[float, ...]]]] = []
    words = []
    for word in (element for element in page.iter() if element.tag.endswith("word")):
        box = tuple(float(word.attrib[key]) for key in ("xMin", "yMin", "xMax", "yMax"))
        words.append((word.text or "", box))
    for word, box in sorted(words, key=lambda item: (item[1][1], item[1][0])):
        row = next(
            (candidate for candidate in rows if abs(candidate[0][1][1] - box[1]) < 0.2), None
        )
        if row is None:
            rows.append([(word, box)])
        else:
            row.append((word, box))
    lines = []
    for row in rows:
        row.sort(key=lambda item: item[1][0])
        boxes = [box for _, box in row]
        lines.append(
            (
                row,
                (
                    min(b[0] for b in boxes),
                    min(b[1] for b in boxes),
                    max(b[2] for b in boxes),
                    max(b[3] for b in boxes),
                ),
            )
        )
    return float(page.attrib["width"]), float(page.attrib["height"]), lines


def _assert_separate_complete_aligned_contact_rows(pdf: Path) -> None:
    page_width, page_height, lines = _bbox_lines(pdf)
    expected = [
        ["Email", "jinho.michael.lee@gmail.com"],
        ["Based", "Mannheim,", "GER"],
        ["Web", "jinholee.is-a.dev"],
        ["LinkedIn", "·", "GitHub"],
    ]
    contact = []
    for words in expected:
        matches = [
            (line_words, box)
            for line_words, box in lines
            if [word for word, _ in line_words] == words
        ]
        assert len(matches) == 1, f"contact row is wrapped, merged, clipped, or missing: {words}"
        contact.append(matches[0])

    boxes = [box for _, box in contact]
    assert all(0 <= x_min < x_max <= page_width for x_min, _, x_max, _ in boxes)
    assert all(0 <= y_min < y_max <= page_height for _, y_min, _, y_max in boxes)
    assert all(boxes[index][3] < boxes[index + 1][1] for index in range(len(boxes) - 1)), (
        f"contact rows overlap or are not vertically separated: {boxes}"
    )

    # The three labeled rows share one label rail and one value rail. This catches
    # visually ragged fallback layouts even when extraction still finds all words.
    labeled_rows = contact[:3]
    label_x = [row[0][1][0] for row, _ in labeled_rows]
    value_x = [row[1][1][0] for row, _ in labeled_rows]
    assert max(label_x) - min(label_x) < 0.2, label_x
    assert max(value_x) - min(value_x) < 0.2, value_x


def test_all_variants_have_separate_complete_aligned_contact_rows(built_pdf):
    """Contact fields stay readable instead of wrapping into adjacent grid cells."""
    _, _, pdf, _, _, _ = built_pdf
    _assert_separate_complete_aligned_contact_rows(pdf)


def test_all_variants_have_outline_and_navigation_links(built_pdf):
    lang, target, _, reader, poppler, _ = built_pdf
    headings = _expected_headings(lang, target)
    assert reader.metadata.title == "Jin-Ho Lee — CV"
    assert reader.metadata.author == "Jin-Ho Lee"
    outline = [title.strip() for title in _outline_titles(reader.outline)]

    for heading in headings:
        assert heading in outline, f"missing bookmark {heading!r}; got {outline}"

    external, internal, urls = _link_counts(reader)
    assert external >= 8, "expected contact, project, and publication web links"
    assert internal == 0, "the approved one-page design has no visible contents strip"
    assert "https://orcid.org/0009-0001-8784-1771" in urls
    assert any(url.startswith("https://scholar.google.com/citations?") for url in urls)
    prefix = "https://jinholee.is-a.dev/de" if lang == "de" else "https://jinholee.is-a.dev"
    assert f"{prefix}/#publications" in urls
    if target == "comp-bio":
        assert {f"{prefix}/projects/{pid}/" for pid in ("L5", "L2", "L1")} <= urls
    assert "ORCID" in poppler and "Google Scholar" in poppler


def test_all_variants_embed_ibm_plex_sans(built_pdf):
    _, _, _, reader, _, _ = built_pdf
    fonts = reader.pages[0]["/Resources"]["/Font"].get_object()
    base_fonts = {str(reference.get_object().get("/BaseFont", "")) for reference in fonts.values()}
    assert base_fonts
    assert all("IBMPlexSans" in name for name in base_fonts), base_fonts


def test_main_evidence_uses_readable_type(built_pdf):
    lang, _, _, reader, _, _ = built_pdf
    anchor = "Cloud Migration:" if lang == "en" else "Cloud-Migration:"
    sizes: list[float] = []

    def collect(text, _cm, _tm, _font, font_size):
        if anchor in text:
            sizes.append(float(font_size))

    reader.pages[0].extract_text(visitor_text=collect)
    assert sizes, f"main evidence anchor {anchor!r} was not extractable"
    assert min(sizes) >= 8.5, f"main evidence fell below the 8.5pt readability floor: {sizes}"


def _image_xobjects(resources) -> list[str]:
    images: list[str] = []
    for name, reference in resources.get("/XObject", {}).items():
        xobject = reference.get_object()
        if xobject.get("/Subtype") == "/Image":
            images.append(str(name))
        nested = xobject.get("/Resources")
        if nested is not None:
            images.extend(_image_xobjects(nested.get_object()))
    return images


def test_stock_variants_are_photo_free(built_pdf):
    _, _, _, reader, _, _ = built_pdf
    images = _image_xobjects(reader.pages[0]["/Resources"].get_object())
    assert images == [], f"stock CV unexpectedly embeds raster image(s): {images}"


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
def test_tailored_export_stays_one_page_and_keeps_extra_evidence(lang: str, tmp_path: Path):
    """Tailored wording remains visible without breaking the one-page contract."""
    apps = tmp_path / "applications"
    _write_tailored_package(apps, "daina-2026", lang)

    manifest = export_application_cv("daina-2026", apps_dir=apps)
    assert manifest["cv"]["variant"] == "comp-bio"
    assert manifest["cv"]["tailoring"]["applied"], "tailoring must be applied"
    pdf = apps / "daina-2026" / manifest["cv"]["pdf_path"]

    labels = SECTION_LABELS[lang]
    page1 = "\n".join(_page_text(pdf, 1))

    assert len(PdfReader(pdf).pages) == 1
    _assert_separate_complete_aligned_contact_rows(pdf)
    assert labels["experience"] in page1
    assert labels["projects"] in page1
    assert "Splice" in page1 and "HLA" in page1
    assert "DAAD" in page1, "appended bullet must remain visible"
