"""Tests for the cover-letter core (paths, profile/application storage, validation, render)."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts import cover_letter_core as clc

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def apps(tmp_path: Path) -> Path:
    """An empty, writable applications/ dir."""
    d = tmp_path / "applications"
    d.mkdir()
    return d


@pytest.mark.parametrize(
    "bad",
    [
        "/etc/passwd",
        "../content/personal.yaml",
        "../../secret.yaml",
        "slug/../../escape.yaml",
        ".hidden/application.yaml",
        "slug/evil.exe",
    ],
)
def test_safe_path_rejects(apps, bad):
    with pytest.raises(ValueError):
        clc._safe_application_path(bad, apps_dir=apps)


def test_safe_path_accepts_dir_and_file(apps):
    assert (
        clc._safe_application_path("acme-bio-2026-06", apps_dir=apps)
        == (apps / "acme-bio-2026-06").resolve()
    )
    assert (
        clc._safe_application_path("acme-bio-2026-06/draft.md", apps_dir=apps)
        == (apps / "acme-bio-2026-06" / "draft.md").resolve()
    )


def test_safe_path_rejects_symlink_escape(apps):
    (apps / "leak").symlink_to(REPO_ROOT / "content")
    with pytest.raises(ValueError):
        clc._safe_application_path("leak/personal.yaml", apps_dir=apps)


def test_sanitize_slug():
    assert clc._sanitize_slug("Acme Genomics / Bioinformatician 2026-06") == (
        "acme-genomics-bioinformatician-2026-06"
    )
    with pytest.raises(ValueError):
        clc._sanitize_slug("///")


def test_profile_roundtrip(apps):
    assert clc.read_profile(apps_dir=apps) == {}
    data = {"motivation": {"en": "x"}, "availability": "now"}
    clc.write_profile(data, apps_dir=apps)
    assert clc.read_profile(apps_dir=apps) == data


def test_write_profile_rejects_invalid(apps):
    with pytest.raises(ValueError):
        clc.write_profile({"motivation": {"de": "only-de-no-en"}}, apps_dir=apps)


def test_create_and_read_application(apps):
    slug = clc.create_application(
        "Acme Bio 2026-06",
        job_text="# Job\nDo bioinformatics.\n",
        meta={
            "company": "Acme",
            "role": "Bioinformatician",
            "language": "de",
            "date": "2026-06-03",
            "subject": "Bewerbung",
            "status": "draft",
        },
        apps_dir=apps,
    )
    assert slug == "acme-bio-2026-06"
    bundle = clc.read_application(slug, apps_dir=apps)
    assert bundle["application"]["company"] == "Acme"
    assert "bioinformatics" in bundle["job"]
    assert bundle["interview"] is None
    assert bundle["draft"] is None


def test_create_application_refuses_collision(apps):
    meta = {
        "company": "Acme",
        "role": "Bioinformatician",
        "language": "de",
        "date": "2026-06-03",
        "subject": "Bewerbung",
        "status": "draft",
    }
    clc.create_application("acme-bio-2026-06", job_text="x", meta=meta, apps_dir=apps)
    with pytest.raises(FileExistsError):
        clc.create_application("acme-bio-2026-06", job_text="y", meta=meta, apps_dir=apps)


def test_list_applications_sorted(apps):
    for s in ("b-role-2026-06", "a-role-2026-06"):
        clc.create_application(
            s,
            job_text="x",
            meta={
                "company": "C",
                "role": "R",
                "language": "en",
                "date": "2026-06-03",
                "subject": "S",
                "status": "draft",
            },
            apps_dir=apps,
        )
    assert clc.list_applications(apps_dir=apps) == ["a-role-2026-06", "b-role-2026-06"]


def test_core_never_writes_under_content(apps):
    """All write helpers route through _safe_application_path; content/ is untouchable."""
    with pytest.raises(ValueError):
        clc._atomic_write("../content/personal.yaml", "boom", apps_dir=apps)


def _make_app(apps: Path, slug: str = "acme-bio-2026-06", **overrides) -> str:
    meta = {
        "company": "Acme",
        "role": "Bioinformatician",
        "language": "de",
        "date": "2026-06-03",
        "subject": "Bewerbung",
        "status": "draft",
    }
    meta.update(overrides)
    return clc.create_application(slug, job_text="x", meta=meta, apps_dir=apps)


def test_save_interview_and_draft(apps):
    slug = _make_app(apps)
    clc.save_interview(
        slug,
        {
            "why_company": "fit",
            "emphasis": ["L1"],
            "gaps": [{"requirement": "Rust", "decision": "transferable", "note": "C work"}],
        },
        apps_dir=apps,
    )
    clc.save_draft(slug, "para one\n\npara two\n", apps_dir=apps)
    bundle = clc.read_application(slug, apps_dir=apps)
    assert bundle["interview"]["why_company"] == "fit"
    assert bundle["draft"].startswith("para one")


def test_save_interview_rejects_bad_decision(apps):
    slug = _make_app(apps)
    with pytest.raises(ValueError):
        clc.save_interview(slug, {"gaps": [{"requirement": "x", "decision": "lie"}]}, apps_dir=apps)


def test_cv_facts_is_pii_safe():
    facts = clc.cv_facts(lang="en")
    assert "personal" in facts
    blob = repr(facts)
    # Address/phone live only in content.private/ and must never surface here.
    assert "phone" not in facts["personal"]
    assert "address" not in facts["personal"]
    assert "Musterstraße" not in blob


def test_validate_application_clean(apps):
    slug = _make_app(apps)
    clc.save_draft(slug, "body\n", apps_dir=apps)
    res = clc.validate_application(slug, apps_dir=apps)
    assert res["valid"] is True
    assert res["errors"] == []


def test_validate_application_missing_required_field(apps):
    slug = _make_app(apps)
    # Corrupt application.yaml: drop the required 'subject'.
    data = clc.read_application(slug, apps_dir=apps)["application"]
    del data["subject"]
    clc._write_yaml(f"{slug}/application.yaml", data, apps_dir=apps)
    res = clc.validate_application(slug, apps_dir=apps)
    assert res["valid"] is False
    assert any("subject" in e for e in res["errors"])


def test_validate_application_bad_language(apps):
    slug = _make_app(apps, language="fr")
    res = clc.validate_application(slug, apps_dir=apps)
    assert res["valid"] is False


def test_validate_application_implausible_date_warns(apps):
    slug = _make_app(apps, date="2026-02-30")  # passes regex, not a real calendar day
    clc.save_draft(slug, "body\n", apps_dir=apps)
    res = clc.validate_application(slug, apps_dir=apps)
    assert any("date" in w for w in res["warnings"])


def test_validate_application_missing_draft_warns(apps):
    slug = _make_app(apps)
    res = clc.validate_application(slug, apps_dir=apps)
    assert any("draft" in w for w in res["warnings"])


def test_validate_application_bad_gap_in_interview(apps):
    slug = _make_app(apps)
    clc.save_draft(slug, "body\n", apps_dir=apps)
    # Write interview.yaml directly with a bad gap decision, bypassing save_interview's guard.
    clc._write_yaml(
        f"{slug}/interview.yaml",
        {"gaps": [{"requirement": "x", "decision": "lie"}]},
        apps_dir=apps,
    )
    res = clc.validate_application(slug, apps_dir=apps)
    assert res["valid"] is False
    assert any("gap" in e for e in res["errors"])


def test_format_date():
    assert clc._format_date("2026-06-03", "en") == "June 3, 2026"
    assert clc._format_date("2026-06-03", "de") == "3. Juni 2026"
    assert clc._format_date("not-a-date", "en") == "not-a-date"  # graceful


def test_format_date_accepts_date_object():
    from datetime import date

    assert clc._format_date(date(2026, 6, 3), "en") == "June 3, 2026"
    assert clc._format_date(date(2026, 6, 3), "de") == "3. Juni 2026"


def test_salutation_and_closing():
    assert clc._salutation("de", "Dr. Mustermann") == "Sehr geehrte/r Dr. Mustermann,"
    assert clc._salutation("de", None) == "Sehr geehrte Damen und Herren,"
    assert clc._salutation("en", "Dr. Lee") == "Dear Dr. Lee,"
    assert clc._salutation("en", None) == "Dear Hiring Manager,"
    assert clc._closing("de") == "Mit freundlichen Grüßen"
    assert clc._closing("en") == "Sincerely,"


def test_render_letter_text_writes_both_flavors(apps):
    slug = _make_app(apps, language="en", subject="Application: Bioinformatician")
    clc.save_draft(slug, "First paragraph.\n\nSecond paragraph.\n", apps_dir=apps)
    res = clc.render_letter(slug, fmt="text", apps_dir=apps)
    assert res["ok"] is True
    assert "cover-letter-en.txt" in res["rendered"]
    assert "cover-letter-en-body.txt" in res["rendered"]
    full = (apps / slug / "cover-letter-en.txt").read_text(encoding="utf-8")
    body = (apps / slug / "cover-letter-en-body.txt").read_text(encoding="utf-8")
    assert "Jin-Ho Lee" in full  # sender block in full
    assert "First paragraph." in body
    assert "Jin-Ho Lee" in body  # signer line in body
    assert "Dear Hiring Manager," in body  # no recipient name -> generic salutation


def test_render_letter_refuses_invalid(apps):
    slug = _make_app(apps, language="fr")  # invalid language fails schema
    res = clc.render_letter(slug, fmt="text", apps_dir=apps)
    assert res["ok"] is False
    assert res["errors"]
    assert res["rendered"] == []


def test_render_letter_skips_pdf_without_typst(apps, monkeypatch):
    monkeypatch.setattr(clc.shutil, "which", lambda tool: None)
    slug = _make_app(apps, language="en")
    clc.save_draft(slug, "Body.\n", apps_dir=apps)
    res = clc.render_letter(slug, fmt="all", apps_dir=apps)
    assert res["ok"] is True
    assert "cover-letter-en.pdf" in res["skipped"]
    assert "cover-letter-en.txt" in res["rendered"]


def test_render_letter_rejects_bad_fmt(apps):
    slug = _make_app(apps, language="en")
    clc.save_draft(slug, "Body.\n", apps_dir=apps)
    with pytest.raises(ValueError):
        clc.render_letter(slug, fmt="docx", apps_dir=apps)


# --- body markup parsing (issue #69) -------------------------------------------


def test_parse_spans_plain_text_single_span():
    assert clc._parse_spans("just text") == [{"text": "just text", "bold": False}]


def test_parse_spans_bold_in_middle():
    assert clc._parse_spans("a **b** c") == [
        {"text": "a ", "bold": False},
        {"text": "b", "bold": True},
        {"text": " c", "bold": False},
    ]


def test_parse_spans_leading_and_trailing_bold_have_no_empty_span():
    assert clc._parse_spans("**x** mid **y**") == [
        {"text": "x", "bold": True},
        {"text": " mid ", "bold": False},
        {"text": "y", "bold": True},
    ]


def test_parse_spans_unmatched_marker_is_literal():
    assert clc._parse_spans("a ** b") == [{"text": "a ** b", "bold": False}]


def test_parse_block_paragraph_with_bold():
    assert clc._parse_block("Hello **world**.") == {
        "type": "paragraph",
        "spans": [
            {"text": "Hello ", "bold": False},
            {"text": "world", "bold": True},
            {"text": ".", "bold": False},
        ],
    }


def test_parse_block_bullet_list_dash():
    blk = clc._parse_block("- one\n- two")
    assert blk["type"] == "bullet_list"
    assert blk["items"] == [
        [{"text": "one", "bold": False}],
        [{"text": "two", "bold": False}],
    ]


def test_parse_block_bullet_list_star_marker():
    blk = clc._parse_block("* a\n* b")
    assert blk["type"] == "bullet_list"
    assert [item[0]["text"] for item in blk["items"]] == ["a", "b"]


def test_parse_block_mixed_lines_is_paragraph_not_list():
    assert clc._parse_block("- one\nplain line")["type"] == "paragraph"


def test_parse_block_bullet_item_keeps_inline_bold():
    blk = clc._parse_block("- **key**: detail")
    assert blk["items"][0] == [
        {"text": "key", "bold": True},
        {"text": ": detail", "bold": False},
    ]


def test_parse_body_mixed_blocks_in_order():
    draft = "Intro paragraph.\n\n- first\n- second\n\nOutro **bold**."
    assert [b["type"] for b in clc._parse_body(draft)] == [
        "paragraph",
        "bullet_list",
        "paragraph",
    ]


def test_parse_body_empty_is_empty_list():
    assert clc._parse_body(None) == []
    assert clc._parse_body("   ") == []


def test_assemble_letter_emits_body_blocks_not_paragraphs():
    app = {"date": "2026-06-03", "subject": "S", "recipient": None}
    letter = clc._assemble_letter(app, "Plain para.", "en")
    assert "body_paragraphs" not in letter
    assert letter["body_blocks"][0]["type"] == "paragraph"
    assert letter["body_blocks"][0]["spans"] == [{"text": "Plain para.", "bold": False}]


def test_validate_application_accepts_unquoted_date(apps):
    """An unquoted YAML date (parsed as datetime.date) must validate, not be rejected."""
    from datetime import date

    slug = _make_app(apps)
    data = clc.read_application(slug, apps_dir=apps)["application"]
    data["date"] = date(2026, 6, 3)  # ruamel dumps unquoted -> reloads as datetime.date
    clc._write_yaml(f"{slug}/application.yaml", data, apps_dir=apps)
    clc.save_draft(slug, "body\n", apps_dir=apps)
    res = clc.validate_application(slug, apps_dir=apps)
    assert res["valid"] is True, res["errors"]


def test_render_letter_warns_on_cliche(apps, capsys):
    slug = _make_app(apps, language="en")
    clc.save_draft(slug, "I am passionate about leveraging robust solutions.\n", apps_dir=apps)
    res = clc.render_letter(slug, fmt="text", apps_dir=apps)
    assert res["ok"] is True  # advisory: never blocks rendering
    err = capsys.readouterr().err
    assert "WARN" in err
    assert "passionate" in err


def test_render_letter_clean_draft_emits_no_warn(apps, capsys):
    slug = _make_app(apps, language="en")
    clc.save_draft(
        slug,
        "I rebuilt the variant-calling pipeline after it kept dropping reads.\n",
        apps_dir=apps,
    )
    clc.render_letter(slug, fmt="text", apps_dir=apps)
    assert "WARN" not in capsys.readouterr().err
