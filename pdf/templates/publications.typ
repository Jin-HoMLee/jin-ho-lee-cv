#import "../styles.typ": *

// Publications section. Reads everything from the prepared `data` object
// (mirrors `sidebar(data, …)`). `data.publications_mode` is "full" (comp-bio →
// verbatim per-paper list) or "aggregate" (bridge / ds-ml → one-line summary +
// ORCID pointer). Depth is resolved in pdf/build.py.
#let publications(data) = {
  section-heading(data.publications_heading)

  if data.publications_mode == "aggregate" {
    // Derived summary sentence (counts + span filled in Python) + ORCID pointer.
    [#data.publications_summary]
    linebreak()
    let orcid = data.personal.links.orcid
    let shown = orcid.replace("https://", "").replace("http://", "")
    text(size: size-small, fill: muted)[#data.publications_pointer #link(orcid)[#text(fill: accent)[#shown]]]
  } else {
    // Full verbatim list (comp-bio) — the #43 per-paper rendering.
    let family = data.personal.name.family
    for (i, p) in data.publications.enumerate() {
      // Line 1 — authors · year. The candidate's surname (text before the comma)
      // is bolded; the BibTeX "others" token renders as italic "et al.".
      for (j, a) in p.authors.enumerate() {
        if j > 0 { ", " }
        if a == "others" {
          emph[et al.]
        } else if a.starts-with(family + ",") {
          text(weight: 600)[#a]
        } else {
          a
        }
      }
      if p.authors.len() > 0 { [ · ] }
      [#str(p.year)]
      linebreak()

      // Line 2 — title. DOI link in accent colour when present; plain otherwise.
      if p.doi != none {
        link("https://doi.org/" + p.doi)[#text(fill: accent)[#p.title]]
      } else {
        p.title
      }

      // Line 3 — venue (muted, small), when present.
      if p.venue != none {
        linebreak()
        text(size: size-small, fill: muted)[#p.venue]
      }

      if i + 1 < data.publications.len() { v(space-paragraph) }
    }
  }
}
