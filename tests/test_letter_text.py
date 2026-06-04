"""Behavioral (non-snapshot) tests for the cover-letter text serializer."""

from __future__ import annotations

import pytest

from scripts import letter_text

_SENDER = {"name": "Jin-Ho Lee", "email": "x@example.com", "location_line": "Mannheim, Germany"}


def _para(*spans):
    """A paragraph block from (text, bold) pairs."""
    return {"type": "paragraph", "spans": [{"text": t, "bold": b} for t, b in spans]}


def _letter(**overrides):
    base = {
        "lang": "en",
        "date_display": "June 3, 2026",
        "recipient": None,
        "subject": "Application",
        "salutation": "Dear Hiring Manager,",
        "closing": "Sincerely,",
        "signer_name": "Jin-Ho Lee",
        "body_blocks": [_para(("A paragraph.", False))],
    }
    base.update(overrides)
    return base


def test_render_rejects_unknown_flavor():
    with pytest.raises(ValueError):
        letter_text.render(_letter(), _SENDER, "markdown")


@pytest.mark.parametrize("flavor", ["full", "body"])
def test_empty_body_has_no_double_blank(flavor):
    out = letter_text.render(_letter(body_blocks=[]), _SENDER, flavor)
    assert "\n\n\n" not in out  # no triple newline == no double blank line
    assert "Dear Hiring Manager,\n\nSincerely," in out


def test_plain_paragraph_renders_unchanged():
    out = letter_text.render(_letter(), _SENDER, "body")
    assert "A paragraph." in out


def test_bold_spans_are_stripped_to_plain_text():
    letter = _letter(
        body_blocks=[_para(("I led the ", False), ("pipeline", True), (" work.", False))]
    )
    out = letter_text.render(letter, _SENDER, "body")
    assert "**" not in out
    assert "I led the pipeline work." in out


def test_bullet_list_renders_as_dot_items():
    letter = _letter(
        body_blocks=[
            {
                "type": "bullet_list",
                "items": [
                    [{"text": "first", "bold": False}],
                    [{"text": "second", "bold": False}],
                ],
            }
        ]
    )
    out = letter_text.render(letter, _SENDER, "body")
    assert "• first" in out
    assert "• second" in out


def test_bullet_item_bold_is_stripped():
    letter = _letter(
        body_blocks=[
            {
                "type": "bullet_list",
                "items": [[{"text": "key", "bold": True}, {"text": ": value", "bold": False}]],
            }
        ]
    )
    out = letter_text.render(letter, _SENDER, "body")
    assert "• key: value" in out
    assert "**" not in out
