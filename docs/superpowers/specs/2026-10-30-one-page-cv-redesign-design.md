# One-page CV redesign

**Status:** approved for implementation
**Date:** 2026-10-30

## Context

External consultancy feedback described the résumé—not the website—as too dense and asked for a more classic, overview-first direction. The captain approved one-page Default/bridge, DS–ML, and computational-biology prototypes after comparison against the three supplied Canva references.

This change is a renderer projection only. `content/` remains the canonical source and machine/web outputs are unaffected.

## Approved visual system

All stock variants share one A4 family:

- warm Beige + White composition and a divider-free 62/38 body;
- Blue date/timeline wayfinding;
- Minimalist thin rules and evidence alignment;
- IBM Plex Sans, dark slate-blue text, muted gold accents, pale proof cards, and a sand footer;
- `JL` monogram plus target-specific line art (cross-domain network, layered ML/deployment graph, genomics helix);
- two-line `Production ML & Data Science` focus title;
- ordinary labeled contact text, no icon-only labels;
- no portrait by default, references, dark sidebar, or visible contents strip.

PDF outline bookmarks and ordinary external links remain available. The optional private `--photo` build stays compatible, but all stock outputs are photo-free.

## Projection model

`pdf/projection.py` builds a renderer-local `pdf_layout` after canonical data has been loaded, target-projected, and language-resolved. It may:

- select or group existing roles;
- select canonical bullets and project summaries;
- abbreviate organization display names structurally;
- add renderer-local headings, focus labels, metrics, and date presentation;
- carry appended tailoring bullets through to the grouped display role.

It must not mutate `content/` or fabricate achievements. Default/bridge groups the two industry roles; DS–ML keeps distinct delivery roles; computational biology expands research evidence across genomics, imaging/chromatin, radiation neurobiology, and grounded funding/supervision evidence. Each variant shows two proof cards and a curated skill projection.

German comp-bio may omit lower-priority education detail before typography is reduced. Tailored comp-bio exports retain both proof identities but may omit their card summaries to make room for approved appended experience evidence.

## Rendering and semantic order

The masthead and focus panel span the page. The body is an asymmetric two-column grid:

- left: Experience and Selected Projects;
- right: Profile, four metrics, Skills, Education, Publications, credential, and Languages.

Source-order extraction reads the left column then the right. Geometry-aware extraction may advance between columns by vertical position. Both orders must retain unique, unsplit headings and coherent section sequences.

## Acceptance gates

For all EN/DE stock variants and an EN/DE tailored comp-bio export:

- exactly one A4 page;
- main evidence at 8.5 pt or larger;
- embedded IBM Plex Sans and selectable Unicode text;
- unique section headings, outline bookmarks, and safe external links;
- target keywords and honesty boundaries remain extractable;
- no raster image in stock PDFs and no public PII;
- no forms, JavaScript, rich media, or fragile interactivity;
- tailored profile and appended experience evidence remain visible;
- `just validate`, `just test`, and `just lint` pass.

If content does not fit, tighten the projection before reducing typography.
