# Phase 5 — Polish: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship Phase 5 polish — custom domain (parameterized), per-project deep-dive pages, build-time OG images, and chart hover tooltips — as one additive bundle on the `phase-5-polish` branch.

**Architecture:** A new `scripts/config.py` (mirrored in `web/src/lib/site-config.ts`) holds `PAGES_BASE_URL`; every URL-emitting renderer reads it. Project pages ship as a single Astro dynamic route per locale, reusing the existing content JSON. OG images are generated at build time by `astro-og-canvas` from the same content JSON. Chart tooltips are tiny per-component `<script>` blocks — no framework, no external dep.

**Tech Stack:** Python 3.12 + pytest + uv (renderers, tests); Astro 5 + Tailwind 4 + pnpm 10 (web); `astro-og-canvas` (NEW dep, OG image generation); GitHub Actions (CI + Pages deploy).

**Spec reference:** [`docs/superpowers/specs/2026-05-26-phase-5-polish-design.md`](../specs/2026-05-26-phase-5-polish-design.md)

**Branch:** `phase-5-polish` (already created; the spec commit is `b6b6562`)

---

## Tasks at a glance

1. Add `scripts/config.py` + `web/src/lib/site-config.ts` + parity test
2. Refactor `render_jsonresume.py` + `render_text.py` to use `PAGES_BASE_URL`
3. Refactor `render_jsonld.py` to use `PAGES_BASE_URL` + add per-project `CreativeWork` to `@graph`
4. Add `ProjectPage.astro` component
5. Add `/projects/[id].astro` dynamic route (EN)
6. Add `/de/projects/[id].astro` dynamic route (DE)
7. Add `↗ Permalink` to `ProjectsSection.astro`
8. Add hover tooltip to `PublicationsChart.astro` (pie)
9. Add hover tooltip to `PublicationsCumulative.astro` (line)
10. Install `astro-og-canvas` dependency
11. Create OG image route (`web/src/pages/og/[...path].png.ts`) with magazine style
12. Wire OG meta tags into `BaseLayout.astro`
13. Add post-build smoke checks to `pages.yml`
14. Cutover: flip `SITE_DOMAIN` + Astro `site`/`base` + create CNAME
15. Update `CLAUDE.md` + `README.md`

**Sequencing principle:** Tasks 1–13 keep emitted URLs **bitwise-identical to the current state** (`https://jin-homlee.github.io/jin-ho-lee-cv/...`). Task 14 is a single atomic cutover. This means every intermediate commit on the branch produces a working build that could safely deploy to the existing github.io URL if needed.

---

### Task 1: Config constants + parity test

**Files:**
- Create: `scripts/config.py`
- Create: `web/src/lib/site-config.ts`
- Create: `tests/test_config.py`
- Create: `tests/test_config_parity.py`

- [ ] **Step 1: Write failing tests for `scripts/config.py`**

Create `tests/test_config.py`:

```python
"""Pytest assertions for site-wide URL constants."""
from __future__ import annotations

import re


def test_site_domain_is_bare_host():
    """SITE_DOMAIN must be just the host — no scheme, no path, no trailing slash."""
    from scripts.config import SITE_DOMAIN
    assert "://" not in SITE_DOMAIN, "SITE_DOMAIN should not include a scheme"
    assert "/" not in SITE_DOMAIN, "SITE_DOMAIN should not include a path"
    assert not SITE_DOMAIN.endswith("."), "SITE_DOMAIN should not end with '.'"
    assert re.match(r"^[a-z0-9.-]+$", SITE_DOMAIN), f"unexpected chars in SITE_DOMAIN: {SITE_DOMAIN!r}"


def test_site_path_starts_with_slash_or_empty():
    """SITE_PATH is either empty (custom-domain cutover) or a leading-slash path with no trailing slash."""
    from scripts.config import SITE_PATH
    if SITE_PATH:
        assert SITE_PATH.startswith("/"), f"SITE_PATH must start with '/' (got {SITE_PATH!r})"
        assert not SITE_PATH.endswith("/"), f"SITE_PATH must not end with '/' (got {SITE_PATH!r})"


def test_pages_base_url_format():
    """PAGES_BASE_URL: https://<host>[<path>] — no trailing slash."""
    from scripts.config import PAGES_BASE_URL
    assert PAGES_BASE_URL.startswith("https://"), f"PAGES_BASE_URL must be https (got {PAGES_BASE_URL!r})"
    assert not PAGES_BASE_URL.endswith("/"), f"PAGES_BASE_URL must not end with '/' (got {PAGES_BASE_URL!r})"
```

- [ ] **Step 2: Run the test — expect failure (module not found)**

```bash
uv run pytest tests/test_config.py -v
```

Expected: 3 errors, all `ModuleNotFoundError: No module named 'scripts.config'`.

- [ ] **Step 3: Implement `scripts/config.py`**

Create `scripts/config.py`:

```python
"""Site-wide URL constants. One place to flip the canonical site URL.

Initial state mirrors today's github.io project-site URL. The cutover to a
custom domain (Task 14 of the Phase 5 plan) edits only this file + the Astro
config + adds CNAME — no other source changes.
"""
from __future__ import annotations

SITE_DOMAIN: str = "jin-homlee.github.io"  # bare host
SITE_PATH: str = "/jin-ho-lee-cv"           # leading slash, no trailing slash; empty string after cutover
PAGES_BASE_URL: str = f"https://{SITE_DOMAIN}{SITE_PATH}"
```

- [ ] **Step 4: Run the test — expect pass**

```bash
uv run pytest tests/test_config.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Create the TS mirror**

Create `web/src/lib/site-config.ts`:

```ts
// Mirror of scripts/config.py — kept in sync via tests/test_config_parity.py.
// To change the canonical site URL, edit both files together.

export const SITE_DOMAIN = "jin-homlee.github.io";
export const SITE_PATH = "/jin-ho-lee-cv";
export const PAGES_BASE_URL = `https://${SITE_DOMAIN}${SITE_PATH}`;
```

- [ ] **Step 6: Write failing parity test**

Create `tests/test_config_parity.py`:

```python
"""Assert the Python and TypeScript site-config constants stay in sync."""
from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
TS_PATH = REPO_ROOT / "web" / "src" / "lib" / "site-config.ts"


def _extract(ts_source: str, name: str) -> str:
    """Pull a string-literal constant out of the TS file."""
    m = re.search(rf'export const {name} = "([^"]+)"', ts_source)
    assert m, f"could not find `export const {name} = \"...\"` in {TS_PATH}"
    return m.group(1)


def test_site_domain_matches():
    from scripts.config import SITE_DOMAIN
    ts = TS_PATH.read_text()
    assert _extract(ts, "SITE_DOMAIN") == SITE_DOMAIN


def test_site_path_matches():
    from scripts.config import SITE_PATH
    ts = TS_PATH.read_text()
    assert _extract(ts, "SITE_PATH") == SITE_PATH
```

- [ ] **Step 7: Run the parity test — expect pass**

```bash
uv run pytest tests/test_config_parity.py -v
```

Expected: 2 passed.

- [ ] **Step 8: Run the full suite to confirm nothing broke**

```bash
just test
```

Expected: all tests pass.

- [ ] **Step 9: Commit**

```bash
git add scripts/config.py web/src/lib/site-config.ts tests/test_config.py tests/test_config_parity.py
git commit -m "feat: add SITE_DOMAIN config constants (Python + TS, parity-tested)"
```

---

### Task 2: Refactor `render_jsonresume.py` + `render_text.py` to use `PAGES_BASE_URL`

This is a no-op refactor — the URL output stays byte-identical because `PAGES_BASE_URL == "https://jin-homlee.github.io/jin-ho-lee-cv"`. Tests assert URL shape after the change.

**Files:**
- Modify: `scripts/render_jsonresume.py:15`
- Modify: `scripts/render_jsonresume.py:50` (uses `SITE_URL`)
- Modify: `scripts/render_text.py:15`
- Modify: `scripts/render_text.py:44` (uses `SITE_URL`)
- Modify: `tests/test_render_jsonresume.py` (add URL assertion)
- Modify: `tests/test_render_text.py` (add URL assertion)

- [ ] **Step 1: Write failing test in `test_render_jsonresume.py`**

Append to `tests/test_render_jsonresume.py`:

```python
def test_basics_url_uses_pages_base(doc):
    from scripts.config import PAGES_BASE_URL
    assert doc["basics"]["url"].startswith(PAGES_BASE_URL)
```

- [ ] **Step 2: Run that test — expect pass (current `SITE_URL` already matches `PAGES_BASE_URL` + trailing slash)**

```bash
uv run pytest tests/test_render_jsonresume.py::test_basics_url_uses_pages_base -v
```

Expected: PASS (current URL `https://jin-homlee.github.io/jin-ho-lee-cv/` starts with `PAGES_BASE_URL`). If it FAILS, the constants drifted — stop and debug `scripts/config.py`.

- [ ] **Step 3: Refactor `render_jsonresume.py`**

In `scripts/render_jsonresume.py`, replace lines 13–15:

```python
REPO_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = REPO_ROOT / "content"
SITE_URL = "https://jin-homlee.github.io/jin-ho-lee-cv/"
```

with:

```python
from scripts.config import PAGES_BASE_URL

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = REPO_ROOT / "content"
SITE_URL = f"{PAGES_BASE_URL}/"  # trailing slash preserved — JSON Resume `basics.url` convention
```

Note: `PAGES_BASE_URL` has **no** trailing slash; `SITE_URL` adds it back for the renderer's existing semantics. Leave the rest of the file untouched.

- [ ] **Step 4: Run the renderer test — expect pass**

```bash
uv run pytest tests/test_render_jsonresume.py -v
```

Expected: all pass (including the new assertion).

- [ ] **Step 5: Write failing test in `test_render_text.py`**

Append to `tests/test_render_text.py`:

```python
def test_header_url_uses_pages_base(en_text):
    from scripts.config import PAGES_BASE_URL
    assert PAGES_BASE_URL in en_text, f"PAGES_BASE_URL ({PAGES_BASE_URL!r}) missing from header"
```

- [ ] **Step 6: Run it — expect pass**

```bash
uv run pytest tests/test_render_text.py::test_header_url_uses_pages_base -v
```

Expected: PASS (current text contains the full URL).

- [ ] **Step 7: Refactor `render_text.py`**

In `scripts/render_text.py`, replace lines 13–16:

```python
REPO_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = REPO_ROOT / "content"
SITE_URL = "https://jin-homlee.github.io/jin-ho-lee-cv/"
DIVIDER = "=" * 80
```

with:

```python
from scripts.config import PAGES_BASE_URL

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = REPO_ROOT / "content"
SITE_URL = f"{PAGES_BASE_URL}/"
DIVIDER = "=" * 80
```

- [ ] **Step 8: Run the text-renderer test — expect pass**

```bash
uv run pytest tests/test_render_text.py -v
```

Expected: all pass.

- [ ] **Step 9: Run the full suite + verify byte-identical output**

```bash
just build-resume && just build-text
git diff --stat dist/  # if dist/ is gitignored, this is empty
```

Then byte-compare against a checkpoint:

```bash
sha256sum dist/resume.json dist/cv-en.txt dist/cv-de.txt
```

These hashes should match what you'd get from `main` for the same content. (If you want to be exhaustive: `git stash; just build-resume; sha256sum dist/resume.json; git stash pop; just build-resume; sha256sum dist/resume.json` — both must match.)

- [ ] **Step 10: Commit**

```bash
git add scripts/render_jsonresume.py scripts/render_text.py tests/test_render_jsonresume.py tests/test_render_text.py
git commit -m "refactor: route render_jsonresume + render_text URLs through PAGES_BASE_URL"
```

---

### Task 3: Refactor `render_jsonld.py` to use `PAGES_BASE_URL` + add per-project `CreativeWork` to `@graph`

Two changes in one task:

1. URL constants → `PAGES_BASE_URL`.
2. Each project gains a `CreativeWork` entry in `@graph` so search engines can crawl `/projects/{id}/` once those pages exist (Task 5–6).

**Files:**
- Modify: `scripts/render_jsonld.py`
- Modify: `tests/test_render_jsonld.py`

- [ ] **Step 1: Write failing tests in `test_render_jsonld.py`**

Append to `tests/test_render_jsonld.py`:

```python
def test_url_uses_pages_base(doc):
    from scripts.config import PAGES_BASE_URL
    assert doc["url"].startswith(PAGES_BASE_URL)


def test_image_uses_pages_base(doc):
    from scripts.config import PAGES_BASE_URL
    assert doc["image"].startswith(PAGES_BASE_URL)


def test_graph_includes_project_creativeworks(doc):
    """Every project in content/projects/ should appear in @graph as a CreativeWork."""
    from scripts.content_loader import load_content
    from scripts.langstring import resolve_langstrings
    content = resolve_langstrings(load_content(CONTENT_DIR, lang="en"), lang="en")
    expected_ids = set(content["projects"].keys())
    works = [g for g in doc["@graph"] if g["@type"] == "CreativeWork"]
    assert len(works) == len(expected_ids), f"expected {len(expected_ids)} CreativeWorks, got {len(works)}"
    work_urls = {w["url"] for w in works}
    for pid in expected_ids:
        assert any(pid in url for url in work_urls), f"no CreativeWork URL contains project id {pid!r}"


def test_creativework_urls_use_pages_base(doc):
    from scripts.config import PAGES_BASE_URL
    works = [g for g in doc["@graph"] if g["@type"] == "CreativeWork"]
    for w in works:
        assert w["url"].startswith(PAGES_BASE_URL + "/projects/"), f"unexpected CreativeWork URL: {w['url']!r}"
```

- [ ] **Step 2: Run those tests — expect failures**

```bash
uv run pytest tests/test_render_jsonld.py -v
```

Expected: `test_url_uses_pages_base` PASS (current `SITE_URL` already starts with `PAGES_BASE_URL`), `test_image_uses_pages_base` PASS (same), `test_graph_includes_project_creativeworks` FAIL (no CreativeWorks yet), `test_creativework_urls_use_pages_base` FAIL (no CreativeWorks yet).

- [ ] **Step 3: Refactor `render_jsonld.py` — URL constants first**

In `scripts/render_jsonld.py`, replace lines 13–16:

```python
REPO_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = REPO_ROOT / "content"
SITE_URL = "https://jin-homlee.github.io/jin-ho-lee-cv/"
PHOTO_URL = f"{SITE_URL}photo.jpg"
```

with:

```python
from scripts.config import PAGES_BASE_URL

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = REPO_ROOT / "content"
SITE_URL = f"{PAGES_BASE_URL}/"
PHOTO_URL = f"{PAGES_BASE_URL}/photo.jpg"
```

- [ ] **Step 4: Add `_projects()` helper to `render_jsonld.py`**

Add this function above `to_jsonld()` (after `_publications()`):

```python
def _projects(content: dict) -> list[dict]:
    """One CreativeWork per project, URL points at the eventual /projects/{id}/ page."""
    out = []
    for pid, proj in content["projects"].items():
        item: dict = {
            "@type": "CreativeWork",
            "name": proj["title"],
            "url": f"{PAGES_BASE_URL}/projects/{pid}/",
            "description": proj["summary"],
            "dateCreated": proj["period"]["start"],
            "keywords": list(proj.get("technologies", [])),
        }
        out.append(item)
    return out
```

- [ ] **Step 5: Wire `_projects()` into the `@graph`**

In `to_jsonld()`, change the final line from:

```python
    doc["@graph"] = _publications(pubs)
    return doc
```

to:

```python
    doc["@graph"] = _publications(pubs) + _projects(content)
    return doc
```

- [ ] **Step 6: Run the renderer tests — expect pass**

```bash
uv run pytest tests/test_render_jsonld.py -v
```

Expected: all pass.

Note: `test_publications_count_matches_bib` asserts on entries where `@type == "ScholarlyArticle"` only, so it's not affected by the new CreativeWorks. If it fails, re-check the filter in that test.

- [ ] **Step 7: Run full suite**

```bash
just test
```

Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add scripts/render_jsonld.py tests/test_render_jsonld.py
git commit -m "feat(jsonld): route URLs through PAGES_BASE_URL + add per-project CreativeWork entries"
```

---

### Task 4: Add `ProjectPage.astro` component

Renders one project's existing fields as a full-page view. No new content authoring — purely a different layout over `Project` data.

**Files:**
- Create: `web/src/components/ProjectPage.astro`

- [ ] **Step 1: Create the component**

Create `web/src/components/ProjectPage.astro`:

```astro
---
import type { Project, Labels, Lang } from "../types/content";
import { formatPeriod } from "../lib/period";

interface Props {
  project: Project;
  labels: Labels;
  lang: Lang;
}

const { project, labels, lang } = Astro.props;

const backLabel = { en: "← Back to CV", de: "← Zurück zum Lebenslauf" }[lang];
const roleLabel = { en: "Role", de: "Rolle" }[lang];
const periodLabel = { en: "Period", de: "Zeitraum" }[lang];
const techLabel = { en: "Technologies", de: "Technologien" }[lang];
const contribLabel = { en: "Contributions", de: "Beiträge" }[lang];
const outcomeLabel = { en: "Outcome", de: "Ergebnis" }[lang];

const backHref = lang === "en" ? `/#${project.id}` : `/de/#${project.id}`;
---
<article class="mx-auto max-w-3xl">
  <nav class="mb-4 text-sm">
    <a href={backHref} class="text-neutral-600 underline hover:text-neutral-900">{backLabel}</a>
  </nav>

  <header class="mb-6">
    <p class="font-mono text-xs text-neutral-500">{project.id}</p>
    <h1 class="text-2xl font-semibold text-[#1f3a68] md:text-3xl">{project.title}</h1>
    <p class="mt-2 text-sm text-neutral-600">
      {project.role} · {formatPeriod(project.period, labels)}
    </p>
  </header>

  <p class="mb-6 text-base text-neutral-800">{project.summary}</p>

  <section class="mb-6">
    <h2 class="mb-2 text-xs font-semibold uppercase tracking-wider text-neutral-500">{techLabel}</h2>
    <p class="flex flex-wrap gap-1">
      {project.technologies.map((t) => (
        <span class="rounded bg-neutral-100 px-2 py-0.5 text-xs text-neutral-700">{t}</span>
      ))}
    </p>
  </section>

  <section class="mb-6">
    <h2 class="mb-2 text-xs font-semibold uppercase tracking-wider text-neutral-500">{contribLabel}</h2>
    <ul class="space-y-1 text-sm text-neutral-800">
      {project.contributions.map((c) => (
        <li class="flex gap-2">
          <span aria-hidden="true" class="text-neutral-400">·</span>
          <span>{c}</span>
        </li>
      ))}
    </ul>
  </section>

  <section class="mb-6 rounded-md bg-[#f4f7fb] p-4">
    <h2 class="mb-1 text-xs font-semibold uppercase tracking-wider text-[#1f3a68]">{outcomeLabel}</h2>
    <p class="text-sm italic text-neutral-700">{project.outcome}</p>
  </section>
</article>
```

- [ ] **Step 2: Type-check**

```bash
pnpm --dir web check
```

Expected: 0 errors, 0 warnings (unused imports OK if any flagged — fix them).

- [ ] **Step 3: Commit**

```bash
git add web/src/components/ProjectPage.astro
git commit -m "feat(web): add ProjectPage component for per-project deep-dive pages"
```

---

### Task 5: Add `/projects/[id].astro` dynamic route (EN)

**Files:**
- Create: `web/src/pages/projects/[id].astro`

- [ ] **Step 1: Create the route**

Create `web/src/pages/projects/[id].astro`:

```astro
---
import contentEn from "../../data/content.en.json";
import BaseLayout from "../../layouts/BaseLayout.astro";
import ProjectPage from "../../components/ProjectPage.astro";
import type { ContentData } from "../../types/content";

const data = contentEn as ContentData;

export function getStaticPaths() {
  return Object.keys(contentEn.projects).map((id) => ({ params: { id } }));
}

const { id } = Astro.params;
const project = data.projects[id as string];
const labels = data.labels;
---
<BaseLayout lang="en" data={data}>
  <ProjectPage project={project} labels={labels} lang="en" />
</BaseLayout>
```

- [ ] **Step 2: Regenerate content JSON + run dev server briefly to verify**

```bash
just web-data
pnpm --dir web build
```

Expected: build succeeds. Check the output:

```bash
ls web/dist/projects/
```

Expected: a folder per project id (`L1/`, `L2/`, …, `C1/`, …), each containing `index.html`.

- [ ] **Step 3: Spot-check one HTML file**

```bash
grep -l "Cancer Neoantigen" web/dist/projects/L1/index.html
```

Expected: file is non-empty and contains the project title.

- [ ] **Step 4: Commit**

```bash
git add web/src/pages/projects/[id].astro
git commit -m "feat(web): add /projects/[id]/ dynamic route (EN)"
```

---

### Task 6: Add `/de/projects/[id].astro` dynamic route (DE)

**Files:**
- Create: `web/src/pages/de/projects/[id].astro`

- [ ] **Step 1: Create the route**

Create `web/src/pages/de/projects/[id].astro`:

```astro
---
import contentDe from "../../../data/content.de.json";
import BaseLayout from "../../../layouts/BaseLayout.astro";
import ProjectPage from "../../../components/ProjectPage.astro";
import type { ContentData } from "../../../types/content";

const data = contentDe as ContentData;

export function getStaticPaths() {
  return Object.keys(contentDe.projects).map((id) => ({ params: { id } }));
}

const { id } = Astro.params;
const project = data.projects[id as string];
const labels = data.labels;
---
<BaseLayout lang="de" data={data}>
  <ProjectPage project={project} labels={labels} lang="de" />
</BaseLayout>
```

- [ ] **Step 2: Build + verify**

```bash
pnpm --dir web build
ls web/dist/de/projects/
test -f web/dist/de/projects/L1/index.html && echo "ok"
```

Expected: `ok` printed; folder structure mirrors EN.

- [ ] **Step 3: Commit**

```bash
git add web/src/pages/de/projects/[id].astro
git commit -m "feat(web): add /de/projects/[id]/ dynamic route (DE)"
```

---

### Task 7: Add `↗ Permalink` to `ProjectsSection.astro`

**Files:**
- Modify: `web/src/components/ProjectsSection.astro:42–48`

- [ ] **Step 1: Add the permalink anchor inside each `<header>`**

In `web/src/components/ProjectsSection.astro`, after the existing `<header>` block (around line 48), inside the `<article>`, add a permalink link. The current header section is:

```astro
            <header class="mb-2">
              <p class="text-xs font-mono text-neutral-500">{p.id}</p>
              <h4 class="text-base font-semibold text-neutral-900">{p.title}</h4>
              <p class="text-xs text-neutral-500">
                {p.role} · {formatPeriod(p.period, labels)}
              </p>
            </header>
```

Change to:

```astro
            <header class="mb-2">
              <p class="text-xs font-mono text-neutral-500">{p.id}</p>
              <h4 class="text-base font-semibold text-neutral-900">
                {p.title}
                <a
                  href={lang === "en" ? `/projects/${p.id}/` : `/de/projects/${p.id}/`}
                  class="ml-1 text-xs font-normal text-neutral-400 hover:text-[#1f3a68]"
                  aria-label={lang === "en" ? `Open project page for ${p.title}` : `Projektseite für ${p.title} öffnen`}
                >↗</a>
              </h4>
              <p class="text-xs text-neutral-500">
                {p.role} · {formatPeriod(p.period, labels)}
              </p>
            </header>
```

- [ ] **Step 2: Build + verify**

```bash
pnpm --dir web build
grep -c "↗" web/dist/index.html
```

Expected: count is ≥ 1 (one permalink per project on the homepage).

- [ ] **Step 3: Commit**

```bash
git add web/src/components/ProjectsSection.astro
git commit -m "feat(web): add ↗ permalink anchor to each inline project block"
```

---

### Task 8: Add hover tooltip to `PublicationsChart.astro` (pie)

Tiny inline `<script>` + `<style>` block. No client framework. Touch devices get tap-to-toggle.

**Files:**
- Modify: `web/src/components/PublicationsChart.astro`

- [ ] **Step 1: Bake data attributes onto each `<path>`**

In `web/src/components/PublicationsChart.astro`, change the `<path>` emission inside the `<svg>` (currently around line 68) from:

```astro
    {arcs.map((arc) => <path d={arc.d} fill={arc.color} />)}
```

to:

```astro
    {arcs.map((arc) => (
      <path
        d={arc.d}
        fill={arc.color}
        data-label={arc.label}
        data-count={arc.count}
        data-pct={((arc.count / total) * 100).toFixed(1)}
        class="cursor-pointer"
      />
    ))}
```

- [ ] **Step 2: Wrap the `<figure>` in a relatively-positioned container so the tooltip anchors to it**

Change the opening `<figure class="my-6 flex items-center gap-6">` to:

```astro
<figure class="relative my-6 flex items-center gap-6">
```

- [ ] **Step 3: Add the tooltip element + style + script before the closing `</figure>`**

Right before `</figure>` (after the existing `<ul>`), insert:

```astro
  <div
    class="pub-tooltip pointer-events-none absolute hidden rounded bg-neutral-900 px-2 py-1 text-xs text-white shadow-lg"
    role="status"
    aria-live="polite"
  ></div>
</figure>

<script>
  // Hover (or tap) a pie slice to surface label + count + percentage.
  const figures = document.querySelectorAll<HTMLElement>("figure.relative");
  for (const fig of figures) {
    const tooltip = fig.querySelector<HTMLElement>(".pub-tooltip");
    const paths = fig.querySelectorAll<SVGPathElement>("svg path[data-label]");
    if (!tooltip || paths.length === 0) continue;

    const show = (e: MouseEvent | TouchEvent, target: SVGPathElement) => {
      const label = target.dataset.label ?? "";
      const count = target.dataset.count ?? "";
      const pct = target.dataset.pct ?? "";
      tooltip.textContent = `${label}: ${count} (${pct}%)`;
      tooltip.classList.remove("hidden");
      const rect = fig.getBoundingClientRect();
      const point = "touches" in e ? e.touches[0] : e;
      tooltip.style.left = `${point.clientX - rect.left + 8}px`;
      tooltip.style.top = `${point.clientY - rect.top + 8}px`;
    };
    const hide = () => tooltip.classList.add("hidden");

    paths.forEach((p) => {
      p.addEventListener("mouseenter", (e) => show(e, p));
      p.addEventListener("mousemove", (e) => show(e, p));
      p.addEventListener("mouseleave", hide);
      // Touch: tap toggles
      p.addEventListener("touchstart", (e) => {
        e.preventDefault();
        if (tooltip.classList.contains("hidden")) show(e, p);
        else hide();
      }, { passive: false });
    });
    // Dismiss on outside tap
    document.addEventListener("touchstart", (e) => {
      if (!fig.contains(e.target as Node)) hide();
    }, { passive: true });
  }
</script>
```

**Note:** the script's selector (`figure.relative`) will also match the cumulative chart figure once Task 9 wraps that too. Each figure scopes its own tooltip via the local `fig` variable, so the cross-component sharing is safe.

- [ ] **Step 4: Build + verify**

```bash
pnpm --dir web build
grep -c "pub-tooltip" web/dist/index.html
```

Expected: count ≥ 1.

- [ ] **Step 5: Manual smoke test in dev**

```bash
just web-dev
# Open http://localhost:4321/, scroll to Publications, hover a pie wedge.
# Tooltip should appear with `label: count (pct%)` formatting.
# Stop the dev server with Ctrl+C when done.
```

If the tooltip doesn't appear, check browser DevTools console for script errors.

- [ ] **Step 6: Commit**

```bash
git add web/src/components/PublicationsChart.astro
git commit -m "feat(web): add hover tooltip to PublicationsChart pie slices"
```

---

### Task 9: Add hover tooltip to `PublicationsCumulative.astro` (line)

Same pattern as Task 8, but per-year. Tooltip shows `year: cum (+delta)`.

**Files:**
- Modify: `web/src/components/PublicationsCumulative.astro`

- [ ] **Step 1: Add invisible hover-target rectangles per year**

In `web/src/components/PublicationsCumulative.astro`, add a helper that emits one transparent `<rect>` per data year, the rect spanning the full chart height. Insert these inside the `<svg>`, AFTER the path lines and BEFORE the text labels (around line 105, after the `<path d={linePath} ... />` line). The rect targets must carry `data-year`, `data-cum`, `data-delta` attributes.

Add this block:

```astro
    {points.map((pt, i) => {
      const x = xScale(pt.year);
      const prevCum = i === 0 ? 0 : points[i - 1].cum;
      const delta = pt.cum - prevCum;
      // Half-year bands left and right of each data point
      const halfBand = (chartRight - chartLeft) / xDomainSpan / 2;
      return (
        <rect
          x={x - halfBand}
          y={chartTop}
          width={halfBand * 2}
          height={chartBottom - chartTop}
          fill="transparent"
          data-year={pt.year}
          data-cum={pt.cum}
          data-delta={delta}
          class="cursor-pointer"
        />
      );
    })}
```

- [ ] **Step 2: Wrap the `<figure>` in `relative`**

Change `<figure class="my-6">` to `<figure class="relative my-6">`.

- [ ] **Step 3: Add tooltip element + script before `</figure>`**

After the existing `<figcaption>` and before `</figure>`, insert:

```astro
  <div
    class="pub-tooltip pointer-events-none absolute hidden rounded bg-neutral-900 px-2 py-1 text-xs text-white shadow-lg"
    role="status"
    aria-live="polite"
  ></div>
</figure>

<script>
  // Hover (or tap) a year band on the cumulative chart to show year + cumulative + delta.
  const figures = document.querySelectorAll<HTMLElement>("figure.relative");
  for (const fig of figures) {
    const tooltip = fig.querySelector<HTMLElement>(".pub-tooltip");
    const rects = fig.querySelectorAll<SVGRectElement>("svg rect[data-year]");
    if (!tooltip || rects.length === 0) continue;

    const show = (e: MouseEvent | TouchEvent, target: SVGRectElement) => {
      const year = target.dataset.year ?? "";
      const cum = target.dataset.cum ?? "";
      const delta = target.dataset.delta ?? "";
      const deltaStr = Number(delta) > 0 ? ` (+${delta})` : "";
      tooltip.textContent = `${year}: ${cum}${deltaStr}`;
      tooltip.classList.remove("hidden");
      const rect = fig.getBoundingClientRect();
      const point = "touches" in e ? e.touches[0] : e;
      tooltip.style.left = `${point.clientX - rect.left + 8}px`;
      tooltip.style.top = `${point.clientY - rect.top + 8}px`;
    };
    const hide = () => tooltip.classList.add("hidden");

    rects.forEach((r) => {
      r.addEventListener("mouseenter", (e) => show(e, r));
      r.addEventListener("mousemove", (e) => show(e, r));
      r.addEventListener("mouseleave", hide);
      r.addEventListener("touchstart", (e) => {
        e.preventDefault();
        if (tooltip.classList.contains("hidden")) show(e, r);
        else hide();
      }, { passive: false });
    });
    document.addEventListener("touchstart", (e) => {
      if (!fig.contains(e.target as Node)) hide();
    }, { passive: true });
  }
</script>
```

**Note:** this is a second `<script>` block in the build. Astro handles script bundling per-component; both blocks ship and both select on `figure.relative`. The selector approach is safe because each script only attaches handlers to elements matching its OWN data attributes (`data-label` for pie paths vs. `data-year` for cumulative rects), so they don't trample on each other.

- [ ] **Step 4: Build + verify**

```bash
pnpm --dir web build
grep -c 'data-year' web/dist/index.html
```

Expected: count ≥ 1 (one rect per data year).

- [ ] **Step 5: Manual smoke test**

```bash
just web-dev
# Open http://localhost:4321/, scroll to Publications,
# hover over different years on the cumulative line — tooltip should show year: cumulative (+delta).
# Stop with Ctrl+C.
```

- [ ] **Step 6: Commit**

```bash
git add web/src/components/PublicationsCumulative.astro
git commit -m "feat(web): add hover tooltip to cumulative-publications chart"
```

---

### Task 10: Install `astro-og-canvas` dependency

**Files:**
- Modify: `web/package.json`
- Modify: `web/pnpm-lock.yaml`

- [ ] **Step 1: Install**

```bash
pnpm --dir web add astro-og-canvas
```

This adds to `dependencies` and updates the lockfile.

- [ ] **Step 2: Verify build still passes**

```bash
pnpm --dir web build
```

Expected: build succeeds. The dependency is unused so far — no behavior change.

- [ ] **Step 3: Commit**

```bash
git add web/package.json web/pnpm-lock.yaml
git commit -m "chore(web): add astro-og-canvas dependency"
```

---

### Task 11: Create OG image route (`web/src/pages/og/[...path].png.ts`) — magazine style

`astro-og-canvas`'s `OGImageRoute()` helper exports `getStaticPaths` + `GET` for a single dynamic route. We give it a `pages` object keyed by URL path; for each key it emits `/og/<key>.png` at build time.

Magazine style chosen during brainstorming: soft `#f4f7fb` background, uppercase `#1f3a68` kicker, large `#1f3a68` title, optional subtitle in `#444`, metadata pills at the bottom.

**Files:**
- Create: `web/src/pages/og/[...path].png.ts`

- [ ] **Step 1: Create the route**

Create `web/src/pages/og/[...path].png.ts`:

```ts
import { OGImageRoute } from "astro-og-canvas";
import contentEn from "../../data/content.en.json";
import contentDe from "../../data/content.de.json";
import type { ContentData, Project, Lang } from "../../types/content";

const en = contentEn as ContentData;
const de = contentDe as ContentData;

// Page object shape consumed by getImageOptions below.
interface OgPage {
  title: string;
  kicker: string;       // small uppercase label on top
  subtitle?: string;    // optional second line under the title
  meta: { label: string; value: string }[];  // 1-3 metadata pills at the bottom
}

function homepagePage(data: ContentData, lang: Lang): OgPage {
  const name = `${data.personal.name.given} ${data.personal.name.family}`;
  return {
    kicker: lang === "en" ? `${name} — CV` : `${name} — Lebenslauf`,
    title: data.profile.tagline,
    subtitle: data.personal.headline,
    meta: [
      { label: lang === "en" ? "Based in" : "Standort", value: data.personal.location.city },
      { label: lang === "en" ? "Languages" : "Sprachen", value: data.languages.map((l) => l.name).join(" · ") },
    ],
  };
}

function projectPage(project: Project, lang: Lang, dataName: string): OgPage {
  const techPreview = project.technologies.slice(0, 3).join(" · ");
  return {
    kicker: lang === "en" ? `${dataName} — Project Brief` : `${dataName} — Projektkurzbeschreibung`,
    title: project.title,
    subtitle: project.role,
    meta: [
      { label: lang === "en" ? "Period" : "Zeitraum",
        value: `${project.period.start}${project.period.end ? ` – ${project.period.end}` : ""}` },
      { label: lang === "en" ? "Stack" : "Technologien", value: techPreview },
      { label: lang === "en" ? "Project" : "Projekt", value: project.id },
    ],
  };
}

const enName = `${en.personal.name.given} ${en.personal.name.family}`;
const deName = `${de.personal.name.given} ${de.personal.name.family}`;

const pages: Record<string, OgPage> = {
  "index-en": homepagePage(en, "en"),
  "index-de": homepagePage(de, "de"),
};
for (const [id, project] of Object.entries(en.projects)) {
  pages[`projects-${id}-en`] = projectPage(project, "en", enName);
}
for (const [id, project] of Object.entries(de.projects)) {
  pages[`projects-${id}-de`] = projectPage(project, "de", deName);
}

export const { getStaticPaths, GET } = OGImageRoute({
  param: "path",
  pages,
  getImageOptions: (_path, page: OgPage) => ({
    title: page.title,
    description: [
      page.kicker,
      page.subtitle ?? "",
      ...page.meta.map((m) => `${m.label}: ${m.value}`),
    ].filter(Boolean).join("\n"),
    bgGradient: [[244, 247, 251]],
    border: { color: [31, 58, 104], width: 8, side: "inline-start" },
    padding: 60,
    font: {
      title: {
        size: 56,
        color: [31, 58, 104],
        weight: "Bold",
        families: ["IBM Plex Sans", "Inter", "Helvetica", "Arial"],
        lineHeight: 1.15,
      },
      description: {
        size: 22,
        color: [68, 68, 68],
        families: ["IBM Plex Sans", "Inter", "Helvetica", "Arial"],
        lineHeight: 1.4,
      },
    },
  }),
});
```

**Note on font availability:** `astro-og-canvas` uses Satori under the hood, which needs actual font binaries. By default it falls back to a bundled font if IBM Plex Sans is not installed system-wide. The strings in `families` are the lookup order. For a polished output, install local font files; the build will succeed regardless of which font is picked.

- [ ] **Step 2: Build + verify OG images are emitted**

```bash
pnpm --dir web build
ls web/dist/og/ | head
test -f web/dist/og/index-en.png && echo "homepage ok"
test -f web/dist/og/projects-L1-en.png && echo "project L1 ok"
```

Expected: both `echo` lines fire. The `web/dist/og/` directory contains 20 PNGs (2 homepages + 18 project files).

- [ ] **Step 3: Sanity-check file size**

```bash
ls -la web/dist/og/index-en.png
```

Expected: file size > 5 KB (a blank/failed render would be ≪ 5 KB).

- [ ] **Step 4: Commit**

```bash
git add web/src/pages/og/
git commit -m "feat(web): generate per-page OG images via astro-og-canvas (magazine style)"
```

---

### Task 12: Wire OG meta tags into `BaseLayout.astro`

The layout currently emits only `<meta name="description">`, `<link rel="canonical">`, `<title>`, and the JSON-LD `<script>`. Add OG + Twitter tags and the page-specific `og:image` URL.

**Files:**
- Modify: `web/src/layouts/BaseLayout.astro`

- [ ] **Step 1: Extend the props**

Replace the `Props` interface in `web/src/layouts/BaseLayout.astro` (lines 6–9):

```ts
interface Props {
  lang: Lang;
  data: ContentData;
}
```

with:

```ts
interface Props {
  lang: Lang;
  data: ContentData;
  // OG metadata — pages pass these. Homepage and project pages compute their own.
  ogSlug?: string;       // e.g. "index-en", "projects-L1-en"
  ogTitle?: string;      // override <title> and og:title
  ogDescription?: string;
  ogType?: "profile" | "article" | "website";
}
```

- [ ] **Step 2: Update the destructure + compute defaults**

Replace lines 11–15:

```ts
const { lang, data } = Astro.props;
const title = `${data.personal.name.given} ${data.personal.name.family} — ${
  lang === "en" ? "CV" : "Lebenslauf"
}`;
const description = data.profile.tagline;
```

with:

```ts
import { PAGES_BASE_URL } from "../lib/site-config";

const { lang, data, ogSlug, ogTitle, ogDescription, ogType } = Astro.props;
const defaultTitle = `${data.personal.name.given} ${data.personal.name.family} — ${
  lang === "en" ? "CV" : "Lebenslauf"
}`;
const title = ogTitle ?? defaultTitle;
const description = ogDescription ?? data.profile.tagline;
const slug = ogSlug ?? `index-${lang}`;
const ogImageUrl = `${PAGES_BASE_URL}/og/${slug}.png`;
const canonicalUrl = `${PAGES_BASE_URL}${Astro.url.pathname}`;
const resolvedOgType = ogType ?? "profile";
```

- [ ] **Step 3: Inject the OG/Twitter meta into `<head>`**

Replace the existing `<head>` body (lines 19–26):

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

with:

```astro
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <meta name="description" content={description} />
    <link rel="canonical" href={canonicalUrl} />
    <title>{title}</title>

    <meta property="og:type" content={resolvedOgType} />
    <meta property="og:title" content={title} />
    <meta property="og:description" content={description} />
    <meta property="og:url" content={canonicalUrl} />
    <meta property="og:image" content={ogImageUrl} />
    <meta property="og:image:width" content="1200" />
    <meta property="og:image:height" content="630" />
    <meta property="og:image:alt" content={title} />

    <meta name="twitter:card" content="summary_large_image" />
    <meta name="twitter:title" content={title} />
    <meta name="twitter:description" content={description} />
    <meta name="twitter:image" content={ogImageUrl} />

    <script type="application/ld+json" set:html={jsonld}></script>
  </head>
```

- [ ] **Step 4: Pass `ogSlug` + `ogType` from project pages**

In `web/src/pages/projects/[id].astro`, replace the `<BaseLayout>` call:

```astro
<BaseLayout lang="en" data={data}>
```

with:

```astro
<BaseLayout
  lang="en"
  data={data}
  ogSlug={`projects-${id}-en`}
  ogTitle={`${project.title} — ${data.personal.name.given} ${data.personal.name.family}`}
  ogDescription={project.summary}
  ogType="article"
>
```

In `web/src/pages/de/projects/[id].astro`, do the same with `en` → `de`.

- [ ] **Step 5: Build + verify**

```bash
pnpm --dir web build
grep -o 'og:image" content="[^"]*"' web/dist/index.html | head
grep -o 'og:image" content="[^"]*"' web/dist/projects/L1/index.html | head
```

Expected: homepage emits `og:image" content="https://jin-homlee.github.io/jin-ho-lee-cv/og/index-en.png"`; project page emits `…/og/projects-L1-en.png`.

- [ ] **Step 6: Commit**

```bash
git add web/src/layouts/BaseLayout.astro "web/src/pages/projects/[id].astro" "web/src/pages/de/projects/[id].astro"
git commit -m "feat(web): wire OG/Twitter meta tags into BaseLayout"
```

---

### Task 13: Add post-build smoke checks to `pages.yml`

Catches three failure modes at deploy time: missing project HTML, missing/blank OG images, stale base path in built HTML.

**Files:**
- Modify: `.github/workflows/pages.yml`

- [ ] **Step 1: Add the smoke step**

In `.github/workflows/pages.yml`, after the existing `Build site` step (around line 57) and BEFORE `Upload Pages artifact` (line 59), insert:

```yaml
      - name: Smoke-check build outputs
        run: |
          set -euo pipefail
          # Homepages
          test -f web/dist/index.html
          test -f web/dist/de/index.html
          # Project pages — L1 is a representative spot-check; if dynamic routes
          # enumerated 0 projects, all 9 ids would be missing simultaneously.
          test -f web/dist/projects/L1/index.html
          test -f web/dist/de/projects/L1/index.html
          # OG images — homepage + one project page, both langs
          test -f web/dist/og/index-en.png
          test -f web/dist/og/index-de.png
          test -f web/dist/og/projects-L1-en.png
          test -f web/dist/og/projects-L1-de.png
          # OG image size sanity (> 5KB rules out blank/failed renders)
          size=$(stat -c%s web/dist/og/index-en.png 2>/dev/null || stat -f%z web/dist/og/index-en.png)
          [ "$size" -gt 5120 ] || (echo "OG image too small ($size bytes) — generation likely failed" && exit 1)
          # OG meta wired into pages
          grep -q 'property="og:image"' web/dist/index.html
          grep -q 'property="og:image"' web/dist/projects/L1/index.html
```

- [ ] **Step 2: Lint the workflow locally (optional, if you have actionlint)**

```bash
actionlint .github/workflows/pages.yml 2>/dev/null || echo "actionlint not installed; skipping"
```

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/pages.yml
git commit -m "ci(pages): add post-build smoke checks for project pages + OG images"
```

---

### Task 14: Cutover — flip `SITE_DOMAIN` + Astro `site`/`base` + create CNAME

Single commit that flips the canonical URL. Before this commit, the branch builds against `jin-homlee.github.io/jin-ho-lee-cv`; after this commit, against the custom domain. **DNS must be configured before merging to `main`** (see Step 6).

**Files:**
- Modify: `scripts/config.py:9–10`
- Modify: `web/src/lib/site-config.ts:4–5`
- Modify: `web/astro.config.mjs:5–6`
- Create: `web/public/CNAME`

- [ ] **Step 1: Pick the final domain**

Decide the actual domain. The plan uses `cv.jinholee.com` as a placeholder in the steps below — substitute the real one consistently in every step.

- [ ] **Step 2: Update Python config**

Edit `scripts/config.py`:

```python
SITE_DOMAIN: str = "cv.jinholee.com"   # was: "jin-homlee.github.io"
SITE_PATH: str = ""                     # was: "/jin-ho-lee-cv"
```

- [ ] **Step 3: Update TS mirror**

Edit `web/src/lib/site-config.ts`:

```ts
export const SITE_DOMAIN = "cv.jinholee.com";
export const SITE_PATH = "";
```

- [ ] **Step 4: Update Astro config**

In `web/astro.config.mjs`, change lines 5–6 from:

```js
  site: "https://jin-homlee.github.io",
  base: "/jin-ho-lee-cv/",
```

to:

```js
  site: "https://cv.jinholee.com",
  base: "/",
```

- [ ] **Step 5: Create CNAME**

Create `web/public/CNAME` with a single line containing the bare domain:

```
cv.jinholee.com
```

(No protocol, no trailing newline beyond one. GitHub Pages reads this exact filename in the publish root.)

- [ ] **Step 6: Document DNS instructions (manual step before merge)**

Add a quick note to your local TODO that before merging this branch to `main`, you must:

1. Add a DNS record at your registrar: CNAME `cv` → `jin-homlee.github.io.` (trailing dot).
2. Wait for propagation (`dig cv.jinholee.com` should return the github.io CNAME).
3. In repo Settings → Pages, set "Custom domain" to `cv.jinholee.com` and tick "Enforce HTTPS" once the certificate provisions (~minutes after the first deploy with `CNAME` present).

These steps are NOT in the plan because they're outside the repo. Skipping any of them means the live deploy 404s.

- [ ] **Step 7: Run the full test suite**

```bash
just test
```

Expected: all pass. The `test_config_parity.py` test asserts the TS and Python constants match.

- [ ] **Step 8: Build the site locally and verify**

```bash
just web-build
grep -c '"https://jin-homlee.github.io/jin-ho-lee-cv' web/dist/index.html
grep -c '"https://cv.jinholee.com' web/dist/index.html
```

Expected: first grep returns `0`, second returns ≥ 1.

Also confirm the OG image URLs flipped:

```bash
grep -o 'og:image" content="[^"]*"' web/dist/index.html
```

Expected: contains `https://cv.jinholee.com/og/index-en.png`.

- [ ] **Step 9: Run renderers to verify they produce the new URL**

```bash
just build-resume && just build-jsonld && just build-text
grep -c '"https://cv.jinholee.com' dist/resume.json dist/person.jsonld dist/cv-en.txt
```

Expected: every file contains the new URL.

- [ ] **Step 10: Commit**

```bash
git add scripts/config.py web/src/lib/site-config.ts web/astro.config.mjs web/public/CNAME
git commit -m "feat: cut over to custom domain (cv.jinholee.com)"
```

---

### Task 15: Update `CLAUDE.md` + `README.md`

**Files:**
- Modify: `CLAUDE.md`
- Modify: `README.md`

- [ ] **Step 1: Mark Phase 5 row as done in CLAUDE.md**

In `CLAUDE.md`, find the Phasing table and update the Phase 5 row from:

```
| 5 | Polish: custom domain, project deep-dive pages, OG images, chart interactivity | Not started |
```

to:

```
| 5 | Polish: custom domain, project deep-dive pages, OG images, chart interactivity | ✅ Done (merged YYYY-MM-DD, commit `xxxxxx`) |
```

(Leave the date/commit as `YYYY-MM-DD`/`xxxxxx` for now — fill in at merge time.)

- [ ] **Step 2: Add new files to the Layout section in CLAUDE.md**

Find the Layout block:

```
scripts/                  validate.py, bib_loader.py, content_loader.py, langstring.py, render_web_data.py, render_jsonresume.py, render_jsonld.py, render_text.py
```

Update to include `config.py`:

```
scripts/                  validate.py, bib_loader.py, content_loader.py, langstring.py, config.py, render_web_data.py, render_jsonresume.py, render_jsonld.py, render_text.py
```

- [ ] **Step 3: Add the "Files to read" entry for the Phase 5 spec**

In CLAUDE.md, under "Files to read before any phase", add a bullet for `docs/superpowers/specs/2026-05-26-phase-5-polish-design.md`. (Phase 5 is the most-recent completed phase after this lands.)

- [ ] **Step 4: Update README.md**

In `README.md`, find the Website section (created in Phase 3):

```markdown
**Website:** [jin-homlee.github.io/jin-ho-lee-cv](https://jin-homlee.github.io/jin-ho-lee-cv/) · auto-deployed on every change to `main`.
```

Replace with:

```markdown
**Website:** [cv.jinholee.com](https://cv.jinholee.com/) · auto-deployed on every change to `main`.

Per-project deep-dives live under [`/projects/{id}/`](https://cv.jinholee.com/projects/L1/) (EN) and [`/de/projects/{id}/`](https://cv.jinholee.com/de/projects/L1/) (DE).
```

(Substitute the actual domain from Task 14.)

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md README.md
git commit -m "docs: mark Phase 5 done; update README + CLAUDE.md for custom domain + project pages"
```

---

## Done criteria

After all 15 tasks land and the branch is ready to merge:

- [ ] `just validate && just test && just lint` all pass.
- [ ] `pnpm --dir web build` succeeds; `web/dist/projects/L1/index.html` and `web/dist/de/projects/L1/index.html` exist; `web/dist/og/index-en.png` exists and is > 5 KB.
- [ ] Hovering a pie slice and a year on the cumulative chart shows tooltips locally (`just web-dev`).
- [ ] DNS for the chosen domain is configured (see Task 14 Step 6); `dig {domain}` returns the github.io CNAME.
- [ ] Repo Settings → Pages "Custom domain" is set to the chosen domain and HTTPS is enforced.
- [ ] PR test plan items are ticked off in the PR body before merging (per project memory).
