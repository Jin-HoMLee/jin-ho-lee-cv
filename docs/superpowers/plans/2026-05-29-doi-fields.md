# DOI fields + outbound links Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an optional `doi` field to publications and expose it as a `https://doi.org/<doi>` outbound link across the web, plain-text, JSON Resume, and JSON-LD renderers.

**Architecture:** `bib_loader` gains a normalized, format-validated `doi: str | None` on the `Publication` dataclass; the web JSON serializer picks it up automatically via `dataclasses.asdict`; the four renderers each emit it when present. Real DOIs (looked up + human-verified) land last as a data-only commit. Code-first TDD against synthetic `Publication` fixtures so the plumbing never waits on the verification loop.

**Tech Stack:** Python 3 (pybtex, pytest), Astro/TypeScript (web component), `just` task runner. Spec: `docs/superpowers/specs/2026-05-29-doi-fields-design.md`. Branch: `issue-26-doi-fields` (already created, linked to issue #26).

---

## File Structure

- `scripts/bib_loader.py` — **modify**: add `doi` field + `_normalize_doi` + `_doi` extractor + format guard. The single source of DOI logic.
- `scripts/render_text.py` — **modify**: `_publications` appends a DOI URL line.
- `scripts/render_jsonresume.py` — **modify**: `_publications` sets `url` from DOI.
- `scripts/render_jsonld.py` — **modify**: `_publications` sets `sameAs` from DOI.
- `scripts/render_web_data.py` — **no change** (auto-serializes the new field); covered by a test only.
- `web/src/types/content.ts` — **modify**: add `doi` to `Publication` interface.
- `web/src/components/PublicationsList.astro` — **modify**: render DOI link on the meta line.
- `content/publications.bib` — **modify**: add verified `doi = {...}` to entries that have one.
- Tests: `tests/test_bib_loader.py`, `tests/test_validate.py`, `tests/test_render_web_data.py`, `tests/test_render_text.py`, `tests/test_render_jsonresume.py`, `tests/test_render_jsonld.py` — **modify** (add cases).

A shared test detail: several test files build synthetic `Publication` objects. Each file defines its own tiny local `_pub(**over)` builder (test-fixture duplication is acceptable and keeps files self-contained).

---

## Task 1: Data model — `doi` field, normalization, format guard

**Files:**
- Modify: `scripts/bib_loader.py`
- Test: `tests/test_bib_loader.py`, `tests/test_validate.py`, `tests/test_render_web_data.py`

- [ ] **Step 1: Write the failing loader tests**

Append to `tests/test_bib_loader.py` (it already imports `load_publications` and `pytest`):

```python
def test_doi_extracted_when_present(tmp_path):
    bib = tmp_path / "doi.bib"
    bib.write_text(
        "@article{x, author={Lee, J.}, title={T}, year={2019}, "
        "journal={Cancers}, type={article}, authorship={first}, "
        "doi={10.3390/cancers11121877}}\n"
    )
    assert load_publications(bib)[0].doi == "10.3390/cancers11121877"


def test_doi_is_none_when_absent(tmp_path):
    bib = tmp_path / "nodoi.bib"
    bib.write_text(
        "@article{x, author={Lee, J.}, title={T}, year={2019}, "
        "journal={Cancers}, type={article}, authorship={first}}\n"
    )
    assert load_publications(bib)[0].doi is None


def test_doi_normalizes_resolver_url_and_label(tmp_path):
    bib = tmp_path / "urls.bib"
    bib.write_text(
        "@article{a, author={Lee, J.}, title={A}, year={2019}, journal={J}, "
        "type={article}, authorship={first}, doi={https://doi.org/10.3390/aaa}}\n"
        "@article{b, author={Lee, J.}, title={B}, year={2018}, journal={J}, "
        "type={article}, authorship={first}, doi={doi:10.1000/bbb}}\n"
    )
    by_key = {p.key: p for p in load_publications(bib)}
    assert by_key["a"].doi == "10.3390/aaa"
    assert by_key["b"].doi == "10.1000/bbb"


def test_malformed_doi_raises(tmp_path):
    bib = tmp_path / "bad.bib"
    bib.write_text(
        "@article{x, author={Lee, J.}, title={T}, year={2019}, journal={J}, "
        "type={article}, authorship={first}, doi={not-a-doi}}\n"
    )
    with pytest.raises(ValueError, match="doi"):
        load_publications(bib)
```

- [ ] **Step 2: Run the loader tests to verify they fail**

Run: `pytest tests/test_bib_loader.py -k doi -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'doi'` / `AttributeError: 'Publication' object has no attribute 'doi'`.

- [ ] **Step 3: Implement the field, normalizer, extractor, and guard**

In `scripts/bib_loader.py`, add `import re` near the top imports (after `from typing import Iterable`):

```python
import re
```

Add the DOI regex constant next to the existing module constants (after `AUTHORSHIP_VALUES = {...}`):

```python
# DOI = "10." + registrant digits + "/" + suffix. Suffix is case-insensitive but
# the registrant is always digits; no flag needed.
_DOI_RE = re.compile(r"^10\.\d{4,}/\S+$")
```

Add the `doi` field to the dataclass, between `venue` and `raw`:

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
```

Add the normalizer + extractor (place them after `_venue`):

```python
def _normalize_doi(value: str) -> str:
    """Reduce a pasted DOI (resolver URL or 'doi:'-prefixed) to bare 10.xxxx/yyy."""
    v = value.strip()
    if v.lower().startswith("doi:"):
        v = v[len("doi:"):].strip()
    marker = "doi.org/"
    idx = v.lower().find(marker)
    if idx != -1:
        v = v[idx + len(marker):].strip()
    return v


def _doi(key: str, fields) -> str | None:
    raw = fields.get("doi")
    if raw is None:
        return None
    value = _normalize_doi(str(raw))
    if not value:
        return None
    if not _DOI_RE.match(value):
        raise ValueError(f"{key}: malformed doi {value!r} (expected '10.xxxx/...')")
    return value
```

Wire it into the `Publication(...)` construction in `_parse_entry`, adding `doi=` before `raw=`:

```python
    return Publication(
        key=key,
        title=fields["title"],
        year=int(fields["year"]),
        type=fields["type"],
        authorship=fields["authorship"],
        authors=authors,
        venue=_venue(entry),
        doi=_doi(key, fields),
        raw=dict(fields),
    )
```

- [ ] **Step 4: Run the loader tests to verify they pass**

Run: `pytest tests/test_bib_loader.py -v`
Expected: PASS (all existing + 4 new).

- [ ] **Step 5: Write the failing validate-tree wiring test**

`validate.py::_validate_publications` already round-trips the bib through `load_publications`, so the guard surfaces with no code change. Prove it. Append to `tests/test_validate.py` (it already imports `validate_tree` and defines `_write_minimal_content_tree` + `_SCHEMA_PATH`):

```python
def test_malformed_doi_in_bib_fails_validate_tree(tmp_path):
    """A malformed doi in publications.bib must surface as a validation error."""
    content = tmp_path / "content"
    (content / "projects").mkdir(parents=True)
    _write_minimal_content_tree(content)
    (content / "publications.bib").write_text(
        "@article{x, author={Lee, J.}, title={T}, year={2019}, journal={J}, "
        "type={article}, authorship={first}, doi={not-a-doi}}\n"
    )
    errors = validate_tree(content, _SCHEMA_PATH)
    assert any("doi" in str(e) for e in errors), f"expected a doi error, got: {errors}"
```

- [ ] **Step 6: Run the validate test**

Run: `pytest tests/test_validate.py::test_malformed_doi_in_bib_fails_validate_tree -v`
Expected: PASS (the guard already wires through; if it fails, the loader change in Step 3 is incomplete).

- [ ] **Step 7: Write the failing web-serialization tests**

Adding `doi` to the dataclass makes `dataclasses.asdict` include it automatically. Lock that contract. Append to `tests/test_render_web_data.py`:

```python
from scripts.render_web_data import _to_jsonable
from scripts.bib_loader import Publication


def test_publication_doi_is_serialized():
    pub = Publication(
        key="x", title="T", year=2019, type="article", authorship="first",
        authors=("Lee, J.",), venue="Cancers", doi="10.3390/x", raw={"foo": "bar"},
    )
    d = _to_jsonable(pub)
    assert d["doi"] == "10.3390/x"
    assert "raw" not in d  # bibtex-internal field stays out of the web dump
```

Also extend the existing `test_publications_shape` so the `doi` key is asserted present (it is `None` until real DOIs land, but always present). Add this line inside its `for pub in en["publications"]:` loop:

```python
        assert "doi" in pub  # optional value, but key is always serialized
```

- [ ] **Step 8: Run the web-serialization tests**

Run: `pytest tests/test_render_web_data.py -v`
Expected: PASS.

- [ ] **Step 9: Run the full Python suite + lint to confirm nothing regressed**

Run: `just test && just lint`
Expected: PASS, no ruff findings. (`just validate` also still passes — the real `publications.bib` has no `doi` fields yet, so the guard is a no-op there.)

- [ ] **Step 10: Commit**

```bash
git add scripts/bib_loader.py tests/test_bib_loader.py tests/test_validate.py tests/test_render_web_data.py
git commit -m "feat: extract, normalize, and validate DOI field in bib_loader"
```

---

## Task 2: Plain-text renderer — DOI URL line

**Files:**
- Modify: `scripts/render_text.py`
- Test: `tests/test_render_text.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_render_text.py`:

```python
from scripts.render_text import _publications as render_text_publications
from scripts.bib_loader import Publication


def _pub(**over) -> Publication:
    base = dict(
        key="x", title="T", year=2019, type="article", authorship="first",
        authors=("Lee, J.",), venue="Cancers", doi=None, raw={},
    )
    base.update(over)
    return Publication(**base)


def test_publications_include_doi_url_line():
    out = render_text_publications([_pub(doi="10.3390/cancers11121877")])
    assert "  https://doi.org/10.3390/cancers11121877" in out


def test_publications_omit_doi_line_when_absent():
    out = render_text_publications([_pub(doi=None)])
    assert "https://doi.org/" not in out
```

- [ ] **Step 2: Run to verify they fail**

Run: `pytest tests/test_render_text.py -k doi -v`
Expected: FAIL — `test_publications_include_doi_url_line` asserts a missing line.

- [ ] **Step 3: Implement**

In `scripts/render_text.py`, replace the `_publications` function body:

```python
def _publications(pubs: list[Publication]) -> str:
    out: list[str] = []
    for p in pubs:
        authors = ", ".join(p.authors)
        venue = f" - {p.venue}" if p.venue else ""
        block = f"{p.year}  {p.title}\n  {authors}{venue}"
        if p.doi:
            block += f"\n  https://doi.org/{p.doi}"
        out.append(block)
    return "\n\n".join(out)
```

- [ ] **Step 4: Run to verify they pass**

Run: `pytest tests/test_render_text.py -v`
Expected: PASS (new + all existing, including `test_no_markdown_chars` and `test_no_trailing_whitespace` — the DOI line has neither markdown chars nor trailing whitespace).

- [ ] **Step 5: Commit**

```bash
git add scripts/render_text.py tests/test_render_text.py
git commit -m "feat: render DOI URL line in plain-text publications"
```

---

## Task 3: JSON Resume — `publications[].url` from DOI

**Files:**
- Modify: `scripts/render_jsonresume.py`
- Test: `tests/test_render_jsonresume.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_render_jsonresume.py`:

```python
from scripts.render_jsonresume import _publications as jsonresume_publications
from scripts.bib_loader import Publication


def _pub(**over) -> Publication:
    base = dict(
        key="x", title="T", year=2019, type="article", authorship="first",
        authors=("Lee, J.",), venue="Cancers", doi=None, raw={},
    )
    base.update(over)
    return Publication(**base)


def test_publication_url_is_doi_when_present():
    [entry] = jsonresume_publications([_pub(doi="10.3390/cancers11121877")])
    assert entry["url"] == "https://doi.org/10.3390/cancers11121877"


def test_publication_url_omitted_when_no_doi():
    [entry] = jsonresume_publications([_pub(doi=None)])
    assert "url" not in entry
```

- [ ] **Step 2: Run to verify they fail**

Run: `pytest tests/test_render_jsonresume.py -k url -v`
Expected: FAIL — `KeyError: 'url'`.

- [ ] **Step 3: Implement**

In `scripts/render_jsonresume.py`, replace the `_publications` function:

```python
def _publications(pubs: list[Publication]) -> list[dict]:
    out = []
    for p in pubs:
        entry = {
            "name": p.title,
            "publisher": p.venue or "",
            "releaseDate": f"{p.year}-01-01",
            "summary": ", ".join(p.authors),
        }
        if p.doi:
            entry["url"] = f"https://doi.org/{p.doi}"
        out.append(entry)
    return out
```

- [ ] **Step 4: Run to verify they pass + schema still validates**

Run: `pytest tests/test_render_jsonresume.py -v`
Expected: PASS, including `test_output_validates_against_schema_fixture` (`publications[].url` is a valid JSON Resume field).

- [ ] **Step 5: Commit**

```bash
git add scripts/render_jsonresume.py tests/test_render_jsonresume.py
git commit -m "feat: populate publications[].url from DOI in JSON Resume"
```

---

## Task 4: JSON-LD — `sameAs` on `ScholarlyArticle` from DOI

**Files:**
- Modify: `scripts/render_jsonld.py`
- Test: `tests/test_render_jsonld.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_render_jsonld.py`:

```python
from scripts.render_jsonld import _publications as jsonld_publications
from scripts.bib_loader import Publication


def _pub(**over) -> Publication:
    base = dict(
        key="x", title="T", year=2019, type="article", authorship="first",
        authors=("Lee, J.",), venue="Cancers", doi=None, raw={},
    )
    base.update(over)
    return Publication(**base)


def test_scholarly_article_sameas_is_doi():
    [item] = jsonld_publications([_pub(doi="10.3390/cancers11121877")])
    assert item["sameAs"] == ["https://doi.org/10.3390/cancers11121877"]


def test_scholarly_article_no_sameas_without_doi():
    [item] = jsonld_publications([_pub(doi=None)])
    assert "sameAs" not in item
```

- [ ] **Step 2: Run to verify they fail**

Run: `pytest tests/test_render_jsonld.py -k sameas -v`
Expected: FAIL — `KeyError: 'sameAs'`.

- [ ] **Step 3: Implement**

In `scripts/render_jsonld.py`, replace the `_publications` function:

```python
def _publications(pubs: list[Publication]) -> list[dict]:
    out = []
    for p in pubs:
        item: dict = {
            "@type": "ScholarlyArticle",
            "name": p.title,
            "datePublished": str(p.year),
            "author": [{"@type": "Person", "name": a} for a in p.authors],
        }
        if p.venue:
            item["isPartOf"] = {"@type": "Periodical", "name": p.venue}
        if p.doi:
            item["sameAs"] = [f"https://doi.org/{p.doi}"]
        out.append(item)
    return out
```

- [ ] **Step 4: Run to verify they pass**

Run: `pytest tests/test_render_jsonld.py -v`
Expected: PASS (the Person-level `test_sameas_includes_github` is unaffected — that asserts on `doc["sameAs"]`, not the article nodes).

- [ ] **Step 5: Commit**

```bash
git add scripts/render_jsonld.py tests/test_render_jsonld.py
git commit -m "feat: add DOI as sameAs on ScholarlyArticle in JSON-LD"
```

---

## Task 5: Website — TypeScript type + publications component

No pytest harness exists for Astro/TS (documented gap in the spec). Verification is type-check + build + visual.

**Files:**
- Modify: `web/src/types/content.ts`
- Modify: `web/src/components/PublicationsList.astro`

- [ ] **Step 1: Add `doi` to the `Publication` interface**

In `web/src/types/content.ts`, update the `Publication` interface to add `doi` after `venue`:

```typescript
export interface Publication {
  key: string;
  title: string;
  year: number;
  type: PublicationType;
  authorship: AuthorshipType;
  authors: string[];
  venue: string | null;
  doi: string | null;
}
```

- [ ] **Step 2: Render the DOI link on the meta line**

In `web/src/components/PublicationsList.astro`, replace the meta `<p>` (the `text-neutral-500` line inside the `<li>`):

```astro
            <p class="text-xs text-neutral-500">
              {p.venue ? `${p.venue} · ` : ""}{p.year} · {p.authorship}
              {p.doi && (
                <> · <a
                  href={`https://doi.org/${p.doi}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  class="underline decoration-dotted underline-offset-2 hover:text-neutral-800"
                >{p.doi}</a></>
              )}
            </p>
```

- [ ] **Step 3: Build the site to verify types + compile**

Run: `just web-build`
Expected: build succeeds with no TypeScript errors. (Before real DOIs land, no link renders yet — the value is `null` for every entry. This step proves the `p.doi` access type-checks and the component compiles; the rendered-link check happens in Task 6 Step 6.)

- [ ] **Step 4: Commit**

```bash
git add web/src/types/content.ts web/src/components/PublicationsList.astro
git commit -m "feat: surface DOI link on website publications list"
```

---

## Task 6: Content — look up, verify, and write real DOIs

This is the bulk of the work and the only task with a human gate (spec Decision 1: "look up, you verify"). It is NOT fully autonomous.

**Files:**
- Modify: `content/publications.bib`

- [ ] **Step 1: Gather candidate DOIs**

Read the author's ORCID id from `content/personal.yaml` (`links.orcid`). Fetch the public works list:

Run (WebFetch): `https://pub.orcid.org/v3.0/<ORCID-ID>/works` with header `Accept: application/json` — this lists the author's registered works with their DOIs (authoritative).

For any `publications.bib` entry not matched in ORCID, query Crossref by title:

Run (WebFetch): `https://api.crossref.org/works?query.bibliographic=<url-encoded title>&rows=3` and match on title + author + year.

- [ ] **Step 2: Present the verification table to the user**

Build and show a table — do NOT write anything yet:

| key | title (short) | proposed DOI | confidence | source |
|-----|---------------|--------------|------------|--------|

Expected to legitimately have NO DOI (leave the field absent): `lee2021_degbs`, `lee2019_conrad`, `lee2018_dro` (conference talks), `lee2025_marketing_automation` (self-published). Best-effort / accept absence if none found: `lee2019_combofish` (OBM Genetics), `lee2021superres_dna_repair` (2021 book chapter).

**Wait for the user to confirm / correct every row before proceeding.** Only confirmed DOIs get written. Never invent a DOI (spec non-goal #1).

- [ ] **Step 3: Write the confirmed DOIs into `content/publications.bib`**

For each confirmed entry, add a `doi` field (bare `10.xxxx/...` form). Example shape — the DOI value shown is an **illustrative placeholder; use the value the user confirmed in Step 2, never this literal**:

```bibtex
@article{scherthan2019_ra223,
  author     = {Scherthan, H. and Lee, J. and others},
  title      = {Nanostructure of Clustered {DNA} Damage in Leukocytes after In-Solution Irradiation with the Alpha Emitter {Ra-223}},
  journal    = {Cancers},
  volume     = {11},
  number     = {12},
  year       = {2019},
  type       = {article},
  authorship = {shared},
  doi        = {10.XXXX/CONFIRMED-VALUE-FROM-STEP-2}
}
```

- [ ] **Step 4: Validate, test, lint**

Run: `just validate && just test && just lint`
Expected: PASS. The format guard from Task 1 catches any typo'd DOI here; fix and re-run if it fires.

- [ ] **Step 5: Regenerate machine formats and confirm DOIs appear**

Run: `just build-formats && just build-text`
Then confirm the resolver URLs are present:

Run: `grep -c "doi.org" dist/resume.json dist/person.jsonld dist/cv-en.txt dist/cv-de.txt`
Expected: a non-zero count in each (equal to the number of DOI-bearing entries; `resume.json`/`person.jsonld` count once per entry, the text files once per entry per language file).

- [ ] **Step 6: Build the website and visually confirm the link**

Run: `just web-build`
Then inspect a built publications page for the rendered link:

Run: `grep -o 'https://doi.org/[^"]*' web/dist/index.html | head`
Expected: DOI resolver URLs present in the built HTML. Optionally open `web/dist/index.html` and confirm each DOI-bearing entry shows a clickable DOI on its meta line and DOI-less entries show none.

- [ ] **Step 7: Verify the issue's "Done when" checklist**

Confirm each spec/issue criterion: bib has DOIs on DOI-bearing entries (absent otherwise); site renders clickable DOI links; `dist/cv-{en,de}.txt` include DOI URLs; `dist/resume.json` has `publications[].url`; `dist/person.jsonld` has `sameAs` on each DOI-bearing `ScholarlyArticle`; `just validate && just test && just lint` green.

- [ ] **Step 8: Commit**

```bash
git add content/publications.bib
git commit -m "content: add DOIs to publications.bib (#26)"
```

---

## After all tasks

`just validate && just test && just lint` must be green. Then use **superpowers:finishing-a-development-branch** to open the PR (verify the issue's Test-plan/Done-when boxes are ticked in the PR body before considering it done). Because the branch was created with `gh issue develop`, the PR auto-links to #26 and closing the PR closes the issue.
