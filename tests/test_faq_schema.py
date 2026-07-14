"""FAQ content must be schema-valid and fully bilingual (Phase 14, issue #113)."""

from __future__ import annotations

from pathlib import Path

from scripts.validate import validate_faq


REPO_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = REPO_ROOT / "content"
FAQ_SCHEMA = REPO_ROOT / "schema" / "faq.schema.json"
FIXTURES = Path(__file__).parent / "fixtures" / "invalid_yaml"


def test_real_faq_validates():
    assert validate_faq(CONTENT_DIR, FAQ_SCHEMA) == []


def test_real_faq_is_bilingual_and_nonempty():
    from ruamel.yaml import YAML

    data = YAML(typ="safe").load((CONTENT_DIR / "faq.yaml").read_text(encoding="utf-8"))
    faqs = data["faqs"]
    assert len(faqs) >= 5, "seed the FAQ with at least 5 curated entries"
    ids = [f["id"] for f in faqs]
    assert len(ids) == len(set(ids)), "FAQ ids must be unique"
    for entry in faqs:
        for field in ("question", "answer"):
            assert entry[field]["en"].strip(), f"{entry['id']}: empty en {field}"
            assert entry[field]["de"].strip(), f"{entry['id']}: empty de {field}"


def test_duplicate_id_fails(tmp_path):
    content = tmp_path / "content"
    content.mkdir()
    (content / "faq.yaml").write_text(
        (FIXTURES / "faq_duplicate_id.yaml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    errors = validate_faq(content, FAQ_SCHEMA)
    assert errors, "duplicate FAQ id must be reported"
    assert "duplicate" in str(errors[0]).lower()


def test_missing_de_fails(tmp_path):
    content = tmp_path / "content"
    content.mkdir()
    (content / "faq.yaml").write_text(
        (FIXTURES / "faq_missing_de.yaml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    errors = validate_faq(content, FAQ_SCHEMA)
    assert errors, "an en-only FAQ entry must be reported (de is required)"


def test_absent_faq_file_is_an_error(tmp_path):
    content = tmp_path / "content"
    content.mkdir()
    errors = validate_faq(content, FAQ_SCHEMA)
    assert errors, "faq.yaml is a required content file"


def test_availability_is_grounded_in_personal_yaml():
    """The is-he-available-for-work FAQ answer must trace to a real content/ fact.

    A prior version asserted an availability status with no underlying source
    in content/ - true today, but silently stale-able. `personal.availability`
    is now that source of truth; this test proves it exists (bilingual,
    non-empty) and that the FAQ answer built on top of it is non-empty too.
    """
    from ruamel.yaml import YAML

    yaml = YAML(typ="safe")
    personal = yaml.load((CONTENT_DIR / "personal.yaml").read_text(encoding="utf-8"))
    availability = personal.get("availability")
    assert availability is not None, "personal.yaml must carry an availability fact"
    assert availability["en"].strip(), "personal.availability.en must be non-empty"
    assert availability["de"].strip(), "personal.availability.de must be non-empty"

    faqs = yaml.load((CONTENT_DIR / "faq.yaml").read_text(encoding="utf-8"))["faqs"]
    entry = next(f for f in faqs if f["id"] == "is-he-available-for-work")
    assert entry["answer"]["en"].strip()
    assert entry["answer"]["de"].strip()
