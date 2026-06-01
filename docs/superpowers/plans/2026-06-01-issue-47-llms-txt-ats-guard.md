# Issue #47 (scoped) — llms.txt renderer + ATS text-layer CI guard — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`).

**Goal:** Add a content-derived `/llms.txt` site map and a CI-verified ATS text-layer guard for the built PDFs. (Crossref counts → #57; `llms-full.txt` skipped.)

**Architecture:** New `scripts/render_llms.py` (mirrors `render_text.py`, EN-only, single-source) → `dist/llms.txt`, copied to `web/public/llms.txt` so the deployed site serves `/llms.txt`. New `tests/test_ats_pdf.py` (pdftotext round-trip, skip-guarded) run by a dedicated CI `ats-guard` job. Download links use a new `RELEASES_BASE_URL` config constant (GitHub release assets), JSON-LD uses the site root.

**Tech Stack:** Python, ruamel.yaml, pybtex, syrupy, pdftotext (poppler), Typst, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-06-01-issue-47-llms-txt-ats-guard-design.md`

---

## Files

- Modify: `scripts/config.py` (`GITHUB_REPO`, `RELEASES_BASE_URL`) — Task 1
- Create: `scripts/render_llms.py` — Task 1
- Create: `tests/test_render_llms.py` — Task 1
- Modify: `justfile` (`build-llms`, `web-llms`, deps) — Task 1
- Modify: `tests/test_snapshots.py` (+ `test_llms_txt`) — Task 2
- Create: `tests/test_ats_pdf.py` — Task 3
- Modify: `.github/workflows/ci.yml` (`ats-guard` job) — Task 4
- Modify: `CLAUDE.md` — Task 5

---

### Task 1: `llms.txt` renderer + build wiring

- [ ] **Step 1: Add release-URL constants to `scripts/config.py`**

Append:
```python
GITHUB_REPO: str = "Jin-HoMLee/jin-ho-lee-cv"
RELEASES_BASE_URL: str = f"https://github.com/{GITHUB_REPO}/releases/latest/download"
```
(The parity test only checks `SITE_DOMAIN`/`SITE_PATH`, so no TS-mirror change is needed.)

- [ ] **Step 2: Write the failing renderer test**

Create `tests/test_render_llms.py`:
```python
"""Pytest assertions for the llms.txt renderer."""
from __future__ import annotations

from pathlib import Path

from scripts.bib_loader import load_publications
from scripts.config import PAGES_BASE_URL, RELEASES_BASE_URL
from scripts.content_loader import load_content
from scripts.langstring import resolve_langstrings
from scripts.render_llms import render

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = REPO_ROOT / "content"


def _content():
    return resolve_langstrings(load_content(CONTENT_DIR, lang="en"), lang="en")


def test_h1_has_name_and_headline():
    out = render()
    assert out.startswith("# Jin-Ho Lee — Bioinformatics · Data Science\n")


def test_blockquote_summary_present():
    c = _content()
    assert f"> {c['profile']['tagline']}" in render()


def test_all_selected_projects_linked():
    c = _content()
    out = render()
    for p in c["selected_projects"]:
        assert f"]({PAGES_BASE_URL}/projects/{p['id']}/)" in out
        assert p["title"] in out


def test_publications_doi_linked():
    pubs = load_publications(CONTENT_DIR / "publications.bib")
    out = render()
    doi_pubs = [p for p in pubs if p.doi]
    assert doi_pubs, "expected at least one DOI'd pub"
    for p in doi_pubs:
        assert f"(https://doi.org/{p.doi})" in out


def test_formats_and_links_sections():
    out = render()
    assert f"{RELEASES_BASE_URL}/cv-en.pdf" in out
    assert f"{RELEASES_BASE_URL}/resume.json" in out
    assert f"{PAGES_BASE_URL}/person.jsonld" in out
    assert "## Links" in out
    assert "[GitHub](" in out and "[ORCID](" in out


def test_no_pii():
    out = render().lower()
    assert "phone" not in out
    for kw in ("strasse", "straße", "hausnummer"):
        assert kw not in out
```

- [ ] **Step 3: Run — verify FAIL**

Run: `uv run pytest tests/test_render_llms.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.render_llms'`.

- [ ] **Step 4: Implement `scripts/render_llms.py`**

```python
"""Render an llms.txt site map (https://llmstxt.org) — a concise, LLM-friendly index
derived from the same YAML + bib as every other renderer (single source of truth).

This is a cheap discoverability aid (honoured by Anthropic/Perplexity), NOT a
replacement for the JSON-LD entity graph."""
from __future__ import annotations

import argparse
from pathlib import Path

from scripts.bib_loader import Publication, load_publications
from scripts.config import PAGES_BASE_URL, RELEASES_BASE_URL
from scripts.content_loader import load_content
from scripts.langstring import resolve_langstrings

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = REPO_ROOT / "content"

_LINK_LABELS = {
    "github": "GitHub",
    "linkedin": "LinkedIn",
    "researchgate": "ResearchGate",
    "website": "Website",
    "orcid": "ORCID",
}


def _projects_section(content: dict) -> str:
    lines = ["## Selected Projects"]
    for p in content["selected_projects"]:
        lines.append(f"- [{p['title']}]({PAGES_BASE_URL}/projects/{p['id']}/): {p['summary']}")
    return "\n".join(lines)


def _publications_section(pubs: list[Publication]) -> str:
    lines = ["## Publications"]
    for p in pubs:
        suffix = f": {p.venue}, {p.year}" if p.venue else f": {p.year}"
        if p.doi:
            lines.append(f"- [{p.title}](https://doi.org/{p.doi}){suffix}")
        else:
            lines.append(f"- {p.title}{suffix}")
    return "\n".join(lines)


def _formats_section() -> str:
    return "\n".join([
        "## CV & machine-readable formats",
        f"- [CV (PDF, EN)]({RELEASES_BASE_URL}/cv-en.pdf)",
        f"- [CV (PDF, DE)]({RELEASES_BASE_URL}/cv-de.pdf)",
        f"- [JSON Resume]({RELEASES_BASE_URL}/resume.json)",
        f"- [JSON-LD (schema.org)]({PAGES_BASE_URL}/person.jsonld)",
        f"- [Plain text (EN)]({RELEASES_BASE_URL}/cv-en.txt)",
    ])


def _links_section(personal: dict) -> str:
    lines = ["## Links"]
    links = personal.get("links") or {}
    for key, label in _LINK_LABELS.items():
        if url := links.get(key):
            lines.append(f"- [{label}]({url})")
    return "\n".join(lines)


def render() -> str:
    content = resolve_langstrings(load_content(CONTENT_DIR, lang="en"), lang="en")
    pubs = load_publications(CONTENT_DIR / "publications.bib")
    personal = content["personal"]
    profile = content["profile"]
    name = f"{personal['name']['given']} {personal['name']['family']}"
    blocks = [
        f"# {name} — {personal['headline']}",
        f"> {profile['tagline']}",
        profile["paragraphs"][0],
        _projects_section(content),
        _publications_section(pubs),
        _formats_section(),
        _links_section(personal),
    ]
    return "\n\n".join(blocks) + "\n"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=REPO_ROOT / "dist" / "llms.txt")
    args = parser.parse_args(argv)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(), encoding="utf-8")
    try:
        rel = args.output.relative_to(REPO_ROOT)
    except ValueError:
        rel = args.output
    print(f"wrote {rel}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run — verify PASS + lint**

```bash
uv run pytest tests/test_render_llms.py -q
uv run ruff check scripts/render_llms.py scripts/config.py tests/test_render_llms.py
```
Expected: all pass; lint clean.

- [ ] **Step 6: Wire into the justfile**

Add recipes (after `build-text`):
```make
# Render the llms.txt site map → dist/llms.txt
build-llms:
    uv run python -m scripts.render_llms
```
Change `build-formats`:
```make
build-formats: build-resume build-jsonld build-text build-llms
```
Add a web copy recipe + add it to the web build/dev deps:
```make
# Render llms.txt and copy into web/public/ so it is served at /llms.txt
web-llms:
    uv run python -m scripts.render_llms
    cp dist/llms.txt web/public/llms.txt
```
Update:
```make
web-dev: web-data web-jsonld web-llms
web-build: web-data web-jsonld web-llms
```
And add `web/public/llms.txt` to the `web-clean` removal list.

- [ ] **Step 7: Verify build + commit**

```bash
just build-llms && head -5 dist/llms.txt
just web-llms && test -f web/public/llms.txt && echo "served copy OK"
git add scripts/config.py scripts/render_llms.py tests/test_render_llms.py justfile
git commit -m "feat: #47 llms.txt renderer (scripts/render_llms.py) + build/web wiring"
```
(Note: `web/public/llms.txt` is a generated copy — confirm it's gitignored or excluded like `person.jsonld`; `web-clean` removes it. Do NOT commit the generated copy.)

---

### Task 2: llms.txt golden snapshot

- [ ] **Step 1: Add the snapshot test**

In `tests/test_snapshots.py`, add the import `from scripts import render_llms` (extend the existing `from scripts import …` line) and:
```python
def test_llms_txt(tmp_path, snapshot):
    out = tmp_path / "llms.txt"
    render_llms.main(["--output", str(out)])
    assert out.read_text(encoding="utf-8") == snapshot.use_extension(_TextSnap)
```

- [ ] **Step 2: Generate + eyeball + verify**

```bash
uv run pytest tests/test_snapshots.py::test_llms_txt -q          # FAIL: snapshot missing
just snapshots-update
cat tests/__snapshots__/test_snapshots/test_llms_txt.txt          # eyeball: valid llms.txt
uv run pytest tests/test_snapshots.py -q                          # 13 passed
```

- [ ] **Step 3: Commit**

```bash
git add tests/test_snapshots.py tests/__snapshots__/test_snapshots/test_llms_txt.txt
git commit -m "test: #47 add llms.txt golden snapshot"
```

---

### Task 3: ATS PDF text-layer guard

- [ ] **Step 1: Write `tests/test_ats_pdf.py`**

```python
"""ATS guard: the built PDF must have an extractable text layer with name, email,
section headings, and umlauts round-tripping through a parser (pdftotext/poppler)."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def _have(tool: str) -> bool:
    return shutil.which(tool) is not None


def _typst_available() -> bool:
    return _have("typst")


pytestmark = pytest.mark.skipif(
    not (_typst_available() and _have("pdftotext")),
    reason="needs typst + pdftotext (poppler) to build a PDF and extract its text layer",
)


def _build_and_extract(tmp_path: Path, lang: str) -> str:
    out = tmp_path / f"cv-{lang}.pdf"
    subprocess.run(
        [sys.executable, "-m", "pdf.build", "--lang", lang, "--target", "bridge", "--output", str(out)],
        cwd=REPO_ROOT, check=True, capture_output=True, text=True,
    )
    return subprocess.run(
        ["pdftotext", str(out), "-"], check=True, capture_output=True, text=True
    ).stdout


def test_en_pdf_text_layer(tmp_path):
    text = _build_and_extract(tmp_path, "en")
    assert len(text) > 800, "PDF appears to have no real text layer (image-only?)"
    assert "Jin-Ho Lee" in text
    assert "jinho.michael.lee@gmail.com" in text
    for heading in ("PROFILE", "SKILLS", "EDUCATION", "PUBLICATIONS"):
        assert heading in text, f"missing section heading {heading!r}"
    # Umlaut round-trips (FZ Jülich) — proves Unicode extraction, not mojibake.
    assert "Jülich" in text


def test_de_pdf_text_layer(tmp_path):
    text = _build_and_extract(tmp_path, "de")
    assert "Jin-Ho Lee" in text
    # At least one umlaut/ß-bearing token survives extraction.
    assert any(ch in text for ch in "äöüßÄÖÜ")
```
(Confirm `pdf.build` supports `--output`; if not, build to the default `dist/cv-{lang}.pdf` and read that instead. Check with `uv run python -m pdf.build --help`.)

- [ ] **Step 2: Run locally — verify PASS (typst + pdftotext present)**

Run: `uv run pytest tests/test_ats_pdf.py -v`
Expected: 2 passed (or skipped if tools absent — then rely on CI Task 4).

- [ ] **Step 3: Commit**

```bash
git add tests/test_ats_pdf.py
git commit -m "test: #47 ATS PDF text-layer guard (name, email, headings, umlauts)"
```

---

### Task 4: Run the ATS guard in CI

- [ ] **Step 1: Add an `ats-guard` job to `.github/workflows/ci.yml`**

After the `build-pdf` job, add (mirror its uv/python/typst/font setup):
```yaml
  ats-guard:
    needs: validate
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - name: Install uv
        uses: astral-sh/setup-uv@v8.1.0
        with:
          version: "latest"
      - name: Set up Python
        run: uv python install 3.12
      - name: Install dependencies
        run: uv sync --all-groups
      - name: Read pinned Typst version
        id: typst-version
        run: echo "version=$(cat .typstversion)" >> "$GITHUB_OUTPUT"
      - name: Install Typst
        uses: typst-community/setup-typst@v5
        with:
          typst-version: ${{ steps.typst-version.outputs.version }}
      - name: Install IBM Plex Sans font
        run: |
          <copy the exact font-install block from the build-pdf job>
      - name: Install pdftotext (poppler)
        run: sudo apt-get update && sudo apt-get install -y poppler-utils
      - name: Run ATS text-layer guard
        run: uv run pytest tests/test_ats_pdf.py -v
```
Copy the font-install `run:` block verbatim from `build-pdf` (lines ~69–74) so fonts resolve identically.

- [ ] **Step 2: Validate the workflow YAML locally**

```bash
python3 -c "import yaml,sys; yaml.safe_load(open('.github/workflows/ci.yml')); print('ci.yml valid YAML')"
```
Expected: prints valid. (Full job execution is verified by the PR's CI run.)

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: #47 run the ATS text-layer guard in a dedicated job"
```

---

### Task 5: CLAUDE.md + final gate + tick boxes

- [ ] **Step 1: Update CLAUDE.md**

In "## Commands", after `build-formats`, note `build-formats` now includes llms.txt; add nothing new there beyond a comment if desired. In "## Layout", add `render_llms.py` to the `scripts/` list. In "## Conventions" (or the CI note), add a short line: the built PDF's ATS text layer is CI-verified (`tests/test_ats_pdf.py` via the `ats-guard` job); `/llms.txt` is generated into `web/public/` for the deployed site.

- [ ] **Step 2: Full gate**

```bash
just validate && just test && just lint
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"
```
Expected: validate OK, all tests pass (incl. llms snapshot + ATS guard locally), lint clean, YAML valid.

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: #47 note llms.txt + ATS guard in CLAUDE.md"
```

- [ ] **Step 4: Tick issue #47 + note the split**

Update issue #47 body: tick the llms.txt + ATS-guard boxes; mark the Crossref sub-item as moved to #57 (with a link). Post a verification comment. (`gh issue edit 47 --body-file …`.)

---

## Notes for the executor

- **Single source of truth** — `render_llms` derives everything from `content/` + bib; no hand-written prose.
- **Download links** point at GitHub release assets (`RELEASES_BASE_URL`) — verified to exist (`gh release view`): `cv-{en,de}.pdf`, `resume.json`, `cv-{en,de}.txt`, `person.jsonld`. JSON-LD also served at the site root.
- **`web/public/llms.txt` is generated** — don't commit it (parallels `person.jsonld`, which `web-clean` removes and regenerates). **IMPORTANT:** `pages.yml` does NOT use the `just web-build` recipe — it has its OWN explicit "Render JSON-LD into web/public/" step (~lines 37–41). So Task 4 must ALSO add a parallel step to `pages.yml` that renders + copies `llms.txt` into `web/public/` before the Astro build, or the deployed site won't serve `/llms.txt`. Mirror the existing JSON-LD step exactly.
- **ATS guard** is skip-guarded locally; the new CI job installs typst+poppler so it actually runs in CI (the existing `validate` job can't — no Typst).
- **Atomic commits**, no Claude attribution trailers.
