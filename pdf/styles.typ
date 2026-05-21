// Design tokens — colors, fonts, sizes, spacing.
// Spec: docs/superpowers/specs/2026-05-21-phase-1-pdf-typst-design.md §4.

#let accent = rgb("#1f3a68")
#let sidebar-bg = rgb("#f4f7fb")
#let muted = rgb("#6b6b6b")
#let body-color = rgb("#222222")

#let font-family = "IBM Plex Sans"

#let size-body = 9.5pt
#let size-small = 8pt
#let size-section = 10pt
#let size-name = 18pt
#let size-headline = 10pt

#let space-section = 6pt
#let space-paragraph = 3pt

#let sidebar-ratio = (1fr, 0.5fr)  // main : sidebar  ≈ 66 : 34
#let column-gutter = 12pt

#let page-margin = 14mm

// Section heading: uppercase (upper()), letterspaced, accent color.
#let section-heading(title) = {
  v(space-section)
  text(
    size: size-section,
    weight: 600,
    fill: accent,
    tracking: 1pt,
  )[#upper(title)]
  v(space-paragraph)
}

// Inline reference chip e.g. "L1" appended to an experience bullet.
#let ref-chip(id) = box(
  fill: accent.lighten(85%),
  inset: (x: 3pt, y: 1pt),
  outset: (y: 1pt),
  radius: 2pt,
)[
  #text(size: 7pt, weight: 600, fill: accent, tracking: 0.5pt)[#upper(id)]
]
