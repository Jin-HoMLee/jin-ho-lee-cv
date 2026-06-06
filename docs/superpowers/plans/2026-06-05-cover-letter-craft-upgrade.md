# Cover-letter Craft Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a personal, non-bland cover letter the floor the skill guarantees — by adding craft guidance to the skill prose and two deterministic, advisory Python tools (a JD↔CV keyword gap report and a cliché/AI-tell linter).

**Architecture:** Three cleanly-separated surfaces. (1) `reference.md` gains positive drafting principles + an AI-tells list + docs for two new fields. (2) `SKILL.md` wires a gap report into step 3, hook/voice/joy prompts into step 4, and voice-priming + "every paragraph" scope + a self-critique pass into step 5. (3) Python gains `jd_keyword_gap()` (surfaced by `just jd-gap <slug>`) and a new `scripts/letter_lint.py` (`lint_body`) called from `render_letter()` — both deterministic, both advisory, neither ever blocks. All changes preserve existing constraints: never fabricate, EN+DE, `applications/` stays gitignored, `content/` read-only, PII only in the gitignored PDF.

**Tech Stack:** Python 3 (stdlib `re`), pytest, jsonschema, ruamel.yaml, `just` recipes, Claude skill markdown. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-06-04-cover-letter-craft-upgrade-design.md` (read it first — Appendix A1/A2/A3 hold the paste-ready prose).

**Key facts the executor needs:**
- The cover-letter core is `scripts/cover_letter_core.py`; the text serializer is `scripts/letter_text.py`; the render CLI is `scripts/render_letter.py`.
- `cv_facts()` (in `cover_letter_core.py`) is the single PII-safe grounding source — a thin reuse of `agent_core.read_cv` (forces `private_path=None`). Never read `content.private/`.
- `render_letter(slug, *, fmt="all", apps_dir=APPS_DIR)` is the orchestrator. After it assembles `letter` and knows `lang`, that is where the linter call goes.
- `validate.py`'s `date_warnings` (printed as `print(f"WARN: {warn}", file=sys.stderr)`) is the exact pattern the linter mirrors: advisory, stderr, never fails.
- Tests live under `tests/`. The shared fixtures are in `tests/test_cover_letter_core.py`: the `apps` fixture (an empty writable `applications/` tmp dir) and the `_make_app(apps, slug=..., **overrides)` helper.
- Drift-guards live in `tests/test_cover_letter_skill_docs.py`. `test_skill_documents_profile_fields` already asserts every `profile.schema.json` property name appears in `reference.md` — so adding `joy` to the schema *forces* documenting it. `test_skill_recipes_exist` asserts every `just <recipe>` named in the skill docs exists in the `justfile`.
- Run a single test: `uv run pytest tests/test_X.py::test_name -v`. Whole suite: `just test`. Validate: `just validate`. Lint: `just lint`. Format check: `uv run ruff format --check .`.

**No-snapshot-churn invariant:** none of these changes alter rendered letter output (#1–#4 are prompt text; the gap report is a separate CLI; the linter only prints to stderr). Task 8 verifies `just snapshots-update` leaves the working tree clean — any movement is a bug to fix, not to accept.

---

### Task 1: Advisory cliché / AI-tell linter (`scripts/letter_lint.py`)

Pure, deterministic, self-contained. Holds the **canonical machine blocklist**. Never raises, never blocks.

**Files:**
- Create: `scripts/letter_lint.py`
- Test: `tests/test_letter_lint.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_letter_lint.py`:

```python
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
    assert lint_body("PASSIONATE about the work.", "en")


def test_de_terms_checked_only_in_german():
    assert lint_body("Ich bin hochmotiviert und teamfähig.", "de")
    # The German-only terms are not flagged for an English letter.
    assert lint_body("Ich bin hochmotiviert und teamfähig.", "en") == []


def test_en_terms_checked_in_german_too():
    # English loanwords creep into German corporate prose, so EN terms apply everywhere.
    assert lint_body("Wir leverage robuste Loesungen.", "de")


def test_never_raises_on_empty_or_none():
    assert lint_body("", "en") == []
    assert lint_body(None, "en") == []


def test_unknown_lang_falls_back_to_english():
    assert lint_body("We leverage robust solutions.", "fr")


def test_each_term_reported_at_most_once():
    out = lint_body("leverage leverage leverage robust", "en")
    leverage_hits = [f for f in out if "leverage" in f]
    assert len(leverage_hits) == 1
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_letter_lint.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.letter_lint'`.

- [ ] **Step 3: Write the implementation**

Create `scripts/letter_lint.py`:

```python
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
    # sentence molds that survive word-banning
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


def _compile(terms: list[str]) -> list[tuple[str, re.Pattern]]:
    return [(t, re.compile(r"\b" + re.escape(t) + r"\b", re.IGNORECASE)) for t in terms]


# EN terms apply in every language (loanwords); DE terms are added for German letters.
_PATTERNS = {
    "en": _compile(_BLOCKLIST_EN),
    "de": _compile(_BLOCKLIST_EN + _BLOCKLIST_DE),
}


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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_letter_lint.py -v`
Expected: PASS (all 10 tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/letter_lint.py tests/test_letter_lint.py
git commit -m "feat(cover-letter): advisory cliché / AI-tell linter (#74)"
```

---

### Task 2: Wire the linter into `render_letter`

`render_letter()` runs the linter on the draft body after assembly and prints each finding as `WARN: …` to stderr. Advisory only — the render result is unchanged.

**Files:**
- Modify: `scripts/cover_letter_core.py` (imports near line 23; `render_letter` body near lines 438–440)
- Test: `tests/test_cover_letter_core.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cover_letter_core.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_cover_letter_core.py::test_render_letter_warns_on_cliche -v`
Expected: FAIL — no `WARN` on stderr (assertion error on `"WARN" in err`).

- [ ] **Step 3: Add the import**

In `scripts/cover_letter_core.py`, add `import sys` to the stdlib import group (it currently imports `io, json, os, re, shutil, subprocess, tempfile` but not `sys`). Place it alphabetically:

```python
import shutil
import subprocess
import sys
import tempfile
```

And add `letter_lint` to the scripts import (currently `from scripts import agent_core, letter_text`):

```python
from scripts import agent_core, letter_lint, letter_text
```

- [ ] **Step 4: Call the linter in `render_letter`**

In `render_letter`, immediately after the line that assembles the letter:

```python
    letter = _assemble_letter(bundle["application"], bundle["draft"], lang)
```

insert:

```python
    for finding in letter_lint.lint_body(bundle["draft"] or "", lang):
        print(f"WARN: {finding}", file=sys.stderr)
```

(It sits before `sender = _public_sender(lang)` — order does not matter; it must run for every `fmt`.)

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_cover_letter_core.py -k "render_letter" -v`
Expected: PASS (the two new tests plus the existing `render_letter` tests stay green — their drafts contain no blocklisted terms).

- [ ] **Step 6: Commit**

```bash
git add scripts/cover_letter_core.py tests/test_cover_letter_core.py
git commit -m "feat(cover-letter): run the cliché linter in render_letter (advisory stderr WARN) (#74)"
```

---

### Task 3: Keyword-gap core (`_flatten_strings`, `_tokenize`, `_keyword_gap`)

The deterministic, fixture-testable heart of the honesty diff. Pure functions over a CV-facts dict and JD text. The contract is an **advisory checklist, not a verdict** — it deliberately over-surfaces.

**Files:**
- Modify: `scripts/cover_letter_core.py` (add a new section; suggested placement: after `cv_facts` near line 222)
- Test: `tests/test_cover_letter_core.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cover_letter_core.py`:

```python
# --- JD↔CV keyword gap (issue #74) ---------------------------------------------


def test_flatten_strings_walks_nested_structures():
    facts = {"a": ["x", {"b": "y"}], "c": "z", "n": 3, "ok": True}
    assert set(clc._flatten_strings(facts)) == {"x", "y", "z"}


def test_tokenize_lowercases_drops_stopwords_and_short_tokens():
    toks = clc._tokenize("The CRISPR and a to Python")
    assert "crispr" in toks
    assert "python" in toks
    assert "the" not in toks  # stopword
    assert "and" not in toks  # stopword
    assert "to" not in toks  # too short
    assert "a" not in toks  # too short


def test_keyword_gap_buckets_evidenced_vs_gaps():
    cv = {"skills": ["Python", "Snakemake"], "exp": {"text": "variant calling pipelines"}}
    job = "We need Python and CRISPR screening experience."
    out = clc._keyword_gap(cv, job)
    assert "python" in out["evidenced"]
    assert "crispr" in out["gaps"]
    assert "screening" in out["gaps"]
    assert "python" not in out["gaps"]


def test_keyword_gap_drops_stopwords_and_short_tokens():
    cv = {"x": "alpha"}
    out = clc._keyword_gap(cv, "the and for a to alpha")
    assert out["evidenced"] == ["alpha"]
    assert out["gaps"] == []


def test_keyword_gap_dedupes_and_handles_empty():
    cv = {"x": "alpha"}
    out = clc._keyword_gap(cv, "beta beta beta")
    assert out["gaps"] == ["beta"]  # deduped, single occurrence
    assert clc._keyword_gap({}, "") == {"evidenced": [], "gaps": []}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_cover_letter_core.py -k "flatten or tokenize or keyword_gap" -v`
Expected: FAIL with `AttributeError: module 'scripts.cover_letter_core' has no attribute '_flatten_strings'`.

- [ ] **Step 3: Write the implementation**

In `scripts/cover_letter_core.py`, add this section (after `cv_facts`):

```python
# --- JD↔CV keyword gap: advisory honesty diff (issue #74) -----------------------
#
# A CHECKLIST, NOT A VERDICT. Deliberately over-surfaces: the gap list will contain
# false alarms (semantic near-misses, generic words). The agent prunes them. The
# high-precision signal is *absence* — a specific technical term appearing literally
# nowhere in the CV is a trustworthy "do not claim this" anti-fabrication flag.
# Deterministic; never blocks anything.

_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9+#]*")
_MIN_TOKEN_LEN = 3
_STOPWORDS = frozenset(
    {
        # English
        "the", "and", "for", "with", "you", "your", "our", "will", "are", "has",
        "have", "this", "that", "from", "who", "all", "any", "can", "not", "but",
        "its", "their", "they", "them", "was", "were", "been", "being", "into",
        "out", "off", "over", "under", "more", "most", "such", "than", "then",
        "also", "may", "must", "should", "would", "could", "about", "across",
        "within", "using", "use", "used", "work", "working", "role", "team",
        "teams", "including", "etc", "ability", "experience", "years", "year",
        "strong", "good", "excellent", "required", "preferred", "plus",
        # German
        "und", "oder", "der", "die", "das", "den", "dem", "des", "ein", "eine",
        "einen", "einer", "mit", "für", "von", "aus", "bei", "sich", "sie",
        "wir", "ihr", "ihre", "ihren", "auf", "als", "auch", "sind", "ist",
        "wird", "werden", "haben", "sein", "nicht", "kann", "sowie", "bzw",
        "unsere", "unseren",
    }
)


def _flatten_strings(obj) -> list[str]:
    """Recursively collect every string leaf from a nested dict/list structure."""
    out: list[str] = []
    if isinstance(obj, str):
        out.append(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            out.extend(_flatten_strings(v))
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            out.extend(_flatten_strings(v))
    return out


def _tokenize(text: str | None) -> set[str]:
    """Lowercase word tokens, dropping stopwords and tokens shorter than the floor."""
    return {
        tok
        for m in _TOKEN_RE.finditer(text or "")
        if (tok := m.group(0).lower()) not in _STOPWORDS and len(tok) >= _MIN_TOKEN_LEN
    }


def _keyword_gap(facts: dict, job_text: str) -> dict:
    """Bucket JD tokens into evidenced (present in the CV) and gaps (absent).

    Advisory: over-surfaces by design. Output lists preserve JD first-seen order and
    are deduplicated.
    """
    cv_tokens: set[str] = set()
    for s in _flatten_strings(facts):
        cv_tokens |= _tokenize(s)

    seen: list[str] = []
    jd_seen: set[str] = set()
    for m in _TOKEN_RE.finditer(job_text or ""):
        tok = m.group(0).lower()
        if tok in _STOPWORDS or len(tok) < _MIN_TOKEN_LEN or tok in jd_seen:
            continue
        jd_seen.add(tok)
        seen.append(tok)

    return {
        "evidenced": [t for t in seen if t in cv_tokens],
        "gaps": [t for t in seen if t not in cv_tokens],
    }
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_cover_letter_core.py -k "flatten or tokenize or keyword_gap" -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/cover_letter_core.py tests/test_cover_letter_core.py
git commit -m "feat(cover-letter): deterministic JD↔CV keyword-gap core (#74)"
```

---

### Task 4: `jd_keyword_gap(slug)` wrapper + `just jd-gap` CLI

The thin slug-facing wrapper that grounds the gap core in the real CV + an application's `job.md`, plus the `scripts/jd_gap.py` CLI (mirrors `render_letter.py`) and the `just jd-gap` recipe.

**Files:**
- Modify: `scripts/cover_letter_core.py` (add `jd_keyword_gap` right after `_keyword_gap`)
- Create: `scripts/jd_gap.py`
- Modify: `justfile` (add `jd-gap` recipe after the `letter` recipe, near line 78)
- Test: `tests/test_cover_letter_core.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_cover_letter_core.py`:

```python
def test_jd_keyword_gap_reads_job_md_and_grounds_in_cv(apps):
    slug = _make_app(apps, language="en")  # _make_app writes job.md = "x"
    clc._atomic_write(
        f"{slug}/job.md",
        "Seeking Python and bioinformatics; frobnicatorxyz mastery required.",
        apps_dir=apps,
    )
    out = clc.jd_keyword_gap(slug, apps_dir=apps)
    assert isinstance(out["evidenced"], list)
    assert "python" in out["evidenced"]  # Python is a core CV skill
    assert "frobnicatorxyz" in out["gaps"]  # nonsense token absent from the CV


def test_jd_keyword_gap_missing_job_raises(apps):
    slug = _make_app(apps, language="en")
    (apps / slug / "job.md").unlink()
    with pytest.raises(FileNotFoundError):
        clc.jd_keyword_gap(slug, apps_dir=apps)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_cover_letter_core.py -k jd_keyword_gap -v`
Expected: FAIL with `AttributeError: ... has no attribute 'jd_keyword_gap'`.

- [ ] **Step 3: Write the wrapper**

In `scripts/cover_letter_core.py`, directly after `_keyword_gap`:

```python
def jd_keyword_gap(slug: str, *, apps_dir: Path = APPS_DIR) -> dict:
    """Advisory JD↔CV keyword report for an application: {'evidenced', 'gaps'}.

    Reads applications/<slug>/job.md and grounds against the PII-safe cv_facts().
    A checklist, not a verdict — see _keyword_gap. Raises FileNotFoundError if the
    application has no job.md yet.
    """
    slug = _sanitize_slug(slug)
    app_dir = _safe_application_path(slug, apps_dir=apps_dir)
    job_file = app_dir / "job.md"
    if not job_file.exists():
        raise FileNotFoundError(f"no job.md for application: {slug}")
    return _keyword_gap(cv_facts(), job_file.read_text(encoding="utf-8"))
```

- [ ] **Step 4: Run the wrapper tests to verify they pass**

Run: `uv run pytest tests/test_cover_letter_core.py -k jd_keyword_gap -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Create the CLI**

Create `scripts/jd_gap.py`:

```python
"""CLI: print the advisory JD↔CV keyword-gap report for an application slug.

Wraps cover_letter_core.jd_keyword_gap so `just jd-gap <slug>` works. The output is
an ADVISORY CHECKLIST, not a verdict: 'evidenced' terms are JD words the CV can back
(emphasize them); 'gaps' are JD words with no CV match (review — a term appearing
literally nowhere in the CV is a "do not claim this" anti-fabrication flag). The list
deliberately over-surfaces; prune the false alarms by hand.
"""

from __future__ import annotations

import argparse
import sys

from scripts.cover_letter_core import jd_keyword_gap


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jd_gap", description=__doc__)
    parser.add_argument("slug", help="Application slug (folder under applications/)")
    args = parser.parse_args(argv)

    report = jd_keyword_gap(args.slug)
    print("EVIDENCED — JD terms your CV can back (emphasize these):")
    for term in report["evidenced"]:
        print(f"  + {term}")
    print("\nGAPS — JD terms with no CV match (review; a term absent everywhere = do not claim):")
    for term in report["gaps"]:
        print(f"  ? {term}")
    print("\n(Advisory checklist, not a verdict — it over-surfaces; prune false alarms.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 6: Add the `just` recipe**

In `justfile`, after the `letter` recipe (lines 76–78), add:

```just
# Advisory JD↔CV keyword gap report (checklist, not a verdict) → stdout
jd-gap slug:
    uv run python -m scripts.jd_gap "{{slug}}"
```

- [ ] **Step 7: Verify the recipe wiring and full suite**

Run: `just --list | grep jd-gap`
Expected: the `jd-gap slug` recipe is listed.

Run: `uv run pytest tests/test_cover_letter_core.py tests/test_cover_letter_skill_docs.py -v`
Expected: PASS (the existing `test_skill_recipes_exist` is unaffected — the recipe exists; docs reference it in Tasks 6–7).

- [ ] **Step 8: Commit**

```bash
git add scripts/cover_letter_core.py scripts/jd_gap.py justfile tests/test_cover_letter_core.py
git commit -m "feat(cover-letter): jd_keyword_gap wrapper + just jd-gap CLI (#74)"
```

---

### Task 5: `joy` profile field + `voice_sample` docs + examples

Add the optional evergreen `joy` field to the profile schema, document `joy` + `voice_sample` in `reference.md`, and show both in the committed examples. Adding `joy` to the schema makes the existing `test_skill_documents_profile_fields` drift-guard fail until it is documented — that is the TDD signal.

**Files:**
- Modify: `schema/profile.schema.json` (properties block, lines 16–23)
- Modify: `.claude/skills/cover-letter/reference.md` (profile table near lines 32–40; interview list near lines 42–48)
- Modify: `applications.example/profile.example.yaml`
- Modify: `applications.example/example-company-role-2026-06/interview.example.yaml`

- [ ] **Step 1: Add `joy` to the schema (this breaks the drift-guard — intentional)**

In `schema/profile.schema.json`, add a `joy` property to the `properties` object (after `preferences`):

```json
  "properties": {
    "motivation": { "$ref": "#/$defs/LangString" },
    "work_style": { "$ref": "#/$defs/LangString" },
    "availability": { "type": "string" },
    "salary_expectation": { "type": "string" },
    "relocation": { "type": "string" },
    "preferences": { "$ref": "#/$defs/LangString" },
    "joy": { "$ref": "#/$defs/LangString" }
  },
```

- [ ] **Step 2: Run the drift-guard to verify it fails**

Run: `uv run pytest tests/test_cover_letter_skill_docs.py::test_skill_documents_profile_fields -v`
Expected: FAIL — `reference.md is missing profile fields: ['joy']`.

- [ ] **Step 3: Document `joy` in the `reference.md` profile table**

In `.claude/skills/cover-letter/reference.md`, add a row to the `profile.yaml` fields table, after the `preferences` row:

```markdown
| `joy` | What you genuinely enjoy about the day-to-day work (`{ en, de }`) — distinct from `motivation` (the bigger why). Optional; ask once. |
```

- [ ] **Step 4: Document `voice_sample` in the `reference.md` interview list**

In the same file, add a bullet to the `interview.yaml` fields list (after `notes`):

```markdown
- `voice_sample` — one concrete anecdote in the user's own words, captured
  **verbatim** (problem → what they did → outcome). The voice exemplar for drafting
  and a STAR source. Optional; schema-free.
```

- [ ] **Step 5: Run the drift-guard to verify it passes**

Run: `uv run pytest tests/test_cover_letter_skill_docs.py::test_skill_documents_profile_fields -v`
Expected: PASS.

- [ ] **Step 6: Update `applications.example/profile.example.yaml`**

Append a `joy` block (mirror the `{ en, de }` shape of the other prose fields):

```yaml
joy:
  en: "The moment a messy dataset finally clicks into a clean, queryable pipeline."
  de: "Der Moment, in dem aus chaotischen Daten endlich eine saubere, abfragbare Pipeline wird."
```

- [ ] **Step 7: Update `applications.example/example-company-role-2026-06/interview.example.yaml`**

Append a `voice_sample` field (verbatim, plain prose):

```yaml
voice_sample: >-
  Their variant-calling pipeline kept silently dropping reads, so I rewrote the
  filtering step over a weekend and added a check that fails loudly when coverage
  drops. Caught two bad runs the next month.
```

- [ ] **Step 8: Run validation + drift-guards**

Run: `just validate && uv run pytest tests/test_cover_letter_skill_docs.py tests/test_cover_letter_schemas.py -v`
Expected: validate OK (it validates `content/`, untouched); all skill-doc + schema tests PASS.

- [ ] **Step 9: Commit**

```bash
git add schema/profile.schema.json .claude/skills/cover-letter/reference.md applications.example/
git commit -m "feat(cover-letter): optional joy profile field + voice_sample docs/examples (#74)"
```

---

### Task 6: `reference.md` craft sections + new drift-guard

Append the two craft sections (Appendix A1 + A2 from the spec) to `reference.md`, plus the `just jd-gap` recipe row, and add a drift-guard asserting the new sections are present.

**Files:**
- Modify: `.claude/skills/cover-letter/reference.md` (recipe table near lines 4–7; append sections at end)
- Test: `tests/test_cover_letter_skill_docs.py` (append)

- [ ] **Step 1: Write the failing drift-guard test**

Append to `tests/test_cover_letter_skill_docs.py`:

```python
def test_reference_documents_craft_sections():
    """Drift-guard: reference.md must carry the craft-upgrade sections (#74)."""
    ref = (SKILL_DIR / "reference.md").read_text(encoding="utf-8")
    assert "How to write the body" in ref
    assert "AI tells" in ref
    assert "voice_sample" in ref  # documented in the interview field list
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_cover_letter_skill_docs.py::test_reference_documents_craft_sections -v`
Expected: FAIL on `assert "How to write the body" in ref`.

- [ ] **Step 3: Add the `just jd-gap` row to the recipe table**

In `.claude/skills/cover-letter/reference.md`, add a row to the `## Just recipes` table (after the `just letter <slug>` row):

```markdown
| `just jd-gap <slug>` | Advisory JD↔CV keyword report (checklist, not a verdict — over-surfaces; prune false alarms). |
```

- [ ] **Step 4: Append the "How to write the body" section**

At the end of `.claude/skills/cover-letter/reference.md`, append (verbatim from spec Appendix A1):

```markdown

## How to write the body

A résumé says why Jin-Ho is qualified. This letter does the one thing the résumé can't:
it says why he WANTS this specific job and shows how he works. Never restate a CV bullet —
if a sentence could be a résumé line verbatim, cut it or deepen it with the why behind it.

VOICE. Write in Jin-Ho's own voice, reconstructed from his interview answers and profile.yaml.
Match his diction, sentence rhythm, and level of formality. Reuse his actual phrasings where
they fit. Do NOT upgrade his plain, specific words into polished corporate English — that
laundering is the main way this reads as AI. Allow contractions. Vary sentence length: don't
let three sentences in a row land in the same length band. Warm but straightforward, not gushy —
the register technical/biotech readers expect.

OPEN WITH A HOOK, NOT A TITLE. The first 2–3 sentences must hook + establish relevance + hint
at value, using one of: a Story hook (a concrete remembered moment that explains why this work
matters to him), an Achievement hook (lead with a specific result), or a Research hook (a
specific, verifiable insight about THIS company). The body must then deliver on the opening's
promise. Never "I am writing to apply".

SHOW, DON'T TELL — EVERY CLAIM TRACES TO A CV FACT. A trait word may appear only if the same
sentence also names a number, a tool, a named project, or a named outcome from the CV or an
interview answer. Replace every evaluative adjective with the concrete fact that makes a reader
INFER it. If you can't cite a CV/interview fact for a sentence, cut it — never invent color.

ONE UNFAKEABLE COMPANY DETAIL. Weave in exactly one concrete, verifiable fact about this
company/role (a product, a paper, a recent launch, a stated value) that could not appear in any
other letter — bound to one specific thing Jin-Ho has done. This single bind defeats the
"could be sent to 500 companies" test. Don't repeat the company name more than ~twice, and
never substitute generic flattery ("I admire your mission") for a real detail.

MAP EVIDENCE TO THE JD EXPLICITLY. Don't make the reader connect dots — name the JD's own
requirement and attach Jin-Ho's proof for it. Every experience sentence should end in an
employer-benefit clause ("...which is what your X team needs to do Y").

HANDLE GAPS HONESTLY AND EARLY. If there's a pivot or a missing method, name it plainly in 1–2
sentences and pivot to the transferable strength — the cover letter is the recruiter-preferred
place to frame this. Let an anecdote earn the flattering conclusion; never assert "I exceed
your requirements".

CLOSE ON CONTRIBUTING + A CONCRETE NEXT STEP. End by naming what he'd contribute (not "work"),
and propose a specific action ("I'd welcome a short call to walk through the [named] pipeline").
Never the rote "thank you for your consideration".

LENGTH. Half a page to one page; 3–4 paragraphs (intro/close 1–3 sentences, body 3–5). Pick
only the strongest evidence — shorter, specific, and selective beats comprehensive.
```

- [ ] **Step 5: Append the "AI tells & clichés to avoid" section**

Immediately after, append (verbatim from spec Appendix A2):

```markdown

## AI tells & clichés to avoid (advisory — backstop, not the main defense)

NEVER open with: "I am writing to apply for", "I am writing to express my interest in",
"I am excited to apply for the [role] at [company]", "Please accept this letter as",
"To Whom It May Concern", "Dear Sir or Madam".

NEVER close with: "Thank you for your consideration", "I look forward to hearing from you"
(unless naming a concrete topic), "I hope to be considered", "Please do not hesitate to contact me".

Hollow fit/confidence claims (cut entirely): "I would be a great/excellent fit",
"I am the perfect candidate", "uniquely qualified", "I am confident that", "valuable asset".

Empty résumé adjectives (replace with the evidence, never assert): results-driven,
results-oriented, detail-oriented, dynamic, proactive, motivated, hard-working, self-starter,
go-getter, team player, people person, passionate, proven track record, well-rounded,
hit the ground running, fast-paced environment, think outside the box, wheelhouse.

LLM-signature vocabulary (statistical ChatGPT fingerprints): delve, leverage, utilize, foster,
robust, seamless, pivotal, tapestry, landscape, realm, beacon, testament / "a testament to",
underscore, showcase, intricate, multifaceted, comprehensive, transformative, cutting-edge,
ever-evolving, vibrant, synergy, streamline, harness, embark, bolster, boasts, navigate the
complexities, unlock potential, elevate, spearhead.

Filler framing: "in today's fast-paced world", "in the realm of", "it is important to note",
"needless to say", "when it comes to", "at the end of the day", "that being said".

Transition-word tics (don't open consecutive paragraphs with): Furthermore, Moreover,
Additionally, Consequently, Nevertheless, Indeed, Hence, Thus.

Sentence MOLDS to avoid (these survive word-banning):
- rule-of-three / tricolon ("skills, collaboration, and leadership") used repeatedly
- "not just X, but Y" / "not only X but also Y" / "it's not X, it's Y" / "we don't do X, we do Y"
- "from X to Y" range constructions
- copula-avoidance ("serves as", "stands as", "marks a testament to" in place of "is")
- main-clause + present-participle tail ("..., revealing/highlighting/ensuring/demonstrating Z")

Punctuation/structure: cap em-dashes at ~one per letter; no four equal-length tidy paragraphs;
no contraction-free flawless register throughout.

Plain-word swaps: "use" not leverage/utilize; "look into" not delve into; "strong/reliable"
not robust; "work/field" not realm/landscape; show interest through what you did — never
announce "passionate about".
```

- [ ] **Step 6: Run the drift-guard + the recipe guard to verify they pass**

Run: `uv run pytest tests/test_cover_letter_skill_docs.py -v`
Expected: PASS — including `test_reference_documents_craft_sections` and `test_skill_recipes_exist` (which now sees `just jd-gap` referenced and present in the justfile).

- [ ] **Step 7: Commit**

```bash
git add .claude/skills/cover-letter/reference.md tests/test_cover_letter_skill_docs.py
git commit -m "docs(cover-letter): craft + AI-tells reference sections, jd-gap recipe, drift-guard (#74)"
```

---

### Task 7: `SKILL.md` procedural changes (steps 3–5 + allowed-tools)

Wire the gap report (step 3), the hook/voice/joy interview prompts (step 4), and voice-priming + "every paragraph" scope + the self-critique pass (step 5). Add `just jd-gap` to `allowed-tools`.

**Files:**
- Modify: `.claude/skills/cover-letter/SKILL.md` (frontmatter line 8; Flow steps 3–5, lines 38–43)

- [ ] **Step 1: Add `just jd-gap` to allowed-tools**

Replace line 8:

```markdown
allowed-tools: Bash(just letter *), Bash(just validate), Read, Write, Edit
```

with:

```markdown
allowed-tools: Bash(just letter *), Bash(just jd-gap *), Bash(just validate), Read, Write, Edit
```

- [ ] **Step 2: Rewrite step 3 (Gap analysis) to wire the report**

Replace:

```markdown
3. **Gap analysis** — match JD requirements against the CV + profile; list each
   requirement not clearly met.
```

with:

```markdown
3. **Gap analysis** — run `just jd-gap <slug>` for an advisory JD↔CV keyword report
   (a checklist, not a verdict: it over-surfaces — prune the false alarms; a term
   absent from the whole CV is a "do not claim this" flag). Combine it with your own
   read to list each JD requirement not clearly met by the CV + profile.
```

- [ ] **Step 3: Rewrite step 4 (Interview) to add hook / voice-sample / joy prompts**

Replace:

```markdown
4. **Interview** — ask why-this-company, which CV experiences/projects to emphasize,
   and walk every gap (the user decides each). Save `interview.yaml`.
```

with:

```markdown
4. **Interview** — ask, in the user's own words:
   - the specific moment or detail that drew them to *this* company/role (the
     opening hook + the one unfakeable company detail);
   - one concrete moment from the experience to emphasize — problem, what they
     actually did, outcome — captured **verbatim** into `interview.yaml: voice_sample`
     (it is the voice exemplar; do not paraphrase it);
   - which CV experiences/projects to foreground, and a walk through every gap
     (the user decides each).
   If `profile.yaml` has no `joy`, ask once what they genuinely enjoy about this kind
   of work (not what they're good at) and save it to `profile.yaml: joy`.
   Save the per-job answers to `interview.yaml`.
```

- [ ] **Step 4: Rewrite step 5 (Draft) for voice-priming + every-paragraph scope + self-critique**

Replace:

```markdown
5. **Draft** — write the body into `draft.md`, grounded strictly in CV + profile +
   interview answers. Plain paragraphs separated by blank lines (no salutation or
   closing — those are added at render time). Show it to the user.
```

with:

```markdown
5. **Draft** — write the body into `draft.md`, grounded strictly in CV + profile +
   interview answers. Before drafting, read the "How to write the body" and "AI tells
   & clichés to avoid" sections in `reference.md`, and treat the raw `interview.yaml`
   answers + `profile.yaml` + `references.md` as a `<voice_sample>`: these are Jin-Ho's
   own words — match his diction, sentence rhythm, and formality, and reuse his actual
   phrasings; do **not** upgrade his plain, specific words into polished corporate
   English (that laundering is the main way letters read as AI). Apply the drafting
   principles and the AI-tells list to **every paragraph** — the model will not
   generalize the rule from one paragraph to the rest. Then run a silent self-critique
   pass: score the draft 1–10 on Directness, Rhythm, Authenticity (matches the voice
   sample), Specificity (every claim CV/interview-traceable), and Density (anything
   cuttable); rewrite any sentence that pulls a dimension below 7; re-score once. Plain
   paragraphs separated by blank lines (no salutation or closing — those are added at
   render time). Show the user the revised draft with a one-line note that you ran a
   self-critique pass (not the scores).
```

- [ ] **Step 5: Run the skill-doc drift-guards**

Run: `uv run pytest tests/test_cover_letter_skill_docs.py -v`
Expected: PASS — `test_skill_recipes_exist` confirms `just jd-gap` (now referenced in SKILL.md) exists; `test_skill_frontmatter_has_name_and_description` still passes.

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/cover-letter/SKILL.md
git commit -m "docs(cover-letter): wire gap report, hook/voice/joy interview, self-critique draft (#74)"
```

---

### Task 8: Full verification, no-snapshot-churn check, CLAUDE.md update

Confirm the whole gate is green, prove rendered output did not move, and refresh the authoritative project doc.

**Files:**
- Modify: `CLAUDE.md` (scripts list under Layout; Commands block; Phasing table Phase 11 row; the cover-letter convention bullet under "Conventions")

- [ ] **Step 1: Run the full gate**

Run:
```bash
just validate
just test
just lint
uv run ruff format --check .
```
Expected: validate OK; all tests PASS; ruff check clean; format check reports no files would be reformatted. If `ruff format --check` flags the new files, run `just fmt`, re-run the suite, and amend the relevant commit.

- [ ] **Step 2: Prove no snapshot churn**

Run:
```bash
just snapshots-update
git status --porcelain tests/__snapshots__
```
Expected: empty output (no snapshot files changed). If anything changed, the rendered output moved unexpectedly — investigate and fix rather than committing the drift.

- [ ] **Step 3: Update the CLAUDE.md scripts list**

In `CLAUDE.md`, in the `scripts/` line under **Layout**, add `letter_lint.py` and `jd_gap.py` to the enumerated list (after `render_letter.py`):

```
... cover_letter_core.py, letter_text.py, render_letter.py, letter_lint.py, jd_gap.py
```

- [ ] **Step 4: Update the CLAUDE.md Commands block**

Add a `just jd-gap` line near the `just letter` entry:

```
just jd-gap <slug>     # advisory JD↔CV keyword report (checklist, not a verdict) for an application
```

- [ ] **Step 5: Update the Phase 11 row note**

In the Phasing table, append to the Phase 11 Status cell a note that the craft upgrade landed:

```
| 11 | Cover-letter generator (interview + JD → tailored letter, PDF + text) | ✅ Done (merged 2026-06-03, `--no-ff`, PR #66 @claude-approved); personal-voice craft upgrade (anti-slop brief, voice sample, self-critique, jd-gap report, cliché linter) added 2026-06-05 (#74) |
```

- [ ] **Step 6: Update the cover-letter convention bullet**

In the **Conventions** section, extend the "Cover letters are a read-only CV consumer" bullet to mention the craft tooling. Append to that bullet's `Core:` sentence:

```
Core: `scripts/cover_letter_core.py` (+ `letter_text.py`, `render_letter.py`,
`letter_lint.py`, `jd_gap.py`); skill: `.claude/skills/cover-letter/`. The skill carries
craft guidance ("How to write the body" + "AI tells & clichés to avoid" in reference.md);
`just jd-gap <slug>` prints an advisory JD↔CV keyword checklist (not a verdict) and the
cliché linter prints advisory `WARN:` lines from `render_letter` — both deterministic,
neither ever blocks. Rendered text never contains the private address; only the gitignored
PDF does.
```

(Adjust to merge cleanly with the existing wording; keep it one bullet.)

- [ ] **Step 7: Re-run the full gate after doc edits**

Run: `just test`
Expected: PASS (the CLAUDE.md edits are doc-only; this confirms nothing regressed).

- [ ] **Step 8: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: record cover-letter craft upgrade in CLAUDE.md (#74)"
```

---

## Self-Review

**Spec coverage:**
- #1 anti-slop brief → Task 6 (reference.md A1/A2) + Task 7 step 4 ("every paragraph"). ✓
- #2 voice-sample emulation → Task 7 step 4 (`<voice_sample>` priming) + Task 5 (`voice_sample` field/docs/example). ✓
- #3 self-critique → revise → Task 7 step 4 (silent 5-dimension score + rewrite + one-line note). ✓
- #4 opening-hook requirement + interview prompt → Task 6 (A1 "OPEN WITH A HOOK") + Task 7 step 3 prompt. ✓
- #5 deterministic honesty diff → Tasks 3 (`_keyword_gap`) + 4 (`jd_keyword_gap` + `just jd-gap`). ✓
- #6 advisory cliché linter → Tasks 1 (`letter_lint.py`) + 2 (wired into `render_letter`). ✓
- Data shape: `joy` schema + `voice_sample` docs + examples → Task 5. ✓
- Testing/drift-guards → TDD throughout; new `test_reference_documents_craft_sections` (Task 6); `joy` auto-guarded by `test_skill_documents_profile_fields` (Task 5). ✓
- No snapshot churn → Task 8 step 2. ✓
- Green gate (`validate`/`test`/`lint`/`ruff format --check`) → Task 8 step 1. ✓
- Final task updates CLAUDE.md → Task 8 steps 3–6. ✓
- Workflow (one issue → branch → one PR → offer @claude review → squash) is handled at execution time, not a code task — branch `74-cover-letter-craft-upgrade` already exists and is linked to issue #74.

**Placeholder scan:** every code/doc step shows the actual content. No TBD/TODO/"add error handling"/"similar to Task N". ✓

**Type/name consistency:** `lint_body(text, lang)` (Task 1) is called identically in Task 2. `_flatten_strings`/`_tokenize`/`_keyword_gap` (Task 3) are consumed by `jd_keyword_gap` (Task 4) and the tests with matching signatures. `jd_keyword_gap(slug, *, apps_dir=...)` (Task 4) matches its CLI and test usage. Return shape `{"evidenced": [...], "gaps": [...]}` is consistent across core, wrapper, CLI, and tests. ✓

**Out of scope (per spec, not implemented):** highlight-a-line reword control; italics/headings/nested lists in body markup; any LLM call inside the Python tools. ✓
