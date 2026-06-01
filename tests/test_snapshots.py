"""Byte-faithful golden snapshots of every shipped renderer artifact.

Each test invokes the renderer's real write path (or render() string) and snapshots
the exact bytes, so a silent shape/byte change in resume.json / person.jsonld /
cv-*.txt / content.*.json fails CI. Regenerate intentionally with `just snapshots-update`.
"""
from __future__ import annotations

import pytest
from syrupy.extensions.single_file import SingleFileSnapshotExtension, WriteMode

from scripts import render_jsonld, render_jsonresume, render_llms, render_web_data
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
