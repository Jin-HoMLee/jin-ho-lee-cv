# Crossref Citation-Count Enrichment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enrich publications with Crossref citation counts (fetched at build time, cached in a committed `data/citations.json`) and surface them as an SVG bar chart + per-paper counts on the website and as `interactionStatistic` in the JSON-LD.

**Architecture:** A manual networked fetcher (`scripts/fetch_citations.py`, run via `just refresh-citations`) writes a committed `data/citations.json` lockfile. A pure reader (`scripts/citations.py`) loads it and enriches `Publication` records offline; renderers (`render_web_data`, `render_jsonld`) call the reader and degrade gracefully when a DOI or the whole cache is absent. No build-path network access, no runtime third-party JS.

**Tech Stack:** Python 3.12 (stdlib `urllib`, `pybtex`, `ruamel.yaml`), pytest + syrupy (golden snapshots), Astro 5 + Tailwind 4 (SVG components), `just` + `uv` task runner.

**Design spec:** `docs/superpowers/specs/2026-06-02-crossref-citation-enrichment-design.md`

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `scripts/bib_loader.py` | `Publication` gains optional `citation_count` field; stays network/cache-free | Modify |
| `scripts/citations.py` | Read committed cache → `{doi: count}`; enrich publications offline | Create |
| `scripts/fetch_citations.py` | The ONLY networked code; fetch Crossref counts → `data/citations.json` | Create |
| `data/citations.json` | Committed, generated cache (lockfile) | Create (seeded) |
| `scripts/render_web_data.py` | Enrich pubs so `citation_count` rides into `content.{en,de}.json` | Modify |
| `scripts/render_jsonld.py` | Enrich pubs; emit `interactionStatistic` per work | Modify |
| `web/src/components/PublicationsCitations.astro` | SVG citations-per-paper bar chart | Create |
| `web/src/components/PublicationsList.astro` | Render the new chart; per-paper "cited by N" in full list | Modify |
| `web/src/types/content.ts` | `Publication` interface gains `citation_count` | Modify |
| `justfile` | `refresh-citations` recipe | Modify |
| `tests/test_citations.py` | Cache load + enrich + staleness guard | Create |
| `tests/test_fetch_citations.py` | Fetch parse + merge-retain + refresh (DI fakes, no network) | Create |
| `tests/test_render_web_data.py` | Enriched web output carries counts | Modify |
| `tests/test_render_jsonld.py` | `interactionStatistic` emitted/omitted | Modify |
| `CLAUDE.md` | Layout / Commands / Conventions updates | Modify (final) |

**Conventions to follow (verified against the codebase):**
- Test modules start with `from __future__ import annotations`, then stdlib, then `pytest`, then `from scripts....`. Returns are type-hinted; args usually not.
- The repo uses **no mock library** — design for dependency injection (pass fake callables) instead of patching.
- Recipes run `uv run python -m scripts.<module>`.
- Ruff: line-length 100, target py312, default rule set (includes `E731` — **never** assign a `lambda`; use `def`).

---

### Task 1: Add `citation_count` to the `Publication` dataclass

**Files:**
- Modify: `scripts/bib_loader.py:23-34` (the `Publication` dataclass)
- Test: `tests/test_bib_loader.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_bib_loader.py`:

```python
def test_publication_has_citation_count_defaulting_none():
    pub = load_publications(BIB_PATH)[0]
    assert pub.citation_count is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_bib_loader.py::test_publication_has_citation_count_defaulting_none -v`
Expected: FAIL with `AttributeError: 'Publication' object has no attribute 'citation_count'`

- [ ] **Step 3: Add the field**

In `scripts/bib_loader.py`, add the field as the LAST entry of the frozen dataclass (after `category`, so both defaulted fields sit together):

```python
@dataclass(frozen=True)
class Publication:
    key: str
    title: str
    year: int
    type: str
    authorship: str
    authors: tuple[str, ...]
    venue: str | None
    doi: str | None
    raw: dict
    category: str = "research"
    citation_count: int | None = None
```

`_parse_entry` does **not** set it (defaults to `None`); citations are attached later by `scripts/citations.py`. Leave `_parse_entry` unchanged.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_bib_loader.py -v`
Expected: PASS

- [ ] **Step 5: Regenerate the web-data snapshots (expected drift)**

`render_web_data` serializes pubs via `dataclasses.asdict`, so every publication in `content.{en,de}.json` now gains `"citation_count": null`. The value is `null` (not a number) because `render_web_data` does not enrich yet — the field simply serializes at its dataclass default `None`. Numbers arrive in Task 6 after the cache is seeded and enrichment is wired. This is the only snapshot affected (jsonld/resume/text/llms read named fields, not `asdict`).

Run: `uv run just snapshots-update`
Then inspect: `git diff tests/__snapshots__/`
Expected: ONLY `test_web_data_snapshot[content.en.json].json` and `test_web_data_snapshot[content.de.json].json` change, each adding `"citation_count": null` to every publication. The `content.*.variants.json` snapshots do **NOT** change — variant output carries only text overrides (headline/tagline/paragraphs), not publications.

- [ ] **Step 6: Verify the whole suite is green**

Run: `uv run just test`
Expected: PASS. No non-snapshot test breaks: the only publication key-set assertion in `tests/test_render_web_data.py` uses `>=` (superset), so the extra `citation_count` key is tolerated; the top-level `set(en.keys()) == expected_keys` checks are unaffected (the new key is nested inside publications).

- [ ] **Step 7: Commit**

```bash
git add scripts/bib_loader.py tests/test_bib_loader.py tests/__snapshots__/
git commit -m "feat: #57 add optional citation_count to Publication"
```

---

### Task 2: `scripts/citations.py` — offline cache reader + enricher

**Files:**
- Create: `scripts/citations.py`
- Test: `tests/test_citations.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_citations.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from scripts.bib_loader import Publication, load_publications
from scripts.citations import enrich_publications, load_citation_cache

REPO_ROOT = Path(__file__).resolve().parent.parent
BIB_PATH = REPO_ROOT / "content" / "publications.bib"
CACHE_PATH = REPO_ROOT / "data" / "citations.json"


def _pub(**over) -> Publication:
    base = dict(
        key="x", title="T", year=2019, type="article", authorship="first",
        authors=("Lee, J.",), venue="Cancers", doi=None, raw={},
    )
    base.update(over)
    return Publication(**base)


def test_load_cache_reads_counts(tmp_path):
    f = tmp_path / "citations.json"
    f.write_text(json.dumps({"counts": {"10.1/a": 5, "10.2/b": 12}}), encoding="utf-8")
    assert load_citation_cache(f) == {"10.1/a": 5, "10.2/b": 12}


def test_load_cache_reads_counts_from_full_document(tmp_path):
    # Mirrors the real shape that fetch_citations.refresh() writes (Task 3/5):
    # the reader must extract `counts` and ignore the metadata fields.
    f = tmp_path / "citations.json"
    f.write_text(json.dumps({
        "_generated_by": "just refresh-citations — do not hand-edit",
        "source": "crossref",
        "fetched_at": "2026-06-02",
        "counts": {"10.1/a": 5},
    }), encoding="utf-8")
    assert load_citation_cache(f) == {"10.1/a": 5}


def test_load_cache_missing_file_is_empty(tmp_path):
    assert load_citation_cache(tmp_path / "nope.json") == {}


def test_load_cache_garbage_is_empty(tmp_path):
    f = tmp_path / "citations.json"
    f.write_text("{not json", encoding="utf-8")
    assert load_citation_cache(f) == {}


def test_load_cache_non_int_values_dropped(tmp_path):
    f = tmp_path / "citations.json"
    payload = {"counts": {"10.1/a": 5, "10.2/b": "oops", "10.3/c": None}}
    f.write_text(json.dumps(payload), encoding="utf-8")
    assert load_citation_cache(f) == {"10.1/a": 5}


def test_enrich_sets_count_for_matching_doi():
    pubs = [_pub(doi="10.1/a"), _pub(doi="10.2/b")]
    out = enrich_publications(pubs, {"10.1/a": 7})
    assert out[0].citation_count == 7
    assert out[1].citation_count is None


def test_enrich_pub_without_doi_stays_none():
    out = enrich_publications([_pub(doi=None)], {"10.1/a": 7})
    assert out[0].citation_count is None


def test_enrich_does_not_mutate_inputs():
    pubs = [_pub(doi="10.1/a")]
    enrich_publications(pubs, {"10.1/a": 7})
    assert pubs[0].citation_count is None  # original untouched (frozen → new objects)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_citations.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.citations'`

- [ ] **Step 3: Implement `scripts/citations.py`**

```python
"""Citation-count enrichment: read the committed Crossref cache, attach counts to publications.

The cache (data/citations.json) is a generated, committed lockfile produced by
scripts/fetch_citations.py (`just refresh-citations`). This module is the ONLY reader of
that cache and never touches the network — every renderer enriches offline and degrades
gracefully when a DOI (or the whole cache) is absent.
"""
from __future__ import annotations

import dataclasses
import json
from pathlib import Path

from scripts.bib_loader import Publication


def load_citation_cache(path: Path) -> dict[str, int]:
    """Read the committed citation cache → {doi: count}.

    A missing or unparseable file (or a malformed ``counts`` block) yields an empty dict —
    the offline-degrade contract: renderers then emit no counts rather than failing.
    """
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {}
    counts = raw.get("counts", {})
    if not isinstance(counts, dict):
        return {}
    return {
        str(doi): n
        for doi, n in counts.items()
        if isinstance(n, int) and not isinstance(n, bool)
    }


def enrich_publications(pubs: list[Publication], cache: dict[str, int]) -> list[Publication]:
    """Return NEW Publication records with citation_count set from the cache by DOI.

    A publication whose DOI is absent from the cache (or which has no DOI) keeps
    citation_count=None. Inputs are never mutated (Publication is frozen).
    """
    out: list[Publication] = []
    for p in pubs:
        count = cache.get(p.doi) if p.doi else None
        out.append(dataclasses.replace(p, citation_count=count))
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_citations.py -v`
Expected: PASS (all 7 tests)

- [ ] **Step 5: Add the staleness-guard test**

Append to `tests/test_citations.py` (guards the committed cache against stale DOIs; passes even before the cache exists, since a missing cache → `{}`):

```python
def test_committed_cache_has_no_orphan_dois():
    """Every DOI in data/citations.json must map to a real publication (no stale keys)."""
    cache = load_citation_cache(CACHE_PATH)
    pub_dois = {p.doi for p in load_publications(BIB_PATH) if p.doi}
    assert set(cache) <= pub_dois
```

- [ ] **Step 6: Run the staleness test (passes with no cache yet)**

Run: `uv run pytest tests/test_citations.py::test_committed_cache_has_no_orphan_dois -v`
Expected: PASS (cache file does not exist yet → `{}` ⊆ pub DOIs)

- [ ] **Step 7: Commit**

```bash
git add scripts/citations.py tests/test_citations.py
git commit -m "feat: #57 add citation cache reader + publication enricher"
```

---

### Task 3: `scripts/fetch_citations.py` — networked fetcher (DI-testable)

**Files:**
- Create: `scripts/fetch_citations.py`
- Test: `tests/test_fetch_citations.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_fetch_citations.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from scripts.fetch_citations import build_counts, fetch_citation_count, refresh

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = REPO_ROOT / "content"
BIB_PATH = CONTENT_DIR / "publications.bib"


class _FakeResp:
    """Minimal context-manager stand-in for an http response (no network)."""
    def __init__(self, data: bytes):
        self._data = data

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self) -> bytes:
        return self._data


def test_fetch_parses_is_referenced_by_count():
    def opener(req, timeout):
        return _FakeResp(b'{"message": {"is-referenced-by-count": 58}}')

    assert fetch_citation_count("10.3390/x", mailto="a@b.c", opener=opener) == 58


def test_build_counts_uses_fetched_values():
    def fetch(doi):
        return {"10.a": 10, "10.b": 20}[doi]

    assert build_counts(["10.a", "10.b"], fetch=fetch, prior={}) == {"10.a": 10, "10.b": 20}


def test_build_counts_retains_prior_on_error():
    def fetch(doi):
        if doi == "10.good":
            return 10
        raise RuntimeError("boom")

    counts = build_counts(["10.good", "10.bad", "10.new"], fetch=fetch, prior={"10.bad": 7})
    # good → fetched; bad → retained prior; new → failed with no prior → omitted
    assert counts == {"10.good": 10, "10.bad": 7}


def test_refresh_writes_sorted_documented_cache(tmp_path):
    cache = tmp_path / "citations.json"

    def fetch(doi):
        return len(doi)  # deterministic, no network

    doc = refresh(
        bib_path=BIB_PATH, cache_path=cache, content_dir=CONTENT_DIR,
        fetch=fetch, today="2026-06-02",
    )
    assert doc["_generated_by"] == "just refresh-citations — do not hand-edit"
    assert doc["source"] == "crossref"
    assert doc["fetched_at"] == "2026-06-02"
    assert list(doc["counts"]) == sorted(doc["counts"])  # keys sorted for stable diffs
    on_disk = json.loads(cache.read_text(encoding="utf-8"))
    assert on_disk == doc
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_fetch_citations.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.fetch_citations'`

- [ ] **Step 3: Implement `scripts/fetch_citations.py`**

```python
"""Fetch Crossref citation counts for publication DOIs → data/citations.json.

The ONLY networked code in the project. Run manually via `just refresh-citations`; never on
the build path (CI/builds read the committed cache offline and deterministically). Uses
Crossref's key-free REST API and joins the polite pool via a User-Agent carrying the CV's
public contact email (read from content — single source of truth).

Crossref counts lag and undercount relative to Google Scholar; web and JSON-LD consumers
label the figures "indicative" to avoid overstating them.
"""
from __future__ import annotations

import datetime
import json
import urllib.request
from pathlib import Path
from typing import Callable

from scripts.bib_loader import load_publications
from scripts.citations import load_citation_cache
from scripts.config import PAGES_BASE_URL
from scripts.content_loader import load_content

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = REPO_ROOT / "content"
BIB_PATH = CONTENT_DIR / "publications.bib"
CACHE_PATH = REPO_ROOT / "data" / "citations.json"
CROSSREF_WORK_URL = "https://api.crossref.org/works/{doi}"
TIMEOUT_S = 30


def _user_agent(mailto: str) -> str:
    """Crossref polite-pool identifier (see crossref.org REST API docs)."""
    return f"jin-ho-lee-cv/1.0 (+{PAGES_BASE_URL}; mailto:{mailto})"


def fetch_citation_count(
    doi: str, *, mailto: str, opener: Callable = urllib.request.urlopen
) -> int:
    """GET Crossref's is-referenced-by-count for one DOI. Raises on any failure.

    `opener` is injectable so tests can supply a fake response without hitting the network.
    """
    req = urllib.request.Request(
        CROSSREF_WORK_URL.format(doi=doi),
        headers={"User-Agent": _user_agent(mailto)},
    )
    with opener(req, timeout=TIMEOUT_S) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return int(payload["message"]["is-referenced-by-count"])


def build_counts(
    dois: list[str], *, fetch: Callable[[str], int], prior: dict[str, int]
) -> dict[str, int]:
    """Fetch each DOI; on per-DOI error, RETAIN the prior cached value (never clobber).

    A DOI that both fails AND has no prior value is omitted. Callers sort keys on write.
    """
    counts: dict[str, int] = {}
    for doi in dois:
        try:
            counts[doi] = fetch(doi)
        except Exception:
            if doi in prior:
                counts[doi] = prior[doi]
    return counts


def refresh(
    *,
    bib_path: Path = BIB_PATH,
    cache_path: Path = CACHE_PATH,
    content_dir: Path = CONTENT_DIR,
    fetch: Callable[[str], int] | None = None,
    today: str | None = None,
) -> dict:
    """Build the cache document, write it to cache_path, and return it."""
    # Read the CV owner's email from content (single source of truth for contact info).
    mailto = load_content(content_dir, lang="en")["personal"]["email"]
    if fetch is None:
        # Nested name differs from the `fetch` param to avoid any redefinition ambiguity.
        def _default_fetch(doi: str) -> int:
            return fetch_citation_count(doi, mailto=mailto)
        fetch = _default_fetch

    dois = [p.doi for p in load_publications(bib_path) if p.doi]
    prior = load_citation_cache(cache_path)
    counts = build_counts(dois, fetch=fetch, prior=prior)
    doc = {
        "_generated_by": "just refresh-citations — do not hand-edit",
        "source": "crossref",
        "fetched_at": today or datetime.date.today().isoformat(),
        "counts": {doi: counts[doi] for doi in sorted(counts)},
    }
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return doc


def main() -> int:
    doc = refresh()
    print(f"wrote {CACHE_PATH.relative_to(REPO_ROOT)} ({len(doc['counts'])} DOIs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_fetch_citations.py -v`
Expected: PASS (4 tests, no network)

- [ ] **Step 5: Lint the new modules**

Run: `uv run ruff check scripts/fetch_citations.py scripts/citations.py tests/test_fetch_citations.py tests/test_citations.py`
Expected: PASS (no `E731`/`F401`/import-order issues)

- [ ] **Step 6: Commit**

```bash
git add scripts/fetch_citations.py tests/test_fetch_citations.py
git commit -m "feat: #57 add Crossref citation fetcher (manual, offline-safe)"
```

---

### Task 4: `just refresh-citations` recipe

**Files:**
- Modify: `justfile` (add near `build-formats`)

- [ ] **Step 1: Add the recipe**

In `justfile`, after the `build-formats` recipe block, add:

```
# Refresh Crossref citation counts → data/citations.json (the ONLY networked recipe; run manually)
refresh-citations:
    uv run python -m scripts.fetch_citations
```

- [ ] **Step 2: Verify the recipe is registered**

Run: `uv run just --list | grep refresh-citations`
Expected: shows `refresh-citations` in the recipe list.

- [ ] **Step 3: Commit**

```bash
git add justfile
git commit -m "build: #57 add refresh-citations recipe"
```

---

### Task 5: Seed the committed cache (one-time network)

**Files:**
- Create: `data/citations.json` (committed)

> **Network required (once).** This is the only step that hits Crossref. If offline, skip and hand-author `data/citations.json` in the same shape (`{"_generated_by": ..., "source": "crossref", "fetched_at": "YYYY-MM-DD", "counts": {}}`), then run Task 5 later — every downstream task degrades gracefully on an empty cache.

- [ ] **Step 1: Fetch real counts**

Run: `uv run just refresh-citations`
Expected: prints `wrote data/citations.json (N DOIs)` where N is the count of DOIs in `publications.bib` that Crossref resolved (up to 11).

- [ ] **Step 2: Inspect the result**

Run: `cat data/citations.json`
Expected: keys sorted; values are non-negative integers; `_generated_by` present. Sanity-check a known DOI (e.g. `10.3390/cancers11121877`) has a plausible count.

- [ ] **Step 3: Confirm the staleness guard still passes against the real cache**

Run: `uv run pytest tests/test_citations.py::test_committed_cache_has_no_orphan_dois -v`
Expected: PASS (every fetched DOI maps to a real publication).

- [ ] **Step 4: Commit the seeded cache**

```bash
git add data/citations.json
git commit -m "data: #57 seed committed Crossref citation cache"
```

---

### Task 6: `render_web_data` enriches publications

**Files:**
- Modify: `scripts/render_web_data.py` (imports + `CITATIONS_PATH` + `render_web_data` signature/body)
- Test: `tests/test_render_web_data.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_render_web_data.py`. The DOI is derived from the real bib (not hardcoded, so the test can't rot), and a tmp cache makes it independent of the committed numbers. A second test pins the offline-degrade contract:

```python
def test_publications_carry_citation_count_from_cache(tmp_path):
    from scripts.bib_loader import load_publications

    target_doi = next(p.doi for p in load_publications(CONTENT_DIR / "publications.bib") if p.doi)
    cache = tmp_path / "citations.json"
    cache.write_text(json.dumps({"counts": {target_doi: 99}}), encoding="utf-8")
    out_dir = tmp_path / "out"
    render_web_data(content_dir=CONTENT_DIR, output_dir=out_dir, citations_path=cache)
    pubs = json.loads((out_dir / "content.en.json").read_text(encoding="utf-8"))["publications"]
    assert all("citation_count" in p for p in pubs)
    hit = next(p for p in pubs if p["doi"] == target_doi)
    assert hit["citation_count"] == 99
    # Every other publication (absent from the single-entry cache) stays None.
    assert all(p["citation_count"] is None for p in pubs if p["doi"] != target_doi)


def test_missing_cache_yields_null_counts(tmp_path):
    """Offline-degrade contract: a nonexistent cache → all counts None, no failure."""
    out_dir = tmp_path / "out"
    render_web_data(
        content_dir=CONTENT_DIR, output_dir=out_dir,
        citations_path=tmp_path / "does-not-exist.json",
    )
    pubs = json.loads((out_dir / "content.en.json").read_text(encoding="utf-8"))["publications"]
    assert all(p["citation_count"] is None for p in pubs)
```

(`json` and `CONTENT_DIR` are already present in `tests/test_render_web_data.py`; `load_publications` is imported locally inside the test.)

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_render_web_data.py::test_publications_carry_citation_count_from_cache -v`
Expected: FAIL with `TypeError: render_web_data() got an unexpected keyword argument 'citations_path'`

- [ ] **Step 3: Implement enrichment**

In `scripts/render_web_data.py`:

a) Add the import (with the existing `from scripts....` imports):

```python
from scripts.citations import enrich_publications, load_citation_cache
```

b) Add the cache-path constant next to the other path constants (after `OUTPUT_DIR`):

```python
CITATIONS_PATH = REPO_ROOT / "data" / "citations.json"
```

c) Change the `render_web_data` signature to accept the cache path:

```python
def render_web_data(
    *, content_dir: Path = CONTENT_DIR, output_dir: Path = OUTPUT_DIR,
    citations_path: Path = CITATIONS_PATH,
) -> None:
```

d) Inside the `for lang in LANGS:` loop, immediately after `bridge_resolved = resolve_langstrings(...)` is assigned (before `pub_labels = ...`), enrich the publications in place:

```python
        bridge_resolved["publications"] = enrich_publications(
            bridge_resolved["publications"], load_citation_cache(citations_path)
        )
```

The existing `format_publication_summary(...)` and `_dump(...)` then consume the enriched list; `_to_jsonable`'s `dataclasses.asdict` carries `citation_count` into the JSON automatically.

- [ ] **Step 4: Run both new tests to verify they pass**

Run: `uv run pytest tests/test_render_web_data.py -k "citation_count or missing_cache" -v`
Expected: PASS (both `test_publications_carry_citation_count_from_cache` and `test_missing_cache_yields_null_counts`)

- [ ] **Step 5: Regenerate web-data snapshots with the real committed counts**

Now that the committed `data/citations.json` exists (Task 5) and `render_web_data` enriches, the default-path output gains real numbers.

Run: `uv run just snapshots-update`
Then inspect: `git diff tests/__snapshots__/`
Expected: ONLY `test_web_data_snapshot[content.en.json].json` and `[content.de.json].json` change — `"citation_count": null` becomes an integer for each publication whose DOI is in the cache; non-cached pubs stay `null`. No other snapshot moves.

- [ ] **Step 6: Verify the suite is green**

Run: `uv run just test`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add scripts/render_web_data.py tests/test_render_web_data.py tests/__snapshots__/
git commit -m "feat: #57 enrich web publication data with citation counts"
```

---

### Task 7: `render_jsonld` emits `interactionStatistic`

**Files:**
- Modify: `scripts/render_jsonld.py` (`CITATIONS_PATH`, `_publications`, `main`)
- Test: `tests/test_render_jsonld.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_render_jsonld.py` (the module already defines `_pub` and imports `_publications as jsonld_publications`):

```python
def test_publication_with_citation_count_emits_interaction_statistic():
    [item] = jsonld_publications(
        [_pub(doi="10.3390/cancers11121877", citation_count=58)],
        "https://orcid.org/X", "Lee, J",
    )
    assert item["interactionStatistic"] == {
        "@type": "InteractionCounter",
        "interactionType": "https://schema.org/CiteAction",
        "userInteractionCount": 58,
    }


def test_publication_without_citation_count_omits_interaction_statistic():
    [item] = jsonld_publications(
        [_pub(doi="10.3390/cancers11121877")], "https://orcid.org/X", "Lee, J",
    )
    assert "interactionStatistic" not in item
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_render_jsonld.py -k interaction_statistic -v`
Expected: FAIL (first test KeyError on `interactionStatistic`)

- [ ] **Step 3: Implement**

In `scripts/render_jsonld.py`:

a) Add the import (with the existing `from scripts....` imports):

```python
from scripts.citations import enrich_publications, load_citation_cache
```

b) Add the cache-path constant near `CONTENT_DIR`:

```python
CITATIONS_PATH = REPO_ROOT / "data" / "citations.json"
```

c) In `_publications`, inside the `for p in pubs:` loop, add the citation block **after** the existing `if p.doi:` block and **immediately before** `out.append(item)`. For unambiguous placement, the surrounding context (existing lines unchanged, new block marked) is:

```python
        if p.doi:
            item["sameAs"] = [doi_url]
            item["identifier"] = {"@type": "PropertyValue", "propertyID": "DOI", "value": p.doi}
        # --- NEW: indicative Crossref citation count -------------------------------
        if p.citation_count is not None:
            item["interactionStatistic"] = {
                "@type": "InteractionCounter",
                "interactionType": "https://schema.org/CiteAction",
                "userInteractionCount": p.citation_count,
            }
        # --------------------------------------------------------------------------
        out.append(item)
```

d) In `main`, enrich the loaded pubs before composing the graph. Change:

```python
    pubs = load_publications(CONTENT_DIR / "publications.bib")
```

to:

```python
    pubs = enrich_publications(
        load_publications(CONTENT_DIR / "publications.bib"),
        load_citation_cache(CITATIONS_PATH),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_render_jsonld.py -k interaction_statistic -v`
Expected: PASS (both)

- [ ] **Step 5: Regenerate the JSON-LD snapshot with real counts**

Run: `uv run just snapshots-update`
Then inspect: `git diff tests/__snapshots__/`
Expected: ONLY `test_person_jsonld.json` changes — each `ScholarlyArticle` whose DOI is in the cache gains an `interactionStatistic` block. (`content.*.json` should NOT change again here.)

- [ ] **Step 6: Verify the suite is green**

Run: `uv run just test`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add scripts/render_jsonld.py tests/test_render_jsonld.py tests/__snapshots__/
git commit -m "feat: #57 emit interactionStatistic citation counts in JSON-LD"
```

---

### Task 8: Web — citations bar chart + per-paper counts

**Files:**
- Create: `web/src/components/PublicationsCitations.astro`
- Modify: `web/src/components/PublicationsList.astro` (import + render + per-paper count)
- Modify: `web/src/types/content.ts` (`Publication.citation_count`)

- [ ] **Step 1: Add the type field**

In `web/src/types/content.ts`, add to the `Publication` interface (after `doi`):

```typescript
  citation_count: number | null;
```

- [ ] **Step 2: Create the bar-chart component**

Create `web/src/components/PublicationsCitations.astro`:

```astro
---
import type { Publication, Lang } from "../types/content";

interface Props {
  publications: Publication[];
  lang: Lang;
}

const { publications, lang } = Astro.props;

// Only papers with a Crossref count; most-cited first.
const cited = publications
  .filter((p) => p.citation_count != null)
  .sort((a, b) => (b.citation_count ?? 0) - (a.citation_count ?? 0));

const maxCount = cited.reduce((m, p) => Math.max(m, p.citation_count ?? 0), 0);

const captionLabel = {
  en: "Crossref citations · indicative (undercounts vs. Google Scholar)",
  de: "Crossref-Zitationen · indikativ (untererfasst ggü. Google Scholar)",
}[lang];

function shortLabel(p: Publication): string {
  const yy = `'${String(p.year).slice(-2)}`;
  return p.venue ? `${p.venue} ${yy}` : `${p.title.slice(0, 18)}… ${yy}`;
}

// SVG geometry: one row per cited paper.
const rowH = 22;
const gap = 6;
const labelW = 130;
const barMax = 220;
const numW = 34;
const W = labelW + barMax + numW;
const H = Math.max(1, cited.length * (rowH + gap));
---
{cited.length > 0 && (
  <figure class="pub-citations relative my-6">
    <svg
      viewBox={`0 0 ${W} ${H}`}
      class="w-full"
      role="img"
      aria-label={`Citation counts for ${cited.length} publications (Crossref, indicative)`}
    >
      {cited.map((p, i) => {
        const y = i * (rowH + gap);
        const w = maxCount > 0 ? ((p.citation_count ?? 0) / maxCount) * barMax : 0;
        return (
          <g
            data-cite-label={p.title}
            data-cite-count={p.citation_count}
            tabindex="0"
            role="button"
            aria-label={`${p.title}: cited by ${p.citation_count}`}
            class="cursor-pointer"
          >
            <text x={labelW - 6} y={y + rowH * 0.7} text-anchor="end" font-size="11" style="fill: var(--muted)">{shortLabel(p)}</text>
            <rect x={labelW} y={y} width={w} height={rowH} rx="2" style="fill: var(--chart-2)" />
            <text x={labelW + w + 5} y={y + rowH * 0.7} font-size="11" style="fill: var(--faint)">{p.citation_count}</text>
          </g>
        );
      })}
    </svg>
    <figcaption class="mt-1 text-xs text-[var(--faint)]">{captionLabel}</figcaption>
    <div
      class="pub-tooltip pointer-events-none absolute hidden rounded px-2 py-1 text-xs shadow-lg"
      style="background: var(--text); color: var(--bg)"
      role="status"
      aria-live="polite"
    ></div>
  </figure>
)}

<script>
  // Hover / tap / keyboard-focus a citation bar to surface the full title + count.
  const figs = document.querySelectorAll<HTMLElement>("figure.pub-citations");
  for (const fig of figs) {
    const tooltip = fig.querySelector<HTMLElement>(".pub-tooltip");
    const rows = fig.querySelectorAll<SVGGElement>("g[data-cite-label]");
    if (!tooltip || rows.length === 0) continue;

    const show = (e: Event, target: SVGGElement) => {
      const title = target.dataset.citeLabel ?? "";
      const count = target.dataset.citeCount ?? "";
      tooltip.textContent = `${title} — cited by ${count}`;
      tooltip.classList.remove("hidden");
      const rect = fig.getBoundingClientRect();
      const usePointer =
        e.type === "mouseenter" || e.type === "mousemove" || e.type === "touchstart";
      if (usePointer) {
        const pe = e as MouseEvent | TouchEvent;
        const point = "touches" in pe ? pe.touches[0] : pe;
        tooltip.style.left = `${point.clientX - rect.left + 8}px`;
        tooltip.style.top = `${point.clientY - rect.top + 8}px`;
      } else {
        const b = target.getBoundingClientRect();
        tooltip.style.left = `${b.left + b.width / 2 - rect.left + 8}px`;
        tooltip.style.top = `${b.top + b.height / 2 - rect.top + 8}px`;
      }
    };
    const hide = () => tooltip.classList.add("hidden");

    rows.forEach((r) => {
      r.addEventListener("mouseenter", (e) => show(e, r));
      r.addEventListener("mousemove", (e) => show(e, r));
      r.addEventListener("mouseleave", hide);
      r.addEventListener("touchstart", (e) => {
        e.preventDefault();
        if (tooltip.classList.contains("hidden")) show(e, r);
        else hide();
      }, { passive: false });
      r.addEventListener("focus", (e) => show(e, r));
      r.addEventListener("blur", hide);
      r.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          if (tooltip.classList.contains("hidden")) show(e, r);
          else hide();
        }
      });
    });
    document.addEventListener("touchstart", (e) => {
      if (!fig.contains(e.target as Node)) hide();
    }, { passive: true });
  }
</script>
```

- [ ] **Step 3: Wire the chart into `PublicationsList.astro`**

a) Add the import (with the other component imports at the top):

```astro
import PublicationsCitations from "./PublicationsCitations.astro";
```

b) Render it as a full-width block immediately AFTER the closing `</div>` of the pie+cumulative flex row (`<div class="flex flex-col gap-2 md:flex-row ...">...</div>`) and BEFORE the `<!-- Aggregate ... -->` comment:

```astro
  <PublicationsCitations publications={publications} lang={lang} />
```

- [ ] **Step 4: Add the per-paper "cited by N" to the full list**

In `PublicationsList.astro`, in the full-list meta paragraph, add the count inline after the DOI link and before the closing `</p>`. The surrounding context (existing lines unchanged, new block marked) is:

```astro
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
                {/* NEW: indicative Crossref count, inline after the DOI */}
                {p.citation_count != null && (
                  <> · cited by {p.citation_count}</>
                )}
              </p>
```

- [ ] **Step 5: Build the site to verify it compiles**

Run: `uv run just web-build`
Expected: `pnpm --dir web build` completes with no errors; `web/dist/` is produced. (Astro compiles the new component and the type addition.)

- [ ] **Step 6: Visual verification**

Regenerate data and screenshot the publications section per the repo's web-verify flow (Playwright with the npx-cache module + system Chrome over `astro preview`, per `reference_web_visual_verify`):

Run: `uv run just web-data && uv run just web-build`
Then preview `web/dist` and capture the `#publications` section. Confirm:
- the bar chart renders below the pie + cumulative, bars sorted descending, "indicative" caption visible;
- hovering/focusing a bar shows the full title + "cited by N" tooltip;
- the bar chart stays visible for **all** targets (bridge, comp-bio, ds-ml) — it is NOT gated like the verbatim full list;
- switching to the comp-bio target reveals the full list with "· cited by N" on cited papers;
- light AND dark themes both render the bars (uses `--chart-2`, `--muted`, `--faint`).

- [ ] **Step 7: Commit**

```bash
git add web/src/components/PublicationsCitations.astro web/src/components/PublicationsList.astro web/src/types/content.ts
git commit -m "feat: #57 add citations bar chart + per-paper counts to web"
```

---

### Task 9: Docs + full green sweep (final)

**Files:**
- Modify: `CLAUDE.md` (Layout, Commands, Conventions, Files-to-read)

- [ ] **Step 1: Update CLAUDE.md — Layout**

In the `## Layout` code block, add the new `data/` directory and the two new scripts. Add this line after the `content.private.example/...` line:

```
data/citations.json      generated, committed Crossref citation cache (lockfile)
```

And in the `scripts/` description line, append `fetch_citations.py, citations.py` to the listed modules.

- [ ] **Step 2: Update CLAUDE.md — Commands**

In the `## Commands` block, add under the build recipes:

```bash
just refresh-citations # fetch Crossref citation counts → data/citations.json (manual, networked)
```

- [ ] **Step 3: Update CLAUDE.md — Conventions**

Add a bullet to `## Conventions`:

```markdown
- **Citation cache is a lockfile.** `data/citations.json` is generated by `just refresh-citations` (the only networked recipe) and committed; renderers read it offline and degrade gracefully when a DOI (or the file) is absent. Regenerate intentionally and review the diff — never hand-edit. Adding/removing a publication DOI may require a refresh (a staleness test guards against orphaned cache keys).
```

- [ ] **Step 4: Update CLAUDE.md — Files to read before any phase**

Add to that list (both the spec and this plan, so the design rationale and the task breakdown are discoverable):

```markdown
- `docs/superpowers/specs/2026-06-02-crossref-citation-enrichment-design.md` — Crossref citation-count enrichment design spec (#57)
- `docs/superpowers/plans/2026-06-02-crossref-citation-enrichment.md` — implementation plan for citation-count enrichment (#57)
```

- [ ] **Step 5: Full green sweep**

Run: `uv run just validate && uv run just test && uv run just lint`
Expected: all three PASS. If `just lint` flags the new files, fix (most likely import order or an accidental `lambda`) and re-run.

- [ ] **Step 6: Confirm the "untouched" formats really are untouched**

Run: `uv run just build-resume && uv run just build-text && uv run just build-llms && git status --porcelain dist/`
Expected: `resume.json`, `cv-*.txt`, `llms.txt` regenerate byte-identical (their snapshots already pass in Step 5; this is a belt-and-suspenders check that the field addition didn't leak into them).

- [ ] **Step 7: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: #57 document citation cache (layout, commands, conventions)"
```

---

## Self-Review (completed during authoring)

**Spec coverage:**
- Committed cache, offline-safe, deterministic → Task 2 (reader → `{}` on missing), Task 3 (fetcher), Task 5 (seed). ✅
- Manual refresh trigger → Task 4 recipe; build path never fetches (enrichment reads cache only). ✅
- Counts as *indicative*, no runtime third-party JS → Task 8 SVG chart + caption; build-time bake. ✅
- Bar chart, all targets → Task 8 (rendered in `PublicationsList`, not target-gated). ✅
- Per-paper counts in full list → Task 8 Step 4. ✅
- JSON-LD `interactionStatistic` → Task 7. ✅
- Snapshot tests cover renderer changes → Tasks 1, 6, 7 regen the exact three snapshots. ✅
- Staleness guard → Task 2 Step 5. ✅
- Untouched: PDF / text / JSON Resume → verified no auto-serialization; Task 9 Step 6 confirms. ✅
- CLAUDE.md updates → Task 9. ✅

**Placeholder scan:** No TBD/TODO; every code/test step shows complete content. ✅

**Type consistency:** `load_citation_cache`/`enrich_publications` signatures match across Tasks 2/6/7; `citation_count` field name consistent in Python (`Publication.citation_count`), JSON (`citation_count`), and TS (`citation_count`); `interactionStatistic` shape identical in Task 7 impl and test; fetcher `fetch`/`opener`/`prior` names consistent across impl and tests. ✅
