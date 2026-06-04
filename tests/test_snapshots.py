"""Byte-faithful golden snapshots of every shipped renderer artifact.

Each test invokes the renderer's real write path (or render() string) and snapshots
the exact bytes, so a silent shape/byte change in resume.json / person.jsonld /
cv-*.txt / content.*.json fails CI. Regenerate intentionally with `just snapshots-update`.
"""

from __future__ import annotations

import pytest
from syrupy.extensions.single_file import SingleFileSnapshotExtension, WriteMode

from scripts import letter_text, render_jsonld, render_jsonresume, render_llms, render_web_data
from scripts.render_text import render as render_text


class _TextSnap(SingleFileSnapshotExtension):
    _write_mode = WriteMode.TEXT
    file_extension = "txt"


class _JsonSnap(SingleFileSnapshotExtension):
    _write_mode = WriteMode.TEXT
    file_extension = "json"


def test_resume_json(tmp_path, snapshot):
    out = tmp_path / "resume.json"
    render_jsonresume.main(["--output", str(out)])
    assert out.read_text(encoding="utf-8") == snapshot.use_extension(_JsonSnap)


def test_person_jsonld(tmp_path, snapshot):
    out = tmp_path / "person.jsonld"
    render_jsonld.main(["--output", str(out)])
    assert out.read_text(encoding="utf-8") == snapshot.use_extension(_JsonSnap)


def test_llms_txt(tmp_path, snapshot):
    out = tmp_path / "llms.txt"
    render_llms.main(["--output", str(out)])
    assert out.read_text(encoding="utf-8") == snapshot.use_extension(_TextSnap)


@pytest.mark.parametrize("lang", ["en", "de"])
@pytest.mark.parametrize("target", ["bridge", "comp-bio", "ds-ml"])
def test_text_snapshot(lang, target, snapshot):
    assert render_text(lang, target) == snapshot.use_extension(_TextSnap)


@pytest.fixture(scope="module")
def web_data_dir(tmp_path_factory):
    d = tmp_path_factory.mktemp("webdata")
    render_web_data.render_web_data(output_dir=d)
    return d


@pytest.mark.parametrize(
    "name",
    [
        "content.en.json",
        "content.de.json",
        "content.en.variants.json",
        "content.de.variants.json",
    ],
)
def test_web_data_snapshot(name, web_data_dir, snapshot):
    assert (web_data_dir / name).read_text(encoding="utf-8") == snapshot.use_extension(_JsonSnap)


_FIXTURE_LETTER = {
    "en": {
        "lang": "en",
        "date_display": "June 3, 2026",
        "recipient": {
            "name": "Dr. Erika Mustermann",
            "company": "Acme Genomics GmbH",
            "address": {"street": "Sample St 1", "postal_code": "68159", "city": "Mannheim"},
        },
        "subject": "Application: Bioinformatician",
        "salutation": "Dear Dr. Erika Mustermann,",
        "closing": "Sincerely,",
        "signer_name": "Jin-Ho Lee",
        "body_blocks": [
            {
                "type": "paragraph",
                "spans": [
                    {"text": "I am writing to apply for the Bioinformatician role.", "bold": False}
                ],
            },
            {
                "type": "paragraph",
                "spans": [
                    {"text": "My ", "bold": False},
                    {"text": "pipeline work", "bold": True},
                    {"text": " maps directly onto your reproducibility goals:", "bold": False},
                ],
            },
            {
                "type": "bullet_list",
                "items": [
                    [{"text": "reproducible Snakemake workflows", "bold": False}],
                    [{"text": "HLA typing and neoepitope prediction", "bold": False}],
                ],
            },
        ],
    },
    "de": {
        "lang": "de",
        "date_display": "3. Juni 2026",
        "recipient": None,
        "subject": "Bewerbung als Bioinformatician",
        "salutation": "Sehr geehrte Damen und Herren,",
        "closing": "Mit freundlichen Grüßen",
        "signer_name": "Jin-Ho Lee",
        "body_blocks": [
            {
                "type": "paragraph",
                "spans": [
                    {
                        "text": "mit großem Interesse habe ich Ihre Ausschreibung gelesen.",
                        "bold": False,
                    }
                ],
            },
            {
                "type": "paragraph",
                "spans": [
                    {"text": "Meine ", "bold": False},
                    {"text": "Pipeline-Arbeit", "bold": True},
                    {"text": " passt zu Ihren Reproduzierbarkeitszielen:", "bold": False},
                ],
            },
            {
                "type": "bullet_list",
                "items": [
                    [{"text": "reproduzierbare Snakemake-Workflows", "bold": False}],
                    [{"text": "HLA-Typisierung und Neoepitop-Vorhersage", "bold": False}],
                ],
            },
        ],
    },
}
_FIXTURE_SENDER = {
    "name": "Jin-Ho Lee",
    "email": "jinho.michael.lee@gmail.com",
    "location_line": "Mannheim, Germany",
}


@pytest.mark.parametrize("lang", ["en", "de"])
@pytest.mark.parametrize("flavor", ["full", "body"])
def test_letter_text_snapshot(lang, flavor, snapshot):
    out = letter_text.render(_FIXTURE_LETTER[lang], _FIXTURE_SENDER, flavor)
    assert out == snapshot.use_extension(_TextSnap)
