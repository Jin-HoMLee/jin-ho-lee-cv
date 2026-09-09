# Design: Phase 8c — Web Variants (client-side target switcher)

**Date:** 2026-05-31  
**Owner:** Jin-Ho Lee  
**Parent spec:** [`2026-05-21-codified-cv-design.md`](./2026-05-21-codified-cv-design.md)  
**Predecessor work:** Phase 8b — Targeted CV variants (merged 2026-05-30, PR #38, commit `b9f6895`)

> **Revision (2026-05-31):** This spec was first drafted and partially executed assuming
> (a) overrides live at the top level of the resolved tree, (b) `selected_projects` is a
> web-rendered field, and (c) the switcher would be a React/Preact island. A review found all
> three assumptions wrong: `headline` lives under `personal`, `tagline`/lead live under `profile`,
> the website never reads `selected_projects` (projects render grouped by `category`), and the
> site ships **no** client framework. The data shape is now extracted from the **nested** tree,
> and the switcher is a **dependency-free vanilla-JS Astro island** whose data is **inlined at
> build time** (no runtime fetch).
>
> **Follow-up revision:** The complementary-view review extended the web projection beyond
> positioning copy. `content/skills.yaml` remains the single canonical Skills baseline; its root
> `skills.variants.<target>.category_order` controls category order for every renderer, while
> `load_content(..., web_projection=True)` applies the web-only category-local `omit`,
> `omit_groups`, and `group_items` operations. Non-web loaders keep the full canonical baseline,
> including when a target is selected. The variants payload therefore carries resolved Skills
> trees for the sidebar and a derived `hero_stack` only when it differs; the switcher still
> receives only its text fields and stack projection.

## 1. Context — third of a three-part arc

8a defined positioning; 8b made variants exist at the data layer (backend); 8c wires the interactive experience on the website.

| Part | Theme | Surface | Status |
|---|---|---|---|
| 8a | Sharpen positioning | `content/` copy only | ✅ Done |
| 8b | Targeted CV variants (comp-bio vs ds-ml from one source) | schema + loader + offline renderers + CI | ✅ Done |
| **8c** | **Visual showcase refresh: client-side target switcher** | **web + render_web_data.py + Pages CI** | **this spec** |

8c keeps the site rendering bridge (remains SEO-canonical, sitemap-canonical, schema.org-canonical), but adds a **client-side island** — the TargetSwitcher component — that lets visitors instantly switch between variants *without a page reload*. Users see the exact same page, but positioned for their audience.

## 2. Problem

Phase 8b shipped the variants but left them invisible on the web:
- The Astro site renders the bridge variant only
- A computational-biology visitor sees "Bioinformatics · Data Science" as the headline and the bridge tagline/intro
- There is no way for them to see the same CV re-positioned for their market without manually requesting a different PDF

The variants exist (buildable as PDFs, in plain-text output), but the website does not expose them. This defeats the UX goal: *show one person, multiple angles, chooseable*.

## 3. Goal

From the bridge website, enable a visitor to **instantly switch between comp-bio and ds-ml positioning** (and back to bridge) without reloading the page. All switching happens in the browser by swapping already-rendered text and skill nodes.

- **Day-one deliverable:** A visible, intuitive target-switcher UI that updates the CV's positioning and Skills sidebar in-place.
- **What varies on the web:** `headline` (sticky header) · `tagline` (profile intro) · both profile paragraphs · the derived CodeHero `hero_stack` · the resolved Skills tree in the sidebar. These are the positioning fields and audience-specific evidence the page renders.

> **Revision (2026-05-31, post-review):** The second profile paragraph was originally the
> single *shared* cross-market anchor (kept identical across targets in 8b). A copy review
> found that for `ds-ml` it restated the lead almost verbatim, and that each audience is
> better served by a tuned ¶1. It is now a **per-target override** (`second_paragraph`),
> symmetric with `lead_paragraph`: it replaces `paragraphs[1]`, falling back to bridge.
> This extends 8b's profile-variant model (schema + `_resolve_profile_target`) and reverses
> the former "¶1 is shared" guard test. bridge keeps its canonical ¶1.
- **What does *not* vary on the web:** project ordering. The site renders **all** projects grouped by `category` and never consumes `selected_projects`; per-target project featuring is explicitly out of scope for 8c (a possible later "showcase" task). `selected_projects` remains a PDF/plain-text concept only.
- The **bridge variant remains canonical** for SEO: the SSG-rendered HTML, `<title>`, `<meta description>`, OG/Twitter tags, `<link rel="canonical">`, sitemap, and schema.org `Person` all stay bridge. The switch mutates only **visible body content**, never `<head>` metadata.
- Variant preference is **persisted** to `localStorage` and auto-applied on return visits.
- **Non-web Skills remain comprehensive.** PDFs and plain-text renderers continue to consume
  `--target` for their positioning and project output, apply target category ordering, and retain
  the full canonical Skills baseline; JSON Resume, JSON-LD, llms.txt, and twin renderers remain
  target-independent.
- **Sitemap routing stays unchanged:** the existing 22 core URLs remain the floor, with any registered English-only write-ups adding their own URLs; target selection adds no routes.

## 4. Data shape — resolved web projections

`render_web_data.py` outputs, per language, the web bridge tree plus a variants file containing
**only the fields that differ and that the web renders**:

| File | Contains | Usage |
|---|---|---|
| `web/src/data/content.{en,de}.json` | Resolved concise web bridge tree | Imported at build time; page renders the bridge statically |
| **`web/src/data/content.{en,de}.variants.json`** | **Resolved target overrides** | **Imported at build time; text is passed to the switcher and Skills trees to the sidebar** |

Each target object may contain these keys when their resolved value differs from the web bridge:
- `headline` — resolved `personal.headline`
- `tagline` — resolved `profile.tagline`
- `lead_paragraph` — resolved `profile.paragraphs[0]`
- `second_paragraph` — resolved `profile.paragraphs[1]`
- `skills` — the complete resolved target Skills tree for `SkillsSidebar`
- `hero_stack` — the short stack derived from the resolved Skills tree for `CodeHero`

`hero_stack` is emitted only when it differs from the bridge stack. The `skills` tree is emitted
when the target projection differs from bridge; it is not a second source of truth, but a build
output derived from `content/skills.yaml`. The target payload never includes bridge values or
`selected_projects`. The non-web bridge content and targeted non-web content continue to use the
full canonical Skills baseline and target category order because they call `load_content` without
`web_projection=True`.

The page splits each target object into two inline payloads: `TargetSwitcher` receives the four
text fields plus `hero_stack`, while `SkillsSidebar` receives a skills-only `{ skills }` map. This
keeps the full Skills tree out of the switcher's payload without duplicating source data.

### 4.1 Category ordering and projections

The root `skills.variants.<target>.category_order` list uses stable English category names. The
loader puts listed categories first and appends any unlisted categories in canonical order. The
validator requires each configured order to contain every canonical category exactly once and
rejects unknown names and duplicate base category names. Category-local `omit`, `omit_groups`,
and `group_items` operations remain web-only.

### 4.2 Why this shape

- **Resolved at build time:** The browser does not interpret YAML projection instructions or
  duplicate the Python resolver; it receives the exact target trees to render.
- **Clear audit trail:** The canonical baseline and category-local operations remain in
  `content/skills.yaml`; the variants JSON is a derived artifact containing only web differences.
- **Web-truthful:** It contains exactly the fields the website renders, while deliberately omitting
  `selected_projects`, which the site does not consume.
- **Language-scoped + parity-checked:** Each language has its own file; EN/DE parity is enforced
  by tests (§8).

## 5. Implementation

### 5.1 Python: `_extract_overrides` walks the nested tree

**File:** `scripts/render_web_data.py`

`render_web_data()` loads the concise web bridge with `web_projection=True`, then loads each
web target with the same flag. `_extract_overrides()` compares their **resolved nested trees**
and emits only differences. It reads `personal.headline`, `profile.tagline`, both profile
paragraphs, and the resolved `skills` tree. `hero_stack` is included only when the stack derived
from the target Skills tree differs from bridge. The variants loop resolves language maps,
extracts overrides against the resolved bridge, and writes `content.{lang}.variants.json`;
`_to_jsonable()` converts the resulting tree to JSON-native values.

**Contract:** never emit bridge values; never emit `selected_projects`; emit a key only when it
genuinely differs. Skill projection instructions are stripped before output, so the browser
receives render-ready trees rather than resolver configuration.

### 5.2 Vanilla-JS TargetSwitcher (no framework)

**File:** `web/src/components/TargetSwitcher.astro` (new)

The site ships **no** client framework (`web/package.json` has only Astro + Tailwind + sitemap + OG canvas). Adding React/Preact for one widget is unjustified. Astro processes and bundles `<script>` tags in `.astro` components out of the box (already used by `PublicationsChart.astro`), so the switcher is a plain component: markup + a bundled module script that mutates the DOM.

**Data delivery — inline, not fetch.** Each page imports the generated variants JSON at build
time and derives two payloads. `TargetSwitcher` receives only the four text fields plus
`hero_stack`; `SkillsSidebar` receives a skills-only `{ skills }` map. Both components use Astro's
`define:vars`, so there is **no `fetch`, no public-dir asset, and no 404 surface**. A missing or
invalid variants file fails the Astro build at import time.

**Component responsibilities:**
- `TargetSwitcher.astro` renders a labelled segmented control (`role="group"`, `aria-label`)
  with **Default** (`bridge`), **Comp Bio** (`comp-bio`), and **DS · ML** (`ds-ml`) buttons.
- It snapshots bridge text, applies the four text overrides and publication depth, persists
  `localStorage["cvTargetPreference"]`, and dispatches `cv-target-change` with the selected target,
  the CodeHero headline/tagline, and optional `hero_stack`.
- `CodeHero.astro` listens for that event and updates its target headline, tagline, and derived
  stack. `SkillsSidebar.astro` listens for the target and swaps the pre-resolved Skills tree,
  falling back to canonical skills when a target has no skills override.
- Pure progressive enhancement: with JS disabled, the page is the fully-rendered bridge CV and
  the hidden control does nothing.

**DOM hooks (added to existing components):**
- `Header.astro` — the headline `<p>` gains `data-cv-field="headline"`.
- `ProfileSection.astro` — the tagline, first paragraph, and second paragraph gain
  `data-cv-field="tagline"`, `data-cv-field="lead"`, and `data-cv-field="second"`.
- `CodeHero.astro` — target text uses `data-cv-hero-headline`, `data-cv-hero-tagline`, and
  `data-cv-hero-stack` for the event-driven update.
- `SkillsSidebar.astro` — `data-cv-skills` and `data-cv-skills-content` delimit the progressive
  skill-tree replacement.

These hooks keep independently mounted components decoupled from the switcher's location, so the
page can update all target surfaces without a shared client framework.

### 5.3 Wiring

**Files:** `web/src/pages/index.astro`, `web/src/pages/de/index.astro`

Each page imports `content.{lang}.variants.json`, then passes separate projections to the two
components:

```astro
const switcherVariants = Object.fromEntries(
  Object.entries(variantsEn).map(([target, variant]) => [target, {
    headline: variant.headline,
    tagline: variant.tagline,
    lead_paragraph: variant.lead_paragraph,
    second_paragraph: variant.second_paragraph,
    hero_stack: "hero_stack" in variant ? variant.hero_stack : undefined,
  }]),
);
const skillVariants = Object.fromEntries(
  Object.entries(variantsEn).map(([target, variant]) => [target, { skills: variant.skills }]),
);
```

The page renders `<TargetSwitcher variants={switcherVariants} ... />` between the hero/stat band
and the profile, and passes `skillVariants` to `<SkillsSidebar>`. The bridge page remains fully
server-rendered; JavaScript only enhances the target switcher and related islands.

## 6. SEO / metadata invariance

The switch mutates only visible body text. It must **not** touch `<head>`:
- `BaseLayout.astro` builds `<title>`, `<meta name="description">`, OG/Twitter title+description, and `<link rel="canonical">` from the **build-time bridge** `personal.headline` / `profile.tagline`. These stay bridge for every visitor and every crawler.
- OG images (`/og/...`) remain bridge. schema.org `Person` (`person.jsonld`) remains bridge. `robots.txt`, sitemap unchanged.

This preserves the single-canonical-identity principle 8b established for machine formats.

## 7. CI / Pages workflow

**File:** `.github/workflows/pages.yml`

The "Render web JSON" step runs `python -m scripts.render_web_data`, which emits the bridge
content and both language-specific variants files. Because the pages import those generated
files, a missing or invalid variants file fails `astro build`. The smoke-check asserts the target
switcher and all four positioning-field hooks reached both built homepages, and checks that
representative variant text was inlined without leaking into `<head>` metadata.

The sitemap smoke-check keeps the existing **22 core-URL floor**; write-ups may add URLs, but
there are no target-specific routes. The release workflow's six target × language PDFs and
machine-format outputs remain unchanged.

## 8. Validation & tests

**`schema/cv.schema.json` / `scripts/validate.py`:** the schema permits only the three known
positioning targets, per-target Skills `category_order`, and the data-only category-local
operations (`omit`, `omit_groups`, `group_items`). The validator rejects unknown, duplicate, or
missing category-order names, duplicate base group labels, and category-local variant references
to unknown groups; existing bilingual variant checks remain in force.

The focused tests assert *positioning and projection correctness*, not just structure:

1. **Resolved loader contract:** non-web target loads retain the full canonical Skills baseline;
   `web_projection=True` strips projection instructions and derives the concise bridge or target
   tree; unknown group references and duplicate labels fail validation.
2. **Web payload:** both `content.{en,de}.variants.json` files contain `comp-bio` and `ds-ml`,
   all four text overrides, and resolved target Skills trees. `hero_stack` is emitted only when it
   differs from bridge; bridge values and `selected_projects` are not emitted as overrides.
3. **Complementary views:** the Comp Bio tree retains computational-biology depth while the DS/ML
   tree foregrounds data science, ML, cloud, and agentic-development items; neither is identical
   to the concise web bridge tree.
4. **EN/DE parity:** target and override-key sets match across languages.
5. **Browser projections:** `TargetSwitcher` receives only text plus `hero_stack`, while
   `SkillsSidebar` receives the skills-only projection and falls back to canonical skills when a
   target has no override. `CodeHero` follows the same target event for headline, tagline, and
   stack.

Tests render into temporary directories rather than the generated working copy so they remain
hermetic and CI-safe.

## 9. Non-goals

- **Project reordering / featuring on the web.** Projects stay grouped by category for all targets; `selected_projects` is not consumed by the site. (Possible later showcase task.)
- **Sitemap/SEO per variant.** Bridge is the only indexable identity; no variant URLs, no per-variant OG, no `rel=canonical` juggling.
- **New client framework.** Vanilla JS only.
- **Runtime fetch / served variants assets.** Variants are bundled inline at build time; the
  browser does not fetch or interpret projection instructions.
- **`<head>` metadata switching.** Meta/OG/canonical stay bridge.
- **Server-side preference storage.** `localStorage` only.

## 10. Success criteria

- ✅ Clicking **Comp Bio** or **DS · ML** updates the header, profile paragraphs, CodeHero stack,
  publication depth, and Skills sidebar; **Default** restores bridge exactly.
- ✅ Second and later switches are instant (data is inlined; no network at any point).
- ✅ Preference persists across reloads (`localStorage`) and auto-applies on return.
- ✅ `content.{en,de}.variants.json` contains only differing text fields, resolved Skills trees,
  and an optional differing `hero_stack`; it contains no `selected_projects`.
- ✅ EN/DE target and override-key sets match.
- ✅ `<title>`/`<meta>`/OG/canonical/sitemap/schema.org all remain bridge; target selection adds no
  routes and the sitemap retains its 22 core-URL floor.
- ✅ With JS disabled, the page is the complete bridge CV (graceful degradation).
- ✅ `just validate && just test && just lint` green; `pnpm --dir web build` succeeds; no regressions.

## 11. Resolved decisions

The original spec's "open questions" are settled:
1. **Store/reactivity:** none — vanilla DOM `textContent` swaps against `[data-cv-field]` hooks;
   separate islands coordinate through `cv-target-change`.
2. **Framework:** vanilla JS; no dependency added.
3. **UI placement:** the segmented control is rendered after the hero/stat band and before the
   profile; data hooks keep its location independent of the updated surfaces.
4. **Skills projection:** `content/skills.yaml` is canonical; target category order applies to
   every renderer, while category-local omit/group projections apply only to web-data rendering.
5. **localStorage:** auto-apply the saved preference on load.
6. **JS-disabled visitors:** bridge CV renders fully server-side; the switcher is progressive
   enhancement.

## 12. Implementation status

The original Phase 8c switcher is implemented. The complementary-view follow-up extends it with
web-only Skills projections and keeps the non-web artifacts on the full canonical baseline. The
current implementation is authoritative in `content/skills.yaml`,
`scripts/content_loader.py`, `scripts/render_web_data.py`, `web/src/components/TargetSwitcher.astro`,
`web/src/components/SkillsSidebar.astro`, and `web/src/components/CodeHero.astro`; this spec records
the resulting contract rather than a pending task sequence.
