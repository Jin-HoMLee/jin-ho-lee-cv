"""Tests for pdf.build data-prep pipeline (no Typst invocation)."""
import json

import pytest

from pdf.build import prepare_data


def test_prepare_data_returns_resolved_content(content_dir):
    result = prepare_data(content_dir, private_path=None, lang="en")
    # Top-level keys mirror content_loader output
    for key in ("personal", "profile", "skills", "education",
                "experience", "projects", "languages", "volunteer", "publications"):
        assert key in result

    # Headline langmap was resolved
    assert result["personal"]["headline"] == "Cancer Immunogenomics | Bioinformatics"

    # Experience role langmap was resolved
    assert isinstance(result["experience"][0]["role"], str)


def test_prepare_data_includes_phone_when_private_provided(content_dir, tmp_path):
    private = tmp_path / "private.yaml"
    private.write_text(
        'phone: "+49 000 0000000"\n'
        'address:\n'
        '  street: "Teststr. 1"\n'
        '  postal_code: "00000"\n'
        '  city: "Testville"\n'
        '  country: "ZZ"\n'
    )
    result = prepare_data(content_dir, private_path=private, lang="en")
    assert result["personal"]["phone"] == "+49 000 0000000"
    assert result["personal"]["address"]["city"] == "Testville"


def test_prepare_data_omits_phone_when_private_absent(content_dir):
    result = prepare_data(content_dir, private_path=None, lang="en")
    assert "phone" not in result["personal"]
    assert "address" not in result["personal"]


def test_prepare_data_bullets_keep_refs(content_dir):
    result = prepare_data(content_dir, private_path=None, lang="en")
    # Find any bullet with refs and assert refs survived resolution
    for entry in result["experience"]:
        for bullet in entry["bullets"]:
            if isinstance(bullet, dict) and "refs" in bullet:
                assert isinstance(bullet["refs"], list)
                return
    pytest.fail("expected at least one bullet with refs in experience.yaml")


def test_prepare_data_json_serializable(content_dir):
    """The dict must be JSON-encodable for Typst to read it."""
    result = prepare_data(content_dir, private_path=None, lang="en")
    encoded = json.dumps(result, ensure_ascii=False)
    assert len(encoded) > 100
    # Round-trip
    decoded = json.loads(encoded)
    assert decoded["personal"]["name"]["given"] == "Jin-Ho"
