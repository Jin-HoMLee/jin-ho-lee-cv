# Phase 4: Machine Formats + Publications Chart — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship four small, independent CV artifacts — JSON Resume, JSON-LD (standalone + embedded), bilingual plain text, and an SVG authorship pie chart on the site — all auto-published on every push to `main`.

**Architecture:** Three new Python renderers reuse the existing `content_loader` + `bib_loader` + `langstring` modules and write to `dist/`. The JSON-LD output is also copied to `web/public/` so Astro inlines it into every page's `<head>`. The chart is a pure-SVG Astro component using the publications data already available in the site's content JSON. CI gains one `build-formats` job; pages.yml gains one render step before the Astro build.

**Tech Stack:** Python 3.12 + uv, pybtex, ruamel.yaml, jsonschema (test-only); Astro 5 + Tailwind 4; pnpm 10.

**Spec:** [`docs/superpowers/specs/2026-05-25-phase-4-machine-formats-design.md`](../specs/2026-05-25-phase-4-machine-formats-design.md)

---

## File Structure

**New Python:**
- `scripts/render_jsonresume.py` — renderer
- `scripts/render_jsonld.py` — renderer
- `scripts/render_text.py` — renderer
- `tests/test_render_jsonresume.py` — pytest
- `tests/test_render_jsonld.py` — pytest
- `tests/test_render_text.py` — pytest
- `tests/fixtures/jsonresume-schema.json` — vendored JSON Resume schema v1.0.0

**New web component:**
- `web/src/components/PublicationsChart.astro` — inline SVG pie

**Modified web:**
- `web/src/components/PublicationsList.astro` — render `<PublicationsChart>`
- `web/src/layouts/BaseLayout.astro` — inject `<script type="application/ld+json">`
- `web/.gitignore` — ignore generated `public/person.jsonld`

**Modified infrastructure:**
- `justfile` — `build-resume`, `build-jsonld`, `build-text`, plus `web-dev`/`web-build` gain a JSON-LD pre-step
- `.github/workflows/ci.yml` — new `build-formats` job; `release` job gains `needs: build-formats` + four new `files:` entries
- `.github/workflows/pages.yml` — one step to render JSON-LD and copy into `web/public/` before `pnpm build`
- `README.md` — "Machine formats" line
- `CLAUDE.md` — Phase 4 status flip + scripts list updated
- `pyproject.toml` — add `jsonschema` as a test dep (Task 2)

---

## Task 1: Set up phase branch + vendor JSON Resume schema

**Files:**
- Create: `tests/fixtures/jsonresume-schema.json`

- [ ] **Step 1: Create the phase branch from current `main` HEAD**

The current local `main` HEAD already contains the spec commit (`7bcde8b`). Branch from there so the spec ships with the phase PR.

```bash
git switch -c phase-4-machine-formats
git log --oneline -3
```
Expected: top commit is `7bcde8b docs: add Phase 4 machine formats + chart design spec`.

- [ ] **Step 2: Create the fixtures directory**

```bash
mkdir -p tests/fixtures
```

- [ ] **Step 3: Download and pin the JSON Resume schema (v1.0.0)**

```bash
curl -sL "https://raw.githubusercontent.com/jsonresume/resume-schema/v1.0.0/schema.json" \
  -o tests/fixtures/jsonresume-schema.json
```

- [ ] **Step 4: Verify the fixture is valid JSON and matches v1.0.0 shape**

```bash
python -c "import json; d=json.load(open('tests/fixtures/jsonresume-schema.json')); print('keys:', list(d.keys())); assert 'properties' in d; assert 'basics' in d['properties']"
```
Expected: prints `keys: [...]` including `properties`; no assertion error.

- [ ] **Step 5: Add jsonschema to the dev test deps in `pyproject.toml`**

Open `pyproject.toml` and locate the test-deps group (look for `[dependency-groups]` or `[tool.uv]` test group). Add `jsonschema>=4.0` to the test group. Then:

```bash
uv sync --all-groups
uv run python -c "import jsonschema; print(jsonschema.__version__)"
```
Expected: prints a version >= 4.0.

- [ ] **Step 6: Commit**

```bash
git add tests/fixtures/jsonresume-schema.json pyproject.toml uv.lock
git commit -m "test: vendor JSON Resume schema v1.0.0 + add jsonschema dep"
```

---

## Task 2: `scripts/render_jsonresume.py` (TDD)

**Files:**
- Create: `scripts/render_jsonresume.py`
- Create: `tests/test_render_jsonresume.py`

**Reference:** spec §5.1.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_render_jsonresume.py`:

```python
"""Pytest assertions for the JSON Resume renderer."""
from __future__ import annotations

import json
import re
from pathlib import Path

import jsonschema
import pytest

from scripts.bib_loader import load_publications
from scripts.content_loader import load_content
from scripts.langstring import resolve_langstrings
from scripts.render_jsonresume import to_jsonresume


REPO_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = REPO_ROOT / "content"
SCHEMA_PATH = REPO_ROOT / "tests" / "fixtures" / "jsonresume-schema.json"


@pytest.fixture(scope="module")
def doc() -> dict:
    content = resolve_langstrings(load_content(CONTENT_DIR, lang="en"), lang="en")
    pubs = load_publications(CONTENT_DIR / "publications.bib")
    return to_jsonresume(content, pubs)


def test_output_validates_against_schema_fixture(doc):
    schema = json.loads(SCHEMA_PATH.read_text())
    jsonschema.validate(instance=doc, schema=schema)


def test_basics_round_trip(doc):
    content = resolve_langstrings(load_content(CONTENT_DIR, lang="en"), lang="en")
    basics = doc["basics"]
    assert basics["name"] == f"{content['personal']['name']['given']} {content['personal']['name']['family']}"
    assert basics["email"] == content["personal"]["email"]
    assert basics["summary"]  # non-empty
    assert any(p["network"].lower() == "github" for p in basics["profiles"])


def test_all_experience_entries_present(doc):
    content = resolve_langstrings(load_content(CONTENT_DIR, lang="en"), lang="en")
    assert len(doc["work"]) == len(content["experience"])


def test_all_publications_present(doc):
    pubs = load_publications(CONTENT_DIR / "publications.bib")
    assert len(doc["publications"]) == len(pubs)


def test_dates_iso_8601(doc):
    iso = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    for entry in doc["work"] + doc.get("education", []):
        if "startDate" in entry:
            assert iso.match(entry["startDate"]), f"bad startDate: {entry['startDate']!r}"
        if "endDate" in entry:
            assert iso.match(entry["endDate"]), f"bad endDate: {entry['endDate']!r}"


def test_skills_flattened_from_categories(doc):
    """Each (category, group) pair becomes one entry in flat skills[]."""
    content = resolve_langstrings(load_content(CONTENT_DIR, lang="en"), lang="en")
    expected_count = sum(len(cat["groups"]) for cat in content["skills"]["categories"])
    assert len(doc["skills"]) == expected_count
```

- [ ] **Step 2: Run tests to verify they fail with ImportError**

```bash
uv run pytest tests/test_render_jsonresume.py -v
```
Expected: `ImportError` or `ModuleNotFoundError` on `from scripts.render_jsonresume import to_jsonresume`.

- [ ] **Step 3: Implement `scripts/render_jsonresume.py`**

```python
"""Render the CV to a JSON Resume document (https://jsonresume.org/schema/)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.bib_loader import Publication, load_publications
from scripts.content_loader import load_content
from scripts.langstring import resolve_langstrings


REPO_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = REPO_ROOT / "content"
SITE_URL = "https://jin-homlee.github.io/jin-ho-lee-cv/"


def _pad_start(yyyy_mm: str) -> str:
    """'2024-05' → '2024-05-01' (ISO 8601 calendar date)."""
    return f"{yyyy_mm}-01"


def _pad_end(yyyy_mm: str | None) -> str | None:
    """'2024-05' → '2024-05-28' (28 is safe in every month). None passes through."""
    return f"{yyyy_mm}-28" if yyyy_mm else None


def _network_for(key: str) -> str:
    return {
        "linkedin":     "LinkedIn",
        "github":       "GitHub",
        "researchgate": "ResearchGate",
        "orcid":        "ORCID",
    }.get(key, key.title())


def _basics(content: dict) -> dict:
    personal = content["personal"]
    profile = content["profile"]
    name = f"{personal['name']['given']} {personal['name']['family']}"
    profiles = [
        {"network": _network_for(k), "url": v}
        for k, v in (personal.get("links") or {}).items()
        if v
    ]
    return {
        "name": name,
        "label": personal["headline"],
        "email": personal["email"],
        "url": SITE_URL,
        "summary": "\n\n".join(profile["paragraphs"]),
        "location": {
            "city": personal["location"]["city"],
            "countryCode": personal["location"]["country"],
        },
        "profiles": profiles,
    }


def _work(content: dict) -> list[dict]:
    out = []
    for exp in content["experience"]:
        out.append({
            "name": exp["org"]["name"],
            "position": exp["role"],
            "startDate": _pad_start(exp["period"]["start"]),
            **({"endDate": _pad_end(exp["period"]["end"])} if exp["period"].get("end") else {}),
            "summary": " ".join(b["en"] for b in exp["bullets"]) if exp.get("bullets") else "",
            "highlights": [b["en"] for b in exp.get("bullets", [])],
        })
    return out


def _education(content: dict) -> list[dict]:
    out = []
    for edu in content["education"]:
        year = str(edu["year"])
        out.append({
            "institution": edu["institution"],
            "studyType": edu["degree"],
            "area": "",
            "startDate": f"{year}-01-01",
            "endDate": f"{year}-12-31",
        })
    return out


def _skills(content: dict) -> list[dict]:
    out = []
    for cat in content["skills"]["categories"]:
        for grp in cat["groups"]:
            out.append({
                "name": cat["name"],
                "level": grp["label"],
                "keywords": list(grp["items"]),
            })
    return out


def _languages(content: dict) -> list[dict]:
    return [
        {"language": lang["name"], "fluency": lang["proficiency"]}
        for lang in content["languages"]
    ]


def _volunteer(content: dict) -> list[dict]:
    out = []
    for cat in content["volunteer"]["categories"]:
        for entry in cat["entries"]:
            out.append({
                "organization": entry,
                "position": cat["name"],
            })
    return out


def _projects(content: dict) -> list[dict]:
    out = []
    for pid, proj in content["projects"].items():
        out.append({
            "name": proj["title"],
            "description": proj["summary"],
            "highlights": list(proj.get("contributions", [])),
            "keywords": list(proj.get("technologies", [])),
            "startDate": _pad_start(proj["period"]["start"]),
            "endDate": _pad_end(proj["period"]["end"]) or _pad_start(proj["period"]["start"]),
            "roles": [proj["role"]],
        })
    return out


def _publications(pubs: list[Publication]) -> list[dict]:
    return [
        {
            "name": p.title,
            "publisher": p.venue or "",
            "releaseDate": f"{p.year}-01-01",
            "summary": ", ".join(p.authors),
        }
        for p in pubs
    ]


def to_jsonresume(content: dict, pubs: list[Publication]) -> dict:
    """Compose the full JSON Resume document."""
    return {
        "$schema": "https://jsonresume.org/schema/0.0.0/resume.json",
        "basics": _basics(content),
        "work": _work(content),
        "education": _education(content),
        "skills": _skills(content),
        "languages": _languages(content),
        "volunteer": _volunteer(content),
        "projects": _projects(content),
        "publications": _publications(pubs),
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "dist" / "resume.json",
        help="Output path (default: dist/resume.json)",
    )
    args = parser.parse_args(argv)

    content = resolve_langstrings(load_content(CONTENT_DIR, lang="en"), lang="en")
    pubs = load_publications(CONTENT_DIR / "publications.bib")
    doc = to_jsonresume(content, pubs)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {args.output.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_render_jsonresume.py -v
```
Expected: 6 passed.

- [ ] **Step 5: Run the CLI end-to-end and inspect**

```bash
uv run python -m scripts.render_jsonresume
ls -la dist/resume.json
python -c "import json; d=json.load(open('dist/resume.json')); print(list(d.keys())); print('basics.name:', d['basics']['name']); print('work entries:', len(d['work'])); print('publications:', len(d['publications']))"
```
Expected: `dist/resume.json` exists; keys include `basics`, `work`, `education`, `skills`, `languages`, `volunteer`, `projects`, `publications`; counts match real content (work=3, publications=15).

- [ ] **Step 6: Sanity-grep for PII (phone, full address)**

```bash
grep -E "\+49|phone|street|hausnummer|strasse" dist/resume.json && echo "FAIL: PII leaked" || echo "OK: no PII"
```
Expected: `OK: no PII`.

- [ ] **Step 7: Run full pytest + lint**

```bash
uv run pytest -v 2>&1 | tail -5
uv run ruff check .
```
Expected: all green.

- [ ] **Step 8: Commit**

```bash
git add scripts/render_jsonresume.py tests/test_render_jsonresume.py
git commit -m "feat(jsonresume): render dist/resume.json from content/ (TDD)"
```

---

## Task 3: `scripts/render_jsonld.py` (TDD)

**Files:**
- Create: `scripts/render_jsonld.py`
- Create: `tests/test_render_jsonld.py`

**Reference:** spec §5.2.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_render_jsonld.py`:

```python
"""Pytest assertions for the JSON-LD renderer."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.bib_loader import load_publications
from scripts.content_loader import load_content
from scripts.langstring import resolve_langstrings
from scripts.render_jsonld import to_jsonld


REPO_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = REPO_ROOT / "content"


@pytest.fixture(scope="module")
def doc() -> dict:
    content = resolve_langstrings(load_content(CONTENT_DIR, lang="en"), lang="en")
    pubs = load_publications(CONTENT_DIR / "publications.bib")
    return to_jsonld(content, pubs)


def test_output_valid_json(doc):
    json.dumps(doc)  # raises if non-serialisable


def test_has_schema_context(doc):
    assert doc["@context"] == "https://schema.org"


def test_type_is_person(doc):
    assert doc["@type"] == "Person"


def test_publications_count_matches_bib(doc):
    pubs = load_publications(CONTENT_DIR / "publications.bib")
    articles = [g for g in doc.get("@graph", []) if g["@type"] == "ScholarlyArticle"]
    assert len(articles) == len(pubs)


def test_alumni_count_matches_education(doc):
    content = resolve_langstrings(load_content(CONTENT_DIR, lang="en"), lang="en")
    assert len(doc["alumniOf"]) == len(content["education"])


def test_no_pii_in_output(doc):
    """`load_content` is hard-coded to private_path=None — no phone, no full address."""
    text = json.dumps(doc).lower()
    assert "phone" not in text
    assert "telephone" not in text
    # Street keywords (German + English)
    for kw in ("strasse", "straße", "street ", "hausnummer"):
        assert kw not in text, f"unexpected PII keyword in output: {kw!r}"


def test_sameas_includes_github(doc):
    assert any("github.com" in url for url in doc.get("sameAs", []))


def test_image_is_absolute_url(doc):
    assert doc["image"].startswith("https://")
```

- [ ] **Step 2: Run tests to verify they fail with ImportError**

```bash
uv run pytest tests/test_render_jsonld.py -v
```
Expected: `ImportError` on `from scripts.render_jsonld import to_jsonld`.

- [ ] **Step 3: Implement `scripts/render_jsonld.py`**

```python
"""Render the CV as schema.org Person JSON-LD."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.bib_loader import Publication, load_publications
from scripts.content_loader import load_content
from scripts.langstring import resolve_langstrings


REPO_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = REPO_ROOT / "content"
SITE_URL = "https://jin-homlee.github.io/jin-ho-lee-cv/"
PHOTO_URL = f"{SITE_URL}photo.jpg"


def _same_as(personal: dict) -> list[str]:
    return [v for v in (personal.get("links") or {}).values() if v]


def _alumni_of(content: dict) -> list[dict]:
    return [
        {"@type": "EducationalOrganization", "name": e["institution"]}
        for e in content["education"]
    ]


def _knows_about(content: dict) -> list[str]:
    out: list[str] = []
    for cat in content["skills"]["categories"]:
        for grp in cat["groups"]:
            out.extend(grp["items"])
    return out


def _works_for(content: dict) -> dict | None:
    """First experience entry whose period.end is null is the current employer."""
    for exp in content["experience"]:
        if exp["period"].get("end") in (None, "present"):
            return {"@type": "Organization", "name": exp["org"]["name"]}
    return None


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
        out.append(item)
    return out


def to_jsonld(content: dict, pubs: list[Publication]) -> dict:
    """Compose the schema.org Person JSON-LD document."""
    personal = content["personal"]
    profile = content["profile"]
    name = f"{personal['name']['given']} {personal['name']['family']}"

    doc: dict = {
        "@context": "https://schema.org",
        "@type": "Person",
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
        "sameAs": _same_as(personal),
        "alumniOf": _alumni_of(content),
        "knowsAbout": _knows_about(content),
    }
    if (works_for := _works_for(content)) is not None:
        doc["worksFor"] = works_for

    doc["@graph"] = _publications(pubs)
    return doc


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "dist" / "person.jsonld",
        help="Output path (default: dist/person.jsonld)",
    )
    args = parser.parse_args(argv)

    content = resolve_langstrings(load_content(CONTENT_DIR, lang="en"), lang="en")
    pubs = load_publications(CONTENT_DIR / "publications.bib")
    doc = to_jsonld(content, pubs)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {args.output.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_render_jsonld.py -v
```
Expected: 8 passed.

- [ ] **Step 5: Run the CLI and inspect**

```bash
uv run python -m scripts.render_jsonld
python -c "import json; d=json.load(open('dist/person.jsonld')); print('@type:', d['@type']); print('alumni:', [a['name'] for a in d['alumniOf']]); print('graph entries:', len(d['@graph']))"
```
Expected: `@type: Person`, alumni list = 2 institutions, graph entries = 15.

- [ ] **Step 6: Run full pytest + lint**

```bash
uv run pytest -v 2>&1 | tail -5
uv run ruff check .
```
Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add scripts/render_jsonld.py tests/test_render_jsonld.py
git commit -m "feat(jsonld): render dist/person.jsonld schema.org Person doc (TDD)"
```

---

## Task 4: `scripts/render_text.py` (TDD, bilingual)

**Files:**
- Create: `scripts/render_text.py`
- Create: `tests/test_render_text.py`

**Reference:** spec §5.3.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_render_text.py`:

```python
"""Pytest assertions for the plain-text renderer."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from scripts.render_text import render


REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def en_text() -> str:
    return render(lang="en")


@pytest.fixture(scope="module")
def de_text() -> str:
    return render(lang="de")


def test_en_and_de_differ(en_text, de_text):
    """Sanity: the two outputs are not byte-identical (something localised differently)."""
    assert en_text != de_text


def test_section_headers_present_en(en_text):
    for section in ("PROFILE", "EXPERIENCE", "EDUCATION", "SKILLS", "LANGUAGES", "VOLUNTEER", "PUBLICATIONS"):
        assert section in en_text, f"missing section header: {section}"


def test_section_headers_present_de(de_text):
    # uppercase translations from labels.yaml
    for section in ("PROFIL", "BERUFSERFAHRUNG", "AUSBILDUNG", "KENNTNISSE", "SPRACHEN", "EHRENAMTLICH", "PUBLIKATIONEN"):
        assert section in de_text, f"missing section header: {section}"


def test_no_markdown_chars(en_text, de_text):
    for body in (en_text, de_text):
        for forbidden in ("**", "__", "`", "[", "]("):
            assert forbidden not in body, f"markdown char in plain text: {forbidden!r}"


def test_email_present(en_text):
    assert "@" in en_text


def test_phone_excluded_when_public(en_text, de_text):
    """`load_content` is hard-coded to private_path=None — no phone."""
    for body in (en_text, de_text):
        assert not re.search(r"\+\d{1,3}[\s\d]{6,}", body), "looks like a phone number"


def test_section_divider_is_80_eq(en_text):
    assert "=" * 80 in en_text


def test_no_trailing_whitespace(en_text, de_text):
    for body in (en_text, de_text):
        for i, line in enumerate(body.splitlines(), start=1):
            assert line == line.rstrip(), f"trailing whitespace on line {i}"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_render_text.py -v
```
Expected: `ImportError` on `from scripts.render_text import render`.

- [ ] **Step 3: Implement `scripts/render_text.py`**

```python
"""Render the CV as section-headed ATS-friendly plain text."""
from __future__ import annotations

import argparse
import textwrap
from pathlib import Path

from scripts.bib_loader import Publication, load_publications
from scripts.content_loader import load_content
from scripts.langstring import resolve_langstrings


REPO_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = REPO_ROOT / "content"
SITE_URL = "https://jin-homlee.github.io/jin-ho-lee-cv/"
DIVIDER = "=" * 80
SECTION_LABELS = {
    "profile":      {"en": "PROFILE",      "de": "PROFIL"},
    "experience":   {"en": "EXPERIENCE",   "de": "BERUFSERFAHRUNG"},
    "education":    {"en": "EDUCATION",    "de": "AUSBILDUNG"},
    "skills":       {"en": "SKILLS",       "de": "KENNTNISSE"},
    "languages":    {"en": "LANGUAGES",    "de": "SPRACHEN"},
    "volunteer":    {"en": "VOLUNTEER",    "de": "EHRENAMTLICH"},
    "publications": {"en": "PUBLICATIONS", "de": "PUBLIKATIONEN"},
}
PRESENT = {"en": "present", "de": "heute"}


def _wrap(paragraph: str, width: int = 80) -> str:
    """Wrap a paragraph at `width` columns. Leaves lines with URLs un-wrapped."""
    if "http" in paragraph:
        return paragraph
    return "\n".join(textwrap.wrap(paragraph, width=width)) or paragraph


def _section(name: str, body: str) -> str:
    return f"{DIVIDER}\n{name}\n{DIVIDER}\n{body}".rstrip()


def _header(content: dict) -> str:
    personal = content["personal"]
    name = f"{personal['name']['given']} {personal['name']['family']}"
    location = f"{personal['location']['city']}, {personal['location']['country']}"
    links = [personal["email"], SITE_URL]
    links.extend(v for v in (personal.get("links") or {}).values() if v)
    return f"{name.upper()}\n{personal['headline']} - {location}\n" + " | ".join(links)


def _profile(content: dict) -> str:
    return "\n\n".join(_wrap(p) for p in content["profile"]["paragraphs"])


def _experience(content: dict, lang: str) -> str:
    out: list[str] = []
    for exp in content["experience"]:
        period_end = exp["period"].get("end") or PRESENT[lang]
        title_line = f"{exp['role']} - {exp['org']['name']}".strip()
        period_line = f"{exp['period']['start']} to {period_end}"
        block = [f"{title_line}    [{period_line}]"]
        for b in exp.get("bullets", []):
            block.append(f"  - {b[lang]}")
        out.append("\n".join(block))
    return "\n\n".join(out)


def _education(content: dict) -> str:
    return "\n".join(
        f"{e['year']}  {e['degree']} - {e['institution']} ({e['location']})"
        for e in content["education"]
    )


def _skills(content: dict) -> str:
    out: list[str] = []
    for cat in content["skills"]["categories"]:
        out.append(cat["name"])
        for grp in cat["groups"]:
            items = ", ".join(grp["items"])
            out.append(f"  {grp['label']}: {items}")
    return "\n".join(out)


def _languages(content: dict) -> str:
    return "\n".join(f"  {lang['name']}: {lang['proficiency']}" for lang in content["languages"])


def _volunteer(content: dict) -> str:
    out: list[str] = []
    for cat in content["volunteer"]["categories"]:
        out.append(cat["name"])
        for entry in cat["entries"]:
            out.append(f"  - {entry}")
    return "\n".join(out)


def _publications(pubs: list[Publication]) -> str:
    out: list[str] = []
    for p in pubs:
        authors = ", ".join(p.authors)
        venue = f" - {p.venue}" if p.venue else ""
        out.append(f"{p.year}  {p.title}\n  {authors}{venue}")
    return "\n\n".join(out)


def render(lang: str) -> str:
    """Return the full plain-text CV for the given language."""
    content = resolve_langstrings(load_content(CONTENT_DIR, lang=lang), lang=lang)
    pubs = load_publications(CONTENT_DIR / "publications.bib")
    L = SECTION_LABELS

    sections = [
        _header(content),
        _section(L["profile"][lang],      _profile(content)),
        _section(L["experience"][lang],   _experience(content, lang)),
        _section(L["education"][lang],    _education(content)),
        _section(L["skills"][lang],       _skills(content)),
        _section(L["languages"][lang],    _languages(content)),
        _section(L["volunteer"][lang],    _volunteer(content)),
        _section(L["publications"][lang], _publications(pubs)),
    ]
    return "\n\n".join(sections) + "\n"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lang", choices=("en", "de"), required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output path (default: dist/cv-{lang}.txt)",
    )
    args = parser.parse_args(argv)

    output = args.output or REPO_ROOT / "dist" / f"cv-{args.lang}.txt"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render(args.lang), encoding="utf-8")
    print(f"wrote {output.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_render_text.py -v
```
Expected: 8 passed.

- [ ] **Step 5: Generate both languages and inspect**

```bash
uv run python -m scripts.render_text --lang en
uv run python -m scripts.render_text --lang de
ls -la dist/cv-en.txt dist/cv-de.txt
head -30 dist/cv-en.txt
echo "---"
head -30 dist/cv-de.txt
```
Expected: both files exist; EN starts with `JIN-HO LEE`; DE starts the same but section headers are German.

- [ ] **Step 6: Sanity-grep for PII**

```bash
grep -E "\+49|phone|street|strasse" dist/cv-en.txt dist/cv-de.txt && echo "FAIL: PII leaked" || echo "OK: no PII"
```
Expected: `OK: no PII`.

- [ ] **Step 7: Run full pytest + lint**

```bash
uv run pytest -v 2>&1 | tail -5
uv run ruff check .
```
Expected: all green.

- [ ] **Step 8: Commit**

```bash
git add scripts/render_text.py tests/test_render_text.py
git commit -m "feat(text): render bilingual dist/cv-{en,de}.txt (TDD)"
```

---

## Task 5: Add justfile recipes

**Files:**
- Modify: `justfile`

- [ ] **Step 1: Append new recipes to `justfile`**

Open `justfile` and append at the end (before any pre-existing `clean` recipe — `clean` already wipes `dist/`, no change needed):

```just

# Render JSON Resume → dist/resume.json
build-resume:
    uv run python -m scripts.render_jsonresume

# Render schema.org JSON-LD → dist/person.jsonld
build-jsonld:
    uv run python -m scripts.render_jsonld

# Render plain text in both languages → dist/cv-{en,de}.txt
build-text:
    uv run python -m scripts.render_text --lang en
    uv run python -m scripts.render_text --lang de

# Build every Phase 4 machine format (resume.json + person.jsonld + plain text)
build-formats: build-resume build-jsonld build-text
```

- [ ] **Step 2: Verify each recipe works**

```bash
just build-resume
just build-jsonld
just build-text
ls dist/resume.json dist/person.jsonld dist/cv-en.txt dist/cv-de.txt
```
Expected: 4 files exist.

- [ ] **Step 3: Verify the umbrella recipe builds all four**

```bash
just clean
just build-formats
ls dist/
```
Expected: `dist/resume.json`, `dist/person.jsonld`, `dist/cv-en.txt`, `dist/cv-de.txt`.

- [ ] **Step 4: Commit**

```bash
git add justfile
git commit -m "chore: add justfile recipes for Phase 4 renderers"
```

---

## Task 6: `PublicationsChart.astro` component + integration

**Files:**
- Create: `web/src/components/PublicationsChart.astro`
- Modify: `web/src/components/PublicationsList.astro`

**Reference:** spec §5.4 and §5.6. Accent palette: `#1f3a68` (deep navy from `pdf/styles.typ`).

- [ ] **Step 1: Create `web/src/components/PublicationsChart.astro`**

```astro
---
import type { Publication, AuthorshipType, Lang } from "../types/content";

interface Props {
  publications: Publication[];
  lang: Lang;
}

const { publications, lang } = Astro.props;

const labels: Record<AuthorshipType, { en: string; de: string }> = {
  first:         { en: "First author",         de: "Erstautor" },
  shared:        { en: "Shared first",         de: "Geteilte Erstautorenschaft" },
  corresponding: { en: "Corresponding author", de: "Korrespondenzautor" },
  last:          { en: "Last author",          de: "Letztautor" },
  middle:        { en: "Co-author",            de: "Co-Autor" },
};

const colors: Record<AuthorshipType, string> = {
  first:         "#1f3a68",
  shared:        "#3d5a8a",
  corresponding: "#5b7aac",
  last:          "#7a99cd",
  middle:        "#b8c7df",
};

const order: AuthorshipType[] = ["first", "shared", "corresponding", "last", "middle"];

const counts: Record<string, number> = {};
for (const p of publications) {
  counts[p.authorship] = (counts[p.authorship] ?? 0) + 1;
}

const slices = order
  .filter((k) => (counts[k] ?? 0) > 0)
  .map((k) => ({ key: k, count: counts[k] }));

const total = slices.reduce((s, x) => s + x.count, 0);

/**
 * Compute one SVG arc path per slice on the unit circle centred at (0, 0).
 * Returns absolute path "M 0 0 L x1 y1 A 1 1 0 large 1 x2 y2 Z".
 */
function computeArcs(slices: { key: AuthorshipType; count: number }[], total: number) {
  let cumulative = 0;
  return slices.map((s) => {
    const startAngle = (cumulative / total) * Math.PI * 2;
    cumulative += s.count;
    const endAngle = (cumulative / total) * Math.PI * 2;
    const x1 = Math.sin(startAngle);
    const y1 = -Math.cos(startAngle);
    const x2 = Math.sin(endAngle);
    const y2 = -Math.cos(endAngle);
    const large = endAngle - startAngle > Math.PI ? 1 : 0;
    // If only one slice (100 %), draw a full circle instead of a zero-length arc.
    const d = slices.length === 1
      ? "M 0 -1 A 1 1 0 1 1 0 1 A 1 1 0 1 1 0 -1 Z"
      : `M 0 0 L ${x1} ${y1} A 1 1 0 ${large} 1 ${x2} ${y2} Z`;
    return { d, color: colors[s.key], label: labels[s.key][lang], count: s.count };
  });
}

const arcs = computeArcs(slices, total);
const totalLabel = { en: "publications", de: "Publikationen" }[lang];
---
<figure class="my-6 flex items-center gap-6">
  <svg
    viewBox="-1.1 -1.1 2.2 2.2"
    class="h-32 w-32 shrink-0"
    role="img"
    aria-label={`Authorship breakdown across ${total} ${totalLabel}`}
  >
    {arcs.map((arc) => <path d={arc.d} fill={arc.color} />)}
  </svg>
  <ul class="space-y-1 text-sm text-neutral-700">
    {arcs.map((arc) => (
      <li class="flex items-center gap-2">
        <span class="inline-block h-3 w-3 shrink-0" style={`background:${arc.color}`} />
        <span>{arc.label}: <span class="font-medium">{arc.count}</span></span>
      </li>
    ))}
    <li class="pt-1 text-xs text-neutral-500">
      Σ {total} {totalLabel}
    </li>
  </ul>
</figure>
```

- [ ] **Step 2: Integrate the chart into `web/src/components/PublicationsList.astro`**

Open `web/src/components/PublicationsList.astro` and:

(a) Add the chart import at the top of the frontmatter:

```astro
import PublicationsChart from "./PublicationsChart.astro";
```

(b) Insert the chart immediately under the `<h2>` (above the `typeOrder.map(...)` line). The final section block should look like:

```astro
<section id="publications" class="py-6">
  <h2 class="mb-4 text-xs font-semibold uppercase tracking-wider text-neutral-500">
    {sectionLabel[lang]}
  </h2>
  <PublicationsChart publications={publications} lang={lang} />
  {typeOrder.map((t) => grouped[t].length > 0 && (
    ...
```

- [ ] **Step 3: Regenerate web data + run a build to verify**

```bash
just web-data
pnpm --dir web build 2>&1 | tail -20
```
Expected: build succeeds, both `web/dist/index.html` and `web/dist/de/index.html` exist, no TS errors.

- [ ] **Step 4: Verify the chart appears in the rendered HTML**

```bash
grep -c '<svg' web/dist/index.html
grep -c '<svg' web/dist/de/index.html
grep -oE 'aria-label="[^"]*"' web/dist/index.html | grep -i authorship
```
Expected: at least 1 `<svg>` on each page; aria-label contains "Authorship breakdown across 15 publications".

- [ ] **Step 5: Commit**

```bash
git add web/src/components/PublicationsChart.astro web/src/components/PublicationsList.astro
git commit -m "feat(web): add PublicationsChart SVG pie + integrate into PublicationsList"
```

---

## Task 7: Inject JSON-LD into BaseLayout + ignore generated file + tie into justfile

**Files:**
- Modify: `web/src/layouts/BaseLayout.astro`
- Modify: `web/.gitignore`
- Modify: `justfile`

**Reference:** spec §5.2, §5.5, §5.7, §5.8.

- [ ] **Step 1: Add `public/person.jsonld` to `web/.gitignore`**

Open `web/.gitignore` and append:

```
public/person.jsonld
```

- [ ] **Step 2: Inject the JSON-LD into `web/src/layouts/BaseLayout.astro`**

Open `web/src/layouts/BaseLayout.astro`. At the top of the frontmatter (above `import "../styles/global.css"`), add the raw import:

```astro
import jsonld from "../../public/person.jsonld?raw";
```

Inside the `<head>` block, immediately above `</head>`, add:

```astro
    <script type="application/ld+json" set:html={jsonld}></script>
```

Final `<head>` should be:

```astro
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <meta name="description" content={description} />
    <link rel="canonical" href={Astro.url.href} />
    <title>{title}</title>
    <script type="application/ld+json" set:html={jsonld}></script>
  </head>
```

- [ ] **Step 3: Wire JSON-LD generation into the local web workflow**

Open `justfile` and modify the existing `web-dev` and `web-build` recipes to render + copy JSON-LD first. Replace the two existing recipes with:

```just
# Render JSON-LD and copy into web/public/ so BaseLayout's raw import resolves.
web-jsonld:
    uv run python -m scripts.render_jsonld
    cp dist/person.jsonld web/public/person.jsonld

# Run the Astro dev server (regenerates data + JSON-LD first)
web-dev: web-data web-jsonld
    pnpm --dir web dev

# Build the static site → web/dist/
web-build: web-data web-jsonld
    pnpm --dir web install --frozen-lockfile
    pnpm --dir web build
```

Also update `web-clean` to remove the generated file:

```just
# Remove web build artifacts
web-clean:
    rm -rf web/dist web/node_modules web/src/data/*.json web/public/person.jsonld
```

- [ ] **Step 4: Build the site locally and verify JSON-LD appears in rendered HTML**

```bash
just clean
just web-build 2>&1 | tail -10
grep -c 'application/ld+json' web/dist/index.html
grep -c 'application/ld+json' web/dist/de/index.html
```
Expected: build succeeds; the `<script type="application/ld+json">` tag appears exactly once per page (both EN and DE).

- [ ] **Step 5: Verify the JSON-LD content survived intact**

```bash
python -c "import re, json; html=open('web/dist/index.html').read(); m=re.search(r'<script type=\"application/ld\\+json\"[^>]*>(.*?)</script>', html, re.S); d=json.loads(m.group(1)); print('@type:', d['@type'], '· graph entries:', len(d.get('@graph', [])))"
```
Expected: `@type: Person · graph entries: 15`.

- [ ] **Step 6: Commit**

```bash
git add web/src/layouts/BaseLayout.astro web/.gitignore justfile
git commit -m "feat(web): inject schema.org JSON-LD into every page's <head>"
```

---

## Task 8: `ci.yml` — `build-formats` job + release file additions

**Files:**
- Modify: `.github/workflows/ci.yml`

**Reference:** spec §5.10.

- [ ] **Step 1: Add the `build-formats` job**

Open `.github/workflows/ci.yml`. Locate the `build-pdf:` job. Immediately after it (and before `release:`), add a sibling job:

```yaml
  build-formats:
    needs: validate
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6

      - name: Install uv
        uses: astral-sh/setup-uv@v8.1.0
        with:
          version: "latest"

      - name: Set up Python
        run: uv python install 3.12

      - name: Install dependencies
        run: uv sync --all-groups

      - name: Build machine formats
        run: |
          uv run python -m scripts.render_jsonresume
          uv run python -m scripts.render_jsonld
          uv run python -m scripts.render_text --lang en
          uv run python -m scripts.render_text --lang de

      - name: Upload formats artifact
        uses: actions/upload-artifact@v7
        with:
          name: cv-formats
          path: |
            dist/resume.json
            dist/person.jsonld
            dist/cv-en.txt
            dist/cv-de.txt
          retention-days: ${{ github.event_name == 'pull_request' && 30 || 1 }}
          if-no-files-found: error
```

- [ ] **Step 2: Update the `release` job to depend on `build-formats` and include the new files**

In the same file, locate the `release:` job. Change the `needs:` line and the `files:` block:

```yaml
  release:
    needs: [build-pdf, build-formats]
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - name: Download all artifacts
        uses: actions/download-artifact@v7
        with:
          path: dist
          merge-multiple: true

      - name: Compute release metadata
        id: meta
        run: |
          echo "date=$(date -u +%Y-%m-%d)" >> "$GITHUB_OUTPUT"
          echo "short_sha=${GITHUB_SHA::7}" >> "$GITHUB_OUTPUT"

      - name: Create GitHub Release
        uses: softprops/action-gh-release@v3
        with:
          tag_name: cv-${{ steps.meta.outputs.date }}-${{ steps.meta.outputs.short_sha }}
          name: CV ${{ steps.meta.outputs.date }}
          files: |
            dist/cv-en.pdf
            dist/cv-de.pdf
            dist/resume.json
            dist/person.jsonld
            dist/cv-en.txt
            dist/cv-de.txt
          make_latest: true
          body: |
            Auto-generated CV release from commit ${{ github.sha }}.

            Commit: ${{ github.event.head_commit.message }}

            View commit: ${{ github.server_url }}/${{ github.repository }}/commit/${{ github.sha }}
```

(Only the `needs:` line, the artifact step name, and the `files:` block change — the rest is the same as the existing job.)

- [ ] **Step 3: Validate YAML syntactically**

```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))" && echo "YAML OK"
```
Expected: `YAML OK`.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add build-formats job; include resume.json + person.jsonld + plain text in release"
```

---

## Task 9: `pages.yml` — render JSON-LD before Astro build

**Files:**
- Modify: `.github/workflows/pages.yml`

**Reference:** spec §5.11.

- [ ] **Step 1: Add the JSON-LD rendering step**

Open `.github/workflows/pages.yml`. In the `build` job, locate the existing step `Render web JSON`. Immediately after it, add:

```yaml
      - name: Render JSON-LD into web/public/
        run: |
          uv run python -m scripts.render_jsonld
          mkdir -p web/public
          cp dist/person.jsonld web/public/person.jsonld
```

The full `build` job steps should now be:

```yaml
    steps:
      - uses: actions/checkout@v6

      - name: Install uv
        uses: astral-sh/setup-uv@v8.1.0
        with:
          version: "latest"

      - name: Set up Python
        run: uv python install 3.12

      - name: Install Python deps
        run: uv sync --all-groups

      - name: Render web JSON
        run: uv run python -m scripts.render_web_data

      - name: Render JSON-LD into web/public/
        run: |
          uv run python -m scripts.render_jsonld
          mkdir -p web/public
          cp dist/person.jsonld web/public/person.jsonld

      - name: Set up Node
        uses: actions/setup-node@v4
        with:
          node-version-file: .nvmrc

      - name: Set up pnpm
        uses: pnpm/action-setup@v4
        with:
          version: 10

      - name: Install web deps
        run: pnpm --dir web install --frozen-lockfile

      - name: Build site
        run: pnpm --dir web build

      - name: Upload Pages artifact
        uses: actions/upload-pages-artifact@v3
        with:
          path: web/dist
```

- [ ] **Step 2: Validate YAML**

```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/pages.yml'))" && echo "YAML OK"
```
Expected: `YAML OK`.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/pages.yml
git commit -m "ci: render JSON-LD before Astro build so /person.jsonld and inline tag ship"
```

---

## Task 10: README + CLAUDE.md updates

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md`

**Reference:** spec §5.12.

- [ ] **Step 1: Add machine-formats line near the top of `README.md`**

Open `README.md`. Locate the existing first paragraph that reads:

```markdown
**Latest CV:** [EN](https://github.com/Jin-HoMLee/jin-ho-lee-cv/releases/latest/download/cv-en.pdf) · [DE](https://github.com/Jin-HoMLee/jin-ho-lee-cv/releases/latest/download/cv-de.pdf) — auto-published on every change to `main`.
```

Immediately under it (above the existing `**Website:**` line), add:

```markdown
**Machine formats:** [JSON Resume](https://github.com/Jin-HoMLee/jin-ho-lee-cv/releases/latest/download/resume.json) · [Plain text EN](https://github.com/Jin-HoMLee/jin-ho-lee-cv/releases/latest/download/cv-en.txt) · [Plain text DE](https://github.com/Jin-HoMLee/jin-ho-lee-cv/releases/latest/download/cv-de.txt) · [JSON-LD](https://jin-homlee.github.io/jin-ho-lee-cv/person.jsonld)
```

- [ ] **Step 2: Update `CLAUDE.md` Layout / scripts list**

Open `CLAUDE.md`. Find the `scripts/` line in the Layout block (currently `scripts/                  validate.py, bib_loader.py, content_loader.py, render_web_data.py`) and replace with:

```
scripts/                  validate.py, bib_loader.py, content_loader.py, langstring.py, render_web_data.py, render_jsonresume.py, render_jsonld.py, render_text.py
```

(Note: `langstring.py` was missing from the previous line; this fix adds it too.)

- [ ] **Step 3: Verify both files render correctly**

```bash
head -10 README.md
grep "scripts/" CLAUDE.md | head -2
```
Expected: README shows the new "Machine formats" line; CLAUDE.md scripts line includes all 8 modules.

- [ ] **Step 4: Commit**

```bash
git add README.md CLAUDE.md
git commit -m "docs: add Phase 4 machine-format download links + update scripts list"
```

---

## Task 11: Local end-to-end smoke + push branch + open PR

**Files:**
- None (verification + git workflow)

- [ ] **Step 1: Clean rebuild of everything**

```bash
just clean
just build
just build-de
just build-formats
just web-build
ls dist/
ls web/dist/
```
Expected:
- `dist/`: `cv-en.pdf`, `cv-de.pdf`, `resume.json`, `person.jsonld`, `cv-en.txt`, `cv-de.txt`
- `web/dist/`: `index.html`, `de/index.html`, `_astro/`, `photo.jpg`, `person.jsonld` (copied from public/)

- [ ] **Step 2: Run validate + tests + lint**

```bash
just validate
just test 2>&1 | tail -3
just lint
```
Expected: all green; pytest reports `43+8+6+8 = 65` (or similar) passed.

- [ ] **Step 3: Dev server visual smoke**

```bash
just web-dev &
DEV_PID=$!
sleep 6
echo "Open: http://localhost:4321/jin-ho-lee-cv/  and  /de/"
curl -s "http://localhost:4321/jin-ho-lee-cv/" | grep -c 'application/ld+json'
curl -s "http://localhost:4321/jin-ho-lee-cv/" | grep -c '<svg'
kill $DEV_PID 2>/dev/null
```

Click through (visual confirm):
- Publications section shows a pie chart with legend
- View page source: `<script type="application/ld+json">` present in `<head>`
- DE page: chart legend uses German labels

If anything looks off, fix on the branch and add commits before continuing.

- [ ] **Step 4: Push the branch**

```bash
git push -u origin phase-4-machine-formats
```

- [ ] **Step 5: Open the PR**

```bash
gh pr create --title "Phase 4: JSON Resume + JSON-LD + plain text + publications chart" --body "$(cat <<'EOF'
## Summary

Ships four small machine-readable / SEO-friendly artifacts:

- `dist/resume.json` — [JSON Resume](https://jsonresume.org/schema/) for ATS interop (EN)
- `dist/person.jsonld` — schema.org `Person` + `ScholarlyArticle[]` graph (EN), also embedded into every site page's `<head>`
- `dist/cv-{en,de}.txt` — section-headed plain text for old ATS systems (bilingual)
- Authorship pie chart inside the website's Publications section (inline SVG, no JS library)

Implements [Phase 4 spec](docs/superpowers/specs/2026-05-25-phase-4-machine-formats-design.md).

## What's in
- `scripts/render_jsonresume.py` + 6 pytest assertions (schema validation, round-trip, dates ISO 8601, skill flatten)
- `scripts/render_jsonld.py` + 8 pytest assertions (context, type, counts, PII isolation, sameAs)
- `scripts/render_text.py` + 8 pytest assertions (bilingual headers, no markdown, no PII, no trailing ws)
- `web/src/components/PublicationsChart.astro` — pure-SVG pie, accent palette, accessible (aria-label + textual legend)
- `web/src/layouts/BaseLayout.astro` — inline JSON-LD via `?raw` import
- `.github/workflows/ci.yml` — new `build-formats` job; release file list extended by 4 files
- `.github/workflows/pages.yml` — JSON-LD render step before Astro build
- `justfile` recipes for each new renderer; `web-dev`/`web-build` gain JSON-LD pre-step
- README + CLAUDE.md updates
- `tests/fixtures/jsonresume-schema.json` (vendored v1.0.0)

## What's not in (deferred)
- Per-language JSON Resume / JSON-LD (EN-only by schema convention)
- Header download links for JSON / TXT (PDF buttons stay as only header download)
- Interactive chart (hover, drill-down) — Phase 5+
- Per-project deep-dive pages, custom domain — Phase 5

## Test plan
- [ ] CI: validate + tests + lint pass (`ci.yml`)
- [ ] CI: `build-pdf` (en/de) passes
- [ ] CI: `build-formats` passes and uploads `cv-formats` artifact
- [ ] CI: `pages.yml` build job passes (deploy job only fires on push to main)
- [ ] After merge: latest release contains `resume.json`, `person.jsonld`, `cv-en.txt`, `cv-de.txt`
- [ ] After merge: `https://jin-homlee.github.io/jin-ho-lee-cv/person.jsonld` returns 200 + valid JSON-LD
- [ ] After merge: site source contains `<script type="application/ld+json">` in `<head>`
- [ ] After merge: site shows authorship pie chart in Publications section
EOF
)"
```

Capture the PR URL.

- [ ] **Step 6: Watch CI**

```bash
gh pr checks --watch
```
Expected: `validate` ✅, `build-pdf` (en/de) ✅, `build-formats` ✅, `release` skipping (PR event).

If `build-formats` fails, the most likely causes are:
- Missing `jsonschema` dep → re-check `pyproject.toml` test-deps were added in Task 1
- PII assertion failing → re-check `private_path=None` is hard-coded in the loaders (already enforced)

If `pages.yml` build fails, the most likely cause is the `?raw` import failing because `web/public/person.jsonld` wasn't created — re-check the render step in `pages.yml`.

---

## Task 12: Merge PR, verify deployment, mark Phase 4 done

The Pages workflow already enabled in Phase 3 deploys on push to `main`; no additional GitHub settings change needed.

**Files:**
- Modify: `CLAUDE.md` (after merge, on a small follow-up PR)

- [ ] **Step 1: Confirm CI green + merge**

```bash
gh pr ready
gh pr checks
gh pr merge phase-4-machine-formats --merge --delete-branch \
  -t "Merge Phase 4: machine formats + publications chart" -b ""
git switch main
git pull --ff-only
```
The `--merge` flag forces a no-ff merge commit (matching Phase 2a/2b/3 style).

- [ ] **Step 2: Watch the post-merge workflows**

```bash
CI_RUN=$(gh run list --workflow=ci.yml --branch=main --event=push --limit=1 --json databaseId --jq '.[0].databaseId')
PAGES_RUN=$(gh run list --workflow=pages.yml --branch=main --event=push --limit=1 --json databaseId --jq '.[0].databaseId')
echo "CI run: $CI_RUN"
echo "Pages run: $PAGES_RUN"

gh run watch "$PAGES_RUN" --exit-status --interval 10
gh run watch "$CI_RUN" --exit-status --interval 10
```
Use a Bash timeout of 600000ms (10 min). Expected: both workflows succeed; CI cuts a new release with all 6 files.

- [ ] **Step 3: Confirm all four new artifacts are in the release**

```bash
gh release view --json tagName,assets --jq '{tag: .tagName, assets: [.assets[].name]}'
```
Expected: `assets` contains `cv-en.pdf`, `cv-de.pdf`, `resume.json`, `person.jsonld`, `cv-en.txt`, `cv-de.txt`.

- [ ] **Step 4: Confirm the site has the JSON-LD inline + standalone, and the chart renders**

```bash
echo "--- JSON-LD inline on EN page:"
curl -s "https://jin-homlee.github.io/jin-ho-lee-cv/" | grep -c 'application/ld+json'
echo "--- JSON-LD standalone:"
curl -sI "https://jin-homlee.github.io/jin-ho-lee-cv/person.jsonld" | head -1
curl -s "https://jin-homlee.github.io/jin-ho-lee-cv/person.jsonld" | python -c "import json,sys; d=json.load(sys.stdin); print('@type:', d['@type'])"
echo "--- Chart SVG present on EN page:"
curl -s "https://jin-homlee.github.io/jin-ho-lee-cv/" | grep -c 'aria-label="Authorship'
echo "--- Chart SVG present on DE page:"
curl -s "https://jin-homlee.github.io/jin-ho-lee-cv/de/" | grep -c 'aria-label="Authorship'
```
Expected:
- inline JSON-LD count: 1 (per page)
- standalone returns 200 + `@type: Person`
- chart aria-label present on both pages

- [ ] **Step 5: Download each release artifact and verify it parses / is readable**

```bash
cd /tmp
curl -sL "https://github.com/Jin-HoMLee/jin-ho-lee-cv/releases/latest/download/resume.json" -o resume.json
curl -sL "https://github.com/Jin-HoMLee/jin-ho-lee-cv/releases/latest/download/person.jsonld" -o person.jsonld
curl -sL "https://github.com/Jin-HoMLee/jin-ho-lee-cv/releases/latest/download/cv-en.txt" -o cv-en.txt
curl -sL "https://github.com/Jin-HoMLee/jin-ho-lee-cv/releases/latest/download/cv-de.txt" -o cv-de.txt
python -c "import json; print('resume.json work entries:', len(json.load(open('resume.json'))['work']))"
python -c "import json; print('person.jsonld graph entries:', len(json.load(open('person.jsonld'))['@graph']))"
head -3 cv-en.txt
echo "---"
head -3 cv-de.txt
cd -
```
Expected: work entries = 3, graph entries = 15, both text files begin with `JIN-HO LEE`.

- [ ] **Step 6: Tick verified test plan items in the PR body**

```bash
gh pr view <PR-number> --json body --jq .body > /tmp/pr-body.md
# Replace `- [ ]` with `- [x]` for each verified item
sed -i '' 's/- \[ \] CI: validate/- [x] CI: validate/' /tmp/pr-body.md
sed -i '' 's/- \[ \] CI: `build-pdf`/- [x] CI: `build-pdf`/' /tmp/pr-body.md
sed -i '' 's/- \[ \] CI: `build-formats`/- [x] CI: `build-formats`/' /tmp/pr-body.md
sed -i '' 's/- \[ \] CI: `pages.yml`/- [x] CI: `pages.yml`/' /tmp/pr-body.md
sed -i '' 's/- \[ \] After merge: latest release/- [x] After merge: latest release/' /tmp/pr-body.md
sed -i '' 's/- \[ \] After merge: `https:\/\/jin-homlee.github.io\/jin-ho-lee-cv\/person.jsonld`/- [x] After merge: `https:\/\/jin-homlee.github.io\/jin-ho-lee-cv\/person.jsonld`/' /tmp/pr-body.md
sed -i '' 's/- \[ \] After merge: site source/- [x] After merge: site source/' /tmp/pr-body.md
sed -i '' 's/- \[ \] After merge: site shows authorship/- [x] After merge: site shows authorship/' /tmp/pr-body.md
gh pr edit <PR-number> --body-file /tmp/pr-body.md
```

- [ ] **Step 7: Mark Phase 4 done in `CLAUDE.md`**

Get the merge SHA:

```bash
MERGE_SHA=$(git log -1 --format=%h main)
TODAY=$(date -u +%Y-%m-%d)
echo "Merge: $MERGE_SHA on $TODAY"
```

Open `CLAUDE.md` and change:

```markdown
| 4 | JSON Resume + JSON-LD + plain text + publication chart | Not started |
```

to (substituting the captured values):

```markdown
| 4 | JSON Resume + JSON-LD + plain text + publication chart | ✅ Done (merged YYYY-MM-DD, commit `<merge-sha>`) |
```

Push the change via a small follow-up PR (the classifier blocks direct-to-main):

```bash
git switch -c docs/mark-phase-4-done
git add CLAUDE.md
git commit -m "docs: mark Phase 4 as done"
git push -u origin docs/mark-phase-4-done
gh pr create --title "docs: mark Phase 4 as done" --body "Status table update following Phase 4 merge (commit \`$MERGE_SHA\` on $TODAY)."
gh pr checks --watch
gh pr merge --rebase --delete-branch
git switch main && git pull --ff-only
```

This second merge triggers another Pages + CI run (idempotent — same site content). Acceptable noise.

---

## Self-Review

### Spec coverage

- **§1 Scope** — Tasks 2 (JSON Resume), 3 (JSON-LD), 4 (plain text), 6 (chart) cover all 4 deliverables.
- **§2 Goal** — release URLs (Task 8/12), site URL for `/person.jsonld` (Tasks 7/9/12), inline `<script>` on every page (Task 7), chart in PublicationsList (Task 6), auto-publish on push to main (Tasks 8/9/12).
- **§3 Non-goals** — no per-language JSON Resume (Task 2 EN only), no per-language JSON-LD (Task 3 EN only), no header download links (omitted from Task 10 / unchanged Header), no chart interactivity (Task 6 static SVG only).
- **§4 Architecture** — three Python renderers each in their own file (Tasks 2-4); one Astro component (Task 6); JSON-LD double-publish via Tasks 7 + 9.
- **§4.1 Bundle rationale** — embodied in the single phase / single PR plan.
- **§4.2 JSON-LD special handling** — Task 7 (BaseLayout import) + Task 9 (pages.yml render + cp step).
- **§5.1 JSON Resume** — Task 2 implements the exact `to_jsonresume` shape from the spec, with the documented skill flattening (`level` ← group label), date padding, schema validation.
- **§5.2 JSON-LD** — Task 3 implements `to_jsonld` with `@graph` of `ScholarlyArticle`, `alumniOf`, `knowsAbout`, `worksFor` (first current experience entry), `sameAs` (filtered for non-null links).
- **§5.3 Plain text** — Task 4 implements `render(lang)` with 80-col wrap, ASCII bullets, section dividers, `labels.yaml`-based section headers, URL-aware non-wrap (handles spec's "skip wrap on lines containing http" decision).
- **§5.4 PublicationsChart** — Task 6 implements `computeArcs` with cumulative-angle SVG paths, full-circle fallback for single-slice, accent-palette colors, accessible legend.
- **§5.5 BaseLayout modification** — Task 7.
- **§5.6 PublicationsList modification** — Task 6 Step 2.
- **§5.7 `web/public/person.jsonld`** — generated in Task 9 (CI) and Task 7 (local); gitignored via Task 7 Step 1.
- **§5.8 web/.gitignore** — Task 7 Step 1.
- **§5.9 Justfile recipes** — Task 5 (renderers) + Task 7 Step 3 (web pipeline).
- **§5.10 ci.yml** — Task 8.
- **§5.11 pages.yml** — Task 9.
- **§5.12 README + CLAUDE.md** — Task 10 + Task 12 Step 7.
- **§6 Failure modes** — Task 2 Step 6 (PII grep) + Task 4 Step 6 (PII grep) cover PII leak. Task 7 Step 5 verifies JSON-LD survives Astro escaping. Task 6 Step 1 has full-circle fallback for rounding edge case. `bib_loader._parse_entry` already raises on unknown authorship.
- **§7 Testing** — Task 2 (jsonresume) + Task 3 (jsonld) + Task 4 (plain text) cover all unit-layer assertions from the spec. Task 11 Step 4 covers integration smoke. Task 12 Steps 4-5 cover post-deploy smoke.
- **§8 Migration / rollback** — fully additive; rollback by reverting the phase-4 merge commit.
- **§9 Sequencing for Phase 5** — `Person.url` is set as a module constant in `render_jsonld.py` (Task 3); Phase 5 custom domain only needs to change `SITE_URL` constants. Per-project pages can append to `@graph` later.
- **§10 Open decisions** — accent color picked in Task 6 (`#1f3a68` from `pdf/styles.typ`), URL wrap behaviour implemented in Task 4 Step 3 (skip wrap on `http`-containing paragraphs), `meta.canonical` set to GitHub Pages URL via `SITE_URL` constant (Task 2/3), stable key order via dict literal in Task 2/3.

### Placeholder scan

Searched the plan for `TBD`, `TODO`, `implement later`, `add appropriate`, `etc.`, `similar to`. None found in step content. The `<PR-number>` token in Task 12 Step 6 is a runtime substitution explicitly noted as "captured" — same convention used in Phase 3 plan.

### Type consistency

- `to_jsonresume(content, pubs)` defined in Task 2 Step 3, imported in Task 2 Step 1 — same name.
- `to_jsonld(content, pubs)` defined in Task 3 Step 3, imported in Task 3 Step 1 — same name.
- `render(lang)` defined in Task 4 Step 3, imported in Task 4 Step 1 — same name.
- `PublicationsChart` component named consistently across Task 6 (create), Task 7 (no rename), and Phase 5 sequencing.
- Justfile recipe names: `build-resume`, `build-jsonld`, `build-text`, `build-formats`, `web-jsonld` — used identically across Tasks 5, 7, and 11.
- `SITE_URL = "https://jin-homlee.github.io/jin-ho-lee-cv/"` and `PHOTO_URL = f"{SITE_URL}photo.jpg"` constants appear in both renderers with the same value.
- `AuthorshipType` enum (`"first" | "shared" | "middle" | "last" | "corresponding"`) matches the values in `scripts/bib_loader.py:AUTHORSHIP_VALUES` — Task 6 Step 1 imports the type from `web/src/types/content.ts` which Phase 3 already defined.

All references resolve.
