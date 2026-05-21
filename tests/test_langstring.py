"""Tests for scripts.langstring.resolve_langstrings."""

import pytest

from scripts.langstring import resolve_langstrings


def test_resolves_simple_langmap():
    assert resolve_langstrings({"en": "x", "de": "y"}, lang="en") == "x"
    assert resolve_langstrings({"en": "x", "de": "y"}, lang="de") == "y"


def test_passes_through_non_langmap_dicts():
    data = {"name": "Cintellic", "url": None}
    assert resolve_langstrings(data, lang="en") == {"name": "Cintellic", "url": None}


def test_recurses_into_lists():
    data = [{"en": "a"}, {"en": "b"}]
    assert resolve_langstrings(data, lang="en") == ["a", "b"]


def test_recurses_into_nested_dicts():
    data = {"role": {"en": "Consultant"}, "period": {"start": "2024-05"}}
    result = resolve_langstrings(data, lang="en")
    assert result == {"role": "Consultant", "period": {"start": "2024-05"}}


def test_falls_back_to_en_when_target_missing():
    # de is requested but only en is present
    assert resolve_langstrings({"en": "x"}, lang="de") == "x"


def test_raises_when_neither_target_nor_en_present():
    with pytest.raises(ValueError, match="language"):
        resolve_langstrings({"fr": "x"}, lang="en")


def test_passes_through_scalars():
    assert resolve_langstrings("hello", lang="en") == "hello"
    assert resolve_langstrings(42, lang="en") == 42
    assert resolve_langstrings(None, lang="en") is None
    assert resolve_langstrings(True, lang="en") is True


def test_handles_realistic_content_loader_output():
    # An experience bullet has BOTH `en` and non-language key `refs`, so it is
    # NOT a pure langmap — the resolver should recurse into it.
    data = {
        "personal": {"name": {"given": "Jin-Ho", "family": "Lee"}, "headline": {"en": "Bio | DS"}},
        "experience": [
            {"role": {"en": "Consultant"}, "bullets": [{"en": "Did things", "refs": ["L1"]}]}
        ],
    }
    result = resolve_langstrings(data, lang="en")
    assert result["personal"]["headline"] == "Bio | DS"
    assert result["personal"]["name"] == {"given": "Jin-Ho", "family": "Lee"}
    assert result["experience"][0]["role"] == "Consultant"
    # bullet is a mixed dict (has `refs`), so the resolver recurses but does
    # NOT pluck out the `en` value; the dict survives as-is.
    assert result["experience"][0]["bullets"][0] == {"en": "Did things", "refs": ["L1"]}
