#import "attachment.typ": *

#let data = json("../.cache/publications.json")
#let lang = sys.inputs.at("lang", default: "en")
#let author = data.personal.name.given + " " + data.personal.name.family
#let document-label = if lang == "de" { "Publikationsliste" } else { "Publication List" }

#attachment-document(
  data.labels.title,
  author,
  data.personal,
  document-label,
)[
  #attachment-masthead(data.personal, document-label)
  #v(8pt)

  // A quiet proof block gives the list a clear scope before the dense records.
  #block(
    width: 100%,
    fill: attachment-sand,
    radius: 1.2mm,
    inset: (x: 5mm, y: 3.5mm),
    [
      #text(size: 10.2pt, weight: 650, fill: attachment-ink)[#data.labels.title]
      #v(2pt)
      #text(size: attachment-small-size, fill: attachment-muted)[#data.summary]
      #v(2pt)
      #text(size: attachment-label-size, fill: attachment-muted)[#data.labels.provenance]
    ],
  )
  #v(7pt)

  #attachment-section(
    if lang == "de" { "Publikationen" } else { "Publications" },
    destination: "section-publications",
  )

  #for category in data.publications {
    block(
      [
        #text(size: 8.2pt, weight: 700, fill: attachment-gold)[#upper(category.label)]
        #v(3pt)
        #for group in category.groups {
          block(
            breakable: false,
            [
              #text(size: attachment-small-size, weight: 650, fill: attachment-blue)[#group.label]
              #v(2pt)
              #for publication in group.items {
                block(
                  breakable: false,
                  below: 6pt,
                  grid(
                    columns: (13mm, 1fr),
                    column-gutter: 3.5mm,
                    align: (right + top, left + top),
                    text(size: 7.8pt, weight: 650, fill: attachment-blue)[#publication.year],
                    [
                      #attachment-publication-meta(
                        publication.authors,
                        family: data.personal.name.family,
                      )
                      #linebreak()
                      #if publication.doi != none {
                        attachment-link(
                          "https://doi.org/" + publication.doi,
                          publication.title,
                        )
                      } else {
                        publication.title
                      }
                      #if publication.venue != none {
                        linebreak()
                        text(size: attachment-small-size, fill: attachment-muted)[#publication.venue]
                      }
                    ],
                  ),
                )
              }
              #v(1pt)
            ],
          )
        }
      ],
    )
    v(3pt)
  }

  #text(size: attachment-small-size, weight: 650, fill: attachment-gold)[
    #data.labels.links
  ]
  #v(2pt)
  #for (index, item) in data.publication_links.enumerate() {
    if index > 0 { [ · ] }
    attachment-link(item.url, item.label)
  }
]
