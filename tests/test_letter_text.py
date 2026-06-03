"""Behavioral (non-snapshot) tests for the cover-letter text serializer."""

from __future__ import annotations

import pytest

from scripts import letter_text

_SENDER = {"name": "Jin-Ho Lee", "email": "x@example.com", "location_line": "Mannheim, Germany"}


def _letter(**overrides):
    base = {
        "lang": "en",
        "date_display": "June 3, 2026",
        "recipient": None,
        "subject": "Application",
        "salutation": "Dear Hiring Manager,",
        "closing": "Sincerely,",
        "signer_name": "Jin-Ho Lee",
        "body_paragraphs": ["A paragraph."],
    }
    base.update(overrides)
    return base


def test_render_rejects_unknown_flavor():
    with pytest.raises(ValueError):
        letter_text.render(_letter(), _SENDER, "markdown")


@pytest.mark.parametrize("flavor", ["full", "body"])
def test_empty_body_has_no_double_blank(flavor):
    out = letter_text.render(_letter(body_paragraphs=[]), _SENDER, flavor)
    assert "\n\n\n" not in out  # no triple newline == no double blank line
    assert "Dear Hiring Manager,\n\nSincerely," in out
