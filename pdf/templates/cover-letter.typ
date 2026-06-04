#import "../styles.typ": *
#import "header.typ": header

#let data = json("../.cache/letter.json")
#let lang = sys.inputs.at("lang", default: "en")
#let has-signature = sys.inputs.at("has-signature", default: "0") == "1"
#let letter = data.letter

#set page(paper: "a4", margin: page-margin)
#set text(font: font-family, size: size-body, fill: body-color)
#set par(leading: 0.6em, justify: true)

// Letterhead — reuses the CV header so the letter visually matches the CV.
#header(data.personal)
#v(10pt)

// Right-aligned date (DIN 5008).
#align(right)[#text(size: size-body)[#letter.date_display]]
#v(6pt)

// Recipient address block.
#if letter.recipient != none {
  let r = letter.recipient
  [
    #if "name" in r and r.name != none [#r.name \ ]
    #if "company" in r and r.company != none [#r.company \ ]
    #if "address" in r and r.address != none {
      let a = r.address
      if "street" in a [#a.street \ ]
      let pc-city = ()
      if "postal_code" in a { pc-city.push(a.postal_code) }
      if "city" in a { pc-city.push(a.city) }
      if pc-city.len() > 0 [#pc-city.join(" ")]
    }
  ]
  v(14pt)
}

// Subject (Betreff): accent + bold + a thin rule beneath (mirrors the header divider).
#text(weight: 700, fill: accent)[#letter.subject]
#v(3pt)
#line(length: 100%, stroke: 0.5pt + accent.lighten(40%))
#v(10pt)

// Salutation.
#letter.salutation
#v(8pt)

// Body blocks: paragraphs (with **bold** spans) and accent-bullet lists.
// Parsing lives in scripts/cover_letter_core.py so PDF + text never diverge.
#let render-spans(spans) = {
  for s in spans {
    if s.bold { text(weight: 700)[#s.text] } else { [#s.text] }
  }
}
#for blk in letter.body_blocks {
  if blk.at("type") == "bullet_list" {
    for (i, item) in blk.items.enumerate() {
      if i > 0 { v(2pt) }
      grid(
        columns: (8pt, 1fr),
        gutter: 4pt,
        text(fill: accent)[•],
        render-spans(item),
      )
    }
    parbreak()
  } else {
    render-spans(blk.spans)
    parbreak()
  }
}

#v(6pt)
// Closing + optional signature image + typed name.
#letter.closing
#v(4pt)
#if has-signature {
  image("/assets/signature.png", height: 36pt)
  v(2pt)
}
#letter.signer_name
