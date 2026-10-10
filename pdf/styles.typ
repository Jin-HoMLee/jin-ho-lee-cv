// Design tokens — colors, fonts, sizes, spacing.
// Spec: docs/superpowers/specs/2026-05-21-phase-1-pdf-typst-design.md §4.

#let accent = rgb("#1f3a68")
#let sidebar-bg = rgb("#f4f7fb")
#let muted = rgb("#6b6b6b")
#let body-color = rgb("#222222")

#let font-family = "IBM Plex Sans"

// The computational-biology variant carries a denser first-page information
// block (profile + skills) and needs the complete Experience section to finish
// before the page break, so Selected Projects opens page two. A modest,
// variant-scoped compaction of leading and block spacing buys that room while
// keeping the type hierarchy and every line of content unchanged. Other
// variants keep the original, roomier tokens.
#let pdf-target = sys.inputs.at("target", default: "bridge")
#let pdf-lang = sys.inputs.at("lang", default: "en")
#let compact-layout = pdf-target == "comp-bio"

// German body text runs longer than English at identical token values, so the
// German comp-bio variant needs slightly tighter bullet spacing to keep the
// complete Experience section on page one. Scoped to de/comp-bio so every
// other variant (including en/comp-bio) keeps its existing metrics.
#let compact-de = compact-layout and pdf-lang == "de"

#let size-body = 9pt
#let size-small = 7.5pt
#let size-section = 10pt
#let size-name = 18pt
#let size-headline = 10pt

#let space-section = if compact-layout { 3pt } else { 5pt }
#let space-paragraph = if compact-layout { 1pt } else { 2pt }
#let space-bullet = if compact-de { 0pt } else if compact-layout { 1pt } else { 2pt }
#let base-leading = if compact-layout { 0.50em } else { 0.56em }

#let sidebar-ratio = (1fr, 0.5fr)  // main : sidebar  ≈ 66 : 34
#let column-gutter = 12pt

#let page-margin = 14mm

// Semantic section heading. Typst uses these heading nodes to generate the PDF
// outline; visible tracking is deliberately zero so ATS extractors see whole words.
#let section-heading(title, destination) = [
  #v(space-section)
  #heading(level: 1, outlined: true, bookmarked: true)[#text(
    size: size-section,
    weight: 600,
    fill: accent,
  )[#upper(title)]]#label(destination)
  #v(space-paragraph)
]

// Inline project reference. Its visible text is complete without the link;
// the annotation only adds a route to the corresponding web detail page.
#let ref-chip(id, url: none) = {
  let chip = box(
    fill: accent.lighten(85%),
    inset: (x: 3pt, y: 1pt),
    outset: (y: 1pt),
    radius: 2pt,
  )[
    #text(size: 7pt, weight: 600, fill: accent)[#upper(id)]
  ]
  if url == none { chip } else { link(url, chip) }
}
