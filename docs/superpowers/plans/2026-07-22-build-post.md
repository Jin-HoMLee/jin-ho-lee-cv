# Build Post ("Ask my CV") Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a long-form build write-up at `/writeups/ask-my-cv/` plus a LinkedIn post draft, both twin-first and grounded strictly in the repo as merged on main.

**Architecture:** Extend the Phase 15 write-ups registry (`web/src/data/writeups.ts`) with a `kind` discriminator and an optional `projectId`, so a project-less "build" write-up reuses every existing renderer path (page, OG image, sitemap) with one data addition. Because a build post has no CV project card to hang off, it surfaces through a language-aware link in the shared footer (`BaseLayout.astro`), which already renders on every page in both languages. A new static-HTML guard (mirroring `tests/test_writeup_static.py`) keeps the article crawler-readable in CI.

**Tech Stack:** Astro (site), TypeScript (registry + OG route), Python/pytest (web-guard tests), `astro-og-canvas` (OG images, already wired), Tailwind + warm-editorial tokens (`web/src/styles/writeup-tokens.css`).

## Global Constraints

- Plain dash `-` only, never em dash `—` (VOICE.md + user global rule).
- Every technical claim must be true of the repo on `main` at writing time; no invented metrics, no traffic/outcome claims, no hype adjectives.
- The write-up itself stakes no hiring-outcome claim (the CNBC "sharing is the measured channel" finding motivates the *post*, not the article's content).
- English only for both pieces (Phase 15 precedent; DE surfaces link out).
- JSON-LD for the build post is `BlogPosting` (not `ScholarlyArticle`).
- One sentence per physical line in long Markdown/prose (user global rule); Astro prose uses one `<p>` per sentence-group as the splice page does.
- Nothing is posted to LinkedIn by an agent - Jin-Ho publishes personally.
- Branch: `140-build-post`. Commit prefix style: lowercase `scope: subject` (repo convention). No Claude attribution trailers.

---

## File Structure

- `web/src/data/writeups.ts` - MODIFY: add `kind: "research" | "build"`, make `projectId` optional, add the `ask-my-cv` entry.
- `web/src/pages/writeups/ask-my-cv.astro` - CREATE: the article page (full prose, `BlogPosting` JSON-LD, OG via registry).
- `web/src/layouts/BaseLayout.astro` - MODIFY: footer gains a language-aware build-post link.
- `web/src/pages/og/[...path].ts` - MODIFY: `writeupPage()` kicker reads `kind` ("Build Write-up" vs "Research Write-up").
- `tests/test_build_writeup_static.py` - CREATE: static-HTML guard for the new page + footer surfacing.
- `AGENTS.md` - MODIFY: Phase 15 row note / new Phase row for the build post; write-ups registry convention mention.

---

## Task 1: Registry extension (kind + optional projectId)

**Files:**
- Modify: `web/src/data/writeups.ts`

**Interfaces:**
- Produces: `Writeup.kind: "research" | "build"`, `Writeup.projectId?: string` (now optional), and a new registry entry `{ slug: "ask-my-cv", kind: "build", ... }`. Consumers: the page (Task 3), the OG route (Task 2), `writeupByProjectId` (unchanged - build posts have no `projectId`, so they never match, which is correct).

- [ ] **Step 1: Make `projectId` optional and add `kind` to the interface**

In `web/src/data/writeups.ts`, update the interface:

```typescript
export interface Writeup {
  /** URL slug under /writeups/. */
  slug: string;
  /** "research" amplifies a CV project; "build" is a meta post about this repo itself. */
  kind: "research" | "build";
  /** Visible article title (also the <h1> and JSON-LD headline). */
  title: string;
  /** One-sentence summary (meta description, OG, card blurb). */
  summary: string;
  /** ISO date the write-up was published/last revised. */
  date: string;
  /** Honest lifecycle marker. */
  status: "draft" | "in-progress" | "published";
  /** Article language. Both current write-ups are English-only. */
  lang: "en";
  /** CV project id a research write-up amplifies (drives the project-card cross-link). Absent for build posts. */
  projectId?: string;
  /** Code repository the article is based on (JSON-LD isBasedOn / linkout). */
  repoUrl: string;
  /** OG-image key registered in web/src/pages/og/[...path].ts. */
  ogSlug: string;
}
```

- [ ] **Step 2: Add `kind: "research"` to the existing splice entry**

The splice entry must keep compiling. Add the field:

```typescript
  {
    slug: "splice-neoepitopes",
    kind: "research",
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
```

- [ ] **Step 3: Add the build-post entry**

Append to the `writeups` array:

```typescript
  {
    slug: "ask-my-cv",
    kind: "build",
    title: "Ask my CV",
    summary:
      "How I turned my CV into one YAML source of truth, five renderers, and a digital twin you can talk to - and had an AI agent build most of it.",
    date: "2026-07-22",
    status: "published",
    lang: "en",
    repoUrl: "https://github.com/Jin-HoMLee/jin-ho-lee-cv",
    ogSlug: "writeups-ask-my-cv-en",
  },
```

- [ ] **Step 4: Typecheck the web package**

Run: `pnpm --dir web astro check 2>&1 | tail -20` (or `pnpm --dir web exec tsc --noEmit` if astro check is slow)
Expected: no new type errors from `writeups.ts`. (A pre-existing baseline of unrelated warnings is acceptable; no error should reference `writeups.ts` or `projectId`.)

- [ ] **Step 5: Commit**

```bash
git add web/src/data/writeups.ts
git commit -m "web(#140): registry supports build-kind write-ups (optional projectId)"
```

---

## Task 2: OG kicker reads the write-up kind

**Files:**
- Modify: `web/src/pages/og/[...path].ts`

**Interfaces:**
- Consumes: `Writeup.kind` from Task 1.
- Produces: an OG page registered under `writeups-ask-my-cv-en` (automatic via the existing `for (const w of writeups)` loop), with a kicker that says "Build Write-up" for `kind: "build"`.

- [ ] **Step 1: Make the kicker kind-aware**

In `web/src/pages/og/[...path].ts`, update `writeupPage()` so the kicker label follows `kind`:

```typescript
const WRITEUP_KIND_LABELS: Record<string, string> = {
  research: "Research Write-up",
  build: "Build Write-up",
};

function writeupPage(w: (typeof writeups)[number], name: string): OgPage {
  return {
    kicker: `${name} - ${WRITEUP_KIND_LABELS[w.kind] ?? "Write-up"}`,
    title: w.title,
    subtitle: w.summary,
    meta: [
      { label: "Status", value: WRITEUP_STATUS_LABELS[w.status] ?? w.status },
      { label: "Language", value: WRITEUP_LANG_LABELS[w.lang] ?? w.lang.toUpperCase() },
    ],
  };
}
```

- [ ] **Step 2: Typecheck**

Run: `pnpm --dir web exec tsc --noEmit 2>&1 | grep -i "og/\|writeup" || echo "no og/writeup type errors"`
Expected: `no og/writeup type errors`.

- [ ] **Step 3: Commit**

```bash
git add web/src/pages/og/\[...path\].ts
git commit -m "web(#140): OG kicker reflects write-up kind (build vs research)"
```

---

## Task 3: The write-up page

**Files:**
- Create: `web/src/pages/writeups/ask-my-cv.astro`

**Interfaces:**
- Consumes: the `ask-my-cv` registry entry (Task 1), `BaseLayout`, `writeup-tokens.css`, `ThemeToggle`.
- Produces: the route `/writeups/ask-my-cv/` with server-rendered article prose, a `BlogPosting` JSON-LD block (escaped `<`), and OG tags via `BaseLayout`.

This page mirrors `web/src/pages/writeups/splice-neoepitopes.astro` structurally but has NO interactive figure components (build post, not research) and uses `BlogPosting` JSON-LD. Every prose claim below is grounded in AGENTS.md / repo behavior on main.

- [ ] **Step 1: Create the page with frontmatter + JSON-LD**

Create `web/src/pages/writeups/ask-my-cv.astro`:

```astro
---
import "../../styles/writeup-tokens.css";
import contentEn from "../../data/content.en.json";
import BaseLayout from "../../layouts/BaseLayout.astro";
import type { ContentData } from "../../types/content";
import { writeups } from "../../data/writeups";
import ThemeToggle from "../../components/ThemeToggle.astro";
import { PAGES_BASE_URL } from "../../lib/site-config";

const data = contentEn as unknown as ContentData;
const w = writeups.find((x) => x.slug === "ask-my-cv")!;
const canonical = `${PAGES_BASE_URL}/writeups/${w.slug}/`;
const twinUrl = PAGES_BASE_URL + "/";

const articleJsonld = {
  "@context": "https://schema.org",
  "@type": "BlogPosting",
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
---
<BaseLayout
  lang="en"
  data={data}
  ogSlug={w.ogSlug}
  ogTitle={`${w.title} - ${data.personal.name.given} ${data.personal.name.family}`}
  ogDescription={w.summary}
  ogType="article"
>
  <article class="writeup mx-auto max-w-3xl">
    <nav class="mb-4 flex items-center justify-between text-sm">
      <a href="/" class="text-[var(--ink-muted)] underline hover:text-[var(--ink)]">← Back to CV</a>
      <ThemeToggle />
    </nav>

    <header class="mb-8">
      <p class="font-mono-plex text-xs uppercase tracking-wider text-[var(--ink-faint)]">Build write-up</p>
      <h1 class="mt-2 font-serif-display text-3xl font-semibold text-[var(--ink)] md:text-4xl">{w.title}</h1>
      <p class="mt-3 text-base text-[var(--ink-muted)]">{w.summary}</p>
    </header>

    <section class="writeup-section">
      <h2 class="font-serif-display text-2xl text-[var(--ink)]">Don't read my CV. Ask it.</h2>
      <p>There is a chat box on <a class="text-[var(--w-accent)] underline hover:text-[var(--w-accent-hover)]" href={twinUrl}>my CV site</a>. It answers questions about my work in my own grounding, not a generic model's guesses.</p>
      <p>Try it with something a recruiter would actually ask: "What has Jin-Ho done with RNA-Seq data?" or "Does he have production ML experience, or only research?" or "Summarize his last three years in two sentences."</p>
      <p>The rest of this post is how that box - and the CV behind it - is built, and why I built it that way.</p>
    </section>

    <section class="writeup-section">
      <h2 class="font-serif-display text-2xl text-[var(--ink)]">One source of truth, many renderers</h2>
      <p>The CV is not a document. It is data: a set of YAML files plus a BibTeX bibliography, with a JSON Schema that every field is validated against.</p>
      <p>Nothing that presents the CV reads from a rendered artifact. The PDF, the website, a JSON Resume export, a schema.org JSON-LD graph, and a plain-text version are all independent scripts that consume the same content. Swap any one of them and the others do not notice.</p>
      <p>That inversion - content knows nothing about presentation - is the whole design. A new output format is a new consumer, never a new copy of the data. The digital twin is just the sixth consumer.</p>
    </section>

    <section class="writeup-section">
      <h2 class="font-serif-display text-2xl text-[var(--ink)]">The twin: full context, not retrieval</h2>
      <p>The obvious way to build a CV chatbot in 2026 is retrieval-augmented generation: chunk the CV, embed it, fetch the top matches per question. I did not do that.</p>
      <p>A whole CV is small - well under the context window of any current model. So a build step compiles the entire CV into one Markdown blob and the model gets all of it on every question. No retrieval step means no retrieval mistakes: the model never fails to fetch the one bullet that mattered.</p>
      <p>There is a deliberate asymmetry here. The public site is a sharp, curated selection. The twin reads from a larger, gitignored "master" overlay - a superset life-database that never ships to the public HTML. The twin can therefore answer questions the crawled page cannot, which is exactly the reason to talk to it instead of scraping the site.</p>
    </section>

    <section class="writeup-section">
      <h2 class="font-serif-display text-2xl text-[var(--ink)]">Running an LLM for free, reliably</h2>
      <p>The twin runs on a Cloudflare Worker with no paid inference bill. It uses free model tiers, and free tiers have daily request caps.</p>
      <p>So the Worker does not depend on one model. It cascades: a best-first chain of Gemini and Gemma models, and when every one of those is exhausted or erroring, it falls through to a different vendor entirely (Cloudflare Workers AI). Each rung has its own separate quota, so chaining them multiplies the daily headroom instead of dying when the top model's quota runs out.</p>
      <p>Getting this right meant learning each family's quirks the hard way - which models need a "thinking" budget set to zero, which reject that setting outright, which stream their reasoning as tokens you have to filter out before the answer reaches the browser. The cascade is boring on purpose: the twin stays reachable.</p>
    </section>

    <section class="writeup-section">
      <h2 class="font-serif-display text-2xl text-[var(--ink)]">Guardrails, and keeping PII out</h2>
      <p>A CV site has real private data behind it - a phone number, an address - that must never leak into a public repo or a model's mouth.</p>
      <p>So the same PII guard runs on three surfaces: a pre-commit hook, an editor-tool hook, and a CI check. All three call one detection core, so there is a single place to be right. Private files live outside git entirely; the guard is the backstop for the day someone runs <span class="font-mono-plex">git add -f</span>.</p>
      <p>The twin has its own guardrails: a bot-check on the browser, per-visitor rate caps, and persona rules that keep it answering as a grounded CV assistant rather than a general chatbot. Consented contact details a visitor chooses to leave are the one thing kept deliberately, because that is the point of leaving them.</p>
    </section>

    <section class="writeup-section">
      <h2 class="font-serif-display text-2xl text-[var(--ink)]">Built by directing an agent</h2>
      <p>I did not hand-write most of this. I directed an AI coding agent through it, in fifteen phases, each one a loop: brainstorm the scope, write a spec, turn the spec into a step-by-step plan, then execute the plan task by task with a fresh agent per task and a review gate between them.</p>
      <p>Tests came first where it mattered - the schema, the renderers, the guards all have failing tests written before the code. The interesting skill in 2026 is not typing the code. It is decomposing the work so an agent can do it correctly, and knowing what to reject when it comes back wrong.</p>
      <p>The whole history is public, spec files and all. If you want to see what agent-directed engineering actually looks like as a git log, it is right there.</p>
    </section>

    <section class="writeup-section">
      <h2 class="font-serif-display text-2xl text-[var(--ink)]">What it cost, and where to look</h2>
      <p>Nothing, in running costs. Static hosting, a free Worker tier, free model tiers, free CI. The bounded pieces are bounded on purpose.</p>
      <p>The code, every spec, and the full build history: <a class="text-[var(--w-accent)] underline hover:text-[var(--w-accent-hover)]" href={w.repoUrl}>{w.repoUrl}</a>.</p>
      <p>And the twin is still waiting for a question: <a class="text-[var(--w-accent)] underline hover:text-[var(--w-accent-hover)]" href={twinUrl}>ask it something</a>.</p>
    </section>

    <script type="application/ld+json" set:html={articleJsonldStr}></script>
  </article>
</BaseLayout>
```

- [ ] **Step 2: Verify the page builds**

Run: `just web-build 2>&1 | tail -15`
Expected: build succeeds; `web/dist/writeups/ask-my-cv/index.html` exists.

- [ ] **Step 3: Eyeball the rendered static HTML for the key strings**

Run: `grep -c "Ask my CV\|Don't read my CV\|BlogPosting\|full context, not retrieval" web/dist/writeups/ask-my-cv/index.html`
Expected: a nonzero count (each phrase present in server-rendered HTML).

- [ ] **Step 4: Commit**

```bash
git add web/src/pages/writeups/ask-my-cv.astro
git commit -m "web(#140): add the 'Ask my CV' build write-up page"
```

---

## Task 4: Footer surfacing (language-aware build-post link)

**Files:**
- Modify: `web/src/layouts/BaseLayout.astro:94-99`

**Interfaces:**
- Consumes: the `lang` prop `BaseLayout` already receives.
- Produces: a footer link to `/writeups/ask-my-cv/` present on every page in both languages, with an English-facing label on DE pages ("Read in English", matching the splice DE-card convention the guard already asserts).

- [ ] **Step 1: Add the language-aware footer link**

Replace the footer `<p>` in `web/src/layouts/BaseLayout.astro` (currently lines ~95-98) with:

```astro
      <p>
        © {new Date().getUTCFullYear()} {data.personal.name.given} {data.personal.name.family} ·
        <a class="underline hover:text-[var(--text)]" href="https://github.com/Jin-HoMLee/jin-ho-lee-cv">Source on GitHub</a> ·
        <a class="underline hover:text-[var(--text)]" href="/writeups/ask-my-cv/">{lang === "de" ? "Wie diese Seite gebaut wurde (Read in English)" : "How this site was built"}</a>
      </p>
```

- [ ] **Step 2: Rebuild and confirm the link is on both index pages**

Run: `just web-build >/dev/null 2>&1 && for f in web/dist/index.html web/dist/de/index.html; do grep -c "/writeups/ask-my-cv/" "$f"; done`
Expected: `1` and `1` (link present on both EN and DE index).

- [ ] **Step 3: Commit**

```bash
git add web/src/layouts/BaseLayout.astro
git commit -m "web(#140): surface the build write-up via a language-aware footer link"
```

---

## Task 5: Static-HTML guard (prove it bites)

**Files:**
- Create: `tests/test_build_writeup_static.py`

**Interfaces:**
- Consumes: the built `web/dist` (guard self-skips without a build, like `test_writeup_static.py`).
- Produces: CI coverage in the `web-guard` job (which builds `web/dist` first). No wiring change needed - `web-guard` runs the whole `tests/test_*static*` set.

- [ ] **Step 1: Write the guard test**

Create `tests/test_build_writeup_static.py`:

```python
"""Static-HTML guard for the 'Ask my CV' build write-up (issue #140).

AI crawlers do not execute JavaScript, so the crawler-critical strings of the
article - title, every section heading, the twin invitation, the BlogPosting
JSON-LD, and the footer surfacing on both index languages - must be in the
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
WRITEUP = DIST / "writeups" / "ask-my-cv" / "index.html"
INDEX_EN = DIST / "index.html"
INDEX_DE = DIST / "de" / "index.html"

REPO_URL = "https://github.com/Jin-HoMLee/jin-ho-lee-cv"
TITLE = "Ask my CV"
SECTION_HEADINGS = [
    "Don&#39;t read my CV. Ask it.",
    "One source of truth, many renderers",
    "The twin: full context, not retrieval",
    "Running an LLM for free, reliably",
    "Guardrails, and keeping PII out",
    "Built by directing an agent",
    "What it cost, and where to look",
]
WRITEUP_PATH = "/writeups/ask-my-cv/"

pytestmark = pytest.mark.skipif(
    not WRITEUP.exists(),
    reason="needs a built site (run: just web-build)",
)


@pytest.fixture(scope="module")
def html() -> str:
    return WRITEUP.read_text(encoding="utf-8")


def test_title_in_static_html(html):
    assert TITLE in html


def test_every_section_heading_in_static_html(html):
    for heading in SECTION_HEADINGS:
        pattern = rf"<h2[^>]*>{re.escape(heading)}</h2>"
        assert re.search(pattern, html), (
            f"section heading {heading!r} not found as an <h2> element in raw HTML"
        )


def test_twin_invitation_in_static_html(html):
    # The whole point of the post: a live, crawler-visible invitation to ask the twin.
    assert "ask it something" in html.lower()


def test_repo_linkout_in_static_html(html):
    assert REPO_URL in html


def _ldjson_blocks(html: str) -> list[str]:
    return re.findall(
        r'<script type="application/ld\+json"[^>]*>(.*?)</script>', html, flags=re.S
    )


def test_blogposting_jsonld_is_present_correct_and_escaped(html):
    article = None
    for raw in _ldjson_blocks(html):
        assert "<" not in raw, "inline JSON-LD carries a raw '<' (lost \\u003c escaping)"
        data = json.loads(raw)
        if isinstance(data, dict) and data.get("@type") == "BlogPosting":
            article = data
    assert article is not None, "no BlogPosting JSON-LD on the build write-up"
    assert article["headline"] == TITLE
    author = article["author"]
    name = author["name"] if isinstance(author, dict) else author
    assert name == "Jin-Ho Lee"
    assert article["isBasedOn"] == REPO_URL


@pytest.mark.skipif(not INDEX_EN.exists(), reason="needs a built site")
def test_en_footer_links_to_build_writeup():
    html = INDEX_EN.read_text(encoding="utf-8")
    assert WRITEUP_PATH in html
    assert "How this site was built" in html


@pytest.mark.skipif(not INDEX_DE.exists(), reason="needs a built site")
def test_de_footer_links_to_build_writeup_in_english():
    html = INDEX_DE.read_text(encoding="utf-8")
    assert WRITEUP_PATH in html
    assert "Read in English" in html


@pytest.mark.skipif(not WRITEUP.exists(), reason="needs a built site")
def test_build_writeup_is_in_sitemap():
    sitemaps = list(DIST.glob("sitemap*.xml"))
    assert sitemaps, "no sitemap emitted by the build"
    joined = "".join(p.read_text(encoding="utf-8") for p in sitemaps)
    assert "writeups/ask-my-cv" in joined, "build write-up route missing from sitemap"
```

Note on the heading assertion: Astro HTML-escapes the apostrophe in "Don't" to `&#39;`, so the expected heading string uses `Don&#39;t`. Verify the exact entity in Step 3 and adjust if the build emits `&#x27;` instead.

- [ ] **Step 2: Run the guard against the current build - expect PASS**

Run: `just web-build >/dev/null 2>&1 && uv run pytest tests/test_build_writeup_static.py -v 2>&1 | tail -20`
Expected: all tests PASS. If `test_every_section_heading_in_static_html` fails only on the apostrophe entity, fix the `SECTION_HEADINGS[0]` literal to match the emitted entity, rebuild, rerun.

- [ ] **Step 3: Prove each assertion bites (guard-tautology lesson)**

For each of the four content assertions, temporarily break its target and confirm the test fails, then restore. Do this in one pass:

```bash
# a) title: temporarily change the registry title, rebuild, expect test_title FAIL
# b) a heading: comment out one <h2> section, rebuild, expect heading test FAIL
# c) JSON-LD: temporarily change @type to "Article", rebuild, expect BlogPosting test FAIL
# d) footer: temporarily remove the footer link, rebuild, expect both footer tests FAIL
```

Run each break → `just web-build` → `uv run pytest tests/test_build_writeup_static.py -v`, confirm the RED, then `git checkout` the file. Record in the commit that each assertion was proven to bite.
Expected: each break produces exactly the corresponding failure; after restore, all green.

- [ ] **Step 4: Commit**

```bash
git add tests/test_build_writeup_static.py
git commit -m "test(#140): static-HTML guard for the build write-up (proven to bite)"
```

---

## Task 6: LinkedIn post draft (both variants)

**Files:**
- Create: `docs/build-post/linkedin-draft.md`

**Interfaces:**
- Consumes: nothing (standalone text deliverable).
- Produces: a committed draft (nothing private in it) Jin-Ho edits and posts himself.

- [ ] **Step 1: Write the draft with both link variants**

Create `docs/build-post/linkedin-draft.md`:

```markdown
# LinkedIn post draft - "Ask my CV" (#140)

Not application material; nothing private here. Jin-Ho reviews, edits, and posts this personally - no agent posts to LinkedIn.
Pick ONE variant at publish time. VOICE.md is the floor; run it past yourself out loud before posting.

---

## Variant A - link inline

Don't read my CV. Ask it.

There's a chat box on my CV site that answers questions about my work - grounded in my actual history, not a model's guesses. Ask it "does he have production ML experience or only research?" and see what comes back.

Under the hood it's the same idea all the way down: my CV isn't a document, it's one YAML source of truth that five renderers read from - PDF, website, JSON Resume, a schema.org graph, plain text. The chat box is just the sixth renderer. It runs on a free Cloudflare Worker with a model cascade so it stays up without an inference bill, and PII guards on three surfaces keep the private data private.

I also didn't hand-write most of it. I directed an AI agent through 15 phases of brainstorm → spec → plan → execute, tests first. The whole history is public, specs and all.

Ask the twin something: [LINK]
Read how it's built: [WRITEUP LINK]

---

## Variant B - link in first comment

Don't read my CV. Ask it.

There's a chat box on my CV site that answers questions about my work - grounded in my actual history, not a model's guesses. Ask it "does he have production ML experience or only research?" and see what comes back.

Under the hood it's one idea all the way down: my CV isn't a document, it's a single YAML source of truth that five renderers read from - PDF, website, JSON Resume, a schema.org graph, plain text. The chat box is just the sixth renderer. Free Cloudflare Worker, a model cascade so it stays up without an inference bill, PII guards on three surfaces.

And I didn't hand-write most of it - I directed an AI agent through 15 phases of brainstorm → spec → plan → execute, tests first. The whole build history is public.

Links in the comments 👇

(first comment: the twin + the write-up)

---

## Notes for Jin-Ho
- Both variants use "→" in the phase arrow; swap for "->" if you want the plain-dash-everywhere rule to hold on LinkedIn too.
- The example question is a stress-test question (research-vs-production) on purpose - it invites the reader to check honesty, which is the point.
- Consider a screen recording of one twin exchange as the post's media; LinkedIn favours native video/image over link posts (Variant B exists for that reason).
```

- [ ] **Step 2: Run the advisory cliché linter over the draft**

`scripts/letter_lint.py` is a library (`lint_body(text, lang="en") -> list[str]`), not a CLI. Call it inline against the draft:

```bash
uv run python -c "
from pathlib import Path
from scripts.letter_lint import lint_body
findings = lint_body(Path('docs/build-post/linkedin-draft.md').read_text(encoding='utf-8'))
print('\n'.join(findings) or 'no cliché hits')
"
```

Expected: `no cliché hits`, or only false positives on legitimate domain words (the module documents "robust"/"landscape" as expected cheap false positives). Fix any genuine cliché hit; a false positive on a real word is fine to leave. Note the blocklist is cover-letter-tuned (openers like "i am writing to apply"), so a marketing-style post may legitimately trip nothing.

- [ ] **Step 3: Commit**

```bash
git add docs/build-post/linkedin-draft.md
git commit -m "docs(#140): LinkedIn build-post draft (both link variants)"
```

---

## Task 7: Update AGENTS.md (plans-update-CLAUDEmd convention)

**Files:**
- Modify: `AGENTS.md` (the canonical context file; `CLAUDE.md` is a symlink to it)

- [ ] **Step 1: Add the build post to the phasing / conventions**

In `AGENTS.md`, extend the Phase 15 row (or add a short follow-up note) recording that the write-ups registry now carries a second, `build`-kind write-up (`/writeups/ask-my-cv/`, #140), surfaced via the shared footer rather than a project card, guarded by `tests/test_build_writeup_static.py` in the `web-guard` job. Keep it to one or two sentences in the existing style. Also note the registry gained a `kind` discriminator and an optional `projectId`.

Grounding for the row text (verify against the merged state): the page is `BlogPosting` JSON-LD, English-only, stakes no hiring claim, zero running cost.

- [ ] **Step 2: Confirm the symlink still resolves (no accidental unlink)**

Run: `readlink CLAUDE.md`
Expected: `AGENTS.md`.

- [ ] **Step 3: Commit**

```bash
git add AGENTS.md
git commit -m "docs(#140): record the build write-up in the phasing table"
```

---

## Task 8: Full green gate + push

- [ ] **Step 1: Run the full local gate**

Run: `just validate && just lint && uv run ruff format --check . && just web-build && just web-guard 2>&1 | tail -15 && just test 2>&1 | tail -3`
Expected: validate OK; lint clean; format clean; web build succeeds; `web-guard` passes (both static-fact and both write-up guards); pytest all green.

- [ ] **Step 2: Push the branch**

```bash
git push origin 140-build-post
```

- [ ] **Step 3: Open the PR**

```bash
gh pr create --repo Jin-HoMLee/jin-ho-lee-cv --base main --head 140-build-post \
  --title "Build post: 'Ask my CV' write-up + LinkedIn draft (#140)" \
  --body "$(cat <<'BODY'
Closes #140 (build + review; the LinkedIn post itself is published by Jin-Ho, tracked as a follow-up tick on #140).

## What this ships
- `/writeups/ask-my-cv/` - a twin-first build write-up, `BlogPosting` JSON-LD, crawler-readable static HTML, OG image, sitemap entry.
- Write-ups registry gains a `kind` discriminator + optional `projectId`; the build post surfaces via a language-aware footer link (no CV project to hang a card off).
- `tests/test_build_writeup_static.py` in the `web-guard` job (each assertion proven to bite).
- `docs/build-post/linkedin-draft.md` - two link variants for Jin-Ho to edit and post personally.

## Test plan
- [ ] `just validate` + `just lint` + `ruff format --check` green
- [ ] `just web-build` + `just web-guard` green (build write-up + existing splice + static-facts guards)
- [ ] `just test` green
- [ ] Every architecture claim in the article verified against main
- [ ] Jin-Ho has read and approved both the write-up prose and the LinkedIn draft
BODY
)"
```

- [ ] **Step 4: Offer @claude review** (per repo convention - offer only, do not ping without Jin-Ho's go).

---

## Task 9: Post-review reuse contract

**Files:**
- Create: `LICENSE`
- Create: `LICENSES/MIT.txt`
- Create: `LICENSES/LicenseRef-All-Rights-Reserved.txt`
- Create: `REUSE.toml`
- Create: `docs/reuse.md`
- Create: `tests/test_reuse_contract.py`
- Modify: `README.md`
- Modify: `web/src/pages/writeups/ask-my-cv.astro`
- Modify: `tests/test_build_writeup_static.py`
- Modify: `AGENTS.md`
- Modify: `docs/superpowers/specs/2026-07-22-build-post-design.md`

**Interfaces:**
- Consumes: the existing public `content/` data model, private-overlay convention, renderer commands, write-up page, and static-HTML guard.
- Produces: a scoped MIT permission grant, an honest fork-and-adapt guide, and a crawler-readable final article section linking that guide.

- [ ] **Step 1: Write the failing reuse-contract tests**

Create `tests/test_reuse_contract.py` with assertions that `LICENSE` contains the standard MIT grant, `REUSE.toml` maps reusable files to MIT and every excluded or duplicated personal-content path to `LicenseRef-All-Rights-Reserved`, `README.md` links the guide, and the guide covers `content/`, the private overlay, identity/domain/workflow replacement, build commands, and the optional twin.

Extend `SECTION_HEADINGS` in `tests/test_build_writeup_static.py` with `Can I use this for my own CV?`, then assert the emitted article links to `https://github.com/Jin-HoMLee/jin-ho-lee-cv/blob/main/docs/reuse.md`.

- [ ] **Step 2: Run the tests and observe RED**

Run: `uv run pytest tests/test_reuse_contract.py -q`
Expected: FAIL because `LICENSE`, `REUSE.toml`, `LICENSES/`, and `docs/reuse.md` do not exist.

Run: `just web-build && uv run pytest tests/test_build_writeup_static.py -q`
Expected: FAIL because the closing heading and reuse-guide link are absent.

- [ ] **Step 3: Add the scoped license and guide**

Create `LICENSE` with the unmodified MIT text so GitHub and other tooling can detect it reliably.
Add the MIT and custom all-rights-reserved texts under `LICENSES/`, then create `REUSE.toml` as the authoritative file-level map.
Apply MIT to software, schemas, reusable templates, build configuration, tests, and technical documentation.
Override `content/`, `web/src/pages/writeups/`, `docs/build-post/`, `web/public/photo.jpg`, `web/src/assets/digital-twin-photo.png`, `tests/__snapshots__/`, and the two implementation plans containing embedded article prose with `LicenseRef-All-Rights-Reserved`.

Create `docs/reuse.md` with the current manual path: fork or clone, install exact prerequisites, replace public content and excluded prose/assets, change identity/domain/deployment settings including the Pages analytics and GSC configuration, keep PII in the private overlay, run the validation/build commands, and either disable the twin or configure independent Cloudflare and model infrastructure.

Add a short `README.md` section linking the guide and stating that this is not yet a one-command template.

- [ ] **Step 4: Add the closing article answer**

Append a final section headed `Can I use this for my own CV?`.
State that the code and reusable templates are MIT-licensed, excluded personal materials must be replaced, the PDF and static site are the easiest starting points, and the twin is optional infrastructure.
Link the current reuse guide.

- [ ] **Step 5: Record the durable license boundary**

Add a concise `AGENTS.md` convention that future changes must preserve the scoped MIT grant and must not move personal data, authored prose, or likeness assets into the licensed set accidentally.

- [ ] **Step 6: Verify GREEN and the complete repository gate**

Run: `uv run pytest tests/test_reuse_contract.py -q`
Expected: PASS.

Run: `just web-build && uv run pytest tests/test_build_writeup_static.py -q`
Expected: PASS.

Run: `just validate && just lint && uv run ruff format --check . && just web-build && just web-guard && just test`
Expected: every command passes without warnings or snapshot drift.

- [ ] **Step 7: Commit and push**

```bash
git add LICENSE LICENSES REUSE.toml README.md AGENTS.md docs/reuse.md tests/test_reuse_contract.py tests/test_build_writeup_static.py web/src/pages/writeups/ask-my-cv.astro docs/superpowers/specs/2026-07-22-build-post-design.md docs/superpowers/plans/2026-07-22-build-post.md
git commit -m "docs(#140): make CV code officially reusable"
git push origin 140-build-post
```

---

## Self-Review (completed during planning)

- **Spec coverage:** write-up (Tasks 1-4), grounding rules (article prose grounded inline, Global Constraints), web integration incl. BlogPosting/OG/sitemap/DE surfacing (Tasks 1-4), guard proven-to-bite (Task 5), LinkedIn draft both variants + cliché lint (Task 6), AGENTS.md update (Task 7), green gate (Task 8), and the approved post-review reuse contract (Task 9). The spec's "DE card linking out" is realized as the footer link (there is no project card for a build post) - a deliberate, documented deviation resolved during planning.
- **Placeholder scan:** none; all prose and code shown in full.
- **Type consistency:** `kind` added in Task 1 is consumed in Task 2 (OG) and implicitly in Task 3 (page uses `w.slug`/`w.ogSlug`/`w.repoUrl` only); `projectId` optionalization does not break `writeupByProjectId` (build post never matches, correct).
- **Known fragility flagged:** the apostrophe HTML-entity in the first heading (Task 5 Step 1 note) - verify the emitted entity and adjust the literal.
