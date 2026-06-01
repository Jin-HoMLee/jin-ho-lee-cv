# Issue #44 — JSON-LD hardening — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Restructure `person.jsonld` into a top-level `@graph` of `@id`-linked schema.org entities — dedupe `alumniOf`, drop `worksFor`, add ORCID/DOI `identifier`, add `hasOccupation`, replace the 45-item `knowsAbout` with a curated content list.

**Architecture:** `to_jsonld` returns `{"@context", "@graph": [Person, …ScholarlyArticle, …CreativeWork]}`. The Person `@id` is the ORCID URI; works link back via `author`/`creator: {"@id": orcid}`. `knowsAbout` becomes a curated `content/personal.yaml` field (schema-validated).

**Tech Stack:** Python (`scripts/render_jsonld.py`), JSON Schema, ruamel.yaml, pytest, syrupy (snapshot re-baseline).

**Spec:** `docs/superpowers/specs/2026-06-01-issue-44-jsonld-hardening-design.md`

---

## Files

- Modify: `content/personal.yaml` (add `knowsAbout`) — Task 1
- Modify: `schema/cv.schema.json` (`personal.properties.knowsAbout`) — Task 1
- Modify: `scripts/render_jsonld.py` (restructure) — Task 2
- Modify: `tests/test_render_jsonld.py` (update broken tests, remove `_works_for` tests, add new-shape tests) — Task 2
- Modify: `tests/__snapshots__/test_snapshots/test_person_jsonld.json` (re-baseline) — Task 3

---

### Task 1: Curated `knowsAbout` content field + schema

- [ ] **Step 1: Add the field to `content/personal.yaml`**

Append a top-level `knowsAbout` list (after `links`/`photo`, before `variants`):
```yaml
knowsAbout:
  - Bioinformatics
  - Cancer Genomics
  - Computational Biology
  - Data Science
  - Machine Learning
  - Next-Generation Sequencing
  - RNA-Seq Analysis
  - Variant Calling
  - HLA Typing
  - Neoantigen Discovery
  - Immunoinformatics
  - Super-Resolution Microscopy
  - Spatial Point-Pattern Analysis
  - Cloud Data Engineering
  - Bioimage Analysis
```

- [ ] **Step 2: Run validate — verify it FAILS (additionalProperties)**

Run: `just validate`
Expected: FAIL — `personal.yaml` has unexpected `knowsAbout` (schema `personal` is `additionalProperties: false`).

- [ ] **Step 3: Add `knowsAbout` to the schema `personal` definition**

In `schema/cv.schema.json`, inside `$defs.personal.properties`, add (e.g. after the `photo` property):
```json
"knowsAbout": {
  "type": "array",
  "items": { "type": "string", "minLength": 1 },
  "minItems": 1
},
```
(Leave `knowsAbout` OUT of `personal.required` — optional, so other fixtures stay valid.)

- [ ] **Step 4: Run validate — verify it PASSES**

Run: `just validate`
Expected: `OK: all content files validate`.

- [ ] **Step 5: Commit**

```bash
git add content/personal.yaml schema/cv.schema.json
git commit -m "feat(content): #44 add curated knowsAbout topics + schema field"
```

---

### Task 2: Restructure `render_jsonld.py` to a top-level `@graph`

**Files:** `scripts/render_jsonld.py`, `tests/test_render_jsonld.py`

- [ ] **Step 1: Write/adjust the failing tests for the new shape**

In `tests/test_render_jsonld.py`:

(a) Add a Person-node helper near the top (after `CONTENT_DIR`):
```python
def _person_node(doc):
    return next(g for g in doc["@graph"] if g["@type"] == "Person")
```

(b) **Update** these tests to read the Person node from `@graph` instead of the root:
```python
def test_graph_has_one_person(doc):
    persons = [g for g in doc["@graph"] if g["@type"] == "Person"]
    assert len(persons) == 1


def test_person_id_is_orcid(doc):
    content = resolve_langstrings(load_content(CONTENT_DIR, lang="en"), lang="en")
    assert _person_node(doc)["@id"] == content["personal"]["links"]["orcid"]


def test_root_has_only_context_and_graph(doc):
    assert set(doc.keys()) == {"@context", "@graph"}


def test_alumni_deduped(doc):
    names = [a["name"] for a in _person_node(doc)["alumniOf"]]
    assert len(names) == len(set(names)), f"duplicate alumniOf: {names}"


def test_no_works_for(doc):
    assert "worksFor" not in _person_node(doc)


def test_person_identifier_is_orcid(doc):
    content = resolve_langstrings(load_content(CONTENT_DIR, lang="en"), lang="en")
    ident = _person_node(doc)["identifier"]
    assert ident["@type"] == "PropertyValue" and ident["propertyID"] == "ORCID"
    assert ident["value"] == content["personal"]["links"]["orcid"]


def test_has_occupation_from_headline(doc):
    names = [o["name"] for o in _person_node(doc)["hasOccupation"]]
    assert names == ["Bioinformatics", "Data Science"]


def test_knows_about_is_curated_content(doc):
    content = resolve_langstrings(load_content(CONTENT_DIR, lang="en"), lang="en")
    assert _person_node(doc)["knowsAbout"] == content["personal"]["knowsAbout"]
```
Replace the OLD root-based tests with Person-node equivalents:
```python
def test_sameas_includes_github(doc):
    assert any("github.com" in url for url in _person_node(doc)["sameAs"])


def test_image_is_absolute_url(doc):
    assert _person_node(doc)["image"].startswith("https://")


def test_url_uses_pages_base(doc):
    from scripts.config import PAGES_BASE_URL
    assert _person_node(doc)["url"].startswith(PAGES_BASE_URL)


def test_image_uses_pages_base(doc):
    from scripts.config import PAGES_BASE_URL
    assert _person_node(doc)["image"].startswith(PAGES_BASE_URL)


def test_orcid_and_website_in_same_as(doc):
    same_as = _person_node(doc)["sameAs"]
    assert "https://orcid.org/0009-0001-8784-1771" in same_as
    assert "https://jinholee.is-a.dev/" in same_as


def test_person_award_present(doc):
    award = _person_node(doc)["award"]
    assert "DAAD PROMOS Scholarship" in award
    assert "DeGBS Poster Award" in award
```
**Delete** `test_type_is_person`, `test_alumni_count_matches_education`, and the entire `# --- #42: period-end edge cases (characterization of _works_for selection) ---` block (`_works_for` import, `_content`, `test_works_for_picks_null_end_entry`, `test_works_for_none_when_all_dated`).

(c) `_publications` gains a `person_id` arg — update its two direct tests + add new assertions:
```python
def test_scholarly_article_sameas_is_doi():
    [item] = jsonld_publications([_pub(doi="10.3390/cancers11121877")], "https://orcid.org/X")
    assert item["sameAs"] == ["https://doi.org/10.3390/cancers11121877"]


def test_scholarly_article_no_sameas_without_doi():
    [item] = jsonld_publications([_pub(doi=None)], "https://orcid.org/X")
    assert "sameAs" not in item


def test_scholarly_article_doi_identifier_and_id():
    [item] = jsonld_publications([_pub(doi="10.3390/cancers11121877")], "https://orcid.org/X")
    assert item["@id"] == "https://doi.org/10.3390/cancers11121877"
    assert item["identifier"] == {"@type": "PropertyValue", "propertyID": "DOI", "value": "10.3390/cancers11121877"}


def test_scholarly_article_links_author_to_person():
    [item] = jsonld_publications([_pub(authors=("Lee, J.", "Hausmann, M."))], "https://orcid.org/X")
    assert {"@id": "https://orcid.org/X"} in item["author"]
    assert {"@type": "Person", "name": "Hausmann, M."} in item["author"]
```
(`test_graph_includes_project_creativeworks` and `test_creativework_urls_use_pages_base` still pass — projects keep `url`; just confirm `@id`/`creator` additionally. Optionally add:)
```python
def test_creativework_has_id_and_creator(doc):
    content = resolve_langstrings(load_content(CONTENT_DIR, lang="en"), lang="en")
    orcid = content["personal"]["links"]["orcid"]
    works = [g for g in doc["@graph"] if g["@type"] == "CreativeWork"]
    for w in works:
        assert w["@id"] == w["url"]
        assert w["creator"] == {"@id": orcid}
```

- [ ] **Step 2: Run — verify FAIL**

Run: `uv run pytest tests/test_render_jsonld.py -q`
Expected: many failures (root has no `@graph`-only shape; `_publications` arity mismatch; etc.). Red.

- [ ] **Step 3: Rewrite `scripts/render_jsonld.py`**

Replace helpers + `to_jsonld`:
```python
def _alumni_of(content: dict) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for e in content["education"]:
        inst = e["institution"]
        if inst not in seen:
            seen.add(inst)
            out.append({"@type": "EducationalOrganization", "name": inst})
    return out


def _knows_about(content: dict) -> list[str]:
    return list(content["personal"].get("knowsAbout", []))


def _has_occupation(content: dict) -> list[dict]:
    headline = content["personal"]["headline"]  # resolved to a str by this point
    return [{"@type": "Occupation", "name": part.strip()}
            for part in headline.split("·") if part.strip()]


def _publications(pubs: list[Publication], person_id: str) -> list[dict]:
    out = []
    for i, p in enumerate(pubs):
        doi_url = f"https://doi.org/{p.doi}" if p.doi else None
        item: dict = {
            "@type": "ScholarlyArticle",
            "@id": doi_url or f"{PAGES_BASE_URL}/#publication-{i}",
            "name": p.title,
            "datePublished": str(p.year),
            "author": [
                {"@id": person_id} if a.startswith("Lee, J") else {"@type": "Person", "name": a}
                for a in p.authors
            ],
        }
        if p.venue:
            item["isPartOf"] = {"@type": "Periodical", "name": p.venue}
        if p.doi:
            item["sameAs"] = [doi_url]
            item["identifier"] = {"@type": "PropertyValue", "propertyID": "DOI", "value": p.doi}
        out.append(item)
    return out


def _projects(content: dict, person_id: str) -> list[dict]:
    out = []
    for pid, proj in content["projects"].items():
        url = f"{PAGES_BASE_URL}/projects/{pid}/"
        out.append({
            "@type": "CreativeWork",
            "@id": url,
            "name": proj["title"],
            "url": url,
            "description": proj["summary"],
            "dateCreated": proj["period"]["start"],
            "keywords": list(proj.get("technologies", [])),
            "creator": {"@id": person_id},
        })
    return out


def _person(content: dict) -> dict:
    personal = content["personal"]
    profile = content["profile"]
    name = f"{personal['name']['given']} {personal['name']['family']}"
    orcid = personal["links"].get("orcid") or f"{SITE_URL}#person"
    person: dict = {
        "@type": "Person",
        "@id": orcid,
        "name": name,
        "url": SITE_URL,
        "image": PHOTO_URL,
        "email": f"mailto:{personal['email']}",
        "jobTitle": personal["headline"],
        "description": profile["paragraphs"][0],
        "address": {
            "@type": "PostalAddress",
            "addressLocality": personal["location"]["city"],
            "addressCountry": personal["location"]["country"],
        },
        "identifier": {"@type": "PropertyValue", "propertyID": "ORCID", "value": orcid},
        "sameAs": _same_as(personal),
        "alumniOf": _alumni_of(content),
        "knowsAbout": _knows_about(content),
        "hasOccupation": _has_occupation(content),
    }
    if content["awards"]:
        person["award"] = [a["title"] for a in content["awards"]]
    return person


def to_jsonld(content: dict, pubs: list[Publication]) -> dict:
    """Compose a schema.org @graph for AI/LLM entity resolution (NOT SEO rich results:
    Google surfaces no Person rich result and dropped EstimatedSalary in June 2025)."""
    person = _person(content)
    person_id = person["@id"]
    return {
        "@context": "https://schema.org",
        "@graph": [person, *_publications(pubs, person_id), *_projects(content, person_id)],
    }
```
**Delete** the now-unused `_works_for`. Keep `_same_as`, `_print_wrote`, `main` (main unchanged — it already writes `to_jsonld(...)`).

- [ ] **Step 4: Run — verify PASS**

Run: `uv run pytest tests/test_render_jsonld.py -q`
Expected: all pass.

- [ ] **Step 5: Lint**

Run: `uv run ruff check scripts/render_jsonld.py tests/test_render_jsonld.py`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add scripts/render_jsonld.py tests/test_render_jsonld.py
git commit -m "feat(jsonld): #44 top-level @graph of @id-linked entities; identifier, hasOccupation; dedupe alumniOf; drop worksFor"
```

---

### Task 3: Re-baseline the person.jsonld snapshot + eyeball

- [ ] **Step 1: Confirm the snapshot now drifts (expected)**

Run: `uv run pytest tests/test_snapshots.py::test_person_jsonld -q`
Expected: FAIL (the JSON-LD shape changed intentionally).

- [ ] **Step 2: Regenerate + eyeball**

```bash
just snapshots-update
git diff --stat tests/__snapshots__/test_snapshots/test_person_jsonld.json
```
Open `tests/__snapshots__/test_snapshots/test_person_jsonld.json` and confirm: a top-level `@graph`; Person node first with `@id` = ORCID, `identifier`, `hasOccupation` (Bioinformatics, Data Science), curated `knowsAbout` (15 items), deduped `alumniOf` (Heidelberg once), **no** `worksFor`; ScholarlyArticles with `@id`/DOI `identifier`/author `{"@id": orcid}`; CreativeWorks with `@id`/`creator`.

- [ ] **Step 3: Full gate**

```bash
just validate && just test && just lint
```
Expected: validate OK, all tests pass (incl. snapshot), lint clean.

- [ ] **Step 4: Commit**

```bash
git add tests/__snapshots__/test_snapshots/test_person_jsonld.json
git commit -m "test: #44 re-baseline person.jsonld golden snapshot for the new @graph shape"
```

- [ ] **Step 5: Tick issue #44 Scope boxes**

Verify each Scope box (refactor to @graph; dedupe alumniOf; deliberate worksFor decision = omit; ORCID + DOI identifier; hasOccupation + trimmed knowsAbout; docs reframe; #42 snapshot covers new shape) and tick via `gh issue edit 44 --body-file <file>`, with a verification comment noting the omit-worksFor decision and the curated knowsAbout.

---

## Notes for the executor

- **`headline` is resolved to a string** by `resolve_langstrings` before `to_jsonld` (so `.split("·")` is valid). The raw `personal.headline` is `{en, de}`, but `main()` resolves EN first.
- **`knowsAbout` is language-neutral** (technical proper terms) — one flat list, EN-only JSON-LD, no DE parity needed.
- **No web component change** — `web-build` copies `dist/person.jsonld`; a top-level `@graph` inlines fine in BaseLayout's `<script type="application/ld+json">`.
- **No CLAUDE.md change** — #44 adds no new convention and is a maintenance item (no phase row). The curated-`knowsAbout` content field is self-evident in `personal.yaml`.
- **Atomic commits**, no Claude attribution trailers.
