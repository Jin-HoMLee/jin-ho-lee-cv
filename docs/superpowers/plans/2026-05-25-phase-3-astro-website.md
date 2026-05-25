# Phase 3 — Astro Website + GitHub Pages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a bilingual static website at `https://jin-homlee.github.io/jin-ho-lee-cv/` (and `/de/`) that renders the same content the PDF renders, auto-deployed on every push to `main`.

**Architecture:** A new Python script (`scripts/render_web_data.py`) dumps the fully-resolved bilingual content to JSON. Astro imports the JSON at build time and emits static HTML. A separate `.github/workflows/pages.yml` workflow builds and deploys to GitHub Pages on every push to `main`. PDF build/release pipeline (Phase 2a/2b) is untouched.

**Tech Stack:** Existing — YAML + BibTeX + Python content loader. Adds Node 22 LTS + pnpm 10 + Astro 5 + Tailwind 4 + `@fontsource/ibm-plex-sans` + GitHub Pages.

**Spec reference:** [docs/superpowers/specs/2026-05-25-phase-3-astro-website-design.md](../specs/2026-05-25-phase-3-astro-website-design.md)

**Branch:** `phase-3-astro-website` (already created at commit `fa3ea3b`, holding the design spec). All implementation lands as commits on this branch; final task merges via PR with `--no-ff`.

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `scripts/render_web_data.py` | Create | Dump bilingual content JSON for Astro consumption. Hard-codes `private_path=None` (no PII reaches web). |
| `tests/test_render_web_data.py` | Create | Round-trip, PII isolation, bilingual parity, publications shape. |
| `web/.gitignore` | Create | `node_modules/`, `dist/`, generated JSON, photo. |
| `web/package.json` | Create | Astro 5, Tailwind 4, `@fontsource/ibm-plex-sans`. |
| `web/pnpm-lock.yaml` | Create (generated) | Lock file (committed). |
| `web/tsconfig.json` | Create | Astro's strict TS config. |
| `web/astro.config.mjs` | Create | `base: '/jin-ho-lee-cv/'`, i18n config, Tailwind Vite plugin. |
| `web/src/styles/global.css` | Create | `@import "tailwindcss"`, IBM Plex Sans font import, base typography. |
| `web/src/types/content.ts` | Create | TS types matching the JSON dump shape. |
| `web/src/layouts/BaseLayout.astro` | Create | HTML scaffold, `<head>` meta, font import, sticky header, footer. |
| `web/src/components/Header.astro` | Create | Name + headline + download buttons + language switcher. |
| `web/src/components/LanguageSwitcher.astro` | Create | EN ↔ DE link, uses Astro's `getRelativeLocaleUrl`. |
| `web/src/components/ProfileSection.astro` | Create | Photo (if present) + tagline + paragraphs. |
| `web/src/components/ExperienceSection.astro` | Create | Per-entry: org, role, period, bullets with project-ref badges linking to `#<id>`. |
| `web/src/components/ProjectsSection.astro` | Create | All project cards, anchored by id, grouped by category. |
| `web/src/components/SkillsSidebar.astro` | Create | Categorized skill groups with item chips. |
| `web/src/components/EducationSection.astro` | Create | Degrees with institution + period. |
| `web/src/components/LanguagesList.astro` | Create | Languages with proficiency label. |
| `web/src/components/VolunteerSection.astro` | Create | Volunteer categories with entries. |
| `web/src/components/PublicationsList.astro` | Create | Publications grouped by type, sorted by year desc, Jin-Ho's name bolded. |
| `web/src/pages/index.astro` | Create | EN root, imports `content.en.json`, wires sections. |
| `web/src/pages/de/index.astro` | Create | DE root, imports `content.de.json`. |
| `.nvmrc` | Create | `22` (Node LTS). |
| `.gitignore` | Modify | Add `web/node_modules/`, `web/dist/`, `web/src/data/*.json`, `web/public/photo.jpg`. |
| `justfile` | Modify | Add `web-data`, `web-dev`, `web-build`, `web-clean`. Extend `clean`. |
| `.github/workflows/pages.yml` | Create | Build (render JSON + pnpm build) + deploy to GitHub Pages on push to main. |
| `README.md` | Modify | Add "Website" line under existing "Latest CV" line. |
| `CLAUDE.md` | Modify | Update Phase 3 row, layout, commands, local-only files. |

---

## Task 1: Create `scripts/render_web_data.py` (TDD)

A new Python script that consumes `content_loader.load_content` + `langstring.resolve_langstrings`, converts `Publication` dataclass instances to plain dicts, and writes two JSON files at `web/src/data/content.{en,de}.json`. Tested via four assertions: round-trip, PII isolation, bilingual parity, publications shape.

**Files:**
- Create: `tests/test_render_web_data.py`
- Create: `scripts/render_web_data.py`

- [ ] **Step 1: Make the output directory exist as a sibling of web/src**

```bash
mkdir -p web/src/data
```

(The directory must exist before tests run; its contents will be gitignored later. The directory itself is fine to leave empty; pytest doesn't care.)

- [ ] **Step 2: Write the failing test file**

Create `tests/test_render_web_data.py`:

```python
"""Tests for scripts/render_web_data.py — dumps bilingual content JSON for Astro."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.render_web_data import render_web_data, OUTPUT_DIR


REPO_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = REPO_ROOT / "content"


@pytest.fixture
def rendered(tmp_path):
    """Render both langs into a tmp_path/web/src/data/ and return the loaded JSON."""
    out_dir = tmp_path / "web" / "src" / "data"
    render_web_data(content_dir=CONTENT_DIR, output_dir=out_dir)
    en = json.loads((out_dir / "content.en.json").read_text(encoding="utf-8"))
    de = json.loads((out_dir / "content.de.json").read_text(encoding="utf-8"))
    return en, de


def test_round_trip_structural_keys(rendered):
    """Both JSON files have the expected top-level keys."""
    en, de = rendered
    expected_keys = {
        "personal", "profile", "skills", "education", "experience",
        "projects", "languages", "volunteer", "publications", "labels",
    }
    assert set(en.keys()) == expected_keys
    assert set(de.keys()) == expected_keys


def test_langmaps_resolved_to_strings(rendered):
    """No raw {en: ..., de: ...} maps should remain in the dumped JSON."""
    en, _ = rendered
    # personal.headline was a langmap in YAML; should be a plain string after resolution
    assert isinstance(en["personal"]["headline"], str)
    # labels.sections.profile was {en: "Profile", de: "Profil"} — should be "Profile" in EN dump
    assert isinstance(en["labels"]["sections"]["profile"], str)
    assert en["labels"]["sections"]["profile"] == "Profile"


def test_pii_never_reaches_dump(tmp_path, monkeypatch):
    """Even with content.private/private.yaml present, no phone or street leaks."""
    # Create a fake private overlay with distinctive values
    private_dir = tmp_path / "content.private"
    private_dir.mkdir()
    (private_dir / "private.yaml").write_text(
        "phone: '+99 999 LEAKED_PHONE_NUMBER'\n"
        "address:\n"
        "  street: 'LEAKED_STREET_NAME 42'\n"
        "  postal_code: '00000'\n"
        "  city: 'Leak City'\n"
        "  country: 'XX'\n",
        encoding="utf-8",
    )

    # render_web_data must NOT accept a private_path argument; it must hard-code None.
    # We verify the contract by checking the dump for the marker strings.
    out_dir = tmp_path / "web" / "src" / "data"
    render_web_data(content_dir=CONTENT_DIR, output_dir=out_dir)

    en_text = (out_dir / "content.en.json").read_text(encoding="utf-8")
    de_text = (out_dir / "content.de.json").read_text(encoding="utf-8")
    assert "LEAKED_PHONE_NUMBER" not in en_text
    assert "LEAKED_PHONE_NUMBER" not in de_text
    assert "LEAKED_STREET_NAME" not in en_text
    assert "LEAKED_STREET_NAME" not in de_text


def test_bilingual_parity(rendered):
    """EN and DE dumps have the same structural shape: same keys, same array lengths, same project ids."""
    en, de = rendered

    # Top-level keys (already covered, but doubles as smoke)
    assert set(en.keys()) == set(de.keys())

    # Experience entries: same count, same ids in same order
    assert len(en["experience"]) == len(de["experience"])
    assert [e["id"] for e in en["experience"]] == [e["id"] for e in de["experience"]]

    # Projects: same id set
    assert set(en["projects"].keys()) == set(de["projects"].keys())

    # Publications: same count and same keys in same order (sorted by year desc)
    assert len(en["publications"]) == len(de["publications"])
    assert [p["key"] for p in en["publications"]] == [p["key"] for p in de["publications"]]


def test_publications_shape(rendered):
    """Each publication has the required fields with allowed enum values."""
    en, _ = rendered
    allowed_types = {"article", "book-chapter", "conference", "book"}
    allowed_authorship = {"first", "shared", "middle", "last", "corresponding"}

    assert en["publications"], "expected at least one publication"
    for pub in en["publications"]:
        assert set(pub.keys()) >= {"key", "title", "year", "type", "authorship", "authors", "venue"}
        assert pub["type"] in allowed_types
        assert pub["authorship"] in allowed_authorship
        assert isinstance(pub["authors"], list)
        assert isinstance(pub["year"], int)
        # raw bibtex dict should NOT be in the dump
        assert "raw" not in pub


def test_output_dir_default_matches_repo_layout():
    """OUTPUT_DIR constant points at web/src/data relative to the repo root."""
    assert OUTPUT_DIR.name == "data"
    assert OUTPUT_DIR.parent.name == "src"
    assert OUTPUT_DIR.parent.parent.name == "web"
```

- [ ] **Step 3: Run the new tests; expect ImportError**

```bash
uv run pytest tests/test_render_web_data.py -v
```
Expected: collection FAILS with `ImportError: cannot import name 'render_web_data' from 'scripts.render_web_data'` (because the script doesn't exist yet).

- [ ] **Step 4: Implement `scripts/render_web_data.py`**

Create `scripts/render_web_data.py`:

```python
"""Render bilingual content JSON for the Astro website.

Produces web/src/data/content.{en,de}.json by composing:
  - scripts.content_loader.load_content (with private_path HARD-CODED to None)
  - scripts.langstring.resolve_langstrings (to flatten langmaps to chosen lang)
  - Publication dataclass → dict conversion
  - Path → str conversion
"""
from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any

from scripts.bib_loader import Publication
from scripts.content_loader import load_content
from scripts.langstring import resolve_langstrings


REPO_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = REPO_ROOT / "content"
OUTPUT_DIR = REPO_ROOT / "web" / "src" / "data"
LANGS = ("en", "de")


def _to_jsonable(obj: Any) -> Any:
    """Recursively convert Publication dataclasses and Path objects to JSON-native types."""
    if isinstance(obj, Publication):
        d = dataclasses.asdict(obj)
        d.pop("raw", None)  # drop bibtex-specific field; not needed for rendering
        # asdict converts tuple → list; that's what we want for JSON
        return _to_jsonable(d)
    if isinstance(obj, Path):
        return obj.as_posix()
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(item) for item in obj]
    return obj


def render_web_data(*, content_dir: Path = CONTENT_DIR, output_dir: Path = OUTPUT_DIR) -> None:
    """Render content.{en,de}.json into output_dir.

    `private_path` is HARD-CODED to None — the web site must never see PII.
    Tests assert this contract.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    for lang in LANGS:
        tree = load_content(content_dir, private_path=None, lang=lang)
        resolved = resolve_langstrings(tree, lang=lang)
        jsonable = _to_jsonable(resolved)
        out_path = output_dir / f"content.{lang}.json"
        out_path.write_text(
            json.dumps(jsonable, indent=2, sort_keys=False, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"wrote {out_path.relative_to(REPO_ROOT)}")


def main() -> int:
    render_web_data()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run tests; expect all pass**

```bash
uv run pytest tests/test_render_web_data.py -v
```
Expected: 6 passed.

If `test_pii_never_reaches_dump` fails with the marker strings present in the dump, double-check `render_web_data` calls `load_content(..., private_path=None, ...)`. The `tmp_path` private file should be irrelevant — that's the contract.

If `test_publications_shape` fails with "raw" key present, check `_to_jsonable` removes it after `dataclasses.asdict`.

- [ ] **Step 6: Run the CLI to dump real JSON into the repo**

```bash
uv run python -m scripts.render_web_data
ls -la web/src/data/
```
Expected: `web/src/data/content.en.json` and `web/src/data/content.de.json` exist, each a few KB.

- [ ] **Step 7: Quick sanity-grep the dump for PII**

```bash
grep -c "27024174\|Gaußstraße\|68165" web/src/data/content.*.json || echo "no PII (good)"
```
Expected: `no PII (good)`. (The grep returns non-zero when nothing matches; the `|| echo` catches it.)

- [ ] **Step 8: Run full pytest + lint**

```bash
uv run pytest -v
uv run ruff check .
```
Expected: all green.

- [ ] **Step 9: Commit**

```bash
git add scripts/render_web_data.py tests/test_render_web_data.py
git commit -m "feat: add render_web_data script for Astro JSON dump"
```

(The freshly generated `web/src/data/*.json` files stay untracked for now; they'll be gitignored in Task 13.)

---

## Task 2: Scaffold `web/` (Astro 5 + Tailwind 4 + dependencies)

Initialize a minimal Astro project at `web/` without using `npm create astro@latest` (which is interactive). Build the files by hand so the layout matches the spec exactly.

**Files:**
- Create: `web/package.json`
- Create: `web/tsconfig.json`
- Create: `web/astro.config.mjs`
- Create: `web/src/styles/global.css`
- Create: `web/src/env.d.ts`
- Generated: `web/pnpm-lock.yaml`, `web/node_modules/`

- [ ] **Step 1: Ensure Node 22 LTS and pnpm 10 are available**

```bash
node --version
pnpm --version
```

If Node is missing or wrong: `nvm install 22 && nvm use 22`. If pnpm is missing: `npm install -g pnpm@10`.

- [ ] **Step 2: Create `web/package.json`**

```json
{
  "name": "jin-ho-lee-cv-web",
  "type": "module",
  "version": "0.0.1",
  "private": true,
  "packageManager": "pnpm@10.0.0",
  "scripts": {
    "dev": "astro dev",
    "build": "astro build",
    "preview": "astro preview",
    "check": "astro check"
  },
  "dependencies": {
    "astro": "^5.0.0",
    "tailwindcss": "^4.0.0",
    "@tailwindcss/vite": "^4.0.0",
    "@fontsource/ibm-plex-sans": "^5.0.0"
  },
  "devDependencies": {
    "@astrojs/check": "^0.9.0",
    "typescript": "^5.5.0"
  }
}
```

- [ ] **Step 3: Create `web/tsconfig.json`**

```json
{
  "extends": "astro/tsconfigs/strict",
  "include": [".astro/types.d.ts", "**/*"],
  "exclude": ["dist"],
  "compilerOptions": {
    "resolveJsonModule": true
  }
}
```

`resolveJsonModule: true` is needed so `import contentEn from "../data/content.en.json"` works with types.

- [ ] **Step 4: Create `web/src/env.d.ts`**

```ts
/// <reference path="../.astro/types.d.ts" />
```

- [ ] **Step 5: Create `web/astro.config.mjs`**

```js
import { defineConfig } from "astro/config";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  site: "https://jin-homlee.github.io",
  base: "/jin-ho-lee-cv/",
  trailingSlash: "always",
  i18n: {
    defaultLocale: "en",
    locales: ["en", "de"],
    routing: { prefixDefaultLocale: false },
  },
  vite: {
    plugins: [tailwindcss()],
  },
});
```

(Tailwind 4 ships as a Vite plugin, not an Astro integration — this is the current-recommended setup.)

- [ ] **Step 6: Create `web/src/styles/global.css`**

```css
@import "tailwindcss";

@import "@fontsource/ibm-plex-sans/400.css";
@import "@fontsource/ibm-plex-sans/500.css";
@import "@fontsource/ibm-plex-sans/600.css";
@import "@fontsource/ibm-plex-sans/700.css";

:root {
  --color-accent: #1e3a8a; /* placeholder; final hex lifted from pdf/styles.typ in Task 12 */
}

html {
  font-family: "IBM Plex Sans", system-ui, -apple-system, sans-serif;
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
}

body {
  @apply text-neutral-900 bg-white;
}
```

- [ ] **Step 7: Install dependencies**

```bash
cd web && pnpm install
```

Expected: pnpm fetches Astro 5 + Tailwind 4 + fontsource. `web/pnpm-lock.yaml` is created. `web/node_modules/` populated.

- [ ] **Step 8: Smoke-test dev server starts**

```bash
cd web && pnpm dev --host 127.0.0.1 --port 4321 &
DEV_PID=$!
sleep 5
curl -sI http://127.0.0.1:4321/jin-ho-lee-cv/ | head -1
kill $DEV_PID 2>/dev/null
```

Expected: HTTP `404` (no pages yet — Task 3 adds them). The fact that the server responded at all means Astro is correctly configured. If the curl fails with connection refused, the dev server didn't start — check the install output for errors.

- [ ] **Step 9: Commit**

```bash
cd /Users/jin-holee/dev/GitHub/Jin-HoMLee/jin-ho-lee-cv
git add web/package.json web/pnpm-lock.yaml web/tsconfig.json web/astro.config.mjs web/src/styles/global.css web/src/env.d.ts
git commit -m "feat(web): scaffold Astro 5 + Tailwind 4 project"
```

(`web/node_modules/` will be gitignored in Task 13.)

---

## Task 3: TS types + minimal pages (smoke build)

Add TS types matching the JSON dump shape, plus two minimal pages that just import and render the headline. Verify `pnpm build` succeeds end-to-end before any UI work.

**Files:**
- Create: `web/src/types/content.ts`
- Create: `web/src/pages/index.astro`
- Create: `web/src/pages/de/index.astro`

- [ ] **Step 1: Re-render the JSON dump (in case content changed since Task 1)**

```bash
uv run python -m scripts.render_web_data
ls web/src/data/
```
Expected: `content.en.json` and `content.de.json` present.

- [ ] **Step 2: Create `web/src/types/content.ts`**

```ts
// Types matching the shape produced by scripts/render_web_data.py.
// If the Python dump shape changes, update here in lockstep.

export interface Name { given: string; family: string }
export interface Location { city: string; country: string }
export interface Links {
  linkedin: string | null;
  github: string | null;
  researchgate: string | null;
  orcid: string | null;
}
export interface Personal {
  name: Name;
  headline: string;
  email: string;
  location: Location;
  links: Links;
  photo: string;
}

export interface Profile {
  tagline: string;
  paragraphs: string[];
}

export interface SkillGroup { label: string; items: string[] }
export interface SkillCategory { name: string; groups: SkillGroup[] }
export interface Skills { categories: SkillCategory[] }

export interface Period { start: string; end: string | null }

export interface Education {
  degree: string;
  institution: string;
  period: Period;
}

export interface ExperienceBullet { text: string; refs?: string[] }
export interface Org { name: string; url: string | null }
export interface Experience {
  id: string;
  org: Org;
  role: string;
  period: Period;
  bullets: ExperienceBullet[];
}

export interface Project {
  id: string;
  category: "life-science" | "data-science" | "consulting";
  title: string;
  summary: string;
  role: string;
  period: Period;
  technologies: string[];
  contributions: string[];
  outcome: string;
}

export interface Language { name: string; proficiency: string }

export interface VolunteerEntry { org: string; period?: Period; note?: string }
export interface VolunteerCategory { name: string; entries: VolunteerEntry[] }
export interface Volunteer { categories: VolunteerCategory[] }

export type PublicationType = "article" | "book-chapter" | "conference" | "book";
export type AuthorshipType = "first" | "shared" | "middle" | "last" | "corresponding";
export interface Publication {
  key: string;
  title: string;
  year: number;
  type: PublicationType;
  authorship: AuthorshipType;
  authors: string[];
  venue: string | null;
}

export interface MonthLabel { en: string; de: string }
export interface Labels {
  sections: {
    profile: string;
    experience: string;
    education: string;
    skills: string;
    languages: string;
    volunteer: string;
  };
  months_abbr: string[]; // resolved to the page's language
  proficiency: {
    native: string;
    fluent: string;
    basic: string;
    passive: string;
  };
}

export interface ContentData {
  personal: Personal;
  profile: Profile;
  skills: Skills;
  education: Education[];
  experience: Experience[];
  projects: Record<string, Project>;
  languages: Language[];
  volunteer: Volunteer;
  publications: Publication[];
  labels: Labels;
}
```

If a property name disagrees with the actual JSON (introspect with `jq keys` on `web/src/data/content.en.json`), correct the type here. The types are advisory — TS won't catch a shape mismatch in JSON imports without a runtime parser, but they guide component code.

- [ ] **Step 3: Inspect the JSON shape to verify the types**

```bash
uv run python -c "
import json
en = json.load(open('web/src/data/content.en.json'))
for top, val in en.items():
    if isinstance(val, list):
        print(f'{top}: list[{len(val)}], first keys: {list(val[0].keys()) if val else None}')
    elif isinstance(val, dict):
        print(f'{top}: dict, keys: {list(val.keys())[:6]}')
    else:
        print(f'{top}: {type(val).__name__}')
"
```

Compare the output against the type definitions; fix the types if anything diverges. Common divergences to look for: `volunteer` actually being `{categories: [{name, entries: [...]}]}` vs. flat list — adjust types accordingly.

- [ ] **Step 4: Create `web/src/pages/index.astro` (minimal)**

```astro
---
import type { ContentData } from "../types/content";
import contentEn from "../data/content.en.json";
import "../styles/global.css";

const data = contentEn as unknown as ContentData;
---
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{data.personal.name.given} {data.personal.name.family} — CV</title>
  </head>
  <body class="p-8">
    <h1 class="text-3xl font-semibold">{data.personal.name.given} {data.personal.name.family}</h1>
    <p class="mt-2 text-lg text-neutral-700">{data.personal.headline}</p>
    <p class="mt-1 text-sm text-neutral-500">smoke-build OK</p>
  </body>
</html>
```

- [ ] **Step 5: Create `web/src/pages/de/index.astro` (minimal)**

```astro
---
import type { ContentData } from "../../types/content";
import contentDe from "../../data/content.de.json";
import "../../styles/global.css";

const data = contentDe as unknown as ContentData;
---
<!doctype html>
<html lang="de">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{data.personal.name.given} {data.personal.name.family} — Lebenslauf</title>
  </head>
  <body class="p-8">
    <h1 class="text-3xl font-semibold">{data.personal.name.given} {data.personal.name.family}</h1>
    <p class="mt-2 text-lg text-neutral-700">{data.personal.headline}</p>
    <p class="mt-1 text-sm text-neutral-500">smoke-build OK</p>
  </body>
</html>
```

- [ ] **Step 6: Run a full Astro build**

```bash
cd web && pnpm build
```

Expected: completes with no errors. Output: `web/dist/index.html` and `web/dist/de/index.html`.

If the build fails with "cannot resolve `../data/content.en.json`" — confirm Task 1 Step 6 dumped the JSON files and re-run if needed.

If the build fails with TS errors — relax the types in `content.ts` to `any` for that field temporarily, OR fix the type definition to match the actual JSON shape (preferred).

- [ ] **Step 7: Inspect the built HTML**

```bash
grep -o "Jin-Ho Lee" web/dist/index.html
grep -o "smoke-build OK" web/dist/index.html
grep -o "Jin-Ho Lee" web/dist/de/index.html
```
Expected: each grep finds the string at least once.

- [ ] **Step 8: Visually confirm with the preview server (optional)**

```bash
cd web && pnpm preview --host 127.0.0.1 --port 4322 &
PREVIEW_PID=$!
sleep 3
curl -s http://127.0.0.1:4322/jin-ho-lee-cv/ | grep "Jin-Ho Lee"
curl -s http://127.0.0.1:4322/jin-ho-lee-cv/de/ | grep "Jin-Ho Lee"
kill $PREVIEW_PID 2>/dev/null
```
Expected: both curls echo `<h1>...Jin-Ho Lee...</h1>` snippets.

- [ ] **Step 9: Commit**

```bash
cd /Users/jin-holee/dev/GitHub/Jin-HoMLee/jin-ho-lee-cv
git add web/src/types/content.ts web/src/pages/index.astro web/src/pages/de/index.astro
git commit -m "feat(web): smoke-test pages + content type definitions"
```

---

## Task 4: BaseLayout component

Extract the HTML scaffold (head, body, font, base styling) into `web/src/layouts/BaseLayout.astro`. Pages will use it as a wrapper.

**Files:**
- Create: `web/src/layouts/BaseLayout.astro`
- Modify: `web/src/pages/index.astro`
- Modify: `web/src/pages/de/index.astro`

- [ ] **Step 1: Create `web/src/layouts/BaseLayout.astro`**

```astro
---
import "../styles/global.css";
import type { ContentData } from "../types/content";

interface Props {
  lang: "en" | "de";
  data: ContentData;
}

const { lang, data } = Astro.props;
const title = `${data.personal.name.given} ${data.personal.name.family} — ${
  lang === "en" ? "CV" : "Lebenslauf"
}`;
const description = data.profile.tagline;
---
<!doctype html>
<html lang={lang}>
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <meta name="description" content={description} />
    <link rel="canonical" href={Astro.url.href} />
    <title>{title}</title>
  </head>
  <body class="min-h-screen bg-white text-neutral-900">
    <slot name="header" />
    <main class="mx-auto max-w-6xl px-4 py-8 md:px-8">
      <slot />
    </main>
    <footer class="mx-auto max-w-6xl px-4 py-8 text-xs text-neutral-500 md:px-8">
      <p>
        © {new Date().getUTCFullYear()} {data.personal.name.given} {data.personal.name.family} ·
        <a class="underline hover:text-neutral-900" href="https://github.com/Jin-HoMLee/jin-ho-lee-cv">Source on GitHub</a>
      </p>
    </footer>
  </body>
</html>
```

The two slots (`header` and the default) let pages inject the header above the main content and content into main.

- [ ] **Step 2: Update `web/src/pages/index.astro` to use the layout**

Replace the entire file with:

```astro
---
import type { ContentData } from "../types/content";
import contentEn from "../data/content.en.json";
import BaseLayout from "../layouts/BaseLayout.astro";

const data = contentEn as unknown as ContentData;
---
<BaseLayout lang="en" data={data}>
  <h1 class="text-3xl font-semibold">{data.personal.name.given} {data.personal.name.family}</h1>
  <p class="mt-2 text-lg text-neutral-700">{data.personal.headline}</p>
</BaseLayout>
```

- [ ] **Step 3: Update `web/src/pages/de/index.astro`**

```astro
---
import type { ContentData } from "../../types/content";
import contentDe from "../../data/content.de.json";
import BaseLayout from "../../layouts/BaseLayout.astro";

const data = contentDe as unknown as ContentData;
---
<BaseLayout lang="de" data={data}>
  <h1 class="text-3xl font-semibold">{data.personal.name.given} {data.personal.name.family}</h1>
  <p class="mt-2 text-lg text-neutral-700">{data.personal.headline}</p>
</BaseLayout>
```

- [ ] **Step 4: Build and verify**

```bash
cd web && pnpm build
grep -o "Source on GitHub" web/dist/index.html
grep -o "Source on GitHub" web/dist/de/index.html
```
Expected: both grep match.

- [ ] **Step 5: Commit**

```bash
cd /Users/jin-holee/dev/GitHub/Jin-HoMLee/jin-ho-lee-cv
git add web/src/layouts/BaseLayout.astro web/src/pages/index.astro web/src/pages/de/index.astro
git commit -m "feat(web): add BaseLayout wrapper"
```

---

## Task 5: Header + LanguageSwitcher components

Two related components. Header holds name, headline, PDF download buttons, and the LanguageSwitcher.

**Files:**
- Create: `web/src/components/Header.astro`
- Create: `web/src/components/LanguageSwitcher.astro`
- Modify: `web/src/pages/index.astro`
- Modify: `web/src/pages/de/index.astro`

- [ ] **Step 1: Create `web/src/components/LanguageSwitcher.astro`**

```astro
---
interface Props {
  currentLang: "en" | "de";
}

const { currentLang } = Astro.props;
const base = import.meta.env.BASE_URL; // "/jin-ho-lee-cv/"

// Build the alternate-language URL by stripping any "/de/" prefix and re-adding it as needed.
const otherLang: "en" | "de" = currentLang === "en" ? "de" : "en";
const otherHref = otherLang === "de" ? `${base}de/` : base;
const otherLabel = otherLang === "de" ? "Deutsch" : "English";
---
<a
  href={otherHref}
  class="rounded-md border border-neutral-300 px-3 py-1.5 text-sm hover:border-neutral-900 hover:text-neutral-900"
  hreflang={otherLang}
  aria-label={`Switch to ${otherLabel}`}
>
  {otherLang.toUpperCase()}
</a>
```

(Astro's built-in `getRelativeLocaleUrl` works but adds complexity; the explicit base-relative URLs above are simpler for a two-locale site.)

- [ ] **Step 2: Create `web/src/components/Header.astro`**

```astro
---
import type { Personal } from "../types/content";
import LanguageSwitcher from "./LanguageSwitcher.astro";

interface Props {
  personal: Personal;
  lang: "en" | "de";
}

const { personal, lang } = Astro.props;
const downloadLabel = lang === "en" ? "Download PDF" : "PDF herunterladen";
const pdfUrlBase = "https://github.com/Jin-HoMLee/jin-ho-lee-cv/releases/latest/download";
---
<header class="sticky top-0 z-10 border-b border-neutral-200 bg-white/90 backdrop-blur">
  <div class="mx-auto flex max-w-6xl flex-wrap items-center gap-3 px-4 py-3 md:px-8">
    <div class="mr-auto">
      <p class="text-lg font-semibold leading-tight">
        {personal.name.given} {personal.name.family}
      </p>
      <p class="text-xs text-neutral-600">{personal.headline}</p>
    </div>
    <div class="flex items-center gap-2 text-sm">
      <span class="text-neutral-500">{downloadLabel}:</span>
      <a
        class="rounded-md bg-neutral-900 px-3 py-1.5 text-white hover:bg-neutral-700"
        href={`${pdfUrlBase}/cv-en.pdf`}
      >EN</a>
      <a
        class="rounded-md bg-neutral-900 px-3 py-1.5 text-white hover:bg-neutral-700"
        href={`${pdfUrlBase}/cv-de.pdf`}
      >DE</a>
      <LanguageSwitcher currentLang={lang} />
    </div>
  </div>
</header>
```

- [ ] **Step 3: Use Header in `web/src/pages/index.astro`**

```astro
---
import type { ContentData } from "../types/content";
import contentEn from "../data/content.en.json";
import BaseLayout from "../layouts/BaseLayout.astro";
import Header from "../components/Header.astro";

const data = contentEn as unknown as ContentData;
---
<BaseLayout lang="en" data={data}>
  <Header slot="header" personal={data.personal} lang="en" />
  <h1 class="text-3xl font-semibold">{data.personal.name.given} {data.personal.name.family}</h1>
  <p class="mt-2 text-lg text-neutral-700">{data.personal.headline}</p>
</BaseLayout>
```

- [ ] **Step 4: Use Header in `web/src/pages/de/index.astro`**

```astro
---
import type { ContentData } from "../../types/content";
import contentDe from "../../data/content.de.json";
import BaseLayout from "../../layouts/BaseLayout.astro";
import Header from "../../components/Header.astro";

const data = contentDe as unknown as ContentData;
---
<BaseLayout lang="de" data={data}>
  <Header slot="header" personal={data.personal} lang="de" />
  <h1 class="text-3xl font-semibold">{data.personal.name.given} {data.personal.name.family}</h1>
  <p class="mt-2 text-lg text-neutral-700">{data.personal.headline}</p>
</BaseLayout>
```

- [ ] **Step 5: Build and verify**

```bash
cd web && pnpm build
grep -o "Download PDF" web/dist/index.html
grep -o "PDF herunterladen" web/dist/de/index.html
grep -o 'href="/jin-ho-lee-cv/de/"' web/dist/index.html
grep -o 'href="/jin-ho-lee-cv/"' web/dist/de/index.html
```
Expected: all four grep find a match — EN page links to `/jin-ho-lee-cv/de/`, DE page links back to `/jin-ho-lee-cv/`.

- [ ] **Step 6: Commit**

```bash
cd /Users/jin-holee/dev/GitHub/Jin-HoMLee/jin-ho-lee-cv
git add web/src/components/Header.astro web/src/components/LanguageSwitcher.astro web/src/pages/index.astro web/src/pages/de/index.astro
git commit -m "feat(web): add Header + LanguageSwitcher with PDF download buttons"
```

---

## Task 6: ProfileSection (with optional photo)

Renders the headline-style profile (tagline + paragraphs). Photo loads only if `web/public/photo.jpg` exists at build time.

**Files:**
- Create: `web/src/components/ProfileSection.astro`
- Modify: `web/src/pages/index.astro`
- Modify: `web/src/pages/de/index.astro`

- [ ] **Step 1: Create `web/src/components/ProfileSection.astro`**

```astro
---
import { existsSync } from "node:fs";
import { resolve } from "node:path";
import type { Personal, Profile, Labels } from "../types/content";

interface Props {
  personal: Personal;
  profile: Profile;
  labels: Labels;
}

const { personal, profile, labels } = Astro.props;

// Check at build time whether a public photo exists in web/public/photo.jpg.
// The `astro build` cwd is the `web/` directory.
const hasPhoto = existsSync(resolve("./public/photo.jpg"));
const photoUrl = `${import.meta.env.BASE_URL}photo.jpg`;
---
<section id="profile" class="py-6">
  <h2 class="mb-3 text-xs font-semibold uppercase tracking-wider text-neutral-500">
    {labels.sections.profile}
  </h2>
  <div class="flex flex-col gap-6 md:flex-row md:items-start">
    {hasPhoto && (
      <img
        src={photoUrl}
        alt={`${personal.name.given} ${personal.name.family}`}
        class="h-32 w-32 flex-shrink-0 rounded-full object-cover md:h-40 md:w-40"
        width="160"
        height="160"
        loading="eager"
      />
    )}
    <div>
      <p class="text-lg font-medium text-neutral-900">{profile.tagline}</p>
      {profile.paragraphs.map((p) => (
        <p class="mt-3 text-neutral-700 leading-relaxed">{p}</p>
      ))}
    </div>
  </div>
</section>
```

- [ ] **Step 2: Use ProfileSection in both pages**

In `web/src/pages/index.astro`, replace the placeholder body (the `<h1>` and `<p>` that came from Task 5) with:

```astro
<ProfileSection personal={data.personal} profile={data.profile} labels={data.labels} />
```

And add the import at the top:

```astro
import ProfileSection from "../components/ProfileSection.astro";
```

Apply the same change to `web/src/pages/de/index.astro` (with `../../components/ProfileSection.astro`).

- [ ] **Step 3: Build and verify**

```bash
cd web && pnpm build
grep -o "Data science and bioinformatics" web/dist/index.html
grep -o "Data Science- und Bioinformatik" web/dist/de/index.html
```
Expected: EN finds the EN tagline, DE finds the DE tagline. If you have a `web/public/photo.jpg` locally, also confirm: `grep -o '<img' web/dist/index.html`.

- [ ] **Step 4: Commit**

```bash
cd /Users/jin-holee/dev/GitHub/Jin-HoMLee/jin-ho-lee-cv
git add web/src/components/ProfileSection.astro web/src/pages/index.astro web/src/pages/de/index.astro
git commit -m "feat(web): add ProfileSection with optional photo"
```

---

## Task 7: ExperienceSection (with project-ref badges)

Renders experience entries. Each bullet that has `refs: [L1, ...]` shows project ID badges that link to `#L1` etc. The Projects section (Task 8) provides the anchored targets.

**Files:**
- Create: `web/src/components/ExperienceSection.astro`
- Modify: both pages

- [ ] **Step 1: Inspect a real experience entry to verify the shape**

```bash
uv run python -c "
import json
d = json.load(open('web/src/data/content.en.json'))
print(json.dumps(d['experience'][0], indent=2)[:500])
"
```

Confirm: `id`, `org.name`, `role`, `period.{start,end}`, `bullets: [{text, refs?}]`.

- [ ] **Step 2: Create a small period-formatter helper, `web/src/lib/period.ts`**

```ts
import type { Period, Labels } from "../types/content";

/** Render a period like "2024-05" → "May 2024", honoring locale month abbreviations. */
export function formatPeriod(period: Period, labels: Labels, present: { en: string; de: string }, lang: "en" | "de"): string {
  const fmt = (ym: string | null) => {
    if (!ym) return present[lang];
    const [y, m] = ym.split("-");
    const monthIdx = parseInt(m, 10) - 1;
    const monthName = labels.months_abbr[monthIdx] ?? m;
    return `${monthName} ${y}`;
  };
  return `${fmt(period.start)} – ${fmt(period.end)}`;
}
```

- [ ] **Step 3: Create `web/src/components/ExperienceSection.astro`**

```astro
---
import type { Experience, Project, Labels } from "../types/content";
import { formatPeriod } from "../lib/period";

interface Props {
  experience: Experience[];
  projects: Record<string, Project>;
  labels: Labels;
  lang: "en" | "de";
}

const { experience, labels, lang } = Astro.props;
const presentLabel = { en: "present", de: "heute" };
---
<section id="experience" class="py-6">
  <h2 class="mb-4 text-xs font-semibold uppercase tracking-wider text-neutral-500">
    {labels.sections.experience}
  </h2>
  <div class="space-y-6">
    {experience.map((exp) => (
      <article id={`exp-${exp.id}`} class="border-l-2 border-neutral-200 pl-4">
        <header class="mb-2 flex flex-wrap items-baseline justify-between gap-2">
          <h3 class="text-base font-semibold text-neutral-900">
            {exp.role}
            <span class="font-normal text-neutral-600"> · {exp.org.name}</span>
          </h3>
          <p class="text-xs text-neutral-500">{formatPeriod(exp.period, labels, presentLabel, lang)}</p>
        </header>
        <ul class="space-y-1.5 text-sm text-neutral-700">
          {exp.bullets.map((b) => (
            <li class="flex gap-2">
              <span aria-hidden="true" class="text-neutral-400">•</span>
              <span>
                {b.text}
                {b.refs && b.refs.length > 0 && (
                  <span class="ml-1 inline-flex gap-1">
                    {b.refs.map((r) => (
                      <a
                        href={`#${r}`}
                        class="rounded bg-neutral-100 px-1.5 py-0.5 text-xs font-medium text-neutral-700 no-underline hover:bg-neutral-200"
                      >{r}</a>
                    ))}
                  </span>
                )}
              </span>
            </li>
          ))}
        </ul>
      </article>
    ))}
  </div>
</section>
```

- [ ] **Step 4: Wire ExperienceSection into both pages**

In `web/src/pages/index.astro`, add the import:

```astro
import ExperienceSection from "../components/ExperienceSection.astro";
```

And add the section after `<ProfileSection ... />`:

```astro
<ExperienceSection experience={data.experience} projects={data.projects} labels={data.labels} lang="en" />
```

Same for `web/src/pages/de/index.astro` with `lang="de"` and `../../` paths.

- [ ] **Step 5: Build and verify**

```bash
cd web && pnpm build
grep -o "href=\"#L1\"" web/dist/index.html | head -1
grep -o "href=\"#C2\"" web/dist/index.html | head -1
```
Expected: at least one match each (project-ref badges link to the project anchors that Task 8 will create).

- [ ] **Step 6: Commit**

```bash
cd /Users/jin-holee/dev/GitHub/Jin-HoMLee/jin-ho-lee-cv
git add web/src/lib/period.ts web/src/components/ExperienceSection.astro web/src/pages/index.astro web/src/pages/de/index.astro
git commit -m "feat(web): add ExperienceSection with project-ref badges"
```

---

## Task 8: ProjectsSection (anchored project cards)

A grid of project cards, each anchored as `#L1`, `#C2`, etc. Grouped by category (life-science / data-science / consulting) with category headings.

**Files:**
- Create: `web/src/components/ProjectsSection.astro`
- Modify: both pages

- [ ] **Step 1: Create `web/src/components/ProjectsSection.astro`**

```astro
---
import type { Project, Labels } from "../types/content";
import { formatPeriod } from "../lib/period";

interface Props {
  projects: Record<string, Project>;
  labels: Labels;
  lang: "en" | "de";
}

const { projects, labels, lang } = Astro.props;
const presentLabel = { en: "present", de: "heute" };

const categoryLabel: Record<Project["category"], { en: string; de: string }> = {
  "life-science": { en: "Life Science", de: "Lebenswissenschaften" },
  "data-science": { en: "Data Science", de: "Data Science" },
  "consulting":   { en: "Consulting",   de: "Beratung" },
};

const sectionLabel = { en: "Projects", de: "Projekte" };

// Group projects by category, preserve insertion order within each group
const grouped: Record<Project["category"], Project[]> = {
  "life-science": [],
  "data-science": [],
  "consulting": [],
};
for (const p of Object.values(projects)) {
  grouped[p.category].push(p);
}
const categoryOrder: Project["category"][] = ["life-science", "data-science", "consulting"];
---
<section id="projects" class="py-6">
  <h2 class="mb-4 text-xs font-semibold uppercase tracking-wider text-neutral-500">
    {sectionLabel[lang]}
  </h2>
  {categoryOrder.map((cat) => grouped[cat].length > 0 && (
    <div class="mb-6">
      <h3 class="mb-3 text-sm font-semibold text-neutral-700">{categoryLabel[cat][lang]}</h3>
      <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
        {grouped[cat].map((p) => (
          <article id={p.id} class="rounded-md border border-neutral-200 p-4">
            <header class="mb-2">
              <p class="text-xs font-mono text-neutral-500">{p.id}</p>
              <h4 class="text-base font-semibold text-neutral-900">{p.title}</h4>
              <p class="text-xs text-neutral-500">
                {p.role} · {formatPeriod(p.period, labels, presentLabel, lang)}
              </p>
            </header>
            <p class="mb-3 text-sm text-neutral-700">{p.summary}</p>
            <details class="text-sm">
              <summary class="cursor-pointer text-neutral-600 hover:text-neutral-900">
                {lang === "en" ? "Details" : "Details"}
              </summary>
              <ul class="mt-2 space-y-1 text-neutral-700">
                {p.contributions.map((c) => (
                  <li class="flex gap-2">
                    <span aria-hidden="true" class="text-neutral-400">·</span>
                    <span>{c}</span>
                  </li>
                ))}
              </ul>
              <p class="mt-2 text-sm italic text-neutral-600">{p.outcome}</p>
              <p class="mt-3 flex flex-wrap gap-1">
                {p.technologies.map((t) => (
                  <span class="rounded bg-neutral-100 px-1.5 py-0.5 text-xs text-neutral-700">{t}</span>
                ))}
              </p>
            </details>
          </article>
        ))}
      </div>
    </div>
  ))}
</section>
```

- [ ] **Step 2: Wire ProjectsSection into both pages**

Add to `web/src/pages/index.astro` (import and section):

```astro
import ProjectsSection from "../components/ProjectsSection.astro";
```

```astro
<ProjectsSection projects={data.projects} labels={data.labels} lang="en" />
```

Same for `de/index.astro`.

- [ ] **Step 3: Build and verify project anchors exist**

```bash
cd web && pnpm build
grep -o 'id="L1"' web/dist/index.html
grep -o 'id="C2"' web/dist/index.html
grep -o 'id="D3"' web/dist/index.html
```
Expected: each anchor present exactly once.

- [ ] **Step 4: Commit**

```bash
cd /Users/jin-holee/dev/GitHub/Jin-HoMLee/jin-ho-lee-cv
git add web/src/components/ProjectsSection.astro web/src/pages/index.astro web/src/pages/de/index.astro
git commit -m "feat(web): add ProjectsSection with anchored cards, grouped by category"
```

---

## Task 9: SkillsSidebar

Categorized skill groups. Will render in the right sidebar on desktop, stacked above publications on mobile. Layout integration (two-column) comes in Task 12.

**Files:**
- Create: `web/src/components/SkillsSidebar.astro`
- Modify: both pages

- [ ] **Step 1: Create `web/src/components/SkillsSidebar.astro`**

```astro
---
import type { Skills, Labels } from "../types/content";

interface Props {
  skills: Skills;
  labels: Labels;
}

const { skills, labels } = Astro.props;
---
<section id="skills" class="py-6">
  <h2 class="mb-4 text-xs font-semibold uppercase tracking-wider text-neutral-500">
    {labels.sections.skills}
  </h2>
  <div class="space-y-5">
    {skills.categories.map((cat) => (
      <div>
        <h3 class="mb-2 text-sm font-semibold text-neutral-800">{cat.name}</h3>
        <div class="space-y-2">
          {cat.groups.map((g) => (
            <div>
              <p class="text-xs font-medium text-neutral-600">{g.label}</p>
              <ul class="mt-1 flex flex-wrap gap-1">
                {g.items.map((item) => (
                  <li class="rounded bg-neutral-100 px-1.5 py-0.5 text-xs text-neutral-700">{item}</li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>
    ))}
  </div>
</section>
```

- [ ] **Step 2: Wire into both pages**

```astro
import SkillsSidebar from "../components/SkillsSidebar.astro";
```

```astro
<SkillsSidebar skills={data.skills} labels={data.labels} />
```

(Same in `de/index.astro` with `../../` paths.)

- [ ] **Step 3: Build and verify**

```bash
cd web && pnpm build
grep -o "Bioinformatics &amp; ML" web/dist/index.html
grep -o "Bioinformatik &amp; ML" web/dist/de/index.html
```
Expected: EN finds the EN category name, DE finds the DE.

- [ ] **Step 4: Commit**

```bash
cd /Users/jin-holee/dev/GitHub/Jin-HoMLee/jin-ho-lee-cv
git add web/src/components/SkillsSidebar.astro web/src/pages/index.astro web/src/pages/de/index.astro
git commit -m "feat(web): add SkillsSidebar"
```

---

## Task 10: EducationSection + LanguagesList + VolunteerSection

Three small adjacent sections. Bundled into one task because each is tiny and they ship as a logical "rest of the CV chrome" group.

**Files:**
- Create: `web/src/components/EducationSection.astro`
- Create: `web/src/components/LanguagesList.astro`
- Create: `web/src/components/VolunteerSection.astro`
- Modify: both pages

- [ ] **Step 1: Inspect the education / languages / volunteer shape**

```bash
uv run python -c "
import json
d = json.load(open('web/src/data/content.en.json'))
print('--- education ---'); print(json.dumps(d['education'][:1], indent=2))
print('--- languages ---'); print(json.dumps(d['languages'][:2], indent=2))
print('--- volunteer ---'); print(json.dumps(d['volunteer'], indent=2)[:400])
"
```

Confirm: education is `list[{degree, institution, period}]`; languages is `list[{name, proficiency}]`; volunteer is `{categories: [{name, entries: [...]}]}`. If the volunteer shape differs (e.g. flat list), adjust the component below to match — the YAML is authoritative.

- [ ] **Step 2: Create `web/src/components/EducationSection.astro`**

```astro
---
import type { Education, Labels } from "../types/content";
import { formatPeriod } from "../lib/period";

interface Props {
  education: Education[];
  labels: Labels;
  lang: "en" | "de";
}

const { education, labels, lang } = Astro.props;
const presentLabel = { en: "present", de: "heute" };
---
<section id="education" class="py-6">
  <h2 class="mb-3 text-xs font-semibold uppercase tracking-wider text-neutral-500">
    {labels.sections.education}
  </h2>
  <div class="space-y-3">
    {education.map((ed) => (
      <div>
        <p class="text-sm font-semibold text-neutral-900">{ed.degree}</p>
        <p class="text-sm text-neutral-700">{ed.institution}</p>
        <p class="text-xs text-neutral-500">{formatPeriod(ed.period, labels, presentLabel, lang)}</p>
      </div>
    ))}
  </div>
</section>
```

- [ ] **Step 3: Create `web/src/components/LanguagesList.astro`**

```astro
---
import type { Language, Labels } from "../types/content";

interface Props {
  languages: Language[];
  labels: Labels;
}

const { languages, labels } = Astro.props;

/** Look up the resolved proficiency label, falling back to the raw value. */
function profLabel(p: string): string {
  return (labels.proficiency as Record<string, string>)[p] ?? p;
}
---
<section id="languages" class="py-6">
  <h2 class="mb-3 text-xs font-semibold uppercase tracking-wider text-neutral-500">
    {labels.sections.languages}
  </h2>
  <ul class="space-y-1">
    {languages.map((l) => (
      <li class="flex items-baseline justify-between text-sm">
        <span class="text-neutral-900">{l.name}</span>
        <span class="text-neutral-500">{profLabel(l.proficiency)}</span>
      </li>
    ))}
  </ul>
</section>
```

- [ ] **Step 4: Create `web/src/components/VolunteerSection.astro`**

```astro
---
import type { Volunteer, Labels } from "../types/content";

interface Props {
  volunteer: Volunteer;
  labels: Labels;
}

const { volunteer, labels } = Astro.props;
---
<section id="volunteer" class="py-6">
  <h2 class="mb-3 text-xs font-semibold uppercase tracking-wider text-neutral-500">
    {labels.sections.volunteer}
  </h2>
  <div class="space-y-3">
    {volunteer.categories.map((cat) => (
      <div>
        <p class="text-sm font-semibold text-neutral-800">{cat.name}</p>
        <ul class="mt-1 space-y-0.5 text-sm text-neutral-700">
          {cat.entries.map((e) => (
            <li>{e.org}{e.note ? <span class="text-neutral-500"> — {e.note}</span> : null}</li>
          ))}
        </ul>
      </div>
    ))}
  </div>
</section>
```

If `volunteer` is structured differently in the JSON (e.g. flat list rather than `{categories: [...]}`), adjust to match. Type definitions in `content.ts` may also need updating.

- [ ] **Step 5: Wire all three into both pages**

In `web/src/pages/index.astro`, add the imports:

```astro
import EducationSection from "../components/EducationSection.astro";
import LanguagesList from "../components/LanguagesList.astro";
import VolunteerSection from "../components/VolunteerSection.astro";
```

And place after the SkillsSidebar / ProjectsSection (final ordering happens in Task 12; for now any reasonable order works):

```astro
<EducationSection education={data.education} labels={data.labels} lang="en" />
<LanguagesList languages={data.languages} labels={data.labels} />
<VolunteerSection volunteer={data.volunteer} labels={data.labels} />
```

Same for `de/index.astro` with `lang="de"` and `../../` paths.

- [ ] **Step 6: Build and verify**

```bash
cd web && pnpm build
grep -o "Education" web/dist/index.html
grep -o "Ausbildung" web/dist/de/index.html
grep -o "Languages" web/dist/index.html
grep -o "Sprachen" web/dist/de/index.html
grep -o "Volunteer" web/dist/index.html
grep -o "Ehrenamtlich" web/dist/de/index.html
```
Expected: each grep matches.

- [ ] **Step 7: Commit**

```bash
cd /Users/jin-holee/dev/GitHub/Jin-HoMLee/jin-ho-lee-cv
git add web/src/components/EducationSection.astro web/src/components/LanguagesList.astro web/src/components/VolunteerSection.astro web/src/pages/index.astro web/src/pages/de/index.astro
git commit -m "feat(web): add Education, Languages, and Volunteer sections"
```

---

## Task 11: PublicationsList

Publications grouped by type, sorted by year descending within each group. Jin-Ho's name bolded in the author list.

**Files:**
- Create: `web/src/components/PublicationsList.astro`
- Modify: both pages

- [ ] **Step 1: Inspect a publication entry**

```bash
uv run python -c "
import json
d = json.load(open('web/src/data/content.en.json'))
print(json.dumps(d['publications'][:1], indent=2))
print('types in use:', sorted({p['type'] for p in d['publications']}))
"
```

- [ ] **Step 2: Create `web/src/components/PublicationsList.astro`**

```astro
---
import type { Publication, PublicationType } from "../types/content";

interface Props {
  publications: Publication[];
  lang: "en" | "de";
}

const { publications, lang } = Astro.props;

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

/** Render an author list, bolding Lee, J. */
function renderAuthors(authors: string[]): string {
  return authors
    .map((a) => /\bLee, ?J/.test(a) ? `<strong>${a}</strong>` : a)
    .join(", ");
}
---
<section id="publications" class="py-6">
  <h2 class="mb-4 text-xs font-semibold uppercase tracking-wider text-neutral-500">
    {sectionLabel[lang]}
  </h2>
  {typeOrder.map((t) => grouped[t].length > 0 && (
    <div class="mb-5">
      <h3 class="mb-2 text-sm font-semibold text-neutral-800">{typeLabel[t][lang]}</h3>
      <ol class="space-y-2 text-sm text-neutral-700">
        {grouped[t].map((p) => (
          <li>
            <p class="font-medium text-neutral-900">{p.title}</p>
            <p set:html={renderAuthors(p.authors)} class="text-xs text-neutral-600" />
            <p class="text-xs text-neutral-500">
              {p.venue ? `${p.venue} · ` : ""}{p.year} · {p.authorship}
            </p>
          </li>
        ))}
      </ol>
    </div>
  ))}
</section>
```

The `set:html` directive is required to render the `<strong>` tags from `renderAuthors`. The input is trusted (originated from our own `publications.bib`).

- [ ] **Step 3: Wire into both pages**

```astro
import PublicationsList from "../components/PublicationsList.astro";
```

```astro
<PublicationsList publications={data.publications} lang="en" />
```

(`lang="de"` for DE page, `../../` paths.)

- [ ] **Step 4: Build and verify**

```bash
cd web && pnpm build
grep -o "Publications" web/dist/index.html
grep -o "Publikationen" web/dist/de/index.html
grep -o "<strong>Lee" web/dist/index.html | head -1
```
Expected: section labels render in correct language; at least one `<strong>Lee` to confirm author-bolding works.

- [ ] **Step 5: Commit**

```bash
cd /Users/jin-holee/dev/GitHub/Jin-HoMLee/jin-ho-lee-cv
git add web/src/components/PublicationsList.astro web/src/pages/index.astro web/src/pages/de/index.astro
git commit -m "feat(web): add PublicationsList grouped by type, Jin-Ho bolded"
```

---

## Task 12: Two-column layout + styling polish

Wire all sections into the two-column desktop layout (main column + sidebar). Lift the accent color from `pdf/styles.typ` so the website's blue matches the PDF.

**Files:**
- Modify: `web/src/styles/global.css`
- Modify: `web/src/pages/index.astro`
- Modify: `web/src/pages/de/index.astro`

- [ ] **Step 1: Find the PDF accent color**

```bash
grep -E "rgb|#[0-9a-fA-F]" pdf/styles.typ | head -10
```

Note the primary blue hex (or convert from rgb). If `pdf/styles.typ` uses a Typst color literal like `rgb("#1a5490")`, that's the value. Capture as `<ACCENT_HEX>` for the next step.

- [ ] **Step 2: Update `web/src/styles/global.css` with the real accent**

Replace the `:root` block:

```css
:root {
  --color-accent: <ACCENT_HEX>;  /* matches pdf/styles.typ */
}
```

If `pdf/styles.typ` doesn't yet define a single named accent (Phase 1's templates might inline colors), pick the most prominent blue used in the PDF and use that here. Document the choice in the commit message.

- [ ] **Step 3: Restructure `web/src/pages/index.astro` for two-column layout**

```astro
---
import type { ContentData } from "../types/content";
import contentEn from "../data/content.en.json";
import BaseLayout from "../layouts/BaseLayout.astro";
import Header from "../components/Header.astro";
import ProfileSection from "../components/ProfileSection.astro";
import ExperienceSection from "../components/ExperienceSection.astro";
import ProjectsSection from "../components/ProjectsSection.astro";
import SkillsSidebar from "../components/SkillsSidebar.astro";
import EducationSection from "../components/EducationSection.astro";
import LanguagesList from "../components/LanguagesList.astro";
import VolunteerSection from "../components/VolunteerSection.astro";
import PublicationsList from "../components/PublicationsList.astro";

const data = contentEn as unknown as ContentData;
---
<BaseLayout lang="en" data={data}>
  <Header slot="header" personal={data.personal} lang="en" />
  <ProfileSection personal={data.personal} profile={data.profile} labels={data.labels} />
  <div class="grid grid-cols-1 gap-8 md:grid-cols-[2fr_1fr]">
    <div class="space-y-2">
      <ExperienceSection experience={data.experience} projects={data.projects} labels={data.labels} lang="en" />
      <ProjectsSection projects={data.projects} labels={data.labels} lang="en" />
      <EducationSection education={data.education} labels={data.labels} lang="en" />
      <PublicationsList publications={data.publications} lang="en" />
    </div>
    <aside class="space-y-2">
      <SkillsSidebar skills={data.skills} labels={data.labels} />
      <LanguagesList languages={data.languages} labels={data.labels} />
      <VolunteerSection volunteer={data.volunteer} labels={data.labels} />
    </aside>
  </div>
</BaseLayout>
```

- [ ] **Step 4: Apply the same restructure to `web/src/pages/de/index.astro`**

```astro
---
import type { ContentData } from "../../types/content";
import contentDe from "../../data/content.de.json";
import BaseLayout from "../../layouts/BaseLayout.astro";
import Header from "../../components/Header.astro";
import ProfileSection from "../../components/ProfileSection.astro";
import ExperienceSection from "../../components/ExperienceSection.astro";
import ProjectsSection from "../../components/ProjectsSection.astro";
import SkillsSidebar from "../../components/SkillsSidebar.astro";
import EducationSection from "../../components/EducationSection.astro";
import LanguagesList from "../../components/LanguagesList.astro";
import VolunteerSection from "../../components/VolunteerSection.astro";
import PublicationsList from "../../components/PublicationsList.astro";

const data = contentDe as unknown as ContentData;
---
<BaseLayout lang="de" data={data}>
  <Header slot="header" personal={data.personal} lang="de" />
  <ProfileSection personal={data.personal} profile={data.profile} labels={data.labels} />
  <div class="grid grid-cols-1 gap-8 md:grid-cols-[2fr_1fr]">
    <div class="space-y-2">
      <ExperienceSection experience={data.experience} projects={data.projects} labels={data.labels} lang="de" />
      <ProjectsSection projects={data.projects} labels={data.labels} lang="de" />
      <EducationSection education={data.education} labels={data.labels} lang="de" />
      <PublicationsList publications={data.publications} lang="de" />
    </div>
    <aside class="space-y-2">
      <SkillsSidebar skills={data.skills} labels={data.labels} />
      <LanguagesList languages={data.languages} labels={data.labels} />
      <VolunteerSection volunteer={data.volunteer} labels={data.labels} />
    </aside>
  </div>
</BaseLayout>
```

- [ ] **Step 5: Visual smoke in the dev server**

```bash
cd web && pnpm dev --host 127.0.0.1 --port 4321 &
DEV_PID=$!
sleep 5
echo "Open: http://127.0.0.1:4321/jin-ho-lee-cv/"
echo "      http://127.0.0.1:4321/jin-ho-lee-cv/de/"
echo "(server is running in background; kill with: kill $DEV_PID)"
```

Open both URLs in a browser. Verify:
- Two-column layout on desktop (≥ 1024px).
- Single column on mobile (resize the window).
- Sticky header with name + headline + EN/DE download buttons + language switcher.
- Profile section with tagline + paragraphs.
- Experience entries with project-ref badges.
- Project cards in a grid, anchored — click a badge to confirm scroll-to-anchor works.
- Sidebar with skills, languages, volunteer.
- Publications grouped by type at the bottom.
- Language switcher round-trips EN ↔ DE.

When done:

```bash
kill $DEV_PID 2>/dev/null
```

- [ ] **Step 6: Production build**

```bash
cd web && pnpm build
```
Expected: clean. Note the output size — should be well under 1 MB total.

- [ ] **Step 7: Commit**

```bash
cd /Users/jin-holee/dev/GitHub/Jin-HoMLee/jin-ho-lee-cv
git add web/src/styles/global.css web/src/pages/index.astro web/src/pages/de/index.astro
git commit -m "feat(web): two-column desktop layout + accent color from pdf/styles.typ"
```

---

## Task 13: Justfile + root .gitignore + .nvmrc

Tooling updates so contributors can run the web build via `just`, and so generated artifacts stay out of git.

**Files:**
- Create: `.nvmrc`
- Create: `web/.gitignore`
- Modify: `.gitignore` (root)
- Modify: `justfile`

- [ ] **Step 1: Create `.nvmrc` (root)**

```
22
```

(Just the major; `nvm use` picks up the latest matching LTS.)

- [ ] **Step 2: Create `web/.gitignore`**

```
node_modules/
dist/
src/data/*.json
public/photo.jpg
.astro/
```

- [ ] **Step 3: Append to root `.gitignore`**

Open root `.gitignore`. Add at the end:

```
# Phase 3 — Astro website
web/node_modules/
web/dist/
web/src/data/*.json
web/public/photo.jpg
web/.astro/
```

(Both the root and `web/.gitignore` cover the same files — defense in depth; either alone would work.)

- [ ] **Step 4: Append to `justfile`**

Before the `clean:` recipe, add:

```just
# Render JSON for the Astro site → web/src/data/content.{en,de}.json
web-data:
    uv run python -m scripts.render_web_data

# Run the Astro dev server (regenerates data first)
web-dev: web-data
    pnpm --dir web dev

# Build the static site → web/dist/
web-build: web-data
    pnpm --dir web install --frozen-lockfile
    pnpm --dir web build

# Remove web build artifacts
web-clean:
    rm -rf web/dist web/node_modules web/src/data/*.json
```

Modify the existing `clean:` recipe so it also cleans the web build:

```just
# Remove build outputs
clean: web-clean
    rm -rf dist/ dist-private/ pdf/.cache/
```

- [ ] **Step 5: Verify gitignore actually ignores the generated files**

```bash
git check-ignore -v web/src/data/content.en.json web/node_modules web/dist web/public/photo.jpg 2>&1 || echo "ignored OK"
git status --short web/src/data/ web/node_modules 2>&1 | head
```
Expected: `check-ignore` shows the ignoring rule for each path. `git status` shows nothing for those paths.

- [ ] **Step 6: Smoke-test the just recipes**

```bash
just web-data
ls web/src/data/
```
Expected: both JSON files present.

```bash
just web-build
ls web/dist/
```
Expected: `index.html`, `de/index.html`, `_astro/` directory all present.

- [ ] **Step 7: Commit**

```bash
git add .nvmrc .gitignore web/.gitignore justfile
git commit -m "chore: add Phase 3 tooling — .nvmrc, gitignore entries, just web-* recipes"
```

---

## Task 14: `.github/workflows/pages.yml`

CI workflow that builds the site and deploys to GitHub Pages on every push to `main`. Separate from `ci.yml` (which handles validate + PDF + release).

**Files:**
- Create: `.github/workflows/pages.yml`

- [ ] **Step 1: Create `.github/workflows/pages.yml`**

```yaml
name: Pages

on:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: pages
  cancel-in-progress: true

jobs:
  build:
    runs-on: ubuntu-latest
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

  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - name: Deploy to GitHub Pages
        id: deployment
        uses: actions/deploy-pages@v4
```

`workflow_dispatch` allows manual re-deploys from the Actions UI without needing a commit.

`concurrency` ensures the newest push wins; in-flight deploys cancel when a new push arrives.

- [ ] **Step 2: Validate YAML syntax**

```bash
uv run python -c "import yaml; yaml.safe_load(open('.github/workflows/pages.yml'))" && echo "YAML OK"
```
Expected: `YAML OK`.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/pages.yml
git commit -m "ci: add GitHub Pages deploy workflow"
```

(The workflow will actually run only on push to `main`, which happens at Task 17. Before then, CI sees `pages.yml` exist but won't execute it.)

---

## Task 15: README + CLAUDE.md updates

Documentation hooks. README gets a "Website" link; CLAUDE.md updates the Phase 3 row and adds new commands/paths.

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Read current README header**

```bash
head -20 README.md
```

- [ ] **Step 2: Add the Website line to README**

Find the line:

```markdown
**Latest CV:** [EN](https://github.com/Jin-HoMLee/jin-ho-lee-cv/releases/latest/download/cv-en.pdf) · [DE](https://github.com/Jin-HoMLee/jin-ho-lee-cv/releases/latest/download/cv-de.pdf) — auto-published on every change to `main`.
```

Add directly after it:

```markdown

**Website:** [jin-homlee.github.io/jin-ho-lee-cv](https://jin-homlee.github.io/jin-ho-lee-cv/) · [`/de/`](https://jin-homlee.github.io/jin-ho-lee-cv/de/) · auto-deployed on every change to `main`.
```

- [ ] **Step 3: Update CLAUDE.md — phase status table**

Find row:

```markdown
| 3 | Astro website + GitHub Pages | Not started |
```

Replace with (use the eventual merge SHA after Task 17; for now mark "In progress"):

```markdown
| 3 | Astro website + GitHub Pages | In progress |
```

Task 17 Step 6 will flip this to `✅ Done` after the merge.

- [ ] **Step 4: Update CLAUDE.md — Layout section**

Find the Layout block:

```markdown
content/                  source of truth (YAML + BibTeX)
content.private/          gitignored PII overlay (phone, address)
content.private.example/  template showing required private keys
schema/cv.schema.json     JSON Schema for content
scripts/                  validate.py, bib_loader.py, content_loader.py (renderers added in later phases)
tests/                    pytest suite (18 tests as of Phase 0)
docs/superpowers/         specs and implementation plans for each phase
.github/workflows/        CI (validate + test + lint on every push)
```

Replace with:

```markdown
content/                  source of truth (YAML + BibTeX)
content.private/          gitignored PII overlay (phone, address)
content.private.example/  template showing required private keys
schema/cv.schema.json     JSON Schema for content
scripts/                  validate.py, bib_loader.py, content_loader.py, render_web_data.py
tests/                    pytest suite
pdf/                      Typst PDF renderer (Phase 1)
web/                      Astro website (Phase 3)
docs/superpowers/         specs and implementation plans for each phase
.github/workflows/        ci.yml (validate + PDF + release), pages.yml (web deploy)
```

- [ ] **Step 5: Update CLAUDE.md — Commands section**

Find the Commands block:

```bash
just validate    # JSON Schema + cross-ref + bib parsing
just test        # pytest, all suites
just lint        # ruff check
just fmt         # ruff format
```

Replace with:

```bash
just validate    # JSON Schema + cross-ref + bib parsing
just test        # pytest, all suites
just lint        # ruff check
just fmt         # ruff format
just web-dev     # Astro dev server (auto-regenerates content JSON)
just web-build   # Production build of web/dist
```

- [ ] **Step 6: Update CLAUDE.md — Local-only files section**

Find:

```markdown
## Local-only files (not in git)

- `assets/photo.jpg` — headshot, referenced from `content/personal.yaml`. Required for Phase 1 PDF builds.
- `content.private/private.yaml` — phone + address. Copy from `content.private.example/private.example.yaml` template.
```

Replace with:

```markdown
## Local-only files (not in git)

- `assets/photo.jpg` — headshot used by the private PDF build. Optional; omit and the PDF renders without a photo.
- `content.private/private.yaml` — phone + address. Copy from `content.private.example/private.example.yaml` template.
- `web/public/photo.jpg` — public-facing photo for the website. Optional; site degrades gracefully without it.
```

- [ ] **Step 7: Commit**

```bash
git add README.md CLAUDE.md
git commit -m "docs: add Phase 3 website link in README, update CLAUDE.md layout/commands"
```

---

## Task 16: Local end-to-end smoke + push branch + open PR

Pre-PR verification, then push and open the PR.

**Files:**
- None (verification + git workflow)

- [ ] **Step 1: Clean rebuild of everything**

```bash
just clean
just web-build
ls web/dist/
```
Expected: `index.html`, `de/index.html`, `_astro/` present, all non-empty.

- [ ] **Step 2: Run validate + tests + lint**

```bash
just validate
just test
just lint
```
Expected: all green.

- [ ] **Step 3: Run the dev server one more time for a visual pass**

```bash
just web-dev &
DEV_PID=$!
sleep 5
echo "Open: http://127.0.0.1:4321/jin-ho-lee-cv/"
echo "      http://127.0.0.1:4321/jin-ho-lee-cv/de/"
```

Click through:
- Language switcher round-trip works
- PDF download buttons link to GitHub Releases (404 in dev is expected if no release yet for that filename; the link should be the right URL though)
- Project anchors scroll to the right card
- Project `<details>` expand/collapse on click

```bash
kill $DEV_PID 2>/dev/null
```

If anything looks off, fix on the branch and add commits before continuing.

- [ ] **Step 4: Push the branch**

```bash
git push -u origin phase-3-astro-website
```

- [ ] **Step 5: Open the PR**

```bash
gh pr create --title "Phase 3: Astro website + GitHub Pages deploy" --body "$(cat <<'EOF'
## Summary

Adds a bilingual static website at https://jin-homlee.github.io/jin-ho-lee-cv/ (EN) and `/de/`, auto-deployed on every push to `main`.

Implements [Phase 3 spec](docs/superpowers/specs/2026-05-25-phase-3-astro-website-design.md).

Key architectural choice: a new Python script (`scripts/render_web_data.py`) dumps content JSON for Astro to consume at build time. Astro is a thin presentation layer; Python remains the only YAML/BibTeX parser. Matches the parent spec's "renderers are interchangeable" principle.

## What's in
- `scripts/render_web_data.py` + 6 pytest assertions (round-trip, PII isolation, bilingual parity, publications shape, output dir)
- `web/` — Astro 5 + Tailwind 4 project: BaseLayout, Header (+ LanguageSwitcher, PDF download buttons), Profile, Experience (with project-ref badges), Projects (anchored cards grouped by category), Skills, Education, Languages, Volunteer, Publications (grouped by type, Jin-Ho bolded)
- `.github/workflows/pages.yml` — separate build + deploy workflow (`ci.yml` untouched)
- `.nvmrc`, `web/.gitignore`, root `.gitignore` additions, `justfile` recipes
- README + CLAUDE.md updates

## What's not in (deferred)
- JSON Resume, JSON-LD `<script>` tag, plain text → Phase 4
- Publications authorship pie chart → Phase 4
- Per-project deep-dive pages → Phase 5
- Custom domain → Phase 5
- PR previews of the deployed site

## Test plan
- [ ] CI: validate + tests + lint pass (existing `ci.yml`)
- [ ] CI: `pages.yml` builds successfully (deploy job skips on PR — only runs on push to main)
- [ ] After merge: site reachable at https://jin-homlee.github.io/jin-ho-lee-cv/
- [ ] After merge: `/de/` reachable, language switcher round-trips
- [ ] After merge: project-ref badges in experience scroll to the corresponding project card
- [ ] After merge: PDF download buttons resolve to the latest release PDFs
EOF
)"
```

Capture the PR URL.

- [ ] **Step 6: Watch CI**

```bash
gh pr checks --watch
```
Expected: `validate` job passes (from `ci.yml`); `build-pdf` matrix both pass; `release` skipped (PR event); `Pages → build` passes; `Pages → deploy` either skipped or runs against the PR (gh-pages publishes only on push to main due to `concurrency` and trigger conditions).

If `Pages → build` fails, the most likely cause is a missing dependency or a TS type mismatch — `gh run view --log-failed` to investigate.

- [ ] **Step 7: Optional — request `@claude` review**

```bash
gh pr comment <PR-number> --body "@claude review this PR for spec compliance and code quality"
```

Address any blockers raised; push extra commits as needed.

---

## Task 17: Enable GitHub Pages, merge, verify deployment, mark phase done

The one manual step (enabling Pages with GitHub Actions as source) happens before the merge so the first deploy lands cleanly.

**Files:**
- Modify: `CLAUDE.md` (after merge)

- [ ] **Step 1: Enable GitHub Pages with "GitHub Actions" as source**

This is a one-time manual step in the repo settings UI:

1. Open https://github.com/Jin-HoMLee/jin-ho-lee-cv/settings/pages
2. Under "Build and deployment" → "Source", select **"GitHub Actions"**.
3. Save.

Or via gh CLI (only if `gh api` supports the Pages endpoint for this repo):

```bash
gh api -X POST /repos/Jin-HoMLee/jin-ho-lee-cv/pages -f build_type=workflow 2>&1 || \
  echo "If this fails (already enabled or permissions), do it manually in repo settings."
```

This is required before the `deploy-pages` action can publish.

- [ ] **Step 2: Mark PR ready and confirm CI green**

```bash
gh pr ready
gh pr checks
```

- [ ] **Step 3: Merge via `gh pr merge --merge --delete-branch`**

```bash
gh pr merge phase-3-astro-website --merge --delete-branch \
  -t "Merge Phase 3: Astro website + GitHub Pages deploy" -b ""
git switch main
git pull
```

The `--merge` flag forces a no-ff merge commit (matching Phase 2a/2b style).

- [ ] **Step 4: Watch the post-merge workflows**

```bash
# ci.yml (validate + PDF + release) — same as Phase 2b
CI_RUN=$(gh run list --workflow=ci.yml --branch=main --event=push --limit=1 --json databaseId --jq '.[0].databaseId')
# pages.yml (build + deploy)
PAGES_RUN=$(gh run list --workflow=pages.yml --branch=main --event=push --limit=1 --json databaseId --jq '.[0].databaseId')

echo "CI run: $CI_RUN"
echo "Pages run: $PAGES_RUN"

gh run watch "$PAGES_RUN" --exit-status --interval 10
```

Use a Bash timeout of 600000ms (10 min). Expected: the Pages workflow's `build` job completes, then `deploy` runs and outputs a `page_url` matching `https://jin-homlee.github.io/jin-ho-lee-cv/`.

- [ ] **Step 5: Confirm the site is live**

```bash
curl -sLI -o /dev/null -w "EN: %{http_code}\n" "https://jin-homlee.github.io/jin-ho-lee-cv/"
curl -sLI -o /dev/null -w "DE: %{http_code}\n" "https://jin-homlee.github.io/jin-ho-lee-cv/de/"
```
Expected: both `200`.

Also open both URLs in a browser. Confirm visually:
- Header sticky, language switcher works.
- Profile / experience / projects / skills / education / languages / volunteer / publications all render.
- PDF download buttons resolve.
- Mobile layout (resize browser) collapses to single column.

If the site shows a "404" or stale content, GitHub Pages may take a few minutes after first enabling to propagate. Re-check after 5 min.

- [ ] **Step 6: Update CLAUDE.md status table — flip Phase 3 to `✅ Done`**

Get the merge SHA:

```bash
MERGE_SHA=$(git log -1 --format=%h main)
TODAY=$(date -u +%Y-%m-%d)
echo "Merge: $MERGE_SHA on $TODAY"
```

Open `CLAUDE.md` and change:

```markdown
| 3 | Astro website + GitHub Pages | In progress |
```

to (substituting the captured values):

```markdown
| 3 | Astro website + GitHub Pages | ✅ Done (merged YYYY-MM-DD, commit `<merge-sha>`) |
```

Open a small follow-up PR (don't push directly to main):

```bash
git switch -c docs/mark-phase-3-done
git add CLAUDE.md
git commit -m "docs: mark Phase 3 as done"
git push -u origin docs/mark-phase-3-done
gh pr create --title "docs: mark Phase 3 as done" --body "Status table update following Phase 3 merge."
gh pr merge --rebase --delete-branch
git switch main && git pull
```

This second merge triggers another Pages deploy (idempotent — same site content). Acceptable noise.

---

## Self-Review

Mapped against spec sections:

- **§1 Scope** — Tasks 1–17 cover all of: bilingual website, GitHub Pages auto-deploy, single-page CV view per language, content reuse from `content/`.
- **§2 Goal** — Task 5 (PDF download buttons), Task 14+17 (auto-deploy), Tasks 6–11 (all sections render), Task 9 (`SkillsSidebar`)/Task 12 (sidebar in layout) implement the photo + section coverage.
- **§3 Non-goals** — explicitly absent from the plan: per-project pages, pie chart, JSON-LD, JSON Resume, plain text, custom domain, OG images, PR previews of site, dark mode, search.
- **§4 Architecture** — Task 1 builds the Python dump; Tasks 2–12 build the Astro layer; Tasks 13–14 wire tooling and CI; the architecture diagram in the spec exactly matches what the plan produces.
- **§5.1 `scripts/render_web_data.py`** — Task 1 implements exactly the script the spec describes (hard-coded `private_path=None`, Publication-to-dict conversion, both langs).
- **§5.2 `web/` project structure** — Tasks 2–12 produce every file listed in the spec's `web/` tree (BaseLayout, Header, LanguageSwitcher, ProfileSection, ExperienceSection, ProjectDetails became `ProjectsSection`, SkillsSidebar, EducationSection, LanguagesList, VolunteerSection, PublicationsList, both `index.astro`).
  - Naming note: the spec used `ProjectDetails.astro` for the per-project rendering. The plan packages this as `ProjectsSection.astro` (the whole section, with per-project cards inline). The component boundary is slightly different but the rendered output is the same. If Phase 5 splits per-project pages out, that's when `ProjectDetails` becomes its own reusable component.
- **§5.3 `astro.config.mjs`** — Task 2 produces the exact config from the spec (with one implementation deviation: Tailwind 4 ships as a Vite plugin, not as `@astrojs/tailwind`. The spec's choice to use `@astrojs/tailwind@^6` is incompatible with Tailwind 4; the plan uses `@tailwindcss/vite@^4` instead. This is the kind of "deferred to implementation" choice §10 allows.)
- **§5.4 Design language** — Task 12 implements two-column desktop / single-column mobile + IBM Plex Sans (loaded in Task 2 via fontsource) + accent color lifted from `pdf/styles.typ`.
- **§5.5 Photo handling** — Task 6 implements the `existsSync` check in `ProfileSection`. Task 13 gitignores `web/public/photo.jpg`. Task 15 documents in CLAUDE.md.
- **§5.6 Tooling pins** — Node 22 in `.nvmrc` (Task 13), pnpm 10 in `package.json` (Task 2), Astro `^5`, Tailwind `^4`, fontsource `^5` (Task 2).
- **§5.7 `.github/workflows/pages.yml`** — Task 14, full workflow content provided.
- **§5.8 Justfile** — Task 13, all four recipes added.
- **§5.9 Gitignore** — Task 13, both root and `web/.gitignore`.
- **§5.10 README** — Task 15, Website line added.
- **§5.11 CLAUDE.md** — Task 15 + Task 17 Step 6.
- **§6 Failure modes** — Task 1's `test_pii_never_reaches_dump` covers PII leak. Task 6's `existsSync` covers absent photo. Task 14's workflow uses pnpm `--frozen-lockfile` so dependency drift causes a clear error rather than silent install. Workflow concurrency group + cancel-in-progress covers the duplicate-deploy case. Subpath base misconfiguration would surface in Task 16 Step 6.
- **§7 Testing** — Task 1 covers the four pytest layers. Task 16 Step 1–2 covers local smoke. Task 17 Step 4–5 covers production smoke.
- **§8 Migration / rollback** — fully additive; rollback by deleting `pages.yml` per §8.
- **§9 Sequencing for Phase 4/5** — the JSON dump pattern in Task 1 is reusable for Phase 4 renderers. Per-project Phase 5 work reuses `ProjectsSection`'s card pattern, extracted as needed.
- **§10 Open decisions** — Task 12 Step 1 lifts the exact accent. Task 3 hand-writes the TS types. Task 8 uses cards-with-`<details>` rather than inline details under bullets (the "try both" decision was made in favor of cards — clean separation, anchor-friendly). Task 5 makes the header always-sticky (the simpler choice). Language switcher doesn't preserve scroll — `top-of-page` is the default `<a href>` behavior.

**Placeholder scan:** searched for "TBD", "TODO", "fill in" — none in step content. The one explicit placeholder is `<ACCENT_HEX>` in Task 12 Step 1–2, which is captured from `pdf/styles.typ` inline; the captured hex is then used.

**Type consistency:** `ContentData` defined in `web/src/types/content.ts` (Task 3) is the only consumer type; later tasks import slices of it (`Personal`, `Profile`, `Experience`, etc.) using the same names. `formatPeriod` helper has one signature, used identically by Experience/Projects/Education. `ProjectsSection` (plan) vs. `ProjectDetails` (spec) name divergence is called out above and traced through the file structure table — no later task refers to a non-existent component.

**Spec coverage gap check:** every numbered spec section §1–§10 is mapped to at least one task above. No silent omissions.
