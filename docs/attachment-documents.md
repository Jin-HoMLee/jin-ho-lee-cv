# Attachment documents

Candidate-authored PDFs use the same **Editorial Continuity** language as the
approved CV without copying its dense one-page projection. The reusable Typst
primitives live in [`pdf/templates/attachment.typ`](../pdf/templates/attachment.typ).

## Shared primitives

- **Masthead:** JHL monogram, name, bilingual headline, labeled contact text,
  optional document label/date, and a quiet divider.
- **Typography:** IBM Plex Sans; slate-blue ink; blue wayfinding; muted gold
  rules and labels; muted metadata.
- **Surfaces:** warm sand for scope/provenance blocks and the footer; pale blue
  for recipient or supporting-information blocks; thin rules rather than heavy
  panels.
- **Furniture:** A4 page, page-number footer, PDF bookmarks for semantic
  sections, selectable Unicode text, and ordinary external links.

The CV remains its own settled renderer and geometry. The attachment system is
intentionally looser: letters preserve readable paragraph rhythm, while the
publication list uses a year rail and grouped records.

## Variants

- `cover-letter.typ` is driven by the existing `scripts.cover_letter_core`
  contract. It preserves recipient data, subject, rich-text body blocks,
  optional signature, English/German output, phone opt-in, and the hard rule
  that a sender street address never enters the letterhead.
- `publication-list.typ` is driven by `scripts.render_publications` from the
  complete `content/publications.bib` inventory. It separates research and
  applied/off-domain records, links DOI titles, bolds the candidate surname,
  and includes ORCID, Google Scholar, and Web CV links.

Build the reusable list with:

```text
just publication-list en
just publication-list de
# or both:
just build-publications
```

The default outputs are `dist/publications-en.pdf` and
`dist/publications-de.pdf`. For an application handoff, render with
`python3 -m scripts.render_publications --lang <en|de> --output <path>` and
place the resulting file at `artifacts/publication-list-<lang>.pdf`. The CV
export recipe detects that optional canonical path and records its SHA-256 in
`attachment-manifest.yaml`; it does not create, alter, or submit application
artifacts.

## Provenance and validation

The publication list's sand scope block states that it is generated from the
version-controlled bibliography. The renderer is public-only and never reads
`content.private/`. Both variants use the same data preparation path, so
English/German differences are limited to resolved labels and content. PDF
checks should cover A4/page count, embedded IBM Plex Sans, text extraction,
DOI/web links, and absence of private values. Rendered pages should be
inspected at full-page and print scale after intentional style changes.
