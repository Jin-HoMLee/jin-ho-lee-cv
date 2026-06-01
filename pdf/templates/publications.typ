#import "../styles.typ": *

// Publications section. `pubs` is the already-filtered list (depth resolved in
// pdf/build.py); `heading` is the already lang+variant-resolved string;
// `family` is the candidate's surname, used to bold their name in author lists.
#let publications(pubs, heading, family) = {
  if pubs.len() == 0 { return }
  section-heading(heading)

  for (i, p) in pubs.enumerate() {
    // Line 1 — authors · year. The candidate is bolded by matching the author
    // string's surname (text before the comma) against `family`; the BibTeX
    // "others" token renders as italic "et al.". Assumes no coauthor shares the
    // candidate's surname and the surname itself has no comma — true here.
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
    // Separator only when authors were emitted — a bib entry should always
    // have authors, but don't leave a dangling " · year" if one somehow has none.
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

    if i + 1 < pubs.len() { v(space-paragraph) }
  }
}
