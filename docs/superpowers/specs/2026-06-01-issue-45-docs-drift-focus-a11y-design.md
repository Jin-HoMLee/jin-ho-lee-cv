# Issue #45 — CLAUDE.md drift fix + global `:focus-visible` + keyboard-accessible chart

**Issue:** [#45](https://github.com/Jin-HoMLee/jin-ho-lee-cv/issues/45) (`documentation`, size: S)

**Goal:** Two doc-accuracy fixes in `CLAUDE.md` plus two web a11y additions — a site-wide keyboard focus ring and keyboard operation of the publication-chart pie slices.

## Why

Three independent, low-risk fixes surfaced by the 2026-05-31 repo audit:

1. `CLAUDE.md` intro says "Eight phases (0–8)" but the Phasing table runs through Phase 9 — stale.
2. "Files to read before any phase" stops at Phase 5, so the Phase 6–9 architecture is undiscoverable from the doc.
3. `web/src/styles/global.css` has **no site-wide `:focus-visible` rule** — keyboard focus is invisible on the header, theme/language toggles, project cards, etc. The only focus style in the tree is the scoped `CodeHero .cv-tab:focus-visible`.
4. The publication-chart pie slices are mouse/touch-only; keyboard users cannot reach the per-slice tooltip (the percentage). (Issue's "optional" item — **in scope** per user decision 2026-06-01.)

All four are additive. No `content/*.yaml` touched — renderer-isolation principle intact.

## Scope & design

### Part A — `CLAUDE.md` doc drift (pure docs)

- **A1.** Intro line `"Eight phases (0–8), sequential."` → `"Ten phases (0–9), sequential."` (phases 0,1,2a,2b,3,4,5,6,7,8a,8b,8c,9 → ten top-level numbers 0–9). The `## Phasing` table already runs through Phase 9; no table edit needed.
- **A2.** Under "## Files to read before any phase", append the six specs that exist but aren't listed (all verified present in `docs/superpowers/specs/`):
  - `docs/superpowers/specs/2026-05-28-phase-6-seo-analytics-design.md`
  - `docs/superpowers/specs/2026-05-29-phase-7-content-audit-design.md`
  - `docs/superpowers/specs/2026-05-30-phase-8a-sharpen-positioning-design.md`
  - `docs/superpowers/specs/2026-05-30-phase-8b-targeted-variants-design.md`
  - `docs/superpowers/specs/2026-05-31-phase-8c-web-variants-design.md`
  - `docs/superpowers/specs/2026-05-31-phase-9-web-redesign-design.md`

  Each line gets a one-clause description matching the existing list style.

### Part B — Global `:focus-visible` ring

Add to `web/src/styles/global.css` (after the existing reusable-component blocks, e.g. near `.eyebrow`):

```css
/* Site-wide keyboard focus ring. Mirrors CodeHero .cv-tab:focus-visible.
   :where() keeps specificity 0 so components can still override. */
:where(button, a, [role="button"]):focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}
```

- Values mirror the existing `.cv-tab:focus-visible` (`2px solid var(--accent)`, `outline-offset: 2px`) for visual consistency in both themes (`--accent` is theme-aware).
- `:focus-visible` (not `:focus`) → ring shows for keyboard/programmatic focus, not mouse click.
- `:where()` → zero specificity; the existing `.cv-tab` rule (and any future component rule) still wins. Same values, so no visible conflict regardless.
- Because Part C gives each slice `role="button"`, this rule also provides the slice focus ring.

### Part C — Keyboard-operable pie slices (`PublicationsChart.astro`)

**Markup:** each `<path>` gains `tabindex="0"`, `role="button"`, and `aria-label={`${arc.label}: ${arc.count} (${arc.pct}%)`}`.
- Add a `pct` field to the `computeArcs` return (currently the percentage is only computed inline for `data-pct`); reuse it for both `data-pct` and the `aria-label` so the number is single-sourced.
- The `aria-label` makes the full datum (label + count + percentage) available to screen readers on focus, independent of the visual tooltip.

**Behavior** (extend the existing `<script>`):
- **focus** → position + show tooltip for that path; **blur** → hide. (Keyboard users see the datum as they land on each slice — better than tabbing through silent slices.)
- **keydown Enter/Space** → toggle the tooltip (Space: `preventDefault()` to stop page scroll). Satisfies the issue's literal "Enter/Space toggling".
- **Positioning fix:** `show()` currently reads pointer `clientX/clientY`, absent for keyboard focus. When the triggering event has no usable pointer coords (focus/keydown), position the tooltip at the focused path's `getBoundingClientRect()` center, relative to the figure's rect. The existing mouse/touch path (mouseenter/mousemove/touchstart) is unchanged.

**SVG outline contingency:** `outline` rendering on SVG sub-elements is reliable in current Chromium/Firefox/Safari, so the Part-B global rule should light the focused slice. If the Playwright check shows it does *not* render on the `<path>` in Chromium, add a scoped fallback in `PublicationsChart.astro`:
```css
svg path[role="button"]:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
```
(or a `stroke`-based indicator if `outline` truly fails). Decision deferred to verification; default is "rely on the global rule".

## Out of scope

- No new content, no renderer changes beyond the chart component, no CI changes.
- No reduced-motion handling needed (tooltip has no animation).
- Not adding a permanent web test suite to CI (would be new infra — disproportionate for size-S). Web verification is a local Playwright run.

## Testing / verification

| Part | How verified |
|---|---|
| A1 phase count | `grep` confirms "Ten phases (0–9)" present and "Eight phases" gone. |
| A2 spec links | `grep` confirms all six new spec paths listed; each path resolves to an existing file. |
| B focus ring | Local Playwright (Chromium, `web-build` output): Tab to a header link/button, assert computed `outline-width` ≈ `2px` / `outline-color` = accent. |
| C markup | Built DOM has `role="button"`, `tabindex="0"`, non-empty `aria-label` on each chart `<path>`. |
| C behavior | Playwright: focus a slice → tooltip visible with correct text; press Enter → toggles; Tab away → hidden. Slice shows focus ring (or fallback). |

`just validate && just test && just lint` stay green (no Python touched, but run them as a regression gate). `just web-build` must succeed (TypeScript/Astro compile).

## Commit plan (atomic)

1. `docs: #45 fix CLAUDE.md phase count + add Phase 6–9 spec links` (Part A)
2. `feat(web): #45 site-wide :focus-visible keyboard focus ring` (Part B)
3. `feat(web): #45 keyboard-operable publication chart slices` (Part C)

(Spec doc committed separately first.)
