# Phase 15 design spec: splice-neoepitope research write-up (warm-editorial pilot)

- **Issue:** #128
- **Date:** 2026-07-20
- **Status:** Approved (brainstorm complete)
- **Branch:** `phase-15-splice-writeup`

## Motivation

Jin-Ho is working toward publishing results from the splice-neoepitope pipeline (a modernized, reproducible reimplementation of a 2015 RNA-Seq cancer-neoepitope pipeline).
He wants to present that work in the "Circuits Thread" style pioneered by Anthropic's interpretability team on `transformer-circuits.pub`: long-form prose with interactive figures the reader can poke at, published on his own site.

The Circuits/Distill self-publish model works because machine-learning accepts self-hosted and preprint venues as legitimate primary research.
Biology and bioinformatics do not: a result that lives only on a personal webpage carries little academic weight, can complicate later peer-reviewed submission (prior-publication concerns), and provides no timestamped citable record for priority.
This spec therefore separates the two acts the Circuits model fuses.
The citable scientific record (bioRxiv preprint, and ideally a journal or conference) is Jin-Ho's own separate action and is out of scope here.
This page is the **amplifier**: a polished, interactive communication piece that presents the *work*, links out to the code and a forthcoming preprint, and stakes no formal claim.

This page also serves a second purpose.
It is the **pilot** for a warm-editorial visual language that a later phase may propagate to the whole CV site.
It is built on reusable design tokens so that adopting the look site-wide, if Jin-Ho likes it live, needs no re-derivation of the palette or type system.

## Goals

- Publish a self-contained, English-only long-form article at `/writeups/splice-neoepitopes/`.
- Tell the method-and-approach story of the pipeline (v1), honestly marked "results in progress."
- Include three purpose-built interactive figures, each with a static, crawler-readable fallback.
- Frame the page explicitly as an amplifier companion to the code and a forthcoming preprint.
- Establish reusable warm-editorial design tokens as a seed for a future site-wide restyle.
- Preserve every existing invariant: `content/` golden snapshots, `web-guard` crawler-readability, the PII guard, and the bilingual no-identical-string test.

## Non-goals (v1)

- The live Mol* 3D TCR-peptide-MHC viewer (deferred to a results-driven v2).
- Actual results (top binders, validation numbers); v1 presents the method, with illustrative figures labelled as such.
- German translation of the article.
- The bioRxiv preprint itself (Jin-Ho's separate action; the page links to it).
- The site-wide warm-editorial restyle (its own future phase; see "Future work").

## Intent: amplifier, not primary publication

The page must never read as the first formal disclosure of novel results.
A visible framing note near the top states that the article is a companion to the code and a forthcoming preprint, and that results are preliminary.
Illustrative or preliminary figures are labelled as illustrative, never presented as findings.

This honors an existing content guardrail.
The splice-neoepitope genomics work is Jin-Ho's *unpublished* line; his peer-reviewed publications are all from a separate super-resolution-microscopy and radiobiology line.
The article must not imply that those publications back the pipeline.

## Architecture

### Placement

- A dedicated route: `web/src/pages/writeups/splice-neoepitopes.astro`.
- The article lives **outside** the `content/*.yaml` source-of-truth model.
  Its prose and bespoke figures are not structured CV data, and forcing them through the YAML schema would fight the core architectural principle.
- The page is linked from the existing splice-pipeline project card on the CV (the relevant `content/projects/` entry; exact id confirmed at plan time).

### No new heavy dependencies

- Authored as a plain `.astro` page composing small figure components under `web/src/components/writeups/`.
- No MDX (not currently installed; not worth adding for a single v1 article).
- No UI framework: interactivity uses the same vanilla `<script>` island pattern already used by the hero tabs, theme toggle, and publication chart.

### Write-ups registry

- A small `web/src/data/writeups.ts` array of entries: `slug`, `title`, `summary`, `date`, `status`, `lang`.
- The route, the CV cross-link, the sitemap inclusion, and the JSON-LD all read from this one source, so a second write-up later is a data addition rather than a refactor.
- This is the one piece of deliberate forward-design; everything else is kept minimal (YAGNI).

### Design tokens (the pilot seed)

- The warm-editorial palette and type are defined as CSS custom properties (paper/surface, ink/text, one warm accent, muted sidenote color; a serif display family, a sans body family, a mono label family).
- Tokens are defined in a scoped, reusable location so a future site-wide phase can adopt them wholesale.
- Light and dark variants are defined in parallel via `prefers-color-scheme` plus the site's existing `data-theme` toggle, matching the site's established theme mechanism.

## Article structure (v1 outline)

1. The question: tumor-specific splice junctions translate into novel peptides (neoepitopes) that are candidate immunotherapy targets; told for a smart non-specialist.
2. The pipeline: the interactive DAG walkthrough (figure 1).
3. Finding tumor-exclusive junctions: the tumor-vs-matched-normal filtering logic (figure 2).
4. From junction to neoepitope: assembly, translation to junction-spanning 9-mers, MHC-I binding prediction (figure 3).
5. Reproducibility: Snakemake, Docker, the "modernized 2015 pipeline" framing.
6. Status and how to follow: honest "results in progress," links to the GitHub repo and the forthcoming preprint.

## Interactive figures

All three are vanilla JS/SVG islands and all three degrade to a meaningful static rendering with JavaScript disabled.

1. **Pipeline explorer** - the Snakemake DAG; clicking a step expands its inputs, outputs, and tooling.
   Anchored on the pipeline's existing `dag.svg`.
   Fallback: the static DAG with all step labels visible.
2. **Junction-origin filter** - shows tumor vs. matched-normal junctions and how the "tumor-exclusive" set is derived as the reader toggles the normal sample.
   Fallback: a static two-set diagram with the exclusive set highlighted.
3. **Binding-score mini-widget** - illustrative 9-mer peptides ranked by MHC-I presentation score, conveying what the prediction step does.
   Data is illustrative and labelled as such.
   Fallback: a static ranked table.

## Bilingual handling

- The article is English-only.
- The German site surface shows the splice project card with an "article available in English" link that points to the English write-up.
- No German article text is authored, so the `tests/test_de_completeness.py` no-identical-EN/DE-string rule is not engaged by this page.

## AEO / SEO

- The route is included in the sitemap (consistent with Phase 14's entity-presence work).
- Inline JSON-LD of type `Article` (or `ScholarlyArticle`) with Jin-Ho as `author` and `isBasedOn` pointing to the GitHub repository.
- Any inline JSON-LD follows the Phase 14 hardening: escape `<` at injection points and reject a literal `</script>` substring.

## Testing

- Extend the `web-guard` / static-facts approach so the article's crawler-critical text is asserted present in the built HTML with JavaScript off: the title, the section headings, and the amplifier disclaimer.
- Snapshot the figure components' static fallbacks.
- Assert the write-up route is present in the built sitemap.
- No `content/` schema or renderer changes, so the existing renderer golden snapshots stay green.
- Every new guard must be proven to bite (a guard never seen to fail is not a guard): each new assertion is demonstrated failing before the feature is complete.

## Future work (out of scope, tracked separately)

- **Site-wide warm-editorial restyle:** its own future phase with its own brainstorm, spec, and plan, adopting the design tokens this page establishes.
  To be filed as a tracking issue.
- **Results v2:** replace illustrative figures with real findings once trustworthy; add the live Mol* 3D viewer as a results-driven centerpiece.
- **German translation** of the article, if desired.

## Documentation

The implementation plan's final task updates the Phasing table in `CLAUDE.md` (adding the Phase 15 row) and any changed convention, per the repo's standing rule that a merged phase with no row there is a doc bug.
