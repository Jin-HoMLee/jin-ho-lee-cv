# Issue #43 — PDF Publications Section Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a publications section to the Typst PDF — DOI-linked titles, the candidate's name bold, a variant-aware depth (full 15 for `comp-bio`, selected 9 for `bridge`/`ds-ml`), placed between Selected Projects and Awards.

**Architecture:** A new pure Python helper `select_publications(pubs, target)` in `pdf/build.py` decides the depth (a PDF *rendering* choice, deliberately NOT in the shared `content_loader` — `bridge` means all 15 for web/text but selected 9 for the PDF). `prepare_data` calls it and injects the filtered list plus an already-resolved heading string into `pdf/.cache/data.json`. A new Typst template `pdf/templates/publications.typ` is a dumb renderer: it prints the heading and iterates the list. No variant logic crosses into Typst (which only receives `lang`).

**Tech Stack:** Python 3.12 (dataclasses, pytest), Typst 0.14.2 (pinned in `.typstversion`), `pdftotext` (poppler) for the best-effort text assertion.

**Spec:** `docs/superpowers/specs/2026-06-01-issue-43-pdf-publications-design.md`

---

## File Structure

| File | Responsibility | Change |
| --- | --- | --- |
| `pdf/build.py` | Build orchestrator: load → resolve → serialize → compile. | Add pure helper `select_publications()`; call it in `prepare_data()` and inject `publications` (filtered) + `publications_heading` (resolved string). |
| `pdf/templates/publications.typ` | Render the publications section. | **New.** `#let publications(pubs, heading, family)`. |
| `pdf/templates/cv.typ` | Compose the document from section templates. | Import `publications`; call it between `selected_projects(...)` and `awards(...)`. |
| `content/labels.yaml` | Section heading langstrings. | Add `sections.publications` and `sections.publications_selected`. |
| `tests/test_pdf_publications.py` | All tests for this feature. | **New.** Unit (helper) + integration (`prepare_data`) + best-effort PDF text. |

**Data flow (confirmed against the code):**

```text
content/publications.bib
  → bib_loader.load_publications()      # 15 Publication records, titles cleaned (#41), sorted research→applied / year-desc
  → content_loader.load_content()       # content["publications"] = full list (web/text consume this unchanged)
  → pdf.build.prepare_data():
        resolve_langstrings(...)         # labels.sections.* → plain strings; Publication dataclasses pass through untouched
        select_publications(pubs, target) → (filtered_list, is_selected)
        inject data["publications"] = filtered_list
        inject data["publications_heading"] = resolved "Publications (selected)" | "Publications" (per is_selected + lang)
  → pdf/.cache/data.json
  → cv.typ → publications(data.publications, data.publications_heading, data.personal.name.family)
```

**Empirical data (verified this session) — drives the assertions below:**

- 15 publications total: `first`=6, `shared`=3, `middle`=6. Subset (`first`+`shared`) = **9**. 11 have a DOI.
- Author strings are `"Family, Initial."` form, e.g. `"Lee, J."`, `"Hausmann, M."`. The candidate's family name is `"Lee"`, so `author.starts-with("Lee,")` selects the candidate (no other author shares it).
- The BibTeX `and others` marker serializes as a literal trailing author token `"others"` → render as italic *et al.*
- `data.personal.name.family == "Lee"`.

---

## Task 1: `select_publications()` pure helper (unit, TDD)

**Files:**
- Modify: `pdf/build.py` (add helper above `prepare_data`, after `_pdf_filename`)
- Test: `tests/test_pdf_publications.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/test_pdf_publications.py`. Import only what this task uses — later
tasks add their own imports at point-of-use (incremental imports keep `ruff`
F401 clean without `# noqa` suppressions):

```python
"""Tests for the PDF publications section (issue #43)."""
from pdf.build import select_publications
from scripts.bib_loader import Publication


def _pub(authorship, key="k", title="T", authors=("Lee, J.",)):
    """Minimal Publication record for exercising select_publications()."""
    return Publication(
        key=key,
        title=title,
        year=2020,
        type="article",
        authorship=authorship,
        authors=authors,
        venue="V",
        doi=None,
        raw={},
        category="research",
    )


def test_select_publications_comp_bio_returns_all_unselected():
    pubs = [_pub("first"), _pub("shared"), _pub("middle")]
    selected, is_selected = select_publications(pubs, "comp-bio")
    assert [p.authorship for p in selected] == ["first", "shared", "middle"]
    assert is_selected is False


def test_select_publications_bridge_keeps_first_and_shared_in_order():
    pubs = [_pub("first", key="a"), _pub("middle", key="b"), _pub("shared", key="c")]
    selected, is_selected = select_publications(pubs, "bridge")
    assert [p.key for p in selected] == ["a", "c"]  # middle dropped, order preserved
    assert is_selected is True


def test_select_publications_ds_ml_keeps_first_and_shared():
    pubs = [_pub("first"), _pub("middle"), _pub("shared")]
    selected, is_selected = select_publications(pubs, "ds-ml")
    assert [p.authorship for p in selected] == ["first", "shared"]
    assert is_selected is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pdf_publications.py -q`
Expected: FAIL — `ImportError: cannot import name 'select_publications' from 'pdf.build'`.

- [ ] **Step 3: Write minimal implementation**

In `pdf/build.py`, add this function directly after `_pdf_filename` (around line 64), before `prepare_data`:

```python
def select_publications(pubs: list, target: str) -> tuple[list, bool]:
    """Pick which publications the PDF shows for `target`.

    `comp-bio` shows the full list (is_selected=False); `bridge` and `ds-ml`
    show the first+shared subset (is_selected=True). Order is preserved from
    bib_loader. Depth is a PDF *rendering* choice — the web and plain-text
    renderers always show all publications — so this lives here, not in the
    shared content_loader.
    """
    if target == "comp-bio":
        return list(pubs), False
    subset = [p for p in pubs if p.authorship in ("first", "shared")]
    return subset, True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pdf_publications.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add pdf/build.py tests/test_pdf_publications.py
git commit -m "feat(pdf): add select_publications depth helper for #43"
```

---

## Task 2: Wire filtering + heading into `prepare_data` + labels (integration, TDD)

**Files:**
- Modify: `content/labels.yaml` (add two `sections` keys)
- Modify: `pdf/build.py` (`prepare_data`)
- Test: `tests/test_pdf_publications.py` (append integration tests)

- [ ] **Step 1: Write the failing tests**

First, add `prepare_data` to the existing import line at the top of `tests/test_pdf_publications.py` (the integration tests below use it):

```python
from pdf.build import prepare_data, select_publications
```

Then append these tests:

```python
def test_prepare_data_bridge_selects_nine_with_selected_heading(content_dir):
    result = prepare_data(content_dir, private_path=None, lang="en", target="bridge")
    assert len(result["publications"]) == 9
    assert result["publications_heading"] == "Publications (selected)"
    assert all(p["authorship"] in ("first", "shared") for p in result["publications"])


def test_prepare_data_comp_bio_selects_all_with_plain_heading(content_dir):
    result = prepare_data(content_dir, private_path=None, lang="en", target="comp-bio")
    assert len(result["publications"]) == 15
    assert result["publications_heading"] == "Publications"


def test_prepare_data_ds_ml_selects_nine(content_dir):
    result = prepare_data(content_dir, private_path=None, lang="en", target="ds-ml")
    assert len(result["publications"]) == 9
    assert result["publications_heading"] == "Publications (selected)"


def test_prepare_data_publications_heading_localized_de(content_dir):
    bridge = prepare_data(content_dir, private_path=None, lang="de", target="bridge")
    comp = prepare_data(content_dir, private_path=None, lang="de", target="comp-bio")
    assert bridge["publications_heading"] == "Publikationen (ausgewählte)"
    assert comp["publications_heading"] == "Publikationen"


def test_prepare_data_publication_entries_have_render_fields(content_dir):
    result = prepare_data(content_dir, private_path=None, lang="en", target="bridge")
    entry = result["publications"][0]
    for field in ("title", "authors", "year", "doi", "venue", "authorship"):
        assert field in entry
    assert isinstance(entry["authors"], list)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_pdf_publications.py -q -k prepare_data`
Expected: FAIL — `KeyError: 'publications_heading'` (the key isn't injected yet); the count assertions also fail because the full 15 still pass through.

- [ ] **Step 3a: Add the two heading langstrings to `content/labels.yaml`**

In the `sections:` block, immediately after the `awards:` line, add:

```yaml
  publications:          { en: "Publications",            de: "Publikationen" }
  publications_selected: { en: "Publications (selected)", de: "Publikationen (ausgewählte)" }
```

(The `sections` block is not constrained by `schema/cv.schema.json` and is not walked by `scripts/validate.py`, so adding keys is safe.)

- [ ] **Step 3b: Filter + inject in `prepare_data`**

In `pdf/build.py`, replace the body of `prepare_data` (currently lines ~73-76):

```python
    raw = load_content(content_dir, private_path=private_path, lang=lang, target=target)
    resolved = resolve_langstrings(raw, lang=lang)
    return _to_serializable(resolved)
```

with:

```python
    raw = load_content(content_dir, private_path=private_path, lang=lang, target=target)
    resolved = resolve_langstrings(raw, lang=lang)
    pubs, is_selected = select_publications(resolved.get("publications", []), target)
    resolved["publications"] = pubs
    sections = resolved["labels"]["sections"]
    resolved["publications_heading"] = (
        sections["publications_selected"] if is_selected else sections["publications"]
    )
    return _to_serializable(resolved)
```

(`resolve_langstrings` resolves the `labels` langmaps to plain strings but passes the `Publication` dataclasses through untouched, so `select_publications` still sees `.authorship`. The filter runs before `_to_serializable`.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_pdf_publications.py -q`
Expected: PASS (8 passed — 3 from Task 1 + 5 here).

Then confirm nothing else regressed:
Run: `just validate && python -m pytest -q`
Expected: validate clean; full suite green (was 178 collected; now 186).

- [ ] **Step 5: Commit**

```bash
git add pdf/build.py content/labels.yaml tests/test_pdf_publications.py
git commit -m "feat(pdf): inject variant-aware publications + heading into build data for #43"
```

---

## Task 3: `publications.typ` template + `cv.typ` wiring (renderer, TDD via PDF text)

**Files:**
- Create: `pdf/templates/publications.typ`
- Modify: `pdf/templates/cv.typ` (import + call between `selected_projects` and `awards`)
- Test: `tests/test_pdf_publications.py` (append the PDF text test)

This task is driven by an observable behavior — the heading text appearing in the compiled PDF, and middle-author-only titles being absent from a `bridge` build. The test is guarded so it skips when `typst` or `pdftotext` is missing; CI's 6-combo `build-pdf` matrix still proves the template compiles even where `pdftotext` is absent.

- [ ] **Step 1: Write the failing test**

First, add the stdlib + pytest imports this test needs at the TOP of `tests/test_pdf_publications.py`, above the existing `from pdf.build ...` line (stdlib group, then third-party, matching the import grouping in `tests/test_build_public.py`):

```python
"""Tests for the PDF publications section (issue #43)."""
import shutil
import subprocess
import sys

import pytest

from pdf.build import prepare_data, select_publications
from scripts.bib_loader import Publication
```

Then append the test:

```python
def _typst_available():
    return shutil.which("typst") is not None


def _pdftotext_available():
    return shutil.which("pdftotext") is not None


def _norm(s):
    return " ".join(s.split()).lower()


@pytest.mark.skipif(
    not (_typst_available() and _pdftotext_available()),
    reason="needs typst + pdftotext (poppler) to extract and assert PDF text",
)
def test_pdf_bridge_shows_heading_and_omits_middle_author_titles(repo_root, content_dir):
    from scripts.bib_loader import load_publications

    out = repo_root / "dist" / "cv-en.pdf"
    if out.exists():
        out.unlink()

    build = subprocess.run(
        [sys.executable, "-m", "pdf.build", "--lang", "en"],  # default target = bridge
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    assert build.returncode == 0, f"build failed:\n{build.stderr}"
    assert out.exists()

    text = subprocess.run(
        ["pdftotext", str(out), "-"], capture_output=True, text=True
    ).stdout
    norm = _norm(text)

    # Heading present (section-heading upper-cases it → "PUBLICATIONS (SELECTED)").
    assert "publications (selected)" in norm

    # A first-author title renders; a middle-author-only title does not (bridge = 9).
    pubs = load_publications(content_dir / "publications.bib")
    first = next(p for p in pubs if p.authorship == "first")
    middle = next(p for p in pubs if p.authorship == "middle")
    assert _norm(first.title) in norm
    assert _norm(middle.title) not in norm
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pdf_publications.py -q -k pdf_bridge`
Expected: FAIL — the build succeeds but has no publications section yet, so `assert "publications (selected)" in norm` fails (and the first-author title is absent).

- [ ] **Step 3: Create the template**

Create `pdf/templates/publications.typ`:

```typst
#import "../styles.typ": *

// Publications section. `pubs` is the already-filtered list (depth resolved in
// pdf/build.py); `heading` is the already lang+variant-resolved string;
// `family` is the candidate's surname, used to bold their name in author lists.
#let publications(pubs, heading, family) = {
  if pubs.len() == 0 { return }
  section-heading(heading)

  for (i, p) in pubs.enumerate() {
    // Line 1 — authors · year. The candidate (surname match) is bold; the
    // BibTeX "others" token renders as italic "et al.".
    for (j, a) in p.authors.enumerate() {
      if j > 0 { ", " }
      if a == "others" {
        emph[et al.]
      } else if a.starts-with(family + ",") {
        text(weight: 600)[#a]
      } else {
        a
      }
    }
    [ · #str(p.year)]
    linebreak()

    // Line 2 — title. DOI link in accent colour when present; plain otherwise.
    if p.doi != none {
      link("https://doi.org/" + p.doi)[#text(fill: accent)[#p.title]]
    } else {
      p.title
    }

    // Line 3 — venue (muted, small), when present.
    if p.venue != none {
      linebreak()
      text(size: size-small, fill: muted)[#p.venue]
    }

    if i + 1 < pubs.len() { v(space-paragraph) }
  }
}
```

- [ ] **Step 4: Wire it into `cv.typ`**

In `pdf/templates/cv.typ`, add the import after the `selected_projects` import (line 5):

```typst
#import "selected_projects.typ": selected_projects
#import "publications.typ": publications
#import "awards.typ": awards
```

Then in the main-column `block(...)` (currently lines 52-57), add the call between `selected_projects(...)` and `awards(...)`:

```typst
  block(width: 100%, {
    profile(data.profile, data.labels)
    experience(data.experience, data.labels, lang)
    selected_projects(data.selected_projects, data.labels)
    publications(data.publications, data.publications_heading, data.personal.name.family)
    awards(data.awards, data.labels)
  }),
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_pdf_publications.py -q -k pdf_bridge`
Expected: PASS.

- [ ] **Step 6: Compile every PDF matrix combo (catch Typst errors CI would catch)**

Run:

```bash
for lang in en de; do for t in bridge comp-bio ds-ml; do \
  python -m pdf.build --lang $lang --target $t >/dev/null 2>&1 \
    && echo "OK $lang $t" || echo "FAIL $lang $t"; done; done
```

Expected: all 6 print `OK`.

- [ ] **Step 7: Full suite + lint, then commit**

Run: `just validate && python -m pytest -q && just lint`
Expected: all green (187 tests: 178 baseline + 9 new).

```bash
git add pdf/templates/publications.typ pdf/templates/cv.typ tests/test_pdf_publications.py
git commit -m "feat(pdf): render publications section between projects and awards for #43"
```

---

## Task 4: Documentation checkpoint (CLAUDE.md)

Per repo convention, every plan ends by refreshing `CLAUDE.md`. Issue #43 is a **backlog item, not a phase** — the Phasing table stays 0–9 and must NOT gain a row (recorded in project memory). The new `pdf/templates/publications.typ` sits under the `pdf/` entry, which the Layout section describes at directory granularity ("Typst PDF renderer"), so no per-file edit is needed either.

- [ ] **Step 1: Verify CLAUDE.md needs no change**

Open `CLAUDE.md`. Confirm:
- The Phasing table requires no new row (backlog item, not a phase).
- The Layout section's `pdf/` line still accurately describes the renderer (directory-level; no per-template listing).

Expected outcome: **no edit**. If — and only if — some genuine drift is found (e.g. a convention this work changed), fix it and commit with `docs: update CLAUDE.md for #43`. Otherwise this task is a no-op and no commit is made.

---

## Self-Review

**1. Spec coverage** — every spec section maps to a task:
- Selected subset = first+shared (9); comp-bio = full 15 → Task 1 (`select_publications`) + Task 2 (asserted counts).
- Title-as-DOI-link compact layout, candidate bold, `others`→*et al.*, venue muted → Task 3 (`publications.typ`).
- Depth resolved in Python build path, not `content_loader`; Typst stays dumb → Task 1/2 architecture; Task 3 passes only resolved data + `family`.
- Heading full vs selected, EN+DE → Task 2 (labels + injection, asserted in all 4 lang×selection combos).
- Placement between Selected Projects and Awards → Task 3 Step 4.
- Empty-list guard, no-DOI plain text, `others` token → Task 3 template (`if pubs.len() == 0 { return }`, `if p.doi != none`, `if a == "others"`).
- Testing items 1/2/3 → Tasks 1 (unit), 2 (integration), 3 (best-effort PDF text + 6-combo compile).

**2. Placeholder scan** — no `TBD`/`TODO`/"add appropriate…"; every code step shows complete code and exact commands.

**3. Type/name consistency** — `select_publications(pubs, target) -> (list, bool)` defined in Task 1, imported and called identically in Task 2 and its tests. `prepare_data(content_dir, *, private_path, lang, target="bridge")` matches the real signature. Typst `publications(pubs, heading, family)` defined in Task 3 Step 3 and called with the matching three arguments in Step 4. `data.publications` / `data.publications_heading` / `data.personal.name.family` match the keys injected in Task 2 and the existing data shape. Author-string surname match (`"Lee,"`) and `"others"` token verified against live data.

---

## Execution Handoff

Plan complete. Recommended: **subagent-driven development** (fresh subagent per task with review checkpoints), per the repo's standard workflow. Tasks are sequential (Task 2 imports Task 1's helper; Task 3 depends on Task 2's injected data).
