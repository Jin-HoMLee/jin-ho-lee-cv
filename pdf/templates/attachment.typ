// Reusable Editorial Continuity primitives for candidate-authored attachments.
//
// The CV keeps its own settled one-page projection. These primitives carry only
// the shared identity language into looser documents such as letters and lists:
// IBM Plex Sans, slate-blue ink, muted gold rules, pale proof surfaces, JHL,
// labeled contact text, and a quiet sand footer.

#let attachment-ink = rgb("#25384a")
#let attachment-blue = rgb("#55718c")
#let attachment-gold = rgb("#a17a45")
#let attachment-sand = rgb("#f6f0e5")
#let attachment-pale-blue = rgb("#edf2f5")
#let attachment-muted = rgb("#68747d")
#let attachment-rule = rgb("#d9d2c6")
#let attachment-font = "IBM Plex Sans"
#let attachment-body-size = 9pt
#let attachment-small-size = 7.3pt
#let attachment-label-size = 6.8pt

#let _attachment-handle(url) = {
  let s = url
  for prefix in (
    "https://linkedin.com/in/",
    "https://www.linkedin.com/in/",
    "https://github.com/",
    "https://www.github.com/",
  ) {
    if s.starts-with(prefix) {
      s = s.slice(prefix.len())
      break
    }
  }
  s
}

#let _attachment-site(url) = {
  let s = url
  for prefix in ("https://", "http://") {
    if s.starts-with(prefix) {
      s = s.slice(prefix.len())
      break
    }
  }
  if s.ends-with("/") { s = s.slice(0, s.len() - 1) }
  s
}

#let _attachment-contact(personal, show-phone: false) = {
  let parts = ()
  parts.push(link("mailto:" + personal.email)[#personal.email])
  if show-phone and "phone" in personal { parts.push(personal.phone) }

  let location = ()
  if "location" in personal {
    if "city" in personal.location { location.push(personal.location.city) }
    if "country" in personal.location { location.push(personal.location.country) }
  }
  if location.len() > 0 { parts.push(location.join(", ")) }

  if "linkedin" in personal.links and personal.links.linkedin != none {
    parts.push(link(personal.links.linkedin)[in/#_attachment-handle(personal.links.linkedin)])
  }
  if "github" in personal.links and personal.links.github != none {
    parts.push(link(personal.links.github)[gh/#_attachment-handle(personal.links.github)])
  }
  text(size: attachment-small-size, fill: attachment-muted)[#parts.join("  ·  ")]
}

#let _attachment-footer(personal, footer-label) = {
  let website = if "website" in personal.links and personal.links.website != none {
    _attachment-site(personal.links.website)
  } else {
    none
  }
  block(
    width: 100%,
    fill: attachment-sand,
    inset: (x: 4mm, y: 2mm),
    grid(
      columns: (1fr, auto),
      align: (left, right),
      text(size: attachment-label-size, weight: 600, fill: attachment-ink)[
        #upper(personal.name.given + " " + personal.name.family) · #upper(footer-label)
      ],
      text(size: attachment-label-size, fill: attachment-muted)[
        #if website != none { website + " · " }
        #counter(page).display()
      ],
    ),
  )
}

// Scope all page/text rules to the supplied document body so future variants
// can reuse the identity without copying page furniture or typography values.
#let attachment-document(title, author, personal, footer-label, body) = {
  set document(title: title, author: author)
  set page(
    paper: "a4",
    margin: (top: 11mm, bottom: 14mm, x: 15mm),
    footer: context { _attachment-footer(personal, footer-label) },
  )
  set text(font: attachment-font, size: attachment-body-size, fill: attachment-ink)
  set par(leading: 0.62em, justify: true)
  set heading(numbering: none)
  body
}

#let attachment-masthead(personal, document-label, date: none, show-phone: false) = {
  let monogram = if "monogram" in personal { personal.monogram } else { "JHL" }
  grid(
    columns: (16mm, 1fr, auto),
    column-gutter: 5mm,
    align: (left + horizon, left + horizon, right + horizon),
    box(
      width: 16mm,
      height: 16mm,
      fill: attachment-sand,
      stroke: 0.7pt + attachment-gold,
      radius: 1.2mm,
      align(center + horizon, text(size: 11pt, weight: 700, fill: attachment-ink)[#monogram]),
    ),
    [
      #text(size: 19pt, weight: 700, fill: attachment-ink)[
        #personal.name.given #personal.name.family
      ]
      #linebreak()
      #text(size: 9pt, weight: 500, fill: attachment-blue)[#personal.headline]
      #v(2.5pt)
      #_attachment-contact(personal, show-phone: show-phone)
    ],
    [
      #text(size: 6.8pt, weight: 700, fill: attachment-gold)[#upper(document-label)]
      #if date != none {
        linebreak()
        text(size: attachment-small-size, fill: attachment-muted)[#date]
      }
    ],
  )
  v(7pt)
  line(length: 100%, stroke: 0.7pt + attachment-rule)
}

#let attachment-section(title, destination: none) = [
  #heading(level: 1, outlined: true, bookmarked: true)[
    #text(size: 9.4pt, weight: 700, fill: attachment-ink)[#upper(title)]
  ]
  #if destination != none { label(destination) }
  #v(1.5pt)
  #line(length: 100%, stroke: 0.7pt + attachment-gold)
  #v(4.5pt)
]

#let attachment-recipient(recipient) = {
  block(
    width: 100%,
    fill: attachment-pale-blue,
    radius: 1.2mm,
    inset: (x: 5mm, y: 3.5mm),
    [
      #if "name" in recipient and recipient.name != none {
        text(weight: 600)[#recipient.name]
        linebreak()
      }
      #if "company" in recipient and recipient.company != none {
        text(recipient.company)
        linebreak()
      }
      #if "address" in recipient and recipient.address != none {
        let a = recipient.address
        if "street" in a { text(a.street); linebreak() }
        let pc-city = ()
        if "postal_code" in a { pc-city.push(a.postal_code) }
        if "city" in a { pc-city.push(a.city) }
        if pc-city.len() > 0 { text(pc-city.join(" ")) }
        if "country" in a { linebreak(); text(a.country) }
      }
    ],
  )
}

#let attachment-subject(subject) = {
  text(size: 12pt, weight: 700, fill: attachment-ink)[#subject]
  v(2pt)
  line(length: 100%, stroke: 0.7pt + attachment-gold)
}

#let attachment-link(url, label) = link(url)[#text(fill: attachment-blue, weight: 500)[#label]]

#let attachment-publication-meta(authors, year: none, venue: none, family: none) = {
  for (i, author) in authors.enumerate() {
    if i > 0 { [, ] }
    if family != none and author.starts-with(family + ",") {
      text(weight: 600)[#author]
    } else if author == "others" {
      emph[et al.]
    } else {
      author
    }
  }
  if year != none {
    if authors.len() > 0 { [ · ] }
    text(fill: attachment-blue, weight: 600)[#str(year)]
  }
  if venue != none {
    [ · ]
    text(size: attachment-small-size, fill: attachment-muted)[#venue]
  }
}
