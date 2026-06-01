# Issue #43 — PDF publications section (DOI links · first-author bold · variant-aware depth)

**Date:** 2026-06-01
**Issue:** [#43](https://github.com/Jin-HoMLee/jin-ho-lee-cv/issues/43) — `feat(pdf): add publications section (DOI links, first-author bold, variant-aware depth)`
**Size:** M · **Type:** feature (pdf)
**Depends on:** #41 (clean publication titles) — merged.

## Problem

The Typst PDF is the only renderer with **no publications** — there is no `pdf/templates/publications.typ`. For an academia→industry bioinformatician with 15 publications, and DFG hiring norms that favour a DOI-bearing Publikationsliste, this is the biggest substance gap. The data is already bridged into `pdf/.cache/data.json` as a `publications` array (15 entries: 6 first · 3 shared · 6 middle author; 11 with DOI; 14 research + 1 applied), so this is a renderer-only addition: a new template plus a small data-prep step.

## Confirmed decisions

- **Selected subset = first + shared (9 pubs).** "Shared" = candidate is in the first-author group (co-led), which is still first-author signalling and includes DOI-bearing journal papers. Matches the website's first-author bolding. `comp-bio` shows all 15.
- **Entry layout = title is the DOI link (compact, ~4 lines/entry).** Protects the 2-page budget; mirrors the al-folio reference model; ATS-safe because the title text remains real text. No-DOI entries render the title as plain text.

## Architecture — depth is a PDF *rendering* choice, resolved in Python

The decisive constraint: `bridge` means **all 15** for the web and plain-text renderers, but **selected 9** for the PDF. Publication depth is therefore **not** a content-variant concern and must **not** live in the shared `scripts/content_loader.py` (that would wrongly filter web/plain-text too). It belongs in the PDF build path alone.

- New pure helper **`select_publications(pubs, target) → (list, is_selected)`** in `pdf/build.py`:
  - `comp-bio` → `(all 15, False)`
  - `bridge`, `ds-ml` → `([p for p in pubs if p.authorship in ("first", "shared")], True)` (9 entries)
  - Order is preserved from `bib_loader` (research→applied, then year-descending) — no re-sorting, no type grouping. Matches `render_text.py`.
- `pdf/build.py` calls the helper, then injects into the serialized data dict:
  - `data["publications"]` = the filtered list
  - `data["publications_heading"]` = the already lang+variant-resolved heading string (`labels.sections.publications_selected` when `is_selected`, else `labels.sections.publications`)
- **Typst stays a dumb renderer** — it prints `data.publications_heading` and iterates `data.publications`. No `target`/variant logic crosses into Typst (which today only receives `lang`).

## Components / files

| File | Change |
| --- | --- |
| `pdf/build.py` | Add `select_publications()` helper; call it in the data-prep step; inject `publications` (filtered) + `publications_heading` (resolved string) into the dict written to `pdf/.cache/data.json`. |
| `pdf/templates/publications.typ` | **New.** `#let publications(pubs, heading, family)` — renders the section. |
| `pdf/templates/cv.typ` | Add `#import "publications.typ": publications` (with the other section imports) and `publications(data.publications, data.publications_heading, data.personal.name.family)` in the main-column block **between `selected_projects(...)` (cv.typ:55) and `awards(...)` (cv.typ:56)**. |
| `content/labels.yaml` | Add to `sections`: `publications: { en: "Publications", de: "Publikationen" }` and `publications_selected: { en: "Publications (selected)", de: "Publikationen (ausgewählte)" }`. |

## Data flow

```text
publications.bib → bib_loader.load_publications() [clean titles via #41, sorted]
  → content_loader.load_content() [full list, unchanged — web/text consume this]
  → pdf/build.py: select_publications(pubs, target) → (filtered, is_selected)
       inject data["publications"]=filtered, data["publications_heading"]=resolved heading
  → pdf/.cache/data.json
  → cv.typ → publications(data.publications, data.publications_heading, family)
```

## Per-entry rendering (layout A)

Single-column flow in the main column (paginates to page 2 — already how the main column behaves). Each entry, using existing `styles.typ` helpers (`section-heading`, colours, spacing):

- **Line 1 — authors · year.** Authors comma-separated; the candidate (any author string starting with `family + ","`, i.e. `"Lee,"`) is rendered `weight: 600` (bold); a literal `"others"` token renders as italic *et al.* The year follows after a `·` separator.
- **Line 2 — title.** Rendered as `link("https://doi.org/" + doi)[title]` in the **accent colour** when `doi != none`, to give the DOI link a visible print affordance (note: the header's links are currently un-coloured plain text; the publications section deliberately colours its DOI links). Plain body-colour text when `doi == none`.
- **Line 3 — venue.** Muted colour, smaller size, when `venue != none`.
- Inter-entry spacing follows the awards/selected_projects pattern (`v(space-paragraph)`), with the trailing gap omitted after the last entry.

Section heading: `section-heading(heading)` (the helper upper-cases it). Full list → `PUBLICATIONS` / `PUBLIKATIONEN`; selected subset → `PUBLICATIONS (SELECTED)` / `PUBLIKATIONEN (AUSGEWÄHLTE)`. The noun leads in both variants, so `PUBLIKATIONEN` sits in the same position whether full or subset.

## Edge cases

- **No DOI** (4 entries) → title is plain text, no link (doubles as a subtle "no DOI" signal).
- **Empty list** → render nothing (no heading, no whitespace). Defensive only; never triggers given the subset is ≥9.
- **Long author lists** (max 8, e.g. Pagačová et al.) → wrap naturally; the candidate stays bold and findable. No truncation (YAGNI).
- **`"others"` token** → italic *et al.* rather than a literal author name.

## Localization

EN + DE via the two new `labels.sections` keys. Publication titles/authors/venues are language-agnostic Unicode straight from BibTeX (no `{en,de}` variants), so only the heading is translated. Both languages keep the noun leading with a parenthetical qualifier — full: `Publications` / `Publikationen`; subset: `Publications (selected)` / `Publikationen (ausgewählte)` — so the leading word is stable across the full/subset variants.

## Testing

1. **Unit (TDD) — `select_publications(pubs, target)`:** `comp-bio` → 15 entries, `is_selected=False`; `bridge` and `ds-ml` → 9 entries, `is_selected=True`; the 9 are exactly the `first`+`shared` entries; bib order is preserved; a known middle-author entry (the Pagačová paper) is absent from the subset and present in `comp-bio`.
2. **Integration — build wiring:** run `python -m pdf.build` for representative `(lang, target)` combos; assert the generated `pdf/.cache/data.json` has the expected `publications` count and the correct `publications_heading` per target, and that the emitted PDF is valid (`%PDF-` magic + size). This proves end-to-end wiring without a PDF text-extraction dependency, and reuses the existing `@skipif(not _typst_available())` pattern from `tests/test_build_public.py`.
3. **Best-effort content assertion:** when a PDF text-extraction path is available in the environment, additionally assert the heading text appears and that a middle-author-only title is absent from a `bridge`/`ds-ml` build — otherwise skipped (the unit + integration tests already prove the filter).

All 6 CI `build-pdf` matrix combos (`en|de` × `bridge|comp-bio|ds-ml`) must stay green; `just validate && just test && just lint` green before merge.

## Out of scope

- No publication rendering changes to the web, JSON Resume, JSON-LD, or plain-text renderers (they keep showing all 15).
- No re-sorting or type-grouping of publications (bib order is preserved).
- No author-list truncation / "et al." capping beyond rendering the existing `"others"` token.
- Variant-depth refinements beyond first+shared / full overlap with #46 and are deferred there.
