"""Tests for the advisory cover-letter cliché / AI-tell linter."""

from __future__ import annotations

from scripts.letter_lint import lint_body


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
