# Phase 15: Splice-Neoepitope Research Write-up Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish a self-contained, English-only long-form "Circuits Thread"-style article at `/writeups/splice-neoepitopes/` that amplifies the L5 splice-neoepitope pipeline with three interactive-but-crawler-safe figures, built on reusable warm-editorial design tokens.

**Architecture:** A dedicated `.astro` route outside the `content/*.yaml` source-of-truth model, composing `BaseLayout` plus small vanilla-JS figure islands under `web/src/components/writeups/`. A tiny `web/src/data/writeups.ts` registry is the single source the route, the CV cross-link, the OG-image route, and the JSON-LD all read from. Warm-editorial CSS custom properties live in a scoped, reusable stylesheet so a future site-wide restyle can lift them wholesale.

**Tech Stack:** Astro (static), vanilla `<script>` islands (same pattern as the hero tabs and publication chart), CSS custom properties, `@fontsource/fraunces` (one new webfont, matching the existing `@fontsource/ibm-plex-*` convention), Python/pytest static-HTML guards.

## Global Constraints

- **Amplifier, never primary publication.** A visible framing note near the top states the article is a companion to the code and a forthcoming preprint, and that results are preliminary. Illustrative figures are labelled illustrative. The page stakes no formal scientific claim.
- **Honor the unpublished-genomics guardrail.** The page must never imply Jin-Ho's peer-reviewed publications (super-resolution microscopy / radiobiology) back this pipeline.
- **English-only.** No German article text is authored. The German site surface links to the English write-up with an "available in English" label (distinct EN/DE strings, so `tests/test_de_completeness.py` is not engaged).
- **Content model untouched.** No `content/*.yaml` schema or renderer changes. The existing renderer golden snapshots stay green.
- **Outside the YAML model.** The article prose and figures are NOT structured CV data and must not be forced through the `content/` schema.
- **No MDX, no UI framework.** Interactivity uses vanilla `<script>` islands only.
- **Crawler-readable public tier.** AI crawlers do not run JavaScript. Every crawler-critical string (title, section headings, amplifier disclaimer, each figure's meaning) must be in the server-rendered HTML with JS off. Each figure degrades to a meaningful static rendering.
- **Every new guard must be proven to bite.** A guard never seen to fail is not a guard. Each new assertion is demonstrated failing before the feature that satisfies it is complete.
- **Inline JSON-LD hardening (Phase 14 rule).** Any inline JSON-LD escapes `<` to `<` at the injection point.
- **Repo facts (verbatim).** Amplified project: `L5`. Pipeline repo: `https://github.com/Jin-HoMLee/splice-neoepitope-pipeline`. Route (trailingSlash always): `/writeups/splice-neoepitopes/`. Canonical: `https://jinholee.is-a.dev/writeups/splice-neoepitopes/`.
- **Markdown style (repo/author rule).** Plain dash `-`, never em dash. In long Markdown put each sentence on its own physical line.

---

## File Structure

**Created:**
- `web/src/data/writeups.ts` - the write-ups registry (one entry today; forward-designed for a second).
- `web/src/pages/writeups/splice-neoepitopes.astro` - the article route.
- `web/src/styles/writeup-tokens.css` - warm-editorial design tokens (the pilot seed) + the Fraunces `@fontsource` imports.
- `web/src/components/writeups/PipelineExplorer.astro` - figure 1.
- `web/src/components/writeups/JunctionFilter.astro` - figure 2.
- `web/src/components/writeups/BindingScoreWidget.astro` - figure 3.
- `tests/test_writeup_static.py` - the write-up's crawler-readability + JSON-LD + sitemap + cross-link guard.

**Modified:**
- `web/src/pages/og/[...path].ts` - add write-up OG-image pages from the registry.
- `web/src/components/ProjectsSection.astro` - render the bilingual write-up cross-link on the matching project card.
- `web/package.json` - add `@fontsource/fraunces`.
- `justfile` - add `tests/test_writeup_static.py` to the `web-guard` recipe.
- `.github/workflows/ci.yml` - add `tests/test_writeup_static.py` to the web-guard pytest step.
- `CLAUDE.md` - add the Phase 15 row to the Phasing table (final task).

---

## Task 1: Registry + route scaffold (prose, disclaimer, headings) + guard wired into CI

Ship the article route with its full prose skeleton (no figures yet), the amplifier disclaimer, and the six section headings, and wire a new static-HTML guard into both the `just web-guard` recipe and the CI job so every later task's assertions actually run in CI.

**Files:**
- Create: `web/src/data/writeups.ts`
- Create: `web/src/pages/writeups/splice-neoepitopes.astro`
- Create: `tests/test_writeup_static.py`
- Modify: `justfile` (the `web-guard` recipe, around line 153)
- Modify: `.github/workflows/ci.yml` (the "Run static-HTML facts + FAQPage guards" step, around line 232)

**Interfaces:**
- Produces: `web/src/data/writeups.ts` exports `interface Writeup`, `const writeups: Writeup[]`, and `writeupByProjectId(id: string): Writeup | undefined`. Consumed by Tasks 6 (OG route) and 7 (cross-link).
- Produces: the built page `web/dist/writeups/splice-neoepitopes/index.html`.

- [ ] **Step 1: Write the write-ups registry**

Create `web/src/data/writeups.ts`:

```ts
// Single source of truth for long-form write-ups (Phase 15).
// The route, the CV cross-link, the OG-image route, and the article JSON-LD all
// read from here, so a second write-up later is a data addition, not a refactor.
// This is the one piece of deliberate forward-design; everything else stays minimal.

export interface Writeup {
  /** URL slug under /writeups/. */
  slug: string;
  /** Visible article title (also the <h1> and JSON-LD headline). */
  title: string;
  /** One-sentence summary (meta description, OG, card blurb). */
  summary: string;
  /** ISO date the write-up was published/last revised. */
  date: string;
  /** Honest lifecycle marker; v1 ships "in-progress". */
  status: "draft" | "in-progress" | "published";
  /** Article language. v1 is English-only. */
  lang: "en";
  /** The CV project id this write-up amplifies (drives the card cross-link). */
  projectId: string;
  /** Code repository the article is based on (JSON-LD isBasedOn / linkout). */
  repoUrl: string;
  /** OG-image key registered in web/src/pages/og/[...path].ts. */
  ogSlug: string;
}

export const writeups: Writeup[] = [
  {
    slug: "splice-neoepitopes",
    title: "From Splice Junctions to Neoepitopes",
    summary:
      "How a modernized, reproducible RNA-Seq pipeline turns tumor-exclusive splice junctions into candidate immunotherapy targets.",
    date: "2026-07-20",
    status: "in-progress",
    lang: "en",
    projectId: "L5",
    repoUrl: "https://github.com/Jin-HoMLee/splice-neoepitope-pipeline",
    ogSlug: "writeups-splice-neoepitopes-en",
  },
];

export function writeupByProjectId(id: string): Writeup | undefined {
  return writeups.find((w) => w.projectId === id);
}
```

- [ ] **Step 2: Write the article route (prose skeleton)**

Create `web/src/pages/writeups/splice-neoepitopes.astro`. This scaffolds all six sections with real prose, the amplifier disclaimer, and figure placeholders (`<!-- figure N -->`) filled in by Tasks 3-5. It composes `BaseLayout` exactly like `projects/[id].astro` does.

```astro
---
import contentEn from "../../data/content.en.json";
import BaseLayout from "../../layouts/BaseLayout.astro";
import type { ContentData } from "../../types/content";
import { writeups } from "../../data/writeups";

const data = contentEn as unknown as ContentData;
const w = writeups.find((x) => x.slug === "splice-neoepitopes")!;
const disclaimer =
  "This article is a companion to the open-source code and a forthcoming preprint. " +
  "Results are preliminary and in progress; figures marked illustrative are for explanation, not findings.";
---
<BaseLayout
  lang="en"
  data={data}
  ogSlug={w.ogSlug}
  ogTitle={`${w.title} — ${data.personal.name.given} ${data.personal.name.family}`}
  ogDescription={w.summary}
  ogType="article"
>
  <article class="writeup mx-auto max-w-3xl">
    <nav class="mb-4 text-sm">
      <a href="/#L5" class="text-[var(--ink-muted)] underline hover:text-[var(--ink)]">← Back to CV</a>
    </nav>

    <header class="mb-8">
      <p class="font-mono-plex text-xs uppercase tracking-wider text-[var(--ink-faint)]">Research write-up · in progress</p>
      <h1 class="mt-2 font-serif-display text-3xl font-semibold text-[var(--ink)] md:text-4xl">{w.title}</h1>
      <p class="mt-3 text-base text-[var(--ink-muted)]">{w.summary}</p>
    </header>

    <aside data-writeup-disclaimer class="mb-8 rounded-md border border-[var(--paper-border)] bg-[var(--paper-raised)] px-4 py-3 text-sm text-[var(--ink-muted)]">
      {disclaimer}
      <span class="mt-1 block">
        Code:
        <a class="text-[var(--w-accent)] underline hover:text-[var(--w-accent-hover)]" href={w.repoUrl}>{w.repoUrl}</a>
      </span>
    </aside>

    <section class="writeup-section">
      <h2 class="font-serif-display text-2xl text-[var(--ink)]">The question</h2>
      <p>Tumors do not only mutate their genes; they mis-splice them.</p>
      <p>When a cancer cell joins two pieces of RNA that a healthy cell never would, the resulting messenger RNA can be translated into a short protein fragment that the immune system has never catalogued as "self."</p>
      <p>Those fragments - <em>neoepitopes</em> - are candidate flags an immunotherapy could be taught to hunt.</p>
      <p>This write-up walks through a pipeline that reads raw RNA-Seq data and works out, junction by junction, which of those flags are worth a closer look.</p>
    </section>

    <section class="writeup-section">
      <h2 class="font-serif-display text-2xl text-[var(--ink)]">The pipeline</h2>
      <p>The whole thing is a directed acyclic graph of Snakemake rules: each box below is a step, each arrow a dependency.</p>
      <p>Click a step to see what it consumes, what it produces, and the tool that does the work.</p>
      <!-- figure 1: PipelineExplorer -->
    </section>

    <section class="writeup-section">
      <h2 class="font-serif-display text-2xl text-[var(--ink)]">Finding tumor-exclusive junctions</h2>
      <p>A splice junction is only interesting if the tumor has it and the patient's matched-normal tissue does not.</p>
      <p>Every observed junction is classified against the GENCODE annotation as <span class="font-mono-plex">annotated</span>, <span class="font-mono-plex">normal_shared</span>, or <span class="font-mono-plex">tumor_exclusive</span>.</p>
      <p>Toggle the matched-normal sample below to watch the tumor-exclusive set shrink to the junctions that survive the comparison.</p>
      <!-- figure 2: JunctionFilter -->
    </section>

    <section class="writeup-section">
      <h2 class="font-serif-display text-2xl text-[var(--ink)]">From junction to neoepitope</h2>
      <p>A surviving junction is transcribed in silico, translated in all frames, and cut into the junction-spanning 9-mers that MHC class I molecules present on the cell surface.</p>
      <p>The patient's own HLA alleles (called from the same RNA-Seq with OptiType) decide which peptides actually get presented; MHCflurry scores how well each one binds.</p>
      <p>The widget below ranks an illustrative set of 9-mers by presentation score to convey what that step produces.</p>
      <!-- figure 3: BindingScoreWidget -->
    </section>

    <section class="writeup-section">
      <h2 class="font-serif-display text-2xl text-[var(--ink)]">Reproducibility</h2>
      <p>The pipeline is a modernized reimplementation of a 2015 splice-junction neoepitope workflow, rebuilt so that a stranger can run it.</p>
      <p>Every rule carries its own Conda environment; the graph runs locally, on a GCP GPU VM, or on a SLURM cluster with a config swap rather than a rewrite.</p>
      <p>Nothing here depends on a dependency you have to install by hand.</p>
    </section>

    <section class="writeup-section">
      <h2 class="font-serif-display text-2xl text-[var(--ink)]">Status and how to follow</h2>
      <p>Results are still cooking. This page presents the method and the shape of the output, not the final binders.</p>
      <p>The citable scientific record will be a forthcoming preprint; this article is the amplifier that links to it and to the code.</p>
      <p>Follow the work on GitHub: <a class="text-[var(--w-accent)] underline hover:text-[var(--w-accent-hover)]" href={w.repoUrl}>{w.repoUrl}</a>.</p>
    </section>
  </article>
</BaseLayout>
```

Note: `.writeup`, `font-serif-display`, and the `--ink*`/`--paper*`/`--w-accent*` tokens are defined in Task 2. Until then the page renders with fallback/unstyled colors, which is fine - the prose and headings (what this task's test checks) are present regardless.

- [ ] **Step 3: Write the failing guard**

Create `tests/test_writeup_static.py`:

```python
"""Static-HTML guard for the Phase 15 splice-neoepitope write-up (issue #128).

AI crawlers do not execute JavaScript, so every crawler-critical string of the
article - title, section headings, the amplifier disclaimer, each figure's
static fallback, the Article JSON-LD, and the CV cross-link - must be in the
server-rendered HTML. Skip-guarded locally (needs a web build); the CI
`web-guard` job and `just web-guard` build web/dist first.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DIST = REPO_ROOT / "web" / "dist"
WRITEUP = DIST / "writeups" / "splice-neoepitopes" / "index.html"
INDEX_EN = DIST / "index.html"
INDEX_DE = DIST / "de" / "index.html"

REPO_URL = "https://github.com/Jin-HoMLee/splice-neoepitope-pipeline"
TITLE = "From Splice Junctions to Neoepitopes"
SECTION_HEADINGS = [
    "The question",
    "The pipeline",
    "Finding tumor-exclusive junctions",
    "From junction to neoepitope",
    "Reproducibility",
    "Status and how to follow",
]

pytestmark = pytest.mark.skipif(
    not WRITEUP.exists(),
    reason="needs a built site (run: just web-build)",
)


@pytest.fixture(scope="module")
def html() -> str:
    return WRITEUP.read_text(encoding="utf-8")


def test_title_in_static_html(html):
    assert TITLE in html


def test_amplifier_disclaimer_in_static_html(html):
    assert "data-writeup-disclaimer" in html
    assert "companion to the open-source code and a forthcoming preprint" in html
    assert "results are preliminary" in html.lower()


def test_every_section_heading_in_static_html(html):
    for heading in SECTION_HEADINGS:
        assert heading in html, f"section heading {heading!r} missing from raw HTML"


def test_repo_linkout_in_static_html(html):
    assert REPO_URL in html
```

- [ ] **Step 4: Run the guard to verify it fails**

Run: `uv run pytest tests/test_writeup_static.py -v`
Expected: SKIPPED (no `web/dist/writeups/...` yet). This proves the skip-guard; the real bite is shown in Step 6.

- [ ] **Step 5: Wire the guard into the recipe and CI**

In `justfile`, change the `web-guard` recipe's pytest line to add the new file:

```
    uv run pytest tests/test_faq_jsonld.py tests/test_static_facts.py tests/test_writeup_static.py -v
```

In `.github/workflows/ci.yml`, change the "Run static-HTML facts + FAQPage guards" step:

```yaml
      - name: Run static-HTML facts + FAQPage guards
        run: uv run pytest tests/test_static_facts.py tests/test_faq_jsonld.py tests/test_writeup_static.py -v
```

- [ ] **Step 6: Build the site and verify the guard now passes (and bites)**

Run: `just web-build && uv run pytest tests/test_writeup_static.py -v`
Expected: PASS (4 tests).
Prove-it-bites: temporarily delete one section heading (e.g. `The pipeline`) from the `.astro` page, `just web-build`, rerun -> `test_every_section_heading_in_static_html` FAILS. Restore the heading, rebuild, confirm green again.

- [ ] **Step 7: Commit**

```bash
git add web/src/data/writeups.ts web/src/pages/writeups/splice-neoepitopes.astro tests/test_writeup_static.py justfile .github/workflows/ci.yml
git commit -m "writeup(#128): registry + route prose skeleton + crawler guard"
```

---

## Task 2: Warm-editorial design tokens (the pilot seed)

Give the article its paper-and-serif surface via scoped, reusable CSS custom properties, dark-default with a `[data-theme="light"]` override that matches the site's established theme mechanism.

**Files:**
- Create: `web/src/styles/writeup-tokens.css`
- Modify: `web/src/pages/writeups/splice-neoepitopes.astro` (import the stylesheet; add the article-surface base styles)
- Modify: `web/package.json` (add `@fontsource/fraunces`)

**Interfaces:**
- Produces: the `.writeup` scope exposing `--paper`, `--paper-raised`, `--paper-border`, `--ink`, `--ink-muted`, `--ink-faint`, `--w-accent`, `--w-accent-hover`, `--sidenote`, and the `.font-serif-display` utility. Consumed by the route and all three figure components.

- [ ] **Step 1: Add the Fraunces webfont dependency**

Run: `pnpm --dir web add @fontsource/fraunces`
Expected: `@fontsource/fraunces` appears in `web/package.json` dependencies. This mirrors the existing `@fontsource/ibm-plex-*` convention (a light, established-pattern dependency, not a framework).

- [ ] **Step 2: Write the tokens stylesheet**

Create `web/src/styles/writeup-tokens.css`:

```css
/* Warm-editorial design tokens (Phase 15 pilot seed).
   Scoped to .writeup so the article can adopt a paper-and-serif surface without
   touching the site-wide dark-technical tokens in global.css. A future
   site-wide restyle phase can lift these to :root wholesale. Dark is the
   default; [data-theme="light"] overrides, matching global.css's mechanism
   (the inline head script stamps data-theme before first paint). */

@import "@fontsource/fraunces/400.css";
@import "@fontsource/fraunces/600.css";

.writeup {
  --paper: #12100e;
  --paper-raised: #1a1613;
  --paper-border: #2b2521;
  --ink: #f3ece2;
  --ink-muted: #b8ab9a;
  --ink-faint: #7c7060;
  --w-accent: #e07a4f;
  --w-accent-hover: #f0916a;
  --sidenote: #9a8d7c;
  --serif-display: "Fraunces", Georgia, "Times New Roman", serif;
}

:root[data-theme="light"] .writeup {
  --paper: #faf6ef;
  --paper-raised: #fffdf9;
  --paper-border: #e8ddcd;
  --ink: #2a2420;
  --ink-muted: #5c5248;
  --ink-faint: #8a7d6d;
  --w-accent: #c25a34;
  --w-accent-hover: #a84a28;
  --sidenote: #7a6f60;
}

/* Article surface + reading rhythm. */
.writeup {
  background: var(--paper);
  color: var(--ink);
  padding: 2rem 1.25rem 4rem;
  border-radius: 0.5rem;
}

.font-serif-display {
  font-family: var(--serif-display);
  letter-spacing: -0.01em;
}

.writeup-section {
  margin-top: 2.5rem;
}
.writeup-section > h2 {
  margin-bottom: 0.75rem;
}
.writeup-section p {
  margin-top: 0.85rem;
  line-height: 1.7;
  color: var(--ink-muted);
  max-width: 40rem;
}
.writeup-section p em {
  color: var(--ink);
  font-style: italic;
}
```

- [ ] **Step 3: Import the tokens into the route**

In `web/src/pages/writeups/splice-neoepitopes.astro`, add to the top of the frontmatter (before other imports):

```ts
import "../../styles/writeup-tokens.css";
```

- [ ] **Step 4: Build and verify the surface renders**

Run: `just web-build`
Expected: build succeeds; `web/dist/writeups/splice-neoepitopes/index.html` exists.

- [ ] **Step 5: Visual verification (the real check for a styling task)**

A styling task's correctness is visual, not unit-assertable. Following the repo's `reference_web_visual_verify` pattern, screenshot the page in both themes with Playwright (npx-cache module + system Chrome; serve `web/dist` on a local static server first). Confirm: warm paper surface, Fraunces serif headings, terracotta accent links, readable in dark AND light. Fix any pixel-off issue before proceeding (author standing rule: pixel perfection).

- [ ] **Step 6: Commit**

```bash
git add web/src/styles/writeup-tokens.css web/src/pages/writeups/splice-neoepitopes.astro web/package.json web/pnpm-lock.yaml
git commit -m "writeup(#128): warm-editorial design tokens (pilot seed)"
```

---

## Task 3: Figure 1 - Pipeline explorer

An inline-SVG/HTML Snakemake DAG whose steps expand on click to show inputs, outputs, and tooling. Authored self-contained (the spec's `dag.svg` is not in this repo). Static fallback: all step labels and tools visible with JS off.

**Files:**
- Create: `web/src/components/writeups/PipelineExplorer.astro`
- Modify: `web/src/pages/writeups/splice-neoepitopes.astro` (import + place at `<!-- figure 1 -->`)
- Modify: `tests/test_writeup_static.py` (assert the fallback)

**Interfaces:**
- Consumes: the `.writeup` tokens from Task 2.
- Produces: server-rendered markup containing every step label and tool name (crawler fallback), progressively enhanced by a vanilla `<script>` island.

- [ ] **Step 1: Write the failing fallback assertion**

Add to `tests/test_writeup_static.py`:

```python
PIPELINE_STEPS = [
    "RNA-Seq FASTQ",
    "Alignment (HISAT2 / STAR)",
    "Junction extraction",
    "Tumor-vs-normal filtering (GENCODE)",
    "Translation to 9-mers",
    "HLA typing (OptiType)",
    "MHC-I binding (MHCflurry)",
    "TCR-pMHC structural validation",
]


def test_pipeline_explorer_fallback_lists_every_step(html):
    assert 'data-figure="pipeline-explorer"' in html
    for step in PIPELINE_STEPS:
        assert step in html, f"pipeline step {step!r} missing from raw HTML (JS-only?)"
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_writeup_static.py::test_pipeline_explorer_fallback_lists_every_step -v`
Expected: SKIPPED if not built, or FAIL after `just web-build` (marker + steps absent).

- [ ] **Step 3: Write the component**

Create `web/src/components/writeups/PipelineExplorer.astro`:

```astro
---
// Figure 1: the Snakemake DAG. Server-rendered as a full ordered list of steps
// (crawler fallback), progressively enhanced into a click-to-expand explorer.
// Self-contained: no external dag.svg dependency.
interface Step {
  id: string;
  label: string;
  inputs: string;
  outputs: string;
  tool: string;
  optional?: boolean;
}

const steps: Step[] = [
  { id: "fastq", label: "RNA-Seq FASTQ", inputs: "Sequencer output", outputs: "Paired-end reads", tool: "-" },
  { id: "align", label: "Alignment (HISAT2 / STAR)", inputs: "FASTQ + reference genome", outputs: "Aligned BAM + splice junctions", tool: "HISAT2 / STAR" },
  { id: "junctions", label: "Junction extraction", inputs: "Aligned BAM", outputs: "Observed splice junctions", tool: "regtools / bedtools" },
  { id: "filter", label: "Tumor-vs-normal filtering (GENCODE)", inputs: "Tumor + matched-normal junctions", outputs: "tumor_exclusive set", tool: "bedtools + GENCODE" },
  { id: "translate", label: "Translation to 9-mers", inputs: "tumor_exclusive junctions", outputs: "Junction-spanning peptides", tool: "Python 3.11" },
  { id: "hla", label: "HLA typing (OptiType)", inputs: "RNA-Seq reads", outputs: "Patient HLA-I alleles", tool: "OptiType" },
  { id: "bind", label: "MHC-I binding (MHCflurry)", inputs: "9-mers + HLA alleles", outputs: "Ranked neoepitope candidates", tool: "MHCflurry 2.x" },
  { id: "struct", label: "TCR-pMHC structural validation", inputs: "Top candidates", outputs: "Modeled ternary complex", tool: "TCRdock / AlphaFold v2", optional: true },
];
---
<figure data-figure="pipeline-explorer" class="my-6 rounded-md border border-[var(--paper-border)] bg-[var(--paper-raised)] p-4">
  <figcaption class="mb-3 font-mono-plex text-xs uppercase tracking-wider text-[var(--ink-faint)]">
    Figure 1 · Pipeline explorer (click a step)
  </figcaption>
  <ol class="flex flex-col gap-2">
    {steps.map((s, i) => (
      <li>
        <details class="rounded border border-[var(--paper-border)] px-3 py-2" open={i === 0}>
          <summary class="cursor-pointer list-none font-medium text-[var(--ink)]">
            <span class="font-mono-plex text-xs text-[var(--w-accent)]">{String(i + 1).padStart(2, "0")}</span>
            <span class="ml-2">{s.label}</span>
            {s.optional && <span class="ml-2 text-xs text-[var(--ink-faint)]">(optional)</span>}
          </summary>
          <dl class="mt-2 grid grid-cols-[max-content_1fr] gap-x-3 gap-y-1 text-sm text-[var(--ink-muted)]">
            <dt class="text-[var(--ink-faint)]">in</dt><dd>{s.inputs}</dd>
            <dt class="text-[var(--ink-faint)]">out</dt><dd>{s.outputs}</dd>
            <dt class="text-[var(--ink-faint)]">tool</dt><dd class="font-mono-plex">{s.tool}</dd>
          </dl>
        </details>
      </li>
    ))}
  </ol>
</figure>
```

Note: `<details>`/`<summary>` gives click-to-expand with zero JavaScript, so the fallback and the interaction are the same DOM - crawlers read every label and tool; readers get expand/collapse for free. No `<script>` needed here.

- [ ] **Step 4: Place the figure in the route**

In `web/src/pages/writeups/splice-neoepitopes.astro`, add the import:

```ts
import PipelineExplorer from "../../components/writeups/PipelineExplorer.astro";
```

Replace `<!-- figure 1: PipelineExplorer -->` with:

```astro
      <PipelineExplorer />
```

- [ ] **Step 5: Build and verify the assertion passes**

Run: `just web-build && uv run pytest tests/test_writeup_static.py::test_pipeline_explorer_fallback_lists_every_step -v`
Expected: PASS.
Prove-it-bites: comment out one step in the component, rebuild, rerun -> FAIL. Restore, rebuild, green.

- [ ] **Step 6: Visual verification**

Screenshot the figure (both themes); confirm expand/collapse works and reads as a DAG walkthrough.

- [ ] **Step 7: Commit**

```bash
git add web/src/components/writeups/PipelineExplorer.astro web/src/pages/writeups/splice-neoepitopes.astro tests/test_writeup_static.py
git commit -m "writeup(#128): figure 1 - pipeline explorer"
```

---

## Task 4: Figure 2 - Junction-origin filter

Toggle the matched-normal sample to watch the tumor-exclusive set derive. Static fallback: a two-set diagram with the exclusive set highlighted and both counts visible.

**Files:**
- Create: `web/src/components/writeups/JunctionFilter.astro`
- Modify: `web/src/pages/writeups/splice-neoepitopes.astro`
- Modify: `tests/test_writeup_static.py`

**Interfaces:**
- Consumes: `.writeup` tokens.
- Produces: crawler-readable set labels and counts; a vanilla `<script>` island that recomputes the exclusive count when the normal sample is toggled.

- [ ] **Step 1: Write the failing fallback assertion**

Add to `tests/test_writeup_static.py`:

```python
def test_junction_filter_fallback_shows_sets(html):
    assert 'data-figure="junction-filter"' in html
    assert "tumor_exclusive" in html
    assert "normal_shared" in html
    # Both raw counts must be present with JS off (illustrative, labelled).
    assert "1,204" in html  # illustrative tumor junctions
    assert "312" in html    # illustrative tumor-exclusive after filtering
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_writeup_static.py::test_junction_filter_fallback_shows_sets -v`
Expected: FAIL (after build) or SKIPPED (before).

- [ ] **Step 3: Write the component**

Create `web/src/components/writeups/JunctionFilter.astro`:

```astro
---
// Figure 2: tumor-vs-matched-normal junction filtering. Illustrative counts.
// Fallback (JS off): both sets and both counts are rendered statically.
// Enhancement: toggling the matched-normal sample recomputes the exclusive set.
const TUMOR = 1204;          // illustrative tumor junctions
const NORMAL_SHARED = 892;   // illustrative overlap with matched-normal
const EXCLUSIVE = TUMOR - NORMAL_SHARED; // 312
const fmt = (n: number) => n.toLocaleString("en-US");
---
<figure data-figure="junction-filter" class="my-6 rounded-md border border-[var(--paper-border)] bg-[var(--paper-raised)] p-4">
  <figcaption class="mb-3 font-mono-plex text-xs uppercase tracking-wider text-[var(--ink-faint)]">
    Figure 2 · Junction-origin filter (illustrative)
  </figcaption>

  <div class="flex flex-wrap items-center gap-4 text-sm">
    <div class="rounded border border-[var(--paper-border)] px-3 py-2">
      <span class="block text-[var(--ink-faint)]">tumor junctions</span>
      <span class="font-mono-plex text-lg text-[var(--ink)]">{fmt(TUMOR)}</span>
    </div>
    <label class="flex items-center gap-2 text-[var(--ink-muted)]">
      <input type="checkbox" data-normal-toggle checked class="accent-[var(--w-accent)]" />
      subtract matched-normal (<span class="font-mono-plex">normal_shared</span>)
    </label>
    <div class="rounded border border-[var(--w-accent)] px-3 py-2">
      <span class="block text-[var(--ink-faint)]"><span class="font-mono-plex">tumor_exclusive</span></span>
      <span data-exclusive-count class="font-mono-plex text-lg text-[var(--w-accent)]">{fmt(EXCLUSIVE)}</span>
    </div>
  </div>
  <p class="mt-2 text-xs text-[var(--ink-faint)]">Counts are illustrative, for explanation only.</p>

  <script is:inline define:vars={{ TUMOR, NORMAL_SHARED, EXCLUSIVE }}>
    (function () {
      const root = document.querySelector('[data-figure="junction-filter"]');
      if (!root) return;
      const toggle = root.querySelector("[data-normal-toggle]");
      const out = root.querySelector("[data-exclusive-count]");
      if (!toggle || !out) return;
      const fmt = (n) => n.toLocaleString("en-US");
      toggle.addEventListener("change", () => {
        out.textContent = fmt(toggle.checked ? EXCLUSIVE : TUMOR);
      });
    })();
  </script>
</figure>
```

- [ ] **Step 4: Place the figure**

In the route, add the import and replace `<!-- figure 2: JunctionFilter -->` with `<JunctionFilter />`:

```ts
import JunctionFilter from "../../components/writeups/JunctionFilter.astro";
```

- [ ] **Step 5: Build and verify**

Run: `just web-build && uv run pytest tests/test_writeup_static.py::test_junction_filter_fallback_shows_sets -v`
Expected: PASS.
Prove-it-bites: change the fallback `EXCLUSIVE` render so `312` no longer appears, rebuild, rerun -> FAIL. Restore, rebuild, green.

- [ ] **Step 6: Visual verification**

Screenshot; confirm the toggle flips the exclusive count between `312` and `1,204`.

- [ ] **Step 7: Commit**

```bash
git add web/src/components/writeups/JunctionFilter.astro web/src/pages/writeups/splice-neoepitopes.astro tests/test_writeup_static.py
git commit -m "writeup(#128): figure 2 - junction-origin filter"
```

---

## Task 5: Figure 3 - Binding-score mini-widget

Illustrative 9-mers ranked by MHC-I presentation score. Static fallback: a ranked table, labelled illustrative.

**Files:**
- Create: `web/src/components/writeups/BindingScoreWidget.astro`
- Modify: `web/src/pages/writeups/splice-neoepitopes.astro`
- Modify: `tests/test_writeup_static.py`

**Interfaces:**
- Consumes: `.writeup` tokens.
- Produces: a crawler-readable ranked table of peptides + scores + the word "illustrative"; a vanilla `<script>` island that re-sorts by score/allele.

- [ ] **Step 1: Write the failing fallback assertion**

Add to `tests/test_writeup_static.py`:

```python
ILLUSTRATIVE_PEPTIDES = ["KLYQVEYAF", "SLLQHLIGL", "RTYGPVFMV"]


def test_binding_widget_fallback_is_a_ranked_table(html):
    assert 'data-figure="binding-score"' in html
    assert "illustrative" in html.lower()
    for pep in ILLUSTRATIVE_PEPTIDES:
        assert pep in html, f"illustrative peptide {pep!r} missing from raw HTML"
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_writeup_static.py::test_binding_widget_fallback_is_a_ranked_table -v`
Expected: FAIL (after build) or SKIPPED.

- [ ] **Step 3: Write the component**

Create `web/src/components/writeups/BindingScoreWidget.astro`:

```astro
---
// Figure 3: illustrative MHC-I presentation ranking. NOT real results.
// Fallback (JS off): a static ranked table. Enhancement: re-sort by score.
interface Row {
  peptide: string;
  allele: string;
  score: number; // higher = better presentation (illustrative, 0-1)
}
const rows: Row[] = [
  { peptide: "KLYQVEYAF", allele: "HLA-A*24:02", score: 0.94 },
  { peptide: "SLLQHLIGL", allele: "HLA-A*02:01", score: 0.88 },
  { peptide: "RTYGPVFMV", allele: "HLA-A*02:01", score: 0.71 },
  { peptide: "AEFGQKLTV", allele: "HLA-B*07:02", score: 0.63 },
  { peptide: "NQFPDVLLM", allele: "HLA-B*07:02", score: 0.41 },
];
const sorted = [...rows].sort((a, b) => b.score - a.score);
---
<figure data-figure="binding-score" class="my-6 rounded-md border border-[var(--paper-border)] bg-[var(--paper-raised)] p-4">
  <figcaption class="mb-3 font-mono-plex text-xs uppercase tracking-wider text-[var(--ink-faint)]">
    Figure 3 · MHC-I presentation ranking (illustrative)
  </figcaption>
  <table class="w-full text-sm">
    <thead>
      <tr class="text-left text-[var(--ink-faint)]">
        <th class="py-1 font-normal">#</th>
        <th class="py-1 font-normal">9-mer</th>
        <th class="py-1 font-normal">HLA allele</th>
        <th class="py-1 font-normal">
          <button data-sort-score class="underline decoration-dotted hover:text-[var(--w-accent)]">score ↓</button>
        </th>
      </tr>
    </thead>
    <tbody data-rows>
      {sorted.map((r, i) => (
        <tr class="border-t border-[var(--paper-border)]" data-score={r.score}>
          <td class="py-1 font-mono-plex text-[var(--ink-faint)]">{i + 1}</td>
          <td class="py-1 font-mono-plex text-[var(--ink)]">{r.peptide}</td>
          <td class="py-1 font-mono-plex text-[var(--ink-muted)]">{r.allele}</td>
          <td class="py-1 font-mono-plex text-[var(--w-accent)]">{r.score.toFixed(2)}</td>
        </tr>
      ))}
    </tbody>
  </table>
  <p class="mt-2 text-xs text-[var(--ink-faint)]">Peptides and scores are illustrative, for explanation only - not findings.</p>

  <script is:inline>
    (function () {
      const root = document.querySelector('[data-figure="binding-score"]');
      if (!root) return;
      const btn = root.querySelector("[data-sort-score]");
      const body = root.querySelector("[data-rows]");
      if (!btn || !body) return;
      let asc = false;
      btn.addEventListener("click", () => {
        asc = !asc;
        btn.textContent = asc ? "score ↑" : "score ↓";
        const trs = Array.from(body.querySelectorAll("tr"));
        trs.sort((a, b) => {
          const da = parseFloat(a.getAttribute("data-score"));
          const db = parseFloat(b.getAttribute("data-score"));
          return asc ? da - db : db - da;
        });
        trs.forEach((tr, i) => {
          tr.querySelector("td").textContent = String(i + 1);
          body.appendChild(tr);
        });
      });
    })();
  </script>
</figure>
```

- [ ] **Step 4: Place the figure**

In the route, add the import and replace `<!-- figure 3: BindingScoreWidget -->` with `<BindingScoreWidget />`:

```ts
import BindingScoreWidget from "../../components/writeups/BindingScoreWidget.astro";
```

- [ ] **Step 5: Build and verify**

Run: `just web-build && uv run pytest tests/test_writeup_static.py::test_binding_widget_fallback_is_a_ranked_table -v`
Expected: PASS.
Prove-it-bites: remove the "illustrative" caption line, rebuild, rerun -> FAIL. Restore, rebuild, green.

- [ ] **Step 6: Visual verification**

Screenshot; confirm the score-sort toggle re-ranks and renumbers rows.

- [ ] **Step 7: Commit**

```bash
git add web/src/components/writeups/BindingScoreWidget.astro web/src/pages/writeups/splice-neoepitopes.astro tests/test_writeup_static.py
git commit -m "writeup(#128): figure 3 - binding-score widget"
```

---

## Task 6: Article JSON-LD + OG image

Add inline `ScholarlyArticle` JSON-LD (author Jin-Ho, `isBasedOn` = repo, escaped `<`) and register the write-up's OG image so `og:image` does not 404.

**Files:**
- Modify: `web/src/pages/writeups/splice-neoepitopes.astro` (inline JSON-LD)
- Modify: `web/src/pages/og/[...path].ts` (register write-up OG pages from the registry)
- Modify: `tests/test_writeup_static.py`

**Interfaces:**
- Consumes: `writeups` from `web/src/data/writeups.ts`.
- Produces: an inline `application/ld+json` `ScholarlyArticle` block on the write-up page, and an OG page keyed by each writeup's `ogSlug`.

- [ ] **Step 1: Write the failing JSON-LD assertion**

Add to `tests/test_writeup_static.py`:

```python
def _ldjson_blocks(html: str) -> list[str]:
    return re.findall(
        r'<script type="application/ld\+json"[^>]*>(.*?)</script>', html, flags=re.S
    )


def test_article_jsonld_is_present_correct_and_escaped(html):
    article = None
    for raw in _ldjson_blocks(html):
        # Injection points escape '<' to <; a raw '<' means a lost escape.
        assert "<" not in raw, "inline JSON-LD carries a raw '<' (lost \\u003c escaping)"
        data = json.loads(raw)
        if isinstance(data, dict) and data.get("@type") in ("Article", "ScholarlyArticle"):
            article = data
    assert article is not None, "no Article/ScholarlyArticle JSON-LD on the write-up"
    assert article["headline"] == TITLE
    author = article["author"]
    name = author["name"] if isinstance(author, dict) else author
    assert name == "Jin-Ho Lee"
    assert article["isBasedOn"] == REPO_URL
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_writeup_static.py::test_article_jsonld_is_present_correct_and_escaped -v`
Expected: FAIL (after build) or SKIPPED.

- [ ] **Step 3: Add the inline JSON-LD to the route**

In `web/src/pages/writeups/splice-neoepitopes.astro` frontmatter, after `const disclaimer = ...`, add:

```ts
import { PAGES_BASE_URL } from "../../lib/site-config";

const canonical = `${PAGES_BASE_URL}/writeups/${w.slug}/`;
const articleJsonld = {
  "@context": "https://schema.org",
  "@type": "ScholarlyArticle",
  headline: w.title,
  description: w.summary,
  datePublished: w.date,
  inLanguage: "en",
  url: canonical,
  author: {
    "@type": "Person",
    name: `${data.personal.name.given} ${data.personal.name.family}`,
  },
  isBasedOn: w.repoUrl,
};
// Escape '<' before inlining (Phase 14 hardening): a "</script>" substring in
// any inlined string would close the tag early. '<' is valid JSON.
const articleJsonldStr = JSON.stringify(articleJsonld).replace(/</g, "\\u003c");
```

Then just before `</article>` in the template, add:

```astro
    <script type="application/ld+json" set:html={articleJsonldStr}></script>
```

- [ ] **Step 4: Register the OG image page**

In `web/src/pages/og/[...path].ts`, add near the other imports:

```ts
import { writeups } from "../../data/writeups";
```

Add a page-builder alongside `projectPage`:

```ts
function writeupPage(w: (typeof writeups)[number], name: string): OgPage {
  return {
    kicker: `${name} — Research Write-up`,
    title: w.title,
    subtitle: w.summary,
    meta: [
      { label: "Status", value: "In progress" },
      { label: "Language", value: "English" },
    ],
  };
}
```

After the project loops that populate `pages`, add:

```ts
for (const w of writeups) {
  pages[w.ogSlug] = writeupPage(w, enName);
}
```

- [ ] **Step 5: Build and verify JSON-LD + OG image exist**

Run: `just web-build && uv run pytest tests/test_writeup_static.py::test_article_jsonld_is_present_correct_and_escaped -v`
Expected: PASS.
Also confirm the OG image built: `test -f web/dist/og/writeups-splice-neoepitopes-en.png` -> exists (no 404).
Prove-it-bites: temporarily change `isBasedOn` in the route to a wrong URL, rebuild, rerun -> FAIL. Restore, rebuild, green.

- [ ] **Step 6: Commit**

```bash
git add web/src/pages/writeups/splice-neoepitopes.astro "web/src/pages/og/[...path].ts" tests/test_writeup_static.py
git commit -m "writeup(#128): ScholarlyArticle JSON-LD + OG image"
```

---

## Task 7: Bilingual CV cross-link + sitemap assertion

Link the L5 project card to the write-up (EN "Read the write-up", DE "Article available in English"), and assert the route is in the built sitemap.

**Files:**
- Modify: `web/src/components/ProjectsSection.astro`
- Modify: `tests/test_writeup_static.py`

**Interfaces:**
- Consumes: `writeupByProjectId` from `web/src/data/writeups.ts`.
- Produces: an anchor to `/writeups/<slug>/` on the matching project card, rendered on both the EN and DE index pages.

- [ ] **Step 1: Write the failing cross-link + sitemap assertions**

Add to `tests/test_writeup_static.py`:

```python
WRITEUP_PATH = "/writeups/splice-neoepitopes/"


@pytest.mark.skipif(not INDEX_EN.exists(), reason="needs a built site")
def test_en_card_links_to_writeup():
    html = INDEX_EN.read_text(encoding="utf-8")
    assert WRITEUP_PATH in html
    assert "Read the write-up" in html


@pytest.mark.skipif(not INDEX_DE.exists(), reason="needs a built site")
def test_de_card_links_to_writeup_in_english():
    html = INDEX_DE.read_text(encoding="utf-8")
    assert WRITEUP_PATH in html
    assert "Read in English" in html


@pytest.mark.skipif(not WRITEUP.exists(), reason="needs a built site")
def test_writeup_is_in_sitemap():
    sitemaps = list((DIST).glob("sitemap*.xml"))
    assert sitemaps, "no sitemap emitted by the build"
    joined = "".join(p.read_text(encoding="utf-8") for p in sitemaps)
    assert "writeups/splice-neoepitopes" in joined, "write-up route missing from sitemap"
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_writeup_static.py -k "card_links or sitemap" -v`
Expected: cross-link tests FAIL (after build); sitemap test may already PASS (Astro auto-includes the route) - if so, note it and keep it as a regression guard.

- [ ] **Step 3: Add the cross-link to ProjectsSection**

In `web/src/components/ProjectsSection.astro` frontmatter, add:

```ts
import { writeupByProjectId } from "../data/writeups";

const writeupLinkLabel = { en: "Read the write-up", de: "Read in English" };
```

Inside the `{grouped[cat].map((p) => (` card, after the `<p class="mb-3 ...">{p.summary}</p>` line, add:

```astro
            {writeupByProjectId(p.id) && (
              <p class="mb-3">
                <a
                  href={`/writeups/${writeupByProjectId(p.id)!.slug}/`}
                  class="text-xs font-medium text-[var(--accent)] underline hover:text-[var(--text)]"
                >
                  {writeupLinkLabel[lang]} →
                </a>
              </p>
            )}
```

Note: the DE label "Read in English" is intentionally distinct from the EN "Read the write-up", so `tests/test_de_completeness.py` (no identical EN/DE content strings) is not engaged - and these are component labels, not `content/` data, so that test does not inspect them anyway.

- [ ] **Step 4: Build and verify**

Run: `just web-build && uv run pytest tests/test_writeup_static.py -k "card_links or sitemap" -v`
Expected: PASS.
Prove-it-bites: temporarily change `projectId` in `writeups.ts` to `"Lxx"` (no such card), rebuild, rerun -> both `card_links` tests FAIL (no link rendered). Restore to `"L5"`, rebuild, green.

- [ ] **Step 5: Commit**

```bash
git add web/src/components/ProjectsSection.astro tests/test_writeup_static.py
git commit -m "writeup(#128): bilingual CV card cross-link + sitemap guard"
```

---

## Task 8: Full-suite verification + CLAUDE.md Phasing row

Run the complete green gate, then update the authoritative Phasing table (a merged phase with no row there is a doc bug).

**Files:**
- Modify: `CLAUDE.md` (Phasing table)

- [ ] **Step 1: Run the full local green gate**

Run:
```bash
just validate && just test && just lint && just fmt && just web-guard
```
Expected: all green. `just web-guard` builds `web/dist` (with `MASTER_CV_DIR=master-cv.example`) and runs `test_static_facts.py`, `test_faq_jsonld.py`, and `test_writeup_static.py`. Confirm `test_writeup_static.py` actually RAN (not skipped) - the build satisfies its skip-guard.

- [ ] **Step 2: Confirm the deep-tier guard still holds**

The write-up is a new public surface. Confirm `tests/test_static_facts.py::test_deep_tier_stays_off_the_public_surface` still passes for both index pages (the write-up does not read the `master-cv/` overlay). Already covered by Step 1; note it explicitly.

- [ ] **Step 3: Add the Phase 15 row to CLAUDE.md**

In `CLAUDE.md`, in the Phasing table, after the Phase 14 row, add:

```
| 15 | Splice-neoepitope research write-up (warm-editorial pilot): long-form `/writeups/splice-neoepitopes/` article amplifying L5, 3 crawler-safe interactive figures, reusable warm-editorial design tokens (seed for a future site-wide restyle), write-ups registry | ✅ Done (merged <DATE>, PR #<N>). Amplifier only (companion to code + forthcoming preprint; stakes no scientific claim); English-only (DE card links out); outside the `content/` schema; new `web-guard` guard `tests/test_writeup_static.py` (crawler text + ScholarlyArticle JSON-LD + OG + sitemap + bilingual cross-link). Site-wide warm-editorial restyle deferred to its own future phase |
```

Fill `<DATE>` and `<N>` at merge time. Also add a one-line pointer under "Files to read before any phase" for the spec and this plan:

```
- `docs/superpowers/specs/2026-07-20-splice-neoepitope-writeup-design.md` - Phase 15 design spec (splice-neoepitope research write-up)
- `docs/superpowers/plans/2026-07-20-phase-15-splice-writeup.md` - implementation plan for the splice-neoepitope write-up (#128)
```

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "writeup(#128): update CLAUDE.md Phasing table (Phase 15)"
```

---

## Self-Review

**Spec coverage:**
- Publish at `/writeups/splice-neoepitopes/` -> Task 1.
- Method-and-approach story, "results in progress" -> Task 1 prose + Global Constraints.
- Three interactive figures, each with static fallback -> Tasks 3, 4, 5.
- Amplifier framing / disclaimer -> Task 1 (`data-writeup-disclaimer`) + Global Constraints.
- Reusable warm-editorial design tokens -> Task 2.
- Preserve invariants (golden snapshots, web-guard, PII, bilingual) -> no `content/` change; Task 8 Step 1-2.
- Placement outside `content/` model -> Tasks 1-2 (bespoke `.astro`, no schema).
- No MDX / no framework -> vanilla islands, Global Constraints.
- Write-ups registry -> Task 1.
- Design tokens light/dark via data-theme -> Task 2.
- Article outline (6 sections) -> Task 1.
- Bilingual handling (EN-only, DE links out) -> Task 7.
- AEO/SEO: sitemap + Article JSON-LD + escaping -> Tasks 6, 7.
- Testing: extend web-guard, snapshot fallbacks, sitemap, prove-it-bites -> Tasks 1, 3-7.
- Documentation: CLAUDE.md Phasing row -> Task 8.
- Non-goals honored: no Mol* 3D viewer, no real results, no DE article, no preprint, no site-wide restyle - none are tasked.

**Deviations from spec (justified):**
- The spec anchors figure 1 on the pipeline's existing `dag.svg`; that file is not in this repo, so figure 1 is authored self-contained from the L5 step list. More robust than depending on a missing asset; same reader outcome.
- The spec says "warm accent + Tufte sidenotes"; v1 tokens define `--sidenote` but the prose uses inline `<em>` rather than margin notes (margin notes are a layout feature better deferred until the prose is final). Tokens are seeded so a later pass can add them without re-derivation.

**Placeholder scan:** No TBD/TODO. Every code step shows complete code. Every test step shows the assertion and the expected result.

**Type consistency:** `Writeup` fields (`slug`, `title`, `summary`, `date`, `status`, `lang`, `projectId`, `repoUrl`, `ogSlug`) are used identically in the route (Task 1), OG route (Task 6), and cross-link (Task 7). `writeupByProjectId` (Task 1) is the name consumed in Task 7. `.writeup` scope and `--ink*/--paper*/--w-accent*` tokens (Task 2) are the names referenced by the route and all figures. `data-figure` attribute values (`pipeline-explorer`, `junction-filter`, `binding-score`) match between components and their assertions.
