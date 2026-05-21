"""Resolve {en: ..., de: ...} langstring maps to the selected language."""

from __future__ import annotations

from typing import Any

LANG_CODE_LEN = 2


def _is_langmap(d: dict) -> bool:
    """A dict is a langmap iff all keys are 2-letter lowercase strings."""
    if not d:
        return False
    return all(
        isinstance(k, str) and len(k) == LANG_CODE_LEN and k.islower() and k.isalpha() for k in d
    )


def resolve_langstrings(tree: Any, lang: str) -> Any:
    """Recursively walk `tree`, replacing every langmap with its `lang` value.

    A langmap is a dict whose keys are ALL 2-letter lowercase language codes.
    Mixed dicts (e.g. {en: "x", refs: [...]}) are NOT langmaps — recurse into them.

    Falls back to `en` if `lang` is missing. Raises ValueError if neither is present.
    """
    if isinstance(tree, dict):
        if _is_langmap(tree):
            if lang in tree:
                return tree[lang]
            if "en" in tree:
                return tree["en"]
            raise ValueError(
                f"no language '{lang}' or fallback 'en' in langmap: keys={sorted(tree)}"
            )
        return {k: resolve_langstrings(v, lang) for k, v in tree.items()}
    if isinstance(tree, list):
        return [resolve_langstrings(item, lang) for item in tree]
    return tree
