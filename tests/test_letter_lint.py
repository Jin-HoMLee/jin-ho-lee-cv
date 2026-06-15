"""Tests for the advisory cover-letter cliché / AI-tell linter."""

from __future__ import annotations

from scripts.letter_lint import lint_body, lint_length


def test_flags_llm_signature_vocab():
    out = lint_body("We will leverage robust synergy to delve into this.", "en")
    joined = " ".join(out).lower()
    assert "leverage" in joined
    assert "robust" in joined
    assert "delve" in joined


def test_flags_opener_phrase():
    out = lint_body("I am writing to apply for the role at your company.", "en")
    assert any("writing to apply" in f for f in out)


def test_flags_closer_phrase():
    out = lint_body("Thank you for your consideration.", "en")
    assert any("consideration" in f for f in out)


def test_clean_text_yields_no_findings():
    text = "I rebuilt the variant-calling pipeline after it kept dropping reads."
    assert lint_body(text, "en") == []


def test_matching_is_case_insensitive():
    out = lint_body("PASSIONATE about the work.", "en")
    assert any("passionate" in f for f in out)


def test_de_terms_checked_only_in_german():
    assert lint_body("Ich bin hochmotiviert und teamfähig.", "de")
    # The German-only terms are not flagged for an English letter.
    assert lint_body("Ich bin hochmotiviert und teamfähig.", "en") == []


def test_en_terms_checked_in_german_too():
    # English loanwords creep into German corporate prose, so EN terms apply everywhere.
    out = lint_body("Wir leverage robuste Loesungen.", "de")
    assert any("leverage" in f for f in out)


def test_never_raises_on_empty_or_none():
    assert lint_body("", "en") == []
    assert lint_body(None, "en") == []


def test_unknown_lang_falls_back_to_english():
    out = lint_body("We leverage robust solutions.", "fr")
    assert any("leverage" in f for f in out)


def test_each_term_reported_at_most_once():
    out = lint_body("leverage leverage leverage robust", "en")
    leverage_hits = [f for f in out if "leverage" in f]
    assert len(leverage_hits) == 1


# --- lint_length: advisory long-letter warning (issue #79) -------------------


def test_length_under_threshold_yields_no_finding():
    body = " ".join(["word"] * 300)
    assert lint_length(body) == []


def test_length_at_threshold_yields_no_finding():
    # Threshold is strict-greater: exactly 400 words is still clean.
    body = " ".join(["word"] * 400)
    assert lint_length(body) == []


def test_length_over_threshold_yields_one_finding_with_count():
    body = " ".join(["word"] * 450)
    out = lint_length(body)
    assert len(out) == 1
    assert "450" in out[0]


def test_length_ignores_bold_and_bullet_markup():
    # 401 plain words would warn, but markup tokens must not be what pushes it over.
    # Build exactly 350 real words wrapped in bold + a leading bullet marker.
    words = " ".join([f"**word{i}**" for i in range(350)])
    body = f"- {words}"
    assert lint_length(body) == []


def test_length_never_raises_on_empty_or_none():
    assert lint_length("") == []
    assert lint_length(None) == []
