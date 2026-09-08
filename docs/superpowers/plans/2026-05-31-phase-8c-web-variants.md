# Plan: Phase 8c — Web Variants (client-side target switcher)

**Date:** 2026-05-31  
**Owner:** Jin-Ho Lee  
**Design spec:** [`2026-05-31-phase-8c-web-variants-design.md`](../specs/2026-05-31-phase-8c-web-variants-design.md)

## Status

Phase 8c's client-side switcher is implemented. The complementary-view follow-up kept
`content/skills.yaml` as the sole Skills source of truth while adding web-only projections:

- `load_content(..., web_projection=True)` resolves concise bridge and target-specific Skills
  trees from category-local `omit`, `omit_groups`, and `group_items` operations.
- Non-web loaders retain the full canonical Skills baseline, including for non-bridge targets.
- `render_web_data.py` emits resolved web target overrides. These include the four text fields,
  target Skills trees, and an optional derived `hero_stack` when it differs from bridge.
- The page passes a text-only projection plus `hero_stack` to `TargetSwitcher` and a skills-only
  projection to `SkillsSidebar`; `CodeHero` follows the same target event for its visible stack.

The detailed current contract lives in the [design spec](../specs/2026-05-31-phase-8c-web-variants-design.md).
The implementation below is recorded as completed scope rather than a pending task sequence.

## Implemented scope

### Data and validation

- `scripts/content_loader.py` owns the Skills projection resolver. Projection instructions are
  stripped before any renderer receives the resolved tree.
- `scripts/render_web_data.py` compares resolved bridge and target trees, emits only differences,
  and derives the short CodeHero stack from the existing Skills data.
- `schema/cv.schema.json` allows only `bridge`, `comp-bio`, and `ds-ml` category variants and
  only the `omit`, `omit_groups`, and `group_items` operations.
- `scripts/validate.py` rejects duplicate base group labels and category-local references to
  unknown groups.
- Targeted non-web outputs continue to use the full canonical Skills baseline; the web renderer
  is the only caller that enables the concise projection.

### Web behavior

- `web/src/components/TargetSwitcher.astro` is a dependency-free vanilla-JS progressive
  enhancement. It inlines its payload with Astro `define:vars`, swaps headline/tagline/profile
  text and publication depth, persists `cvTargetPreference`, and dispatches `cv-target-change`.
- `web/src/components/SkillsSidebar.astro` swaps complete pre-resolved target trees and falls
  back to canonical skills when no target override exists.
- `web/src/components/CodeHero.astro` updates headline, tagline, and the derived stack from the
  target-change event.
- `web/src/pages/index.astro` and `web/src/pages/de/index.astro` keep the bridge content
  server-rendered and split the variants data into the two component-specific projections.
- SEO metadata, OG images, JSON-LD, canonical URLs, and the sitemap remain bridge-canonical;
  target selection adds no routes. The Pages workflow checks the switcher, field hooks, inlined
  variant text, and metadata invariance.

## Verification record

The focused regression coverage is in:

- `tests/test_variants.py` — resolver, validation, non-web baseline, and target projection cases.
- `tests/test_content_loader.py` — full non-web Skills baseline and concise web bridge checks.
- `tests/test_render_web_data_variants.py` — resolved web payload, complementary trees, hero
  stack derivation, and EN/DE parity.
- `tests/test_de_completeness.py` — German label parity for the relocated Skills group.

The normal repository checks are `just validate`, `just test`, `just lint`, and
`pnpm --dir web check` / `pnpm --dir web build`. The Pages CI job additionally runs the static
web guard and deployment smoke checks.

## Architectural invariants

- `content/skills.yaml` is the canonical Skills baseline; generated JSON and snapshots are not
  hand-edited.
- Skills projections are web-only. PDFs, JSON Resume, plain text, llms.txt, and twin artifacts
  retain the comprehensive baseline.
- The bridge remains the no-JavaScript and SEO-canonical web view.
- There is no runtime variant fetch, client framework, variant route, or second Skills source.

## Final documentation task

Before recording this follow-up as merged, update `CLAUDE.md` (the `AGENTS.md` owner) only if the
Phase 8c status or a project-wide invariant changes. Keep the phase row concise and point detailed
Skills-projection behavior to this design spec rather than duplicating it.
