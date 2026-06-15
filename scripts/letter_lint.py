"""Advisory cover-letter cliché / AI-tell linter.

Pure and deterministic. NEVER raises and NEVER blocks. Holds the canonical machine
blocklist (EN-primary + a small DE set). render_letter() calls lint_body() after
assembly and prints each finding as `WARN: ...` to stderr, exactly like validate.py's
date_warnings. False positives on legitimate domain words ("robust", "landscape") are
expected and cheap — this is a backstop, not a gate. reference.md holds the (overlapping,
not identical) human-facing list; THIS module is the one the code reads.
"""

from __future__ import annotations

import re

_BLOCKLIST_EN = [
    # openers
    "i am writing to apply",
    "i am writing to express my interest",
    "please accept this letter",
    "to whom it may concern",
    "dear sir or madam",
    # closers
    "thank you for your consideration",
    "i look forward to hearing from you",
    "please do not hesitate to contact me",
    # hollow fit / confidence claims
    "great fit",
    "excellent fit",
    "perfect candidate",
    "uniquely qualified",
    "i am confident that",
    "valuable asset",
    # empty résumé adjectives
    "results-driven",
    "results-oriented",
    "detail-oriented",
    "proactive",
    "self-starter",
    "go-getter",
    "team player",
    "people person",
    "passionate",
    "proven track record",
    "well-rounded",
    "hit the ground running",
    "fast-paced environment",
    "think outside the box",
    "wheelhouse",
    # LLM-signature vocabulary
    "delve",
    "leverage",
    "utilize",
    "foster",
    "robust",
    "seamless",
    "pivotal",
    "tapestry",
    "landscape",
    "realm",
    "beacon",
    "testament",
    "underscore",
    "showcase",
    "intricate",
    "multifaceted",
    "transformative",
    "cutting-edge",
    "ever-evolving",
    "synergy",
    "streamline",
    "harness",
    "embark",
    "bolster",
    "unlock potential",
    "elevate",
    "spearhead",
    # filler framing
    "in today's fast-paced world",
    "in the realm of",
    "it is important to note",
    "needless to say",
    "at the end of the day",
    "that being said",
    # sentence molds that survive word-banning — rhetorical molds with an
    # elevated false-positive rate; acceptable because output is advisory only
    "not just",
    "not only",
    "serves as",
    "stands as",
]

_BLOCKLIST_DE = [
    "hochmotiviert",
    "teamfähig",
    "teamplayer",
    "dynamisch",
    "proaktiv",
    "leidenschaftlich",
    "ganzheitlich",
    "nahtlos",
    "reibungslos",
    "mehrwert",
    "zielorientiert",
    "lösungsorientiert",
    "belastbar",
    "kommunikationsstark",
]


def _compile(terms: list[str]) -> list[tuple[str, re.Pattern[str]]]:
    return [(t, re.compile(r"\b" + re.escape(t) + r"\b", re.IGNORECASE)) for t in terms]


# EN terms apply in every language (loanwords); DE terms are added for German letters.
_PATTERNS = {
    "en": _compile(_BLOCKLIST_EN),
    "de": _compile(_BLOCKLIST_EN + _BLOCKLIST_DE),
}


# Advisory length backstop (issue #79). The craft guide aims ~300–350 words with a
# hard stop ~375; the linter warns only above 400 — a ~25-word grace band so a letter
# at target that creeps slightly over does not trip a warning.
_LENGTH_THRESHOLD = 400

# Drop bold markers (**…**) and a leading bullet marker (- / *) so the count reflects
# rendered words, not markup tokens.
_BOLD_MARKER = re.compile(r"\*\*")
_BULLET_MARKER = re.compile(r"^[ \t]*[-*]\s+", re.MULTILINE)


def _word_count(text: str | None) -> int:
    """Count rendered words in a draft body, ignoring bold + bullet markup."""
    if not text:
        return 0
    cleaned = _BULLET_MARKER.sub(" ", _BOLD_MARKER.sub("", text))
    return len(cleaned.split())


def lint_length(text: str | None, threshold: int = _LENGTH_THRESHOLD) -> list[str]:
    """Return an advisory finding when the body runs long (> threshold words).

    Never raises. Markup (bold + bullets) is stripped before counting. Returns at
    most one finding; an empty/None body or one at/under the threshold yields [].
    """
    n = _word_count(text)
    if n <= threshold:
        return []
    return [
        f"letter body runs long: {n} words "
        "(aim ~300–350, hard stop ~375); cut the weakest 1–2 ideas, not words"
    ]


def lint_body(text: str | None, lang: str = "en") -> list[str]:
    """Return advisory findings (human-readable strings) for clichés / AI-tells.

    Never raises. Unknown languages fall back to the English blocklist. Each matched
    term is reported at most once, in blocklist order.
    """
    patterns = _PATTERNS.get(lang, _PATTERNS["en"])
    findings: list[str] = []
    for term, rx in patterns:
        if rx.search(text or ""):
            findings.append(f"possible AI-tell/cliché: {term!r}")
    return findings
