#import "../styles.typ": *

#let _publication-links(data) = {
  text(size: size-small, fill: muted)[
    #data.publications_pointer
    #h(3pt)
    #for (i, item) in data.publication_links.enumerate() {
      if i > 0 { [ · ] }
      link(item.url)[#text(fill: accent)[#item.label]]
    }
  ]
}

// Application-PDF publication projection. Computational Biology shows three
// representative research records; other targets show only the derived total.
// The complete canonical bibliography remains available through all three links.
#let publications(data) = {
  section-heading(data.publications_heading, "section-publications")

  [#data.publications_summary]
  v(space-paragraph)

  if data.publications_mode == "selected" {
    let family = data.personal.name.family
    for (i, p) in data.publications.enumerate() {
      block(breakable: false, {
        for (j, author) in p.authors.enumerate() {
          if j > 0 { [, ] }
          if author == "others" {
            emph[et al.]
          } else if author.starts-with(family + ",") {
            text(weight: 600)[#author]
          } else {
            author
          }
        }
        if p.authors.len() > 0 { [ · ] }
        [#str(p.year)]
        linebreak()
        if p.doi != none {
          link("https://doi.org/" + p.doi)[#text(fill: accent)[#p.title]]
        } else {
          p.title
        }
        if p.venue != none {
          [ · ]
          text(size: size-small, fill: muted)[#p.venue]
        }
      })
      if i + 1 < data.publications.len() { v(space-paragraph) }
    }
    v(space-paragraph)
  }

  _publication-links(data)
}
