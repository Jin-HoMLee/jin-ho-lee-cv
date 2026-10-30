#let data = json("../.cache/data.json")
#let lang = sys.inputs.at("lang", default: "en")
#let has-photo = sys.inputs.at("has-photo", default: "0") == "1"
#let tailored = sys.inputs.at("tailored", default: "0") == "1"
#let layout = data.pdf_layout

#let ink = rgb("#25384a")
#let blue = rgb("#55718c")
#let gold = rgb("#a17a45")
#let sand = rgb("#f6f0e5")
#let pale-blue = rgb("#edf2f5")
#let muted = rgb("#68747d")
#let rule = rgb("#d9d2c6")

#set document(
  title: data.personal.name.given + " " + data.personal.name.family + " — CV",
  author: data.personal.name.given + " " + data.personal.name.family,
)
#set page(
  paper: "a4",
  margin: (top: 10mm, bottom: 13mm, x: 13mm),
  footer: context {
    block(
      width: 100%,
      fill: sand,
      inset: (x: 4mm, y: 2mm),
      grid(
        columns: (1fr, auto),
        align: (left, right),
        text(size: 6.8pt, weight: 600, fill: ink)[JIN-HO LEE · #upper(layout.target)],
        text(size: 6.8pt, fill: muted)[jinholee.is-a.dev · #counter(page).display()],
      ),
    )
  },
)
#set text(font: "IBM Plex Sans", size: 9pt, fill: ink)
#set par(leading: 0.52em, justify: false)
#set heading(numbering: none)
#show heading.where(level: 1): item => item.body

#let section-title(title, destination) = [
  #heading(level: 1, outlined: true, bookmarked: true)[
    #text(size: 9.2pt, weight: 700, fill: ink)[#upper(title)]
  ]#label(destination)
  #v(1.5pt)
  #line(length: 100%, stroke: 0.7pt + gold)
  #v(4pt)
]

#let contact-line(label, value, url: none) = {
  let value = text(fill: muted)[#value]
  let row = grid(
    columns: (11mm, 1fr),
    column-gutter: 2mm,
    text(weight: 600, fill: ink)[#label],
    value,
  )
  if url == none { row } else { link(url, row) }
}

#let public-contact = grid(
  columns: (1fr,),
  row-gutter: 2.5pt,
  text(size: 7.4pt)[#contact-line("Email", data.personal.email, url: "mailto:" + data.personal.email)],
  text(size: 7.4pt)[#contact-line("Based", data.personal.location.city + ", " + data.personal.location.country)],
  text(size: 7.4pt)[#contact-line("Web", "jinholee.is-a.dev", url: data.personal.links.website)],
  text(size: 7.4pt)[
    #if "phone" in data.personal {
      contact-line("Phone", data.personal.phone)
    } else {
      contact-line("", [
        #link(data.personal.links.linkedin)[LinkedIn]
        #text(fill: muted)[ · ]
        #link(data.personal.links.github)[GitHub]
      ])
    }
  ],
)

#grid(
  columns: (1fr, 65mm),
  column-gutter: 8mm,
  align: (left, bottom),
  [
    #grid(
      columns: (14mm, 1fr),
      column-gutter: 4mm,
      align: (left, center),
      if has-photo {
        box(clip: true, width: 14mm, height: 14mm, radius: 1.2mm)[
          #image("/assets/photo.jpg", width: 14mm, height: 14mm, fit: "cover")
        ]
      } else {
        box(
          width: 14mm,
          height: 14mm,
          fill: sand,
          stroke: 0.7pt + gold,
          radius: 1.2mm,
          align(center + horizon, text(size: 10.5pt, weight: 700, fill: ink)[#layout.monogram]),
        )
      },
      [
        #text(size: 20pt, weight: 700, fill: ink)[#data.personal.name.given #data.personal.name.family]
        #linebreak()
        #text(size: 9pt, weight: 500, fill: blue)[#data.personal.headline]
      ],
    )
  ],
  public-contact,
)

#v(4.5mm)
#block(
  width: 100%,
  fill: sand,
  radius: 1.5mm,
  inset: (x: 6mm, y: 4mm),
  grid(
    columns: (1fr, 55mm),
    column-gutter: 7mm,
    align: (left, center),
    [
      #text(size: 6.8pt, weight: 700, fill: gold)[FOCUS]
      #v(2pt)
      #text(size: 16pt, weight: 650, fill: ink)[
        #for (index, line) in layout.focus.title_lines.enumerate() {
          if index > 0 { linebreak() }
          line
        }
      ]
      #v(2pt)
      #text(size: 8pt, fill: muted)[#layout.focus.subtitle]
    ],
    image("../assets/focus-" + layout.focus.art + ".svg", width: 52mm, height: 25mm, fit: "contain"),
  ),
)

#v(4.5mm)

#let year-span(period) = {
  let start = period.start.slice(0, 4)
  let finish = if "end" in period and period.end != none {
    period.end.slice(0, 4)
  } else if lang == "de" {
    "heute"
  } else {
    "now"
  }
  if start == finish { start } else { start + "–" + finish }
}

#let experience-entry(entry) = block(
  breakable: false,
  below: 6.5pt,
  grid(
    columns: (14mm, 1fr),
    column-gutter: 3.5mm,
    align: (right, top),
    text(size: 7.5pt, weight: 600, fill: blue)[#year-span(entry.period)],
    block(
      stroke: (left: 0.8pt + blue),
      inset: (left: 4mm),
      [
        #text(size: 9.5pt, weight: 650, fill: ink)[#entry.role]
        #linebreak()
        #text(size: 7.8pt, weight: 600, fill: gold)[#entry.org]
        #v(2.2pt)
        #for bullet in entry.bullets {
          grid(
            columns: (5pt, 1fr),
            column-gutter: 2.5pt,
            text(fill: gold)[•],
            text(size: 8.5pt, fill: ink)[#bullet],
          )
          v(1.8pt)
        }
      ],
    ),
  ),
)

#let proof-card(proof) = block(
  height: if tailored and layout.target == "comp-bio" { 20mm } else if layout.target == "comp-bio" { 56mm } else if layout.target == "bridge" { 41mm } else { 36mm },
  fill: pale-blue,
  radius: 1.2mm,
  inset: 3.5mm,
  [
    #grid(
      columns: (1fr, auto),
      column-gutter: 2mm,
      link(proof.url)[#text(size: 8.7pt, weight: 650, fill: ink)[#proof.title]],
      if proof.links.len() > 1 {
        text(size: 6.3pt, fill: muted)[
          #for (index, item) in proof.links.enumerate() {
            if index > 0 { [ · ] }
            link(item.url)[#item.id]
          }
        ]
      },
    )
    #if not (tailored and layout.target == "comp-bio") {
      v(2pt)
      text(size: 7.8pt, fill: muted)[#proof.text]
    }
  ],
)

#let metric(metric) = block(
  fill: sand,
  radius: 1mm,
  inset: (x: 2.5mm, y: 2mm),
  [
    #text(size: 10.8pt, weight: 700, fill: ink)[#metric.value]
    #linebreak()
    #text(size: 6.6pt, fill: muted)[#metric.label]
  ],
)

#let compact-section(title, destination, body) = {
  section-title(title, destination)
  body
  v(1pt)
}

#grid(
  columns: (1.62fr, 1fr),
  column-gutter: 8mm,
  align: (left, top),
  [
    #section-title(data.labels.sections.experience, "section-experience")
    #for entry in layout.experience { experience-entry(entry) }
    #v(1pt)
    #section-title(data.labels.sections.selected_projects, "section-projects")
    #grid(
      columns: (1fr, 1fr),
      column-gutter: 3.5mm,
      ..layout.proofs.map(proof-card),
    )
  ],
  [
    #compact-section(
      data.labels.sections.profile,
      "section-profile",
      text(size: 8.2pt, fill: ink)[#layout.profile],
    )
    #grid(
      columns: (1fr, 1fr),
      column-gutter: 2.5mm,
      row-gutter: 2.5mm,
      ..layout.metrics.map(metric),
    )
    #v(5pt)
    #compact-section(
      data.labels.sections.skills,
      "section-skills",
      [
        #for skill in layout.skills {
          text(size: 7.9pt, weight: 650, fill: ink)[#skill.label]
          linebreak()
          text(size: 7.4pt, fill: muted)[#skill.items.join(" · ")]
          v(3.2pt)
        }
      ],
    )
    #compact-section(
      data.labels.sections.education,
      "section-education",
      [
        #for item in layout.education {
          text(size: 7.9pt, weight: 650)[#item.degree]
          linebreak()
          text(size: 7.3pt, fill: muted)[#item.institution · #item.year]
          v(2.8pt)
        }
      ],
    )
    #compact-section(
      data.labels.sections.publications,
      "section-publications",
      [
        #text(size: 7.3pt, fill: muted)[#if layout.publication_boundary != none { layout.publication_boundary } else { data.publications_summary }]
        #v(2pt)
        #text(size: 7.1pt)[
          #for (index, item) in data.publication_links.enumerate() {
            if index > 0 { text(fill: muted)[ · ] }
            link(item.url)[#item.label]
          }
        ]
      ],
    )
    #compact-section(
      data.labels.sections.awards,
      "section-awards",
      [
        #for award in layout.credentials {
          text(size: 7.6pt, weight: 650)[#award.title]
          linebreak()
          text(size: 7pt, fill: muted)[#award.issuer · #award.year]
        }
      ],
    )
    #compact-section(
      data.labels.sections.languages,
      "section-languages",
      text(size: 7.3pt, fill: muted)[
        #for (index, item) in layout.languages.enumerate() {
          if index > 0 { [ · ] }
          strong(item.name)
          [ (#item.proficiency)]
        }
      ],
    )
  ],
)
