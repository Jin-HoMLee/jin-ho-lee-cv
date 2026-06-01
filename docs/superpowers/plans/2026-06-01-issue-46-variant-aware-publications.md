# Variant-aware Publication Depth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the publications section vary by positioning target — `comp-bio` keeps the full per-paper list; `bridge`/`ds-ml` show a derived, honest one-line aggregate + ORCID pointer — across the PDF, plain-text, and web renderers (machine formats unchanged).

**Architecture:** A new shared module `scripts/publications.py` owns the policy (`publication_mode`) and the derived aggregate (`publication_summary`, `format_publication_summary`). Counts/span are derived from `bib_loader`; the prose lives in `content/labels.yaml`. PDF/text branch in Python; the web renders both an aggregate block and a `hidden` full block and the client-side switcher toggles them by target name. Supersedes #43's "Selected Publications" subset for the industry variants.

**Tech Stack:** Python 3 (pytest, ruff), Typst, Astro/TypeScript. Commands: `just validate`, `just test`, `just lint`, `just web-build`.

**Spec:** `docs/superpowers/specs/2026-06-01-issue-46-variant-aware-publications-design.md`

**Live-data facts (verified against `content/publications.bib`):** 15 entries = 10 journal articles + 2 book chapters (1 research 2021, 1 applied 2025) + 3 conference contributions. Peer-reviewed (research articles+chapters) = **11** → 2 first-author, 3 shared-first, 6 co-author. Conference contributions = **3** (all first-author). Research-body span = **2017–2021**. ORCID = `https://orcid.org/0009-0001-8784-1771` at `personal.links.orcid`.

---

## File Structure

| File | Responsibility |
|---|---|
| `scripts/publications.py` (**new**) | `publication_mode(target)`, `PublicationSummary`, `publication_summary(pubs)`, `format_publication_summary(template, pubs)` — shared by PDF/text/web; machine formats do not import it. |
| `tests/test_publications.py` (**new**) | Unit + live-bib tests for the module. |
| `content/labels.yaml` | +`publications` block (summary template + pointer label); −`sections.publications_selected`. Not schema-validated. |
| `pdf/build.py` | −`select_publications`; `prepare_data` branches on `publication_mode`, injects `publications_mode`/`publications_summary`/`publications_pointer` + plain `publications_heading`. |
| `pdf/templates/publications.typ` | Branch: aggregate (summary + ORCID link) vs full list (the #43 loop). New signature `publications(data)`. |
| `pdf/templates/cv.typ` | Call `publications(data)`. |
| `tests/test_pdf_publications.py` | Reworked for mode/aggregate (drops `select_publications`). |
| `scripts/render_text.py` | Per-target aggregate branch. |
| `tests/test_render_text.py` | +aggregate/full assertions. |
| `scripts/render_web_data.py` | Inject `publications_aggregate` into content JSON. |
| `tests/test_render_web_data.py` | Update exact key-set; +aggregate assertions. |
| `web/src/components/PublicationsList.astro` | Charts always; aggregate block (default-visible) + `hidden` full block. |
| `web/src/components/TargetSwitcher.astro` | `apply()` toggles the two blocks by `target === "comp-bio"`. |
| `web/src/pages/index.astro`, `web/src/pages/de/index.astro` | Pass `aggregate` + `orcid` props. |
| `web/src/types/content.ts` | `ContentData.publications_aggregate`. |
| `CLAUDE.md` | Add `scripts/publications.py` to Layout; phasing table unchanged. |

---

## Task 1: Shared publication-policy module

**Files:**
- Create: `scripts/publications.py`
- Test: `tests/test_publications.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_publications.py`:

```python
"""Tests for scripts/publications.py — variant publication policy + aggregate."""
from pathlib import Path

from scripts.bib_loader import Publication
from scripts.bib_loader import load_publications
from scripts.publications import (
    format_publication_summary,
    publication_mode,
    publication_summary,
)

CONTENT_DIR = Path(__file__).resolve().parent.parent / "content"


def _pub(authorship="first", type="article", category="research", year=2020, key="k"):
    return Publication(
        key=key, title="T", year=year, type=type, authorship=authorship,
        authors=("Lee, J.",), venue="V", doi=None, raw={}, category=category,
    )


def test_publication_mode_comp_bio_is_full():
    assert publication_mode("comp-bio") == "full"


def test_publication_mode_bridge_and_ds_ml_are_aggregate():
    assert publication_mode("bridge") == "aggregate"
    assert publication_mode("ds-ml") == "aggregate"


def test_summary_peer_reviewed_excludes_conference_and_applied():
    pubs = [
        _pub(type="article", authorship="first", year=2018),
        _pub(type="article", authorship="middle", year=2019),
        _pub(type="book-chapter", authorship="first", year=2020),     # peer-reviewed
        _pub(type="conference", authorship="first", year=2021),       # NOT peer-reviewed
        _pub(type="book-chapter", authorship="first", category="applied", year=2025),  # excluded
    ]
    s = publication_summary(pubs)
    assert s.peer_reviewed == 3        # 2 articles + 1 research book chapter
    assert s.conferences == 1
    assert s.pr_first == 2             # article first + chapter first
    assert s.pr_shared == 0
    assert s.pr_coauthor == 1          # the middle article
    assert (s.year_start, s.year_end) == (2018, 2021)  # research only; excludes 2025


def test_summary_folds_coauthor_buckets():
    pubs = [
        _pub(type="article", authorship="middle"),
        _pub(type="article", authorship="last"),
        _pub(type="article", authorship="corresponding"),
    ]
    assert publication_summary(pubs).pr_coauthor == 3


def test_format_fills_placeholders_with_en_dash_span():
    template = "{peer_reviewed} PR ({pr_first}/{pr_shared}/{pr_coauthor}) + {conferences} conf, {span}."
    pubs = [
        _pub(type="article", authorship="first", year=2017),
        _pub(type="conference", authorship="first", year=2019),
    ]
    assert format_publication_summary(template, pubs) == "1 PR (1/0/0) + 1 conf, 2017–2019."


def test_live_bib_aggregate_numbers():
    pubs = load_publications(CONTENT_DIR / "publications.bib")
    s = publication_summary(pubs)
    assert (s.peer_reviewed, s.pr_first, s.pr_shared, s.pr_coauthor, s.conferences) == (11, 2, 3, 6, 3)
    assert (s.year_start, s.year_end) == (2017, 2021)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_publications.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.publications'`.

- [ ] **Step 3: Implement the module**

Create `scripts/publications.py`:

```python
"""Variant-aware publication rendering policy + aggregate summary.

Shared by the PDF (pdf/build.py), website (scripts/render_web_data.py) and
plain-text (scripts/render_text.py) renderers so all three agree on (a) which
targets show the full per-paper list vs. a one-line aggregate, and (b) the exact
wording of that aggregate. The machine formats (JSON Resume, JSON-LD) bypass this
and always emit the full structured list.
"""
from __future__ import annotations

from dataclasses import dataclass

from scripts.bib_loader import Publication, authorship_counts  # noqa: F401  (re-export anchor)

_PEER_REVIEWED_TYPES = ("article", "book-chapter")  # conference contributions are not
_COAUTHOR = ("middle", "last", "corresponding")      # everything that isn't first/shared
EN_DASH = "–"


def publication_mode(target: str) -> str:
    """Return "full" for the academic variant, "aggregate" for everyone else.

    comp-bio foregrounds the verbatim list; bridge/ds-ml collapse it to a derived
    summary line + ORCID pointer (de-emphasize-don't-delete).
    """
    return "full" if target == "comp-bio" else "aggregate"


@dataclass(frozen=True)
class PublicationSummary:
    peer_reviewed: int   # research articles + book chapters
    pr_first: int        # …of which first-author
    pr_shared: int       # …shared-first
    pr_coauthor: int     # …co-author (middle/last/corresponding)
    conferences: int     # research conference contributions (all first-author)
    year_start: int
    year_end: int


def publication_summary(pubs: list[Publication]) -> PublicationSummary:
    """Derive the honest, type-segmented aggregate from the research publications.

    Only ``category == "research"`` entries are summarized (the lone applied piece
    is off-domain and excluded). Peer-reviewed = research articles + book chapters;
    conference contributions are counted separately. ``pr_coauthor`` folds
    middle/last/corresponding. The span is the research-body min/max year.
    """
    research = [p for p in pubs if p.category == "research"]
    peer = [p for p in research if p.type in _PEER_REVIEWED_TYPES]
    years = [p.year for p in research] or [p.year for p in pubs]
    return PublicationSummary(
        peer_reviewed=len(peer),
        pr_first=sum(1 for p in peer if p.authorship == "first"),
        pr_shared=sum(1 for p in peer if p.authorship == "shared"),
        pr_coauthor=sum(1 for p in peer if p.authorship in _COAUTHOR),
        conferences=sum(1 for p in research if p.type == "conference"),
        year_start=min(years),
        year_end=max(years),
    )


def format_publication_summary(template: str, pubs: list[Publication]) -> str:
    """Fill a resolved (single-language) label template with derived figures.

    The template owns the prose + per-language word order; only the derived counts
    and the span are substituted, so nothing is hardcoded.
    """
    s = publication_summary(pubs)
    span = f"{s.year_start}{EN_DASH}{s.year_end}"
    return template.format(
        peer_reviewed=s.peer_reviewed, pr_first=s.pr_first, pr_shared=s.pr_shared,
        pr_coauthor=s.pr_coauthor, conferences=s.conferences, span=span,
    )
```

> Note on the `authorship_counts` import: it is re-exported only to anchor the module to `bib_loader`. If ruff flags F401, drop `authorship_counts` from the import (keep `Publication`) rather than adding `# noqa` — `Publication` is used in the type hint.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_publications.py -q`
Expected: PASS (7 tests).

- [ ] **Step 5: Lint**

Run: `just lint`
Expected: no errors in `scripts/publications.py` / `tests/test_publications.py`. (If F401 fires on `authorship_counts`, remove it from the import and re-run.)

- [ ] **Step 6: Commit**

```bash
git add scripts/publications.py tests/test_publications.py
git commit -m "feat(pubs): #46 shared publication policy + derived aggregate module"
```

---

## Task 2: Add the aggregate label block

**Files:**
- Modify: `content/labels.yaml`

`labels.yaml` is not schema-validated (`scripts/validate.py` `_FILE_RULES` omits it). Add the new block now; the old `publications_selected` key is removed in Task 3 (its last consumer is `pdf/build.py`).

- [ ] **Step 1: Add the `publications` block**

In `content/labels.yaml`, after the `misc:` block (end of file), append:

```yaml

publications:
  summary:
    en: "{peer_reviewed} peer-reviewed publications ({pr_first} first-author, {pr_shared} shared-first, {pr_coauthor} co-author) and {conferences} first-author conference contributions, {span}, in radiation biophysics & super-resolution DNA-repair imaging."
    de: "{peer_reviewed} begutachtete Publikationen ({pr_first} als Erstautor, {pr_shared} geteilte Erstautorenschaft, {pr_coauthor} als Co-Autor) sowie {conferences} Konferenzbeiträge als Erstautor, {span}, in Strahlenbiophysik & Super-Resolution-Bildgebung der DNA-Reparatur."
  full_list_pointer:
    en: "Full list & metrics:"
    de: "Vollständige Liste:"
```

- [ ] **Step 2: Verify it resolves and nothing breaks**

Run:
```bash
python -c "from pathlib import Path; from scripts.content_loader import load_content; from scripts.langstring import resolve_langstrings; r = resolve_langstrings(load_content(Path('content'), private_path=None, lang='en', target='bridge'), lang='en'); print(repr(r['labels']['publications']))"
```
Expected: prints `{'summary': '{peer_reviewed} peer-reviewed publications …', 'full_list_pointer': 'Full list & metrics:'}` — the langmaps resolved to plain EN strings, the `{…}` placeholders intact.

- [ ] **Step 3: Validate + full suite still green**

Run: `just validate && just test`
Expected: PASS (no test depends on the new block yet; adding it is additive).

- [ ] **Step 4: Commit**

```bash
git add content/labels.yaml
git commit -m "feat(pubs): #46 add publications aggregate label template (en/de)"
```

---

## Task 3: PDF — aggregate for industry variants

**Files:**
- Modify: `pdf/build.py` (remove `select_publications`; rewrite `prepare_data` publication logic)
- Modify: `content/labels.yaml` (remove `sections.publications_selected`)
- Rewrite: `pdf/templates/publications.typ`
- Modify: `pdf/templates/cv.typ:57`
- Rewrite: `tests/test_pdf_publications.py`

This is one cohesive slice so commits stay green (changing `build.py` without the Typst + test rework would leave failing tests).

- [ ] **Step 1: Rewrite the PDF data + Typst tests (failing)**

Replace the entire contents of `tests/test_pdf_publications.py` with:

```python
"""Tests for the PDF publications section (issues #43, #46)."""
import shutil
import subprocess
import sys

import pytest

from pdf.build import prepare_data
from scripts.bib_loader import load_publications


def test_prepare_data_comp_bio_full_list(content_dir):
    all_pubs = load_publications(content_dir / "publications.bib")
    result = prepare_data(content_dir, private_path=None, lang="en", target="comp-bio")
    assert result["publications_mode"] == "full"
    assert [p["key"] for p in result["publications"]] == [p.key for p in all_pubs]
    assert result["publications_heading"] == "Publications"
    assert result["publications_summary"] is None
    assert result["publications_pointer"] is None


def test_prepare_data_bridge_aggregate(content_dir):
    result = prepare_data(content_dir, private_path=None, lang="en", target="bridge")
    assert result["publications_mode"] == "aggregate"
    assert result["publications_heading"] == "Publications"
    assert "11 peer-reviewed publications" in result["publications_summary"]
    assert "3 first-author conference contributions" in result["publications_summary"]
    assert result["publications_pointer"] == "Full list & metrics:"


def test_prepare_data_ds_ml_aggregate(content_dir):
    result = prepare_data(content_dir, private_path=None, lang="en", target="ds-ml")
    assert result["publications_mode"] == "aggregate"
    assert result["publications_summary"] is not None


def test_prepare_data_de_aggregate_localized(content_dir):
    result = prepare_data(content_dir, private_path=None, lang="de", target="bridge")
    assert result["publications_heading"] == "Publikationen"
    assert "begutachtete Publikationen" in result["publications_summary"]
    assert result["publications_pointer"] == "Vollständige Liste:"


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
def test_pdf_bridge_aggregate_vs_comp_bio_full(repo_root, content_dir):
    pubs = load_publications(content_dir / "publications.bib")
    middle = next(p for p in pubs if p.authorship == "middle")

    def build(target, name):
        out = repo_root / "dist" / name
        if out.exists():
            out.unlink()
        r = subprocess.run(
            [sys.executable, "-m", "pdf.build", "--lang", "en", "--target", target],
            cwd=repo_root, capture_output=True, text=True,
        )
        assert r.returncode == 0, f"build failed:\n{r.stderr}"
        assert out.exists()
        return subprocess.run(["pdftotext", str(out), "-"], capture_output=True, text=True).stdout

    bridge = _norm(build("bridge", "cv-en.pdf"))
    compbio = _norm(build("comp-bio", "cv-en-comp-bio.pdf"))

    # bridge → aggregate: ORCID pointer present, the middle-author paper title absent.
    assert "orcid.org/0009-0001-8784-1771" in bridge.replace(" ", "")
    assert _norm(middle.title) not in bridge
    # comp-bio → full list: the middle-author paper title present.
    assert _norm(middle.title) in compbio
```

- [ ] **Step 2: Run the data-layer tests to verify they fail**

Run: `python -m pytest tests/test_pdf_publications.py -q -k "prepare_data"`
Expected: FAIL — `prepare_data` still produces the #43 shape (`publications_mode` KeyError / `publications_heading == "Selected Publications"`).

- [ ] **Step 3: Rewrite `prepare_data` in `pdf/build.py`**

In `pdf/build.py`: delete the `select_publications` function entirely. Replace the import line `from scripts.content_loader import TARGETS, load_content` is unchanged; add `from scripts.publications import publication_mode, format_publication_summary`. Replace the body of `prepare_data` (keep its signature + docstring intent) with:

```python
def prepare_data(
    content_dir: Path,
    *,
    private_path: Path | None,
    lang: str,
    target: str = "bridge",
) -> dict[str, Any]:
    """Load content tree, merge private overlay, resolve langstrings, return flat dict.

    Applies variant-aware publication depth (PDF-only rendering choice — web/text
    decide independently): comp-bio renders the full verbatim list, bridge/ds-ml a
    derived aggregate summary + ORCID pointer. Injects ``publications_mode`` and,
    for the aggregate, ``publications_summary`` / ``publications_pointer``.
    """
    raw = load_content(content_dir, private_path=private_path, lang=lang, target=target)
    resolved = resolve_langstrings(raw, lang=lang)
    sections = resolved["labels"]["sections"]
    resolved["publications_heading"] = sections["publications"]
    mode = publication_mode(target)
    resolved["publications_mode"] = mode
    if mode == "aggregate":
        pub_labels = resolved["labels"]["publications"]
        resolved["publications_summary"] = format_publication_summary(
            pub_labels["summary"], resolved.get("publications", [])
        )
        resolved["publications_pointer"] = pub_labels["full_list_pointer"]
    else:
        resolved["publications_summary"] = None
        resolved["publications_pointer"] = None
    return _to_serializable(resolved)
```

- [ ] **Step 4: Remove the dead label**

In `content/labels.yaml`, delete the line:
```yaml
  publications_selected: { en: "Selected Publications", de: "Ausgewählte Publikationen" }
```
(Leave `publications: { en: "Publications", de: "Publikationen" }`.)

- [ ] **Step 5: Run data-layer tests to verify they pass**

Run: `python -m pytest tests/test_pdf_publications.py -q -k "prepare_data"`
Expected: PASS (4 tests).

- [ ] **Step 6: Rewrite the Typst renderer**

Replace the entire contents of `pdf/templates/publications.typ` with:

```typst
#import "../styles.typ": *

// Publications section. Reads everything from the prepared `data` object
// (mirrors `sidebar(data, …)`). `data.publications_mode` is "full" (comp-bio →
// verbatim per-paper list) or "aggregate" (bridge / ds-ml → one-line summary +
// ORCID pointer). Depth is resolved in pdf/build.py.
#let publications(data) = {
  section-heading(data.publications_heading)

  if data.publications_mode == "aggregate" {
    // Derived summary sentence (counts + span filled in Python) + ORCID pointer.
    [#data.publications_summary]
    linebreak()
    let orcid = data.personal.links.orcid
    let shown = orcid.replace("https://", "").replace("http://", "")
    text(size: size-small, fill: muted)[#data.publications_pointer #link(orcid)[#text(fill: accent)[#shown]]]
  } else {
    // Full verbatim list (comp-bio) — the #43 per-paper rendering.
    let family = data.personal.name.family
    for (i, p) in data.publications.enumerate() {
      // Line 1 — authors · year. The candidate's surname (text before the comma)
      // is bolded; the BibTeX "others" token renders as italic "et al.".
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
      if p.authors.len() > 0 { [ · ] }
      [#str(p.year)]
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

      if i + 1 < data.publications.len() { v(space-paragraph) }
    }
  }
}
```

- [ ] **Step 7: Update the Typst call site**

In `pdf/templates/cv.typ`, change line 57 from:
```typst
    publications(data.publications, data.publications_heading, data.personal.name.family)
```
to:
```typst
    publications(data)
```

- [ ] **Step 8: Run the full PDF test file**

Run: `python -m pytest tests/test_pdf_publications.py -q`
Expected: PASS (4 data tests + 1 Typst test; the Typst test SKIPS if typst/pdftotext are absent — if present it must PASS).

- [ ] **Step 9: Eyeball the PDFs (if typst is installed)**

Run:
```bash
just build && just build-de
python -m pdf.build --lang en --target comp-bio
```
Open `dist/cv-en.pdf` (should show the aggregate line + ORCID under "PUBLICATIONS") and `dist/cv-en-comp-bio.pdf` (full list). Confirm no Typst warnings about `replace`/`link`.

- [ ] **Step 10: Commit**

```bash
git add pdf/build.py pdf/templates/publications.typ pdf/templates/cv.typ content/labels.yaml tests/test_pdf_publications.py
git commit -m "feat(pdf): #46 aggregate publications for bridge/ds-ml; full list for comp-bio"
```

---

## Task 4: Plain text — aggregate for industry variants

**Files:**
- Modify: `scripts/render_text.py`
- Modify: `tests/test_render_text.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_render_text.py` (the file already has `REPO_ROOT` and imports `render`):

```python
from scripts.bib_loader import load_publications

CONTENT_DIR = REPO_ROOT / "content"


def test_publications_aggregate_for_bridge_en():
    text = render(lang="en", target="bridge")
    assert "11 peer-reviewed publications" in text
    assert "Full list & metrics: https://orcid.org/0009-0001-8784-1771" in text


def test_publications_aggregate_for_bridge_de():
    text = render(lang="de", target="bridge")
    assert "begutachtete Publikationen" in text
    assert "Vollständige Liste: https://orcid.org/0009-0001-8784-1771" in text


def test_publications_full_list_for_comp_bio():
    pubs = load_publications(CONTENT_DIR / "publications.bib")
    middle = next(p for p in pubs if p.authorship == "middle")
    full = render(lang="en", target="comp-bio")
    bridge = render(lang="en", target="bridge")
    assert middle.title in full          # verbatim list present
    assert middle.title not in bridge    # aggregate omits per-paper titles
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_render_text.py -q -k "aggregate or full_list"`
Expected: FAIL — `render()` ignores `target` for publications today (always full list), so the aggregate strings are absent.

- [ ] **Step 3: Implement the branch in `scripts/render_text.py`**

Add the import near the other `scripts.*` imports (after the `from scripts.content_loader import …` line):
```python
from scripts.publications import publication_mode, format_publication_summary
```

Add this helper directly after the existing `_publications` function (around line 137):
```python
def _publications_aggregate(content: dict, pubs: list[Publication]) -> str:
    """One-line derived summary + ORCID pointer (full URL, matching the DOI style)."""
    pub_labels = content["labels"]["publications"]
    summary = format_publication_summary(pub_labels["summary"], pubs)
    orcid = content["personal"]["links"]["orcid"]
    return f"{_wrap(summary)}\n{pub_labels['full_list_pointer']} {orcid}"
```

In `render()`, replace the publications section line. Find:
```python
        _section(L["publications"][lang],      _publications(pubs)),
```
and change the `_publications(pubs)` argument by computing the body first. Just above the `sections = [` list, add:
```python
    pub_body = (
        _publications(pubs)
        if publication_mode(target) == "full"
        else _publications_aggregate(content, pubs)
    )
```
then change that line to:
```python
        _section(L["publications"][lang],      pub_body),
```

- [ ] **Step 4: Run to verify they pass**

Run: `python -m pytest tests/test_render_text.py -q`
Expected: PASS (all, including the existing ones).

- [ ] **Step 5: Lint + eyeball**

Run: `just lint && just build-text`
Then inspect `dist/cv-en.txt` (PUBLICATIONS shows the aggregate + ORCID) and run `python -m scripts.render_text --lang en --target comp-bio --output /tmp/cv-en-comp-bio.txt` to confirm the full list renders for comp-bio.

- [ ] **Step 6: Commit**

```bash
git add scripts/render_text.py tests/test_render_text.py
git commit -m "feat(text): #46 aggregate publications for bridge/ds-ml; full list for comp-bio"
```

---

## Task 5: Web data — inject the aggregate

**Files:**
- Modify: `scripts/render_web_data.py`
- Modify: `tests/test_render_web_data.py`

- [ ] **Step 1: Update the failing tests**

In `tests/test_render_web_data.py`, edit `test_round_trip_structural_keys`'s `expected_keys` set to add `"publications_aggregate"`:
```python
    expected_keys = {
        "personal", "profile", "skills", "education", "experience",
        "projects", "selected_projects", "languages", "volunteer",
        "publications", "labels", "awards", "publications_aggregate",
    }
```
Then add a new test:
```python
def test_publications_aggregate_present(rendered):
    en, de = rendered
    assert "11 peer-reviewed publications" in en["publications_aggregate"]["summary"]
    assert en["publications_aggregate"]["pointer"] == "Full list & metrics:"
    assert "begutachtete Publikationen" in de["publications_aggregate"]["summary"]
    assert de["publications_aggregate"]["pointer"] == "Vollständige Liste:"
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_render_web_data.py -q -k "structural_keys or aggregate_present"`
Expected: FAIL — `publications_aggregate` is not yet in the dumped JSON (key-set mismatch + missing key).

- [ ] **Step 3: Implement the injection in `scripts/render_web_data.py`**

Add the import after the existing `from scripts.bib_loader import Publication`:
```python
from scripts.publications import format_publication_summary
```

In `render_web_data()`, inside the `for lang in LANGS:` loop, after `bridge_resolved = resolve_langstrings(...)` and **before** `_dump(bridge_resolved, f"content.{lang}.json")`, insert:
```python
        pub_labels = bridge_resolved["labels"]["publications"]
        bridge_resolved["publications_aggregate"] = {
            "summary": format_publication_summary(pub_labels["summary"], bridge_resolved["publications"]),
            "pointer": pub_labels["full_list_pointer"],
        }
```

- [ ] **Step 4: Run to verify they pass**

Run: `python -m pytest tests/test_render_web_data.py tests/test_render_web_data_variants.py -q`
Expected: PASS — including the unchanged variants regression guard (we did not touch `variants.json`).

- [ ] **Step 5: Commit**

```bash
git add scripts/render_web_data.py tests/test_render_web_data.py
git commit -m "feat(web-data): #46 inject publications_aggregate into content JSON"
```

---

## Task 6: Web components — variant-aware rendering

**Files:**
- Modify: `web/src/types/content.ts`
- Modify: `web/src/components/PublicationsList.astro`
- Modify: `web/src/components/TargetSwitcher.astro`
- Modify: `web/src/pages/index.astro:33`, `web/src/pages/de/index.astro` (the `PublicationsList` line)

Astro components have no pytest; the gate is `just web-build` (type-checks props/types) + a Playwright toggle check.

- [ ] **Step 1: Extend the `ContentData` type**

In `web/src/types/content.ts`, add to the `ContentData` interface (after the `publications: Publication[];` line):
```typescript
  publications_aggregate: { summary: string; pointer: string };
```

- [ ] **Step 2: Restructure `PublicationsList.astro`**

Replace the contents of `web/src/components/PublicationsList.astro` with (charts unchanged; the grouped list moves into a `hidden` full block, and an aggregate block is added before it):

```astro
---
import type { Publication, PublicationType, Lang } from "../types/content";
import PublicationsChart from "./PublicationsChart.astro";
import PublicationsCumulative from "./PublicationsCumulative.astro";

interface Props {
  publications: Publication[];
  aggregate: { summary: string; pointer: string };
  orcid: string;
  lang: Lang;
}

const { publications, aggregate, orcid, lang } = Astro.props;
const orcidDisplay = orcid.replace(/^https?:\/\//, "");

const sectionLabel = { en: "Publications", de: "Publikationen" };
const typeLabel: Record<PublicationType, { en: string; de: string }> = {
  "article":      { en: "Peer-reviewed articles", de: "Peer-Review-Artikel" },
  "book-chapter": { en: "Book chapters",          de: "Buchkapitel" },
  "conference":   { en: "Conference contributions", de: "Konferenzbeiträge" },
  "book":         { en: "Books",                  de: "Bücher" },
};
const typeOrder: PublicationType[] = ["article", "book-chapter", "conference", "book"];

const grouped: Record<PublicationType, Publication[]> = {
  "article": [],
  "book-chapter": [],
  "conference": [],
  "book": [],
};
for (const p of publications) {
  grouped[p.type].push(p);
}
for (const t of typeOrder) {
  grouped[t].sort((a, b) => b.year - a.year);
}

/** Render an author list, bolding Lee, J. (input is trusted — from publications.bib). */
function renderAuthors(authors: string[]): string {
  return authors
    .map((a) => /\bLee, ?J/.test(a) ? `<strong>${a}</strong>` : a)
    .join(", ");
}
---
<section id="publications" class="py-6">
  <h2 class="eyebrow mb-4">
    {sectionLabel[lang]}
  </h2>
  <div class="flex flex-col gap-2 md:flex-row md:items-center md:gap-8">
    <div class="shrink-0">
      <PublicationsChart publications={publications} lang={lang} />
    </div>
    <div class="flex-1 min-w-0">
      <PublicationsCumulative publications={publications} lang={lang} />
    </div>
  </div>

  <!-- Aggregate (bridge / ds-ml) — visible by default; charts above stay for every target. -->
  <div data-cv-pub="aggregate" class="mt-4 text-sm text-[var(--muted)]">
    <p>{aggregate.summary}</p>
    <p class="mt-1 text-xs text-[var(--faint)]">
      {aggregate.pointer}{" "}
      <a
        href={orcid}
        target="_blank"
        rel="noopener noreferrer"
        class="underline decoration-dotted underline-offset-2 hover:text-[var(--text)]"
      >{orcidDisplay}</a>
    </p>
  </div>

  <!-- Full verbatim list (comp-bio) — hidden by default; the switcher reveals it. -->
  <div data-cv-pub="full" hidden class="mt-4">
    {typeOrder.map((t) => grouped[t].length > 0 && (
      <div class="mb-5">
        <h3 class="mb-2 text-sm font-semibold text-[var(--text)]">{typeLabel[t][lang]}</h3>
        <ol class="space-y-2 text-sm text-[var(--muted)]">
          {grouped[t].map((p) => (
            <li>
              <p class="font-medium text-[var(--text)]">{p.title}</p>
              <p set:html={renderAuthors(p.authors)} class="text-xs text-[var(--muted)]" />
              <p class="text-xs text-[var(--faint)]">
                {p.venue ? `${p.venue} · ` : ""}{p.year} · {p.authorship}
                {p.doi && (
                  <> · <a
                    href={`https://doi.org/${p.doi}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    class="underline decoration-dotted underline-offset-2 hover:text-[var(--text)]"
                  >{p.doi}</a></>
                )}
              </p>
            </li>
          ))}
        </ol>
      </div>
    ))}
  </div>
</section>
```

- [ ] **Step 3: Toggle the blocks in `TargetSwitcher.astro`**

In `web/src/components/TargetSwitcher.astro`, inside the `apply(target)` function, after the existing `for (const [field, jsonKey] of Object.entries(FIELDS)) { … }` loop and before the `for (const btn of buttons) {` aria-pressed loop, add:

```javascript
      // Publications depth: comp-bio shows the verbatim list; bridge/ds-ml the
      // aggregate. Charts (rendered outside both blocks) stay visible for all.
      const showFull = target === "comp-bio";
      const fullBlock = document.querySelector('[data-cv-pub="full"]');
      const aggBlock = document.querySelector('[data-cv-pub="aggregate"]');
      if (fullBlock) fullBlock.hidden = !showFull;
      if (aggBlock) aggBlock.hidden = showFull;
```

(No `Variant` interface change — depth is derived from `target`, not the variants payload.)

- [ ] **Step 4: Pass the new props in both pages**

In `web/src/pages/index.astro`, change line 33 from:
```astro
      <PublicationsList publications={data.publications} lang="en" />
```
to:
```astro
      <PublicationsList publications={data.publications} aggregate={data.publications_aggregate} orcid={data.personal.links.orcid} lang="en" />
```
In `web/src/pages/de/index.astro`, make the same change to its `PublicationsList` line (with `lang="de"`).

- [ ] **Step 5: Build (regenerates data + type-checks)**

Run: `just web-build`
Expected: SUCCESS. Astro type-checks the new `aggregate`/`orcid` props against `Props` and the `ContentData` type; a mismatch fails the build. If it complains that `content.{lang}.json` lacks `publications_aggregate`, the data wasn't regenerated — `just web-build` runs `render_web_data` first; confirm Task 5 is committed.

- [ ] **Step 6: Behaviour check with Playwright**

Per the repo's web-verify convention (Playwright via the npx cache module + system Chrome over `astro preview`):
```bash
cd web && npm run build && npm run preview &   # serves http://localhost:4321
```
Run a Playwright script that, for `http://localhost:4321/`:
1. Asserts `[data-cv-pub="aggregate"]` is visible and `[data-cv-pub="full"]` is hidden on initial load (bridge default).
2. Clicks `[data-cv-target="comp-bio"]`, then asserts `[data-cv-pub="full"]` is visible and `[data-cv-pub="aggregate"]` is hidden, and that `svg`/chart nodes remain visible.
3. Clicks `[data-cv-target="ds-ml"]`, asserts aggregate visible / full hidden again.

Stop the preview server afterward. Document the result (pass/fail) in the task notes.

- [ ] **Step 7: Commit**

```bash
git add web/src/types/content.ts web/src/components/PublicationsList.astro web/src/components/TargetSwitcher.astro web/src/pages/index.astro web/src/pages/de/index.astro
git commit -m "feat(web): #46 variant-aware publications — charts always, list/aggregate toggle"
```

---

## Task 7: Docs + final green

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add the new module to the Layout**

In `CLAUDE.md`, in the `## Layout` code block, update the `scripts/` line to include `publications.py`. Find:
```
scripts/                  validate.py, bib_loader.py, content_loader.py, langstring.py, config.py, render_web_data.py, render_jsonresume.py, render_jsonld.py, render_text.py
```
and add `publications.py` to the list (e.g. after `bib_loader.py`):
```
scripts/                  validate.py, bib_loader.py, publications.py, content_loader.py, langstring.py, config.py, render_web_data.py, render_jsonresume.py, render_jsonld.py, render_text.py
```

- [ ] **Step 2: Confirm the phasing table is unchanged**

#46 is a post-Phase-9 maintenance item, not a phase. Verify the `## Phasing` table still ends at Phase 9 and gains no new row. (No edit expected — this step is a guard.)

- [ ] **Step 3: Full suite green**

Run: `just validate && just test && just lint && just web-build`
Expected: ALL PASS.

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: #46 list scripts/publications.py in CLAUDE.md Layout"
```

---

## Self-Review (completed during planning)

**Spec coverage:** PDF aggregate (Task 3), plain-text aggregate (Task 4), web variant-aware with charts-always (Task 6), shared derived module (Task 1), labels (Tasks 2–3), machine formats untouched (no task — by omission), `select_publications`/`publications_selected` removal (Task 3), CLAUDE.md (Task 7). All spec sections map to a task.

**Type consistency:** `publication_mode`, `publication_summary`, `format_publication_summary`, and `PublicationSummary` fields (`peer_reviewed`, `pr_first`, `pr_shared`, `pr_coauthor`, `conferences`, `year_start`, `year_end`) are identical across Tasks 1, 3, 4, 5. The label keys (`labels.publications.summary`, `labels.publications.full_list_pointer`) match between Task 2 (definition) and Tasks 3/4/5 (consumption). The `{placeholders}` in the Task 2 template exactly match the `format_publication_summary` kwargs in Task 1. The data fields injected by `prepare_data` (`publications_mode`, `publications_summary`, `publications_pointer`, `publications_heading`) match the Typst reads in Task 3. The web `aggregate`/`orcid` props (Task 6) match `ContentData.publications_aggregate` + `personal.links.orcid`.

**Green-between-commits:** Task 2 only adds a label (additive). Task 3 bundles the `build.py` + Typst + label-removal + test rework so no intermediate commit has `build.py` ahead of the Typst/tests. `variants.json` is never touched, so `test_render_web_data_variants.py` stays green throughout.
