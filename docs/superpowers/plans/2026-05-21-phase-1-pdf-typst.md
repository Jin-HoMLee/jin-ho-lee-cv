# Phase 1 — PDF Rendering via Typst — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a one-page, EN-only CV PDF rendered from the Phase 0 content tree, via a Python orchestrator that drives a Typst template.

**Architecture:** Python (`pdf/build.py`) loads + resolves YAML, serializes to a flat JSON cache file. Typst template (`pdf/templates/cv.typ`) reads the JSON and renders the layout. Public build omits PII; private build merges `content.private/private.yaml`.

**Tech Stack:** Python 3.12 + `uv`, ruamel.yaml (already a dep), Typst CLI (system install), pytest (already a dev dep). No new Python dependencies.

**Spec:** [`docs/superpowers/specs/2026-05-21-phase-1-pdf-typst-design.md`](../specs/2026-05-21-phase-1-pdf-typst-design.md).

---

## File Structure

**New files:**

- `scripts/langstring.py` — `resolve_langstrings(tree, lang)` recursively replaces `{en: ..., de: ...}` maps with the chosen language's value.
- `pdf/__init__.py` — makes `pdf` a Python package so `python -m pdf.build` works (matches `scripts/` pattern from Phase 0).
- `pdf/build.py` — orchestrator CLI: load → resolve → serialize JSON → invoke `typst compile`.
- `pdf/styles.typ` — design tokens (colors, fonts, sizes, spacing) as Typst values.
- `pdf/templates/cv.typ` — entry point: page setup, reads data, composes sections.
- `pdf/templates/header.typ` — name, headline, contact line.
- `pdf/templates/profile.typ` — tagline + paragraphs.
- `pdf/templates/experience.typ` — entries with inline ref chips.
- `pdf/templates/education.typ` — degree + institution + year.
- `pdf/templates/sidebar.typ` — photo, skills, languages, volunteer.
- `.typstversion` — pinned version string for documentation/warning.
- `tests/test_langstring.py` — unit tests for the resolver.
- `tests/test_build_public.py` — smoke test for public PDF build.
- `tests/test_build_private.py` — smoke test for private overlay.

**Modified files:**

- `.gitignore` — add `pdf/.cache/`.
- `justfile` — add `build`, `build-private`, `clean` recipes.
- `README.md` — add a "Building the PDF" section.

**Design boundary:** the JSON cache lives at `pdf/.cache/data.json` (gitignored). Build.py writes it; cv.typ reads it as `../.cache/data.json`. Keeping the cache inside `pdf/` means we don't need `--root` flag gymnastics — Typst defaults the root to the source file's enclosing directory, and `../.cache/` resolves relative to `pdf/templates/cv.typ`. To allow that parent traversal, `build.py` invokes `typst compile --root pdf pdf/templates/cv.typ <output>`.

---

## Task 1: Langstring resolver (TDD)

**Files:**

- Create: `scripts/langstring.py`
- Create: `tests/test_langstring.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_langstring.py`:

```python
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
    data = {
        "personal": {"name": {"given": "Jin-Ho", "family": "Lee"},
                     "headline": {"en": "Bio | DS"}},
        "experience": [
            {"role": {"en": "Consultant"},
             "bullets": [{"en": "Did things", "refs": ["L1"]}]}
        ],
    }
    result = resolve_langstrings(data, lang="en")
    assert result["personal"]["headline"] == "Bio | DS"
    assert result["personal"]["name"] == {"given": "Jin-Ho", "family": "Lee"}
    assert result["experience"][0]["role"] == "Consultant"
    assert result["experience"][0]["bullets"][0]["en"] == "Did things"  # bullet itself is a langmap → resolved... actually no, bullet is a dict with `en` and `refs`. See implementation note.
```

**Implementation note:** an experience bullet like `{en: "...", refs: [L1]}` is NOT a pure langmap — it has the non-language key `refs`. The resolver must detect this case. Define "langmap" as: a dict whose keys are **all** 2-letter lowercase strings. Anything else is a regular dict → recurse into values.

So in the realistic test, `{en: "Did things", refs: ["L1"]}` is NOT a langmap; the resolver recurses, leaving `en` as-is and `refs` as-is. Update the last assertion:

```python
    assert result["experience"][0]["bullets"][0] == {"en": "Did things", "refs": ["L1"]}
```

- [ ] **Step 2: Run tests, confirm they fail**

```bash
uv run pytest tests/test_langstring.py -v
```

Expected: `ModuleNotFoundError: No module named 'scripts.langstring'`.

- [ ] **Step 3: Implement `scripts/langstring.py`**

```python
"""Resolve {en: ..., de: ...} langstring maps to the selected language."""
from __future__ import annotations

from typing import Any

LANG_CODE_LEN = 2


def _is_langmap(d: dict) -> bool:
    """A dict is a langmap iff all keys are 2-letter lowercase strings."""
    if not d:
        return False
    return all(
        isinstance(k, str) and len(k) == LANG_CODE_LEN and k.islower() and k.isalpha()
        for k in d
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
                f"langmap has no '{lang}' or fallback 'en' key: keys={sorted(tree)}"
            )
        return {k: resolve_langstrings(v, lang) for k, v in tree.items()}
    if isinstance(tree, list):
        return [resolve_langstrings(item, lang) for item in tree]
    return tree
```

- [ ] **Step 4: Run tests, confirm they pass**

```bash
uv run pytest tests/test_langstring.py -v
```

Expected: 8 passed.

- [ ] **Step 5: Run lint and full suite**

```bash
uv run ruff check . && uv run ruff format --check . && uv run pytest -v
```

Expected: lint clean, all tests pass (Phase 0 tests still green + 8 new).

- [ ] **Step 6: Commit**

```bash
git add scripts/langstring.py tests/test_langstring.py
git commit -m "feat: add resolve_langstrings for language selection"
```

---

## Task 2: Bootstrap `pdf/` module + styles + Typst version pin

**Files:**

- Create: `pdf/__init__.py` (empty)
- Create: `pdf/styles.typ`
- Create: `.typstversion`
- Modify: `.gitignore`

- [ ] **Step 1: Create `pdf/__init__.py`**

```python
"""PDF rendering — Python orchestrator + Typst templates."""
```

- [ ] **Step 2: Create `pdf/styles.typ`**

```typst
// Design tokens — colors, fonts, sizes, spacing.
// Spec: docs/superpowers/specs/2026-05-21-phase-1-pdf-typst-design.md §4.

#let accent = rgb("#1f3a68")
#let sidebar-bg = rgb("#f4f7fb")
#let muted = rgb("#6b6b6b")
#let body-color = rgb("#222222")

#let font-family = "IBM Plex Sans"

#let size-body = 9.5pt
#let size-small = 8pt
#let size-section = 10pt
#let size-name = 18pt
#let size-headline = 10pt

#let space-section = 8pt
#let space-paragraph = 4pt

#let sidebar-ratio = (1fr, 0.5fr)  // main : sidebar  ≈ 66 : 34
#let column-gutter = 12pt

#let page-margin = 14mm

// Section heading: small-caps, letterspaced, accent color.
#let section-heading(title) = {
  v(space-section)
  text(
    size: size-section,
    weight: 600,
    fill: accent,
    tracking: 1pt,
  )[#upper(title)]
  v(space-paragraph)
}

// Inline reference chip e.g. "L1" appended to an experience bullet.
#let ref-chip(id) = box(
  fill: accent.lighten(85%),
  inset: (x: 3pt, y: 1pt),
  outset: (y: 1pt),
  radius: 2pt,
)[
  #text(size: 7pt, weight: 600, fill: accent, tracking: 0.5pt)[#upper(id)]
]
```

- [ ] **Step 3: Create `.typstversion`**

```
0.13.0
```

(Implementing engineer: replace with the actual `typst --version` output on your machine if different — this is a documentation pin, not a hard requirement.)

- [ ] **Step 4: Update `.gitignore`**

Append after the existing `dist-private/` line:

```
# PDF build cache (JSON intermediate written by pdf/build.py)
pdf/.cache/
```

- [ ] **Step 5: Run lint and tests**

```bash
uv run ruff check . && uv run pytest -v
```

Expected: still green; nothing imports the new files yet.

- [ ] **Step 6: Commit**

```bash
git add pdf/__init__.py pdf/styles.typ .typstversion .gitignore
git commit -m "feat: scaffold pdf/ module with design tokens"
```

---

## Task 3: `pdf/build.py` — data prep + JSON serialization (TDD, no Typst yet)

**Files:**

- Create: `pdf/build.py`
- Create: `tests/test_build_data.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_build_data.py`:

```python
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
    assert result["personal"]["headline"] == "Bioinformatics | Data Science | Consulting"

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
```

- [ ] **Step 2: Run tests, confirm they fail**

```bash
uv run pytest tests/test_build_data.py -v
```

Expected: `ModuleNotFoundError: No module named 'pdf.build'`.

- [ ] **Step 3: Implement `pdf/build.py` (data prep only)**

```python
"""PDF build orchestrator: load content → resolve langs → serialize JSON → compile Typst."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from scripts.content_loader import load_content
from scripts.langstring import resolve_langstrings

REPO_ROOT = Path(__file__).resolve().parent.parent


def prepare_data(
    content_dir: Path,
    *,
    private_path: Path | None,
    lang: str,
) -> dict[str, Any]:
    """Load content tree, merge private overlay, resolve langstrings, return flat dict."""
    raw = load_content(content_dir, private_path=private_path, lang=lang)
    return resolve_langstrings(raw, lang=lang)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="pdf.build",
        description="Render the CV PDF via Typst.",
    )
    p.add_argument("--lang", default="en", help="Language code (default: en)")
    p.add_argument(
        "--private",
        action="store_true",
        help="Merge content.private/private.yaml; PDF lands in dist-private/",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    content_dir = REPO_ROOT / "content"
    private_path = REPO_ROOT / "content.private" / "private.yaml" if args.private else None

    if args.private and not private_path.exists():
        print(
            f"--private was given but {private_path} does not exist. "
            "Refusing to silently produce a public build.",
            file=sys.stderr,
        )
        return 2

    data = prepare_data(content_dir, private_path=private_path, lang=args.lang)

    cache_dir = REPO_ROOT / "pdf" / ".cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "data.json").write_text(json.dumps(data, ensure_ascii=False, indent=2))

    # Typst invocation added in Task 4.
    print(f"Wrote {cache_dir / 'data.json'}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests, confirm they pass**

```bash
uv run pytest tests/test_build_data.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Manual smoke**

```bash
uv run python -m pdf.build --lang en
```

Expected: stderr line `Wrote .../pdf/.cache/data.json`, exit 0. File should be valid JSON containing your content. Inspect with `head -40 pdf/.cache/data.json`.

- [ ] **Step 6: Run lint + full suite**

```bash
uv run ruff check . && uv run pytest -v
```

Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add pdf/build.py tests/test_build_data.py
git commit -m "feat: pdf.build data-prep pipeline (load + resolve + serialize)"
```

---

## Task 4: Minimal Typst integration — cv.typ stub + build.py invokes typst

**Files:**

- Create: `pdf/templates/cv.typ`
- Modify: `pdf/build.py`
- Create: `tests/test_build_public.py`

This task gets a *bare* PDF out (page setup + just the name rendered) so we verify the toolchain end-to-end. Subsequent tasks add the real content sections.

- [ ] **Step 1: Verify Typst is installed**

```bash
typst --version
```

If not installed: `brew install typst` (macOS) or `cargo install --locked typst-cli`.

- [ ] **Step 2: Create `pdf/templates/cv.typ` (stub)**

```typst
#import "../styles.typ": *

#let data = json("../.cache/data.json")

#set page(
  paper: "a4",
  margin: page-margin,
)
#set text(
  font: font-family,
  size: size-body,
  fill: body-color,
)

= #data.personal.name.given #data.personal.name.family
```

- [ ] **Step 3: Modify `pdf/build.py` to invoke typst**

Replace the `# Typst invocation added in Task 4.` block in `main()` with:

```python
    out_dir = REPO_ROOT / ("dist-private" if args.private else "dist")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"cv-{args.lang}.pdf"

    template = REPO_ROOT / "pdf" / "templates" / "cv.typ"

    import subprocess
    result = subprocess.run(
        [
            "typst", "compile",
            "--root", str(REPO_ROOT / "pdf"),
            str(template),
            str(out_path),
        ],
        check=False,
    )
    if result.returncode != 0:
        print(f"typst compile failed (exit {result.returncode})", file=sys.stderr)
        return result.returncode

    print(f"Wrote {out_path}", file=sys.stderr)
    return 0
```

Also move `import subprocess` to the top of the file with the other imports.

- [ ] **Step 4: Manual smoke**

```bash
uv run python -m pdf.build --lang en
```

Expected: produces `dist/cv-en.pdf`. Open it and verify the name "Jin-Ho Lee" appears.

- [ ] **Step 5: Write smoke test**

Create `tests/test_build_public.py`:

```python
"""Smoke test: public PDF build produces a valid PDF."""
import shutil
import subprocess
import sys

import pytest


def _typst_available() -> bool:
    return shutil.which("typst") is not None


pytestmark = pytest.mark.skipif(
    not _typst_available(),
    reason="typst CLI not installed; install via 'brew install typst' to run PDF tests.",
)


def test_public_build_produces_valid_pdf(repo_root, tmp_path, monkeypatch):
    """Run `python -m pdf.build --lang en` and assert dist/cv-en.pdf exists + valid."""
    # Run from repo root; output lands in repo_root/dist/. We clean it after.
    dist = repo_root / "dist"
    out = dist / "cv-en.pdf"
    if out.exists():
        out.unlink()

    result = subprocess.run(
        [sys.executable, "-m", "pdf.build", "--lang", "en"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, f"build failed:\nstdout={result.stdout}\nstderr={result.stderr}"
    assert out.exists(), f"expected {out} to be created"
    assert out.stat().st_size > 500, "PDF suspiciously small"

    with out.open("rb") as f:
        magic = f.read(5)
    assert magic == b"%PDF-", f"not a PDF (magic bytes: {magic!r})"
```

- [ ] **Step 6: Run smoke test**

```bash
uv run pytest tests/test_build_public.py -v
```

Expected: 1 passed (or skipped if typst missing).

- [ ] **Step 7: Run lint + full suite**

```bash
uv run ruff check . && uv run pytest -v
```

Expected: all green.

- [ ] **Step 8: Commit**

```bash
git add pdf/templates/cv.typ pdf/build.py tests/test_build_public.py
git commit -m "feat: end-to-end Typst compile producing minimal PDF"
```

---

## Task 5: Header template

**Files:**

- Create: `pdf/templates/header.typ`
- Modify: `pdf/templates/cv.typ`

- [ ] **Step 1: Create `pdf/templates/header.typ`**

Header renders name, headline, and contact line (email, LinkedIn handle, GitHub handle, city/country, phone if private). Photo lives in the sidebar (Task 7), NOT here.

```typst
#import "../styles.typ": *

#let _link-handle(url) = {
  // Strip "https://linkedin.com/in/" etc. to just the handle.
  let s = url
  for prefix in (
    "https://linkedin.com/in/",
    "https://www.linkedin.com/in/",
    "https://github.com/",
    "https://www.github.com/",
    "https://researchgate.net/profile/",
    "https://www.researchgate.net/profile/",
  ) {
    if s.starts-with(prefix) {
      s = s.slice(prefix.len())
    }
  }
  s
}

#let header(personal) = {
  // Name
  text(size: size-name, weight: 700, fill: accent)[
    #personal.name.given #personal.name.family
  ]
  linebreak()

  // Headline (already resolved to a string)
  text(size: size-headline, fill: muted)[#personal.headline]
  v(6pt)

  // Contact line — pipe-separated
  let parts = ()
  parts.push(personal.email)
  if "phone" in personal { parts.push(personal.phone) }

  let loc = ()
  if "city" in personal.location { loc.push(personal.location.city) }
  if "country" in personal.location { loc.push(personal.location.country) }
  if loc.len() > 0 { parts.push(loc.join(", ")) }

  if "linkedin" in personal.links and personal.links.linkedin != none {
    parts.push("in/" + _link-handle(personal.links.linkedin))
  }
  if "github" in personal.links and personal.links.github != none {
    parts.push("gh/" + _link-handle(personal.links.github))
  }

  text(size: size-small, fill: muted)[#parts.join("  ·  ")]

  v(4pt)
  line(length: 100%, stroke: 0.5pt + accent.lighten(60%))
}
```

- [ ] **Step 2: Update `pdf/templates/cv.typ` to use header**

Replace the body of `cv.typ` (everything after the `#set text(...)` block) with:

```typst
#import "header.typ": header

#header(data.personal)
```

So the full `cv.typ` is now:

```typst
#import "../styles.typ": *
#import "header.typ": header

#let data = json("../.cache/data.json")

#set page(
  paper: "a4",
  margin: page-margin,
)
#set text(
  font: font-family,
  size: size-body,
  fill: body-color,
)

#header(data.personal)
```

- [ ] **Step 3: Manual smoke + visual check**

```bash
uv run python -m pdf.build --lang en
open dist/cv-en.pdf  # macOS
```

Expected: name in navy at top, headline in muted grey below, contact line, separator. If typography looks wrong (missing IBM Plex Sans), Typst falls back to a default font — run `typst fonts` to see what's available. Install IBM Plex Sans: `brew install --cask font-ibm-plex` on macOS.

- [ ] **Step 4: Run tests**

```bash
uv run pytest -v
```

Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add pdf/templates/header.typ pdf/templates/cv.typ
git commit -m "feat: pdf header with name, headline, contact line"
```

---

## Task 6: Profile + Experience templates (main column)

**Files:**

- Create: `pdf/templates/profile.typ`
- Create: `pdf/templates/experience.typ`
- Modify: `pdf/templates/cv.typ`

- [ ] **Step 1: Create `pdf/templates/profile.typ`**

```typst
#import "../styles.typ": *

#let profile(p) = {
  section-heading("Profile")

  if "tagline" in p {
    text(weight: 600)[#p.tagline]
    v(space-paragraph)
  }

  for para in p.paragraphs {
    par(justify: true)[#para]
    v(space-paragraph)
  }
}
```

- [ ] **Step 2: Create `pdf/templates/experience.typ`**

Experience entries: each has `org.name`, `role` (string after resolution), `period.start`–`period.end`, and `bullets`. Each bullet is either a string (legacy) or a dict `{en: "...", refs: [...]}`. After langstring resolution, the `en` key remains because the bullet dict isn't a pure langmap. So a bullet looks like `{en: "text", refs: ["L1"]}` post-resolution.

```typst
#import "../styles.typ": *

#let _period(p) = {
  let s = if "start" in p { p.start } else { "" }
  let e = if "end" in p and p.end != none { p.end } else { "present" }
  s + " – " + e
}

#let _bullet(b) = {
  let txt = if type(b) == str { b } else { b.en }
  let refs = if type(b) == dictionary and "refs" in b { b.refs } else { () }

  // Bullet line: dash + text + optional refs at end
  grid(
    columns: (8pt, 1fr),
    gutter: 4pt,
    text(fill: accent)[•],
    {
      txt
      if refs.len() > 0 {
        h(4pt)
        for (i, r) in refs.enumerate() {
          if i > 0 { h(2pt) }
          ref-chip(r)
        }
      }
    },
  )
  v(2pt)
}

#let experience(entries) = {
  section-heading("Experience")

  for entry in entries {
    // Org + period on one line; role on next
    grid(
      columns: (1fr, auto),
      align: (left, right),
      text(weight: 600)[#entry.org.name],
      text(size: size-small, fill: muted)[#_period(entry.period)],
    )
    text(style: "italic", fill: muted)[#entry.role]
    v(space-paragraph)

    for bullet in entry.bullets {
      _bullet(bullet)
    }
    v(space-section / 2)
  }
}
```

- [ ] **Step 3: Update `pdf/templates/cv.typ` to compose main column**

Update `cv.typ` to wrap profile + experience in a two-column grid. The sidebar column is empty for now (filled in Task 7).

```typst
#import "../styles.typ": *
#import "header.typ": header
#import "profile.typ": profile
#import "experience.typ": experience

#let data = json("../.cache/data.json")

#set page(
  paper: "a4",
  margin: page-margin,
)
#set text(
  font: font-family,
  size: size-body,
  fill: body-color,
)

#header(data.personal)
#v(6pt)

#grid(
  columns: sidebar-ratio,
  gutter: column-gutter,
  // Main column
  {
    profile(data.profile)
    experience(data.experience)
  },
  // Sidebar (placeholder until Task 7)
  rect(fill: sidebar-bg, width: 100%, height: 100%)[],
)
```

- [ ] **Step 4: Manual build + visual check**

```bash
uv run python -m pdf.build --lang en
open dist/cv-en.pdf
```

Expected: header at top, then two columns — left has Profile and Experience with ref chips like `L1` `C1` next to bullets; right is a light-blue rectangle.

- [ ] **Step 5: Run tests**

```bash
uv run pytest -v
```

Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add pdf/templates/profile.typ pdf/templates/experience.typ pdf/templates/cv.typ
git commit -m "feat: pdf profile and experience templates with ref chips"
```

---

## Task 7: Education + Sidebar templates

**Files:**

- Create: `pdf/templates/education.typ`
- Create: `pdf/templates/sidebar.typ`
- Modify: `pdf/templates/cv.typ`

- [ ] **Step 1: Create `pdf/templates/education.typ`**

Education entries: list of `{degree: <string after resolve>, institution: <str>, location: <str>, year: <int>}`.

```typst
#import "../styles.typ": *

#let education(entries) = {
  section-heading("Education")

  for entry in entries {
    grid(
      columns: (1fr, auto),
      align: (left, right),
      {
        text(weight: 600)[#entry.degree]
        linebreak()
        text(size: size-small, fill: muted)[
          #entry.institution#if "location" in entry { " · " + entry.location }
        ]
      },
      text(size: size-small, fill: muted)[#entry.year],
    )
    v(space-paragraph)
  }
}
```

- [ ] **Step 2: Create `pdf/templates/sidebar.typ`**

Sidebar: circular photo at top (if `assets/photo.jpg` exists), then Skills (categorized), Languages, Volunteer.

```typst
#import "../styles.typ": *

#let _maybe-photo() = {
  // Photo lives at repo_root/assets/photo.jpg. From this file (pdf/templates/sidebar.typ),
  // the relative path is ../../assets/photo.jpg. typst gracefully errors if missing;
  // we wrap in a context that warns instead via build-time presence check below.
  // For now, conditionally include based on a sidecar marker.
  // (Implementation note: presence is checked in build.py; if missing, it removes
  //  pdf/.cache/has-photo. We check existence of that marker here.)
  if sys.inputs.at("has-photo", default: "0") == "1" {
    align(center)[
      #box(clip: true, radius: 50%, width: 80pt, height: 80pt)[
        #image("/../assets/photo.jpg", width: 80pt, height: 80pt, fit: "cover")
      ]
    ]
    v(8pt)
  }
}

#let _skills(skills) = {
  section-heading("Skills")
  for category in skills.categories {
    text(weight: 600, size: size-small)[#category.name]
    v(2pt)
    for group in category.groups {
      text(size: size-small, fill: muted)[#group.label: ]
      text(size: size-small)[#group.items.join(", ")]
      linebreak()
    }
    v(space-paragraph)
  }
}

#let _languages(langs) = {
  section-heading("Languages")
  for l in langs {
    grid(
      columns: (1fr, auto),
      text(size: size-small)[#l.name],
      text(size: size-small, fill: muted)[#l.proficiency],
    )
    v(2pt)
  }
}

#let _volunteer(v_data) = {
  section-heading("Volunteer")
  for category in v_data.categories {
    text(weight: 600, size: size-small)[#category.name]
    v(2pt)
    text(size: size-small, fill: muted)[#category.entries.join(", ")]
    v(space-paragraph)
  }
}

#let sidebar(data) = {
  block(
    fill: sidebar-bg,
    inset: (x: 10pt, y: 10pt),
    stroke: (left: 3pt + accent),
    width: 100%,
  )[
    #_maybe-photo()
    #_skills(data.skills)
    #_languages(data.languages)
    #_volunteer(data.volunteer)
  ]
}
```

**About the photo:** Typst can't easily probe whether a file exists. Workaround: `build.py` checks `assets/photo.jpg` presence and passes `--input has-photo=1` (or `0`) to `typst compile`. Sidebar reads `sys.inputs.has-photo` and skips the photo block when `0`.

- [ ] **Step 3: Modify `pdf/build.py` to pass `has-photo` input**

In `main()`, before the `subprocess.run` call, add:

```python
    has_photo = (REPO_ROOT / "assets" / "photo.jpg").exists()
    photo_input = f"has-photo={'1' if has_photo else '0'}"

    if not has_photo:
        print(
            "warning: assets/photo.jpg not found; sidebar will render without photo",
            file=sys.stderr,
        )
```

And modify the `subprocess.run` call to include `"--input", photo_input`:

```python
    result = subprocess.run(
        [
            "typst", "compile",
            "--root", str(REPO_ROOT / "pdf"),
            "--input", photo_input,
            str(template),
            str(out_path),
        ],
        check=False,
    )
```

- [ ] **Step 4: Update `pdf/templates/cv.typ` to compose all sections**

```typst
#import "../styles.typ": *
#import "header.typ": header
#import "profile.typ": profile
#import "experience.typ": experience
#import "education.typ": education
#import "sidebar.typ": sidebar

#let data = json("../.cache/data.json")

#set page(
  paper: "a4",
  margin: page-margin,
)
#set text(
  font: font-family,
  size: size-body,
  fill: body-color,
)

#header(data.personal)
#v(6pt)

#grid(
  columns: sidebar-ratio,
  gutter: column-gutter,
  // Main column
  {
    profile(data.profile)
    experience(data.experience)
    education(data.education)
  },
  // Sidebar
  sidebar(data),
)
```

- [ ] **Step 5: Manual build + visual check**

```bash
uv run python -m pdf.build --lang en
open dist/cv-en.pdf
```

Expected: full PDF with header, two-column layout. Main column: Profile → Experience (with ref chips) → Education. Sidebar (light blue with navy left border): photo at top (or skipped with warning), then Skills (grouped), Languages, Volunteer. Should fit on **one page**. If it overflows, that's editorial — note it as a follow-up but don't block on it.

- [ ] **Step 6: Run tests + lint**

```bash
uv run ruff check . && uv run pytest -v
```

Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add pdf/templates/education.typ pdf/templates/sidebar.typ pdf/templates/cv.typ pdf/build.py
git commit -m "feat: pdf education + sidebar (photo, skills, languages, volunteer)"
```

---

## Task 8: Private overlay smoke test

**Files:**

- Create: `tests/test_build_private.py`

- [ ] **Step 1: Write the test**

```python
"""Smoke test: --private overlay produces a different PDF in dist-private/."""
import shutil
import subprocess
import sys

import pytest


def _typst_available() -> bool:
    return shutil.which("typst") is not None


pytestmark = pytest.mark.skipif(
    not _typst_available(),
    reason="typst CLI not installed",
)


@pytest.fixture
def fake_private_yaml(repo_root):
    """Write a temporary content.private/private.yaml; clean up after.

    Build.py reads from REPO_ROOT/content.private/private.yaml unconditionally
    when --private is given, so we have to write there (and restore afterward
    if a real one exists).
    """
    private_dir = repo_root / "content.private"
    private_file = private_dir / "private.yaml"

    had_dir = private_dir.exists()
    backup_content = None
    if private_file.exists():
        backup_content = private_file.read_text()

    private_dir.mkdir(exist_ok=True)
    private_file.write_text(
        'phone: "+49 000 0000000"\n'
        'address:\n'
        '  street: "Teststr. 1"\n'
        '  postal_code: "00000"\n'
        '  city: "Testville"\n'
        '  country: "ZZ"\n'
    )

    yield private_file

    if backup_content is not None:
        private_file.write_text(backup_content)
    else:
        private_file.unlink()
        if not had_dir:
            private_dir.rmdir()


def test_private_build_produces_pdf_different_from_public(repo_root, fake_private_yaml):
    """Public and private builds should produce byte-different PDFs.

    The private build's PDF will contain the phone number rendered in the header,
    so the file bytes must differ from the public build.
    """
    public_out = repo_root / "dist" / "cv-en.pdf"
    private_out = repo_root / "dist-private" / "cv-en.pdf"

    # Clean prior outputs
    for p in (public_out, private_out):
        if p.exists():
            p.unlink()

    # Public build
    r_pub = subprocess.run(
        [sys.executable, "-m", "pdf.build", "--lang", "en"],
        cwd=repo_root, capture_output=True, text=True,
    )
    assert r_pub.returncode == 0, f"public build failed: {r_pub.stderr}"
    assert public_out.exists()

    # Private build (with fixture overlay)
    r_priv = subprocess.run(
        [sys.executable, "-m", "pdf.build", "--lang", "en", "--private"],
        cwd=repo_root, capture_output=True, text=True,
    )
    assert r_priv.returncode == 0, f"private build failed: {r_priv.stderr}"
    assert private_out.exists()

    # PDFs must differ — phone got rendered in private build
    assert public_out.read_bytes() != private_out.read_bytes(), (
        "private and public PDFs are byte-identical; overlay did not affect output"
    )


def test_private_build_fails_when_private_yaml_missing(repo_root):
    """If --private is passed but content.private/private.yaml is absent, exit non-zero."""
    private_dir = repo_root / "content.private"
    private_file = private_dir / "private.yaml"

    # Move aside any existing file
    backup = None
    if private_file.exists():
        backup = private_file.read_text()
        private_file.unlink()

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pdf.build", "--lang", "en", "--private"],
            cwd=repo_root, capture_output=True, text=True,
        )
        assert result.returncode != 0, "expected non-zero exit when private.yaml missing"
        assert "does not exist" in result.stderr.lower() or "private" in result.stderr.lower()
    finally:
        if backup is not None:
            private_file.write_text(backup)
```

- [ ] **Step 2: Run tests**

```bash
uv run pytest tests/test_build_private.py -v
```

Expected: 2 passed (or skipped if typst missing).

- [ ] **Step 3: Run lint + full suite**

```bash
uv run ruff check . && uv run pytest -v
```

Expected: all green.

- [ ] **Step 4: Commit**

```bash
git add tests/test_build_private.py
git commit -m "test: smoke test for --private overlay producing different PDF"
```

---

## Task 9: justfile recipes + README

**Files:**

- Modify: `justfile`
- Modify: `README.md`

- [ ] **Step 1: Update `justfile`**

Read the current `justfile` and append (after the existing `fmt:` recipe):

```just

# Build the public PDF (no PII) → dist/cv-en.pdf
build:
    uv run python -m pdf.build --lang en

# Build the private PDF (with phone + address) → dist-private/cv-en.pdf
build-private:
    uv run python -m pdf.build --lang en --private

# Remove build outputs
clean:
    rm -rf dist/ dist-private/ pdf/.cache/
```

- [ ] **Step 2: Verify recipes work**

```bash
just clean
just build
ls -la dist/cv-en.pdf
```

Expected: PDF produced.

- [ ] **Step 3: Update README.md**

Read the current `README.md`. After the existing commands section (or at an appropriate location), add a "Building the PDF" section:

```markdown
## Building the PDF

Phase 1 produces a one-page English PDF locally. Requirements:

- Python 3.12 + `uv` (already needed for Phase 0)
- Typst CLI: `brew install typst` (macOS) or `cargo install --locked typst-cli`
- IBM Plex Sans font (recommended): `brew install --cask font-ibm-plex` on macOS. If absent, Typst falls back to a default sans font.
- Optional: `assets/photo.jpg` for the sidebar photo. If missing, the sidebar reflows without it.

### Commands

```bash
just build          # → dist/cv-en.pdf (no PII)
just build-private  # → dist-private/cv-en.pdf (with phone + address)
just clean          # remove dist/, dist-private/, and pdf/.cache/
```

The private build requires `content.private/private.yaml` to exist. Copy `content.private.example/private.example.yaml` and fill in your details.

### How it works

`pdf/build.py` loads the YAML content tree (Phase 0 loader), merges the private overlay if present, resolves language maps to plain strings, writes the result to `pdf/.cache/data.json`, then invokes `typst compile` on `pdf/templates/cv.typ`. The Typst template reads the JSON and renders the layout. Design tokens live in `pdf/styles.typ`.
```

(The implementing engineer should read the current README structure and insert this section in a sensible location — after Phase 0 docs but before any deferred-phase placeholders.)

- [ ] **Step 4: Run the full validation suite**

```bash
just validate && just test && just lint
```

Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add justfile README.md
git commit -m "docs: justfile recipes and README section for PDF builds"
```

---

## Task 10: Final review and merge prep

- [ ] **Step 1: Re-read the spec** (`docs/superpowers/specs/2026-05-21-phase-1-pdf-typst-design.md`) and verify each done-criterion in §12:
  - [ ] `just build` produces `dist/cv-en.pdf` — one page, all sections present, no PII
  - [ ] `just build-private` produces `dist-private/cv-en.pdf` — phone + address rendered
  - [ ] `just test` is green
  - [ ] `just lint` and `just validate` pass
  - [ ] README has a "Building the PDF" section

- [ ] **Step 2: Open both PDFs**, side by side, visually confirm:
  - [ ] Layout is two-column with sidebar on the right, light blue background, navy left border
  - [ ] Header has name, headline, contact line
  - [ ] Profile is at top of main column
  - [ ] Experience entries have inline ref chips (e.g. `L1`)
  - [ ] Education appears under Experience
  - [ ] Sidebar contains photo (if present), Skills, Languages, Volunteer
  - [ ] Private PDF has phone, public PDF doesn't
  - [ ] Whole CV fits on one page (or you've noted the overflow as editorial)

- [ ] **Step 3: Verify branch state**

```bash
git log --oneline main..phase-1-pdf
```

Expected: a clean chain of focused commits per task.

- [ ] **Step 4: Use the `superpowers:finishing-a-development-branch` skill** to handle the merge to `main` with `--no-ff` per repo convention.

---

## Self-review notes

Skimmed each spec section against the plan:

- §2 In scope — covered by Tasks 1-9 (build flow, public + private builds, tests).
- §2 Out of scope — explicitly *not* in the plan: DE, CI, web, JSON Resume, JSON-LD, publications, separate projects section. ✓
- §3 Sections + ordering — covered by Tasks 5-7.
- §4 Visual decisions — locked into `pdf/styles.typ` in Task 2; consumed by all template tasks.
- §5 Build flow + langstring resolution — Tasks 1, 3, 4.
- §5.2 Private overlay — Tasks 3 (data), 4 (CLI flag), 8 (test).
- §6 File structure — Task 2 bootstraps it; subsequent tasks fill in.
- §7 CLI — Task 9.
- §8 Testing — Tasks 1 (langstring), 3 (data prep), 4 (public smoke), 8 (private smoke). All three test types from spec covered.
- §9 Typst install + version pinning — Task 2 (`.typstversion`), Task 9 README.
- §10 Assets — Task 7 sidebar handles missing photo gracefully.
- §11 Open questions — left to implementation tuning, no plan changes needed.
- §12 Done criteria — Task 10 checklist mirrors them.

No spec gaps. Type/name consistency verified: `prepare_data`, `resolve_langstrings`, `section-heading`, `ref-chip`, `sidebar-ratio` all named consistently across tasks where used.
