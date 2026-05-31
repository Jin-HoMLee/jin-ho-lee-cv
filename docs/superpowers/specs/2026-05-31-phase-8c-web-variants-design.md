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
> site ships **no** client framework. Sections 3–12 below are the corrected design. The data
> shape is now **text-only** (`headline` + `tagline` + `lead_paragraph`), extraction walks the
> **nested** tree, and the switcher is a **dependency-free vanilla-JS Astro island** whose data is
> **inlined at build time** (no runtime fetch).

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

From the bridge website, enable a visitor to **instantly switch between comp-bio and ds-ml positioning** (and back to bridge) without reloading the page. All switching happens in the browser by swapping the text of three already-rendered fields.

- **Day-one deliverable:** A visible, intuitive target-switcher UI that updates the CV's positioning in-place.
- **What varies on the web (text-only):** `headline` (sticky header) · `tagline` (profile intro) · lead paragraph (`profile.paragraphs[0]`). These are the three positioning fields the page actually renders and the first thing a hiring manager reads.
- **What does *not* vary on the web:** project ordering. The site renders **all** projects grouped by `category` and never consumes `selected_projects`; per-target project featuring is explicitly out of scope for 8c (a possible later "showcase" task). `selected_projects` remains a PDF/plain-text concept only.
- The **bridge variant remains canonical** for SEO: the SSG-rendered HTML, `<title>`, `<meta description>`, OG/Twitter tags, `<link rel="canonical">`, sitemap, and schema.org `Person` all stay bridge. The switch mutates only **visible body text**, never `<head>` metadata.
- Variant preference is **persisted** to `localStorage` and auto-applied on return visits.
- **Zero impact on PDFs, JSON Resume, JSON-LD, or plain-text.** Those renderers continue to consume the `--target` flag directly.
- **Sitemap stays at 22 URLs** (unchanged); only the in-memory display varies.

## 4. Data shape — lean, text-only overrides

`render_web_data.py` outputs, per language, the existing bridge tree plus a small variants file containing **only the fields that differ and that the web renders**:

| File | Contains | Usage |
|---|---|---|
| `web/src/data/content.{en,de}.json` | Full bridge tree, resolved | Imported at build time; page renders bridge statically |
| **`web/src/data/content.{en,de}.variants.json`** | **Text overrides only** | **Imported at build time by the page, inlined into the switcher** |

**Shape of `content.en.variants.json`:**
```json
{
  "comp-bio": {
    "headline": "Computational Biology · Cancer Genomics",
    "tagline": "Bioinformatician with a decade in cancer genomics — …",
    "lead_paragraph": "I build reproducible, production-grade pipelines for cancer genomics. …"
  },
  "ds-ml": {
    "headline": "Data Science · Machine Learning",
    "tagline": "Data scientist who ships production ML on GCP — …",
    "lead_paragraph": "I build and ship production machine-learning systems on Google Cloud. …"
  }
}
```

Each target object contains **only** the three text fields, and only when they differ from bridge:
- `headline` — sourced from the resolved tree's `personal.headline`
- `tagline` — from `profile.tagline`
- `lead_paragraph` — from `profile.paragraphs[0]` (the lead; `paragraphs[1]`, the shared industry-proof paragraph, never varies and is never emitted)

The variant JSON does **not** include bridge values and does **not** include `selected_projects`. Merging is additive: bridge (rendered at build time) + variant text overrides = displayed positioning.

### 4.1 Why this shape

- **Tiny payload (~300 bytes/lang):** Three short strings × two targets. Cheap to inline directly into the page — no separate network request, no flash-of-bridge while an async fetch resolves.
- **Clear audit trail:** Storing only the overrides makes it obvious *what* varies per target.
- **Web-truthful:** It contains exactly the fields the website renders, nothing it ignores. (The earlier draft emitted only `selected_projects` — the one field the web never displays — and dropped all three rendered fields; this shape is the corrective.)
- **Language-scoped + parity-checked:** Each language has its own file; EN/DE parity is enforced by tests (§8).

## 5. Implementation

### 5.1 Python: `_extract_overrides` walks the nested tree

**File:** `scripts/render_web_data.py`

`render_web_data()` keeps its existing bridge loop unchanged, then adds a variants loop. The helper compares the **resolved nested trees** of bridge and a variant and pulls the three positioning strings from their real locations:

```python
def _extract_overrides(bridge: dict, variant: dict) -> dict:
    """Return the web-rendered positioning fields that differ from bridge.

    Reads from the nested resolved tree:
      headline       <- personal.headline
      tagline        <- profile.tagline
      lead_paragraph <- profile.paragraphs[0]

    Only includes a key when the variant value differs from bridge.
    `selected_projects` is intentionally excluded — the website renders
    projects grouped by category and never consumes it.
    """
    overrides: dict[str, str] = {}

    b_headline = bridge.get("personal", {}).get("headline")
    v_headline = variant.get("personal", {}).get("headline")
    if v_headline is not None and v_headline != b_headline:
        overrides["headline"] = v_headline

    b_tagline = bridge.get("profile", {}).get("tagline")
    v_tagline = variant.get("profile", {}).get("tagline")
    if v_tagline is not None and v_tagline != b_tagline:
        overrides["tagline"] = v_tagline

    b_paras = bridge.get("profile", {}).get("paragraphs") or []
    v_paras = variant.get("profile", {}).get("paragraphs") or []
    b_lead = b_paras[0] if b_paras else None
    v_lead = v_paras[0] if v_paras else None
    if v_lead is not None and v_lead != b_lead:
        overrides["lead_paragraph"] = v_lead

    return overrides
```

The variants loop loads each target with `load_content(..., target=…)`, resolves langstrings, extracts overrides against the resolved bridge, and writes `content.{lang}.variants.json`. Output is fed through `_to_jsonable` for consistency (the three values are plain strings, so this is a no-op safeguard).

**Contract:** never emit bridge values; never emit `selected_projects`; emit a key only when it genuinely differs.

### 5.2 Vanilla-JS TargetSwitcher (no framework)

**File:** `web/src/components/TargetSwitcher.astro` (new)

The site ships **no** client framework (`web/package.json` has only Astro + Tailwind + sitemap + OG canvas). Adding React/Preact for one widget is unjustified. Astro processes and bundles `<script>` tags in `.astro` components out of the box (already used by `PublicationsChart.astro`), so the switcher is a plain component: markup + a bundled module script that mutates the DOM.

**Data delivery — inline, not fetch.** The parent page imports the variants JSON at build time (mirroring how it already imports `content.{lang}.json`) and passes it to `<TargetSwitcher>`. The component embeds it as a `<script type="application/json">` block. The client script reads that block — **no `fetch`, no public-dir asset, no 404 surface**. A missing/invalid variants file fails the Astro build (import error), which is stronger than a runtime check.

**Component responsibilities:**
- Render a labelled segmented control (`role="group"`, `aria-label`) with three buttons: **Default** (`bridge`), **Comp Bio** (`comp-bio`), **DS · ML** (`ds-ml`), each with `aria-pressed`.
- On load: snapshot the current (bridge) text of every `[data-cv-field]` element so "Default" can restore exactly; read `localStorage["cvTargetPreference"]`; if it names a non-bridge target, apply it.
- On click: if `bridge`, restore snapshots; else read the inlined variants object and set `textContent` on each matching `[data-cv-field]` element for the keys present (`headline`, `tagline`, `lead`). Update `aria-pressed`, persist the choice.
- Pure progressive enhancement: with JS disabled, the page is the fully-rendered bridge CV and the control simply does nothing (or is hidden via a `no-js`/`js` class toggle).

**DOM hooks (added to existing components):**
- `Header.astro` — the headline `<p>` gains `data-cv-field="headline"`.
- `ProfileSection.astro` — the tagline `<p>` gains `data-cv-field="tagline"`; the **first** rendered paragraph gains `data-cv-field="lead"`.

Marking the swap targets with data attributes decouples them from the switcher's own location, so placement is movable without touching the swap logic.

### 5.3 Wiring

**Files:** `web/src/pages/index.astro`, `web/src/pages/de/index.astro`

Each page already imports `content.{lang}.json`. Add a sibling import of `content.{lang}.variants.json` and render the switcher at the **top of the profile section** (right above the tagline, where positioning lives):

```astro
import variants from "../data/content.en.variants.json";
...
<TargetSwitcher variants={variants} lang="en" />
<ProfileSection ... />
```

Placement is a low-risk visual choice (the data-attribute hooks make it movable); top-of-profile is the default and can be tuned later. The headline swap still happens in the sticky header via its `data-cv-field` hook regardless of where the control sits.

## 6. SEO / metadata invariance

The switch mutates only visible body text. It must **not** touch `<head>`:
- `BaseLayout.astro` builds `<title>`, `<meta name="description">`, OG/Twitter title+description, and `<link rel="canonical">` from the **build-time bridge** `personal.headline` / `profile.tagline`. These stay bridge for every visitor and every crawler.
- OG images (`/og/...`) remain bridge. schema.org `Person` (`person.jsonld`) remains bridge. `robots.txt`, sitemap unchanged.

This preserves the single-canonical-identity principle 8b established for machine formats.

## 7. CI / Pages workflow

**File:** `.github/workflows/pages.yml`

The "Render content JSON" step already runs `python -m scripts.render_web_data`, which now also emits the two variants files. Because the pages import those files, a missing/invalid variants file already fails `astro build`. Add one lightweight assertion to the existing "Smoke-check build outputs" step to confirm the switcher actually reached the built HTML:

```bash
# Target switcher present in built pages
grep -q 'data-cv-switcher' web/dist/index.html || (echo "switcher missing in EN" && exit 1)
grep -q 'data-cv-switcher' web/dist/de/index.html || (echo "switcher missing in DE" && exit 1)
```

The sitemap smoke-check stays at **22 URLs** (no new routes). Release artifacts (6 PDFs + machine formats) are unchanged.

## 8. Validation & tests

**`schema/cv.schema.json` / `scripts/validate.py`:** no changes — variant structure and EN/DE parity are already enforced by 8b at the content layer.

**`tests/test_render_web_data_variants.py`** is rewritten to assert *positioning correctness*, not just structure. The original four tests passed against broken output because none checked that the rendered fields were present. The corrected suite asserts, after running the renderer into a `tmp_path`:

1. **Files valid:** both `content.{en,de}.variants.json` parse to dicts keyed exactly `{comp-bio, ds-ml}`.
2. **Required fields present:** every target in every language has all three keys `headline`, `tagline`, `lead_paragraph`, each a non-empty string. *(This is the regression guard the bug slipped through.)*
3. **No bridge leak:** each override value differs from the corresponding bridge value (`personal.headline`, `profile.tagline`, `profile.paragraphs[0]`).
4. **`selected_projects` absent:** no target object contains `selected_projects` (or any key beyond the three).
5. **EN/DE parity:** identical target keys and identical override-key sets across languages.
6. **`_extract_overrides` unit tests:** identical trees → `{}`; a tree differing only in `personal.headline` → `{"headline": …}`; a difference in `paragraphs[1]` only → `{}` (shared paragraph never emitted); top-level `selected_projects` difference → ignored.

Tests render into a temporary directory (not the gitignored working copy) so they are hermetic and CI-safe.

## 9. Non-goals

- **Project reordering / featuring on the web.** Projects stay grouped by category for all targets; `selected_projects` is not consumed by the site. (Possible later showcase task.)
- **Sitemap/SEO per variant.** Bridge is the only indexable identity; no variant URLs, no per-variant OG, no `rel=canonical` juggling.
- **New client framework.** Vanilla JS only.
- **Runtime fetch / served data assets.** Variants are inlined at build time.
- **`<head>` metadata switching.** Meta/OG/canonical stay bridge.
- **Server-side preference storage.** `localStorage` only.

## 10. Success criteria

- ✅ Clicking **Comp Bio** updates the header headline, the profile tagline, and the lead paragraph in place; **DS · ML** likewise; **Default** restores bridge exactly.
- ✅ Second and later switches are instant (data is inlined; no network at any point).
- ✅ Preference persists across reloads (`localStorage`) and auto-applies on return.
- ✅ `content.{en,de}.variants.json` contain exactly the three text keys per target, no bridge values, no `selected_projects`.
- ✅ EN/DE variant key sets match.
- ✅ `<title>`/`<meta>`/OG/canonical/sitemap/schema.org all remain bridge; sitemap still 22 URLs.
- ✅ With JS disabled, the page is the complete bridge CV (graceful degradation).
- ✅ `just validate && just test && just lint` green; `pnpm --dir web build` succeeds; no regressions.

## 11. Resolved decisions

The original spec's "open questions" are settled:
1. **Store/reactivity:** none — vanilla DOM `textContent` swaps against `[data-cv-field]` hooks.
2. **Framework:** vanilla JS; no dependency added.
3. **UI placement:** segmented control at the top of the profile section (movable via data-attribute hooks).
4. **localStorage:** auto-apply the saved preference on load.
5. **JS-disabled visitors:** bridge CV renders fully server-side; the switcher is progressive enhancement.

## 12. Commits / branch

Branch `phase-8c-web-variants` (already created; three commits exist from the initial pass and are corrected in place rather than reverted). Remaining atomic commits:

1. `fix(web-data): extract nested positioning overrides; drop selected_projects` — corrected `_extract_overrides` + rewritten/again-green `tests/test_render_web_data_variants.py` (TDD: failing assertions first).
2. `feat(web): vanilla-JS target switcher island + data-cv-field hooks` — `TargetSwitcher.astro`, `Header.astro`/`ProfileSection.astro` hooks, page wiring.
3. `ci(pages): assert target switcher present in built HTML` — `pages.yml` smoke-check.
4. `docs: mark Phase 8c row in CLAUDE.md phasing table` — final task per repo convention.

A final verification pass (`just validate && just test && just lint`, `pnpm --dir web build`, manual switch in `astro dev`) confirms the feature end-to-end; it commits nothing.
